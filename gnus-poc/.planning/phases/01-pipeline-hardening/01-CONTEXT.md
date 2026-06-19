# Phase 1: Pipeline Hardening - Context

**Gathered:** 2026-06-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Delivers a reliable, production-grade 7-stage training pipeline with multi-teacher cascade, budget enforcement, retry with exponential backoff, circuit breaker protection, and validated checkpoint resume. Takes the existing skeleton pipeline (which prints commands but doesn't execute them) and makes it actually run end-to-end for all 5 specialist niches.
</domain>

<decisions>
## Implementation Decisions

### Teacher Model Cascade (Multi-Teacher)
- **D-01:** Three-tier benchmark-routed teacher mesh. Level 1 (always): DeepSeek v4 Fast — fastest/cheapest entry point. Level 2 (domain-routed): selected from a pre-configured benchmark table by domain strength. Known mappings: DSv4 Pro strong at orchestration, GLM 5.2 strong at coding. The benchmark table starts as a static YAML config and evolves dynamically as perplexity/evaluation data accumulates across runs.
- **D-02:** Escalation trigger — when Level 1 output confidence falls below a configurable threshold, escalate to the best Level 2 teacher for that domain. Confidence measured via teacher logprobs (mean token probability). Level 2 only runs when Level 1 is insufficient — not always.
- **D-03:** GLM 5.2 is NOT a mandatory final pass. It runs only when routed by the benchmark table for its strong domains, or when DSv4 Pro's output is also below threshold and GLM 5.2 rates higher for that domain. The cascade is: Fast → (best Level 2 by benchmark) → (try other Level 2 if first is still below threshold).
- **D-04:** Each teacher gets its own config entry (model name, API key env var, base URL, max_tokens, temperature) in `pipeline.yaml` as a list. API keys stored in `.env` only — never committed.

### Teacher API Integration
- **D-05:** All teachers use Anthropic/OpenAI-compatible API. The existing `TeacherClient` (OpenAI client) works for DSv4 Fast, DSv4 Pro, and GLM 5.2 — no separate client class needed per provider. GLM 5.2 is accessible via an OpenAI-compatible endpoint.
- **D-06:** Teacher selection is config-driven — adding a new teacher requires only a YAML config entry + API key, no code change.

### Pipeline Runner
- **D-07:** `pipeline/runner.py` must actually invoke stage commands via subprocess, not just print them. Each stage gets its own module/script execution with stdout/stderr capture and exit code checking.
- **D-08:** Error handling depends on error type:
  - Connection/network errors → exponential backoff with configurable retries, then circuit breaker.
  - API errors (4xx) → log and abort (non-retryable).
  - Stage execution errors → abort current niche, continue to next niche (don't abort entire pipeline for one niche failure).
  - Data errors (missing files, schema mismatch) → abort with clear error message.
- **D-09:** Per-stage retry count and backoff configurable in `pipeline.yaml`.

### Budget & Cost Controls
- **D-10:** Budget cap (`budget_cap_usd`) persists cumulative spend to `artifacts/api_cost.jsonl` (already logged) AND a summary file (`artifacts/.budget_state.json`). Budget enforcement reads the persisted total on startup — not just in-memory.
- **D-11:** Budget check happens before every teacher API call. When cap exceeded, all teacher calls stop. Synthetic data and distillation stages that depend on teacher calls fail gracefully with BudgetExceededError logged.

### Checkpoint Validation
- **D-12:** Checkpoints validate stage outputs before marking complete — not just empty `.done` marker files. Validation checks per stage:
  - `data_prep` → dataset directory exists with expected files
  - `synthetic_data` → output JSONL has minimum row count, non-empty responses
  - `dedup` → normalized hash file exists, dedup count logged
  - `train` → adapter weights file + `training_metadata.json` exist and are loadable
  - `evaluate` → evaluation metrics JSON exists with required fields
  - `distill` → distillation loss log exists with decreasing loss curve
  - `quantize` → FP4 export files exist with correct header format
- **D-13:** `--force` flag bypasses checkpoint validation and re-runs all stages. `--from-stage` resumes from any stage with checkpoint awareness. Checkpoints are per-niche, per-stage.

### Claude's Discretion
- Exact retry count defaults and backoff multipliers
- Benchmark table YAML schema and initial pre-configured values
- Budget state file format
- Checkpoint validation check implementations (specific assertions per stage)
- Circuit breaker half-open recovery interval
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Planning
- `.planning/PROJECT.md` — Key decisions: adapter-based specialists, per-specialist quantization, single-machine scope
- `.planning/REQUIREMENTS.md` — Phase 1 requirements: PIPE-01 through PIPE-03, TEACH-01 through TEACH-03
- `.planning/ROADMAP.md` — Phase 1 goal and success criteria

### Architecture Docs (GeniusCognitiveSystem)
- `../../docs/architecture/03-model-and-router.md` — ELM model architecture, specialist types
- `../../docs/architecture/13-eggroll-swarm-retraining.md` — Teacher→student distillation architecture (future phases)
- `../../docs/architecture/16-ultra-fp4-format.md` — Ultra FP4 quantization format spec

### Existing Implementation
- `config/pipeline.yaml` — Current single-teacher config, training/eval/fp4 settings
- `distill/teacher.py` — Current TeacherClient (OpenAI-compatible, single model)
- `distill/teacher_errors.py` — Existing error types (BudgetExceededError, CircuitBreakerOpenError, TeacherConfigError)
- `pipeline/runner.py` — Current pipeline runner (7 stages, prints commands, doesn't execute)
- `distill/distillation.py` — KD distiller (temperature, alpha, sweep)
- `training/train_specialists_mlx.py` — MLX LoRA training (active implementation)
- `training/train_specialists.py` — Deprecated (do not modify)
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`TeacherClient`** (`distill/teacher.py`): Already has OpenAI-compatible client, cost tracking, circuit breaker, exponential backoff, budget check. Extend for multi-teacher support rather than rewrite.
- **`PipelineRunner`** (`pipeline/runner.py`): Has 7-stage list, checkpoint detection, `--force`/`--from-stage` flags. Needs actual subprocess execution.
- **`TeacherConfigError` / `BudgetExceededError` / `CircuitBreakerOpenError`** (`distill/teacher_errors.py`): Reuse existing error types.
- **`pipeline.yaml`** (`config/pipeline.yaml`): Existing config structure with teacher, training, evaluation, fp4_export sections. Extend teacher section to a list.

### Established Patterns
- YAML config loaded at init time, resolved relative to project root
- Cost logging to JSONL (`artifacts/api_cost.jsonl`)
- Checkpoint markers as `.done` files in `artifacts/.checkpoints/<niche>/`
- Per-specialist niche iteration in pipeline loop

### Integration Points
- `TeacherClient` is instantiated in `distill/synthetic.py` and `distill/distillation.py` — multi-teacher changes flow through here
- `PipelineRunner.run()` is the main entry point — subprocess execution added here
- Budget state must be readable by all modules that call the teacher API
</code_context>

<specifics>
## Specific Ideas

- Benchmark table: pre-configured YAML mapping domain → {teacher: strength_score}. Example structure:
  ```yaml
  teacher_benchmark:
    coding:       {deepseek-v4-pro: 0.82, glm-5.2: 0.91}
    orchestration: {deepseek-v4-pro: 0.88, glm-5.2: 0.75}
    medical:      {deepseek-v4-pro: 0.79, glm-5.2: 0.85}
  ```
  Evolves over time as perplexity data accumulates per teacher/domain pair.

- Escalation flow: Fast (always) → check confidence → if below threshold, query benchmark table for best Level 2 teacher for detected domain → run Level 2 → if still below, try next best Level 2 → return best result.
</specifics>

<deferred>
## Deferred Ideas

- Dynamic benchmark table evolution from evaluation data — Phase 2 (Training & Distillation Quality)
- "Always run GLM 5.2 final pass" mode — user explicitly rejected; GLM runs only when benchmark-routed
- Per-teacher cost tracking and cost-based teacher selection — future enhancement
- Distributed teacher execution across multiple nodes — out of scope (single-machine)
</deferred>

---

*Phase: 01-pipeline-hardening*
*Context gathered: 2026-06-19*
