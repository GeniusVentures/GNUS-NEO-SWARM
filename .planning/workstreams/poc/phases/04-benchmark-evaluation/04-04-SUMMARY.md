---
phase: 04-benchmark-evaluation
plan: 04
subsystem: eval
tags: [benchmark, trend-analysis, bootstrap-ci, repair-reports, statistical-significance]
requires: [04-01, 04-02, 04-03]
provides:
  - MetricStore benchmark persistence (record_benchmark_results, load_benchmark_results, load_all_benchmark_results, load_benchmark_run_by_fingerprint)
  - benchmark_trends module (append_to_trend_file, load_trend_file, compute_trend_deltas, bootstrap_ci, is_degradation_significant)
  - benchmark_repair module (generate_repair_report, save_repair_report, should_block_pipeline)
affects: [eval/metric_store.py, eval/, artifacts/benchmarks/, artifacts/trends/, artifacts/repair_reports/]
tech-stack:
  added: []
  patterns:
    - Bootstrap percentile CI with seeded/deterministic RNG (no global random state)
    - Derived trend views over MetricStore source-of-truth (D-11 regenerable)
    - Advisory repair reports with no config-mutation code paths (D-10, T-04-19)
key-files:
  created:
    - gnus-poc/eval/benchmark_trends.py (296 lines)
    - gnus-poc/eval/benchmark_repair.py (321 lines)
    - gnus-poc/tests/test_benchmark_trends.py (283 lines)
    - gnus-poc/tests/test_benchmark_repair.py (254 lines)
  modified:
    - gnus-poc/eval/metric_store.py (+157 lines, Phase 3 methods unchanged)
decisions:
  - "D-09: bootstrap 95% CI on per-category score differences; regression significant when CI excludes zero AND mean delta negative"
  - "D-10: repair suggestions are advisory only -- never auto-mutate distillation config; 3rd consecutive failure blocks pipeline promotion"
  - "D-11: MetricStore is source of truth; artifacts/trends/ are regenerable derived views"
metrics:
  duration: 16m
  completed_date: 2026-06-28
  tests_passing: 37 new (21 trends + 16 repair); 312 total passing
---

# Phase 04 Plan 04: Benchmark Trend Analysis + Bootstrap CI + Repair Reports

**One-liner:** Extended MetricStore as the D-11 source of truth for benchmark results, added seeded bootstrap 95% confidence intervals (D-09) over derived trend views in `artifacts/trends/`, and built advisory repair suggestion reports (D-10) with severity escalation that blocks pipeline promotion on the 3rd consecutive failure -- with no config-mutation code paths.

## Tasks Completed

| # | Task | Status | Commit | Key Files |
|---|------|--------|--------|-----------|
| 1 | Benchmark MetricStore persistence + trend storage with bootstrap CI significance | Complete | 187183e | metric_store.py, benchmark_trends.py, test_benchmark_trends.py |
| 2 | Repair suggestion reports + consecutive failure escalation per D-10 | Complete | 96a2dca | benchmark_repair.py, test_benchmark_repair.py |

## What Was Built

### metric_store.py -- Extended (D-11 source of truth)
- `record_benchmark_results(niche, benchmark, results)` -- writes per-run JSON to `artifacts/benchmarks/{niche}_{benchmark}_{YYYYMMDD-HHMMSS-microseconds}.json`; validates required keys (niche, timestamp_utc, mode, fingerprint, results); flags invalid fingerprints non-destructively (`fingerprint_valid: False`) and stores `fingerprint_hash` for regression lookup.
- `load_benchmark_results(niche, benchmark=None)` -- most recent result for a niche (+optional benchmark); lexicographic glob sort.
- `load_all_benchmark_results(niche)` -- all results sorted ascending by `timestamp_utc`.
- `load_benchmark_run_by_fingerprint(niche, benchmark, hash)` -- exact-run lookup for regression comparison.
- Phase 3 SGFP4 methods (`record_sgfp4_metrics`, `load_sgfp4_metrics`, `list_all_metrics`) unchanged and separately tested.

### benchmark_trends.py -- Derived trend views (D-11)
- `append_to_trend_file` / `load_trend_file` -- append-only run records to `artifacts/trends/{niche}_trend.json`; fail-open on corrupt files (T-04-20).
- `compute_trend_deltas` -- per-benchmark `{metric: curr - prev}` between the two most recent runs; `insufficient_data` status when fewer than 2 runs; new benchmarks skipped.
- `bootstrap_ci(sample_differences, n_bootstrap=10000, confidence=0.95, seed=None)` -- percentile bootstrap on replicate means; **deterministic given a seed** (uses a fresh `random.Random(seed)`, never touches global state); caps `n_bootstrap` at 100k and input at 10k samples (T-04-18).
- `is_degradation_significant(curr, prev, ...)` -- per-benchmark CI on per-category differences; significant when CI excludes zero AND mean delta negative (D-09).

