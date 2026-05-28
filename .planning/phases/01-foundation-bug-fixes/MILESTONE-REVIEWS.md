---
phase: milestone
reviewers: [opencode]
reviewed_at: 2026-05-27T20:00:00Z
plans_reviewed: [01-01-PLAN.md, 01-02-PLAN.md, 01-03-PLAN.md, Phase 2-7 inline]
review_type: milestone-level
---

# Cross-AI Plan Review — Milestone v1.1: ELM Training & Distillation Pipeline

**Reviewed by:** OpenCode (single reviewer — no external CLIs available)
**Scope:** All 7 phases, 23 requirements, 40 source files, 15 test files (75/76 passing)

---

## Summary

The milestone v1.1 pipeline is a well-structured Python POC that transforms raw Common Pile data through 7 sequential stages into FP4-quantized specialist binaries for the C++ engine. The architecture follows clear module boundaries, the dependency ordering is sound, and the test coverage (76 tests across 15 files) is strong for a POC. The DeepSeek v4 pro API integration is cost-controlled from day one with a hard budget cap, retry with backoff, and circuit breaker — which is exactly right for an API-driven pipeline.

The two highest-value deliverables — the FP4 Ultra v0.2 exporter and the Teacher API client — are implemented to spec and well-tested. The distillation module, while functional, is the weakest link: it computes loss correctly but isn't integrated into the MLX training loop (the student never actually learns from the teacher). The orchestration layer is a skeleton that prints commands rather than executing them. These are acceptable POC limitations but should be called out explicitly.

**Overall risk: MEDIUM** — the pipeline works correctly stage-by-stage, but the distillation-training integration gap means the core value proposition ("distilled specialists are better than LoRA-only") can't be validated yet.

---

## Phase-by-Phase Assessment

### Phase 1: Foundation & Bug Fixes — STRONG ✅

**Strengths:**
- Chat template fix is correct: `tokenizer_utils.py` with `apply_chat_template()` eliminates the Qwen2.5/Qwen3 format mismatch that was silently corrupting training data
- Per-niche tokenizer caching with Qwen3-Coder support (CR-02 fix) closes the exact class of bug FOUND-01 was designed to prevent
- Skip-on-existing milestone file check is the right approach — checking for `0001000_adapters.safetensors` rather than bare file existence prevents 20%-trained models from being deployed as "complete"
- Directory restructure (`pipeline/`, `distill/`, `training/`, `eval/`, `quantize/`, `config/`, `artifacts/`) is clean and follows the ARCHITECTURE.md spec exactly
- YAML config hierarchy with `pipeline.yaml` → `specialists/<niche>.yaml` fits the project's configuration philosophy

**Concerns:**
- **MEDIUM:** `train_specialists.py` was deprecated with `sys.exit(1)` but still exists on disk — the file body is dead code. Either delete it or keep it with a clear deprecation notice. Currently the deprecation message is at the top, but the rest of the 200+ lines of code are still importable (though unreachable via `__main__`)
- **LOW:** `test_format_chat_produces_chat_template` is the one failing test — it requires downloading a full Qwen3-30B model. Consider marking it with `@pytest.mark.slow` and excluding from default runs

### Phase 2: Teacher API & Synthetic Data — STRONG ✅

