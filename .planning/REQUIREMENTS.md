# GNUS-POC ELM Training & Distillation Pipeline — Requirements v1.1

## Milestone v1.1: ELM Training & Distillation Pipeline (gnus-poc)

**Teacher model:** DeepSeek v4 pro API (MIT license, explicit distillation permission)
**Platform:** Apple Silicon macOS with MLX 0.30.0
**Output:** Trained/distilled ELM specialists, FP4 binaries for C++ engine consumption

## Active Requirements

### Foundation & Bug Fixes

- [x] **FOUND-01**: Fix chat template mismatch — use `tokenizer.apply_chat_template()` from the actual loaded tokenizer, not hand-rolled `<|im_start|>` format, to match Qwen3-30B-A3B models in `train_specialists_mlx.py`
- [x] **FOUND-02**: Fix skip-on-existing false completions — check for milestone file matching configured `iters` (e.g., `0001000_adapters.safetensors`), validate `training_metadata.json` iters field, add `--force-retrain` flag
- [x] **FOUND-03**: Directory restructure — create module layout: `pipeline/`, `distill/`, `training/` (refactored from `models/`), `eval/`, `quantize/`, `config/`, `artifacts/`, `data/scripts/` (moved existing scripts)
- [x] **FOUND-04**: YAML config hierarchy — `pipeline.yaml` (global), `specialists/<niche>.yaml` (per-specialist overrides), `experiments/<exp>.yaml` (A/B test overrides), with `${ENV_VAR}` interpolation for API keys and budget caps

### Data Pipeline

- [ ] **DATA-01**: Teacher API client — `TeacherClient` using `openai` SDK with `base_url="https://api.deepseek.com"`, retry/backoff via `tenacity`, hard dollar budget cap via config, per-call cost tracking logged to MLflow
- [ ] **DATA-02**: Synthetic data generation — per-niche prompt templates, output quality filtering (min length, relevance scoring, valid JSONL), output to `data/specialists/<niche>/synthetic/`
- [ ] **DATA-03**: Cross-niche deduplication — MinHash or Jaccard overlap computation between niche datasets, dedup before training, log overlap percentage in metadata

### Training

- [ ] **TRAIN-01**: TrainingConfig dataclass — single source of truth for all LoRA hyperparameters (rank, alpha, dropout, scale, iters, batch_size, num_layers, learning_rate, etc.), extracted from scattered `OVERRIDES` dicts in `train_specialists_mlx.py`
- [ ] **TRAIN-02**: Pre-flight memory estimator — check `psutil` available RAM against estimated model+optimizer requirements, warn/recommend qLoRA or reduced batch_size before training starts
- [ ] **TRAIN-03**: Structured per-specialist status — `TRAINING_STATUS.json` with `final_train_loss`, `best_val_loss`, `perplexity`, loss curves, iteration count, training duration; write on completion or failure
- [ ] **TRAIN-04**: SpecialistTrainer wrapper — wraps `mlx_lm.lora.train_model()` with MLflow logging (`mlflow.log_params`, `mlflow.log_metrics`), post-training adapter load test, structured error reporting

### Evaluation

- [ ] **EVAL-01**: Per-specialist evaluator — compute perplexity, generation accuracy (exact match / BLEU / ROUGE), and token latency on held-out test sets using MLX native inference
- [ ] **EVAL-02**: Benchmarker — head-to-head comparison across training variants (differing LoRA ranks, layer counts, batch sizes), produce comparison table output
- [ ] **EVAL-03**: Standard benchmarks — `lm-eval` integration via HF backend for MMLU, HellaSwag, ARC, GSM8K on base models; custom MLX evaluation scripts for LoRA-adapted specialists

### Knowledge Distillation

- [ ] **DISTILL-01**: Logit-based distillation — temperature-scaled KL divergence loss from teacher logprobs (DeepSeek API `logprobs=True`) to student output distribution, combined with standard cross-entropy loss
- [ ] **DISTILL-02**: Temperature sweep framework — grid search over temperature values per specialist, log optimal temperature to config
- [ ] **DISTILL-03**: *(Optional)* Subspace extraction — SVD on teacher logit matrices to produce subspace vectors for C++ router consumption; research spike, may be deferred

