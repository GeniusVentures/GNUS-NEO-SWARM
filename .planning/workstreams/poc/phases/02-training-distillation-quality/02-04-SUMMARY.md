---
phase: 02-training-distillation-quality
plan: 04
subsystem: gnus-poc/eval
tags: [evaluation, persistence, auto-gating, adaptive-gating, train-03]
requires:
  - "01-01 (MetricStore, SpecialistEvaluator, Benchmarker base classes)"
  - "config/specialists/*.yaml existing specialist config structure"
  - "config/pipeline.yaml eval_gates block pattern"
provides:
  - "MetricStore.record_training_eval_metrics / load_training_eval_metrics / load_training_eval_history"
  - "SpecialistEvaluator optional metric_store injection + P95 latency + auto-persist"
  - "Benchmarker.gate_check_training_eval (D-14/D-16/D-17 auto-gating)"
  - "eval/adaptive_gating.py AdaptiveGating (D-15 LLM threshold evolution)"
  - "Specialist YAML distillation/validation/evaluation sections (D-01/D-06/D-07/D-14)"
  - "pipeline.yaml adaptive_gating config block"
affects:
  - "config/specialists/*.yaml (all 5 specialists + future specialists follow the new section pattern)"
  - "eval/evaluator.py evaluate() result dict (+ latency_ms_per_token_p95)"
  - "eval/metric_store.py (new training-eval persistence namespace, separate from SGFP4 + benchmark)"
tech-stack:
  added: []
  patterns:
    - "Additive API extension (record/load_training_eval_metrics follow record_sgfp4_metrics pattern)"
    - "Separate gate-state file per gate family ({niche}_training_gate_state.json)"
    - "Numeric-only LLM prompt assembly (T-02-22 prompt-injection mitigation)"
    - "Safety-bound clamping for LLM-suggested thresholds (T-02-21)"
    - "Fail-open on corrupt JSON (Phase 3/4 pattern preserved)"
key-files:
  created:
    - gnus-poc/eval/adaptive_gating.py
    - gnus-poc/tests/test_eval_persistence.py
  modified:
    - gnus-poc/config/specialists/code.yaml
    - gnus-poc/config/specialists/encyclopedic.yaml
    - gnus-poc/config/specialists/medical.yaml
    - gnus-poc/config/specialists/patents.yaml
    - gnus-poc/config/specialists/qa_technical.yaml
    - gnus-poc/eval/evaluator.py
    - gnus-poc/eval/metric_store.py
    - gnus-poc/eval/benchmarker.py
    - gnus-poc/config/pipeline.yaml
decisions:
  - "D-14: per-metric per-specialist gates loaded from specialist YAML evaluation.gates"
  - "D-15: AdaptiveGating disabled by default; human approval always required before applying LLM suggestions"
  - "D-16: outlier = > metric_drop_pct drop vs prior run; notification only, does not block"
  - "D-17: block only after N consecutive_failures_to_block on the same metric; counter resets on pass"
metrics:
  duration: 11m
  completed: 2026-06-30
  tasks: 4
  files_created: 2
  files_modified: 9
  tests_added: 29
  commits: 7
---

# Phase 02 Plan 04: Training-Eval Persistence, Auto-Gating, Adaptive Gating Summary

Training-eval metrics (perplexity, BLEU, ROUGE-L, latency mean/P95, accuracy) are now persisted per run via MetricStore; Benchmarker enforces per-metric per-specialist gates with consecutive-failure blocking (D-17) and non-blocking outlier notification (D-16); the new AdaptiveGating module offers opt-in LLM-driven threshold evolution with safety bounds and mandatory human approval (D-15).

## What Was Built

### Task 1 — Specialist config sections (D-01/D-06/D-07/D-14)
All 5 specialist YAMLs (code, encyclopedic, medical, patents, qa_technical) now carry three additive sections after the existing `training:` block:
- **distillation**: `alpha`, `distill_loss_target` (per-specialist per D-01), `distill_loss_warning`/`distill_loss_hard_stop` two-tier stopping (D-04), `patience`/`min_delta` (D-03).
- **validation**: `validation_loss_threshold` (per-specialist D-07), `behavioral_diff_threshold`, `test_split_path`, `min_test_samples` (D-06/D-08).
- **evaluation**: per-metric gates (`perplexity` max, `bleu_score` min, `accuracy` min) with `consecutive_failures_to_block` (D-14/D-17) and `outlier_trigger.metric_drop_percent` (D-16).

