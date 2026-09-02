---
phase: 13-sgfp4-v2-model-support
verified: 2026-09-02T19:55:00Z
status: passed
score: 11/11 must-haves verified
overrides_applied: 0
---

# Phase 13: SGFP4 v2 Model Support Verification Report

**Phase Goal:** Run a real SGFP4-quantized `.mnn` model through `MNNInferenceEngine → SGProcessingManager` via the direct-call path (no SuperGenius network/job submission), with explicit CPU and Vulkan session support, a defensive malformed-model error fix, dead NF4 code removed, and stale FP4 tests corrected.
**Verified:** 2026-09-02T19:55:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

Merged from ROADMAP Phase 13 scope + PLAN 13-01/02/03 frontmatter `must_haves`.

| # | Truth | Source | Status | Evidence |
|---|-------|--------|--------|----------|
| 1 | D-09: cross-repo commits land innermost-first (SGProcessingManager branch carries Phase 13 commits) | 13-01 | ✓ VERIFIED | `git log` on `SGProcessingManager` shows `3291f5c` → `dd8c4e5` → `8c83001` on branch `gsd/phase-13-sgfp4-v2`, parented on `e1f28d7` (dev_cognitive) |
| 2 | D-04/D-05: MNN_Tensor creates explicit CPU or Vulkan session from a schema parameter (no silent Vulkan hardcode) | 13-01 | ✓ VERIFIED | `processing_processor_mnn_tensor.cpp:195` calls `ResolveMnnBackend(parameters)`; `Process(...)` takes `MNNForwardType backend` param, `config.type = backend` (line 495); `ResolveMnnBackend` returns `MNN_FORWARD_CPU` only for "cpu", `MNN_FORWARD_VULKAN` fallback otherwise (`quantization.cpp:88-121`) |
| 3 | D-11/SGF-02: malformed/incompatible model bytes return a structured ProcessingError instead of crashing on `procresults->host<float>()` | 13-01 | ✓ VERIFIED | Null-check at line 338 returns `ProcessingError{FORMAT_UNSUPPORTED, "MNN_Tensor::Process returned null (malformed or incompatible model)"}` before `host<float>()` deref; `MalformedModelBufferReturnsCleanErrorNoCrash` re-run this session → PASS |
| 4 | SGF-04a: FP4_ULTRA unit coverage no longer asserts decode unavailable | 13-01 | ✓ VERIFIED | `Fp4UltraRecognizedAndMalformedModelReturnsCleanError` replaced the stale test; grep for `MNN_Ultra\|DecodeUnavailable` in `mnn_tensor_fp4_test.cpp` → only a historical comment; test re-run → PASS |
| 5 | D-01: E2E targets real local execution, not a permanent skip-gate (deadlock closed per RESEARCH Finding 2) | 13-02 | ✓ VERIFIED | Test comments cite closed `VulkanInitMutex` deadlock (sgproc-render Phase 18, 528a92a); Vulkan test's only skip is `!HasUsableVulkanDevice()` (D-03); on this host the Vulkan test EXECUTED (231 ms, `[OK]`), not skipped |
| 6 | SGF-01/D-02: real SGFP4-quantized .mnn fixture returns non-empty output through SubmitDirect on CPU and Vulkan | 13-02 | ✓ VERIFIED | `Sgfp4DirectCpu_EndToEnd` (221 ms) and `Sgfp4DirectVulkan_EndToEnd` (231 ms) both re-run this session — real execution, `SubmitDirect` result non-empty asserted; full suite 17/17 PASSED |
| 7 | D-07: E2E test fails loudly if fixture contains zero `OpType_SGFP4Dequant` ops | 13-02 | ✓ VERIFIED | `AssertModelContainsSgfp4DequantOp` (lines 81-114) verifies flatbuffer, walks `Net::oplists()`, `EXPECT_TRUE` in both tests; failure message explicitly rejects vacuous all-FP32 models |
| 8 | D-03: Vulkan skipped ONLY when `HasUsableVulkanDevice()` reports no device | 13-02 | ✓ VERIFIED | Single `GTEST_SKIP` gated on `!HasUsableVulkanDevice()`; no deadlock-citing skip |
| 9 | SGF-03: orphaned NF4 `fp4_codec` implementation and test target removed entirely | 13-03 | ✓ VERIFIED | `src/core/fp4/` does not exist; `src/core/CMakeLists.txt` has zero `fp4` matches; `test/CMakeLists.txt` has zero `test_fp4_codec` matches; `git grep fp4_codec\|FP4Codec` over src+test → empty |
| 10 | SGF-04b: FP4_ULTRA schema regression asserts `type=tensor`, `format=FP4_ULTRA`, lowercase `fp4_ultra` absent | 13-03 | ✓ VERIFIED | `test_sg_connectivity.cpp:74-76` — `EXPECT_NE find("\"type\":\"tensor\"")`, `EXPECT_NE find("\"format\":\"FP4_ULTRA\"")`, `EXPECT_EQ find("fp4_ultra", npos)`; suite re-run 8/8 PASSED |
| 11 | D-08: no code/tests call SGFP4 by the wrong "Ultra FP4" name | 13-03 | ✓ VERIFIED | Grep `Ultra FP4` across both touched NEO-SWARM test files → empty |

