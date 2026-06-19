# Roadmap: gnus-poc

## Overview

gnus-poc evolves from a fragile sequential training script into a hardened ELM training and distillation pipeline with cognitive system layers. The journey progresses through three logical arcs: **hardening** (Phases 1–3, making the existing pipeline production-grade), **architectural extension** (Phases 4–5, adding the router and EGGROLL retraining from the GeniusCognitiveSystem architecture), and **cognitive system** (Phases 6–7, adding memory, grounding, reputation, and continuous learning). Each phase delivers a distinct, verifiable capability that builds on the previous.

## Phases

- [ ] **Phase 1: Pipeline Hardening** — End-to-end reliability with budget enforcement, retry, circuit breaker, and checkpointing
- [ ] **Phase 2: Training & Distillation Quality** — KD convergence, temperature sweeping, valid LoRA adapters, evaluation persistence
- [ ] **Phase 3: FP4 Quantization & Artifact Integrity** — Standards-compliant Ultra FP4 export with dual-mode selection and provenance manifests
- [ ] **Phase 4: Router & Specialist Selection** — Rule-based query classification and specialist routing with configurable YAML rules
- [ ] **Phase 5: EGGROLL Retraining** — Single-machine evolutionary retraining with deterministic perturbations and fitness-based promotion
- [ ] **Phase 6: Memory & Grounding** — GAML-compatible memory store and knowledge grounding with contradiction detection
- [ ] **Phase 7: Reputation & Continuous Learning** — Multi-dimension reputation scoring and feedback-driven continuous learning loop

## Phase Details

### Phase 1: Pipeline Hardening
**Goal**: The 7-stage training pipeline executes reliably end-to-end with checkpoint resume, budget enforcement, retry with exponential backoff, and circuit breaker protection.
**Depends on**: Nothing (first phase)
**Requirements**: PIPE-01, PIPE-02, PIPE-03, TEACH-01, TEACH-02, TEACH-03
**Success Criteria** (what must be TRUE):
  1. Pipeline completes all 7 stages for all 5 specialist niches without unhandled errors, producing verifiable output artifacts at each stage.
  2. Pipeline checkpoints skip already-completed stages on re-run; `--from-stage` resumes from any stage; `--force` bypasses all checkpoints.
  3. Per-specialist YAML configs override global defaults at runtime; invalid configs produce descriptive error messages at load time.
  4. Budget cap stops all teacher API calls when cumulative spend exceeds the limit, with spend state persisted between runs.
  5. Retry with exponential backoff recovers from rate limits (429) and server errors (5xx); circuit breaker opens after consecutive failures and supports half-open recovery.
**Plans**: TBD

### Phase 2: Training & Distillation Quality
**Goal**: Knowledge distillation converges with configurable KD loss, temperature sweeping produces analysis data, specialist training produces valid LoRA adapters, and evaluation persists metrics per run.
**Depends on**: Phase 1
**Requirements**: DIST-01, DIST-02, DIST-03, TRAIN-01, TRAIN-02, TRAIN-03
**Success Criteria** (what must be TRUE):
  1. KD loss decreases over training steps and converges to below the configured `distill_loss_target` threshold.
  2. Temperature sweeping runs multiple distillation passes at configurable temperatures, producing per-temperature loss curves.
  3. Synthetic data passes quality checks: minimum length, no empty responses, deduplication by normalized text hash.
  4. LoRA adapter training produces loadable adapter weights that change inference behavior, with `training_metadata.json` recording loss and hyperparameters.
  5. Hyperparameters from YAML config are respected at runtime; invalid combinations (e.g., batch_size <= 0) produce clear validation errors.
  6. Model evaluation produces accuracy, perplexity, and latency metrics (mean/P95) persisted to `artifacts/evaluations/` per run.
**Plans**: TBD

### Phase 3: FP4 Quantization & Artifact Integrity
**Goal**: Ultra FP4 export produces standards-compliant quantized models with 64x64 macroblocks, dual-mode per-block selection (FP4_AFFINE/T158_AFFINE), and provenance manifests.
**Depends on**: Phase 2
**Requirements**: QUANT-01, QUANT-02, QUANT-03
**Success Criteria** (what must be TRUE):
  1. Quantized weight tensors use correct 64x64 macroblock partitioning with properly packed header (half2 scale+bias), offset (mode flags), and codes_blob (B * 2048 bytes) arrays.
  2. Both FP4_AFFINE and T158_AFFINE mode errors are evaluated per macroblock; T158 is selected when `err_t158 <= (1.0 + delta) * err_fp4`; mode flags in offset bits are set correctly.
  3. Model manifest records source model identity, adapter identity, quantization parameters, encoder version, and timestamp; manifest hash enables integrity verification.
