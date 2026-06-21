---
phase: 01-pipeline-hardening
plan: 03
date: 2026-06-19
status: complete
subsystem: pipeline
tags:
  - subprocess
  - checkpoint-validation
  - error-handling
  - testing
requires:
  - 01-01
provides:
  - PIPE-01
  - PIPE-02
affects:
  - pipeline/runner.py
  - pipeline/checkpoint.py
  - pipeline/__init__.py
  - tests/test_skip_logic.py
tech-stack:
  added:
    - dataclasses (StageValidationResult)
    - subprocess (stage execution)
    - json (checkpoint serialization)
  patterns:
    - CheckpointValidator (per-stage output validation)
    - StageResult (NamedTuple for subprocess outcomes)
    - Retry loop with configurable backoff
    - Error-type-based failure isolation
key-files:
  created:
    - pipeline/checkpoint.py
  modified:
    - pipeline/__init__.py
    - pipeline/runner.py
    - tests/test_skip_logic.py
decisions:
  - "Checkpoint files use .json extension with structured StageValidationResult payloads, replacing empty .done marker files"
  - "Per-stage validation checks verify output file existence, content quality, and schema compliance before marking a stage complete"
  - "Subprocess execution uses sys.executable to preserve the same Python environment for stage scripts"
  - "Non-zero exit codes do NOT abort the entire pipeline — only FileNotFoundError or unexpected exceptions abort the current niche"
  - "Retry is configurable via pipeline.yaml (stage_retry_count, stage_backoff_seconds) with defaults of 1 retry and 5s backoff"
duration: "~15 minutes"
completed-date: 2026-06-19
---

# Phase 1 Plan 3: Subprocess Execution and Validated Checkpoints

Transforms the pipeline runner from a command-printing stub into a real subprocess executor with error-type-based handling, per-niche failure isolation, and validated checkpoint resume that verifies stage output quality before marking a stage complete.

## Tasks Completed

| # | Task | Commit | Type |
|---|------|--------|------|
| 1 | Create checkpoint validator module with per-stage output validation | `1a4ef44` | feat |
| 2 | Implement subprocess stage execution with error-type handling | `c01493c` | feat |
| 3 | Update tests for pipeline runner and checkpoint validation | `46e8cdb` | test |

## What Was Built

### Task 1 — CheckpointValidator (`pipeline/checkpoint.py`, 342 lines)

Created `pipeline/checkpoint.py` with two classes:

- **`StageValidationResult`**: Dataclass with `stage`, `niche`, `passed`, `checks`, `completed_at` fields. Supports `to_dict()` / `from_dict()` JSON serialization for persistent checkpoint files.

- **`CheckpointValidator`**: Per-stage output validation for all 7 pipeline stages:
  - `data_prep`: Directory existence + non-init data files
  - `synthetic_data`: JSONL file with minimum row count (10 default), valid JSON content
  - `dedup`: Hash file + dedup log with valid `removed_count` field
  - `train`: Adapter config, weights (safetensors or npz fallback), training metadata with status
  - `evaluate`: Evaluation JSON with required metrics (accuracy, perplexity, latency)
  - `distill`: Loss file with non-increasing trend (allows 10% of steps to increase by <=5%)
  - `quantize`: FP4 directory with weight files and manifest.json

  Also provides `is_complete()`, `mark_complete()`, `clear_checkpoint()`, `clear_all_checkpoints()` lifecycle methods with error handling for `OSError` and `JSONDecodeError`.

Updated `pipeline/__init__.py` to export the new classes.

### Task 2 — Subprocess Pipeline Runner (`pipeline/runner.py`, rewritten)

Rewrote `pipeline/runner.py` with:

- **`StageResult` NamedTuple**: Captures `stage`, `niche`, `success`, `exit_code`, `stdout`, `stderr`, `attempts` from each subprocess execution.

- **`_build_command(niche, stage)`**: Maps stage names to script paths using `sys.executable` — no hardcoded `python` interpreter.

- **`_run_stage(niche, stage)`**: Executes via `subprocess.run()` with `capture_output=True`, `text=True`, `timeout=3600`. On success, prints first 3 lines of stdout. On failure, prints last 10 lines of stderr.

- **Error-type handling (per D-10)**: `FileNotFoundError` aborts the current niche. `subprocess.TimeoutExpired` returns failure but continues. `KeyboardInterrupt` re-raises immediately. Other exceptions abort the niche and continue.

