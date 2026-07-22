---
phase: 01-pipeline-hardening
plan: 02
type: execute
subsystem: distill
tags: [backend, multi-provider, refactor, teacher-api, openai, anthropic]
requires: [01-01]
provides: [dual-backend-teacher-client]
affects: [distill/synthetic.py, distill/distillation.py]
tech-stack:
  added: [anthropic SDK, openai SDK, abc-based backend interface]
  patterns: [strategy-pattern, lazy-initialization, uniform-response-wrapper]
key-files:
  created:
    - distill/backends/__init__.py
    - distill/backends/base.py
    - distill/backends/openai_backend.py
    - distill/backends/anthropic_backend.py
  modified:
    - distill/teacher.py
    - distill/teacher_errors.py
    - tests/test_teacher.py
decisions:
  - "Lazy backend construction: backends are created on first use, not at TeacherClient.__init__ time, enabling test injection without mocking real SDK clients"
  - "Uniform response dict ({content, prompt_tokens, completion_tokens, raw_response}) across all backends with _ResponseWrapper for backward-compatible .choices[0].message.content access"
  - "API key resolution priority: LITELLM_API_KEY > {ENDPOINT}_API_KEY > {API_TYPE}_API_KEY"
  - "Anthropic message conversion: system messages extracted to top-level param, user/assistant passthrough"
  - "Anthropic cost estimation uses default formula; marked for per-model pricing in future phase"
metrics:
  duration_seconds: 264
  tasks_completed: 3
  tests_passing: 17
  completed_date: 2026-06-19
---

# Phase 01 Plan 02: Multi-Backend TeacherClient Refactor

Refactored the single-backend (OpenAI-only) `TeacherClient` into a multi-backend architecture supporting both OpenAI and Anthropic API backends, dispatched per-call based on the model's endpoint `apiType` configuration.

## Tasks Completed

### Task 1: Create backend interface and extract OpenAI backend

Created `distill/backends/` module:
- `base.py`: Abstract `TeacherBackend` with `generate()`, `estimate_cost()`, `backend_type`
- `openai_backend.py`: `OpenAIBackend` wrapping `openai` SDK `chat.completions.create`
- `__init__.py`: Module init exporting API surface

**Commit:** `1b66c2b`

### Task 2: Implement Anthropic backend

Created `distill/backends/anthropic_backend.py`:
- `AnthropicBackend` wrapping `anthropic` SDK `messages.create`
- `_convert_messages()`: OpenAI-format messages to Anthropic format (system as top-level param, user/assistant passthrough)
- Response extraction: `content[0].text`, `usage.input_tokens`, `usage.output_tokens`
- Extended thinking params passed through via `**kwargs`

**Commit:** `40c0461`

### Task 3: Refactor TeacherClient and update tests

Refactored `distill/teacher.py`:
- Lazy backend construction via `_get_or_create_backend()` — backends created on first use
- `_resolve_backend(model_name)` dispatches to correct backend by endpoint `apiType`
- `generate(model_name, messages, **kwargs)` — model_name is first positional arg
- `_ResponseWrapper` adapts uniform backend dict for backward-compatible `.choices[0].message.content`
- `_check_circuit`, `_check_budget`, retry logic preserved unchanged

Added `BackendNotFoundError` to `distill/teacher_errors.py`.

Updated `tests/test_teacher.py`:
- Config fixture updated for two-layer `endpoints` + `models` format
- New tests: `test_dispatches_to_correct_backend_by_api_type`, `test_dispatches_to_anthropic_backend`, `test_resolve_backend_for_unknown_model_raises`
- All 17 tests passing

**Commit:** `bb6d1c1`

## Architecture

```
distill/backends/
    __init__.py              → exports TeacherBackend, OpenAIBackend, AnthropicBackend
    base.py                  → abstract TeacherBackend (generate, estimate_cost, backend_type)
    openai_backend.py        → OpenAIBackend (openai SDK chat.completions.create)
    anthropic_backend.py     → AnthropicBackend (anthropic SDK messages.create, message conversion)

distill/teacher.py           → TeacherClient (lazy backend registry, _resolve_backend dispatch)
distill/teacher_errors.py    → +BackendNotFoundError
```

**Dispatch flow:**
```
generate("deepseek-v4-fast", messages)
  → _resolve_backend("deepseek-v4-fast")
    → models["deepseek-v4-fast"].endpoint = "litellm"
    → _get_or_create_backend("litellm")
      → endpoint["litellm"].apiType = "openai" → OpenAIBackend
  → backend.generate() → uniform dict → _ResponseWrapper
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Module-level _BACKEND_CLASSES dict captured real class references before test patch**
- **Found during:** Task 3 test execution
- **Issue:** `_BACKEND_CLASSES` dict evaluated at module import time, so `patch("distill.teacher.OpenAIBackend")` didn't affect it. Tests tried to mock the backend classes but the real SDK clients were still created.
- **Fix:** Removed module-level dict. Replaced with `_backend_class_for()` function (looks up names at call time). Also converted backend construction from eager (in `__init__`) to lazy (`_get_or_create_backend`) so tests can inject mocks into `client._backends` before any real SDK client is constructed.
- **Files modified:** `distill/teacher.py`
- **Commit:** `bb6d1c1`

## Verification

- `python -m pytest tests/test_teacher.py -x -v` — 17/17 passed
- `python -c "from distill.teacher import TeacherClient; print('import OK')"` — passes
- `python -c "from distill.backends import TeacherBackend, OpenAIBackend, AnthropicBackend; print('backends OK')"` — passes
- All plan acceptance criteria verified: backend dispatch by apiType, unknown model error, generate signature, properties preserved, config format supported

## Known Stubs

None. All backends and the TeacherClient refactor are fully implemented — no placeholder code, mock defaults, or TODO-fallback paths.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: api-key-resolution | distill/teacher.py | `_resolve_api_key` searches multiple env vars (LITELLM_API_KEY, endpoint-specific, apiType-specific). Key leakage via error messages is mitigated (error message lists candidate var names, not values). |
| threat_flag: message-forwarding | distill/backends/anthropic_backend.py | System messages joined with newline and forwarded as top-level param. Content is not validated beyond type coercion to str. |

## Self-Check

- `distill/backends/__init__.py` — EXISTS
- `distill/backends/base.py` — EXISTS
- `distill/backends/openai_backend.py` — EXISTS
- `distill/backends/anthropic_backend.py` — EXISTS
- `distill/teacher.py` — EXISTS (refactored)
- `distill/teacher_errors.py` — EXISTS (updated)
- `tests/test_teacher.py` — EXISTS (updated)
- Commit `1b66c2b` — FOUND in git log
- Commit `40c0461` — FOUND in git log
- Commit `bb6d1c1` — FOUND in git log

## Self-Check: PASSED
