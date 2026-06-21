---
phase: 01-pipeline-hardening
plan: "05"
subsystem: pipeline
tags: [teacher-client, cascade, multi-backend, logprobs, knowledge-distillation, synthetic-data]

# Dependency graph
requires:
  - phase: 01-pipeline-hardening
    plan: "04"
    provides: TeacherCascade with benchmark-routed escalation, _DOMAIN_MAP
  - phase: 01-pipeline-hardening
    plan: "02"
    provides: Multi-backend TeacherClient with generate_with_cascade(), generate(model_name, messages)
  - phase: 01-pipeline-hardening
    plan: "03"
    provides: Backends package (OpenAIBackend, AnthropicBackend)

provides:
  - Cascade-aware SyntheticDataGenerator with niche-to-benchmark-domain routing
  - Verified Distiller compatibility with multi-backend teacher logprobs format
  - Both dict and list logprobs format support confirmed via tests

affects:
  - pipeline runner (synthetic data stage consumes SyntheticDataGenerator)
  - future training phases (distillation stage depends on logprobs format)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Cascade-first synthetic data generation: generate_with_cascade() is default, direct generate() is opt-out"
    - "Niche-to-domain routing via _DOMAIN_MAP import from distill.cascade (single source of truth)"
    - "All private instance state prefixed with underscore (self._use_cascade, self._default_domain)"

key-files:
  created: []
  modified:
    - distill/synthetic.py
    - tests/test_synthetic.py
    - tests/test_distillation.py

key-decisions:
  - "Imported _DOMAIN_MAP from distill.cascade instead of defining redundant NICHE_DOMAIN_MAP — single source of truth for niche-to-domain mapping"
  - "Passed model_name=None to TeacherClient.generate() for direct mode — lets TeacherClient resolve the default level1 teacher from config"
  - "Default use_cascade=True — multi-teacher cascade is the primary generation mode; direct mode is opt-out"
  - "Distiller class unchanged — no TeacherClient import needed; logprobs format already compatible"

patterns-established:
  - "Cascade-first generation: SyntheticDataGenerator defaults to generate_with_cascade() with niche-to-domain routing"
  - "Config-driven teacher selection: direct mode delegates model_name resolution to TeacherClient.generate()"

requirements-completed: []

# Metrics
duration: ~2min
completed: 2026-06-20
---

# Phase 1 Plan 05: Teacher Consumer Updates Summary

**SyntheticDataGenerator updated to use multi-backend cascade-capable TeacherClient with niche-to-benchmark-domain routing; Distiller confirmed compatible with new logprobs format**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-06-19T18:46:50-07:00
- **Completed:** 2026-06-20T02:10:49Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- SyntheticDataGenerator now calls `generate_with_cascade(messages, domain=domain)` by default, routing niche names (e.g., "code" → "coding") to benchmark domain keys via `_DOMAIN_MAP` from `distill.cascade`
- Direct generation mode (`use_cascade=False`) supported as opt-out, calling `generate(model_name=None, messages=messages)` — TeacherClient resolves the default level1 model from config
- Quality filtering (`_passes_quality`) unchanged — short content, refusal patterns, and keyword checking all still work
- Distiller confirmed compatible with multi-backend TeacherClient logprobs — no code changes needed
- Both dict-format (`{token_id: logprob}`) and list-format (`[logprob, ...]`) teacher logprobs verified working via new compatibility test

## Task Commits

Each task was committed atomically:

1. **Task 1: Update SyntheticDataGenerator for multi-backend cascade TeacherClient** - `0675f2e` (feat)
2. **Task 2: Verify distillation.py compatibility and update tests** - `e9cbda9` (test)

## Files Created/Modified

- `distill/synthetic.py` - Added `use_cascade`/`domain` params to constructor; `generate_for_niche()` calls `generate_with_cascade()` in cascade mode (default) or `generate(model_name=None, messages=messages)` in direct mode; imports `_DOMAIN_MAP` from `distill.cascade` for niche-to-domain routing
- `tests/test_synthetic.py` - Updated `test_generates_for_niche()` to mock `generate_with_cascade`; added `test_cascade_generation_for_niche()` (verifies domain mapping) and `test_direct_generation_for_niche()` (verifies direct mode with model_name)
- `tests/test_distillation.py` - Added `test_teacher_logprobs_format_compatibility()` verifying both dict and list logprobs formats compute finite loss values

## Decisions Made

- Imported `_DOMAIN_MAP` from `distill.cascade` instead of defining a redundant `NICHE_DOMAIN_MAP` — cascade.py is the single source of truth for domain mapping
- Passed `model_name=None` to `TeacherClient.generate()` for direct mode — the client already resolves the default level1 teacher from config, avoiding config access pattern duplication
- Kept `Distiller` class completely unchanged — it does not import `TeacherClient` and its `_kl_divergence_loss()` already handles both dict and list logprobs formats

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- SyntheticDataGenerator is ready for pipeline runner integration — supports both cascade (multi-teacher) and direct (single-teacher) modes with configurable `use_cascade` flag
- Distiller remains backward-compatible and forward-compatible with new TeacherClient logprobs output
- All 15 tests pass across both test suites (10 synthetic + 5 distillation)

---
*Phase: 01-pipeline-hardening*
*End-of-Plan: 05*
*Completed: 2026-06-20*

---

## Self-Check: PASSED

- SUMMARY.md: found
- Task 1 commit `0675f2e`: found
- Task 2 commit `e9cbda9`: found
