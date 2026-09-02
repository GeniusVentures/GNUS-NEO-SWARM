---
phase: 13
slug: sgfp4-v2-model-support
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-09-02
---

# Phase 13 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `13-RESEARCH.md` § Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | GoogleTest (GTest) via CTest — two repos: NEO-SWARM (`neoswarm_test(...)` macro) and SuperGenius/SGProcessingManager (`addtest(...)` macro) |
| **Config file** | `test/CMakeLists.txt` (NEO-SWARM); `SGProcessingManager/test/**/CMakeLists.txt` (SuperGenius submodule) |
| **Quick run command** | `ctest --test-dir build/Windows/Release -R test_sg_connectivity --output-on-failure` (NEO-SWARM); `ctest --test-dir build/Windows/Debug -R mnn_tensor_fp4_test --output-on-failure` (SuperGenius, Debug per D-10) |
| **Full suite command** | `ctest --test-dir build/Windows/Release --output-on-failure --parallel` (NEO-SWARM 5-suite gate per RUN_AND_DEPLOY.md); `ctest --test-dir build/Windows/Debug --output-on-failure` (SuperGenius) |
| **Estimated runtime** | ~2–5 min full suite (both repos); seconds per targeted test |

---

## Sampling Rate

- **After every task commit:** Run targeted `ctest -R <specific test>` in the repo the task touched
- **After every plan wave:** Run full suite in both repos (`build/Windows/{Release,Debug}`) — innermost submodule first per D-09 (SGProcessingManager → SuperGenius → NEO-SWARM)
- **Before `/gsd-verify-work`:** Full suite green (both configs) + committed `.mnn` test asset present with documented production recipe (D-06)
- **Max feedback latency:** ~300 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 13-XX (backend resolver) | TBD | 0 | SGF-01 | — | N/A | unit/build | `cmake --build build/Windows/Release --target neoswarm_core` | ❌ W0 | ⬜ pending |
| 13-XX (SGFP4 E2E CPU) | TBD | TBD | SGF-01 | — | N/A | integration | `ctest --test-dir build/Windows/Release -R "SGProcessingPipeline.SgfP4.*Cpu"` | ❌ W0 | ⬜ pending |
| 13-XX (SGFP4 E2E Vulkan) | TBD | TBD | SGF-01 | — | N/A | integration | `ctest --test-dir build/Windows/Release -R "SGProcessingPipeline.SgfP4.*Vulkan"` | ❌ W0 | ⬜ pending |
| 13-XX (Dequant op assertion) | TBD | TBD | SGF-01 (D-07) | Tampering | Assert ≥1 `OpType_SGFP4Dequant` op in loaded `.mnn` — silent FP32 fallback fails loudly | assertion in E2E test | (same test binary as SGF-01 E2E) | ❌ W0 | ⬜ pending |
| 13-XX (null-check fix) | TBD | TBD | SGF-02 | T-13-01 DoS | Malformed model → structured `ProcessingError`, never a crash | unit | `ctest --test-dir build/Windows/Debug -R mnn_tensor_fp4_test` (new negative TEST case) | ❌ W0 | ⬜ pending |
| 13-XX (fp4_codec deletion) | TBD | TBD | SGF-03 | — | N/A | build-only | `cmake --build build/Windows/Release --target neoswarm_core` (zero `fp4_codec` references) | n/a deletion | ⬜ pending |
| 13-XX (FP4_ULTRA test fix) | TBD | TBD | SGF-04a | — | N/A | unit | `ctest --test-dir build/Windows/Debug -R MnnTensorFp4Test` | ✅ rewrite | ⬜ pending |
| 13-XX (connectivity literal fix) | TBD | TBD | SGF-04b | — | N/A | unit | `ctest --test-dir build/Windows/Release -R SGConnectivity` | ✅ rewrite | ⬜ pending |

*Task IDs to be finalized by PLAN.md files; wave column reflects research-recommended ordering (backend resolver first).*

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] Backend-selection resolver + `MNN_Tensor::Process()` signature change (RESEARCH Finding 3) — must land before SGF-01 session tests can meaningfully differ
- [ ] New E2E test cases for SGF-01 (CPU + Vulkan sessions + `OpType_SGFP4Dequant` presence assertion) — new `test/integration/test_sgfp4_e2e.cpp` or cases in `test_sgprocessing_pipeline.cpp` following `Fp4UltraFormat_DispatchesToTensorProcessor` pattern
- [ ] Committed `.mnn` test asset + documented manual `mnnconvert --sgfp4` recipe (D-06) — does not exist yet
- [ ] New negative-regression TEST case for SGF-02 in `mnn_tensor_fp4_test.cpp` (malformed model bytes → structured error)

*GTest/CTest wiring, fixture conventions, and `neoswarm_test`/`addtest` macros are already established and reusable.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Produce SGFP4 test model via `mnnconvert --sgfp4` | SGF-01 (D-06) | CLI tool invocation with a source model; one-time asset production (same pattern as RUN_AND_DEPLOY.md's `llmexport.py`) | Run `mnnconvert --sgfp4` on a small inline source model (below `_largeModel` threshold); commit output `.mnn` under test assets; record exact command in the test/recipe docs |

*All other phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 300s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