Per-specialist threshold variations match domain difficulty: medical/code tightened (distill_loss_target 2.5, perplexity max 45/50, accuracy min 0.50/0.40), encyclopedic/patents loosened (3.0, 60/55, 0.35/0.30).

### Task 2 — MetricStore training-eval persistence + SpecialistEvaluator wiring (TRAIN-03)
- `MetricStore.record_training_eval_metrics(niche, metrics)` — validates payload, writes `artifacts/evaluations/{niche}_eval_{YYYYMMDD-HHMMSS-%f}.json` (microsecond precision for lexicographic sort), copies through extra numeric metrics (e.g. accuracy) beyond the core required set.
- `MetricStore.load_training_eval_metrics(niche)` — newest-first glob, fail-open on corrupt JSON.
- `MetricStore.load_training_eval_history(niche)` — chronological list for D-15 trend computation.
- `SpecialistEvaluator.__init__` gains optional `metric_store` (default-constructed to keep persistence on by default); `evaluate()` computes P95 latency (`np.percentile`) and auto-persists via `_persist_results` (best-effort, fail-open).

### Task 3 — Benchmarker.gate_check_training_eval (D-14/D-16/D-17)
New additive method (existing `gate_check` SGFP4 and `gate_check_benchmarks` Phase-4 paths untouched). Uses a separate gate-state file `{niche}_training_gate_state.json` so SGFP4/benchmark counters are never disturbed.
- **D-14**: loads `evaluation.gates` from specialist YAML; per-metric pass/fail against `max` (perplexity) or `min` (bleu/accuracy).
- **D-16**: computes delta vs prior run; > `metric_drop_percent` drop sets `outlier_triggered=True` (notification only — handles min-gated and max-gated drop directions correctly).
- **D-17**: single failure logs + continues; only N consecutive failures on the same metric block (`consecutive_failures_to_block`); counter resets on pass; state persisted across process restart. Fail-open on corrupt state (T-02-15).

### Task 4 — AdaptiveGating module (D-15, BLOCKER 1)
New `eval/adaptive_gating.py` (480 lines). Opt-in feature gated behind `adaptive_gating.enabled` (default `false` in pipeline.yaml).
- `suggest_threshold_updates(niche)` — loads multi-run history, extracts per-metric trend direction (improving/degrading/stable), builds a **numeric-only** LLM prompt (T-02-22 prompt-injection mitigation), parses JSON response, clamps to safety bounds.
- **Safety bounds (T-02-21)**: never tighten below `safety_bound_pct` of original (default 50%), never loosen above `safety_bound_loosen_pct` (default 200%), capped to `max_adjustment_percent` per update (default 20%).
- `apply_approved_changes(niche, suggestions)` — writes human-approved thresholds to specialist YAML with old/new values + approval timestamp (audit trail). `requires_approval=True` always (D-15).
- `pipeline.yaml` extended with the `adaptive_gating` config block.

## Verification

```
pytest tests/test_eval_persistence.py -x -v    # 29 passed
pytest tests/ -q --ignore=tests/test_benchmark_mlx_model.py   # 336 passed (no regressions)
```

All 29 new tests pass (10 persistence, 12 auto-gating, 7 adaptive gating). Full suite (336 tests) green — no regressions in metric_store, evaluator, or benchmarker tests.

## Commits

| Task | Phase | Commit | Message |
|------|-------|--------|---------|
| 1 | — | c2297d2 | feat(02-04): add distillation/validation/evaluation sections to specialist configs |
| 2 | RED | 25de797 | test(02-04): add failing tests for training-eval metric persistence |
| 2 | GREEN | d19ef97 | feat(02-04): persist training-eval metrics via MetricStore (TRAIN-03) |
| 3 | RED | 7bf6e96 | test(02-04): add failing tests for training-eval auto-gating |
| 3 | GREEN | 282d5ce | feat(02-04): training-eval auto-gating with consecutive-failure tracking |
| 4 | RED | bd03c51 | test(02-04): add failing tests for AdaptiveGating (D-15) |
| 4 | GREEN | c8dc7cd | feat(02-04): AdaptiveGating — LLM-based threshold evolution (D-15) |