**Score:** 11/11 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `SuperGenius/SGProcessingManager/include/util/quantization.hpp` | `ResolveMnnBackend` declaration | ✓ VERIFIED | Declared with full doc comment; `<MNN/MNNForwardType.h>` include present |
| `SuperGenius/SGProcessingManager/src/util/quantization.cpp` | Implementation with Vulkan fallback | ✓ VERIFIED | Lowercase-normalize → accept-list (cpu/vulkan) → `kFallbackBackend = MNN_FORWARD_VULKAN` |
| `SuperGenius/SGProcessingManager/src/processors/processing_processor_mnn_tensor.cpp` | Backend threading + null-safe error | ✓ VERIFIED | Resolver call, `backend` param through `Process()`, CPU branch bypasses `VulkanInitMutex`, null-check with structured error |
| `SuperGenius/SGProcessingManager/test/processors/mnn_tensor_fp4_test.cpp` | Malformed-model regression + non-stale FP4_ULTRA | ✓ VERIFIED | Both tests present and passing (5/5 suite) |
| `test/integration/processing_datatypes/sgfp4_tiny.mnn` | SGFP4 fixture with ≥1 SGFP4Dequant op | ✓ VERIFIED | 26,448 bytes (matches recipe claim exactly); op-presence asserted at test time |
| `test/integration/processing_datatypes/sgfp4_tiny_input.raw` | Input tensor bytes | ✓ VERIFIED | 23,104 bytes = 5,776 floats × 4 (declared [1,1,76,76] input) |
| `test/integration/processing_datatypes/sgfp4_tiny.recipe.md` | Literal `--sgfp4` provenance | ✓ VERIFIED | Contains literal `mnnconvert --sgfp4` command, vendored MNNConvert path, byte-diff verification note |
| `test/integration/test_sgprocessing_pipeline.cpp` | CPU + Vulkan direct-path E2E tests | ✓ VERIFIED | Both tests substantive: fixture-op gate, backend-parameterized schema, SubmitDirect, non-empty output assertions |
| `src/core/CMakeLists.txt` | Source list without fp4_codec | ✓ VERIFIED | Zero fp4 matches |
| `test/CMakeLists.txt` | Test list without test_fp4_codec; stages 3 sgfp4 fixtures | ✓ VERIFIED | Lines 107-109 stage `.mnn`/`.raw`/`.recipe.md` via `copy_if_different` |
| `test/integration/test_sg_connectivity.cpp` | Corrected FP4_ULTRA assertions | ✓ VERIFIED | Lines 74-76 mirror canonical pipeline assertions |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `processing_processor_mnn_tensor.cpp` | `src/util/quantization.cpp` | `StartProcessing()` resolves backend before `Process()` builds ScheduleConfig | ✓ WIRED | Line 195 resolver call → line 337 `Process(..., backend)` → line 495 `config.type = backend` |
| `mnn_tensor_fp4_test.cpp` | `processing_processor_mnn_tensor.cpp` | Direct StartProcessing() regression coverage | ✓ WIRED | `CallStartProcessing(...)` invokes real processor; both tests assert structured error stage+message |
| `test/CMakeLists.txt` | `sgfp4_tiny.mnn` | copy_if_different staging | ✓ WIRED | POST_BUILD copy into `$<TARGET_FILE_DIR>/processing_datatypes/` — confirmed by tests finding fixtures at runtime |
| `test_sgprocessing_pipeline.cpp` | `processing_processor_mnn_tensor.cpp` | Backend param in schema JSON → SubmitDirect → Create/Process | ✓ WIRED | `BuildBackendParameterizedSchemaJson` injects `backend` param + patches type→tensor; `SubmitDirect` promoted public (`sg_processing_bridge.hpp:112`) |
| `src/core/CMakeLists.txt` | `src/core/fp4/fp4_codec.cpp` | Source-list removal | ✓ WIRED (removed) | Directory gone; no dangling reference |
| `test/CMakeLists.txt` | `test/core/test_fp4_codec.cpp` | Target removal | ✓ WIRED (removed) | File gone; no dangling reference |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|-------------------|--------|
| `test_sgprocessing_pipeline.cpp` E2E tests | `result` (SubmitDirect return) | Real `.mnn` fixture file → ProcessingManager → MNN interpreter | Yes — non-empty bytes asserted, 221/231 ms real inference | ✓ FLOWING |
| `AssertModelContainsSgfp4DequantOp` | `sgfp4Count` | Committed flatbuffer bytes via `MNN::GetNet` | Yes — count ≥1 asserted (would fail on all-FP32 model) | ✓ FLOWING |
| `BuildBackendParameterizedSchemaJson` | `doc["parameters"]` | Bridge `BuildSchemaJson` output + JSON patch | Yes — real schema, backend string reaches resolver | ✓ FLOWING |

