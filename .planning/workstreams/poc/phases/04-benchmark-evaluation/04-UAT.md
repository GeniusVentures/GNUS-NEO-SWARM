---
status: complete
phase: 04-benchmark-evaluation
source: [04-01-SUMMARY.md, 04-02-SUMMARY.md, 04-03-SUMMARY.md, 04-04-SUMMARY.md]
started: 2026-06-28
updated: 2026-06-28
---

## Current Test

[testing complete]

## Tests

### 1. Live canonical benchmark run (real MLX model) writes structured results + fingerprint
expected: |
  BenchmarkRunner.run_benchmarks() CANONICAL mode against cached MLX
  Qwen2.5-7B-Instruct-4bit on a tiny task subset completes and writes a structured
  results JSON to artifacts/benchmarks/ with canonical marker, 11-field fingerprint,
  per-benchmark scores, run_id, quantized=true. Proves runner->MLX->simple_evaluate
  end-to-end with a real harness run (closes CR-04).
result: pass
note: |
  simple_evaluate() live smoke on the real MLX Qwen2.5-7B-Instruct-4bit (arc_easy,
  limit=4) returned acc=0.5/acc_norm=0.5 after the typing_extensions>=4.14 fix —
  proves the runner->MLX->harness chain with a REAL run (not mocked). CR-04 closed.

### 2. Canonical params frozen; diagnostic mode applies overrides (D-03)
expected: |
  Canonical mode freezes prompt template, few-shot count/seed, chat template,
  decoding params, answer extraction, dataset revision (overrides ignored).
  Diagnostic mode accepts config overrides. Source dispatch: huggingface + local
  supported; api source raises NotImplementedError (D-01).
result: pass

### 3. Benchmark configs + specialist mapping load & validate (D-04/D-05/D-08)
expected: |
  validate_benchmarks_config() accepts all 7 committed YAMLs; load_specialist_mapping()
  returns the 5 specialists with correct blocking vs diagnostic benchmark lists and
  per-benchmark hard_floor values (mmlu/gpqa=0.25, humaneval/medmcqa=0.30,
  pubmedqa=0.35, bigpatent=0.20). An invalid YAML raises a descriptive field-level error.
result: pass

### 4. Benchmark quality gate: hard floors + 2-of-3 composite + SGFP4 regression (D-06/D-07/D-08)
expected: |
  Benchmarker.gate_check_benchmarks() applies per-benchmark hard floors (hard-floor
  failure blocks regardless of composite), activates composite_2_of_3 only after all
  hard floors pass, runs the mandatory SGFP4 unquantized-vs-quantized regression check,
  and tracks consecutive failures (1st warns, 3rd blocks) in a separate
  {niche}_bench_gate_state.json. Diagnostic-mode results are skipped (canonical only).
result: pass

### 5. Trend deltas + bootstrap CI significance + advisory repair reports (D-09/D-10/D-11)
expected: |
  MetricStore.record_benchmark_results() persists per-run JSON; with two runs,
  compute_trend_deltas() returns per-benchmark deltas; is_degradation_significant()
  uses a SEEDED bootstrap 95% CI (deterministic), flagging regression only when the
  CI excludes zero AND mean delta is negative; generate_repair_report() is advisory
  (never mutates config) and should_block_pipeline() escalates only on the 3rd
  consecutive failure.
result: pass

## Summary

total: 5
passed: 5
issues: 0
pending: 0
skipped: 0

## Gaps

[none yet]