## TDD Gate Compliance

Tasks 2, 3, and 4 followed strict RED/GREEN. Git log confirms the mandatory gate sequence:
1. `test(...)` RED commits exist (25de797, 7bf6e96, bd03c51) — each preceded by a failing pytest run.
2. `feat(...)` GREEN commits follow each RED (d19ef97, 282d5ce, c8dc7cd) — each verified by a passing pytest run.
3. No REFACTOR commits — the GREEN code was already clean; no separate refactor step was needed.

Task 1 was config-only (no `tdd="true"` flag) and committed directly after `yaml.safe_load()` verification.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] record_training_eval_metrics dropped non-core metric keys (accuracy)**
- **Found during:** Task 3 GREEN — `test_gate_check_fails_when_accuracy_below_min` failed because the `accuracy` value was not persisted in the record.
- **Issue:** `record_training_eval_metrics` built the record from a fixed key set (the required keys), silently dropping `accuracy` (which gate configs reference). The gate could never see the value, so it always passed.
- **Fix:** After writing the core keys, copy any additional numeric metric keys from the input dict into the record. Required-key contract unchanged; additive passthrough.
- **Files modified:** gnus-poc/eval/metric_store.py
- **Commit:** 282d5ce

**2. [Rule 1 - Bug] AdaptiveGating project_root defaulted to real repo, ignoring MetricStore root**
- **Found during:** Task 4 GREEN — `test_apply_approved_changes_writes_yaml` failed because `apply_approved_changes` wrote to the real `config/specialists/code.yaml` instead of the test's `tmp_path` copy (mutating `perplexity.max` from 50.0 to 45.0 on the tracked file).
- **Issue:** `AdaptiveGating.__init__` fell back to the module-level `PROJECT_ROOT` when `project_root=None`, ignoring the `MetricStore`'s `_project_root`. Tests injecting a `MetricStore(project_root=tmp_path)` expected the same root to flow through.
- **Fix:** Derive `project_root` from `metric_store._project_root` when not explicitly provided. Also restored the mutated `code.yaml` back to `max: 50.0`.
- **Files modified:** gnus-poc/eval/adaptive_gating.py, gnus-poc/config/specialists/code.yaml
- **Commit:** c8dc7cd

Otherwise the plan was executed exactly as written.

## Threat Mitigations Applied

All threat-register items from the plan's `<threat_model>` were honored:
- **T-02-15 (Tampering, gate state)**: training-gate state file records consecutive-failure counters + timestamps + truncated history (max 20). Fail-open on corrupt files. Separate from SGFP4/benchmark gate state files.
- **T-02-16 (Repudiation)**: every gate check result recorded with timestamp; consecutive counters provide audit trail; `blocked=True` only after N consecutive failures.
- **T-02-17 (DoS, JSON persistence)**: fail-open on corrupt metric files (returns None, logs warning); fixed metric schema (< 1 KB per record); one file per run.
- **T-02-18 (EoP, gate bypass)**: consecutive_failures_to_block enforces eventual blocking; gate state persistence prevents counter reset on restart.
- **T-02-20 (Tampering, config thresholds)**: loaded via `yaml.safe_load()`; numeric validation at `record_training_eval_metrics` (rejects non-numeric).
- **T-02-21 (Tampering, LLM thresholds)**: disabled by default; `require_human_approval=True`; safety bounds clamp suggestions; all suggestions logged with rationale.
- **T-02-22 (Spoofing, prompt injection)**: LLM prompt assembled from numeric metrics only (no free-form text); prompt template fixed with numeric variable substitution.

## Known Stubs

None. All persisted values are real metrics computed by the evaluator or seeded by tests; no hardcoded empty values, placeholder text, or TODO markers in production code paths.

## Self-Check: PASSED

- All 11 created/modified files exist on disk (verified via `[ -f ... ]`).
- All 7 commit hashes (c2297d2, 25de797, d19ef97, 7bf6e96, 282d5ce, bd03c51, c8dc7cd) present in `git log --oneline --all`.
- Full test suite (336 tests) green; plan test suite (29 tests) green.
