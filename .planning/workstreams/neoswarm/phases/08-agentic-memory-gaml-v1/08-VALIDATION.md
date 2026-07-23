---
phase: 8
slug: agentic-memory-gaml-v1
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-22
---

# Phase 8 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Google Test (pre-built via thirdparty), CTest runner |
| **Config file** | test/CMakeLists.txt (neoswarm_test macro) |
| **Quick run command** | `cd build/OSX/Debug && ninja <test_target> && ./test/<test_target>` |
| **Full suite command** | `cd build/OSX/Debug && ninja && ctest --output-on-failure` |
| **Estimated runtime** | ~90 seconds |

---

## Sampling Rate

- **After every task commit:** Build + run the module's test target
- **After every plan wave:** Run `ctest --output-on-failure`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 120 seconds

---

## Per-task Verification Map

*To be filled by planner — each PLAN.md task maps here.*

---

## Wave 0 Requirements

- New test targets registered via existing `neoswarm_test` macro as created per wave
- `neoswarm_memory` CMake library target registered in Wave 1
- GTest + RocksDB already linked — no new framework installs

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Memory persistence across restarts | GAML-04 | Requires process restart | `./neo-swarm --memory-db /tmp/test.db --serve`, prompt, kill, restart, verify facts |

---

## Validation Sign-Off

- [ ] All tasks have <automated> verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 120s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
