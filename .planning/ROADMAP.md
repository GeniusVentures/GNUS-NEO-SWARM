# Roadmap: GNUS-POC — ELM Training & Distillation Pipeline (v1.1)

## Overview

This roadmap covers the **v1.1 milestone**: building a Python pipeline in `gnus-poc/` to train, distill, evaluate, orchestrate, quantize, and deploy Expert Language Models (ELMs) for the Genius NEO-SWARM C++ engine. The teacher model is DeepSeek v4 pro API; the training platform is Apple Silicon macOS with MLX 0.30.0; the pipeline output is FP4-quantized specialist binaries consumed by the C++ `FP4Codec`.

**Current state:** 5 LoRA-adapted Qwen3-30B-MoE specialists exist (medical, code, qa_technical, encyclopedic, patents) with training scripts in a flat `gnus-poc/` layout. Two silent data-corrupting bugs exist (chat template mismatch, skip-on-existing false completions). No evaluation, distillation, orchestration, or deployment pipeline exists.

**Exit strategy:** FP4 binaries + `manifest.json` + subspace vectors — consumed by C++ engine Phase 4+ as pre-quantized adapters.

## Phases

- [ ] **Phase 1: Foundation & Bug Fixes** — Fix silent data-corrupting bugs, restructure directories, establish YAML config hierarchy
- [ ] **Phase 2: Teacher API & Synthetic Data Generation** — DeepSeek v4 pro API client with cost controls, synthetic data generator
- [ ] **Phase 3: Training Hardening** — Centralize configs, memory safety, status tracking, cross-niche deduplication
- [ ] **Phase 4: Evaluation & Experiment Tracking** — Per-specialist eval, benchmarking, MLflow experiment tracking
- [ ] **Phase 5: Knowledge Distillation** — Logit-based distillation with temperature sweep, optional subspace extraction
- [ ] **Phase 6: Orchestration & Pipeline Unification** — Single-command DAG runner, CLI entry point, checkpoint detection
- [ ] **Phase 7: FP4 Quantization & Deployment** — FP4 binary export, manifest catalog, round-trip C++ validation

## Phase Details

### Phase 1: Foundation & Bug Fixes
**Goal**: The existing gnus-poc codebase is structurally sound, bug-free, and ready for new capability development.
**Depends on**: Nothing (first phase)
**Requirements**: FOUND-01, FOUND-02, FOUND-03, FOUND-04
**Success Criteria** (what must be TRUE):
1. Running `prepare_datasets.py` and then training on its output produces coherent completions — the chat template used during data prep matches what `train_specialists_mlx.py` consumes (no garbled tokens from template mismatch)
2. A partially-trained specialist (e.g., iteration 200/1000) is NOT recognized as complete by the skip-on-existing check; only a specialist with `training_metadata.json` reporting `iters == configured_iters` passes. The `--force-retrain` flag bypasses the check
3. All existing scripts run from their new module locations (`data/scripts/`, `training/`) without import errors, broken relative paths, or missing dependencies
4. YAML config hierarchy loads correctly: `pipeline.yaml` → per-specialist overrides → experiment overrides, with `${DEEPSEEK_API_KEY}` resolved from environment at load time
**Plans**: 3 plans

Plans:
- [ ] 01-01-PLAN.md — Bug fixes: chat template mismatch (FOUND-01) + skip-on-existing false completions (FOUND-02)
- [ ] 01-02-PLAN.md — Directory restructure: move scripts, fix paths, delete stale files (FOUND-03)
- [ ] 01-03-PLAN.md — Config & test infrastructure: YAML hierarchy, pytest skeleton, .gitignore (FOUND-04)

