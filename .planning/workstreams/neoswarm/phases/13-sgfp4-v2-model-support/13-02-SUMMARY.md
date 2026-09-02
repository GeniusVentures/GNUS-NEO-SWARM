---
phase: 13-sgfp4-v2-model-support
plan: 02
subsystem: testing
tags: [sgfp4, e2e, mnn, vulkan, cpu-backend, integration, fixture]

requires:
  - phase: 13-01
    provides: "ResolveMnnBackend schema parameter + MNN_Tensor backend threading + null-safe Process"
  - phase: 13-03
    provides: "NF4 dead code removed and FP4 schema contract canonicalized"
provides:
  - "Committed inline SGFP4 fixture (sgfp4_tiny.mnn, 26,448 bytes, 1 SGFP4Dequant op) with literal mnnconvert --sgfp4 provenance"
  - "SGProcessingPipeline.Sgfp4DirectCpu_EndToEnd — real SGFP4 run through SubmitDirect on an explicit CPU session"
  - "SGProcessingPipeline.Sgfp4DirectVulkan_EndToEnd — same on explicit Vulkan session (skip only when no device)"
  - "AssertModelContainsSgfp4DequantOp helper (D-07 anti-vacuous gate)"
  - "SGProcessingBridge::SubmitDirect promoted to public for parameter-injecting callers"
affects: [neoswarm api consumers, future SGFP4 correctness work]

tech-stack:
  added: ["MNN_generated.h flatbuffer reader (header-only, test-scope include)"]
  patterns: ["Schema JSON patch for dispatch type + parameters injection (extends the LLM test's patch pattern)"]

key-files:
  created:
    - "test/integration/processing_datatypes/sgfp4_tiny.mnn"
    - "test/integration/processing_datatypes/sgfp4_tiny_input.raw"
    - "test/integration/processing_datatypes/sgfp4_tiny.recipe.md"
  modified:
    - "test/integration/test_sgprocessing_pipeline.cpp"
    - "test/CMakeLists.txt"
    - "src/core/sgprocessing/sg_processing_bridge.hpp"

key-decisions:
  - "SubmitDirect promoted from private to public (body unchanged) so tests can inject a schema `parameters` array that SubmitJob's builder does not emit — the same need the LLM test solved by calling ProcessingManager directly, but keeping the FULL bridge->Create->Process chain per D-02"
  - "Test helper patches input type float->tensor so dispatch reaches MNN_Tensor (the only processor consuming `backend`); the schema's input format stays FLOAT32 per D-08 — SGFP4 is a weight format, never an input encoding"
  - "Fixture = 2-conv ONNX (conv weights 648 + 5184 elements; 5184 > 4096 guarantees an SGFP4Dequant macroblock), converted with the VENDORED MNNConvert (thirdparty/MNN/.build/Release — carries --sgfp4; C:\MNNTools copy does not)"
  - "D-07 op-walk uses the header-only generated reader (MNN::GetNet/VerifyNetBuffer) with include dirs derived from PROJECT_SUPER_ROOT — no MNN lib symbols needed, so no new link dependencies"

patterns-established:
  - "Flatbuffer op-presence assertion pattern: verify buffer -> GetNet -> iterate oplists -> compare OpType enum"

requirements-completed: [SGF-01]

coverage:
  - id: D1
    description: "SuperGenius Release install-location libs rebuilt and proven newer than 13-01 sources (D-10)"
    requirement: SGF-01
    verification:
      - kind: command
        ref: "cmake --build W:/gnus/GeniusNetwork/SuperGenius/build/Windows/Release --target INSTALL (exit 0); SGProcessors.lib 09/02 18:49:56 > processing_processor_mnn_tensor.cpp 09/02 18:37:28; sgprocmanagerquant.lib 18:49:53 > quantization.cpp 18:34:48"
        status: pass
    human_judgment: false
  - id: D2
    description: "Inline SGFP4 fixture + input + recipe committed and staged via copy_if_different"
    requirement: SGF-01
    verification:
      - kind: command
        ref: "post-build check: sgfp4_tiny.mnn/sgfp4_tiny_input.raw/sgfp4_tiny.recipe.md present under test output processing_datatypes/"
        status: pass
      - kind: command
        ref: "raw flatbuffer scan: OpType 605 (SGFP4Dequant) present exactly once in sgfp4_tiny.mnn, absent in plain conversion"
        status: pass
    human_judgment: false
  - id: D3
    description: "CPU direct-path SGFP4 E2E returns non-empty output through SubmitDirect -> ProcessingManager::Create/Process"
    requirement: SGF-01
    verification:
      - kind: integration
        ref: "test/integration/test_sgprocessing_pipeline.cpp#SGProcessingPipeline.Sgfp4DirectCpu_EndToEnd (283 ms, 'Tensor processing complete' log confirms MNN_Tensor path)"
        status: pass
    human_judgment: false
  - id: D4
    description: "Vulkan direct-path SGFP4 E2E returns non-empty output; skips only when no usable Vulkan device"
    requirement: SGF-01
    verification:
      - kind: integration
        ref: "test/integration/test_sgprocessing_pipeline.cpp#SGProcessingPipeline.Sgfp4DirectVulkan_EndToEnd (246 ms, executed real assertions on this host)"
        status: pass
    human_judgment: false
  - id: D5
    description: "Both tests prove fixture carries >=1 OpType_SGFP4Dequant op before dispatch (D-07)"
    requirement: SGF-01
    verification:
      - kind: integration
        ref: "AssertModelContainsSgfp4DequantOp EXPECT_TRUE in both tests (flatbuffer VerifyNetBuffer + oplists walk)"
        status: pass
    human_judgment: false

duration: 52min
completed: 2026-09-02
status: complete
---

