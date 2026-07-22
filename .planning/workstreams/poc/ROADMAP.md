# Roadmap: gnus-poc

## Overview

gnus-poc evolves from a fragile sequential training script into a hardened ELM training and distillation pipeline with benchmark-validated quality gates. The roadmap progresses through four phases: **hardening** (Phase 1, making the pipeline production-grade), **training quality** (Phase 2, KD convergence + evaluation + rules-based routing), **quantization** (Phase 3, SGFP4 dual-mode export), and **benchmark validation** (Phase 4, established suite scoring as quality gate).

Scope is bounded to what a Python training pipeline can prove. Distributed swarm execution, EGGROLL retraining, GAML memory, reputation/consensus, Tool Intermediary, and epistemic arbitration belong to the GNUS-NEO-SWARM C++ parent repo — not gnus-poc.

## Phases

- [x] **Phase 1: Pipeline Hardening** — Multi-teacher cascade with dual-backend API, subprocess pipeline execution, budget persistence, retry/circuit breaker, validated checkpoints
- [x] **Phase 2: Training & Distillation Quality** — KD convergence with temperature sweeping, valid LoRA adapters, evaluation metrics, rules-based specialist routing (completed 2026-06-21)
- [ ] **Phase 3: FP4 Quantization & Artifact Integrity** — SGFP4 v2 adaptive macroblock quantization (4×4 to 64×64), Laplacian error analysis, quadtree layout, dual-mode + Log mode, provenance manifests
- [ ] **Phase 4: Benchmark Evaluation** — Established benchmark suite scoring as quality gate with manual feedback loop to distillation
- [ ] **Phase 5: PTDS v4 Unsloth Integration** — Unsloth training backend (parallel to MLX), Teacher→Parent→Specialist 3-tier distillation, SGFP4 hybrid quantization, role-based specialist taxonomy

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
**Plans**: 5 plans

Plans:
- [x] 02-01-PLAN.md — Config extensions: training convergence, eval gates, router config, per-specialist thresholds
- [x] 02-02-PLAN.md — Convergence tracking: ConvergenceTracker with plateau detection, two-tier stopping, sweep analysis
- [x] 02-03-PLAN.md — Training quality validation: AdapterValidator with multi-prong checks, post-training validation
- [x] 02-04-PLAN.md — Evaluation metrics & gating: MetricStore, ThresholdAdapter, auto-gating, trend analysis
- [x] 02-05-PLAN.md — Rules-based router: GQHSM-compatible state machine, YAML-driven rule engine, fallback chaining

### Phase 3: FP4 Quantization & Artifact Integrity
**Goal**: SGFP4 v2 adaptive macroblock quantization — variable block sizes (4×4 to 64×64) with encode-side Laplacian error analysis, quadtree layout, dual-mode per-block selection (FP4_AFFINE/T158_AFFINE + Log mode), and provenance manifests with integrity hashes.
**Depends on**: Phase 2 (needs trained and evaluated specialists to quantize)
**Requirements**: QUANT-01, QUANT-02, QUANT-03
**Success Criteria** (what must be TRUE):
  1. Encoder supports adaptive macroblock hierarchy (64×64 → 32×32 → 16×16 → 8×8 → 4×4) with encode-side Laplacian-weighted error to select block size per region.
  2. 64×64 superblock container with layout enum (0-5): one 64×64, four 32×32s, sixteen 16×16s, sixty-four 8×8s, mixed quadtree, full 4×4 stamps.
  3. Both FP4_AFFINE and T158_AFFINE modes evaluated per block; mode flag (bit 0 of offset) set correctly. Log mode (bit 1) supported per PTDS v4 §6.
  4. Payload scales with block area — not fixed 2048 bytes. 4×4 FP4 = 8 bytes, 64×64 FP4 = 2048 bytes.
  5. Variable effective bitrate: typical average ~2.7-3.3 bpw (vs fixed 4.0 bpw in v1).
  6. Error tolerance thresholds per macroblock size, configurable in pipeline.yaml.
  7. Quantization results feed back into Phase 2 evaluation gating to identify distillation paths that map well to SGFP4.
  8. Model manifest records source model identity, adapter identity, quantization parameters, encoder version, timestamp, and content hash for integrity verification.
**Plans**: 3 plans

Plans:
- [ ] 03-01-PLAN.md — SGFP4 v2 encoder core: Laplacian pyramid, adaptive macroblock quadtree, layout enum, variable payload, per-block header
- [ ] 03-02-PLAN.md — Config & checkpoint extensions: pipeline.yaml error thresholds, ConfigLoader validation, CheckpointValidator v2 checks
- [ ] 03-03-PLAN.md — Evaluation integration: MetricStore SGFP4 dimensions, Benchmarker SGFP4 auto-gating
### Phase 4: Benchmark Evaluation
**Goal**: Quantized specialist models are scored against established benchmark suites (MMLU, HumanEval, GSM8K, domain-specific) as a quality gate. Failed benchmarks feed back into distillation strategy refinement.
**Depends on**: Phase 3 (needs quantized models to benchmark)
**Requirements**: BMARK-01, BMARK-02, BMARK-03
**Success Criteria** (what must be TRUE):
  1. Each quantized specialist runs against its domain-relevant benchmark suite and produces structured scores.
  2. Benchmarks act as a quality gate — models below configurable thresholds are flagged for distillation refinement.
  3. Benchmark results persist with model identity, quantization config, and timestamp for trend analysis across runs.
  4. Failed benchmarks produce actionable feedback (which categories underperformed, by how much) to guide manual distillation strategy adjustments.
**Plans**: 3 plans

### Phase 5: PTDS v4 Unsloth Integration
**Goal**: Add Unsloth as a parallel training backend following the Phase 1 multi-backend pattern, implement Teacher→Parent→Specialist 3-tier distillation per PTDS v4 §3, support SGFP4 hybrid quantization, and introduce role-based specialist taxonomy.
**Depends on**: Phase 4 (needs benchmark-validated specialists from MLX pipeline to compare against)
**Requirements**: TBD (to be defined in discuss-phase)
**Success Criteria** (what must be TRUE):
  1. Unsloth `FastLanguageModel` with LoRA runs as a config-selectable training backend alongside MLX.
  2. 3-tier distillation pipeline: Teacher → Parent (7-13B) → Specialist (0.2-3B) with KL divergence loss.
  3. SGFP4 hybrid quantization (FP4/Ternary + Log mode) produces compliant export artifacts.
  4. Role-based specialists (Planner, Solver, Verifier, Arbiter, Refiner) replace or complement domain specialists.
  5. Backend-agnostic training abstraction (TrainingBackend) enables config-driven dispatch.
**Plans**: 3 plans

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Pipeline Hardening | 5/5 | Shipped | PR #75 |
| 2. Training & Distillation Quality | 5/5 | Shipped | PR #76 |
| 3. FP4 Quantization & Artifact Integrity | 0/3 | Planned | - |
| 4. Benchmark Evaluation | 0/? | Not started | - |
| 5. PTDS v4 Unsloth Integration | 0/? | Not started | - |

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
- SGFP4 quantization export with dual-mode selection
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
