---
phase: 13-sgfp4-v2-model-support
plan: 01
subsystem: api
tags: [mnn, vulkan, cpu-backend, sgfp4, quantization, error-handling]

requires:
  - phase: 4-sgprocessing-integration
    provides: "FP4_ULTRA decode wiring (e1f28d7) and the SGProcessingBridge::SubmitDirect() direct-call path"
provides:
  - "sgns::sgprocmanagerquant::ResolveMnnBackend(parameters) — schema-driven CPU/Vulkan MNN session backend selection, Vulkan fallback"
  - "MNN_Tensor::StartProcessing()/Process() parameter-driven backend threading (no more hardcoded MNN_FORWARD_VULKAN)"
  - "Null-safe MNN_Tensor::Process() error propagation — structured ProcessingError instead of null-deref crash on malformed model bytes"
  - "Rewritten non-stale FP4_ULTRA unit coverage (SGF-04a) + MalformedModelBufferReturnsCleanErrorNoCrash regression (SGF-02/D-11)"
affects: [13-02 (E2E direct-call proof), neoswarm SGProcessingBridge consumers]

tech-stack:
  added: []
  patterns: ["Schema-parameter-driven MNN backend selection mirroring ResolveQuantScale find-by-name convention"]

key-files:
  created: []
  modified:
    - "W:/gnus/GeniusNetwork/SuperGenius/SGProcessingManager/include/util/quantization.hpp"
    - "W:/gnus/GeniusNetwork/SuperGenius/SGProcessingManager/src/util/quantization.cpp"
    - "W:/gnus/GeniusNetwork/SuperGenius/SGProcessingManager/src/processors/processing_processor_mnn_tensor.cpp"
    - "W:/gnus/GeniusNetwork/SuperGenius/SGProcessingManager/include/processors/processing_processor_mnn_tensor.hpp"
    - "W:/gnus/GeniusNetwork/SuperGenius/SGProcessingManager/test/util/quantization_test.cpp"
    - "W:/gnus/GeniusNetwork/SuperGenius/SGProcessingManager/test/processors/mnn_tensor_fp4_test.cpp"

key-decisions:
  - "ResolveMnnBackend lives in sgprocmanagerquant next to ResolveQuantScale/ResolveByteQuantMode, reusing the identical find-by-name-in-parameters lookup; MNNForwardType.h include added to the public header (MNN includes already directory-wide via CommonBuildParameters.cmake include_directories)"
  - "CPU session creation bypasses VulkanInitMutex entirely (D-05 genuinely distinct path); Vulkan branch preserves the existing locked createSession"
  - "Null-check uses ProcessingErrorStage::FORMAT_UNSUPPORTED with the exact message 'MNN_Tensor::Process returned null (malformed or incompatible model)' per plan acceptance criteria"

patterns-established:
  - "Backend resolution pattern: schema STRING parameter -> lowercase normalize -> accept-list (cpu|vulkan) -> safe fallback (vulkan); untrusted values can never select an unintended backend (T-13-02)"

requirements-completed: [SGF-02, SGF-04]

coverage:
  - id: D1
    description: "ResolveMnnBackend schema-driven CPU/Vulkan resolver with Vulkan fallback on null/missing/wrong-type/unsupported values"
    requirement: SGF-01
    verification:
      - kind: unit
        ref: "SGProcessingManager test/util/quantization_test.cpp#QuantizationTest.ResolveMnnBackendFallsBackOnNullParameters/UsesCpuWhenRequested/UsesVulkanWhenRequested/FallsBackOnInvalidString"
        status: pass
    human_judgment: false
  - id: D2
    description: "MNN_Tensor threads resolved backend through Process(); CPU sessions bypass VulkanInitMutex; Vulkan keeps locked createSession"
    requirement: SGF-01
    verification:
      - kind: unit
        ref: "command: cmake --build build/Windows/Debug --target mnn_tensor_fp4_test SGProcessors sgprocmanagerquant && ctest -R 'MNNTensorFp4Test|QuantizationTest' (2/2 passed)"
        status: pass
    human_judgment: false
  - id: D3
    description: "Malformed model buffer returns structured ProcessingError instead of crashing StartProcessing() (null procresults dereference removed)"
    requirement: SGF-02
    verification:
      - kind: unit
        ref: "SGProcessingManager test/processors/mnn_tensor_fp4_test.cpp#MnnTensorFp4Test.MalformedModelBufferReturnsCleanErrorNoCrash (RED: SEH 0xc0000005 crash -> GREEN: pass)"
        status: pass
    human_judgment: false
  - id: D4
    description: "Stale FP4_ULTRA test rewritten — no longer asserts decode unavailable / MNN_Ultra message"
    requirement: SGF-04
    verification:
      - kind: unit
        ref: "SGProcessingManager test/processors/mnn_tensor_fp4_test.cpp#MnnTensorFp4Test.Fp4UltraRecognizedAndMalformedModelReturnsCleanError"
        status: pass
    human_judgment: false

