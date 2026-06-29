# Deferred Items (out-of-scope discoveries)

Pre-existing test failures discovered during Plan 04-03 execution. These are
NOT caused by this plan's changes (verified via git stash) and are out of scope
per the executor SCOPE BOUNDARY rule.

## Pre-existing test failures (2026-06-28)

- `tests/test_chat_template.py::test_format_chat_produces_chat_template` — FAILS
- `tests/test_skip_logic.py::TestCheckpointValidator::test_validate_train_stage_adapter_exists` — FAILS
- `tests/test_synthetic.py::TestSyntheticDataGenerator::test_cascade_generation_for_niche` — FAILS
  (assertion: expected `coding`, got `code` — likely a specialist-name drift)

**Verification:** Confirmed pre-existing via `git stash` + re-run on the prior
commit (1ba0624). All 3 fail identically without Plan 04-03 changes applied.

**Recommendation:** Triage in a separate maintenance phase.
