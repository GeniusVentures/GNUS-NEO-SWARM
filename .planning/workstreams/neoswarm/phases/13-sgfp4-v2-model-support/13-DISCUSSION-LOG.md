# Phase 13: SGFP4 v2 Model Support - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-09-02
**Phase:** 13-sgfp4-v2-model-support
**Areas discussed:** E2E verification gate, Test model logistics, Backend coverage, Cross-repo fix mechanics

---

## E2E Verification Gate

**Q1: Posture toward the VulkanInitMutex deadlock (sgproc-render Phase 18)?**

| Option | Description | Selected |
|--------|-------------|----------|
| Check first, fallback skip-gate | Research step checks Phase 18 status; fixed → real E2E, open → skip-gate per 04-04; documented in RESEARCH.md | ✓ |
| Skip-gate unconditionally | Assume deadlock open; prove wiring/dispatch only | |
| Fix deadlock first | Hard blocking prerequisite; real local E2E as hard success criterion | |

**Q2: SGF-01's success criterion?**

| Option | Description | Selected |
|--------|-------------|----------|
| Wiring proven + conditional exec | Full path to Create() always runs; asserts when possible, GTEST_SKIP() citing bug when not; passes either way | ✓ |
| Real E2E or phase blocks | Only passes on completed real local run | |
| Wiring/dispatch only | No GPU execution attempted this phase | |

**Q3: Skip-gate mechanics?**

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse 04-04 pattern | HasUsableVulkanDevice() → GTEST_SKIP() with bug name in message | ✓ |
| Env flag + device check | NEO_SWARM_TEST_* env var for CI vs local control | |
| Claude decides | Planner picks mechanism at plan time | |

**User's choice:** Check first + conditional bar + 04-04 mechanics
**Notes:** None needed — all three recommended options accepted.

---

## Test Model Logistics

**Q1: How does the test SGFP4 .mnn get into the test run?**

| Option | Description | Selected |
|--------|-------------|----------|
| Committed tiny conv model | Committed test asset; manual mnnconvert recipe documented; self-contained test | ✓ |
| Manual prerequisite doc | Each machine produces the .mnn by hand before running | |
| Build-time conversion step | CMake fixture converts if mnnconvert available, skips otherwise | |

**Q2: Verify the model actually contains SGFP4 ops?**

| Option | Description | Selected |
|--------|-------------|----------|
| Assert SGFP4 op present | Walk op list; assert ≥1 OpType_SGFP4Dequant; all-FP32 model fails loudly | ✓ |
| Load-and-run only | Trust mnnconvert output; unquantized model passes vacuously | |
| Claude decides | Depends on MNN op-introspection API at plan time | |

**Q3: Naming/format documentation discipline?**

| Option | Description | Selected |
|--------|-------------|----------|
| SGFP4 v2 everywhere | Never "Ultra FP4"/"FP4 Ultra" in new tests/files/docs | ✓ |
| SGFP4 v2 + format primer | Also document the three-format distinction in test comments | |

**User's choice:** Committed model + op-presence assertion + strict naming
**Notes:** None.

---

## Backend Coverage

**Q1: Which MNN backends must Phase 13 E2E cover?**

| Option | Description | Selected |
|--------|-------------|----------|
| CPU primary + Vulkan conditional | CPU asserts; Vulkan follows Area-1 skip-gate decision | |
| CPU only | MNN already verified Vulkan SGFP4 decode internally | |
| CPU + Vulkan both required | Hard success criteria; Vulkan must execute locally | ✓ |

**Q2: How should the E2E test pin the session backend?**

| Option | Description | Selected |
|--------|-------------|----------|
| Explicit CPU session | Deterministic everywhere; single backend | |
| Both explicit sessions | One CPU test + one Vulkan test; proves both direct paths | ✓ |
| Processor default | Ride existing SGProcessingManager session config | |

