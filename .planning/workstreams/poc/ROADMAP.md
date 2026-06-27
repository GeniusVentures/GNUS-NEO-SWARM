# Roadmap: gnus-poc

## Overview

gnus-poc evolves from a fragile sequential training script into a hardened ELM training and distillation pipeline with benchmark-validated quality gates. The roadmap progresses through four phases: **hardening** (Phase 1, making the pipeline production-grade), **training quality** (Phase 2, KD convergence + evaluation + rules-based routing), **quantization** (Phase 3, SGFP4 v2 adaptive macroblock dual-mode export), and **benchmark validation** (Phase 4, established suite scoring as quality gate).

Scope is bounded to what a Python training pipeline can prove. Distributed swarm execution, EGGROLL retraining, GAML memory, reputation/consensus, Tool Intermediary, and epistemic arbitration belong to the GNUS-NEO-SWARM C++ parent repo — not gnus-poc.

## Phases

- [ ] **Phase 1: Pipeline Hardening** — Multi-teacher cascade with dual-backend API, subprocess pipeline execution, budget persistence, retry/circuit breaker, validated checkpoints
- [ ] **Phase 2: Training & Distillation Quality** — KD convergence with temperature sweeping, valid LoRA adapters, evaluation metrics, rules-based specialist routing
- [ ] **Phase 3: FP4 Quantization & Artifact Integrity** — SGFP4 v2 adaptive macroblock export with quadtree partitioning, Laplacian error analysis, dual-mode selection, and provenance manifests
- [ ] **Phase 4: Benchmark Evaluation** — Established benchmark suite scoring as quality gate with manual feedback loop to distillation

## Phase Details

### Phase 1: Pipeline Hardening
**Goal**: The 7-stage training pipeline executes reliably end-to-end with multi-teacher cascade, dual-backend API (OpenAI + Anthropic), budget enforcement, retry with exponential backoff, circuit breaker protection, and validated checkpoints.
**Depends on**: Nothing (first phase)
**Requirements**: PIPE-01, PIPE-02, PIPE-03, TEACH-01, TEACH-02, TEACH-03, TEACH-04, TEACH-05
**Success Criteria** (what must be TRUE):
  1. Pipeline completes all 7 stages for all 5 specialist niches without unhandled errors, producing verifiable output artifacts at each stage.
  2. Multi-teacher cascade routes Level 1 (DSv4 Fast) always, escalating to domain-routed Level 2 when confidence below threshold. Benchmark table drives Level 2 selection.
  3. Both `openai` and `anthropic` API backends are functional — endpoint `apiType` determines which SDK is used per call.
  4. Pipeline checkpoints skip already-completed stages on re-run; `--from-stage` resumes from any stage; `--force` bypasses all checkpoints.
  5. Per-specialist YAML configs override global defaults at runtime; invalid configs produce descriptive error messages at load time.
  6. Budget cap stops all teacher API calls when cumulative spend exceeds the limit, with spend state persisted between runs.
  7. Retry with exponential backoff recovers from rate limits (429) and server errors (5xx); circuit breaker opens after consecutive failures and supports half-open recovery.
  8. Checkpoints validate stage outputs (file existence, content quality, schema) before marking complete — not just empty `.done` files.
**Plans**: 5 plans

Plans:
- [ ] 01-01-PLAN.md — Config layer: endpoints/models two-layer structure, benchmark table, ConfigLoader with validation and per-specialist overrides
- [ ] 01-02-PLAN.md — Multi-backend TeacherClient: OpenAI + Anthropic backend architecture with apiType dispatch
- [ ] 01-03-PLAN.md — Pipeline runner: subprocess execution, error-type handling, validated checkpoint system
- [ ] 01-04-PLAN.md — Multi-teacher cascade with benchmark routing, budget persistence, half-open circuit breaker
- [ ] 01-05-PLAN.md — Integration: update synthetic.py and distillation.py for new TeacherClient API

### Phase 2: Training & Distillation Quality
**Goal**: Knowledge distillation converges with configurable KD loss, temperature sweeping produces analysis data, specialist training produces valid LoRA adapters, evaluation persists metrics per run, and a rules-based router maps query patterns to specialists.
**Depends on**: Phase 1 (needs hardened pipeline and teacher client)
**Requirements**: DIST-01, DIST-02, DIST-03, TRAIN-01, TRAIN-02, TRAIN-03, ROUTE-01, ROUTE-02
**Success Criteria** (what must be TRUE):
  1. KD loss decreases over training steps and converges to below the configured `distill_loss_target` threshold.
  2. Temperature sweeping runs multiple distillation passes at configurable temperatures, producing per-temperature loss curves.
  3. Synthetic data passes quality checks: minimum length, no empty responses, deduplication by normalized text hash.
  4. LoRA adapter training produces loadable adapter weights that change inference behavior, with `training_metadata.json` recording loss and hyperparameters.
  5. Hyperparameters from YAML config are respected at runtime; invalid combinations produce clear validation errors.
  6. Model evaluation produces accuracy, perplexity, and latency metrics (mean/P95) persisted to `artifacts/evaluations/` per run.
  7. Rules-based router classifies queries by keyword/syntax patterns and selects appropriate specialists from YAML config.
