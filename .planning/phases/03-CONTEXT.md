# Phase 3: Training Hardening — Context

**Gathered:** 2026-05-27
**Status:** Ready for planning
**Mode:** Auto-generated (smart discuss)

## Phase Boundary

Centralize LoRA hyperparameters into a single TrainingConfig dataclass, add pre-flight memory safety checks, structured per-specialist status tracking, wrap MLX training with error handling and logging, and implement cross-niche deduplication.

**In scope:**
- TRAIN-01: TrainingConfig dataclass — single source of truth for all LoRA hyperparameters
- TRAIN-02: Pre-flight memory estimator — check available RAM before training
- TRAIN-03: Structured per-specialist status — TRAINING_STATUS.json with loss curves
- TRAIN-04: SpecialistTrainer wrapper — mlx_lm.lora.train_model() with MLflow logging
- DATA-03: Cross-niche deduplication — MinHash LSH, Jaccard threshold 0.3

**Out of scope:**
- MLflow integration (Phase 4)
- Evaluation metrics (Phase 4)
- Distillation (Phase 5)

## Implementation Decisions

### TrainingConfig dataclass
Location: `training/config.py`. Single `@dataclass` with 18 fields: fine_tune_type, optimizer, batch_size, iters, val_batches, learning_rate, steps_per_report, steps_per_eval, save_every, num_layers, grad_checkpoint, grad_accumulation_steps, mask_prompt, seed, lora_rank, lora_dropout, lora_scale, use_qlora. Class method `from_yaml()` loads from config YAML.

### qLoRA default
Enable 4-bit base quantization by default (`use_qlora: true` in config). Cuts memory ~75% for 30B-A3B models on 64GB Macs. Overridable per specialist.

### Cross-niche dedup
MinHash LSH with 128 permutations, Jaccard threshold 0.3. Run `deduplicate()` in prepare_datasets.py after all niches are collected, before train/val split. Log overlap matrix.

### Memory estimator
Use `psutil.virtual_memory().available`. If psutil not available, parse `subprocess.run(['sysctl', 'hw.memsize'])`. Warn if < 10GB headroom. Abort training if < 2GB headroom.

### Structured logging
JSON lines to `artifacts/training_logs/<niche>_<timestamp>.jsonl`. One record per training event: start, step_report, eval_result, completion, error. Consumed by MLflow in Phase 4.

## Deferred Ideas
- MLflow autolog (Phase 4)
- Optuna hyperparameter search (v1.2+)
