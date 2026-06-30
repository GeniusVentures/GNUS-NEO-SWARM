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
import argparse
import shutil
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import yaml

from datasets import load_from_disk
from mlx_lm import utils as mlx_utils
from mlx_lm import lora as mlx_lora
from mlx_lm.tuner.datasets import load_dataset as mlx_load_dataset

from training.config import TrainingConfig, validate_hyperparameters
from training.validation import validate_adapter

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Default validation loss threshold when a specialist YAML has no
# ``validation.validation_loss_threshold`` (D-07). See RESEARCH.md Pattern 2.
DEFAULT_VALIDATION_LOSS_THRESHOLD = 3.0

# Map each specialist to its base model
SPECIALIST_BASE_MODELS = {
    "medical":      "mlx-community/Qwen3-30B-A3B-Instruct-2507-bf16",
    "qa_technical": "mlx-community/Qwen3-30B-A3B-Instruct-2507-bf16",
    "code":         "mlx-community/Qwen3-Coder-30B-A3B-Instruct-bf16",
    "encyclopedic": "mlx-community/Qwen3-30B-A3B-Instruct-2507-bf16",
    "patents":      "mlx-community/Qwen3-30B-A3B-Instruct-2507-bf16",
}

SPECIALISTS = list(SPECIALIST_BASE_MODELS.keys())

DATA_DIR = str(PROJECT_ROOT / "data" / "specialists")
OUTPUT_DIR = str(PROJECT_ROOT / "models" / "specialists_mlx")
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


def _read_validation_config(niche_name: str) -> tuple[float, Path]:
    """Read validation_loss_threshold and test_split_path for a specialist (D-07).

    Reads the ``validation`` block from ``config/specialists/<niche>.yaml``.
    Falls back to DEFAULT_VALIDATION_LOSS_THRESHOLD and the canonical
    ``data/specialists/<niche>/test.jsonl`` path when the block is absent so
    validation can run before specialist YAMLs are updated.

    Args:
        niche_name: Specialist niche key.

    Returns:
        (validation_loss_threshold, test_split_path) tuple.
    """
    spec_yaml = PROJECT_ROOT / "config" / "specialists" / f"{niche_name}.yaml"
    threshold = DEFAULT_VALIDATION_LOSS_THRESHOLD
    test_split_path = Path(DATA_DIR) / niche_name / "test.jsonl"

    if spec_yaml.exists():
        try:
            with spec_yaml.open() as f:
                cfg = yaml.safe_load(f) or {}
            validation = cfg.get("validation", {}) or {}
            threshold = float(
                validation.get("validation_loss_threshold", threshold)
            )
            configured_path = validation.get("test_split_path")
            if configured_path:
                test_split_path = PROJECT_ROOT / configured_path
        except (yaml.YAMLError, ValueError, TypeError) as e:
            print(f"  ⚠ Could not read validation config from {spec_yaml}: {e} "
                  f"— using defaults (threshold={threshold})")

    return threshold, test_split_path


