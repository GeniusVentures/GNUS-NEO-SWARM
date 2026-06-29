---
phase: 04-benchmark-evaluation
plan: 03
subsystem: eval
tags: [reproducibility, fingerprint, benchmark-gates, composite-2of3, sgfp4-regression, tiered-gating]
requires: [04-01, 04-02]
provides:
  - benchmark_fingerprint module (11-field D-02 fingerprint)
  - Benchmarker.gate_check_benchmarks (hard floors, composite, SGFP4 regression)
  - composite_2_of_3 gate logic
  - pipeline.yaml benchmark_composite + sfgp4_regression dimensions
affects: [eval/benchmarker.py, config/pipeline.yaml]
tech-stack:
  added: []  # stdlib only (hashlib, json, importlib.metadata, pyyaml already present)
  patterns:
    - 11-field reproducibility fingerprint with SHA256 manifest integrity (T-04-11)
    - Additive gate dimensions preserving Phase 3 behavior
    - Separate gate-state files per gate family (SGFP4 vs benchmark)
    - 2-of-3 composite with hard-floor precondition
key-files:
  created:
    - gnus-poc/eval/benchmark_fingerprint.py (202 lines)
    - gnus-poc/tests/test_benchmark_fingerprint.py (241 lines)
  modified:
    - gnus-poc/eval/benchmarker.py (332 -> 831 lines, +499)
    - gnus-poc/config/pipeline.yaml (+18 lines, benchmark gate dims)
    - gnus-poc/tests/test_benchmarker.py (255 -> 539 lines, +284)
decisions:
  - "D-02: 11-field fingerprint implemented; task_revision/dataset_revision explicitly nullable (pinning optional per spec)"
  - "D-03: gate_check_benchmarks() skips diagnostic-mode results; only canonical mode is evaluated"
  - "D-04: MMLU non-blocking enforced via specialist_mapping.yaml (diagnostic_benchmarks list)"
  - "D-06: consecutive failure tracking with separate {niche}_bench_gate_state.json; 1st warns, 3rd blocks"
  - "D-07: _load_baseline_scores() raises MissingBaselineError when untrained-backbone baseline absent"
  - "D-08: hard floor precondition overrides composite; composite_2_of_3 activates only after all hard floors pass"
  - "D-08: mandatory SGFP4 regression check (_sgfp4_regression_check) compares unquantized vs quantized"
  - "D-09: bootstrap CI deferred to Plan 04-04; needs_bootstrap flag set on regression results"
  - "T-04-11: validate_fingerprint + fingerprint_hash enable tamper detection"
  - "T-04-12: benchmark gate state persisted with history (audit trail)"
  - "T-04-15: 10 MB manifest read ceiling in _sha256_file"
metrics:
  duration: ~30 min
  completed_date: 2026-06-28
  tests_passing: 39 (10 fingerprint + 29 benchmarker)
---

# Phase 04 Plan 03: Reproducibility Fingerprint + Benchmark Quality Gates

**One-liner:** Implemented the 11-field D-02 reproducibility fingerprint module (compute/validate/hash/match) and extended `Benchmarker` additively with `gate_check_benchmarks()` enforcing per-benchmark hard floors, a 2-of-3 composite gate, mandatory SGFP4 unquantized-vs-quantized regression check, D-06 tiered consecutive-failure tracking, and D-07 internal-baseline deviation -- all while leaving the Phase 3 SGFP4 `gate_check()` behavior and its gate-state file untouched.

## Tasks Completed

| # | Task | Status | Commit | Key Files |
|---|------|--------|--------|-----------|
| 1 | Reproducibility fingerprint module per D-02 (TDD) | Complete | e628566 (RED), 24b7796 (GREEN) | benchmark_fingerprint.py, test_benchmark_fingerprint.py |
| 2 | Extend Benchmarker.gate_check() with benchmark gates (TDD) | Complete | 1ba0624 (RED), 0e0bb79 (GREEN) | benchmarker.py, pipeline.yaml, test_benchmarker.py |

## What Was Built

### benchmark_fingerprint.py -- D-02 11-field fingerprint
- `compute_fingerprint()` computes all 11 fields: `harness_commit` (lm-eval version via `importlib.metadata`), `task_name`, `task_revision`, `dataset_revision`, `prompt_hash` (SHA256 of whitespace-normalized template), `fewshot_seed`, `chat_template_hash` (or `"none"`), `answer_extraction`, `generation_params`, `model_manifest_sha256` (SHA256 over file bytes), `sgfp4_manifest_sha256`
- `validate_fingerprint(fp)` -> `(is_valid, missing_fields)`; presence-check with explicit-nullable revision fields per D-02
- `fingerprint_hash(fp)` -> deterministic SHA256 of `json.dumps(fp, sort_keys=True)`
- `fingerprints_match(fp_a, fp_b)` -> bool via hash equality (T-04-11 tamper detection)
- T-04-15: `_sha256_file` enforces a 10 MB read ceiling on manifest files

