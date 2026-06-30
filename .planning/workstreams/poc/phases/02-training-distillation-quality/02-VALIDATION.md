---
phase: 02
slug: training-distillation-quality
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-29
---

# Phase 02 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | none — Wave 0 installs |
| **Quick run command** | `pytest tests/test_convergence.py tests/test_router_rules.py -x` |
| **Full suite command** | `pytest tests/ -x` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_convergence.py tests/test_router_rules.py -x`
- **After every plan wave:** Run `pytest tests/ -x`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| *Filled by executor* | — | — | — | — | — | — | — | — | ⬜ pending |

---

## Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DIST-01 | KD loss converges below target within patience | unit | `pytest tests/test_convergence.py::test_converges_below_target -x` | ❌ W0 |
| DIST-01 | Two-tier stopping: warning logged, hard-stop aborts | unit | `pytest tests/test_convergence.py::test_two_tier_stopping -x` | ❌ W0 |
| DIST-02 | Temperature sweep produces structured JSON | integration | `pytest tests/test_distillation.py::test_temperature_sweep_output -x` | ❌ W0 |
| DIST-03 | Synthetic data quality checks (length, empty, dedup) | unit | `pytest tests/test_synthetic_quality.py::test_quality_checks -x` | ❌ W0 |
| TRAIN-01 | Adapter loads cleanly via MLX | integration | `pytest tests/test_training_validation.py::test_adapter_loadability -x` | ❌ W0 |
| TRAIN-01 | Adapter produces different output from base model | integration | `pytest tests/test_training_validation.py::test_behavioral_difference -x` | ❌ W0 |
| TRAIN-02 | Hyperparameters from config respected at runtime | unit | `pytest tests/test_training_config.py::test_hyperparameter_override -x` | ❌ W0 |
| TRAIN-03 | Evaluation metrics persisted per run | unit | `pytest tests/test_eval_persistence.py::test_metrics_persisted -x` | ❌ W0 |
| ROUTE-01 | Keyword rule matches code query | unit | `pytest tests/test_router_rules.py::test_keyword_code_detection -x` | ❌ W0 |
| ROUTE-01 | Syntax density rule routes math query | unit | `pytest tests/test_router_rules.py::test_syntax_density_math -x` | ❌ W0 |
| ROUTE-01 | No-match routes to encyclopedic | unit | `pytest tests/test_router_rules.py::test_default_fallback -x` | ❌ W0 |
| ROUTE-02 | Execution plan includes specialist and mode | unit | `pytest tests/test_router_engine.py::test_execution_plan_output -x` | ❌ W0 |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_convergence.py` — covers DIST-01 convergence criteria
- [ ] `tests/test_distillation.py` — covers DIST-02 temperature sweep output
- [ ] `tests/test_synthetic_quality.py` — covers DIST-03 data quality checks
- [ ] `tests/test_training_validation.py` — covers TRAIN-01 adapter validity
- [ ] `tests/test_training_config.py` — covers TRAIN-02 hyperparameter respect
- [ ] `tests/test_eval_persistence.py` — covers TRAIN-03 metric persistence
- [ ] `tests/test_router_rules.py` — covers ROUTE-01 rule matching
- [ ] `tests/test_router_engine.py` — covers ROUTE-02 execution plan output
- [ ] Framework install: `pip install pytest` — if not already installed

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Behavioral difference quality (subjective) | D-08 | Subjective judgment (style, tone, phrasing) | Human review of adapter output vs base model on domain queries |
| Adaptive gating LLM prompt quality | D-15 | LLM output evaluation | Review threshold update suggestions for reasonableness |
| Severe outlier human review | D-16 | Requires domain expertise | Review metric variance reports in artifacts/trends/ |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
