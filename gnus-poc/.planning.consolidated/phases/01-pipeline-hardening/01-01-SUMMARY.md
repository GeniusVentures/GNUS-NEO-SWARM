---
phase: 01-pipeline-hardening
plan: 01
type: execute
autonomous: true
wave: 1
subsystem: config
tags: [config, yaml, validation, teacher-benchmark, per-specialist-overrides, endpoints-models]
provides: Two-layer pipeline config schema, centralized ConfigLoader with validation, per-specialist deep-merge override resolution
affects: "config/pipeline.yaml, config/loader.py, config/__init__.py"
requires: []
tech-stack:
  added: []
  patterns: [two-layer-endpoints-models, deep-merge-config-override, schema-validation-with-key-paths]
key-files:
  created:
    - config/loader.py
  modified:
    - config/pipeline.yaml
    - config/__init__.py
decisions:
  - "Two-layer config: endpoints define WHERE (connection), models define WHAT (model identity)"
  - "API key naming convention: {UPPERCASE_MODEL_NAME}_API_KEY in .env only, never in YAML"
  - "Per-specialist base_model override: specialist.base_model -> training.base_model in effective config"
  - "Deep-merge rules: dicts merge recursively, lists replace, scalars replace"
  - "Benchmark table is static YAML at this phase; dynamic evolution deferred to Phase 2"
metrics:
  duration: 98s
  completed_date: 2026-06-19
---

# Phase 1 Plan 1: Two-Layer Pipeline Config & ConfigLoader Summary

**One-liner:** Restructured pipeline config from flat single-teacher block into a two-layer `endpoints` + `models` architecture with benchmark table and per-stage retry, backed by a centralized ConfigLoader with schema validation and per-specialist override resolution.

## Plan Objective

Restructure the pipeline configuration from a flat single-teacher block into a two-layer `endpoints` + `models` architecture with a benchmark table and per-stage retry settings. Create a centralized config loader with schema validation and per-specialist override resolution.

Purpose: Enable "add a teacher via YAML config only" (D-08), support dual-backend API dispatch (D-05), and provide the config contract that Plans 02-05 depend on.

## Tasks Completed

| # | Task | Type | Commit | Files |
|---|------|------|--------|-------|
| 1 | Restructure pipeline.yaml to two-layer endpoints/models architecture | auto | `ac480cd` | `config/pipeline.yaml` |
| 2 | Create config/loader.py with validation and per-specialist overrides | auto | `ccf6b14` | `config/loader.py`, `config/__init__.py` |

## What Was Built

### Task 1: Restructured pipeline.yaml

Replaced the flat `teacher:` block with a two-layer architecture:

- **`endpoints:`** — Connection details per API backend. One entry: `litellm` at `http://127.0.0.1:4000` with `apiType: openai`.
- **`models:`** — Three literal model keys (`deepseek-v4-fast`, `deepseek-v4-pro[1m]`, `glm-5.2`), each referencing endpoint `litellm` with a matching `model_id`.
- **`teacher:`** — Cascade settings: `level1` (always-first teacher), `confidence_threshold` (0.7), retry/backoff config, budget cap, circuit breaker params.
- **`teacher_benchmark:`** — Six domain-to-scores mappings (coding, orchestration, medical, qa_technical, encyclopedic, patents), each scoring DSv4 Pro and GLM 5.2 by domain strength.
- **`pipeline:`** — Added `stage_retry_count: 1` and `stage_backoff_seconds: 5.0` to the preserved specialists list.
- Preserved unchanged: `paths:`, `training:`, `evaluation:`, `fp4_export:` sections.

Top-level comments document the two-layer architecture ("endpoints define WHERE, models define WHAT") and the API key naming convention (`{UPPERCASE_MODEL_NAME}_API_KEY`).

### Task 2: ConfigLoader (config/loader.py)

Created `ConfigLoader` class and `ConfigValidationError` exception:

| Feature | Details |
|---------|---------|
| **Schema validation** | Validates `endpoints` (url, apiType), `models` (endpoint reference), `teacher` (level1 exists in models), `teacher_benchmark` (domain scores reference valid models), `pipeline.specialists` (non-empty list) |
| **Error messages** | All validation errors include the YAML key path (e.g., `endpoints.litellm.url: missing required field 'url'`) |
| **Per-specialist overrides** | `get_effective_config(niche)` deep-copies global config and deep-merges specialist YAML values. `specialist.base_model` overrides `training.base_model`. `specialist.training.*` overrides `training.*`. `system_prompt` and `synthetic_prompts` surfaced as top-level keys. |
| **Unknown niche rejection** | `get_effective_config('nonexistent')` raises `ConfigValidationError` listing valid specialist names |
| **Self-test** | `python config/loader.py` runs 12 assertions validating loading, overrides, error cases, and key preservation |

Updated `config/__init__.py` to export both `ConfigLoader` and `ConfigValidationError`.

## Verification Results

### Task 1 Acceptance Criteria

- `yaml.safe_load()` on pipeline.yaml produces dict with `endpoints`, `models`, `teacher`, `teacher_benchmark`, `pipeline`, `paths`, `training`, `evaluation`, `fp4_export` — PASSED
- `endpoints.litellm.apiType` equals `"openai"` — PASSED
- `models` contains exactly 3 entries: `deepseek-v4-fast`, `deepseek-v4-pro[1m]`, `glm-5.2` — PASSED
- `teacher_benchmark` contains exactly 6 domain keys — PASSED
- `training.base_model` preserved unchanged — PASSED
- `grep -c "apiType:" config/pipeline.yaml` returns >= 1 — PASSED (1)
- YAML comment mentions "two-layer" or "endpoints define WHERE, models define WHAT" — PASSED

### Task 2 Acceptance Criteria

- `ConfigLoader(Path('.'))` loads without error — PASSED
- `get_effective_config('code')` returns Qwen3-Coder base model — PASSED
- `get_effective_config('medical')` returns global default base model — PASSED
- `get_effective_config('nonexistent')` raises `ConfigValidationError` — PASSED
- Malformed config raises `ConfigValidationError` with key path — PASSED
- `grep -c "class ConfigLoader" config/loader.py` returns 1 — PASSED
- `grep -c "class ConfigValidationError" config/loader.py` returns 1 — PASSED
- `grep -cE "deep.*copy|deepcopy" config/loader.py` returns >= 1 — PASSED (2)
- `python config/loader.py` runs and prints results — PASSED (12/12)

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None. All validation logic is fully implemented, all config fields have concrete values. The `teacher_benchmark` values are the initial static pre-configuration called for in D-01; dynamic evolution is deferred to Phase 2 per the plan's design.

## Threat Flags

None. All threat mitigations from the plan's threat model are implemented:
- T-01-01 (schema validation): ConfigLoader validates all required fields with key-path error messages.
- T-01-02 (API keys in .env): No API keys in YAML; ConfigLoader does not read or log env vars.
- T-01-03 (per-specialist override scope): Specialist overrides apply only within their merge scope.
- T-01-SC (pip installs): No new pip packages added.

## Requirements Addressed

| Requirement | Description | Status |
|-------------|-------------|--------|
| TEACH-03 | Two-Layer Teacher Configuration | Implemented — `endpoints` + `models` sections, literal model keys, .env API key convention |
| PIPE-03 | Per-Specialist Configuration Override | Implemented — ConfigLoader deep-merges specialist YAML over global defaults |

---

## Self-Check: PASSED

All created/modified files exist, all commits confirmed in git log.
