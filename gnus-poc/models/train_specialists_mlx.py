"""
Train GNUS.ai specialist models using mlx-lm's internal LoRA trainer.

Specialists:
  - medical        -> mlx-community/Qwen3-30B-A3B-Instruct-2507-bf16
  - qa_technical   -> mlx-community/Qwen3-30B-A3B-Instruct-2507-bf16
  - code           -> mlx-community/Qwen3-Coder-30B-A3B-Instruct-bf16
  - encyclopedic   -> mlx-community/Qwen3-30B-A3B-Instruct-2507-bf16
  - patents        -> mlx-community/Qwen3-30B-A3B-Instruct-2507-bf16

Data:
  - data/specialists/<niche> (HF datasets saved with save_to_disk)
  - This script converts each to:
      data/specialists/<niche>_mlx/{train,valid}.jsonl
    with {"text": "..."} lines as mlx-lm docs specify.

Pipeline (per specialist):
  - Build args from mlx_lm.lora.CONFIG_DEFAULTS + overrides
  - mlx_lm.utils.load(model_id) -> model, tokenizer
  - mlx_lm.tuner.datasets.load_dataset(args, tokenizer) -> train/val/test
  - mlx_lm.lora.train_model(args, model, train_set, valid_set)
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
    "medical":      "mlx-community/Qwen3-30B-A3B-Instruct-2507-bf16",
    "qa_technical": "mlx-community/Qwen3-30B-A3B-Instruct-2507-bf16",
    "code":         "mlx-community/Qwen3-Coder-30B-A3B-Instruct-bf16",
    "encyclopedic": "mlx-community/Qwen3-30B-A3B-Instruct-2507-bf16",
    "patents":      "mlx-community/Qwen3-30B-A3B-Instruct-2507-bf16",
}

SPECIALISTS = list(SPECIALIST_BASE_MODELS.keys())

DATA_DIR = "data/specialists"
OUTPUT_DIR = "models/specialists_mlx"
Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

# Our overrides relative to CONFIG_DEFAULTS in mlx_lora.lora
OVERRIDES = {
    "fine_tune_type": "lora",    # LoRA/QLoRA
    "optimizer": "adamw",
    "batch_size": 4,
    "iters": 1000,               # drop to 200–400 while testing if needed
    "val_batches": 25,
    "learning_rate": 1e-5,
    "steps_per_report": 50,
    "steps_per_eval": 200,
    "save_every": 200,
    "num_layers": 16,            # how many layers to LoRA-ize (see docs)
    "grad_checkpoint": True,
    "grad_accumulation_steps": 1,
    "mask_prompt": False,
    "report_to": None,
    "project_name": None,
    "seed": 42,
    "lora_parameters": {
        "rank": 16,
        "dropout": 0.05,
        "scale": 20.0,
    },
}


def prepare_dataset_for_mlx(niche_name: str) -> str:
    """
    Convert HF dataset (save_to_disk) into MLX-LM JSONL format:
      data/specialists/<niche>_mlx/{train,valid}.jsonl

    Each line: {"text": "..."}  (mlx-lm LORA.md 'text' format).
    """
    ds_path = f"{DATA_DIR}/{niche_name}"
    print(f"\nLoading HF dataset for {niche_name} from {ds_path} ...")
    ds = load_from_disk(ds_path)

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
        f"✓ Prepared MLX JSONL data for {niche_name}: "
        f"{len(ds['train']):,} train, {len(ds['validation']):,} val -> {mlx_data_dir}"
    )
    return mlx_data_dir


def build_args_for_niche(
    niche_name: str,
    base_model: str,
    data_dir: str,
    adapter_path: str,
) -> SimpleNamespace:
    """
    Build args namespace exactly like mlx_lm.lora.run() would,
    but we call train_model() directly instead of run().
    """
    # Start from upstream defaults
    args = dict(mlx_lora.CONFIG_DEFAULTS)

    # Core options
    args["model"] = base_model
    args["train"] = True
    args["test"] = False
    args["data"] = data_dir
    args["adapter_path"] = adapter_path

    # Force local JSONL mode, not HF dataset mode
    args["hf_dataset"] = False

    # No resume
    args["resume_adapter_file"] = None

    # Apply our overrides
    for k, v in OVERRIDES.items():
        args[k] = v

    # Reasonable project name for logging if used
    if args.get("project_name") is None:
        args["project_name"] = f"gnus_{niche_name}"

    return SimpleNamespace(**args)


def train_specialist(niche_name: str):
    base_model = SPECIALIST_BASE_MODELS[niche_name]

    print("\n" + "=" * 80)
    print(f"TRAINING {niche_name.upper()} SPECIALIST")
    print(f"Base model: {base_model}")
    print("=" * 80)

    # 1) Prepare data for MLX
    data_dir = prepare_dataset_for_mlx(niche_name)

    # 2) Adapter output path
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

    # 4) Load model+tokenizer via mlx-lm utils
    print("\nLoading pretrained model via mlx_lm.utils.load() ...")
    model, tokenizer = mlx_utils.load(
        args.model,
        tokenizer_config={"trust_remote_code": True},
    )

    # 5) Load datasets via official loader
    print("Loading datasets via mlx_lm.tuner.datasets.load_dataset() ...")
    train_set, valid_set, test_set = mlx_load_dataset(args, tokenizer)

    # 6) Train via mlx_lm.lora.train_model() ONLY
    print("Calling mlx_lm.lora.train_model() ...\n")
    start = datetime.now()
    mlx_lora.train_model(args, model, train_set, valid_set, training_callback=None)
    duration = (datetime.now() - start).total_seconds() / 60.0

    # 7) Save metadata
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
    print(f"  Adapters+config under: {adapter_path}")
    return metadata


def main():
    print("GNUS.ai Specialist Training via mlx-lm.lora.train_model")
    print("=" * 80)
    print(f"Specialists: {', '.join(SPECIALISTS).upper()}")
    print("=" * 80)

    all_meta = {}
    total_start = datetime.now()

    for i, niche in enumerate(SPECIALISTS, 1):
        adapter_path = Path(OUTPUT_DIR) / niche
        final_adapter = adapter_path / "adapters.safetensors"

        print(f"\n\n{'#' * 80}")
        print(f"# SPECIALIST {i}/{len(SPECIALISTS)}: {niche.upper()}")
        print(f"{'#' * 80}")

        # --- NEW: skip if already trained ---
        if final_adapter.exists():
            print(f"✓ Skipping {niche.upper()} – adapters already exist at {final_adapter}")
            # Optionally load metadata if you want to summarize later
            meta_file = adapter_path / "training_metadata.json"
            if meta_file.exists():
                with meta_file.open() as f:
                    all_meta[niche] = json.load(f)
            continue
        # -------------------------------------

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
            print(f"{niche.upper()}: {meta['training_duration_minutes']:.1f} minutes")
        print(f"\nTotal time: {total_minutes:.1f} minutes")
        print(f"Average per specialist: {total_minutes / len(all_meta):.1f} minutes")
        print(f"\n✓ Adapters for all trained specialists are under {OUTPUT_DIR}/")
    else:
        print("✗ No specialists successfully trained")


if __name__ == "__main__":
    main()
