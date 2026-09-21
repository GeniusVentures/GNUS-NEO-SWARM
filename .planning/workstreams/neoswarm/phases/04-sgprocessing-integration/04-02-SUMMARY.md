---
phase: 04-sgprocessing-integration
plan: 02
subsystem: infra
tags: [cpp, sgprocessingmanager, mnn, fp4, tensor, cross-repo, gtest]

# Dependency graph
requires: []
provides:
  - "FP4_ULTRA-formatted TENSOR jobs pass ProcessingManager::CheckProcessValidity()'s per-DataType schema validation"
  - "MNN_Tensor::StartProcessing() recognizes FP4_ULTRA and returns a structured ProcessingError{FORMAT_UNSUPPORTED, ...} instead of crashing or falling into the generic unsupported-format rejection"
  - "Buffer-size-vs-declared-dimensions validation for FP4_ULTRA (T-04-03 mitigation) before any decode attempt"
  - "First processor-level direct-unit-test location in SGProcessingManager (test/processors/)"
affects: [poc, sgproc-render]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Direct-processor unit testing: instantiate a ProcessingProcessor subclass and call StartProcessing() directly with a hand-built IoDeclaration/Dimensions, bypassing ProcessingManager::Create() entirely -- avoids the tracked VulkanInitMutex re-entrancy deadlock (sgproc-render Phase 18) and needs no real Vulkan device/model file"

key-files:
  created:
    - "SGProcessingManager/test/processors/CMakeLists.txt"
    - "SGProcessingManager/test/processors/mnn_tensor_fp4_test.cpp"
  modified:
    - "SGProcessingManager/src/processingbase/ProcessingManager.cpp"
    - "SGProcessingManager/src/processors/processing_processor_mnn_tensor.cpp"
    - "SGProcessingManager/test/CMakeLists.txt"

key-decisions:
  - "FP4_ULTRA buffer-size validation uses generic 4-bit-packing arithmetic (ceil(width/2) bytes minimum) rather than any format-specific macroblock layout -- honest sanity-check per D-09 (no dequant math), since no FP4 Ultra wire-format spec file exists on disk (RESEARCH.md Pitfall 3)"
  - "SGProcessingManager is itself a nested git submodule of the outer SuperGenius repo, pinned to its own branch (dev_rendering), separate from the outer repo's dev_childwallet -- all 3 task commits landed in the submodule on dev_rendering, followed by one submodule-pointer-bump commit in the outer repo on dev_childwallet"

patterns-established:
  - "Direct-processor GTest pattern for SGProcessingManager: build IoDeclaration/Dimensions via generated setters (no JSON), instantiate the processor class directly, call StartProcessing() with ExecutionContext::NoOp() -- fully deterministic, no Vulkan/MNN session dependency"

requirements-completed: [PROC-02]

coverage:
  - id: D1
    description: "FP4_ULTRA passes ProcessingManager's TENSOR schema validation (format-acceptance check no longer excludes it)"
    requirement: "PROC-02"
    verification:
      - kind: unit
        ref: "manual grep verify: SGProcessingManager/src/processingbase/ProcessingManager.cpp no longer contains the commented-out FP4_ULTRA exclusion clause"
        status: pass
    human_judgment: false
  - id: D2
    description: "MNN_Tensor::StartProcessing() gives FP4_ULTRA a structured FORMAT_UNSUPPORTED ProcessingError (decode-unavailable and buffer-size-mismatch paths), never touching VulkanInitMutex/MNN session creation"
    requirement: "PROC-02"
    verification:
      - kind: unit
        ref: "SGProcessingManager/test/processors/mnn_tensor_fp4_test.cpp#MnnTensorFp4Test.Fp4UltraRecognizedButDecodeUnavailable"
        status: pass
      - kind: unit
        ref: "SGProcessingManager/test/processors/mnn_tensor_fp4_test.cpp#MnnTensorFp4Test.Fp4UltraUndersizedBufferFailsSizeCheck"
        status: pass
    human_judgment: false
  - id: D3
    description: "Existing FLOAT32/FLOAT16/INT32/INT16/INT8 tensor dispatch and the pre-existing bare-rejection path for genuinely unsupported formats (e.g. RGB8) are unchanged by this plan"
    requirement: "PROC-02"
    verification:
      - kind: unit
        ref: "SGProcessingManager/test/processors/mnn_tensor_fp4_test.cpp#MnnTensorFp4Test.UnrecognizedFormatStillUsesPreExistingRejection"
        status: pass
    human_judgment: false

duration: ~20min
completed: 2026-08-18
status: complete
---

# Phase 4 Plan 2: FP4_ULTRA Input Format Processor Summary

**Re-enabled FP4_ULTRA schema validation in ProcessingManager and gave MNN_Tensor a structured `ProcessingError{FORMAT_UNSUPPORTED}` failure path for it, with new direct-processor GTest coverage in a first-of-its-kind `SGProcessingManager/test/processors/` directory -- all without implementing any FP4 dequant math (D-09 preserved).**

## Performance

