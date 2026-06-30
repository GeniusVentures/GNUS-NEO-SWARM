---
phase: 02-training-distillation-quality
plan: 03
subsystem: training
tags: [mlx, lora, validation, hyperparameters, adapter-quality, tdd]

# Dependency graph
requires:
  - phase: 01-foundation
    provides: TeacherClient/TeacherCascade interfaces (Phase 1, importable), train_specialists_mlx.py trainer, TrainingConfig dataclass
provides:
  - validate_adapter multi-prong adapter validity check (loadability, validation loss, behavioral diff, objective error tracking)
  - Post-training validation pass integrated into train_specialist() on held-out test set
  - validate_hyperparameters config-load gate (TRAIN-02)
  - Pre-flight verification tests for Phase 1 interface availability and test split existence
affects: [04-benchmark-evaluation, training-quality, adapter-trust, pipeline-runner]

# Tech tracking
tech-stack:
  added: []  # No new libraries — mlx-lm 0.28.4 already present
  patterns:
    - "Fail-open validation: MLX load failures captured into result dict, not raised (T-02-10)"
    - "Held-out test set separation: validation uses data/specialists/{niche}/test.jsonl, never training val_batches (D-06, Pitfall 4)"
    - "Status-flag trust: training_metadata.json status reflects validation outcome (complete / validation_failed / not_loadable)"
    - "Config-load hyperparameter gate: invalid combos raise ValueError before mlx_lora.train_model() (T-02-14)"

key-files:
  created:
    - gnus-poc/training/validation.py
    - gnus-poc/tests/test_training_validation.py
    - gnus-poc/tests/test_training_config.py
  modified:
    - gnus-poc/training/train_specialists_mlx.py
    - gnus-poc/training/config.py

key-decisions:
  - "validate_hyperparameters lives in training/config.py (not train_specialists_mlx.py) — config concerns colocated with TrainingConfig, cleanly testable, wired into build_args_for_niche() with one call"
  - "Validation threshold defaults to 3.0 when specialist YAML lacks a validation block — non-blocking, lets validation run before YAMLs are updated (D-07)"
  - "Pre-flight tests are fail-open by design: missing interfaces/data log warnings, not test failures (operator visibility per RESEARCH.md Open Questions 1 & 2)"
  - "Objective vs subjective error tracking uses label/ground_truth keys when present; samples without ground truth count as subjective diffs (D-08)"

patterns-established:
  - "Pattern: validate_adapter result dict contract (loadable, load_error, validation_loss, loss_valid, jaccard_similarity, behavioral_diff, objective_errors, subjective_diffs, overall_valid)"
  - "Pattern: _read_validation_config / _load_test_samples helpers in trainer for config-driven, non-blocking validation"
  - "Pattern: TDD RED/GREEN gate commits for tdd=true tasks (test commit then feat commit)"

requirements-completed: [TRAIN-01, TRAIN-02]

# Metrics
duration: 9min
completed: 2026-06-30
---

# Phase 02 Plan 03: Post-Training Adapter Validation Summary

**Multi-prong adapter validity check (loadability + held-out validation loss + behavioral Jaccard diff) wired into train_specialist() with config-driven hyperparameter validation gate**

## Performance

- **Duration:** 9 min
- **Started:** 2026-06-30T18:41:27Z
- **Completed:** 2026-06-30T18:50:17Z
- **Tasks:** 3 (Task 0 pre-flight, Task 1 validation module TDD, Task 2 integration + config tests)
- **Files modified:** 5 (3 created, 2 modified)

## Accomplishments
- validate_adapter() in training/validation.py implements the three D-08 checks (loadability, validation loss, behavioral Jaccard diff) plus objective vs. subjective error tracking, fail-open on all MLX ops
- train_specialist() now runs the validation pass after mlx_lora.train_model() on the held-out test split (D-06); training_metadata.json records the full validation result and status reflects outcome
- validate_hyperparameters() in training/config.py gates invalid combos (batch_size<=0, learning_rate<=0, lora_rank<1, iterations<=0) before training starts (TRAIN-02, T-02-14)
- Pre-flight verification confirms Phase 1 interfaces (TeacherClient, TeacherCascade) are importable and documents the test-split creation policy

## Task Commits

Each task was committed atomically:

1. **Task 0: Pre-flight verification — Phase 1 interfaces and test split availability** — `6f261b2` (test)
2. **Task 1 RED: Failing tests for validate_adapter** — `d3f11bb` (test)
3. **Task 1 GREEN: Implement validate_adapter multi-prong checks** — `bb69499` (feat)
4. **Task 2: Integrate validation into train_specialist() + hyperparameter config tests** — `878f615` (feat)

_Note: Task 1 is tdd=true — RED gate (d3f11bb) precedes GREEN gate (bb69499) per the mandatory TDD cycle. No REFACTOR gate needed — helpers already extracted, single exit point._

