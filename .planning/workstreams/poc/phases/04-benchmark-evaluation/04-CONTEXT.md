# Phase 4: Benchmark Evaluation — Context

**Gathered:** 2026-06-27
**Reviewed:** 2026-06-28 — decisions re-evaluated, high-risk items hardened
**Status:** Ready for planning

<domain>
## Phase Boundary

Scores quantized specialist models (from Phase 3) against established benchmark suites as a quality gate. Failed benchmarks feed back into distillation strategy refinement (Phase 2).

**Depends on:** Phase 3 (quantized models from SGFP4 v2 export)
**Requirements:** BMARK-01, BMARK-02, BMARK-03
</domain>

<decisions>
## Implementation Decisions (Reviewed 2026-06-28)

### Benchmark Strategy (Area A)

- **D-01: Multi-mode with separated concerns.** Three independent dimensions, not one merged flag: (1) **dataset source** — `local` files or `huggingface` datasets API, (2) **model backend** — local MLX inference or `api` (DeepSeek v4 Pro for judge-only), (3) **baseline model** — configurable reference model identity for computing deviation scores. API mode is judge-only — the specialist under test always runs locally; the API provides reference answers or verification, not the primary evaluation.
- **D-02: lm-eval-harness format with frozen reproducibility.** Use EleutherAI's `lm-evaluation-harness` standard protocols. Each benchmark uses its established shot count (MMLU=5-shot, HumanEval=0-shot, etc.). Scores are comparable to published results. Every canonical run records a reproducibility fingerprint: `harness_commit`, `task_name`, `task_revision`, `dataset_revision`, `prompt_hash`, `fewshot_seed`, `chat_template_hash`, `answer_extraction`, `generation_params`, `model_manifest_sha256`, `sgfp4_manifest_sha256`. Without this, trend analysis degrades over time.
- **D-03: Separate canonical vs diagnostic prompt modes.** Canonical mode uses each benchmark's official lm-eval-harness template — these are the scores reported and gated. **Canonical eval is frozen:** fixed prompt template, fixed few-shot examples, fixed chat template, fixed decoding params, fixed answer extraction, fixed dataset revision. Diagnostic mode allows per-benchmark prompt overrides in `config/benchmarks/<name>.yaml` for internal analysis — diagnostic scores are informational only, never gated, and may use API judges or variant prompts.

### Domain-to-Benchmark Mapping (Area B)

- **D-04: MMLU as sanity baseline, NOT blocking.** Every specialist runs MMLU (57 subjects). MMLU scores are reported for trend analysis but do NOT block production promotion. Per-subject MMLU breakdown is diagnostic — subject-scoped regressions are surfaced, not gated. Domain-specific benchmarks are the blocking gates.
- **D-05: Specialist-benchmark mapping (reviewed):**

  | Specialist | Blocking Benchmarks | Diagnostic |
  |-----------|-------------------|------------|
  | `code` | HumanEval + LiveCodeBench (code generation + test coverage) | MMLU |
  | `medical` | MedMCQA + PubMedQA + MedHELM subset + safety/refusal eval | MMLU |
  | `qa_technical` | GPQA (STEM subsets) | MMLU |
  | `encyclopedic` | RAG pipeline eval (retrieval-augmented generation quality) | MMLU |
  | `patents` | BIGPATENT (summarization only) + patent classification task (USPTO) | MMLU |

  **FRAMES:** Deferred to Phase 5. Replace with RAG pipeline eval for encyclopedic — this evaluates retrieval quality + generation fidelity, not raw model knowledge.
  **Google Patents:** Deferred to Phase 5. BIGPATENT summarization remains. Patent classification using USPTO bulk data replaces Google Patents query task.
  **Code:** LiveCodeBench added alongside HumanEval — test-case-pass-rate eval catches regressions HumanEval misses.

### Quality Gate Design (Area C)

- **D-06: Tiered gating.** Warning on first below-threshold, block on consecutive failures (following Phase 3 auto-gating pattern in `Benchmarker.gate_check()`).
- **D-07: Internal baselines, not published.** Published benchmark scores are informational context only — they reflect models at different scales and training regimes. Hard thresholds use internal baselines: the untrained backbone model score establishes the floor. Thresholds are relative-to-baseline, not absolute.
- **D-08: Hard floors before composite.** Hard floor: every blocking benchmark must pass its per-category minimum (no benchmark can catastrophically fail while others carry it). **Mandatory SGFP4 regression check:** unquantized adapter vs SGFP4 quantized model comparison isolates "model got worse because of training" from "model got worse because SGFP4 damaged it." Composite gate (2 of 3 dimensions) only activates AFTER all hard floors pass. Three dimensions: (1) benchmark scores above per-category hard floors, (2) regression from previous run ≤10%, (3) deviation from baseline model ≤20%. All thresholds configurable per specialist.