- **Duration:** ~20 min
- **Completed:** 2026-08-18T21:35:16Z
- **Tasks:** 3/3 completed
- **Files modified:** 5 (2 edited source files, 1 edited CMakeLists.txt, 2 new test files)

## Accomplishments
- `ProcessingManager::CheckProcessValidity()`'s `DataType::TENSOR` case now accepts `InputFormat::FP4_ULTRA` alongside FLOAT32/FLOAT16/INT32/INT16/INT8 -- the previously commented-out clause is live code, minimal one-clause diff
- `MNN_Tensor::StartProcessing()` recognizes `FP4_ULTRA` before the generic format-rejection branch, validates the declared buffer size against the declared width (2 elements/byte, T-04-03 mitigation), and returns `ProcessingError{FORMAT_UNSUPPORTED, "..."}` describing either the size mismatch or that MNN_Ultra's E2M1 decode kernel is not yet merged into this build (D-04/D-09) -- never reaches `Process()`/MNN session creation/`VulkanInitMutex()` for this format
- New `SGProcessingManager/test/processors/` directory (first processor-level direct-unit-test location in this repo) with 3 GTest cases, all passing deterministically in <10ms total, proving the new FP4_ULTRA paths and regression-covering that unrecognized formats (RGB8) keep their pre-existing bare-rejection behavior
- Verified via a real build: `SGProcessors`, `ProcessingBase`, and the new `mnn_tensor_fp4_test` target all compile cleanly against the live `W:\gnus\GeniusNetwork\SuperGenius\build\Windows\Release` build environment; `ctest -R MNNTensorFp4Test` passes (also re-ran alongside `QuantizationTest`/`DiffUtilsTest` with no regressions)

## Task Commits

All 3 task commits landed in the `SGProcessingManager` submodule (its own branch, `dev_rendering` -- see Deviations), followed by a submodule-pointer-bump commit in the outer `SuperGenius` repo (`dev_childwallet`):

**SGProcessingManager submodule (`dev_rendering`):**
1. **Task 1: Re-enable FP4_ULTRA in ProcessingManager's TENSOR schema validation** - `e644921` (feat)
2. **Task 2: Extend MNN_Tensor to recognize FP4_ULTRA with a structured, honest failure path** - `b5471e0` (feat)
3. **Task 3: Direct-processor unit test for MNN_Tensor's FP4_ULTRA path** - `133c463` (test)

**SuperGenius outer repo (`dev_childwallet`):**
- **Submodule pointer bump** - `0318ccf3` (chore) -- repoints the outer repo's `SGProcessingManager` gitlink at `133c463`

**Plan metadata (PLANNING_REPO, GNUS-NEO-SWARM):** committed separately after this summary (see final commit).

_No TDD RED/GREEN/REFACTOR sequence was applicable here in the strict per-task sense: the plan's own task breakdown separates schema-validation (Task 1), processor-behavior (Task 2), and test-authoring (Task 3) into distinct tasks, with Task 3's tests proving Tasks 1-2's `<behavior>` contracts after the fact rather than before. Plan frontmatter `type: execute` (not `type: tdd`), so the plan-level TDD gate does not apply._

## Files Created/Modified
- `SGProcessingManager/src/processingbase/ProcessingManager.cpp` (submodule) - Uncommented the `FP4_ULTRA` format-acceptance clause in the `DataType::TENSOR` validation case
- `SGProcessingManager/src/processors/processing_processor_mnn_tensor.cpp` (submodule) - Added an early-return branch for `InputFormat::FP4_ULTRA`: buffer-size validation, then a structured `FORMAT_UNSUPPORTED` `ProcessingError`
- `SGProcessingManager/test/CMakeLists.txt` (submodule) - Added `add_subdirectory(processors)`
- `SGProcessingManager/test/processors/CMakeLists.txt` (submodule, new) - New test target `mnn_tensor_fp4_test`, registered as ctest `MNNTensorFp4Test`
- `SGProcessingManager/test/processors/mnn_tensor_fp4_test.cpp` (submodule, new) - 3 GTest cases exercising `MNN_Tensor::StartProcessing()` directly

