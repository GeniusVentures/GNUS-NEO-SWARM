# Project Research Summary

**Project:** GNUS-POC ELM Training & Distillation Pipeline (Milestone v1.1)
**Domain:** ML training/distillation pipeline for specialist SLMs on Apple Silicon
**Researched:** 2026-05-27
**Confidence:** HIGH

## Executive Summary

This is a Python pipeline that trains Expert Language Models (ELMs) for a decentralized specialist swarm. Five LoRA-adapted Qwen3-30B-MoE specialists already exist (medical, code, qa_technical, encyclopedic, patents), trained via MLX-LM on Apple Silicon. The v1.1 milestone adds: teacher-driven synthetic data generation, knowledge distillation (teacher-to-student logit transfer and subspace extraction), per-specialist evaluation/benchmarking, experiment tracking, FP4 quantization for deployment, and an orchestration layer to tie it all together.

The recommended approach is: **fix existing bugs first, then build new capabilities in dependency order**. Two existing bugs are silently corrupting training output today (chat template mismatch between data prep and training, and skip-on-existing logic producing false completions). These must be fixed before any new specialist training. After that, the critical path is: synthetic data generation (teacher API) → evaluation framework → knowledge distillation → orchestration → FP4 quantization → deployment packaging. Experiment tracking should be built alongside evaluation. FP4 quantization and deployment packaging can run partially in parallel with distillation.

The single biggest risk is **teacher model licensing**: using a closed commercial API (DeepSeek v4 pro) to generate training data for open-source student models may violate API Terms of Service. This is flagged as an existential, project-level risk — not a technical bug — and requires a user decision before any API integration code is written. The fallback is to use only open-source models with permissive licenses (e.g., DeepSeek-V3, Llama 3.1, Qwen 3). Other key risks include API cost explosion (fixed with hard budget caps), Apple Silicon OOM during 30B model training (fixed with pre-flight memory checks and qLoRA), and cross-niche data contamination (fixed with deduplication).

## Key Findings

### Recommended Stack

**Already installed (no changes needed):** MLX 0.30.0 ecosystem (mlx, mlx-lm, mlx-metal), PyTorch 2.7.1, transformers 4.54.1, datasets 4.0.0, openai 1.101.0, scikit-learn 1.7.1, numpy 1.26.4, and all utilities (rich, tenacity, python-dotenv, PyYAML, nltk, tqdm, pytest, responses).

**Core technologies:**
- **MLX 0.30.0** (mlx, mlx-lm, mlx-metal): Apple Silicon tensor compute — already the training engine. 2-3x faster than PyTorch+MPS for LLM workloads. Extend existing `train_specialists_mlx.py`, don't replace.
- **openai 1.101.0** (existing, not `deepseek-sdk`): DeepSeek v4 pro API client — DeepSeek API is OpenAI-compatible. Use the official `openai` Python SDK with `base_url="https://api.deepseek.com"`. The third-party `deepseek-sdk` (v0.1.1) is a thin wrapper from a single maintainer — avoid.
- **mlflow 3.12.0** (NEW install): Experiment tracking — replaces need for W&B (cloud-dependent). Native DeepSeek integration, LLM tracing, local UI (`mlflow ui`), zero external dependencies. Log params/metrics/artifacts from training loops.
- **lm-eval 0.4.12** (NEW install): Standard benchmark evaluation — EleutherAI's harness for MMLU, HellaSwag, ARC, GSM8K. Use for base model calibration (HF backend only — MLX not directly supported). Custom eval scripts needed for specialist-specific accuracy/latency/perplexity.
- **MLX native quantization** (built-in): FP4 weight quantization — `mlx.core.quantize()` supports mxfp4/nvfp4/affine modes. Use instead of the PyTorch FP4 code in `docs/code-in-markdown.md` (legacy research). The C++ `FP4Codec.hpp` in `src/core/fp4/` defines the binary format contract for C++ engine consumption.

**New pip installs (5 packages):** `mlflow==3.12.0`, `lm_eval[hf]`, `pytest-mock`, `pytest-cov`, `pytest-timeout`.

