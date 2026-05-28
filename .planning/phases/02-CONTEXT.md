# Phase 2: Teacher API & Synthetic Data — Context

**Gathered:** 2026-05-27
**Status:** Ready for planning
**Mode:** Auto-generated (smart discuss)

## Phase Boundary

Build the DeepSeek v4 pro API client with cost controls, per-niche synthetic data generation, mock-testable without real API key.

**In scope:**
- DATA-01: Teacher API client — `TeacherClient` using `openai` SDK, retry/backoff via `tenacity`, hard dollar budget cap, per-call cost tracking
- DATA-02: Synthetic data generation — per-niche prompt templates, output quality filtering, JSONL output to `data/specialists/<niche>/synthetic/`

**Out of scope:**
- Distillation (Phase 5)
- Evaluation of synthetic data quality (Phase 4)
- Orchestration integration (Phase 6)
- Cross-niche dedup (Phase 3)

## Implementation Decisions

### Budget cap
Default $5.00 hard cap in `pipeline.yaml` (`api.budget_cap: 5.0`), overridable via env `DEEPSEEK_BUDGET_CAP`. TeacherClient raises `BudgetExceededError` when cap is hit. Cost tracking logs each API call cost to MLflow (when available) and a local `api_cost.jsonl`.

### Synthetic data volume
500 samples per niche initially — augments source data, doesn't replace it. Configurable per niche in `specialists/<niche>.yaml` → `synthetic_data.samples`.

### Prompt templates
Per-niche system prompts + few-shot examples in `config/specialists/<niche>.yaml` under `synthetic_data.prompts` section. Structure:
```yaml
synthetic_data:
  samples: 500
  prompts:
    system: "You are a {role} specialist..."
    few_shot:
      - user: "..."
        assistant: "..."
    user_template: "Generate a {topic} explanation..."
```

### Quality filtering
- Min 200 characters
- Must contain niche-relevant keywords (configured per niche)
- No refusal phrases: "I cannot", "I'm unable", "as an AI", "I don't have"
- Valid JSONL output (no broken lines)

### API error handling
- `tenacity` `retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))`
- Circuit breaker: after 5 consecutive failures, raise `CircuitBreakerOpenError` and stop all API calls
- All errors logged to `api_errors.jsonl` with timestamp, status code, and request context

### Mock-first testing
All tests use `responses` library (already installed) to mock DeepSeek API endpoints. Tests cover:
- Successful synthetic data generation
- Budget cap enforcement
- Retry on 429/500 errors
- Circuit breaker activation
- Quality filter rejection of bad outputs
- Empty response handling

## Existing Code Insights

- `gnus-poc/.env` already contains `DEEPSEEK_API_KEY`
- `openai` 1.101.0 and `tenacity` already installed in .venv
- `responses` 0.25.7 available for mocking
- `config/pipeline.yaml` has `api` section placeholder
- `config/specialists/*.yaml` exist for all 5 niches

## Specific Ideas

- `distill/__init__.py` — exports TeacherClient, SyntheticDataGenerator
- `distill/teacher.py` — TeacherClient class with cost tracking, budget cap, circuit breaker
- `distill/synthetic.py` — SyntheticDataGenerator with config-driven prompts, quality filtering
- `tests/test_teacher.py` — mock-based tests for API client
- `tests/test_synthetic.py` — mock-based tests for data generation
- `artifacts/.gitkeep` for cost logs and error logs

## Deferred Ideas

- MLflow integration (Phase 4)
- Orchestration CLI (Phase 6)
- Real API integration tests (dev-only)
