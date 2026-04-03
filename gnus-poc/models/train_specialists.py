"""
Train GNUS.ai specialist models using mlx-lm's internal LoRA trainer.

- No CLI, no subprocess, no quantized base.
- Each specialist uses the most appropriate Qwen3-7B base:
  - medical / qa_technical / encyclopedic / patents -> Qwen3-7B-Instruct
  - code -> Qwen3-7B-Coder

Assumes:
  - data/specialists/<niche> was created via prepare_datasets.py
  - Each <niche> dir is a HF dataset with 'train' and 'validation' splits
"""

import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from datasets import load_from_disk
from mlx_lm import utils as mlx_utils
from mlx_lm import lora as mlx_lora
from mlx_lm.tuner.datasets import load_dataset as mlx_load_dataset

# Map each specialist to its base model
SPECIALIST_BASE_MODELS = {
    "medical":        "Qwen/Qwen3-7B-Instruct",
    "qa_technical":   "Qwen/Qwen3-7B-Instruct",
    "code":           "Qwen/Qwen3-7B-Coder",
    "encyclopedic":   "Qwen/Qwen3-7B-Instruct",
    "patents":        "Qwen/Qwen3-7B-Instruct",
}

# All 5 specialists you prepared
SPECIALISTS = list(SPECIALIST_BASE_MODELS.keys())

DATA_DIR = "data/specialists"
OUTPUT_DIR = "models/specialists"
Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

# Our overrides relative to CONFIG_DEFAULTS in mlx_lora
OVERRIDES = {
    "fine_tune_type": "lora",    # use LoRA/QLoRA
    "optimizer": "adamw",
    "batch_size": 4,
    "iters": 1000,
    "val_batches": 25,
    "learning_rate": 1e-5,
    "steps_per_report": 50,
    "steps_per_eval": 200,
    "save_every": 200,
    "num_layers": 16,            # number of layers to LoRA-ize
    "grad_checkpoint": True,
    "grad_accumulation_steps": 1,
    "mask_prompt": False,
    "report_to": None,
    "project_name": None,
    "seed": 42,
    "lora_parameters": {         # MUST match what linear_to_lora_layers expects
        "rank": 16,
        "dropout": 0.05,
        "scale": 20.0,
    },
}


def prepare_dataset_for_mlx(niche_name: str) -> str:
    """
    Convert HF dataset (saved with save_to_disk) into MLX-LM JSONL format:
      <data_dir>_mlx/train.jsonl
      <data_dir>_mlx/valid.jsonl

    Each line: {"text": "..."}  (mlx-lm LORA.md 'text' format)
    """
    dataset_path = f"{DATA_DIR}/{niche_name}"
    print(f"\nPreparing {niche_name.upper()} dataset for MLX...")
    ds = load_from_disk(dataset_path)

    mlx_data_dir = f"{DATA_DIR}/{niche_name}_mlx"
    Path(mlx_data_dir).mkdir(exist_ok=True)

    train_file = Path(mlx_data_dir) / "train.jsonl"
    valid_file = Path(mlx_data_dir) / "valid.jsonl"

    with train_file.open("w") as f:
        for item in ds["train"]:
            f.write(json.dumps({"text": item["text"]}) + "\n")

    with valid_file.open("w") as f:
        for item in ds["validation"]:
            f.write(json.dumps({"text": item["text"]}) + "\n")

    print(
        f"✓ Dataset prepared for {niche_name}: "
        f"{len(ds['train']):,} train, {len(ds['validation']):,} val → {mlx_data_dir}"
    )
    return mlx_data_dir


def build_args_for_niche(
    niche_name: str,
    base_model: str,
    data_dir: str,
    adapter_path: str,
) -> SimpleNamespace:
    """
    Build args namespace compatible with mlx_lora.train_model(),
    starting from CONFIG_DEFAULTS and applying overrides + required fields.
    """
    # Start from upstream defaults; this keeps us in sync with mlx-lm
    args_dict = dict(mlx_lora.CONFIG_DEFAULTS)

    # Core training switches
    args_dict["model"] = base_model
    args_dict["train"] = True
    args_dict["test"] = False
    args_dict["data"] = data_dir
    args_dict["adapter_path"] = adapter_path

    # Explicitly avoid HF dataset mode; we are using local jsonl
    args_dict["hf_dataset"] = False

    # No resume for PoC
    args_dict["resume_adapter_file"] = None

    # Apply our overrides
    for k, v in OVERRIDES.items():
        args_dict[k] = v

    # Reasonable project name for logging
    if args_dict.get("project_name") is None:
        args_dict["project_name"] = f"gnus_{niche_name}"

    return SimpleNamespace(**args_dict)


