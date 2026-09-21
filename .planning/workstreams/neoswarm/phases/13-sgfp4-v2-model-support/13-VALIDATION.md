---
phase: 13
slug: sgfp4-v2-model-support
status: draft
nyquist_compliant: true
wave_0_complete: true
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
| **Quick run command** | `ctest --test-dir build/Windows/Release -R test_sg_connectivity --output-on-failure` (NEO-SWARM); `cd "W:/gnus/GeniusNetwork/SuperGenius/build/Windows/Debug" && ctest --test-dir . -R mnn_tensor_fp4_test --output-on-failure` (SuperGenius, Debug per D-10) |
| **Full suite command** | `ctest --test-dir build/Windows/Release --output-on-failure --parallel` (NEO-SWARM 5-suite gate per RUN_AND_DEPLOY.md); `cd "W:/gnus/GeniusNetwork/SuperGenius/build/Windows/Debug" && ctest --test-dir . --output-on-failure` (SuperGenius) |
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
| 13-01-T1 | 13-01 | 1 | SGF-01 | T-13-02 | Backend selection accepts only `cpu`/`vulkan`, otherwise falls back to Vulkan | unit | `cd "W:/gnus/GeniusNetwork/SuperGenius/build/Windows/Debug" && cmake --build . --target quantization_test && ctest --test-dir . -R QuantizationTest --output-on-failure` | ✅ planned file targets exist | ⬜ pending |
| 13-01-T2 | 13-01 | 1 | SGF-02, SGF-04a | T-13-01 | Malformed model bytes return structured `ProcessingError`; FP4_ULTRA regression no longer asserts decode unavailable | unit | `cd "W:/gnus/GeniusNetwork/SuperGenius/build/Windows/Debug" && cmake --build . --target mnn_tensor_fp4_test SGProcessors sgprocmanagerquant && ctest --test-dir . -R MNNTensorFp4Test --output-on-failure` | ✅ planned file targets exist | ⬜ pending |
| 13-02-T1 | 13-02 | 2 | SGF-01 (D-10) | T-13-SC | Release libraries linked by NEO-SWARM are rebuilt after 13-01 source changes | build-only | `cd "W:/gnus/GeniusNetwork/SuperGenius/build/Windows/Release" && cmake --build . --target SGProcessors sgprocmanagerquant && powershell -NoProfile -Command "$lib1 = Get-Item 'W:/gnus/GeniusNetwork/SuperGenius/build/Windows/Release/SuperGenius/lib/SGProcessingManager/SGProcessors.lib'; $lib2 = Get-Item 'W:/gnus/GeniusNetwork/SuperGenius/build/Windows/Release/SuperGenius/lib/SGProcessingManager/sgprocmanagerquant.lib'; $src1 = Get-Item 'W:/gnus/GeniusNetwork/SuperGenius/SGProcessingManager/src/processors/processing_processor_mnn_tensor.cpp'; $src2 = Get-Item 'W:/gnus/GeniusNetwork/SuperGenius/SGProcessingManager/src/util/quantization.cpp'; if ($lib1.LastWriteTime -lt $src1.LastWriteTime -or $lib2.LastWriteTime -lt $src2.LastWriteTime) { throw 'Release libraries are older than 13-01 source changes'; }"` | ✅ build outputs exist | ⬜ pending |
| 13-02-T2 | 13-02 | 2 | SGF-01, D-06 | T-13-03 | Fixture provenance is committed and staged into the NEO-SWARM integration test output directory | build/assertion | `cmake --build build/Windows/Release --target test_sgprocessing_pipeline && ctest --test-dir build/Windows/Release -R SGProcessingBridge.BuildSchemaJson_Fp4Ultra --output-on-failure` | ❌ new fixture files | ⬜ pending |
| 13-02-T3 | 13-02 | 2 | SGF-01, D-07 | T-13-04, T-13-05 | CPU and Vulkan direct-path tests assert `OpType_SGFP4Dequant` presence and skip Vulkan only for no-device hosts | integration | `cmake --build build/Windows/Release --target test_sgprocessing_pipeline && ctest --test-dir build/Windows/Release -R "SGProcessingPipeline.Sgfp4Direct(Cpu|Vulkan)_EndToEnd" --output-on-failure` | ❌ new test cases | ⬜ pending |
| 13-03-T1 | 13-03 | 1 | SGF-03 | T-13-07 | Orphaned NF4 codec surface is removed and no residual references remain | build-only | `git grep -n "fp4_codec\|FP4Codec" -- src test && cmake --build build/Windows/Release --target neoswarm_core test_sg_connectivity` | ✅ existing files to delete | ⬜ pending |
| 13-03-T2 | 13-03 | 1 | SGF-04b | T-13-06 | Connectivity regression matches the canonical FP4_ULTRA schema contract | unit | `cmake --build build/Windows/Release --target test_sg_connectivity && ctest --test-dir build/Windows/Release -R SGConnectivity.BuildSchemaJsonFP4UltraFormatEmitsFP4Type --output-on-failure` | ✅ rewrite target exists | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Plan Coverage Check

- [x] Every planned task has a concrete `<automated>` verifier.
- [x] SuperGenius-targeted automated commands use the absolute SGProcessingManager build trees rather than NEO-SWARM's unrelated `build/` directory.
- [x] D-10's explicit Release rebuild step is represented as Task `13-02-T1` before the release-mode NEO-SWARM integration tests.
- [x] No placeholder task IDs remain; all validation rows map to `13-01`, `13-02`, or `13-03` tasks.

*GTest/CTest wiring, fixture conventions, and `neoswarm_test`/`addtest` macros are already established and reusable.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Produce SGFP4 test model via `mnnconvert --sgfp4` | SGF-01 (D-06) | CLI tool invocation with a source model; one-time asset production (same pattern as RUN_AND_DEPLOY.md's `llmexport.py`) | Run `mnnconvert --sgfp4` on a small inline source model (below `_largeModel` threshold); commit output `.mnn` under test assets; record exact command in the test/recipe docs |

*All other phase behaviors have automated verification.*

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or explicit covered prerequisite tasks
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] No placeholder Wave 0 dependencies remain
- [ ] No watch-mode flags
- [ ] Feedback latency < 300s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
