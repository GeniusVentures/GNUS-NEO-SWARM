# Phase 1: Pipeline Hardening — Discussion Log

**Date:** 2026-06-19
**Mode:** interactive (default)
**Areas discussed:** 5

---

## Area 1: Teacher Cascade Escalation Logic

**Question:** Escalation trigger mechanism
**Options presented:** Quality threshold vs always-run-all
**User selected:** Quality threshold — confidence-based escalation from Fast to domain-routed Level 2

**Question:** Escalation metric
**User selected:** Confidence (logprobs mean token probability) triggers escalation. Level 2 teacher selected from benchmark table by domain strength.

**Question:** Per-teacher config location
**User selected:** All teacher configs in `pipeline.yaml` as a list. API keys in `.env`.

**Question:** GLM 5.2 role
**User selected:** GLM 5.2 runs only when benchmark-routed for its strong domains or when other Level 2 teachers are below threshold. NOT a mandatory final pass.

**Captured as:** D-01 through D-04

---

## Area 2: GLM 5.2 API Integration

**Question:** Separate client class needed?
**User selected:** No — all teachers use Anthropic/OpenAI-compatible API. Existing TeacherClient works for all three.

**Captured as:** D-05, D-06

---

## Area 3: Pipeline Execution & Failure Handling

**Question:** Should runner.py actually execute stages?
**User selected:** Yes — invoke via subprocess, not just print commands.

**Question:** Error handling strategy
**User selected:** Connection errors → exponential backoff; API errors (4xx) → abort/log; stage execution errors → abort niche, continue to next niche.

**Captured as:** D-07, D-08, D-09

---

## Area 4: Budget Persistence

**Question:** Persist budget to disk?
**User selected:** Yes — persist cumulative spend across runs so budget cap is enforced globally, not per-run.

**Captured as:** D-10, D-11

---

## Area 5: Checkpoint Validation

**Question:** Validate stage outputs before marking complete?
**User selected:** Yes — per-stage validation checks (file existence, schema, content quality), not just empty `.done` files.

**Captured as:** D-12, D-13

---

## Deferred Ideas

- Dynamic benchmark table evolution — Phase 2
- Per-teacher cost tracking — future
- Distributed teacher execution — out of scope

## Claude's Discretion Items

- Retry count defaults and backoff multipliers
- Benchmark table YAML schema
- Budget state file format
- Checkpoint validation check implementations
- Circuit breaker half-open recovery interval