**Plans**: TBD

### Phase 4: Router & Specialist Selection
**Goal**: A rule-based router classifies input queries by keyword/syntax patterns, selects appropriate specialists, and produces execution plans. All routing rules are configurable in YAML.
**Depends on**: Phase 2 (needs trained specialists to route to)
**Requirements**: ROUTE-01, ROUTE-02, ROUTE-03
**Success Criteria** (what must be TRUE):
  1. Math-heavy queries (30%+ numeric tokens) route to the math specialist path; code syntax queries route to the code specialist; factual-verification queries route to the grounding path.
  2. Router produces execution plans containing primary specialist, optional secondary specialists, and execution mode (single or chain).
  3. Routing rules are defined in `config/router.yaml`; new specialist mappings can be added without code changes; invalid rules produce descriptive errors at load time.
**Plans**: TBD

### Phase 5: EGGROLL Retraining
**Goal**: Single-machine EGGROLL evolutionary retraining proves the core primitive: deterministic perturbation from seeds, adapter-targeted perturbation application, compact fitness packet production, and best-perturbation promotion.
**Depends on**: Phase 2 (needs trained adapters to perturb) and Phase 4 (router provides specialist targets)
**Requirements**: EGG-01, EGG-02, EGG-03, EGG-04
**Success Criteria** (what must be TRUE):
  1. Same seed tuple produces identical low-rank perturbation matrices across multiple invocations, using SHA-256 for deterministic reconstruction.
  2. Perturbed LoRA adapters run inference on task shards and produce fitness scores computed via the configured reward function.
  3. Fitness packets are compact (scalar fitness + metadata only, no tensor data) and conform to the EGGROLL packet schema with validation flags.
  4. Best perturbation by aggregated fitness is validated against `promotion_threshold` and promoted as the new active adapter; previous version is archived with version history.
**Plans**: TBD

### Phase 6: Memory & Grounding
**Goal**: GAML-compatible memory objects are storable and retrievable with trust classification, and a grounding client retrieves structured facts for injection and post-generation contradiction detection.
**Depends on**: Phase 2 (needs generation to ground and memorize)
**Requirements**: MEM-01, MEM-02, MEM-03, GND-01, GND-02, GND-03
**Success Criteria** (what must be TRUE):
  1. Memory objects (bridge_blocks, facts, policies, events) can be created, stored, and retrieved by ID, type, entity, trust_class, and provenance threshold.
  2. Higher-trust and lower-trust memory are separated by trust_class; higher-trust memory requires verified provenance; trust_class is immutable after write.
  3. Grounding client returns structured facts from a local knowledge base (static JSON or SQLite) matching the grounding API contract.
  4. Injected grounding facts appear in generation context with source attribution; generated output includes traceability markers linking claims to fact IDs.
  5. Post-generation contradiction detection flags factual claims that conflict with grounded knowledge and logs contradiction severity.
**Plans**: TBD

### Phase 7: Reputation & Continuous Learning
**Goal**: Multi-dimension reputation scores (quality, latency, consistency, safety) persist across runs, influence specialist selection, and drive a feedback-driven continuous learning loop.
**Depends on**: Phase 2 (needs evaluation data) and Phase 4 (router uses reputation) and Phase 5 (EGGROLL provides retraining target)
**Requirements**: REP-01, REP-02, REP-03
**Success Criteria** (what must be TRUE):
  1. Per-specialist quality_score, latency_score, consistency_score, and safety_score are computed after each evaluation run and clipped to [0, 1].
  2. Reputation-weighted specialist selection prefers higher-reputation specialists for their domain; specialists below `min_quality_score` are excluded from selection.
  3. Reputation state persists across pipeline runs in `artifacts/reputation/` and accumulates (not resets) over time; state file includes schema version for forward compatibility.
  4. The continuous learning loop triggers retraining events when evaluation feedback degrades below configured thresholds, feeding into the EGGROLL retraining pipeline.
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Pipeline Hardening | 0/? | Not started | - |
| 2. Training & Distillation Quality | 0/? | Not started | - |
| 3. FP4 Quantization & Artifact Integrity | 0/? | Not started | - |
| 4. Router & Specialist Selection | 0/? | Not started | - |
| 5. EGGROLL Retraining | 0/? | Not started | - |
| 6. Memory & Grounding | 0/? | Not started | - |
| 7. Reputation & Continuous Learning | 0/? | Not started | - |