### benchmark_repair.py -- Advisory repair reports (D-10)
- `generate_repair_report(niche, gate_result, benchmark_results, config, previous_results=None)` -- structured report with `underperforming_categories`, `suggested_config_adjustments`, `severity`, `action_required`, `sgfp4_regression`, and `no_baseline_available` flag.
- `_compute_severity(consecutive_failures)` -- D-10 escalation: 0 -> none, 1 -> warning, 2 -> critical, 3+ -> blocking (highest count across benchmarks wins).
- `_generate_config_suggestions` -- advisory-only suggestions (`distill_loss_target`, `iterations`, `rerun`) keyed to underperformance magnitude (>10% / 5-10% / <5%). **T-04-19 verified: no config-write imports, no mutation code paths** (grep-confirmed).
- `save_repair_report` -- writes JSON to `artifacts/repair_reports/`.
- `should_block_pipeline(gate_result)` -- True when `blocking=True` AND any benchmark has 3+ consecutive failures (D-10 block rule).
- Per-category breakdown: emits separate entries per category when `per_category_hard_floor` is configured (e.g. `clinical_knowledge: -0.15`).

## Verification Results

```
# Plan tests (new)
python3 -m pytest tests/test_benchmark_trends.py tests/test_benchmark_repair.py tests/test_metric_store.py -q
# 48 passed in 0.98s

# Full regression
python3 -m pytest tests/ -q
# 312 passed, 3 failed in 43.57s
#   FAILED test_chat_template.py::test_format_chat_produces_chat_template   [KNOWN pre-existing]
#   FAILED test_skip_logic.py::TestCheckpointValidator::test_validate_train_stage_adapter_exists  [KNOWN pre-existing]
#   FAILED test_synthetic.py::TestSyntheticDataGenerator::test_cascade_generation_for_niche  [KNOWN pre-existing]
```

Baseline was 275 passed / 3 failed. After this plan: 312 passed / 3 failed -- +37 new passing tests, **zero new failures** (same 3 known pre-existing failures, unchanged in count or identity).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Same-second filename collisions in MetricStore**
- **Found during:** Task 1 (test `load_all_benchmark_results_sorted` failed -- only 2 of 3 records returned).
- **Issue:** The plan spec fixed the filename timestamp format at `YYYYMMDD-HHMMSS` (second precision). Test payloads written in the same second produced identical filenames and silently overwrote each other.
- **Fix:** Extended the filename timestamp to microsecond precision (`%Y%m%d-%H%M%S-%f`). This preserves the lexicographic-sort recency contract that `load_benchmark_results` relies on (later writes sort after earlier ones) without any collision-suffix that would break ordering. An earlier `-N` suffix attempt was reverted because `.` (46) sorts after `-` (45), breaking recency order.
- **Files modified:** gnus-poc/eval/metric_store.py
- **Commit:** 187183e

No other deviations. The plan executed exactly as written aside from this implementation detail.

## Threat Flags

None beyond the plan's threat model. All STRIDE threats mitigated as specified:
- T-04-16 (trend tampering): trend entries validated on append; bad fingerprints flagged but stored non-destructively.
- T-04-18 (bootstrap DoS): `n_bootstrap` capped at 100k, input capped at 10k samples.
- T-04-19 (elevation via auto-config): grep-confirmed NO config-write imports in benchmark_repair.py; reports are read-only JSON.
- T-04-20 (corrupt trend file): `load_trend_file` fail-opens with empty runs list and a warning; MetricStore remains authoritative.

## Known Stubs

None. Bootstrap CI currently uses per-category scores as pseudo-samples (flagged with an inline comment in `benchmark_trends.py::is_degradation_significant`); this is a documented precision limitation per Plan 04-04 Task 1, not a stub -- the CI is fully functional and tightens automatically when per-item scores become available from the harness.

## Self-Check: PASSED

- [x] `gnus-poc/eval/metric_store.py` -- FOUND (extended, min_lines 40 met; Phase 3 methods verified unchanged by tests/test_metric_store.py)
- [x] `gnus-poc/eval/benchmark_trends.py` -- FOUND (296 lines, min 120)
- [x] `gnus-poc/eval/benchmark_repair.py` -- FOUND (321 lines, min 120)
- [x] `gnus-poc/tests/test_benchmark_trends.py` -- FOUND (283 lines, 21 tests)
- [x] `gnus-poc/tests/test_benchmark_repair.py` -- FOUND (254 lines, 16 tests)
- [x] Commit 187183e -- FOUND (Task 1)
- [x] Commit 96a2dca -- FOUND (Task 2)
- [x] 37 new tests passing; full regression 312 passed / 3 known failures (no new failures)
