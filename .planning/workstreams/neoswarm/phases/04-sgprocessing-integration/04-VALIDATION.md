---
phase: 4
slug: sgprocessing-integration
status: planned
nyquist_compliant: true
wave_0_complete: true
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
| 04-01 Task 1 | 04-01 | 1 | PROC-03, FIX-04 | — | CMake relinks against GeniusNetwork's real SuperGenius build output; `neoswarm_core` links cleanly | build-verification | `cmake ... && cmake --build ... --target neoswarm_core` (grep-confirms "SGProcessingManager: linked") | ✅ | ⬜ pending |
| 04-01 Task 2 | 04-01 | 1 | PROC-03, FIX-04 | V5 | `SGProcessingBridge` `ProcessOutput`/`InputFormatToTypeString(FP4_ULTRA)` fixes compile and dispatch correctly | unit | `ctest -R "SGProcessingBridge.BuildSchemaJson_Fp4Ultra"` | ✅ | ⬜ pending |
| 04-01 Task 3 | 04-01 | 1 | PROC-03 | — | Stale SentencePiece/protobuf-conflict docs corrected (no `GENIUS_HAS_SENTENCEPIECE` references remain) | doc-verification | `! grep -q "GENIUS_HAS_SENTENCEPIECE" CONCERNS.md PROJECT.md` | ✅ | ⬜ pending |
| 04-02 Task 1 | 04-02 | 1 | PROC-02 | V5 | FP4_ULTRA re-enabled in `TENSOR` DataType validation (D-10/D-13) | source-verification | `! grep -q "format != sgns::InputFormat::FP4_ULTRA\*/" ProcessingManager.cpp` | ✅ | ⬜ pending |
| 04-02 Task 2 | 04-02 | 1 | PROC-02 | V5, DoS (Pitfall: malformed buffer) | `MNN_Tensor` handles FP4_ULTRA format with fail-closed structured error (E2M1 decode not yet merged) | unit | `ctest -R MNNTensorFp4Test` | ✅ | ⬜ pending |
| 04-02 Task 3 | 04-02 | 1 | PROC-02 | — | FP4_ULTRA dispatch end-to-end through `CheckProcessValidity()` | unit | `cmake --build . --target mnn_tensor_fp4_test && ctest -R MNNTensorFp4Test --timeout 30` | ✅ | ⬜ pending |
| 04-03 Task 1 | 04-03 | 2 (deps: 04-02) | PROC-01 | — | New `DataType::LLM` enum value registered in generated schema | source-verification | `grep -c "DataType::LLM" DataType.hpp Generators.hpp` | ✅ | ⬜ pending |
| 04-03 Task 2 | 04-03 | 2 | PROC-01 | V5 | `MNN_Llm` processor skeleton: class scaffold, model materialization, `VulkanInitMutex()`-guarded load, fail-closed on load failure | build-verification | `cmake --build . --target SGProcessors` | ❌ Wave 0 (new file) | ⬜ pending |
| 04-03 Task 3 | 04-03 | 2 | PROC-01 | DoS (Pitfall: unbounded generation) | Generation loop via `MNN::Transformer::Llm::response()`, `PushTeardown()`, cancellation + progress + hash wiring, `DataType::LLM` registered in `Init()` | build-verification | `cmake --build . --target SGProcessors` | ❌ Wave 0 (new file) | ⬜ pending |
| 04-03 Task 4 | 04-03 | 2 | PROC-01 | V5 | New LLM processor generates coherent multi-token text via `ProcessingManager::Process()` | integration | `cmake --build . --target mnn_llm_test && ctest -R MNNLlmTest --timeout 30` | ❌ Wave 0 (new file) | ⬜ pending |
| 04-04 Task 1 | 04-04 | 2 (deps: 04-01) | PROC-01, PROC-02 | — | Duplicate hand-rolled sampling loop (`InferViaStandardInterpreter`/`SampleToken`/`ApplyRepetitionPenalty`) deleted (D-06) | source+build-verification | `! grep -qE "InferViaStandardInterpreter\|SampleToken\|ApplyRepetitionPenalty" ... && cmake --build ... --target neoswarm_core` | ✅ | ⬜ pending |
| 04-04 Task 2 | 04-04 | 2 | PROC-01, PROC-02 | — | Orphaned `fp4_codec`/`FP4Codec` member removed (D-13) | source+build+unit | `! grep -q "fp4_codec\|FP4Codec" ... && cmake --build ... --target neoswarm_core test_fp4_codec && ctest -R test_fp4_codec` | ✅ | ⬜ pending |
| 04-04 Task 3 | 04-04 | 2 | PROC-01, PROC-02 | V5 | End-to-end FP4_ULTRA + LLM dispatch through `SGProcessingBridge` (schema-level; `ProcessingManager::Create()`-dependent path is a documented Manual-Only item, see below) | integration | `ctest -R "SGProcessingPipeline.(Fp4UltraFormat_DispatchesToTensorProcessor\|LlmDataType_JobReachesRegisteredProcessor)" --timeout 15` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] New processor tests (SuperGenius side) — `mnn_tensor_fp4_test` (04-02 Task 3) and `mnn_llm_test` (04-03 Task 4) cover FP4_ULTRA and MNN LLM generation respectively
- [x] `test/integration/test_sgprocessing_pipeline.cpp` (NEO-SWARM) — 04-04 Task 3 adds `Fp4UltraFormat_DispatchesToTensorProcessor` and `LlmDataType_JobReachesRegisteredProcessor` cases
- [x] `SUPERGENIUS_TEST_DATA_DIR` CMake variable fix — 04-01 Task 1 repoints it at `${GENIUSNETWORK_SUPERGENIUS_DIR}/test/src`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Full end-to-end `ProcessingManager::Create()` + `Process()` run of the new MNN LLM / FP4_ULTRA processor (SubmitDirect path) | PROC-01, PROC-02 | `ProcessingManager::Create()` unconditionally deadlocks (`VulkanInitMutex` re-entrancy, `ProcessingManager.cpp:429-440`) on any machine with a real Vulkan device — including this Windows dev machine — via a pre-existing, tracked-but-not-yet-started sgproc-render Phase 18 bug. Not fixable within this phase's scope. | Verify source-level correctness (schema validation, registration, generation-loop logic) via unit tests that don't call `Create()`. Coordinate with the sgproc-render workstream for timing on when a real end-to-end run becomes possible, or run on a machine without a real Vulkan device if one becomes available. |
| macOS/Linux `-ld_classic` propagation re-verification (FIX-04) | FIX-04 | No macOS/Linux machine was available during research; D-12 requires empirical re-verification per platform, not assumption. | Build on an available macOS/Linux machine after the CMake relink lands; confirm test binaries link without duplicate protobuf symbol errors, with or without `-ld_classic`. |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies (confirmed by gsd-plan-checker re-verification pass)
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < N/A (build-gated, see Sampling Rate)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-08-18 (gsd-plan-checker re-verification pass 1/3 — VERIFICATION PASSED)

**Known limitation carried forward, not resolved here:** the `VulkanInitMutex` deadlock (Pitfall 4) means no task's automated verify can exercise a real `ProcessingManager::Create()` call end-to-end on this machine — see Manual-Only Verifications above. All automated commands above were designed to route around that constraint (unit tests calling processors directly, or schema-level dispatch checks), per the plan checker's confirmation that "no acceptance criterion anywhere would hang on this machine."
