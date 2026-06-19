# Requirements: gnus-poc

> Synthesized from GeniusCognitiveSystem architecture docs, current codebase analysis, and scope decisions. No PRDs were present in the ingest set; these requirements are derived from the architecture specification and mapped to gnus-poc's scope.

---

## Categories

| Category | ID Prefix | Source | Count |
|----------|-----------|--------|-------|
| Pipeline Hardening | PIPE | codebase (pipeline/runner.py) | 3 |
| Teacher API | TEACH | codebase (distill/teacher.py) | 3 |
| Knowledge Distillation | DIST | codebase (distill/distillation.py) + doc 13 | 3 |
| Specialist Training | TRAIN | codebase (training/*.py) + doc 03 | 3 |
| FP4 Quantization | QUANT | codebase (quantize/*.py) + doc 16 | 3 |
| Router/Planner | ROUTE | doc 03 (Model and Router) | 3 |
| EGGROLL Retraining | EGG | doc 13 (EGGROLL Swarm Retraining) | 4 |
| Memory Layer | MEM | doc 06 (Agentic Memory Layer) | 3 |
| Grounding | GND | doc 05 (Grounding and Retrieval) | 3 |
| Reputation | REP | doc 04 (Reputation-Based Consensus) | 3 |

**Total v1 requirements: 31**

---

## PIPE — Pipeline Hardening

### PIPE-01: End-to-End Pipeline Execution
The 7-stage pipeline (data_prep -> synthetic_data -> dedup -> train -> evaluate -> distill -> quantize) must execute end-to-end for all 5 configured specialist niches (medical, qa_technical, code, encyclopedic, patents) without unhandled errors. Each stage must produce verifiable output artifacts.

**Acceptance Criteria:**
- `python pipeline/runner.py` completes all 7 stages for all 5 niches.
- Each stage produces expected output files in `artifacts/` or `models/`.
- Pipeline returns exit code 0 on success.

### PIPE-02: Checkpoint Resume
Pipeline checkpoints must correctly detect completed stages via marker files and support resume from any stage using `--from-stage`. The `--force` flag must bypass checkpoint detection and re-run all stages.

**Acceptance Criteria:**
- Running the pipeline twice for the same niche skips all 7 stages on the second run.
- `--from-stage train` resumes from the train stage, skipping data_prep, synthetic_data, and dedup.
- `--force` re-runs all stages regardless of checkpoints.

### PIPE-03: Per-Specialist Configuration Override
Specialist-specific YAML configs (`config/specialists/<niche>.yaml`) must override global pipeline defaults. Overrides must include: base_model, training hyperparameters, system prompt, synthetic prompts, and niche_sources.

**Acceptance Criteria:**
- `code` specialist uses `Qwen3-Coder-30B-A3B-Instruct-bf16` instead of the default base model.
- Per-specialist training params (e.g., lora_rank, iterations) override global defaults.
- Config loading validates required fields and reports missing keys with clear errors.

---

## TEACH — Teacher API

### TEACH-01: Budget Enforcement
The teacher API client must track cumulative spend against the configured `budget_cap_usd`, persist spend state between runs, and refuse all API calls when the cap is exceeded by raising a `BudgetExceededError`.

**Acceptance Criteria:**
- Spend state is persisted to disk (e.g., `artifacts/.teacher_spend.json`).
- After spend exceeds budget cap, all subsequent API calls raise `BudgetExceededError`.
- Spend tracking resets only via explicit `--reset-budget` flag.

### TEACH-02: Retry with Exponential Backoff
The teacher must retry failed API calls with exponential backoff for transient errors (rate limits 429, server errors 5xx). Non-retryable errors (4xx except 429) must fail immediately.

**Acceptance Criteria:**
- Backoff starts at `backoff_base_seconds` and doubles each retry up to `max_retries`.
- 429 responses are retried; 400/401/403/404 are not retried.
- Maximum retry count is configurable and respected.

### TEACH-03: Circuit Breaker
The teacher must implement a circuit breaker that opens after N consecutive failures and transitions through half-open state to test recovery before closing. A `CircuitBreakerOpenError` must be raised when calls are attempted while the circuit is open.

**Acceptance Criteria:**
- Circuit opens after configurable `failure_threshold` consecutive failures.
- Circuit remains open for configurable `recovery_timeout` seconds.
- After timeout, one probe request is allowed (half-open); success closes circuit, failure reopens it.

---

## DIST — Knowledge Distillation

### DIST-01: KD Loss Convergence
The logit-based knowledge distillation loss `L_KD = alpha * KL_divergence(student_logits || teacher_logits) + (1-alpha) * cross_entropy(student_logits, labels)` must converge to below a configurable threshold within the training budget.

**Acceptance Criteria:**
- KD loss decreases monotonically over training steps (with minor oscillations tolerated).
- Final loss is below the configured `distill_loss_target`.
- Alpha is configurable per specialist (range 0.0–1.0).

### DIST-02: Temperature Sweeping
Distillation must support temperature sweeping — running multiple distillation passes at different softmax temperatures — and recording per-temperature loss for analysis.

**Acceptance Criteria:**
- Temperature values are configurable as a list (e.g., `[1.0, 2.0, 4.0, 8.0]`).
- Each temperature produces a separate loss curve logged to artifacts.
- Sweep results include per-temperature final loss and convergence rate.

### DIST-03: Synthetic Data Quality
Synthetic data generated by the teacher must pass basic quality checks: minimum length threshold, no hallucinated code/formatting artifacts, no empty responses, and diversity across prompts.

**Acceptance Criteria:**
- Generated examples shorter than `min_example_length` tokens are discarded.
- Empty or whitespace-only responses are discarded with a warning.
- Duplicate examples (by normalized text hash) are deduplicated before training ingestion.

---

## TRAIN — Specialist Training

### TRAIN-01: LoRA Adapter Validity
Training must produce valid MLX LoRA adapter weights for each specialist niche. Adapter weights must be loadable by MLX and produce different inference outputs from the base model.

**Acceptance Criteria:**
- `adapter_config.json` and `adapter_model.safetensors` are produced for each niche.
- Loading the adapter with MLX and running inference produces outputs distinct from the base model.
- Training metadata (loss curve, hyperparameters, duration) is recorded in `training_metadata.json`.

### TRAIN-02: Hyperparameter Configurability
All training hyperparameters (batch_size, iterations, learning_rate, lora_rank, lora_dropout, lora_scale, num_layers, optimizer, seed) must be configurable via YAML and respected at runtime.

**Acceptance Criteria:**
- Changing `learning_rate` in config changes the optimizer learning rate used during training.
- Per-specialist overrides take precedence over global defaults.
- Invalid hyperparameter combinations (e.g., batch_size <= 0) are caught with clear errors at config load time.

### TRAIN-03: Evaluation Metrics
Model evaluation must compute and report accuracy, perplexity, and latency metrics for each specialist on held-out test data. Results must be persisted in a structured format (JSON or YAML) per evaluation run.

**Acceptance Criteria:**
- Accuracy is computed against ground-truth labels in the test split.
- Perplexity is computed on the test set.
- Inference latency (mean and P95) is measured and reported.
- Metrics are written to `artifacts/evaluations/<niche>_<timestamp>.json`.

---

## QUANT — FP4 Quantization

### QUANT-01: Ultra FP4 Format Compliance
The FP4 exporter must produce weight tensors partitioned into 64x64 macroblocks with the Ultra FP4 container layout: headers (uint32 packed half2 scale+bias), offsets (uint32 with mode flags), and codes_blob (B * 2048 bytes of concatenated per-block payloads).

**Acceptance Criteria:**
- Exported tensor dimensions are padded to multiples of 64.
- Headers array length equals the number of macroblocks.
- Codes blob size equals B * kMacroblockPayloadBytes (2048).
- Exported files include shape metadata for reconstruction.

### QUANT-02: Dual-Mode Support
The exporter must evaluate both FP4_AFFINE (4-bit signed codes) and T158_AFFINE (ternary codes) modes per macroblock and select the better mode. The selection rule: prefer T158 when `err_t158 <= (1.0 + delta) * err_fp4`.

**Acceptance Criteria:**
- Both modes are evaluated for each macroblock during encoding.
- Per-block mode flag (bit 0 of offset) is set correctly for each block.
- T158 blocks produce ternary codes in {-1, 0, +1}.
- FP4 blocks produce 4-bit signed codes in [-8, 7].

### QUANT-03: Model Manifest with Provenance
Quantized model exports must include a manifest recording: source model identity, base model CID/hash, adapter identity/hash, quantization parameters, encoder version, timestamp, and specialist niche.

**Acceptance Criteria:**
- `manifest.json` is written alongside quantized model files.
- Manifest includes: model_name, niche, base_model_ref, adapter_ref, quantization_params, encoder_version, timestamp_utc.
- Manifest content is hashed and the hash included for integrity verification.

---

## ROUTE — Router/Planner

### ROUTE-01: Rule-Based Query Classification
The router must classify input queries using keyword, pattern, and syntax density rules: numeric density triggers math specialist, code syntax triggers code specialist, grounding-sensitive keywords trigger grounding specialist, formatting-sensitive patterns trigger formatter.

**Acceptance Criteria:**
- A query containing >30% numeric tokens routes to the math specialist path.
- A query containing code fences or class/function definitions routes to the code specialist path.
- A query containing factual-verification keywords (e.g., "verify", "check", "fact") routes to the grounding path.
- No-match queries route to the default semantic core / encyclopedic specialist.

### ROUTE-02: Specialist Selection
Based on classification, the router must select the appropriate specialist model(s) and produce an execution plan specifying: selected specialist, execution mode (single-specialist or chain), and optional secondary specialists (verifier, formatter).

**Acceptance Criteria:**
- Classification result maps to a configured specialist (e.g., math -> `qa_technical` with math verifier).
- Execution plan includes: primary_specialist, secondary_specialists (list), execution_mode ("single" or "chain").
- Plan is logged to the thinking trace for inspectability.

### ROUTE-03: Configurable Routing Rules
Routing rules must be defined in YAML configuration (`config/router.yaml`) and support: pattern-to-specialist mappings, confidence thresholds for classification, and fallback chains.

**Acceptance Criteria:**
- Adding a new routing rule in YAML adds it to the classifier without code changes.
- Pattern syntax supports: regex, keyword lists, numeric density thresholds, and code syntax density thresholds.
- Invalid rules are rejected at config load time with descriptive errors.

---

## EGG — EGGROLL Retraining

### EGG-01: Deterministic Perturbation Generation
Given a seed tuple `(model_version, adapter_version, layer_id, worker_id, generation_id, perturbation_id)`, the system must deterministically generate a low-rank perturbation matrix that can be reconstructed from the seed alone.

**Acceptance Criteria:**
- Same seed produces identical perturbation across multiple invocations.
- Perturbation is low-rank (rank configurable via `perturbation_rank`).
- Perturbation values are scaled by `perturbation_scale` parameter.
- Seed derivation uses a cryptographic hash (SHA-256) of the seed tuple for reproducibility.

### EGG-02: Perturbation Application and Fitness Evaluation
The system must apply a perturbation to a specialist's LoRA adapter weights, run inference on a task shard, and compute fitness according to a declared reward function.

**Acceptance Criteria:**
- Perturbation is added to adapter weights (not backbone weights) per the adapter-oriented evolution principle.
- Inference runs on the assigned task shard with the perturbed adapter.
- Fitness is computed using the configured reward function (accuracy, loss, or custom metric).
- Original adapter weights are restored after evaluation.

### EGG-03: Compact Fitness Packet
Each perturbation evaluation must produce a compact fitness packet containing: training_job_id, worker_node ID, artifact_target, seed_range, fitness_values, latency_ms, validation_flags, and result_signature.

**Acceptance Criteria:**
- Fitness packet is a valid JSON or structured dict matching the EGGROLL schema.
- validation_flags includes self_check_passed and any policy compliance flags.
- Packet size is minimal (no tensor data — only scalar fitness and metadata).

### EGG-04: Best-Perturbation Selection and Promotion
After evaluating a generation of perturbations, the system must select the best perturbation by fitness, validate it against quality thresholds, and promote it as the new active adapter.

**Acceptance Criteria:**
- Best perturbation is the one with the highest aggregated fitness across task shards.
- Promotion requires fitness above configurable `promotion_threshold`.
- Promoted adapter is saved as the new active adapter version.
- Previous adapter version is archived with version history.
- Promotion event is logged with full metadata (seed, fitness, generation, timestamp).

---

## MEM — Memory Layer

### MEM-01: GAML Memory Object Storage and Retrieval
The system must support storing and retrieving GAML-compatible memory objects with fields: id (UUID), entity, type (bridge_block, fact, policy, event, tenant_operational), payload (structured JSON), timestamp, source_node, confidence_score, provenance_score, and trust_class.

**Acceptance Criteria:**
- Memory objects can be created, stored, and retrieved by ID.
- Objects can be queried by type, entity, trust_class, and timestamp range.
- Storage backend is local (SQLite or JSON file) for single-machine operation.
- Retrieved objects maintain all metadata fields intact.

### MEM-02: Trust Classification
Memory objects must carry `trust_class` (higher_trust or lower_trust) and `provenance_score` metadata. Higher-trust memory requires verified origin and strong provenance; lower-trust memory may be raw/unvalidated external content.

**Acceptance Criteria:**
- New memory objects are classified as higher_trust or lower_trust at write time based on provenance and source.
- Trust classification rules are configurable (e.g., teacher-generated content -> lower_trust; verified distillation output -> higher_trust).
- trust_class is immutable after write (upgrading requires explicit promotion with re-validation).

### MEM-03: Trust-Filtered Retrieval
Memory retrieval must support filtering by trust_class and minimum provenance_score threshold. Retrieval for grounding/verification must only use higher-trust memory; retrieval for general context may include lower-trust memory with scrubbing.

**Acceptance Criteria:**
- Query with `trust_class=higher_trust` returns only higher-trust objects.
- Query with `min_provenance=0.8` returns only objects with provenance_score >= 0.8.
- Retrieval for grounding workflows enforces higher-trust-only by default.

---

## GND — Grounding

### GND-01: External Knowledge Retrieval
The system must include a grounding client that retrieves structured knowledge from an external source. For PoC, this may be a mock/local knowledge base that conforms to the grounding API contract.

**Acceptance Criteria:**
- Grounding client accepts a query string and returns structured facts (at minimum: fact_text, source, confidence).
- For PoC, a local knowledge base (static JSON or SQLite) provides fact responses without external API dependency.
- Client interface is swappable to connect to Grokipedia or other external source when available.

### GND-02: Grounded Fact Injection with Traceability
Retrieved grounding facts must be injectable into the generation context (system prompt or context window) with traceability tags that identify the fact source in the model output.

**Acceptance Criteria:**
- Facts are formatted as context blocks with source attribution.
- Generated output includes traceability markers (e.g., `[source: <fact_id>]`) linking claims to grounding facts.
- Injection is configurable: inject before generation, during generation, or post-generation as validation.

### GND-03: Post-Generation Contradiction Detection
After generation, the system must check factual claims in the output against grounded knowledge and flag contradictions. Contradictions must lower the grounding/consistency score for that output.

**Acceptance Criteria:**
- Factual claims extracted from output are compared against grounded facts.
- Contradictions are logged with: claim_text, contradicting_fact, contradiction_severity.
- Contradiction count reduces the consistency score for reputation updates.

---

## REP — Reputation

### REP-01: Multi-Dimension Reputation Scoring
The system must compute per-specialist reputation scores across multiple dimensions: quality_score, latency_score, consistency_score, and safety_score. Scores must be updated after each task and clipped to [0, 1].

**Acceptance Criteria:**
- quality_score reflects accuracy/agreement metrics from evaluation.
- latency_score penalizes above-median inference times.
- consistency_score reflects output stability across similar inputs.
- All scores are in [0, 1] and persisted between runs.

### REP-02: Reputation-Weighted Specialist Selection
When multiple specialists are candidates for a task, the router must use reputation scores as input to specialist selection. Higher-reputation specialists must be preferred for their domain.

**Acceptance Criteria:**
- Specialist selection includes reputation rank as a weighting factor.
- A specialist with quality_score 0.3 is skipped in favor of one with 0.8 if both are eligible.
- Reputation thresholds are configurable (e.g., min_quality_score before a specialist is eligible).

### REP-03: Persisted Reputation State
Reputation scores must be persisted across pipeline runs so that reputation accumulates over time. State must include versioning to detect and handle schema changes.

**Acceptance Criteria:**
- Reputation state is saved to `artifacts/reputation/<niche>_scores.json` after each evaluation.
- Scores from previous runs are loaded and updated (not reset) on subsequent runs.
- State file includes schema version for forward compatibility.

---

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| PIPE-01 | Phase 1 | Pending |
| PIPE-02 | Phase 1 | Pending |
| PIPE-03 | Phase 1 | Pending |
| TEACH-01 | Phase 1 | Pending |
| TEACH-02 | Phase 1 | Pending |
| TEACH-03 | Phase 1 | Pending |
| DIST-01 | Phase 2 | Pending |
| DIST-02 | Phase 2 | Pending |
| DIST-03 | Phase 2 | Pending |
| TRAIN-01 | Phase 2 | Pending |
| TRAIN-02 | Phase 2 | Pending |
| TRAIN-03 | Phase 2 | Pending |
| QUANT-01 | Phase 3 | Pending |
| QUANT-02 | Phase 3 | Pending |
| QUANT-03 | Phase 3 | Pending |
| ROUTE-01 | Phase 4 | Pending |
| ROUTE-02 | Phase 4 | Pending |
| ROUTE-03 | Phase 4 | Pending |
| EGG-01 | Phase 5 | Pending |
| EGG-02 | Phase 5 | Pending |
| EGG-03 | Phase 5 | Pending |
| EGG-04 | Phase 5 | Pending |
| MEM-01 | Phase 6 | Pending |
| MEM-02 | Phase 6 | Pending |
| MEM-03 | Phase 6 | Pending |
| GND-01 | Phase 6 | Pending |
| GND-02 | Phase 6 | Pending |
| GND-03 | Phase 6 | Pending |
| REP-01 | Phase 7 | Pending |
| REP-02 | Phase 7 | Pending |
| REP-03 | Phase 7 | Pending |

**Coverage: 31/31 requirements mapped — 100%**