**User's choice:** Both required + both explicit sessions
**Notes:** Claude flagged the conflict between "both required" (this area) and the Area-1 skip-gate fallback. Reconciliation question asked (below).

**Q3 (reconciliation): How to resolve "both required" vs. skip-gate fallback?**

| Option | Description | Selected |
|--------|-------------|----------|
| Vulkan hard — fix deadlock in-phase | If deadlock open, phase plan includes fixing/pulling the fix; CPU ships first; Vulkan skip-gated only until fixed | ✓ |
| Vulkan hard — phase blocks | No skip-gating; phase stays open until sgproc-render Phase 18 lands separately | |
| Both covered, skip-gate OK | "Required" meant test coverage, not execution | |

**User's choice:** Vulkan hard — fix deadlock in-phase
**Notes:** This is the strongest-cost option: the phase may absorb upstream deadlock-fix work as prerequisite. Captured as D-04 in CONTEXT.md.

---

## Cross-Repo Fix Mechanics

**Q1: How do SGF-02/04 (SuperGenius-side) land relative to Phase 13?**

| Option | Description | Selected |
|--------|-------------|----------|
| One phase, cross-repo plans | Same as Phase 4; innermost-first commits; git status --short verification | ✓ |
| Split by repo | NEO-SWARM-only phase; SuperGenius fixes to sgproc-render workstream | |

**Q2: How do NEO-SWARM tests pick up the SGF-02 fix?**

| Option | Description | Selected |
|--------|-------------|----------|
| Rebuild SuperGenius libs | Rebuild build/Windows/Release/SuperGenius/lib/ after source fix | |
| Link existing prebuilts | Fix lands upstream but isn't exercised this phase | |
| Researcher verifies | Recheck D-02 link path and rebuild procedure at plan time | |

**User's choice:** (free text) "I rebuilt SuperGenius / GeniusSDK now."
**Notes:** Follow-up asked to confirm baseline vs. rebuild-on-change.

**Q2b: Treat your rebuild as baseline, or rebuild after SGF-02 lands?**

**User's choice:** (free text) "We can rebuild those if needed due to source changes. I also added debug builds."
**Notes:** Final confirmation question asked (below).

**Q2c: Which rebuild rule goes into plans?**

| Option | Description | Selected |
|--------|-------------|----------|
| Rebuild after source changes | Explicit rebuild step after SGF-02/deadlock-fix commits; Debug builds available for deadlock debugging | ✓ |
| Rebuild Release + Debug for debug | Pin exact configs per change type | |

**Q3: Does SGF-02 ship with its own regression test?**

| Option | Description | Selected |
|--------|-------------|----------|
| Fix + negative test | Malformed model through MNN_Tensor processor; assert clean error, no crash | ✓ |
| Fix only | Null-check and error return alone | |
| Claude decides | Based on StartProcessing() error propagation shape | |

**User's choice:** Cross-repo single phase + rebuild-on-change + fix with negative test
**Notes:** User proactively rebuilt SuperGenius/GeniusSDK (2026-09-02) with Debug builds added — captured as the baseline in D-10.

---

## Claude's Discretion

- SGF-02 error-propagation shape (error code vs. exception vs. empty-result) — per `StartProcessing()`'s existing paths on `dev_childwallet`
- Test-asset conv architecture choice (stacked convs, >4096-element weights, well under externalization threshold)
- CMake wiring for the committed `.mnn` test asset
- Whether CPU E2E can run unconditionally (CPU path may not touch VulkanInitMutex — researcher verifies)

## Deferred Ideas

- MNN-side `op->externalPath` injection gap for externalized SGFP4 weights (mitigated by small/inline models)
- gnus-poc `--adaptive` default flip + `"fp4_ultra_v0.2"` naming collision
- arxiv §8 verifiable-execution/attestation
- `InputFormat::SGFP4_V2` wire format
- Real-data accuracy validation of SGFP4 decode (MNN's E2E gate is liveness-only)
