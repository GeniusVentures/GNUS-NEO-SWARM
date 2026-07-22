---
phase: 04-benchmark-evaluation
plan: 01
subsystem: eval
tags: [lm-eval-harness, mlx, benchmark-runner, canonical, diagnostic, mmlu]
requires: []
provides: [MLXBenchmarkModel, BenchmarkRunner, canonical benchmark execution]
affects: [eval/]
tech-stack:
  added: [lm-evaluation-harness v0.4.12 Python API (simple_evaluate)]
  patterns: [LM subclass for in-process inference, frozen canonical params, structured results JSON]
key-files:
  created:
    - gnus-poc/eval/benchmark_runner.py (616 lines)
    - gnus-poc/tests/test_benchmark_runner.py (430 lines)
  modified:
    - gnus-poc/eval/benchmark_mlx_model.py (400 lines)
    - gnus-poc/tests/test_benchmark_mlx_model.py (241 lines)
decisions:
  - "D-01: source=api raises NotImplementedError (judge-only, deferred); huggingface + local supported"
  - "D-02: results JSON records reproducibility fingerprint fields"
  - "D-03: canonical mode freezes prompt/few-shot/chat-template/decoding/answer-extraction/dataset-revision; diagnostic allows overrides"
  - "D-04: MMLU runs for every specialist as diagnostic baseline, never blocks"
metrics:
  duration: interrupted-then-resumed
  completed_date: 2026-06-28
  tests_passing: 32
---

# Phase 04 Plan 01: lm-eval Integration + MLX Model Wrapper + Canonical Runner

**One-liner:** Integrated EleutherAI lm-evaluation-harness as an in-process Python library via an `MLXBenchmarkModel` subclass of `lm_eval.api.model.LM`, plus a `BenchmarkRunner` entry point that dispatches per-specialist task lists with frozen canonical parameters and writes structured results JSON.

## Tasks Completed

| # | Task | Status | Commit | Key Files |
|---|------|--------|--------|-----------|
| 1 | MLX model wrapper for lm-eval LM interface | Complete | c58b6e5, 20c3f4b | benchmark_mlx_model.py, test_benchmark_mlx_model.py |
| 2 | Benchmark runner entry point with simple_evaluate() | Complete | ad450c8 | benchmark_runner.py, test_benchmark_runner.py |

## What Was Built

### benchmark_mlx_model.py — MLXBenchmarkModel
- Subclasses `lm_eval.api.model.LM`; implements `loglikelihood`, `loglikelihood_rolling`, `generate_until`
- Wraps MLX-loaded quantized specialist weights for in-process inference (no subprocess)
- Constructor accepts model path + MLX config; lazy-loads weights

### benchmark_runner.py — BenchmarkRunner
- `run_benchmarks(niche, mode, source)` entry point invoking `simple_evaluate()` with per-niche task lists
- **Canonical mode (D-03):** frozen prompt template, few-shot count/seed, chat template, decoding params, answer extraction, dataset revision
- **Diagnostic mode (D-03):** allows config overrides — informational only, never gated
- **Source dispatch (D-01):** `huggingface` (datasets API) and `local` (pre-downloaded) supported; `api` raises `NotImplementedError` (judge-only, deferred)
- MMLU per-subject breakdown preserved in results (D-04)
- Writes structured results JSON to `artifacts/benchmarks/` conforming to the D-02 reproducibility schema
- CLI: `--niche`, `--mode`, `--source`, `--force-download`

## Verification Results

```
python3 -m pytest tests/test_benchmark_mlx_model.py tests/test_benchmark_runner.py -q
# 32 passed in 1.12s
python3 eval/benchmark_runner.py --help   # prints usage
```

## Deviations from Plan

### Resumed Mid-Plan
- **Found during resume:** Task 1 (MLX wrapper) was committed (c58b6e5 test, 20c3f4b impl) by the prior executor session; Task 2 (runner) files existed on disk but were uncommitted when the session was interrupted.
- **Resolution:** Verified runner implementation complete, ran tests.

### Test Fix
- **[Bug]** `test_runner_source_api_raises_not_implemented` regex `api.*not implemented` did not match the actual message `"API judge mode is not implemented..."` due to case sensitivity.
- **Fix:** Made the match case-insensitive (`r"(?i)api.*not implemented"`). The descriptive message was left intact. One line changed in `test_benchmark_runner.py`.

## Threat Flags

None beyond the plan's threat model. The `api` source path fails closed (raises) per D-01 — no silent fallback.

## Self-Check: PASSED

- [x] `gnus-poc/eval/benchmark_mlx_model.py` — FOUND (400 lines, min 80)
- [x] `gnus-poc/eval/benchmark_runner.py` — FOUND (616 lines, min 200)
- [x] `gnus-poc/tests/test_benchmark_mlx_model.py` — FOUND (241 lines)
- [x] `gnus-poc/tests/test_benchmark_runner.py` — FOUND (430 lines)
- [x] Commit c58b6e5 — FOUND (Task 1 test)
- [x] Commit 20c3f4b — FOUND (Task 1 impl)
- [x] Commit ad450c8 — FOUND (Task 2 runner)
- [x] 32 tests passing