def _load_test_samples(test_split_path: Path) -> list:
    """Load held-out test samples from JSONL (D-06: NOT training val_batches).

    Returns an empty list when the file is missing or unreadable so the
    validation pass can be skipped non-blockingly (Pitfall 4 avoidance).
    """
    if not test_split_path.exists():
        print(f"  ⚠ Test split not found at {test_split_path} — "
              f"skipping post-training validation (Pitfall 4: held-out set required)")
        return []

    samples = []
    try:
        with test_split_path.open() as f:
            for line in f:
                line = line.strip()
                if line:
                    samples.append(json.loads(line))
    except (json.JSONDecodeError, OSError) as e:
        print(f"  ⚠ Could not parse test split {test_split_path}: {e} — "
              f"skipping post-training validation")
        return []

    return samples


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

    # Validate hyperparameters before training starts (TRAIN-02, T-02-14).
    # Invalid combos raise ValueError, blocked before mlx_lora.train_model().
    hyperparam_config = TrainingConfig(
        batch_size=args["batch_size"],
        iters=args["iters"],
        learning_rate=args["learning_rate"],
        lora_rank=args["lora_parameters"]["rank"],
    )
    validate_hyperparameters(hyperparam_config)

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

    # 6.5) Post-training validation pass on held-out test set (D-06, D-08).
    # Non-blocking when test split is missing (Pitfall 4: held-out set required).
    validation_loss_threshold, test_split_path = _read_validation_config(niche_name)
    test_samples = _load_test_samples(test_split_path)
    validation_result = None
    training_status = "complete"
    if test_samples:
        print(f"\nRunning post-training validation on {len(test_samples)} "
              f"held-out test samples (threshold={validation_loss_threshold}) ...")
        try:
            validation_result = validate_adapter(
                model_id=base_model,
                adapter_path=str(adapter_path),
                test_samples=test_samples,
                loss_threshold=validation_loss_threshold,
            )
            if validation_result.get("load_error") is not None:
                training_status = "training_complete_adapter_not_loadable"
            elif not validation_result["overall_valid"]:
                training_status = "training_complete_validation_failed"
            print(f"  validation: overall_valid={validation_result['overall_valid']} "
                  f"loadable={validation_result['loadable']} "
                  f"loss_valid={validation_result['loss_valid']} "
                  f"behavioral_diff={validation_result['behavioral_diff']}")
        except Exception as e:
            print(f"  ⚠ Post-training validation raised (non-blocking): {e}")
            training_status = "training_complete_validation_error"
    else:
        print("\nSkipping post-training validation — no held-out test split available")

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
        "status": training_status,      # Reflects validation outcome (D-08)
        "dataset_hash": None,           # Placeholder — populated by data versioning in Phase 3
    }
    if validation_result is not None:
        metadata["validation"] = {
            "overall_valid": validation_result["overall_valid"],
            "loadable": validation_result["loadable"],
            "loss_valid": validation_result["loss_valid"],
            "validation_loss": validation_result["validation_loss"],
            "behavioral_diff": validation_result["behavioral_diff"],
            "jaccard_similarity": validation_result["jaccard_similarity"],
            "objective_errors": validation_result["objective_errors"],
            "subjective_diffs": validation_result["subjective_diffs"],
        }
    with open(f"{adapter_path}/training_metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)

    # Write TRAINING_STATUS.json for skip logic (FOUND-02)
    status = {
        "niche": niche_name,
        "iters_completed": args.iters,
        "status": training_status,
        "completed_at": datetime.now().isoformat(),
    }
    with open(f"{adapter_path}/TRAINING_STATUS.json", "w") as f:
        json.dump(status, f, indent=2)

    # Verify milestone file was written by MLX
    milestone_file = f"{args.iters:07d}_adapters.safetensors"
    expected_milestone = Path(adapter_path) / milestone_file
    if not expected_milestone.exists():
        print(f"  ⚠ Warning: Expected milestone file {milestone_file} not found — "
              f"training may have been interrupted before final save.")

    print(f"\n✓ Finished {niche_name.upper()} in {duration:.1f} minutes")
    print(f"  Adapters+config under: {adapter_path}")
    return metadata


def main():
    print("GNUS.ai Specialist Training via mlx-lm.lora.train_model")
    print("=" * 80)
    print(f"Specialists: {', '.join(SPECIALISTS).upper()}")
    print("=" * 80)

    # Parse --force-retrain flag (FOUND-02)
    parser = argparse.ArgumentParser(description="Train GNUS-POC specialist models")
    parser.add_argument(
        "--force-retrain",
        action="store_true",
        help="Delete existing adapters and retrain from scratch"
    )
    args = parser.parse_args()

    all_meta = {}
    total_start = datetime.now()

    for i, niche in enumerate(SPECIALISTS, 1):
        adapter_path = Path(OUTPUT_DIR) / niche
        final_adapter = adapter_path / "adapters.safetensors"

        print(f"\n\n{'#' * 80}")
        print(f"# SPECIALIST {i}/{len(SPECIALISTS)}: {niche.upper()}")
        print(f"{'#' * 80}")

        # --- Phase 1: Force retrain (FOUND-02) ---
        if args.force_retrain:
            if adapter_path.exists():
                print(f"🔁 Force retrain — deleting existing adapters for {niche.upper()}")
                shutil.rmtree(adapter_path)
            # Fall through to training below — no skip, no continue.

        # --- Phase 2 + 3: Skip-on-existing check (FOUND-02) ---
        elif final_adapter.exists():
            configured_iters = OVERRIDES["iters"]
            milestone_file = f"{configured_iters:07d}_adapters.safetensors"
            expected_milestone = adapter_path / milestone_file

            if not expected_milestone.exists():
                # Milestone file missing — training was interrupted or incomplete
                print(f"⚠ No milestone file {milestone_file} found — "
                      f"training from scratch (or resuming) for {niche.upper()}")
            else:
                # Milestone exists — validate metadata
                meta_file = adapter_path / "training_metadata.json"
                if meta_file.exists():
                    try:
                        with meta_file.open() as f:
                            meta = json.load(f)
                        meta_iters = meta.get("iters")
                        meta_status = meta.get("status")

                        if meta_iters == configured_iters and meta_status == "complete":
                            print(f"✓ Skipping {niche.upper()} — training complete "
                                  f"at iteration {meta_iters}")
                            all_meta[niche] = meta
                            continue
                        else:
                            print(f"⚠ Existing adapters appear incomplete "
                                  f"(metadata iters={meta_iters} vs configured {configured_iters}, "
                                  f"status={meta_status}) — retraining {niche.upper()}")
                    except (json.JSONDecodeError, KeyError) as e:
                        print(f"⚠ Could not read training_metadata.json: {e} — "
                              f"retraining {niche.upper()}")
                else:
                    print(f"⚠ No training_metadata.json found — "
                          f"retraining {niche.upper()}")
        # --- End skip check ---

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