**Rejected alternatives:** W&B (cloud-dependent, heavier), deepseek-sdk (third-party, single-maintainer), Prefect/Airflow (overkill for single-machine sequential pipeline), DVC (unnecessary complexity for v1.1 data volumes <10GB), async API patterns (sync is sufficient for batch sizes in hundreds to low thousands).

### Expected Features

**Must have (table stakes) — these already exist:**
- Niche discovery via TF-IDF clustering (`analyze_common_pile.py`) — exists, use as-is
- Dataset preparation with train/val/test splits (`prepare_datasets.py`) — exists, **needs chat template fix (Pitfall #1)**
- LoRA fine-tuning pipeline (`train_specialists_mlx.py`) — exists, **needs skip-logic fix (Pitfall #2)**, needs TrainingConfig extraction

**Must have (table stakes) — must build in v1.1:**
- Teacher-driven synthetic data generation via DeepSeek v4 pro API — **missing entirely**
- Per-specialist evaluation & benchmarking — **missing entirely**
- Knowledge distillation (logit transfer + subspace extraction) — **missing entirely**
- Experiment tracking (cross-run comparison, hyperparameter search) — **missing entirely**
- Orchestration layer (single-command DAG) — **missing entirely**
- Deployment packaging (MLX→FP4 binary for C++ engine) — **missing entirely**

**Should have (differentiators, build if time allows):**
- FP4 pyramid-based quantization integrated into pipeline — strategic docs describe proprietary breakthrough in `FP4Codec.hpp`; bridge C++ codec with Python
- Subspace extraction distillation (not just logit-based) — per strategic docs, extract specialized subspaces from teacher; research-grade, no existing implementation
- Multi-model base support per specialist — existing `SPECIALIST_BASE_MODELS` dict; extend for per-niche best model
- Swarm-ready adapter packaging (checksums, versioning, LoRA signatures for P2P distribution)
- Cost-tracking & resource estimation — project forward from existing training metadata

**Defer (v2+):**
- Full pretraining from scratch ($135k+ estimated, out of scope for PoC)
- Real-time serving/inference endpoints (belongs in C++ `genius_node`, not Python pipeline)
- Multi-teacher distillation ($480k+ estimated, licensing risks with OpenAI/Anthropic)
- Dynamic adapter loading/hot-swapping (C++ runtime concern)
- Human feedback LoRA loops (requires swarm runtime integration)
- AutoML/hyperparameter optimization frameworks (Optuna, Ray Tune — premature for PoC)
- Streaming/distributed training across multiple Macs (swarm networking problem, Phase 6+)

### Architecture Approach

The architecture follows a **flat-module pipeline with YAML configuration and staged execution**. Each pipeline stage is a self-contained Python module with a clear input/output contract. The pipeline is sequential (single Mac Studio M2 Ultra), not distributed. Synthetic data **augments** (does not replace) source-extracted data — the pipeline runs without teacher API using source data alone if credentials are unavailable. The FP4 exporter at pipeline end produces binary artifacts consumed by the C++ engine — this is the critical Python-to-C++ integration boundary.

**Major components:**
1. **pipeline/** — Orchestrator: loads YAML config (global → specialist → experiment override), runs stages in dependency order, skips completed stages, logs to MLflow. No ML logic.
2. **distill/** — Teacher API + distillation: `TeacherClient` (DeepSeek v4 pro with retry/backoff/cost tracking/budget cap), `SyntheticDataGenerator` (per-niche prompt templates → JSONL output), `Distiller` (logit transfer via temperature-scaled KL divergence + subspace extraction via SVD).
3. **training/** — LoRA training (refactored from `models/`): `TrainingConfig` dataclass (single source of truth for all 18 LoRA hyperparams, replacing scattered `OVERRIDES` dicts), `SpecialistTrainer` wrapping `mlx_lm.lora.train_model()` with MLflow logging.
4. **eval/** — Evaluation: `Evaluator` (perplexity, accuracy, latency per specialist on held-out test sets), `Benchmarker` (head-to-head comparison across training variants). Uses `lm-eval` for standard benchmarks, custom scripts for MLX models.
5. **quantize/** — FP4 export: `FP4Exporter` converts LoRA safetensors to FP4-packed binary matching the C++ `FP4Codec` spec. Writes `manifest.json` cataloging all specialists for the C++ engine.
6. **data/scripts/** — Existing scripts moved here: niche discovery, source extraction, dataset preparation (with synthetic data augmentation flag).
7. **config/** — YAML hierarchy: `pipeline.yaml` (global), `specialists/<niche>.yaml` (per-specialist overrides), `experiments/<exp>.yaml` (A/B test overrides). Env-var interpolation for secrets.
8. **artifacts/** — Structured outputs for C++ consumption: FP4 binaries, manifold JSON, eval results, experiment logs. Separate from `models/` (raw training outputs for debugging/retraining).

**Key architectural decisions:**
- Flat modules, not a pip package — gnus-poc is a POC pipeline, exit strategy is artifacts (FP4 binaries, manifest JSON), not a Python API
- YAML configs (not JSON) — comments document hyperparameter choices, anchors share configs across specialists
- Augment (not replace) source data with synthetic — both together > either alone
- FP4 export at pipeline end — C++ engine loads pre-quantized adapters, quantization done once in Python
- `models/` ≠ `artifacts/` — different consumers, different lifecycle
- `config/` at top level — single load at pipeline start rather than per-module config files

**Directory restructure:** ~34 new files, 6 modified/moved, 1 deleted (`train_specialists-old.py` duplicate). See ARCHITECTURE.md Section 2 for full tree and Section 10 for file count summary.

### Critical Pitfalls

Ranked by impact × likelihood, from codebase audit and strategic document analysis. Full details in PITFALLS.md including detection methods and code-level evidence.

1. **Chat template mismatch between data prep and training (Pitfall #1)** — HIGH impact, HIGH likelihood. **Already present in current code.** `prepare_datasets.py` hardcodes Qwen2.5 `<|im_start|>` format but `train_specialists_mlx.py` loads Qwen3-30B-A3B models with a different chat template. Produces silently garbage output. **Prevention:** Use `tokenizer.apply_chat_template()` from the actual loaded tokenizer instead of hand-rolled format strings. This must be fixed in Phase 1 before any new training.

2. **Teacher model licensing contamination of student models (Pitfall #6)** — **EXISTENTIAL** impact, HIGH likelihood. Using closed commercial API (DeepSeek v4 pro) to generate training data for open-source student models likely violates API Terms of Service. All specialists trained on contaminated data become legal liabilities. **Prevention:** Use ONLY open-source models with permissive licenses for training data generation. This is a user decision that must be made before any API code is written.

3. **API cost explosion without rate limiting or budget control (Pitfall #3)** — HIGH impact, HIGH likelihood (when API code is added). A loop bug generating malformed prompts could fire thousands of API calls before detection, producing a $500-$5000+ surprise bill. **Prevention:** Hard dollar budget cap that stops all API calls when exceeded, exponential backoff with jitter, dry-run mode, cost audit logging. Test with 10 prompts first.

4. **Skip-on-existing logic produces false training completions (Pitfall #2)** — HIGH impact, MEDIUM likelihood. `train_specialists_mlx.py` checks only for `adapters.safetensors` existence, but a partial/crashed training run at iteration 200/1000 still writes that file. Undertrained specialists (20-60% complete) are deployed with no warning. **Prevention:** Check for the milestone file matching configured `iters` (e.g., `0001000_adapters.safetensors`), validate `training_metadata.json` iters field, add `--force-retrain` flag.

5. **Silent failures in long-running training jobs (Pitfall #10)** — HIGH impact, MEDIUM likelihood. `try/except` catches training crashes and continues to next specialist with only a traceback print. User sees training output wall and misses the single error line. **Prevention:** Structured logging (JSON lines), `TRAINING_STATUS.json` per specialist, post-training adapter load test, assert all specialists trained successfully at end.

6. **Cross-niche data contamination from streaming dataset reseeding (Pitfall #5)** — MEDIUM impact, HIGH likelihood. Each niche re-streams Common Pile from the beginning independently. No deduplication across niches. StackExchange documents appear in both `qa_technical` AND `code`. Specialists share 15-30% training data, evaluations overstate differentiation. **Prevention:** Jaccard overlap computation between niches, MinHash deduplication, log overlap percentage in metadata.

7. **Missing validation metrics in training metadata (Pitfall #12)** — MEDIUM impact, HIGH likelihood. `training_metadata.json` captures only config (iters, batch_size, lora_params) with zero performance metrics. Cannot determine if specialist is good or bad without manual re-evaluation. **Prevention:** Capture `final_train_loss`, `best_val_loss`, perplexity, and loss curves. Run quick benchmark after training (10 test prompts, BLEU/ROUGE).

8. **OOM on Apple Silicon during 30B-A3B LoRA training (Pitfall #7)** — HIGH impact, MEDIUM likelihood. Qwen3-30B-A3B (~55GB in bf16) plus optimizer states (AdamW = 2x params) pushes a 64GB Mac Studio to its limit. **Prevention:** Pre-flight memory estimator, start with batch_size=1, reduce num_layers to 8, use qLoRA (4-bit base quantization) to cut memory ~75%.

## Implications for Roadmap

Based on combined research across all four dimensions, a synthesized 7-phase roadmap respecting hard dependency chains, existing code bugs, and the teacher licensing decision gate. This merges ARCHITECTURE.md's 7 build-order phases with FEATURES.md's 3 value-delivery phases.

### Phase 1: Foundation & Bug Fixes
**Rationale:** Two silent data-corrupting bugs exist in current code (chat template mismatch, skip-on-existing false completions). Every subsequent phase trains specialists — if these bugs aren't fixed first, all output is silently corrupted. Foundation wiring (directory restructure, config YAML, gitignore) is zero-risk and unblocks all new modules.
**Delivers:** Fixed chat template using `tokenizer.apply_chat_template()`, fixed skip logic with milestone file check, relative → absolute path resolution, metadata field validation for Common Pile schema drift, versioned dataset/adapter directories, YAML config hierarchy, directory restructure, `.gitignore` updates, `pyproject.toml` + `requirements.txt`.
**Addresses:** FEATURES: existing pipeline hardening. ARCHITECTURE: Phase A (Foundation).
**Avoids:** Pitfalls #1 (chat template), #2 (skip-on-existing), #4 (metadata field drift), #11 (relative paths), #16 (hardcoded niche formats), #17 (no versioning).

### Phase 2: Teacher API & Synthetic Data Generation
**Rationale:** Synthetic data generation is a hard prerequisite for knowledge distillation (Phase 5). The API client must be built with cost control from day one — retrofitting budget caps after an incident is too late. This phase is gated on the **teacher licensing decision** (Pitfall #6) — the user must decide whether to use DeepSeek v4 pro API (commercial, potential ToS violation) or open-source alternatives (Llama 3.1, Qwen 3, DeepSeek-V3 distilled).
**Delivers:** `TeacherClient` with retry/backoff/cost tracking/hard budget cap, `SyntheticDataGenerator` with per-niche prompt templates and output quality filtering, mock API test fixtures.
**Uses:** `openai` (existing), `tenacity` (existing), `mlflow` (new — logging API calls as MLflow runs).
**Implements:** ARCHITECTURE: Phase B (`distill/teacher.py`, `distill/synthetic.py`).
**Avoids:** Pitfall #3 (API cost explosion — hard budget cap from day one), #6 (licensing — resolved before code written).

### Phase 3: Training Hardening
**Rationale:** Before training new specialists or scaling to N niches, the existing training pipeline needs hardening: config extraction (deduplicate `OVERRIDES` dicts), per-niche LoRA rank tuning, memory safety checks, and proper error tracking. This phase makes existing training production-grade before adding new capabilities.
**Delivers:** `TrainingConfig` dataclass (single source of truth), `SpecialistTrainer` wrapper, per-niche rank A/B testing framework, pre-flight memory estimator, structured logging (JSON lines), `TRAINING_STATUS.json`, validation metrics in metadata (loss curves, perplexity), cross-niche deduplication.
**Implements:** ARCHITECTURE: `training/config.py`, refactored `training/train_specialists_mlx.py`.
**Avoids:** Pitfalls #2 (skip logic — refined in Phase 1, validated here), #5 (cross-niche contamination), #7 (OOM), #8 (LoRA rank wrong), #10 (silent failures), #12 (missing validation metrics).

### Phase 4: Evaluation & Experiment Tracking
**Rationale:** Evaluation is a hard dependency for distillation (can't measure distillation quality without eval) and training (can't compare specialists without metrics). Experiment tracking should be built alongside evaluation since eval results are what you track. These two are tightly coupled — build them together.
**Delivers:** `Evaluator` (perplexity, accuracy, latency per specialist on held-out test sets using MLX), `Benchmarker` (head-to-head comparison), `lm-eval` integration for standard benchmarks (base model calibration via HF backend), `ExperimentTracker` with MLflow integration (run comparison, artifact management, hyperparameter logging).
**Uses:** `mlflow` (new), `lm-eval` (new), `nltk` (existing — BLEU/ROUGE).
**Implements:** ARCHITECTURE: Phase D (`eval/`) + Phase C partially (`pipeline/experiment.py`).
**Avoids:** Pitfall #12 (validation metrics — addressed in Phase 3, consumed here).

### Phase 5: Knowledge Distillation
**Rationale:** Core milestone deliverable. Depends on evaluation (Phase 4) and synthetic data generation (Phase 2) — both must be operational before distillation can be built or validated. Logit-based distillation (temperature-scaled KL divergence) is the primary path; subspace extraction (SVD on teacher logit matrices) is research-grade and should be an optional enhancement. Temperature calibration (Pitfall #9) is essential for quality.
**Delivers:** `Distiller` with logit transfer (temperature-scaled KL divergence loss as additional training signal), subspace extraction via SVD for C++ router vectors (optional), temperature sweep framework, teacher logit extraction via `logprobs=True` on DeepSeek API.
**Uses:** `openai` (existing — `logprobs` parameter), `scikit-learn` (existing — SVD), `numpy` (existing — KL computation).
**Implements:** ARCHITECTURE: Phase E (`distill/distillation.py`).
**Avoids:** Pitfall #9 (temperature miscalibration — temperature sweep framework), #6 (licensing — resolved in Phase 2).

### Phase 6: Orchestration & Pipeline Unification
**Rationale:** Wraps all existing stages into a single-command DAG. This is logically last among new capabilities (depends on everything working independently). Or staging here ensures the orchestrator configures stages that actually exist and work.
**Delivers:** `PipelineRunner` (YAML config → stage execution → artifact collection), `PipelineConfig` dataclass, CLI entry point (`orchestrate.py`), resumability (checkpoint detection — skip completed stages, retry failed ones), MLflow run grouping.
**Implements:** ARCHITECTURE: Phase C (`pipeline/pipeline.py`).
**Avoids:** Pitfall #10 (silent failures — structured logging from Phase 3 consumed here, orchestrator aggregates status).

### Phase 7: FP4 Quantization & Deployment Packaging
**Rationale:** The bridge from Python training pipeline to C++ engine. FP4 binary format must align exactly with C++ `FP4Codec` spec — round-trip tests are non-negotiable. This phase is partially parallelizable with Phases 5-6 (doesn't depend on distillation or orchestration, depends on having trained adapters) but is placed last because the C++ `FP4Codec.hpp` may need refinement based on binary format definition.
**Delivers:** `FP4Exporter` (safetensors → FP4 binary + metadata JSON), `manifest.json` catalog for C++ engine, adapter merging (`mlx_lm.fuse()`), round-trip tests (Python quantize → C++ load → dequantize → compare MSE), tokenizer export for C++ alignment.
**Implements:** ARCHITECTURE: Phase F (`quantize/fp4_export.py`) + Phase G (integration testing).
**Avoids:** Pitfalls #15 (FP4 on LoRA weights), #18 (tokenizer mismatch with C++), #19 (LoRA adapter format for MNN), #20 (FP4 layout mismatch).

### Phase Ordering Rationale

- **Bug fixes first (Phase 1):** Chat template mismatch and skip-on-existing are silently corrupting output today. Every subsequent phase trains specialists — building on broken training produces garbage at every stage. Fixing existing bugs is the absolute prerequisite.
- **Teacher API before distillation (Phase 2 → 5):** Synthetic data is the distillation input. Cost controls (budget cap, backoff) must be built with the API client — retrofitting after an incident is too late. The teacher licensing decision gates Phase 2 entirely.
- **Evaluation before distillation (Phase 4 → 5):** Can't measure distillation quality without evaluation metrics. Building eval first provides the yardstick for all subsequent work.
- **Training hardening before scaling (Phase 3):** Existing pipeline trains 5 specialists with a single config. Before scaling to N niches with A/B testing, extract configs, add validation metrics, fix cross-niche contamination — otherwise the "N specialist" output is questionable quality at scale.
- **Orchestration last among new code (Phase 6):** The orchestrator wraps stages that must exist first. Building orchestration before stages exist means building against stubs — wasteful and fragile.
- **FP4 + integration last (Phase 7):** Depends on having trained adapters to quantize. Parallelizable with earlier phases for development, but final integration validation requires complete pipeline output. The C++ integration contract (binary format, manifest schema) must be validated end-to-end.

### Research Flags

**Phases likely needing deeper research during planning** (`/gsd-plan-phase --research`):

- **Phase 2 (Teacher API):** Teacher licensing decision is unresolved. Research needed: legal analysis of DeepSeek v4 pro API ToS for derivative training, comparison of open-source teacher alternatives (DeepSeek-V3, Llama 3.1 405B, Qwen 3), evaluation of synthetic data quality from open-source vs commercial teachers. This is the single highest-risk open question.
- **Phase 5 (Knowledge Distillation):** Subspace extraction is research-grade with no existing implementation in this codebase. The strategic docs describe a novel approach; feasibility assessment needed. Recommendation: build logit-based distillation first (well-understood pattern), defer subspace extraction to a follow-on phase after logit-based is validated.
- **Phase 7 (FP4 Quantization):** Bridging the C++ `FP4Codec.hpp` with Python requires defining and testing a binary format specification. The Grok vetting doc describes JPEG-style macro-block FP4; the existing codec in `src/core/fp4/` may use a different layout. Round-trip test must validate MSE < 1e-6. Also: MLX-LoRA to MNN adapter format conversion has no off-the-shelf solution — may need to export full merged model to ONNX then MNN.

**Phases with standard patterns (skip research-phase):**

- **Phase 1 (Foundation):** Directory restructure, path hygiene, gitignore — all standard Python project patterns. Bug fixes have code-level evidence and clear fixes.
- **Phase 3 (Training Hardening):** LoRA rank A/B testing and memory estimation are well-documented in MLX-LM examples. Structured logging and status tracking are standard patterns.
- **Phase 4 (Evaluation):** Perplexity computation on held-out sets is standard. `lm-eval` has extensive documentation. MLflow experiment tracking is well-established.
- **Phase 6 (Orchestration):** Sequential stage runner with YAML config and checkpoint detection is a standard script-level pattern. No workflow framework needed.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All existing libraries verified at installed versions via `pip list`. New recommendations (mlflow 3.12.0, lm-eval 0.4.12) verified via PyPI release pages and official documentation. API integration pattern (openai → DeepSeek) is the documented DeepSeek recommendation. |
| Features | HIGH | All 6 existing Python scripts audited line-by-line. 5 specialist checkpoints confirmed on disk. Feature gaps identified through codebase absence + strategic doc requirements. Feature dependency chain validated against both code and ML best practices. |
| Architecture | HIGH | All existing scripts inspected for integration points. Proposed module boundaries mapped to existing code paths. C++ integration contract defined with binary format spec. File count and directory restructure enumerated. Build order respects all dependency constraints found in code. |
| Pitfalls | HIGH | 20 pitfalls identified with code-level evidence (line numbers, file paths). Impact × likelihood matrix. Detection methods and prevention strategies for each. Verified against actual code behavior, not assumptions. Phase-specific mapping table. |

**Overall confidence:** HIGH

All four research dimensions are grounded in direct codebase audit, not assumptions or external-only sources. The primary uncertainty is the teacher licensing decision (legal/compliance, not technical) and the research-grade subspace extraction approach (novelty, not ignorance). These are flagged as open questions.

### Gaps to Address

- **Teacher licensing decision (BLOCKING):** Must be resolved by the user before any API code is written. The current stack recommendation (DeepSeek v4 pro API via openai client) and the architecture design (TeacherClient → SyntheticDataGenerator → Distiller) assume API access. If the user decides open-source only, the teacher pipeline switches to local inference (requires downloading a 370B+ teacher model and running on Mac Studio — potentially infeasible on current hardware) or using open-source model APIs (e.g., Together AI, Fireworks). Resolution needed in Phase 2 planning.

- **Subspace extraction feasibility:** Strategic docs describe this as a key differentiator but no implementation exists, open-source or otherwise. Logit-based distillation (temperature-scaled KL) is the fallback. Recommendation: build logit-based first, evaluate subspace approach as a research spike in parallel. If subspace extraction works, swap it in; if not, logit-based is still a complete distillation pipeline.

- **C++ `FP4Codec.hpp` alignment:** The existing codec uses a specific binary layout (documented in `src/core/fp4/FP4Codec.hpp`). The Python `FP4Exporter` must produce byte-identical output. Plan a round-trip validation test in Phase 7 planning. If the C++ codec spec changes during Phase 4 C++ development, the Python exporter must track it.

- **MNN adapter format conversion:** No off-the-shelf MLX-LoRA → MNN converter exists. Options: (1) export full merged model (base + LoRA) to ONNX → MNN, (2) build custom safetensors → MNN weight loader in C++, (3) use MLX native inference in C++ via MLX C API (if available). This decision can be deferred to Phase 7 planning but should be flagged.

- **GPU memory for 30B training at batch_size=4:** The current config pushes a 64GB Mac Studio to its limit. qLoRA (4-bit base quantization) is the recommended mitigation for Phase 3, but it cuts base model precision. Validation needed: does qLoRA-trained specialist match bf16-trained specialist quality on held-out test sets? If not, batch_size=1 with full precision may be the only safe path (slower but correct).

## Sources

### Primary (HIGH confidence)
- **Codebase audit of `gnus-poc/`:** All 6 Python files read line-by-line. 5 specialist checkpoints confirmed in `models/specialists_mlx/`. Source niche analysis results in `data/analysis/source_based_niches.json`. Training metadata verified per specialist. Training config (OVERRIDES dicts, LoRA params) extracted.
- **Strategic docs:** ChatGPT Idea Vetting (dAMoE architecture, cost projections), Grok Vetting (FP4 pyramid quantization, Common Pile rationale, teacher licensing analysis), Grok Idea Vetting (feasibility assessment). All contexualized against actual codebase state.
- **MLX 0.30.0 quantization API:** Verified via `help(mlx.core.quantize)` in installed environment. Supports mxfp4, nvfp4, affine modes with configurable group_size and bits.
- **DeepSeek API documentation:** Confirmed OpenAI-compatible endpoint, `openai` Python SDK as official recommendation, `logprobs` parameter support for distillation logit extraction.
- **MLflow 3.12.0 release:** Verified via PyPI (released May 5, 2026). DeepSeek integration confirmed in official integrations list. LLM tracing and evaluation support confirmed.
- **lm-eval 0.4.12:** Verified via PyPI (released May 11, 2026). Lighter base install with `[hf]` extra. MLX models not directly supported — confirmed via documentation gap.

### Secondary (MEDIUM confidence)
- **deepseek-sdk 0.1.1:** Verified via PyPI (Oct 2025, single maintainer, 5.3KB). Recommendation to avoid is based on maintainer risk and redundancy with `openai` SDK — not on bugs or known issues.
- **open-webui dependency (langfuse 2.44.0):** Already installed as open-webui dependency. Confirmed via `pip list`. Not suitable for benchmark evaluation (observability/tracing tool, not evaluation harness).

### Tertiary (LOW confidence — needs validation)
- **Subspace extraction distillation:** Referenced in strategic docs as "teaching phase workflow" but no existing implementation found in codebase or open-source. Feasibility assessment needed in Phase 5 research spike.
- **C++ FP4Codec binary layout:** Documented in `src/core/fp4/FP4Codec.hpp` but not verified against the Grok vetting doc's JPEG-style macro-block description. Round-trip test required to confirm alignment.

---
*Research completed: 2026-05-27*
*Ready for roadmap: yes*
*Blocking issue: Teacher licensing decision (Pitfall #6) — user must resolve before Phase 2*