duration: 33min
completed: 2026-09-02
status: complete
---

# Phase 13 Plan 01: SuperGenius Backend Resolver + Null-Safe MNN_Tensor Summary

**Schema-driven CPU/Vulkan MNN session selection for MNN_Tensor plus a structured-error fix for the malformed-model null-deref crash — the SuperGenius prerequisite for Phase 13's real SGFP4 direct-path E2E proof.**

## Performance

- **Duration:** ~33 min
- **Started:** 2026-09-02T22:25Z
- **Completed:** 2026-09-02T22:58Z
- **Tasks:** 2
- **Files modified:** 6 (all in SGProcessingManager submodule)

## Accomplishments

- Added `ResolveMnnBackend(const std::vector<sgns::Parameter>*)` to `sgprocmanagerquant` — resolves a `backend` STRING schema parameter (`cpu`|`vulkan`, lowercase-normalized accept-list), falling back to `MNN_FORWARD_VULKAN` on null/missing/wrong-type/unsupported so every existing caller keeps today's exact behavior (D-04/D-05).
- `MNN_Tensor::StartProcessing()` resolves the backend once per invocation and threads it into `Process(...)`; `config.type` is no longer hardcoded Vulkan. CPU sessions create without taking `VulkanInitMutex()`; the Vulkan branch keeps the existing locked `createSession()`.
- Closed the SGF-02 crash: `procresults` is null-checked immediately after `Process(...)` and returns `ProcessingError{FORMAT_UNSUPPORTED, "MNN_Tensor::Process returned null (malformed or incompatible model)"}` before any `host<float>()` dereference. RED run reproduced the SEH 0xc0000005 access violation; GREEN run passes.
- Rewrote the stale `Fp4UltraRecognizedButDecodeUnavailable` (decode is live since e1f28d7) into `Fp4UltraRecognizedAndMalformedModelReturnsCleanError` (SGF-04a) and added the D-11 negative regression `MalformedModelBufferReturnsCleanErrorNoCrash`.
- Full SuperGenius Debug rebuild: zero errors (D-10). Targeted Release rebuild of `SGProcessors` + `sgprocmanagerquant`: zero errors, fresh `.lib`s for 13-02.
- D-09 innermost-first commits: SGProcessingManager branch `gsd/phase-13-sgfp4-v2` (3 commits) → SuperGenius `dev_cognitive` pointer → GeniusNetwork root `dev_persisprocresults` pointer.

## Task Commits

SGProcessingManager (branch `gsd/phase-13-sgfp4-v2`, forked from `dev_cognitive`@e1f28d7):

1. **Task 1 RED** - `3291f5c` (test: failing ResolveMnnBackend unit cases)
2. **Task 1 GREEN** - `dd8c4e5` (feat: ResolveMnnBackend resolver)
3. **Task 2 (RED+GREEN)** - `8c83001` (feat: backend threading + null-safe error + test rewrites)

Pointer commits:

- SuperGenius `dev_cognitive` - `281531cc` (chore: advance SGProcessingManager pointer)
- GeniusNetwork root `dev_persisprocresults` - `9c8845a` (chore: advance SuperGenius pointer)

## Files Created/Modified