### Behavioral Spot-Checks

All re-run by the verifier this session (not relying on SUMMARY claims):

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| NEO-SWARM full pipeline suite (both SGFP4 E2E) | `test_sgprocessing_pipeline.exe` | 17/17 PASSED; CPU E2E 221 ms, Vulkan E2E 231 ms (executed, not skipped) | ✓ PASS |
| NEO-SWARM connectivity suite (FP4_ULTRA contract) | `test_sg_connectivity.exe` | 8/8 PASSED | ✓ PASS |
| SuperGenius resolver unit tests | `quantization_test.exe` | 24/24 PASSED incl. all 4 `ResolveMnnBackend` cases (null/cpu/vulkan/invalid) | ✓ PASS |
| SuperGenius FP4 malformed-model regression | `mnn_tensor_fp4_test.exe` | 5/5 PASSED incl. `MalformedModelBufferReturnsCleanErrorNoCrash` (logged "Failed to create MNN interpreter" → clean error, no crash) | ✓ PASS |
| Install libs newer than Phase 13 source edits | timestamp compare | `SGProcessors.lib` 18:49:56 > processor .cpp 18:37:28; `sgprocmanagerquant.lib` 18:49:53 > quantization .cpp 18:34:48 | ✓ PASS |
| Test binaries newer than phase sources | timestamp compare | `test_sgprocessing_pipeline.exe` 19:40:43; connectivity 19:04:22 — both post-edit | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| SGF-01 | 13-01, 13-02 | Real SGFP4 .mnn through MNNInferenceEngine → SubmitDirect → ProcessingManager::Create/Process, direct-call path | ✓ SATISFIED | Both E2E tests re-run and passing on CPU + Vulkan; engine→bridge wiring exists in production (`InferViaSGProcessing` → `m_bridge->SubmitJob`, `mnn_inference_engine.cpp:257-293`); bridge→manager segment proven with backend parameter (see INFO note below) |
| SGF-02 | 13-01 | Defensive null-check fix in processing_processor_mnn_tensor.cpp | ✓ SATISFIED | Null-check + structured ProcessingError; regression test re-run PASS |
| SGF-03 | 13-03 | Delete orphaned NF4 fp4_codec + test | ✓ SATISFIED | All files/dirs/CMake entries gone; grep clean |
| SGF-04 | 13-01, 13-03 | Fix stale FP4-area tests (SuperGenius + NEO-SWARM) | ✓ SATISFIED | Both rewritten to canonical contract; re-run PASS |

No orphaned requirements — REQUIREMENTS.md maps exactly SGF-01..04 to Phase 13; all four appear in PLAN frontmatter; traceability table rows 212-215 consistent.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | No TBD/FIXME/XXX/TODO/HACK markers in any phase-modified file (both repos) | — | — |
| — | — | No stub returns, empty handlers, or hardcoded empty data in touched files | — | — |

### INFO Observations (non-blocking)

1. **E2E entry point is the bridge, not the engine.** SGF-01 names `MNNInferenceEngine` in the chain; the E2E tests enter at `SGProcessingBridge::SubmitDirect` with a schema-patched `backend` parameter because `MNNInferenceEngine::InferViaSGProcessing` uses `SubmitJob`, which does not emit a backend parameter. The engine→bridge segment is pre-existing production wiring (Phase 4, exercised by `SGConnectivity` tests), and the new tests prove the bridge→ProcessingManager→MNN_Tensor segment end-to-end. `SubmitDirect` was promoted to public for this purpose — a documented key decision in 13-02-SUMMARY. Chain composition is sound; no action needed.
2. `sgfp4_tiny_src.onnx` also exists in `processing_datatypes/` (recipe says "not committed") — it is staged neither by CMake nor referenced by tests; harmless addition to the recipe's reproducibility story.

### Human Verification Required

None. All phase truths were verified through static code inspection plus direct re-execution of every relevant test binary on this host (CPU and Vulkan E2E both executed with real assertions). No visual, UX, or external-service checks are implicated by this phase.

### Gaps Summary

No gaps. All 11 merged must-have truths verified against actual code in both repositories; all 11 artifacts exist, are substantive, and are wired; all 6 key links verified; all 4 requirements (SGF-01..04) satisfied with re-run test evidence; no debt markers or stub patterns in phase-modified files; SuperGenius install libs and NEO-SWARM test binaries verified newer than Phase 13 source edits.

---

_Verified: 2026-09-02T19:55:00Z_
_Verifier: the agent (gsd-verifier)_
