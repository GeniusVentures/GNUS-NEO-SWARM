# Phase 1: Pipeline Hardening - Context

**Gathered:** 2026-06-19
**Updated:** 2026-06-19 (assumptions mode — LiteLLM proxy, dual-backend, scope expansion)
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

### API Client Architecture (Dual-Backend)
- **D-05:** `TeacherClient` provides a multi-backend abstraction supporting both `openai` and `anthropic` API types. The backend is selected per-call based on the model's endpoint configuration (`apiType` field). OpenAI backend uses `openai` Python SDK `chat.completions`. Anthropic backend uses `anthropic` Python SDK `messages` — enabling extended thinking, prompt caching, and citations for teacher calls.
- **D-06:** Both backends are fully implemented in Phase 1, not stubbed. All current models route through LiteLLM proxy (OpenAI-compatible), but the Anthropic backend is ready for future Anthropic-native teachers.
- **D-07:** Teacher config structure is two-layer: `endpoints` define connection details (`url`, `apiType: openai|anthropic`), and `models` map model name → endpoint reference + model identifier. Model names are literal (e.g., `deepseek-v4-pro[1m]`) — no aliasing. API keys stored in `.env` only.
- **D-08:** Adding a teacher requires only a YAML config entry (model → endpoint mapping) + API key — no code change.

### Pipeline Runner
- **D-09:** `pipeline/runner.py` must actually invoke stage commands via subprocess, not just print them. Each stage gets its own module/script execution with stdout/stderr capture and exit code checking.
- **D-10:** Error handling depends on error type:
  - Connection/network errors → exponential backoff with configurable retries, then circuit breaker.
  - API errors (4xx) → log and abort (non-retryable).
  - Stage execution errors → abort current niche, continue to next niche (don't abort entire pipeline for one niche failure).
  - Data errors (missing files, schema mismatch) → abort with clear error message.
- **D-11:** Per-stage retry count and backoff configurable in `pipeline.yaml`.
- **D-12:** Phase 1 scope includes updating `distill/synthetic.py` and `distill/distillation.py` to consume the refactored multi-backend `TeacherClient`. These are the primary teacher consumers — they must be updated in this phase, not deferred.

### Budget & Cost Controls
- **D-13:** Budget cap (`budget_cap_usd`) persists cumulative spend to `artifacts/api_cost.jsonl` (already logged) AND a summary file (`artifacts/.budget_state.json`). Budget enforcement reads the persisted total on startup — not just in-memory.
- **D-14:** Budget check happens before every teacher API call. When cap exceeded, all teacher calls stop. Synthetic data and distillation stages that depend on teacher calls fail gracefully with BudgetExceededError logged.

### Checkpoint Validation
- **D-15:** Checkpoints validate stage outputs before marking complete — not just empty `.done` marker files. Validation checks per stage:
  - `data_prep` → dataset directory exists with expected files
  - `synthetic_data` → output JSONL has minimum row count, non-empty responses
  - `dedup` → normalized hash file exists, dedup count logged
  - `train` → adapter weights file + `training_metadata.json` exist and are loadable
  - `evaluate` → evaluation metrics JSON exists with required fields
  - `distill` → distillation loss log exists with decreasing loss curve
  - `quantize` → FP4 export files exist with correct header format
- **D-16:** `--force` flag bypasses checkpoint validation and re-runs all stages. `--from-stage` resumes from any stage with checkpoint awareness. Checkpoints are per-niche, per-stage.

### Claude's Discretion
- Exact retry count defaults and backoff multipliers
- Benchmark table YAML schema and initial pre-configured values
- Budget state file format
- Checkpoint validation check implementations (specific assertions per stage)
- Circuit breaker half-open recovery interval
- Anthropic backend implementation details (extended thinking config, prompt caching strategy, citation handling)
- `endpoints` + `models` YAML schema validation rules
- `apiType` dispatch mechanism (factory pattern vs strategy pattern)
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
- `../../docs/architecture/16-sgfp4-format.md` — SGFP4 quantization format spec

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
- **`TeacherClient`** (`distill/teacher.py`): Has OpenAI client, cost tracking, circuit breaker, exponential backoff, budget check. Refactor into multi-backend architecture (OpenAI + Anthropic SDKs) supporting endpoint-driven backend selection.
- **`PipelineRunner`** (`pipeline/runner.py`): Has 7-stage list, checkpoint detection, `--force`/`--from-stage` flags. Needs subprocess execution + error handling.
- **`TeacherConfigError` / `BudgetExceededError` / `CircuitBreakerOpenError`** (`distill/teacher_errors.py`): Reuse existing error types.
- **`pipeline.yaml`** (`config/pipeline.yaml`): Existing config with teacher, training, evaluation, fp4_export sections. Replace single `teacher` block with `endpoints` + `models` two-layer structure.

### Established Patterns
- YAML config loaded at init time, resolved relative to project root
- Cost logging to JSONL (`artifacts/api_cost.jsonl`)
- Checkpoint markers as `.done` files in `artifacts/.checkpoints/<niche>/`
- Per-specialist niche iteration in pipeline loop

### Integration Points
- `TeacherClient` is instantiated in `distill/synthetic.py` and `distill/distillation.py` — must update both for new multi-backend client API
- `PipelineRunner.run()` is the main entry point — subprocess execution added here
- Budget state must be readable by all modules that call the teacher API
- LiteLLM proxy runs at localhost — all teacher traffic routes through it for OpenAI-compatible models. Anthropic-native endpoint available for future direct Anthropic API use.
</code_context>

<specifics>
## Specific Ideas

- **Teacher config structure** — two-layer: endpoints define connections, models reference endpoints:
  ```yaml
  endpoints:
    litellm:
      url: "http://127.0.0.1:4000"
      apiType: openai

  models:
    deepseek-v4-pro[1m]:
      endpoint: litellm
    deepseek-v4-fast:
      endpoint: litellm
    glm-5.2:
      endpoint: litellm
  ```
  Adding a new endpoint (e.g., direct Anthropic) requires only a new `endpoints` entry + API key. Adding a model requires only a `models` entry referencing an existing endpoint.

- **Benchmark table** — pre-configured YAML mapping domain → {model_name: strength_score}:
  ```yaml
  teacher_benchmark:
    coding:       {"deepseek-v4-pro[1m]": 0.82, "glm-5.2": 0.91}
    orchestration: {"deepseek-v4-pro[1m]": 0.88, "glm-5.2": 0.75}
    medical:      {"deepseek-v4-pro[1m]": 0.79, "glm-5.2": 0.85}
  ```
  Evolves over time as perplexity data accumulates per teacher/domain pair. Model names match the `models` registry keys.

- **Escalation flow:** Fast (always) → check confidence → if below threshold, query benchmark table for best Level 2 teacher for detected domain → run Level 2 → if still below, try next best Level 2 → return best result.
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