### Phase 2: Teacher API & Synthetic Data Generation
**Goal**: The pipeline can generate high-quality synthetic training data using the DeepSeek v4 pro API, with cost controls active from day one.
**Depends on**: Phase 1 (needs YAML config for API key resolution and directory structure for output)
**Requirements**: DATA-01, DATA-02
**⚠️ Gating Decision**: Teacher licensing (Pitfall #6) — user must resolve whether DeepSeek v4 pro API ToS permits synthetic data generation for training derivative models before any API code is written. Fallback: open-source teacher model (DeepSeek-V3, Llama 3.1, Qwen 3).
**Success Criteria** (what must be TRUE):
1. Running `TeacherClient.generate()` with a valid prompt returns a completion from the DeepSeek v4 pro API; running it 5 consecutive times against a failing endpoint triggers exponential backoff and stops after `max_retries=3`
2. Attempting to generate data that would exceed the configured `budget_cap` (e.g., $10) raises `BudgetExceededError` and logs cumulative cost — no further API calls are made
3. Running `SyntheticDataGenerator.generate_for_niche("medical", num_samples=100)` against a mock teacher API produces 100 valid JSONL entries in `data/synthetic/medical/` with `prompt`, `completion`, and `quality_score` fields
**Plans**: TBD

### Phase 3: Training Hardening
**Goal**: Training is production-grade — configs are centralized, memory is checked before OOM, results are tracked, and data contamination across niches is eliminated.
**Depends on**: Phase 1 (needs directory structure), Phase 2 (synthetic data may augment training sets)
**Requirements**: TRAIN-01, TRAIN-02, TRAIN-03, TRAIN-04, DATA-03
**Success Criteria** (what must be TRUE):
1. Changing a LoRA hyperparameter (e.g., `lora_rank=32`) in `TrainingConfig` and passing it to `SpecialistTrainer.train()` produces a trained adapter with that rank — no `OVERRIDES` dicts remain scattered across training scripts
2. Running training on a machine with insufficient RAM (e.g., `batch_size=32` on a 64GB Mac Studio) prints a pre-flight warning recommending qLoRA or reduced `batch_size` BEFORE allocating any GPU memory
3. After training completes or fails, `TRAINING_STATUS.json` exists in the specialist directory containing `final_train_loss`, `best_val_loss`, `perplexity`, `iterations`, and `duration_seconds`
4. Training two specialists on overlapping niche data logs a deduplication report showing Jaccard overlap percentage and count of duplicate samples removed before training starts
**Plans**: TBD

### Phase 4: Evaluation & Experiment Tracking
**Goal**: Every trained specialist can be quantitatively evaluated against baselines, and experiments are tracked for cross-run comparison.
**Depends on**: Phase 3 (needs trained specialists and validation metrics to evaluate)
**Requirements**: EVAL-01, EVAL-02, EVAL-03
**Success Criteria** (what must be TRUE):
1. Running `Evaluator.evaluate()` on a trained medical specialist produces an `EvalResult` with `accuracy`, `perplexity`, and `avg_latency_ms` — all three fields populated from MLX native inference on the held-out test set
2. Running `Benchmarker.benchmark()` across two training variants (e.g., rank-16 vs. rank-32) produces a human-readable comparison table showing which variant scores higher on each metric
3. MLflow experiment tracking is active: two training runs with different hyperparameters are visible in `mlflow ui` as separate runs with logged params, metrics, loss curves, and evaluation artifacts, comparable side-by-side
**Plans**: TBD

### Phase 5: Knowledge Distillation
**Goal**: Specialists can be distilled from the teacher model using logit-based transfer with temperature calibration, producing higher-quality adapters than direct LoRA training alone.
**Depends on**: Phase 2 (needs teacher API for logit extraction), Phase 4 (needs evaluation to measure distillation quality)
**Requirements**: DISTILL-01, DISTILL-02, DISTILL-03 (optional)
**Success Criteria** (what must be TRUE):
1. Running `Distiller.distill()` on a medical specialist trains a distilled adapter whose KL divergence from teacher logits decreases over training iterations (logged to MLflow)
2. Running the temperature sweep framework with temperatures `[0.5, 1.0, 2.0, 4.0]` produces a summary identifying the optimal temperature (lowest student eval loss) per specialist
3. *(Optional)* Running `Distiller.extract_subspace_vector()` on a trained adapter produces a float32 NumPy array that can be written to `artifacts/adapters/subspace_vectors.npy` for C++ router consumption
**Plans**: TBD

### Phase 6: Orchestration & Pipeline Unification
**Goal**: The entire pipeline runs end-to-end with a single command, respecting stage dependencies and supporting checkpoint-based resumption.
**Depends on**: Phase 3 (training stage must exist), Phase 4 (eval stage must exist), Phase 5 (distillation stage must exist)
**Requirements**: ORCH-01, ORCH-02, ORCH-03
**Success Criteria** (what must be TRUE):
1. Running `python orchestrate.py --niche medical` executes the full DAG (data → train → eval → distill → quantize) in dependency order, producing FP4 binaries in `artifacts/adapters/` for the medical specialist
2. Running the same command a second time skips all completed stages with log messages (e.g., `Stage 'train' already complete — skipping`); running with `--force-retrain` re-executes training regardless
3. Running `orchestrate.py --from-stage eval --niche medical` skips data preparation and training, starting execution at evaluation
4. All pipeline runs are grouped under a single MLflow parent run with child runs per stage, hyperparameters logged at pipeline start, and a summary report at pipeline end
**Plans**: TBD
**UI hint**: yes

### Phase 7: FP4 Quantization & Deployment
**Goal**: Trained/distilled specialists are exported as FP4-packed binaries consumable by the C++ engine, with verified round-trip fidelity and a complete manifest catalog.
**Depends on**: Phase 3 (needs trained adapters to quantize), Phase 5 (distilled adapters are the preferred quantization source)
**Requirements**: DEPLOY-01, DEPLOY-02, DEPLOY-03
**Success Criteria** (what must be TRUE):
1. Running `FP4Exporter.export_adapter()` on a trained medical specialist produces `<niche>_fp4.bin` and `<niche>_fp4_meta.json` in `artifacts/adapters/` — the binary is approximately 4× smaller than the original safetensors
2. `manifest.json` exists in `artifacts/adapters/` listing all exported specialists with checksums, LoRA signatures, evaluation scores, FP4 binary paths, and tokenizer config — matching the contract in `ARCHITECTURE.md` Section 5.3
3. Round-trip validation passes: Python quantize → write binary → C++ `FP4Codec` parse → dequantize → compare reports MSE < 1e-6 against original weights
**Plans**: TBD

## Inter-Phase Dependency Chain

```
Phase 1 (Foundation & Bug Fixes) ─────────────────────────────────────────────────────►
    │         │
    │         └────────────────────────────────────────────────────────────────────────┐
    ▼                                                                                  │
Phase 2 (Teacher API & Synthetic Data) ──────┐                                        │
    │                                         │                                        │
    ▼                                         ▼                                        │
Phase 3 (Training Hardening) ───────────────────────────────────────┐                  │
    │         │                                                      │                  │
    │         └───────────────────────────┐                          │                  │
    ▼                                     │                          ▼                  │
Phase 4 (Evaluation & Tracking) ──┐       │               Phase 5 (Distillation)       │
    │                             │       │                      │                     │
    │                             │       │                      │                     │
    ├─────────────────────────────┤       │                      │                     │
    ▼                             ▼       ▼                      ▼                     ▼
Phase 6 (Orchestration) ◄── Needs all stages built before orchestrator can wrap them ──┘
    │
    ▼
Phase 7 (FP4 Quantization & Deployment) ◄── Needs trained/distilled adapters to quantize
```

**Hard dependencies:**
- **Phase 2 → Phase 1**: YAML config and directory structure required for API client and output paths
- **Phase 3 → Phase 2**: Synthetic data may augment training sets (soft dep — pipeline runs on source data alone if teacher API unavailable)
- **Phase 4 → Phase 3**: Needs trained specialists and `TRAINING_STATUS.json` to evaluate
- **Phase 5 → Phase 2 + Phase 4**: Needs teacher API for logit extraction AND evaluation framework to measure distillation quality
- **Phase 6 → Phase 3, 4, 5**: The orchestrator wraps stages that must exist first
- **Phase 7 → Phase 3, 5**: Needs trained/distilled adapters to quantize

**Partially parallelizable:**
- Phase 7 (FP4 quantize) can begin development in parallel with Phase 5 (distillation) and Phase 6 (orchestration), since it depends on having trained adapters (Phase 3 output), not on distillation or orchestration being complete. Final integration validation requires full pipeline output.

**Gating risks:**
- **Teacher licensing decision (Phase 2)**: User must resolve DeepSeek v4 pro API ToS compliance before any API code. If rejected, fallback to open-source teacher model changes Phase 2 implementation significantly.
- **API cost control (Phase 2)**: Hard dollar budget cap must be implemented before any API call — retrofitting after an incident is too late.
- **C++ `FP4Codec` alignment (Phase 7)**: Binary format must match the C++ codec spec exactly. Round-trip test is non-negotiable.

## Progress

| Phase | Plans Complete | Status |
|-------|----------------|--------|
| 1. Foundation & Bug Fixes | 0/3 | Planned |
| 2. Teacher API & Synthetic Data | 0/3 | Not started |
| 3. Training Hardening | 0/5 | Not started |
| 4. Evaluation & Experiment Tracking | 0/3 | Not started |
| 5. Knowledge Distillation | 0/3 | Not started |
| 6. Orchestration & Pipeline Unification | 0/3 | Not started |
| 7. FP4 Quantization & Deployment | 0/3 | Not started |

---
*Last updated: 2026-05-27 — Milestone v1.1 gnus-poc roadmap created*