### Orchestration

- [ ] **ORCH-01**: PipelineRunner — single-command DAG executing stages in dependency order (data → train → eval → distill → quantize), checkpoint detection (skip completed, retry failed), reads YAML config
- [ ] **ORCH-02**: CLI entry point — `orchestrate.py` with `--niche`, `--from-stage`, `--config`, `--force-retrain`, `--budget-cap` flags
- [ ] **ORCH-03**: Experiment tracking — MLflow run grouping per pipeline execution, hyperparameter logging, artifact management, cross-run comparison UI via `mlflow ui`

### Deployment

- [ ] **DEPLOY-01**: FP4 exporter — convert LoRA safetensors to FP4-packed binary matching C++ `FP4Codec` spec in `src/core/fp4/FP4Codec.hpp`, using MLX native `mlx.core.quantize()`
- [ ] **DEPLOY-02**: Manifest catalog — `manifest.json` per specialist with model checksums, LoRA adapter signature, training metadata, tokenizer config, FP4 binary paths, and versioning
- [ ] **DEPLOY-03**: Round-trip validation — Python quantize → write binary → read with C++ parser → dequantize → compare MSE against original weights; acceptable threshold: MSE < 1e-6

## Future Requirements (deferred to v1.2+)

- Multi-teacher distillation (cost/latency prohibitive for v1.1)
- Full pretraining from scratch
- Real-time inference serving endpoint
- Human feedback LoRA retraining loops (requires swarm runtime)
- Dynamic adapter hot-swapping (C++ runtime concern)
- AutoML hyperparameter optimization (Optuna/Ray Tune)
- Distributed training across multiple Macs (swarm networking Phase 6+)

## Out of Scope

- C++ engine Phase 4 ELM integration (separate workstream)
- Flutter/UI changes
- gRPC server modifications
- Network/P2P integration
- Any changes outside `gnus-poc/` directory (except .gitignore)

## Traceability

| REQ-ID | Requirement | Category | Phase | Status |
|--------|-------------|----------|-------|--------|
| FOUND-01 | Fix chat template mismatch | Foundation | Phase 1 | Pending |
| FOUND-02 | Fix skip-on-existing false completions | Foundation | Phase 1 | Pending |
| FOUND-03 | Directory restructure | Foundation | Phase 1 | Pending |
| FOUND-04 | YAML config hierarchy | Foundation | Phase 1 | Pending |
| DATA-01 | Teacher API client | Data | Phase 2 | Pending |
| DATA-02 | Synthetic data generation | Data | Phase 2 | Pending |
| DATA-03 | Cross-niche deduplication | Data | Phase 3 | Pending |
| TRAIN-01 | TrainingConfig dataclass | Training | Phase 3 | Pending |
| TRAIN-02 | Pre-flight memory estimator | Training | Phase 3 | Pending |
| TRAIN-03 | Structured per-specialist status | Training | Phase 3 | Pending |
| TRAIN-04 | SpecialistTrainer wrapper | Training | Phase 3 | Pending |
| EVAL-01 | Per-specialist evaluator | Evaluation | Phase 4 | Pending |
| EVAL-02 | Benchmarker | Evaluation | Phase 4 | Pending |
| EVAL-03 | Standard benchmarks | Evaluation | Phase 4 | Pending |
| DISTILL-01 | Logit-based distillation | Distillation | Phase 5 | Pending |
| DISTILL-02 | Temperature sweep | Distillation | Phase 5 | Pending |
| DISTILL-03 | Subspace extraction (optional) | Distillation | Phase 5 | Pending |
| ORCH-01 | PipelineRunner | Orchestration | Phase 6 | Pending |
| ORCH-02 | CLI entry point | Orchestration | Phase 6 | Pending |
| ORCH-03 | Experiment tracking | Orchestration | Phase 6 | Pending |
| DEPLOY-01 | FP4 exporter | Deployment | Phase 7 | Pending |
| DEPLOY-02 | Manifest catalog | Deployment | Phase 7 | Pending |
| DEPLOY-03 | Round-trip validation | Deployment | Phase 7 | Pending |

---
*Last updated: 2026-05-27 — Milestone v1.1 requirements + traceability with phase mappings*
