---
status: complete
phase: 01-pipeline-hardening
source:
  - 01-01-SUMMARY.md
  - 01-02-SUMMARY.md
  - 01-03-SUMMARY.md
  - 01-04-SUMMARY.md
  - 01-05-SUMMARY.md
started: 2026-06-21
updated: 2026-06-21
---

## Current Test

[testing complete]

## Tests

### 1. Config loads and validates
expected: `python config/loader.py` self-test passes all 12 assertions. pipeline.yaml loads with correct two-layer structure. Invalid config raises descriptive ConfigValidationError.
result: pass

### 2. Per-specialist config override
expected: `ConfigLoader.get_effective_config('code')` returns config where `base_model` is overridden to `Qwen3-Coder-30B-A3B-Instruct-bf16` (from `config/specialists/code.yaml`). Training hyperparameters from specialist YAML take precedence over global defaults. Requesting unknown niche raises error listing valid niches.
result: pass

### 3. TeacherClient OpenAI backend
expected: With LiteLLM proxy running at localhost:4000 and `LITELLM_API_KEY` set in `.env`, `TeacherClient.generate('deepseek-v4-fast', messages)` returns a response with `content`, `prompt_tokens`, `completion_tokens`. The response wrapper supports `.choices[0].message.content` for backward compatibility.
result: pass
note: API key is LITELLM_API_KEY (model keys live in LiteLLM proxy config, not individual env vars)

### 4. TeacherClient backend dispatch
expected: Calling with a model whose endpoint has `apiType: openai` routes through OpenAIBackend. Models on endpoints with `apiType: anthropic` route through AnthropicBackend. Both backends produce uniform response dicts with identical field names.
result: pass

### 5. Pipeline subprocess execution
expected: `python pipeline/runner.py --niche medical --from-stage data_prep` actually invokes `data_prep.py` via subprocess (not just printing a command). Successful execution shows first 3 lines of stdout. Non-zero exit codes are captured and logged without aborting the pipeline.
result: pass

### 6. Validated checkpoints
expected: After a stage completes successfully, a JSON checkpoint file is written (not an empty `.done` file). Re-running the pipeline skips that stage. `--force` clears all checkpoints and re-runs everything. Checkpoint validation includes file existence, content quality, and schema checks per stage.
result: pass

### 7. Multi-teacher cascade
expected: Level 1 teacher (deepseek-v4-fast) runs first for every request. When logprobs mean confidence is below the configured threshold (0.7 default), Level 2 is selected from the benchmark table by detected domain. The cascade logs which teachers ran and their confidence scores.
result: pass

### 8. Budget enforcement
expected: Spend state persists to `artifacts/.budget_state.json`. After cumulative spend exceeds `budget_cap_usd` (default 5.0), all subsequent teacher API calls raise `BudgetExceededError`. `--reset-budget` flag resets spend tracking from zero.
result: pass

### 9. Circuit breaker
expected: After N consecutive failures (circuit_breaker_failure_threshold, default 5), the circuit opens and all calls immediately raise `CircuitBreakerOpenError` without hitting the network. After recovery_timeout seconds (default 60), one probe request is allowed (half-open). Success closes the circuit; failure re-opens with fresh timer.
result: pass

### 10. SyntheticDataGenerator with cascade
expected: `SyntheticDataGenerator` works with the multi-teacher cascade client. Generated examples include niche-to-benchmark-domain routing. Per-specialist synthetic prompts from config are used. Generated data passes quality checks (minimum length, non-empty responses).
result: pass

## Summary

total: 10
passed: 10
issues: 0
pending: 0
skipped: 0

## Gaps

[none]
