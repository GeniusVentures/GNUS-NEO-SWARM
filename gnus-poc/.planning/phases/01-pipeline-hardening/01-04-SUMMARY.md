---
phase: 01-pipeline-hardening
plan: 04
subsystem: distill
tags: [teacher-cascade, budget-persistence, circuit-breaker, half-open, benchmark-routing]
requires: [01-02 (multi-backend TeacherClient)]
provides: [multi-teacher cascade orchestration, persistent budget enforcement, half-open circuit breaker]
affects: [distill/teacher.py, distill/cascade.py]
tech-stack:
  added: []
  patterns: [cascade-orchestrator, benchmark-routed-escalation, half-open-circuit-breaker, disk-persisted-budget]
key-files:
  created: [distill/cascade.py]
  modified: [distill/teacher.py, distill/teacher_errors.py]
decisions:
  - "compute_logprob_confidence tries response directly then _raw_response fallback for test mock compatibility"
  - "generate_with_cascade() returns _ResponseWrapper with truncated usage data (prompt_tokens=0) since cascade aggregates multiple teacher calls"
  - "Budget state file is a soft limit, not a security boundary — documented per T-04-01"
  - "Circuit breaker half-open logic: recovery timeout -> allow one probe -> success closes / failure re-opens with fresh timer"
  - "Level 1 teacher always runs first; Level 2 only when logprobs mean confidence < threshold"
metrics:
  duration: ""
  completed_date: "2026-06-19"
  task_count: 2
  file_count: 3
---

# Phase 1 Plan 4: Multi-Teacher Cascade, Budget Persistence, Half-Open Circuit Breaker Summary

**One-liner:** Benchmark-routed three-tier teacher cascade with disk-persisted budget enforcement and half-open circuit breaker recovery.

## Execution Summary

| # | Task | Type | Commit | Files |
|---|------|------|--------|-------|
| 1 | Multi-teacher cascade with benchmark-routed Level 2 | auto | `9d8c269` | `distill/cascade.py` (new), `distill/teacher.py` |
| 2 | Budget persistence and half-open circuit breaker | auto | `55e45f8` | `distill/teacher.py` |

### What Was Built

**Task 1 — `distill/cascade.py`:** Created the multi-teacher cascade orchestrator implementing the D-01/D-02/D-03 escalation flow:

- `CascadeResult` — result record with confidence scores, model info, escalation tracking, and all attempt details
- `TeacherCascade` — orchestrator wired with the TeacherClient reference, benchmark table, Level 1 model, and confidence threshold
- `compute_logprob_confidence()` — extracts token logprobs from OpenAI-compatible responses and computes `exp(mean(logprob))` as a 0.0–1.0 confidence score
- `_DOMAIN_MAP` — maps specialist niche names (`"code"`) to benchmark table keys (`"coding"`)
- Integrated into `TeacherClient` via `self._cascade` instantiation in `__init__` and `generate_with_cascade()` public method

Cascade flow:
1. Level 1 (Fast) always runs first
2. If confidence >= threshold → return immediately (no Level 2)
3. If confidence < threshold → route to best Level 2 teacher from benchmark table
4. If first Level 2 still below threshold → try next-best Level 2
5. If all Level 2 below threshold → return best (highest confidence) result
6. If all teachers raise exceptions → raise `TeacherConfigError`

**Task 2 — Budget Persistence:** Added disk-persisted budget state:

- `_budget_state_path` → `artifacts/.budget_state.json`
- `_load_budget_state()` → loads cumulative spend on startup; fresh start = $0.00
- `_save_budget_state()` → writes current state after each successful API call
- `reset_budget()` → zeros cumulative spend and persists (for `--reset-budget` CLI flag)
- Budget enforcement (`_check_budget`) now spans runs — cumulative spend persists across process restarts

**Task 2 — Half-Open Circuit Breaker:** Replaced binary open/closed circuit with three-state machine:

| State | Behavior |
|-------|----------|
| Closed | Calls proceed normally |
| Open | Calls blocked; after `recovery_timeout` seconds → half-open |
| Half-open | One probe call allowed; success → closed, failure → re-opened with fresh timer |

Circuit breaker configuration:
- `circuit_breaker_failure_threshold`: consecutive failures before opening (default 5)
- `circuit_breaker_recovery_timeout`: seconds before half-open probe (default 60)
- Retry: exponential backoff (`base * 2^attempt`), 429/5xx retried, 4xx (except 429) not retried

## Deviations from Plan

None — plan executed exactly as written.

## Verification Results

- [x] `distill/cascade.py` imports without error
- [x] `distill/teacher.py` imports without error
- [x] `compute_logprob_confidence` returns ~0.85 for tokens with logprobs log(0.9) and log(0.8)
- [x] Cascade with high confidence does NOT escalate to Level 2
- [x] `_DOMAIN_MAP` correctly maps `"code"` → `"coding"`, `"medical"` → `"medical"`
- [x] Budget state loads from disk across `TeacherClient` instances
- [x] `_save_budget_state()` writes cumulative spend after cost update
- [x] `reset_budget()` zeros spend and persists
- [x] Circuit breaker half-open state machine verified (open → timeout → half-open → probe success/failure)

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: tampering | `distill/teacher.py:_load_budget_state` | Budget state file is world-readable JSON; soft cost limit, not security boundary. Documented per T-04-01. |
| threat_flag: dos | `distill/teacher.py:_check_circuit` | Half-open recovery prevents permanent circuit lockout; timeout is configurable per T-04-02. |

## Self-Check: PASSED

- `distill/cascade.py` exists ✓
- `distill/teacher.py` modified with cascade + budget + circuit breaker ✓
- Commit `9d8c269` exists ✓
- Commit `55e45f8` exists ✓
- All acceptance criteria met (grep counts verified) ✓