- `include/util/quantization.hpp` — `ResolveMnnBackend` declaration + `<MNN/MNNForwardType.h>` include
- `src/util/quantization.cpp` — resolver implementation (find-by-name + lowercase accept-list)
- `src/processors/processing_processor_mnn_tensor.cpp` — backend resolution, threaded `Process()` call, CPU/Vulkan branch split, null-check, structured size-mismatch error
- `include/processors/processing_processor_mnn_tensor.hpp` — `Process()` private signature gains `MNNForwardType backend`
- `test/util/quantization_test.cpp` — 4 new ResolveMnnBackend cases
- `test/processors/mnn_tensor_fp4_test.cpp` — `CallStartProcessing` gains parameters/modelFile args; stale test rewritten; malformed-model regression added

## Decisions Made

- `ResolveMnnBackend` placed in `sgprocmanagerquant` (not a new util) to mirror the established `ResolveQuantScale` convention exactly; MNN's `MNNForwardType.h` is a self-contained C enum header so the quant lib gains no MNN link dependency.
- Kept `ProcessingErrorStage::FORMAT_UNSUPPORTED` for the null-return path per the plan's exact-message acceptance criterion (error-stage taxonomy refinement deferred).
- SGProcessingManager commits anchored on a new `gsd/phase-13-sgfp4-v2` branch because the checkout was in detached HEAD at e1f28d7 (dev_cognitive tip); branch keeps the three commits discoverable for later merge.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Pre-existing test failure on baseline: `Fp4UltraUndersizedBufferFailsSizeCheck`**
- **Found during:** Task 2 RED verification
- **Issue:** The size-mismatch early return in `StartProcessing()` returned a bare `ProcessingResult{}` (no structured error), so the pre-existing UndersizedBuffer test asserting `error.has_value()` fails on the clean baseline (e1f28d7) — verified by stash + rebuild. The test only "passed" in CI-order because the earlier crash aborted the process before it.
- **Fix:** Upgraded that early return to carry `ProcessingError{FORMAT_UNSUPPORTED, "Tensor input size N bytes is smaller than expected M bytes (buffer size vs dimensions mismatch)"}` — message still contains "buffer size" so the test's substring assertion holds.
- **Files modified:** `src/processors/processing_processor_mnn_tensor.cpp`
- **Verification:** All 5 MNNTensorFp4Test cases pass (previously 2 pass / 1 wrong-order / 2 crash).
- **Committed in:** `8c83001`

**2. [Rule 1 - Tooling] Self-inflicted duplicate closing brace after size-check edit**
- **Found during:** Task 2 GREEN build
- **Issue:** First edit attempt left a doubled `}` producing C2447; caught by build.
- **Fix:** Removed the extra brace; rebuild clean.
- **Committed in:** `8c83001`

**3. [Rule 2 - Missing critical] Two concurrent MSBuild invocations corrupted `.obj` files (Permission denied C1083)**
- **Found during:** Plan-level full rebuild
- **Issue:** A backgrounded full build overlapped a foreground re-run; two MSBuild instances contended for the same `.obj` outputs.
- **Fix:** Waited for the background instance, re-ran single-instance; full Debug build then completed with zero errors.
- **Verification:** `$env:TEMP\sgp_debug_build.log` — NO_ERRORS, exit 0.

---

**Total deviations:** 3 auto-fixed (2 bug, 1 tooling)
**Impact on plan:** Fix #1 was necessary for the plan's own test gate to pass; no scope creep.

## Issues Encountered

None beyond the deviations above. Release rebuild of the two changed libs succeeded for 13-02's dependency (note: the install-location copies under `build/Windows/Release/SuperGenius/lib/SGProcessingManager/` still show 8/31 timestamps — the `sgnus_install` step was not part of the targeted rebuild; NEO-SWARM links via the build-tree paths, which are fresh).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Wave 1 remaining: 13-03 (NEO-SWARM NF4 dead-code removal + stale schema test fix) — independent of this plan.
- Wave 2: 13-02 depends on this plan's backend resolver (`backend` schema parameter now actually selects CPU vs Vulkan) and the null-safe path. Fresh Debug + Release libs are in place.
- Reminder carried from RESEARCH: externalized-weight SGFP4 models likely don't load (op->externalPath not auto-injected) — 13-02's committed fixture must use small/inline models only (D-06).

## Self-Check: PASSED

---
*Phase: 13-sgfp4-v2-model-support*
*Completed: 2026-09-02*
