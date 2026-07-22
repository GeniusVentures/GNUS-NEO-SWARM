---
phase: 7
slug: expert-language-models-router
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-15
---

# Phase 7 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Google Test (pre-built via thirdparty), CTest runner |
| **Config file** | `test/CMakeLists.txt` (`neoswarm_test` macro) |
| **Quick run command** | `cd build/OSX/Debug && ninja <test_target> && ./test/<test_target>` |
| **Full suite command** | `cd build/OSX/Debug && ninja && ctest --output-on-failure` |
| **Estimated runtime** | ~60 seconds full suite (140+ existing tests) |

---

## Sampling Rate

- **After every task commit:** Build + run the test target for the module touched (e.g. `./test/test_elm_chain_builder`)
- **After every plan wave:** Run `ctest --output-on-failure` (full suite)
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 120 seconds

---

## Per-task Verification Map

*To be filled by planner — each PLAN.md task maps here. Template rows:*

| task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 07-01-XX | 01 | 1 | ELM-core | — | N/A | unit | `./test/test_elm_types` | ❌ W0 | ⬜ pending |
| 07-02-XX | 02 | 2 | ELM-roles | — | N/A | unit | `./test/test_role_elms` | ❌ W0 | ⬜ pending |
| 07-03-XX | 03 | 3 | ELM-router | — | N/A | unit | `./test/test_elm_chain_builder` | ❌ W0 | ⬜ pending |
| 07-04-XX | 04 | 4 | ELM-orchestration | — | N/A | integration | `./test/test_elm_pipeline` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] New test targets registered in `test/CMakeLists.txt` via existing `neoswarm_test` macro as they are created per wave
- [ ] MockEngine pattern (from existing specialist tests) reused for ELM unit tests — no model files needed
- [ ] Existing infrastructure covers framework needs (GTest already linked; no new installs)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real-model chain quality | ELM output quality | Requires a real `.mnn` model file on disk | `./neo-swarm --model <path> --prompt "solve 12*37" --verbose` — observe chain trace: Planner → Math → Verifier |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 120s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