### benchmarker.py -- additive benchmark gate dimensions
- **`gate_check_benchmarks(niche_name, benchmark_results_path=None, config=None)`** -- the new benchmark quality gate. Loads specialist mapping + per-benchmark thresholds, finds most-recent canonical result (D-03 skip diagnostic), evaluates hard floors, computes 2-of-3 composite, runs SGFP4 regression, tracks consecutive failures, persists state.
- **`composite_2_of_3(scores_pass, regression_pass, deviation_pass)`** -- D-08: passes when >=2 of 3 dimensions pass.
- **`_sgfp4_regression_check(niche_name, current_scores)`** -- D-08 mandatory: compares unquantized adapter scores vs SGFP4 quantized. Does NOT block on first run (no baseline). Flags `needs_bootstrap: true` for Plan 04-04 (D-09).
- **`_load_baseline_scores(niche_name)`** -- D-07: loads untrained-backbone baseline; raises `MissingBaselineError` if absent.
- **Hard floor precondition (D-08):** if any blocking benchmark fails its hard floor, overall `passed=False` regardless of composite.
- **Separate gate state:** `{niche}_bench_gate_state.json` -- never touches Phase 3 `{niche}_gate_state.json`.
- **`gate_check()` UNCHANGED:** existing SGFP4 dim logic (fp4_mse, fp4_effective_bitrate, fp4_t158_ratio) and its gate-state file are byte-for-byte equivalent to Phase 3.

### pipeline.yaml -- extended eval_gates
- Added `benchmark_composite` (consecutive_failures_to_block: 3) and `sfgp4_regression` (max_regression_pct: 0.10, consecutive_failures_to_block: 3) alongside unchanged SGFP4 dims.

## Verification Results

```
# New tests (Task 1 + Task 2)
python3 -m pytest tests/test_benchmark_fingerprint.py tests/test_benchmarker.py -q
# 39 passed in 5.23s

# Full regression
python3 -m pytest tests/ -q
# 3 failed, 275 passed in 56.25s
```

The 3 failures are **pre-existing** (verified via `git stash` on the parent commit) and unrelated to this plan -- see Deviations below.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] validate_fingerprint nullable-field semantics**
- **Found during:** Task 1 GREEN
- **Issue:** The plan spec says "is_valid = True only when all 11 required fields present and non-None," but D-02 explicitly allows `task_revision=None` and `dataset_revision=None` when revisions are not pinned. The two specs conflict.
- **Fix:** `validate_fingerprint` requires all 11 keys to be present, but treats `task_revision` and `dataset_revision` as explicitly nullable (None is valid). All other fields must be present AND non-None. Added `_NULLABLE_FIELDS` frozenset. Updated my own test count (9 missing, not 10) and removed the over-strict non-None assertion on nullable fields.
- **Files modified:** benchmark_fingerprint.py, test_benchmark_fingerprint.py
- **Commit:** 24b7796

**2. [Rule 1 - Bug] Test helper class inheritance caused test inflation**
- **Found during:** Task 2 GREEN
- **Issue:** Initially made `TestGateCheckBenchmarks` inherit from `TestBenchmarker` to reuse `_make_sgfp4_metrics`. This caused pytest to collect all 18 Phase 3 tests under the subclass name too (47 total instead of 29), inflating the count.
- **Fix:** Replaced inheritance with a standalone module-level `_make_sgfp4_metrics()` helper. Final count: 29 (18 Phase 3 + 11 new) as expected.
- **Files modified:** test_benchmarker.py
- **Commit:** 0e0bb79

### Pre-existing Failures (out of scope -- logged to deferred-items.md)

Three pre-existing test failures were discovered during full regression. Verified pre-existing via `git stash` (they fail identically on the prior commit 1ba0624 without Plan 04-03 changes). Per the executor SCOPE BOUNDARY rule, these are NOT fixed and are logged to `deferred-items.md`:

- `tests/test_chat_template.py::test_format_chat_produces_chat_template`
- `tests/test_skip_logic.py::TestCheckpointValidator::test_validate_train_stage_adapter_exists`
- `tests/test_synthetic.py::TestSyntheticDataGenerator::test_cascade_generation_for_niche` (specialist-name drift: expected `coding`, got `code`)

## Threat Flags

None beyond the plan's threat model. All six threat-register entries (T-04-11 through T-04-15, T-04-SC) are mitigated as specified:

| Threat | Mitigation |
|--------|-----------|
| T-04-11 (tampering) | `fingerprint_hash` + `fingerprints_match` enable tamper detection; mismatch = untrusted result |
| T-04-12 (repudiation) | Benchmark gate state persisted with timestamp + 20-entry history in separate file |
| T-04-13 (config tampering) | Per-benchmark thresholds loaded via YAML with float coercion; ConfigLoader validation in Plan 04-02 |
| T-04-15 (DoS) | 10 MB read ceiling in `_sha256_file` |
| T-04-SC (package installs) | No new packages -- stdlib only |

## Self-Check: PASSED

- [x] `gnus-poc/eval/benchmark_fingerprint.py` -- FOUND (202 lines, min 100)
- [x] `gnus-poc/eval/benchmarker.py` -- FOUND (831 lines, min 250)
- [x] `gnus-poc/config/pipeline.yaml` -- FOUND (extended eval_gates)
- [x] `gnus-poc/tests/test_benchmark_fingerprint.py` -- FOUND (241 lines)
- [x] `gnus-poc/tests/test_benchmarker.py` -- FOUND (539 lines, 29 tests)
- [x] Commit e628566 -- FOUND (Task 1 RED)
- [x] Commit 24b7796 -- FOUND (Task 1 GREEN)
- [x] Commit 1ba0624 -- FOUND (Task 2 RED)
- [x] Commit 0e0bb79 -- FOUND (Task 2 GREEN)
- [x] 39 new tests passing; Phase 3 SGFP4 gate_check behavior unchanged