**Plans**: TBD

### Phase 3: FP4 Quantization & Artifact Integrity
**Goal**: SGFP4 v2 adaptive quantized export produces variable-effective-bitrate models with quadtree block partitioning (4x4 through 64x64), encode-side Laplacian error analysis, dual-mode per-block encoding (FP4_AFFINE/T158_AFFINE), superblock layout enum, and provenance manifests with SHA256 integrity.
**Depends on**: Phase 2 (needs trained and evaluated specialists to quantize)
**Requirements**: QUANT-01, QUANT-02, QUANT-03
**Success Criteria** (what must be TRUE):
  1. SGFP4 v2 binary uses variable block sizes (4x4-64x64) selected by Laplacian-weighted error analysis with quadtree recursion, superblock layout enum, and variable payloads scaling with block area.
  2. Both FP4_AFFINE and T158_AFFINE mode errors are evaluated per block; T158 is selected when `err_t158 <= (1.0 + delta) * err_fp4`; mode flags in per-block header bits are set correctly.
  3. Model manifest records model_name, niche, base_model_ref, adapter_ref, quantization_params, encoder_version, timestamp_utc, and SHA256 hash for integrity verification.
  4. ConfigLoader validates fp4_export thresholds at load time; CheckpointValidator verifies SGFP4 v2 magic header and manifest integrity.
  5. SGFP4 quantization metrics (MSE, effective bitrate, T158 ratio) are persisted and gated via eval_gates with configurable thresholds.
**Plans**: 3 plans

Plans:
- [ ] 03-01-PLAN.md — FP4Exporter v2 upgrade: Laplacian analysis, quadtree encoder, variable payload, superblock layout, dual-mode, backward compatibility, manifest output
- [ ] 03-02-PLAN.md — Config extension: ConfigLoader._validate_fp4_export(), pipeline.yaml v2 thresholds, CheckpointValidator SGFP4 v2 output validation
- [ ] 03-03-PLAN.md — Eval gating: MetricStore for SGFP4 metrics, Benchmarker.gate_check() for quantization quality gates

### Phase 4: Benchmark Evaluation
**Goal**: Quantized specialist models are scored against established benchmark suites (MMLU, HumanEval, GSM8K, domain-specific) as a quality gate. Failed benchmarks feed back into distillation strategy refinement.
**Depends on**: Phase 3 (needs quantized models to benchmark)
**Requirements**: BMARK-01, BMARK-02, BMARK-03
**Success Criteria** (what must be TRUE):
  1. Each quantized specialist runs against its domain-relevant benchmark suite and produces structured scores.
  2. Benchmarks act as a quality gate — models below configurable thresholds are flagged for distillation refinement.
  3. Benchmark results persist with model identity, quantization config, and timestamp for trend analysis across runs.
  4. Failed benchmarks produce actionable feedback (which categories underperformed, by how much) to guide manual distillation strategy adjustments.
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Pipeline Hardening | 0/5 | Planned | - |
| 2. Training & Distillation Quality | 0/? | Not started | - |
| 3. FP4 Quantization & Artifact Integrity | 0/3 | Planned | - |
| 4. Benchmark Evaluation | 0/? | Not started | - |

## Scope Boundaries

**In scope (gnus-poc v1):**
- Multi-teacher cascade (DSv4 Fast → domain-routed Level 2)
- Dual-backend teacher API (OpenAI + Anthropic SDKs)
- 7-stage pipeline execution with validated checkpoints
- Budget enforcement, retry, circuit breaker
- Knowledge distillation with KD loss + temperature sweeping
- LoRA specialist training with MLX
- Model evaluation metrics (accuracy, perplexity, latency)
- Rules-based specialist routing (YAML config)
- SGFP4 v2 adaptive macroblock quantization with dual-mode selection, quadtree partitioning, and provenance manifests
- Benchmark evaluation gate (MMLU, HumanEval, GSM8K, domain suites)

**Deferred to parent repo (GNUS-NEO-SWARM C++):**
- EGGROLL swarm retraining and evolutionary optimization
- GAML agentic memory layer
- Reputation-weighted consensus
- Distributed swarm execution (libp2p, IPFS-lite)
- Tool Intermediary / secure agent architecture
- Epistemic arbitration / GQHSM
- Hierarchical Critical Thinking Specialists (HCTS)
- Multi-node beehive aggregation