# Phase 13 Plan 02: SGFP4 Direct-Call E2E Proof Summary

**Real SGFP4-quantized model proven through the full direct-call chain on BOTH explicit CPU and explicit Vulkan sessions — with a committed fixture whose SGFP4Dequant op is asserted at test time so the proof can never go vacuous.**

## Performance

- **Duration:** ~52 min
- **Started:** 2026-09-02T23:07Z
- **Completed:** 2026-09-02T23:45Z
- **Tasks:** 3
- **Files:** 3 created, 3 modified

## Accomplishments

- Task 1 (D-10): ran the SuperGenius Release INSTALL target; install-location `SGProcessors.lib`/`sgprocmanagerquant.lib` (the exact paths NEO-SWARM's `src/core/CMakeLists.txt` links) now postdate the 13-01 source edits — timestamp evidence captured.
- Task 2 (D-06): built a tiny 2-conv ONNX net (conv weights 648 + 5184 elements — the latter exceeds the >4096 gate), converted with the vendored `MNNConvert.exe --sgfp4` to a 26,448-byte inline fixture; committed the matching 5,776-float input and a recipe documenting the literal command. Raw-scan verified: `OpType` 605 (`SGFP4Dequant`) appears exactly once in the SGFP4 model and zero times in a plain conversion of the same source.
- Task 3 (SGF-01/D-05/D-07): added `Sgfp4DirectCpu_EndToEnd` and `Sgfp4DirectVulkan_EndToEnd` — schema via `BuildSchemaJson` (FLOAT32 input per D-08), patched to `type=tensor` + injected `parameters:[{backend}]`, run through `SubmitDirect()` → `ProcessingManager::Create()`/`Process()`. Both pass with non-empty output (283/246 ms) and the log confirms the genuine `MNN_Tensor` path (`Tensor processing complete`). Vulkan executed real assertions (device present); its only skip condition is `HasUsableVulkanDevice() == false` (D-03).
- Full `test_sgprocessing_pipeline` suite: 17/17 green.

## Task Commits

1. **Task 1** - rebuild/INSTALL evidence only (no source commit; captured above and in SUMMARY)
2. **Task 2** - `a4fbd6b` (test: commit inline SGFP4 fixture with provenance)
3. **Task 3** - `f47ce0e` (test: SGFP4 CPU+Vulkan direct-path E2E + SubmitDirect public)

## Files Created/Modified

- `test/integration/processing_datatypes/sgfp4_tiny.mnn` / `sgfp4_tiny_input.raw` / `sgfp4_tiny.recipe.md` — fixture trio
- `test/integration/test_sgprocessing_pipeline.cpp` — helpers + 2 E2E tests + MNN_generated.h/json includes
- `test/CMakeLists.txt` — fixture staging entries + MNN schema/flatbuffers include dirs (PROJECT_SUPER_ROOT-derived)
- `src/core/sgprocessing/sg_processing_bridge.hpp` — `SubmitDirect` public with docs

## Decisions Made

- `SubmitDirect` made public rather than adding a test-only overload or duplicating the chain in test code — smallest change preserving the full production path.
- Dispatch patch (`float`→`tensor`) discovered necessary mid-task: first run passed but logged `Float processing complete` (MNN_Float ignores `backend`). Fixed so D-05's explicit-session requirement is genuinely exercised.
- Input declared as one 5,776-element block (not 64-element windows) so the model's real `[1,1,76,76]` input is fed whole.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 4-adjacent - API surface] SubmitDirect is private; plan requires tests to call it**
- **Found during:** Task 3 build
- **Issue:** `SGProcessingBridge::SubmitDirect` was private; the plan's tests call it directly.
- **Fix:** Promoted to public with documentation (body unchanged — it is the exact body `SubmitJob` reaches in direct mode). This is a deliberate, minimal API-surface change; recorded here because it touches a public header beyond the plan's `files_modified` list.
- **Files modified:** `src/core/sgprocessing/sg_processing_bridge.hpp`
- **Verification:** Build clean; both E2E tests pass through the real chain.
- **Committed in:** `f47ce0e`

**2. [Rule 1 - Test correctness] First E2E run dispatched to MNN_Float, not MNN_Tensor**
- **Found during:** Task 3 verification
- **Issue:** Schema built with FLOAT32 maps to `type:"float"` → MNN_Float — which ignores the `backend` parameter (only MNN_Tensor resolves it). Tests initially passed vacuously w.r.t. D-05.
- **Fix:** Helper patches the input type to `tensor` (the LLM test's established JSON-patch pattern); input `format` stays FLOAT32 per D-08. Rerun logs confirm `Tensor processing complete`.
- **Committed in:** `f47ce0e`

---

**Total deviations:** 2 auto-fixed (1 API-surface, 1 test-correctness)
**Impact on plan:** Both necessary for the plan's own acceptance criteria; no scope creep beyond the public-header promotion noted above.

## Issues Encountered

- The plan's `files_modified` listed the SuperGenius build-tree lib paths; the libs NEO-SWARM actually links are the install-location copies under `build/Windows/Release/SuperGenius/lib/SGProcessingManager/` — refreshed via the INSTALL target instead of a plain target build.
- Cached `GENIUSNETWORK_SUPERGENIUS_DIR` in the root build tree resolves to a nonexistent path (pre-existing quirk); the schema-include wiring uses `PROJECT_SUPER_ROOT` (which resolves correctly) instead.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- SGF-01 fully proven: both backends, real execution, op-presence-gated fixture.
- Phase 13's three plans are complete; phase-level verification can run.

## Self-Check: PASSED

---
*Phase: 13-sgfp4-v2-model-support*
*Completed: 2026-09-02*