## Files Created/Modified
- `gnus-poc/training/validation.py` (created, 241 lines) — validate_adapter + 3 helpers (_compute_validation_loss, _compute_jaccard_similarity, _track_objective_errors); fail-open try/except, logging
- `gnus-poc/tests/test_training_validation.py` (created, 324 lines) — TestPreflightVerification (2 tests) + TestValidateAdapter (8 tests); MLX mocked via @patch
- `gnus-poc/tests/test_training_config.py` (created, 69 lines) — TestTrainingConfig with 6 hyperparameter validation tests
- `gnus-poc/training/train_specialists_mlx.py` (modified, 324→445 lines) — surgical insertion of validation pass after train_model(); _read_validation_config/_load_test_samples helpers; validate_hyperparameters wired into build_args_for_niche()
- `gnus-poc/training/config.py` (modified, 97→129 lines) — added validate_hyperparameters() function

## Decisions Made
- **validate_hyperparameters location:** Placed in training/config.py (not train_specialists_mlx.py) to colocate with TrainingConfig and keep it cleanly unit-testable; wired into build_args_for_niche() with a single validate_hyperparameters(TrainingConfig(...)) call so the gate fires before mlx_lora.train_model() without restructuring the trainer.
- **Default validation threshold:** DEFAULT_VALIDATION_LOSS_THRESHOLD=3.0 used when a specialist YAML has no validation block, so validation can run before YAMLs are updated (D-07 configurability preserved; defaults are non-blocking).
- **Pre-flight test tolerance:** The pre-flight tests log warnings instead of failing when data/interfaces are absent — this is intentional per the plan ("Do NOT fail the task") so the suite runs before data_prep produces training data.
- **TDD commit structure:** Task 1 split into RED (test commit d3f11bb) and GREEN (feat commit bb69499) gates to satisfy the mandatory TDD cycle for tdd=true tasks.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] validate_hyperparameters placed in config.py instead of train_specialists_mlx.py**
- **Found during:** Task 2 (hyperparameter config tests)
- **Issue:** The plan's test_training_config.py says "Import hyperparameter validation from training.train_specialists_mlx or config loader" — both are permitted. Placing it in config.py alongside the existing TrainingConfig dataclass is the cleaner, more testable choice and avoids polluting the trainer module with validation logic.
- **Fix:** Added validate_hyperparameters(config: TrainingConfig) to training/config.py; wired it into build_args_for_niche() via a single call so the gate fires before training. The test imports from training.config (the natural home for config validation).
- **Files modified:** gnus-poc/training/config.py, gnus-poc/training/train_specialists_mlx.py
- **Verification:** All 6 test_training_config.py tests pass; validate_hyperparameters is called in build_args_for_niche before the args namespace is returned (blocked before train_model).
- **Committed in:** 878f615 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 missing critical / architectural placement choice explicitly permitted by the plan)
**Impact on plan:** No scope creep — the plan explicitly allowed either location; chose the cleaner one. All acceptance criteria and success criteria met.

## Issues Encountered
None — plan executed cleanly. RESEARCH.md Open Questions 1 & 2 were already marked RESOLVED (2026-06-29) with correct references to Task 0, so no RESEARCH.md edit was required.

## TDD Gate Compliance

Task 1 (tdd=true) followed the mandatory RED/GREEN/REFACTOR cycle:
1. RED gate: `d3f11bb` (test commit — 8 failing tests, ModuleNotFoundError confirmed)
2. GREEN gate: `bb69499` (feat commit — all 8 tests passing)
3. REFACTOR gate: Not needed — helpers already extracted into single-purpose functions, validate_adapter has a single exit point via the result dict, no deep nesting.

Gate sequence verified in git log. No compliance warnings.

## User Setup Required
None — no external service configuration required. Validation uses the existing mlx-lm 0.28.4 dependency already in requirements.txt. No new package installs.

## Next Phase Readiness
- Adapter quality is now verified at training time — downstream pipeline stages can branch on metadata.status and metadata.validation.overall_valid before trusting an adapter (T-02-13 mitigation).
- Held-out test splits must be produced by data_prep (currently absent) for the validation pass to run non-trivially; the trainer skips validation gracefully (Pitfall 4) until then.
- Per-specialist validation_loss_threshold can be added to config/specialists/<niche>.yaml under a validation block (D-07); defaults to 3.0 until added.
- The validate_adapter result dict contract is stable for Phase 4 benchmark evaluation to consume.

---
*Phase: 02-training-distillation-quality*
*Completed: 2026-06-30*

## Self-Check: PASSED

Created files exist:
- gnus-poc/training/validation.py — FOUND
- gnus-poc/tests/test_training_validation.py — FOUND
- gnus-poc/tests/test_training_config.py — FOUND
- .planning/workstreams/poc/phases/02-training-distillation-quality/02-03-SUMMARY.md — FOUND

Commits exist:
- 6f261b2 (Task 0) — FOUND
- d3f11bb (Task 1 RED) — FOUND
- bb69499 (Task 1 GREEN) — FOUND
- 878f615 (Task 2) — FOUND