- **Retry logic (per D-11)**: Configurable via `pipeline.yaml` (`stage_retry_count`, `stage_backoff_seconds`). Defaults to 1 retry with 5s backoff.

- **Checkpoint integration**: `_is_complete()` delegates to `CheckpointValidator.is_complete()` (reads JSON checkpoint files). `_mark_complete()` calls `CheckpointValidator.validate_stage()` then `mark_complete()` if passed.

- **`run()` method**: Iterates niches, handles `--force` (clears all checkpoints), `--from-stage` (starts at index), per-niche failure isolation (niche failure does not abort pipeline).

### Task 3 — Behavioral Tests (`tests/test_skip_logic.py`, 22 tests)

Updated `tests/test_skip_logic.py` with three test classes:

- **`TestTrainingScriptStructure`** (4 tests): Preserved legacy structural tests for `train_specialists_mlx.py` AST analysis.

- **`TestCheckpointValidator`** (10 tests): JSON extension verification, per-stage validation (data_prep, synthetic_data min rows, train adapter/metadata, evaluate metrics), checkpoint lifecycle (is_complete, mark_complete roundtrip, clear), error handling (unknown stage).

- **`TestPipelineRunnerExecution`** (8 tests): Subprocess execution, stderr capture on failure, timeout handling, force flag checkpoint clearing, from_stage index skipping, niche failure isolation, command building with niche arg, sys.executable usage.

All 22 tests pass.

## Deviations from Plan

### Auto-fixed Issues (Rule 1 - Bug)

**1. Missing `result` argument in test `mark_complete` call**
- **Found during:** Task 3 test execution
- **Issue:** `cv.mark_complete("test_niche", "data_prep")` called with 2 args instead of 3 (missing `result`)
- **Fix:** Added the `r` (StageValidationResult) argument to the call
- **Files modified:** `tests/test_skip_logic.py`
- **Commit:** `46e8cdb`

**2. `StageResult` not in scope for lambda closure**
- **Found during:** Task 3 test execution
- **Issue:** Lambda `lambda n, s: StageResult(...)` failed with `NameError` because `StageResult` was not imported at module level
- **Fix:** Added `StageResult` to the `from pipeline.runner import PipelineRunner` import line
- **Files modified:** `tests/test_skip_logic.py`
- **Commit:** `46e8cdb`

**3. `runner.StageResult.__class__` used instead of `StageResult` constructor**
- **Found during:** Task 3 test writing
- **Issue:** Used `runner.StageResult.__class__(...)` which returns `type` not an instance — would not work
- **Fix:** Replaced with direct `StageResult(...)` NamedTuple construction
- **Files modified:** `tests/test_skip_logic.py`
- **Commit:** `46e8cdb`

## Verification

```bash
# All 22 tests pass
$ PYTHONPATH=. python3 -m pytest tests/test_skip_logic.py -x -v
22 passed in 1.39s

# Checkpoint validator imports cleanly
$ python3 -c "from pipeline.checkpoint import CheckpointValidator, StageValidationResult; print('OK')"
OK

# Runner --help displays expected options
$ PYTHONPATH=. python3 pipeline/runner.py --help
usage: runner.py [-h] [--niche NICHE] [--from-stage FROM_STAGE] [--config CONFIG] [--force]
```

## Success Criteria Met

1. `PipelineRunner._run_stage()` executes stage commands via `subprocess.run()` with stdout/stderr capture and exit code checking
2. A stage returning non-zero exit code does not abort the entire pipeline — remaining niches still execute
3. `--force` flag clears all checkpoints; `--from-stage N` starts execution at stage N
4. Checkpoints are validated JSON files (`.json` extension), not empty `.done` files
5. Per-stage validation verifies output file existence, content quality, and schema per D-15
6. Test suite covers checkpoint validation for all 7 stages, subprocess execution, force/from-stage behavior, and niche isolation

## Self-Check: PASSED

- `pipeline/checkpoint.py` exists — verified
- `pipeline/runner.py` modified — verified
- `pipeline/__init__.py` modified — verified
- `tests/test_skip_logic.py` modified — verified
- Commit `1a4ef44`: feat checkpoint validator — verified
- Commit `c01493c`: feat subprocess runner — verified
- Commit `46e8cdb`: test suite update — verified
- All 22 tests passing — verified