### Trend Analysis & Feedback (Area D)

- **D-09: Statistical significance, not fixed deltas.** Replace fixed percentage thresholds with paired item statistics. Bootstrap confidence intervals (95% CI) on per-benchmark score differences. A regression is significant when the CI excludes zero, not when a magic number is crossed. Per-benchmark sample sizes and variance are automatically accounted for.
- **D-10: Repair suggestions, not auto-mutation.** On below-threshold: the system generates a repair suggestion report (which categories underperformed, by how much, suggested config adjustments). The operator reviews and decides. On 3rd consecutive failure: blocks pipeline promotion — manual intervention required. The system never automatically mutates distillation config — it advises, the operator acts.
- **D-11: MetricStore is source of truth; trends are derived.** Benchmark results persist in MetricStore (one record per specialist per run). Trends are computed views over MetricStore data stored in `artifacts/trends/` as derived artifacts. Trends can be regenerated from MetricStore at any time — no independent state to drift.

### Claude's Discretion
- lm-eval-harness integration approach (Python API — `simple_evaluate()`)
- MLX model wrapper for lm-eval (`lm_eval.api.model.LM` subclass)
- Per-benchmark config file schema
- Benchmark dataset download and caching strategy
- Trend derivation from MetricStore records
- Bootstrap CI implementation for paired comparisons
- Hard floor per-category threshold defaults
- Repair suggestion report format
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Planning
- `.planning/workstreams/poc/ROADMAP.md` — Phase 4 goal and success criteria
- `.planning/workstreams/poc/REQUIREMENTS.md` — BMARK-01 through BMARK-03

### Existing Implementation (build ON TOP of)
- `eval/benchmarker.py` — Benchmarker with `compare_variants()`, `gate_check()` (SGFP4 from Phase 3)
- `eval/evaluator.py` — SpecialistEvaluator (perplexity, BLEU, ROUGE, latency)
- `eval/metric_store.py` — MetricStore (structured persistence from Phase 3)
- `config/pipeline.yaml` — Existing `eval_gates:` section to extend

### Phase 3 Context (dependencies)
- `.planning/workstreams/poc/phases/03-fp4-quantization-artifact-integrity/03-CONTEXT.md` — D-09 (eval gating pattern), D-10 (manifest)
- `quantize/fp4_exporter.py` — SGFP4 v2 export (produces models to benchmark)

### External Standards
- lm-evaluation-harness (EleutherAI) — standard LLM benchmark framework
- MMLU: 5-shot, 57 subjects
- HumanEval: 0-shot pass@1/pass@10
- MedMCQA: multiple choice medical QA
- GPQA: graduate-level science reasoning
- FRAMES: factuality + retrieval benchmark
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **Benchmarker** (`eval/benchmarker.py`): Has `compare_variants()`, `gate_check()`, `MetricStore`. Extend `gate_check()` with benchmark dimensions (MMLU score, HumanEval pass@1, etc.).
- **MetricStore** (`eval/metric_store.py`): Already persists per-specialist metrics. Extend with benchmark-specific records.
- **SpecialistEvaluator** (`eval/evaluator.py`): Perplexity, BLEU, ROUGE, latency. Benchmark evaluation is a new capability layered on top.
- **Pipeline runner** (`pipeline/runner.py`): Benchmark stage to invoke after quantize stage.

### Established Patterns
- Auto-gating with consecutive failure tracking (Phase 3 `gate_check()`)
- ConfigLoader front-loading validation (`_validate_teacher()`, `_validate_fp4_export()`)
- Two-layer config (endpoints/models) → extend for benchmark configs
- Per-specialist YAML overrides (`config/specialists/<niche>.yaml`)

### Integration Points
- **Pipeline runner**: New benchmark stage after quantize
- **Benchmarker.gate_check()**: New benchmark gate dimensions
- **MetricStore**: New benchmark metric methods
- **ConfigLoader**: `_validate_benchmarks()` validation
</code_context>

<deferred>
## Deferred Ideas

- LiveBench-style continuously updated benchmarks — v2
- Full LLM-as-judge evaluation — v2
- Cross-specialist ensemble scoring — separate phase
- Automated hyperparameter search from benchmark results — separate phase
</deferred>

---
*Phase: 04-benchmark-evaluation*
*Context gathered: 2026-06-27*