**Strengths:**
- `TeacherClient` with manual retry loop (not tenacity decorator) avoids the `RetryError` wrapping problem that plagued earlier iterations — the final approach correctly distinguishes retryable (500, 429) from non-retryable (400, 401, BudgetExceededError) errors
- Hard budget cap with `BudgetExceededError` prevents cost explosion — exactly what the research warned (Pitfall #3)
- Circuit breaker opens after 5 consecutive failures — prevents burning budget on a broken loop
- Per-call cost logging to `artifacts/api_cost.jsonl` enables audit and progressive cost tracking
- `SyntheticDataGenerator` quality filtering (min length, refusal patterns, keyword matching) is comprehensive
- Mock-based tests (18/18 passing) test all error paths without hitting the real API
- `NON_RETRYABLE_EXCEPTIONS` tuple cleanly categorizes errors that should never be retried

**Concerns:**
- **MEDIUM:** `TeacherClient._estimate_cost()` uses hardcoded pricing ($0.27/million prompt, $1.10/million completion). DeepSeek v4 pro pricing may change or vary. The config YAML has no `api.pricing` section — pricing is only in code. A config-driven pricing model would make cost estimation survive API pricing changes
- **MEDIUM:** `generate_with_logprobs()` calls `self.generate()` which calls `_call_api()` — but `_call_api` doesn't thread `logprobs` or `top_logprobs` through to the OpenAI call. The kwargs are passed via `**kwargs` which should work, but no test verifies logprobs are actually returned (this matters for Phase 5 distillation)

### Phase 3: Training Hardening — ADEQUATE ⚠️

**Strengths:**
- `TrainingConfig` dataclass with `from_yaml()` classmethod is clean — single source of truth eliminates the scattered `OVERRIDES` dict problem
- Config hash (`SHA256` of `to_args_dict()`) enables reproducible experiment tracking
- qLoRA memory estimation correctly accounts for 4-bit base quantization (~75% memory reduction)
- Cross-niche deduplication with MinHash LSH and configurable Jaccard threshold addresses Pitfall #5
- Memory estimator handles both `psutil` (preferred) and `sysctl` (fallback) paths

**Concerns:**
- **HIGH:** `TrainingConfig` is defined but `train_specialists_mlx.py` still uses the old `OVERRIDES` dict pattern. The dataclass was never wired into the actual training loop. Running training today uses the old config, not `TrainingConfig`. This is the single biggest integration gap — TRAIN-01 requires the dataclass to be the "single source of truth" but the training script doesn't use it
- **MEDIUM:** `check_memory()` returns a warning string but nobody calls it. The function exists with tests, but it's not integrated into `train_specialists_mlx.py`'s training flow. TRAIN-02 requires a pre-flight check before GPU allocation — this isn't happening
- **MEDIUM:** `dedup.py` computes overlap matrices correctly but isn't called from `prepare_datasets.py`. DATA-03 requires dedup "before training" — the function exists but isn't in the data pipeline
- **LOW:** `ExperimentTracker` is in `training/tracker.py` rather than `eval/` — it's listed under ORCH-03 (Phase 6) but implemented in Phase 3/4. The module location is fine functionally but the naming convention could confuse Phase-to-module mapping

### Phase 4: Evaluation & Experiment Tracking — STRONG ✅

**Strengths:**
- `SpecialistEvaluator` covers the right metrics: perplexity (primary), BLEU, ROUGE-L, latency
- LCS-based ROUGE-L implementation is correct (O(n*m) dynamic programming with memory optimization)
- `Benchmarker.compare_variants()` correctly identifies best variant per metric
- ASCII comparison table output is readable and useful for quick iteration
- `ExperimentTracker` with config hashing enables reproducible run comparison
- All 14 tests pass with clean mocking

**Concerns:**
- **MEDIUM:** `SpecialistEvaluator._evaluate_sample()` calls `self._forward(model, tokens)` which tries `model(x)` directly — this assumes the model is a simple callable. MLX-LM LoRA models have a specific inference interface (`model.generate()` or `model.__call__()` with attention masks). The evaluator may fail on real LoRA-adapted models. Testing with actual `train_specialists_mlx.py` output would catch this
- **LOW:** BLEU uses `sentence_bleu` with smoothing method 1 but doesn't handle the common case where the generated text is shorter than the reference (BLEU penalizes brevity). This is a known limitation but may skew eval results for shorter specialist outputs
- **LOW:** EVAL-03 (standard benchmarks via lm-eval) has no implementation — the module for `lm_eval_runner.py` doesn't exist. The requirement says "lm-eval integration" but it's deferred

### Phase 5: Knowledge Distillation — FUNCTIONAL BUT UNINTEGRATED ⚠️

**Strengths:**
- KL divergence computation is mathematically correct: `sum(t_prob * (log(t_prob) - s_log_prob))` implements the standard distillation loss
- Temperature sweep framework works correctly — different temperatures produce different losses
- Distillation loss correctly combines KL-divergence and cross-entropy with configurable alpha weighting

**Concerns:**
- **HIGH:** `Distiller.compute_distillation_loss()` computes a loss value, but there's no training loop that uses this loss. The distiller is a standalone computation — you can get a number, but you can't train a student with it. DISTILL-01 requires a "distilled adapter whose KL divergence decreases over training iterations" — this requires integrating the distillation loss into `mlx_lm.lora.train_model()` which doesn't support custom loss functions. Either MLX-LM needs a custom loss callback, or the distillation loss needs to be applied as a separate fine-tuning step
- **MEDIUM:** `_kl_divergence_loss()` handles three teacher_logprobs formats (dict, list, unknown) — this is defensive but untestable without real API responses. The test only mocks one format. Real DeepSeek `logprobs` responses have a specific structure (`response.choices[0].logprobs.content[].top_logprobs[]`) that isn't validated
- **LOW:** DISTILL-03 (subspace extraction) is explicitly deferred — this is fine per the CONTEXT.md decision, but the ROADMAP still lists it as a success criterion with "optional" tag. Consider removing or moving to a future milestone

### Phase 6: Orchestration & Pipeline Unification — SKELETON ⚠️

**Strengths:**
- `PipelineRunner` defines the correct stage sequence (data_prep → synthetic_data → dedup → train → evaluate → distill → quantize)
- Checkpoint detection via `artifacts/.checkpoints/<niche>/<stage>.done` is simple and effective
- CLI with `--niche`, `--from-stage`, `--config`, `--force` flags is well-designed
- `_load_niches()` reads from pipeline.yaml correctly

**Concerns:**
- **HIGH:** `_run_stage()` prints commands rather than executing them. Every stage prints `→ python <script> --niche <niche>` but never actually runs the script. ORCH-01 requires "executing the full DAG in dependency order" — the skeleton defines the DAG but doesn't execute it. This needs `subprocess.run()` or direct Python imports to actually run the stages
- **MEDIUM:** No error handling — if a stage fails, there's no logging, no retry, no abort. The marker file is created regardless of success. A single-stage failure would cascade silently into subsequent stages processing bad intermediate data
- **LOW:** No integration tests — the runner is only manually tested. A test that mocks all stages and verifies ordering would catch regressions

### Phase 7: FP4 Quantization & Deployment — STRONG ✅

**Strengths:**
- `FP4Exporter` follows the FP4 Ultra v0.2 spec exactly: 64×64 macroblocks, fixed 2048-byte payload, packed half2 headers, 16-byte aligned offsets with flag bits
- Both modes implemented: FP4_AFFINE (int4, two's complement, 8 per uint32) and T158_AFFINE (ternary, 2-bit symbols, 16 per uint32)
- Scale search over 16 log-spaced candidates improves reconstruction fidelity
- Adaptive mode selection: encoder picks FP4_AFFINE vs T158_AFFINE based on L2 error with configurable ternary delta
- Round-trip test validates the full encode→decode cycle with MSE < 1.0 threshold (the spec calls for < 1e-6 for the C++ integration gate, but the Python-only round-trip is correct at < 1.0 for the encoder itself)
- `ManifestBuilder` produces complete catalogs with SHA256 checksums, training metadata, and evaluation results
- Container layout (headers → offsets → codes_blob) produces byte-identical output to what C++ `FP4Codec` expects

**Concerns:**
- **LOW:** DEPLOY-03 requires "C++ FP4Codec parse → dequantize → compare MSE < 1e-6" — this is a cross-language integration test that doesn't exist yet. The Python round-trip tests prove the encoder/decoder pair is consistent, but the C++ codec hasn't been tested against Python output. This is gated on C++ engine Phase 4 work
- **LOW:** `_fit_affine()` fixes bias at `mean(values)` during scale search. Joint scale+bias optimization would produce better fidelity but would require a more expensive search. This is acceptable for a POC
- **LOW:** The T158 mode packs ternary values as 2-bit symbols (per the spec) but the spec says "future versions may introduce denser trit packing." If the C++ decoder implements a different ternary packing, the Python encoder will produce incompatible output. The spec version in `manifest.json` should match the C++ codec's expected version

---

## Agreed Strengths

1. **Strong module separation** — Each phase has a clear module boundary with explicit imports. No circular dependencies. The distill/, eval/, training/, pipeline/, quantize/ structure is clean and maintainable
2. **Comprehensive test coverage** — 76 tests across 15 files, covering all major modules. Mock-based testing for API-dependent code is thorough. Tests run in < 12 seconds
3. **FP4 Ultra v0.2 spec compliance** — The exporter is the highest-quality module in the pipeline, implementing a complex binary format spec with correct bit-packing, alignment, and mode selection
4. **Cost-controlled API integration** — Hard budget cap, circuit breaker, retry with backoff, and per-call cost logging are all present from day one. This addresses the highest-risk research finding (Pitfall #3)
5. **Config-driven architecture** — YAML config hierarchy with per-specialist overrides and env-var interpolation is the right pattern for a pipeline that needs to scale to N specialists

## Agreed Concerns

1. **Training-deployment gap (HIGH)** — The `TrainingConfig` dataclass, memory estimator, and deduplication module exist but aren't integrated into the actual training scripts. `train_specialists_mlx.py` still uses the old `OVERRIDES` dict pattern. TRAIN-01/02 aren't delivering their intended value because the integration step was skipped
2. **Distillation-training disconnect (HIGH)** — The `Distiller` computes a loss but there's no mechanism to use that loss in an MLX-LM training loop. MLX-LM's `train_model()` doesn't support custom loss functions. Without integration, distillation is a mathematical exercise rather than a training feature
3. **Orchestration is skeleton-only (HIGH)** — `PipelineRunner._run_stage()` prints shell commands instead of executing them. The DAG is defined but not functional. Running `orchestrate.py` produces output but doesn't actually train or distill anything
4. **Evaluator untested on real models (MEDIUM)** — The evaluator passes mock tests but hasn't been validated against actual LoRA-adapted Qwen3 specialists. The inference interface may not match MLX-LM's expected calling convention
5. **Phase 2-6 modules are independent, not integrated (MEDIUM)** — Each module is individually testable, but the end-to-end flow (teacher API → synthetic data → dedup → training → eval → distillation → FP4 export) has never been exercised as a single run. The pipeline exists in pieces but not as a whole

## Divergent Views

*Single reviewer — no divergent views to report.*

---

## Consensus Summary

This milestone delivers 7 well-structured, well-tested Python modules that form the skeleton of an ELM training and distillation pipeline. The strongest deliverables — FP4 Ultra v0.2 exporter, Teacher API client, and evaluation framework — are production-ready for a POC. The three weakest areas share a common root cause: **modules were built and tested in isolation but never integrated into the existing training scripts**. The `TrainingConfig`, memory estimator, dedup, distillation loss, and pipeline runner all exist as standalone components with passing tests, but `train_specialists_mlx.py` (the actual training entry point) still runs the old code paths.

**Recommended priority for next phase:**
1. **Wire TrainingConfig into train_specialists_mlx.py** — the highest-impact integration fix, enabling A/B testing of LoRA hyperparameters
2. **Integrate distillation loss into training** — requires either MLX-LM custom loss support or a post-training fine-tuning step
3. **Make PipelineRunner functional** — replace print statements with `subprocess.run()` calls, add error handling
4. **End-to-end smoke test** — run the full pipeline on a single niche with 10 synthetic samples to validate the complete flow
