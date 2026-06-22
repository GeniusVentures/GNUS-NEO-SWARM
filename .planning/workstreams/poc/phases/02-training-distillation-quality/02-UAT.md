---
status: testing
phase: 02-training-distillation-quality
source:
  - 02-01-SUMMARY.md
  - 02-02-SUMMARY.md
  - 02-03-SUMMARY.md
  - 02-04-SUMMARY.md
  - 02-05-SUMMARY.md
started: 2026-06-21
updated: 2026-06-21
---

## Current Test

number: 1
name: Config loads with Phase 2 sections
expected: |
  `python config/loader.py` self-test passes all assertions.
  pipeline.yaml has `training.distill_loss_target`, `eval_gates`, and `router` sections.
  Per-specialist distill_loss_target overrides work (medical=2.0, code=2.5, encycl=3.0).
  transitions 0.9.3 is installed and importable.
awaiting: user response

## Tests

### 1. Config loads with Phase 2 sections
expected: `python config/loader.py` self-test passes. pipeline.yaml has training convergence, eval_gates, router sections. Per-specialist distill_loss_target overrides work. transitions importable.
result: pending

### 2. ConvergenceTracker plateau detection
expected: `pytest tests/test_convergence.py -x` passes. ConvergenceTracker correctly detects hard-stop, convergence after patience steps, warning threshold, and improvement reset.
result: pending

### 3. SweepAnalyzer produces structured JSON
expected: `pytest tests/test_sweep_analyzer.py -x` passes. Distiller.sweep_temperature() with ConvergenceConfig tracks convergence per temperature. SweepAnalyzer produces artifacts/sweeps/<niche>_sweep.json.
result: pending

### 4. AdapterValidator multi-prong checks
expected: `pytest tests/test_adapter_validator.py -x` passes. Validator checks loadability (safetensors/npz files, non-zero norms), validation loss, and behavioral diff. Inert adapters detected.
result: pending

### 5. MetricStore persistence and auto-gating
expected: `pytest tests/test_evaluator.py -x` passes. MetricStore persists versioned JSON. load_prior() retrieves previous runs. evaluate_and_persist() writes gate pass/fail data.
result: pending

### 6. ThresholdAdapter LLM prompt
expected: ThresholdAdapter exists with THRESHOLD_EVALUATION_PROMPT constant containing {niche}, {current_ppl_max}, recommended_thresholds, and confidence placeholders. Auto-apply gate (confidence > 0.9 AND change < 20%).
result: pending

### 7. Router rule-based classification
expected: `pytest tests/test_router.py -x` passes. Code queries route to code specialist. Math queries route to math path. No-match routes to encyclopedic. Rules are YAML-driven.
result: pending

### 8. Router GQHSM state machine
expected: GQHSM_JSON_SCHEMA loads with 7 states and 9 transitions. RouterStateMachine handles keyword_hit/keyword_miss/regex_hit/syntax_hit transitions. Graceful degradation when transitions not installed.
result: pending

## Summary

total: 8
passed: 0
issues: 0
pending: 8
skipped: 0

## Gaps

[none yet]
