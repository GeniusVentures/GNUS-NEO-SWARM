# Requirements: gnus-poc

> Synthesized from GeniusCognitiveSystem architecture docs, current codebase analysis, and scope decisions. Requirements beyond the training pipeline boundary (EGGROLL, GAML memory, reputation/consensus) belong to the GNUS-NEO-SWARM C++ parent repo.

---

## Categories

| Category | ID Prefix | Source | Count |
|----------|-----------|--------|-------|
| Pipeline Hardening | PIPE | codebase (pipeline/runner.py) | 3 |
| Teacher API | TEACH | codebase (distill/teacher.py) + discuss-phase | 5 |
| Knowledge Distillation | DIST | codebase (distill/distillation.py) + doc 13 | 3 |
| Specialist Training | TRAIN | codebase (training/*.py) + doc 03 | 3 |
| Rules-Based Routing | ROUTE | doc 03 (Model and Router) | 2 |
| FP4 Quantization | QUANT | codebase (quantize/*.py) + doc 16 | 3 |
| Benchmark Evaluation | BMARK | explore session | 3 |

**Total v1 requirements: 22**

---

## PIPE — Pipeline Hardening

### PIPE-01: End-to-End Pipeline Execution
The 7-stage pipeline (data_prep -> synthetic_data -> dedup -> train -> evaluate -> distill -> quantize) must execute end-to-end for all 5 configured specialist niches (medical, qa_technical, code, encyclopedic, patents) without unhandled errors. Each stage must produce verifiable output artifacts.

**Acceptance Criteria:**
- `python pipeline/runner.py` completes all 7 stages for all 5 niches.
- Each stage produces expected output files in `artifacts/` or `models/`.
- Pipeline returns exit code 0 on success.

### PIPE-02: Checkpoint Resume
Pipeline checkpoints must correctly detect completed stages via validated marker files and support resume from any stage using `--from-stage`. The `--force` flag must bypass checkpoint detection and re-run all stages.

**Acceptance Criteria:**
- Running the pipeline twice for the same niche skips all 7 stages on the second run.
- `--from-stage train` resumes from the train stage, skipping data_prep, synthetic_data, and dedup.
- `--force` re-runs all stages regardless of checkpoints.
- Checkpoints validate stage outputs (file existence, content quality, schema) before marking complete.

### PIPE-03: Per-Specialist Configuration Override
Specialist-specific YAML configs (`config/specialists/<niche>.yaml`) must override global pipeline defaults. Overrides must include: base_model, training hyperparameters, system prompt, synthetic prompts, and niche_sources.

**Acceptance Criteria:**
- `code` specialist uses `Qwen3-Coder-30B-A3B-Instruct-bf16` instead of the default base model.
- Per-specialist training params (e.g., lora_rank, iterations) override global defaults.
- Config loading validates required fields and reports missing keys with clear errors.

---

## TEACH — Teacher API

### TEACH-01: Multi-Teacher Cascade with Benchmark Routing
The teacher client must support a three-tier benchmark-routed cascade. Level 1 (always): DeepSeek v4 Fast. Level 2 (domain-routed): selected from a pre-configured benchmark table by domain strength. Escalation triggers when Level 1 output confidence falls below a configurable threshold.

**Acceptance Criteria:**
- Level 1 (DeepSeek v4 Fast) always runs first for every request.
- Confidence is measured via teacher logprobs (mean token probability).
- When confidence < threshold, Level 2 teacher is selected from benchmark table by detected domain.
- Benchmark table maps domain -> {model_name: strength_score} in YAML.

### TEACH-02: Dual-Backend API Architecture
The teacher client must support both OpenAI and Anthropic API backends, selected per-call based on the model's endpoint `apiType` configuration. Both backends must be fully implemented.

**Acceptance Criteria:**
- OpenAI backend uses `openai` SDK `chat.completions.create()`.
- Anthropic backend uses `anthropic` SDK `messages.create()`.
- Backend selection is driven by `apiType` field on the endpoint config entry.
- Both backends share the same cost tracking, retry, circuit breaker, and budget enforcement.

### TEACH-03: Two-Layer Teacher Configuration
Teacher config uses a two-layer structure: `endpoints` define connection details (url, apiType), `models` map model names to endpoint references. Model names are literal — no aliasing. API keys stored in `.env` only.

**Acceptance Criteria:**
- `endpoints` entries specify: url, apiType (openai|anthropic).
- `models` entries specify: endpoint reference (must match an endpoints key).
- Adding a teacher requires only a config entry + API key — no code change.
- All current models (DSv4 Fast, DSv4 Pro, GLM 5.2) route through LiteLLM proxy.

### TEACH-04: Budget Enforcement
The teacher API client must track cumulative spend against the configured `budget_cap_usd`, persist spend state between runs, and refuse all API calls when the cap is exceeded by raising a `BudgetExceededError`.

**Acceptance Criteria:**
- Spend state is persisted to disk (`artifacts/.budget_state.json`).
- After spend exceeds budget cap, all subsequent API calls raise `BudgetExceededError`.
- Spend tracking resets only via explicit `--reset-budget` flag.
- Budget check includes spend from all backends (OpenAI + Anthropic combined).

### TEACH-05: Retry with Exponential Backoff and Circuit Breaker
The teacher must retry failed API calls with exponential backoff for transient errors (rate limits 429, server errors 5xx). Non-retryable errors (4xx except 429) must fail immediately. A circuit breaker must open after N consecutive failures and transition through half-open state.

**Acceptance Criteria:**
- Backoff starts at `backoff_base_seconds` and doubles each retry up to `max_retries`.
- 429 responses are retried; 400/401/403/404 are not retried.
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

## ROUTE — Rules-Based Specialist Routing

### ROUTE-01: Rule-Based Query Classification
A lightweight rules-based router must classify input queries using keyword, pattern, and syntax density rules to select the appropriate specialist. No learned model — pure YAML-driven rule matching.

**Acceptance Criteria:**
- A query containing >30% numeric tokens routes to the math specialist path.
- A query containing code fences or class/function definitions routes to the code specialist path.
- No-match queries route to the default encyclopedic specialist.
- Routing rules defined in YAML config, no code changes required to add rules.

### ROUTE-02: Specialist Selection and Execution Plan
Based on classification, the router must select the appropriate specialist model and produce an execution plan specifying: selected specialist and execution mode (single-specialist or chain).

**Acceptance Criteria:**
- Classification result maps to a configured specialist.
- Execution plan includes: primary_specialist, execution_mode ("single" or "chain").
- Plan is logged for inspectability.

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

## BMARK — Benchmark Evaluation

### BMARK-01: Benchmark Suite Execution
Quantized specialist models must be scored against established benchmark suites. Each specialist maps to domain-relevant benchmarks: code specialist -> HumanEval, math specialist -> GSM8K, general specialists -> MMLU, medical -> MedQA or equivalent.

**Acceptance Criteria:**
- Benchmark datasets are acquired and cached locally for reproducible scoring.
- Each specialist runs its domain-relevant benchmark(s) with standardized prompting.
- Benchmark results include: benchmark name, score, per-category breakdown, model identity, quantization config, timestamp.
- Results are written to `artifacts/benchmarks/<niche>_<benchmark>_<timestamp>.json`.

### BMARK-02: Quality Gate Threshold
Benchmark results act as a quality gate — specialists scoring below configurable per-benchmark thresholds are flagged as failed and block the pipeline from marking the specialist as "production-ready."

**Acceptance Criteria:**
- Per-benchmark thresholds are configurable in YAML (e.g., HumanEval pass@1 >= 0.40, MMLU >= 0.50).
- Failed benchmarks produce a clear failure report: which categories underperformed, by what margin.
- Failed specialists do not receive a "production-ready" marker in their manifest.
- The pipeline continues (does not abort) — failure is recorded, not fatal.

### BMARK-03: Trend Analysis and Feedback
Benchmark results across runs must be comparable to enable trend analysis. The system must surface score deltas between runs to guide distillation strategy adjustments.

**Acceptance Criteria:**
- Previous benchmark results for the same specialist are loaded for comparison.
- Score deltas (current - previous) are computed and displayed per benchmark and per category.
- Trend data is persisted to enable multi-run analysis.
- Degradation flags (score dropped > configurable threshold) trigger warnings.

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
| TEACH-04 | Phase 1 | Pending |
| TEACH-05 | Phase 1 | Pending |
| DIST-01 | Phase 2 | Pending |
| DIST-02 | Phase 2 | Pending |
| DIST-03 | Phase 2 | Pending |
| TRAIN-01 | Phase 2 | Pending |
| TRAIN-02 | Phase 2 | Pending |
| TRAIN-03 | Phase 2 | Pending |
| ROUTE-01 | Phase 2 | Pending |
| ROUTE-02 | Phase 2 | Pending |
| QUANT-01 | Phase 3 | Complete |
| QUANT-02 | Phase 3 | Complete |
| QUANT-03 | Phase 3 | Complete |
| BMARK-01 | Phase 4 | Pending |
| BMARK-02 | Phase 4 | Pending |
| BMARK-03 | Phase 4 | Pending |

**Coverage: 22/22 requirements mapped — 100%**