def train_specialist(niche_name: str):
    print("\n" + "=" * 80)
    print(f"TRAINING {niche_name.upper()} SPECIALIST (mlx-lm.lora.train_model)")
    print("=" * 80)

    base_model = SPECIALIST_BASE_MODELS[niche_name]

    start = datetime.now()

    # 1) Prepare data in MLX expected format
    data_dir = prepare_dataset_for_mlx(niche_name)

    # 2) Where adapters + config will be written
    adapter_path = f"{OUTPUT_DIR}/{niche_name}"
    Path(adapter_path).mkdir(parents=True, exist_ok=True)

    # 3) Build args
    args = build_args_for_niche(niche_name, base_model, data_dir, adapter_path)

    print("\nArgs summary:")
    print(f"  model={args.model}")
    print(f"  data={args.data}")
    print(f"  adapter_path={args.adapter_path}")
    print(f"  iters={args.iters}, batch_size={args.batch_size}, num_layers={args.num_layers}")
    print(f"  fine_tune_type={args.fine_tune_type}, optimizer={args.optimizer}")

    # 4) Load model + tokenizer via mlx-lm utils
    print("\nLoading pretrained model via mlx_lm.utils.load()...")
    model, tokenizer = mlx_utils.load(
        args.model,
        tokenizer_config={"trust_remote_code": True},
    )

    # 5) Load datasets via official loader
    print("Loading datasets via mlx_lm.tuner.datasets.load_dataset()...")
    train_set, valid_set, test_set = mlx_load_dataset(args, tokenizer)

    # 6) Call official train_model (handles LoRA, optimizer, trainer)
    print("Calling mlx_lm.lora.train_model()...\n")
    mlx_lora.train_model(args, model, train_set, valid_set, training_callback=None)

    duration = (datetime.now() - start).total_seconds() / 60.0
    metadata = {
        "niche": niche_name,
        "base_model": base_model,
        "training_duration_minutes": duration,
        "trained_at": datetime.now().isoformat(),
        "iters": args.iters,
        "batch_size": args.batch_size,
        "num_layers": args.num_layers,
        "lora_parameters": args.lora_parameters,
    }

    with open(f"{adapter_path}/training_metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"\n✓ Finished {niche_name.upper()} in {duration:.1f} minutes")
    print(f"  Adapters/config saved under: {adapter_path}")
    return metadata


def main():
    print("GNUS.ai Specialist Training via mlx-lm.lora.train_model")
    print("=" * 80)
    print(f"Specialists ({len(SPECIALISTS)}): {', '.join(s.upper() for s in SPECIALISTS)}")
    print("=" * 80)

    all_meta = {}
    total_start = datetime.now()

    for i, niche in enumerate(SPECIALISTS, 1):
        print(f"\n\n{'#' * 80}")
        print(f"# SPECIALIST {i}/{len(SPECIALISTS)}: {niche.upper()}")
        print(f"{'#' * 80}")
        try:
            meta = train_specialist(niche)
            all_meta[niche] = meta
        except Exception as e:
            print(f"\n✗ Error training {niche}: {e}")
            import traceback
            traceback.print_exc()
            continue

    total_minutes = (datetime.now() - total_start).total_seconds() / 60.0

    print("\n\n" + "=" * 80)
    print("TRAINING COMPLETE")
    print("=" * 80)
    if all_meta:
        for niche, meta in all_meta.items():
            print(f"\n{niche.upper()}: {meta['training_duration_minutes']:.1f} minutes")
        print(f"\nTotal: {total_minutes:.1f} minutes")
        print(f"Average per specialist: {total_minutes / len(all_meta):.1f} minutes")
        print(f"\n✓ Adapters for all trained specialists are under {OUTPUT_DIR}/")
    else:
        print("✗ No specialists successfully trained")


if __name__ == "__main__":
    main()