## Decisions Made
- **Buffer-size check arithmetic:** Used the generic fact that any 4-bit ("FP4") format packs 2 elements per byte (`ceil(width / 2)` minimum bytes) rather than any macroblock-specific layout, since RESEARCH.md's Pitfall 3 confirmed no FP4 Ultra wire-format spec file exists on disk and three incompatible "FP4" formats exist across the ecosystem. This is pure size arithmetic on the declared bit-width, not FP4 dequant math -- D-09 is unaffected.
- **Two distinct FORMAT_UNSUPPORTED messages:** the plan asked for the buffer-size-mismatch failure to be "distinct from the decode kernel unavailable message" -- implemented as two separate return points with different message text, both staged `FORMAT_UNSUPPORTED` (there is no more specific stage for "format valid but not yet decodable" in the current `ProcessingErrorStage` enum).
- **Test regression case for RGB8:** asserts `result.error.has_value()` is `false` (not `true`) for RGB8, matching the actual pre-existing code (`return ProcessingResult{};`, no `.error` ever set for genuinely-unsupported formats) -- this is a more precise assertion than the plan's slightly loose "still returns an error result too" phrasing, chosen because it's what the actual unmodified code does and most directly proves Task 2 didn't widen acceptance beyond FP4_ULTRA.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `git add`/`git commit` at the stated file paths failed -- SGProcessingManager is a nested submodule**
- **Found during:** Task 1, first commit attempt
- **Issue:** `git -C "W:\gnus\GeniusNetwork\SuperGenius" add SGProcessingManager/src/...` failed with `fatal: Pathspec '...' is in submodule 'SGProcessingManager'`. `SGProcessingManager` is itself a git submodule of the outer `SuperGenius` repo (confirmed via `git submodule status`), currently checked out on its own branch `dev_rendering` -- distinct from the outer repo's `dev_childwallet`. This structural detail was not called out in the plan's `<cross_repo>` framing (which described CODE_REPO as a single repo on `dev_childwallet`).
- **Fix:** Committed each task's file changes inside the `SGProcessingManager` submodule directory directly (its own git repo, already on `dev_rendering` -- not switched, that was its pre-existing state), then added one additional submodule-pointer-bump commit in the outer `SuperGenius` repo on `dev_childwallet` so the outer repo's gitlink points at the new submodule commit. This is the standard, correct git-submodule workflow for landing changes that live inside a submodule while keeping the outer repo's branch as the "current branch, no switching" per the sequential-execution instructions.
- **Files modified:** None beyond the plan's own scope -- this only changed *where* commits were made, not what was changed.
- **Verification:** `git -C SuperGenius diff -- SGProcessingManager` showed the expected gitlink SHA change before committing; `git log` in both repos confirms all 4 commits (3 task + 1 bump) are present and reachable.
- **Committed in:** `e644921`, `b5471e0`, `133c463` (submodule, per-task), `0318ccf3` (outer repo, pointer bump)

**2. [Rule 1 - Bug] Acceptance criteria's expected `git grep` count of 2 for Task 1 did not match reality (1 actual match)**
- **Found during:** Task 1 verification
- **Issue:** Task 1's `acceptance_criteria` stated `git grep -c "InputFormat::FP4_ULTRA" ProcessingManager.cpp` should return 2 ("the now-active format check plus any other FP4_ULTRA reference in this file"). The file's only other `FP4_ULTRA` occurrence (line 1430) is a bare string literal `"FP4_ULTRA"` inside a `formatNames[]` array, not qualified as `sgns::InputFormat::FP4_ULTRA` -- so the qualified-name grep pattern only ever matches once (line 894, the new live clause).
- **Fix:** No code fix needed -- this was a documentation/estimation error in the plan's acceptance criteria, not a functional gap. Verified correctness via the plan's own `<verify>` automated command instead (`! grep -q "format != sgns::InputFormat::FP4_ULTRA\*/"`), which is the authoritative check and passed.
- **Files modified:** None.
- **Verification:** `<verify>` command ran and printed `VERIFY PASS`; separately confirmed via direct `Grep` tool that exactly 1 qualified `InputFormat::FP4_ULTRA` reference exists post-edit.
- **Committed in:** `e644921` (Task 1 commit, no additional fix commit needed)

---

**Total deviations:** 2 auto-fixed (1 blocking/structural, 1 bug/documentation-mismatch)
**Impact on plan:** Neither deviation changed the scope or shape of the plan's intended code changes. Deviation 1 changed *where* git commands were run (submodule vs. outer repo) to correctly land the same file edits; deviation 2 was a pre-existing estimation slip in the plan text, resolved by trusting the plan's own functional `<verify>` command over its acceptance-criteria count. No scope creep.

## Issues Encountered
None beyond the two deviations documented above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- PROC-02's plumbing is complete and tested: FP4_ULTRA-formatted TENSOR jobs pass schema validation and reach `MNN_Tensor`, which gives them an honest, structured, non-crashing failure path.
- Future work (a separate phase, per D-04) that merges MNN_Ultra's E2M1 decode kernel only needs to change the single early-return branch added in Task 2 (replace the "decode unavailable" `ProcessingError` with an actual call into MNN's decode API) -- the validation, dispatch, and error-handling contract shipped in this plan is already correct and test-covered.
- No blockers for subsequent Phase 4 plans (PROC-01 MNN LLM processor, CMake relink, bridge fixes) -- this plan's scope was fully self-contained to the two files + new test directory it touched.

---
*Phase: 04-sgprocessing-integration*
*Completed: 2026-08-18*

## Self-Check: PASSED

- FOUND: `04-02-SUMMARY.md` (this file)
- FOUND: `e644921` (SGProcessingManager submodule, `dev_rendering`)
- FOUND: `b5471e0` (SGProcessingManager submodule, `dev_rendering`)
- FOUND: `133c463` (SGProcessingManager submodule, `dev_rendering`)
- FOUND: `0318ccf3` (SuperGenius outer repo, `dev_childwallet`)
- FOUND: `SGProcessingManager/test/processors/mnn_tensor_fp4_test.cpp`
