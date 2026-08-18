---
phase: 4
slug: sgprocessing-integration
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-18
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | GoogleTest (GTest) — discovered via `find_package(GTest QUIET)` with a manual fallback search (`test/CMakeLists.txt:1-31`, NEO-SWARM side) |
| **Config file** | `GNUS-NEO-SWARM/test/CMakeLists.txt` (NEO-SWARM); `GeniusNetwork/SuperGenius/SGProcessingManager/test/CMakeLists.txt` (SuperGenius, wired into CTest by sgproc-render Phase 10-06) |
| **Quick run command** | `ctest -R test_sgprocessing_pipeline` (NEO-SWARM); `ctest -R ProcessingDatatypesTest` (SuperGenius — currently deadlocks on real-Vulkan-device machines, see Manual-Only Verifications) |
| **Full suite command** | `ctest` from the respective configured `build/<Platform>/<BuildType>` directory |
| **Estimated runtime** | Unknown — no configured build directory currently exists on this machine (`build/Windows/` has no `CMakeCache.txt`); a fresh `cmake ..` + `ninja` run is required before any command above can execute |

---

## Sampling Rate

- **After every task commit:** Attempt a fresh `cmake ..` + `ninja` build in `build/Windows/Release` (or `Debug`) after each CMake/source fix — no configured build exists yet, so this doubles as first-build verification.
- **After every plan wave:** Full `ctest` run on whichever platform is available. Expect `ProcessingDatatypesTest`/`ProcessingDispatchTest` (SuperGenius side) to hit the `VulkanInitMutex` re-entrancy deadlock (sgproc-render's own tracked, not-yet-started Phase 18) on any machine with a real Vulkan device — document as a known, out-of-scope-to-fix blocker, not a regression this phase caused.
- **Before `/gsd-verify-work`:** Full suite must be green *for the subset not blocked by the Vulkan deadlock* — a literal "100% green" gate is not achievable end-to-end on a real-GPU machine until sgproc-render Phase 18 ships. Define the phase gate narrowly: builds and links cleanly; schema/validation-level unit tests pass; `ProcessingManager::Create()`-dependent integration tests are explicitly tracked as known-blocked, not silently skipped.
- **Max feedback latency:** N/A (build/link-gated, not watch-mode) — verification is "does it compile and link" and "do non-Vulkan-dependent unit tests pass," not a time-boxed test loop.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD (assigned at plan time) | TBD | TBD | PROC-01 | V5 (input validation) | New LLM processor generates coherent multi-token text via `ProcessingManager::Process()` | integration | New test, e.g. `SGProcessingManager/test/src/mnn_llm_processor_test.cpp` | ❌ Wave 0 | ⬜ pending |
| TBD (assigned at plan time) | TBD | TBD | PROC-02 | V5 (input validation) | FP4_ULTRA input (E2M1, per D-13) passes `CheckProcessValidity()` and dispatches to a registered processor | unit | New test alongside existing `processing_datatypes_test.cpp` fixtures | ❌ Wave 0 | ⬜ pending |
| TBD (assigned at plan time) | TBD | TBD | PROC-03 | — | Single protobuf version confirmed across the whole link (no duplicate-symbol errors) | build-verification | Full rebuild + link of `neoswarm_core` and its test binaries | N/A — verified by build success, not a test file | ⬜ pending |
| TBD (assigned at plan time) | TBD | TBD | FIX-04 | — | Test binaries link and run without duplicate-symbol errors on available platforms | build-verification | `ctest` (any suite) succeeding to link | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] New processor test (SuperGenius side) — no test currently exercises an MNN LLM generation processor or FP4_ULTRA end-to-end (PROC-01, PROC-02)
- [ ] `test/integration/test_sgprocessing_pipeline.cpp` (NEO-SWARM) — only exercises FLOAT32 today; needs an FP4_ULTRA/LLM case added
- [ ] `SUPERGENIUS_TEST_DATA_DIR` CMake variable fix — currently points at a nonexistent sibling `../SuperGenius/test/src` path; required before any SuperGenius-fixture-dependent NEO-SWARM test can locate its data

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Full end-to-end `ProcessingManager::Create()` + `Process()` run of the new MNN LLM / FP4_ULTRA processor (SubmitDirect path) | PROC-01, PROC-02 | `ProcessingManager::Create()` unconditionally deadlocks (`VulkanInitMutex` re-entrancy, `ProcessingManager.cpp:429-440`) on any machine with a real Vulkan device — including this Windows dev machine — via a pre-existing, tracked-but-not-yet-started sgproc-render Phase 18 bug. Not fixable within this phase's scope. | Verify source-level correctness (schema validation, registration, generation-loop logic) via unit tests that don't call `Create()`. Coordinate with the sgproc-render workstream for timing on when a real end-to-end run becomes possible, or run on a machine without a real Vulkan device if one becomes available. |
| macOS/Linux `-ld_classic` propagation re-verification (FIX-04) | FIX-04 | No macOS/Linux machine was available during research; D-12 requires empirical re-verification per platform, not assumption. | Build on an available macOS/Linux machine after the CMake relink lands; confirm test binaries link without duplicate protobuf symbol errors, with or without `-ld_classic`. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < N/A (build-gated, see Sampling Rate)
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
