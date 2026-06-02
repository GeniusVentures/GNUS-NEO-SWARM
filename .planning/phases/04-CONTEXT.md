# Phase 4: Evaluation & Experiment Tracking — Context

**Gathered:** 2026-05-27
**Status:** Ready for planning
**Mode:** Auto-generated (smart discuss)

## Phase Boundary

Build per-specialist evaluation metrics, head-to-head benchmark comparison across training variants, and MLflow experiment tracking integration.

**In scope:**
- EVAL-01: Per-specialist evaluator — perplexity, BLEU/ROUGE, latency on held-out test sets via MLX
- EVAL-02: Benchmarker — head-to-head comparison across training variants
- EVAL-03: Standard benchmarks — lm-eval integration (base models only, HF backend)
- ORCH-03: Experiment tracking — MLflow run grouping, hyperparameter logging, artifact management

**Out of scope:**
- Distillation evaluation (Phase 5)
- Pipeline orchestration CLI (Phase 6)
- Real API benchmarks (needs running models)

## Implementation Decisions

### Metrics per niche
Perplexity (primary), BLEU/ROUGE via nltk (already installed), latency in ms/token. All computed on held-out test sets via MLX native inference.

### Benchmarker output
JSON to `artifacts/benchmarks/<niche>_<variant>.json`. Comparison table printed to stdout with columns: niche, variant, perplexity, BLEU, latency, params.

### MLflow experiment tracking
Install mlflow, wrap training sessions in `mlflow.start_run()`, log params (from TrainingConfig) and metrics. Use `mlflow ui` for visual comparison. Config hash (SHA256 of TrainingConfig) as experiment ID.

### lm-eval integration
Install `lm_eval[hf]`. Run MMLU, HellaSwag, ARC, GSM8K on base Qwen3 models via HF backend for calibration baselines. LoRA-adapted specialists use custom MLX eval scripts (lm-eval doesn't support MLX).

## Deferred Ideas
- Optuna hyperparameter optimization (v1.2+)
- Real-time eval dashboard (v2+)
- Multi-model benchmark suite
