---
phase: 04-sgprocessing-integration
plan: 04
subsystem: infra
tags: [cpp, mnn, fp4, cleanup, gtest, vulkan]

# Dependency graph
requires:
  - phase: 04-sgprocessing-integration
    provides: "neoswarm_core CMake link path + SGProcessingBridge fixes (04-01); MNN_Llm processor / DataType::LLM (04-03)"
provides:
  - "MNNInferenceEngine with only the two supported inference paths (InferViaSGProcessing, InferViaMnnLlm) plus stub mode -- the hand-rolled raw-MNN sampling loop is gone"
  - "fp4::FP4Codec no longer referenced from MNNInferenceEngine (orphaned member removed per D-13)"
  - "SGProcessingPipeline.Fp4UltraFormat_DispatchesToTensorProcessor / SGProcessingPipeline.LlmDataType_JobReachesRegisteredProcessor -- new integration test cases, Vulkan-deadlock-skip-gated"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Fail-closed 'interpreter' mode: when mnn_llm_ is null, Infer()/StreamInfer() return outcome::failure(Error::InferenceFailed) instead of falling through to a hidden equivalent path"

key-files:
  created: []
  modified:
    - src/core/engine/mnn_inference_engine.hpp
    - src/core/engine/mnn_inference_engine.cpp
    - src/core/fp4/fp4_codec.hpp
    - test/integration/test_sgprocessing_pipeline.cpp

key-decisions:
  - "Config::m_temperature/m_topP/m_topK/m_repetitionPenalty (public struct fields, only ever consumed by the now-deleted sampling loop) were left in place -- removing public struct fields is a larger surface change than this plan's deletion scope calls for, and no other code sets/reads them, so leaving them is harmless and matches CLAUDE.md's minimal-diff philosophy"
  - "fp4_codec.hpp/.cpp and the standalone test_fp4_codec target are left in place (not deleted), flagged with a D-13-citing Doxygen note, per the plan's explicit instruction that full-file removal is a separate, bigger decision"
  - "LlmDataType_JobReachesRegisteredProcessor builds its schema via SGProcessingBridge::BuildSchemaJson(FLOAT32) and string-patches the modelInput's \"type\" field to \"llm\", then calls ProcessingManager::Create() directly -- InputFormat has no LLM value and SGProcessingBridge has no LLM-specific schema-building support (out of this plan's scope to add), so this is the minimal way to exercise the same JSON-parse/registration-lookup path a real LLM job's schema would use"

patterns-established: []

requirements-completed: [PROC-01, PROC-02]

coverage:
  - id: D1
    description: "InferViaStandardInterpreter/RunForward/SampleToken/ApplyRepetitionPenalty are deleted; StreamInfer's hand-rolled fallback and LoadModel's orphaned single-file-.mnn branch are removed as a mechanical consequence; InferViaMnnLlm/InferViaSGProcessing remain byte-for-byte unchanged"
    requirement: "PROC-01"
    verification:
      - kind: other
        ref: "git grep -c \"InferViaStandardInterpreter|RunForward|SampleToken|ApplyRepetitionPenalty\" (0) and \"m_interpreter|m_session|SelectBackend\" (0) against src/core/engine/mnn_inference_engine.{hpp,cpp}; git diff confirms zero changes inside InferViaMnnLlm/InferViaSGProcessing bodies"
        status: pass
    human_judgment: false
  - id: D2
    description: "fp4::FP4Codec m_fp4Codec member and its (void) discard are removed from MNNInferenceEngine; fp4_codec.hpp/.cpp and test_fp4_codec remain untouched and flagged per D-13"
    requirement: "PROC-02"
    verification:
      - kind: other
        ref: "git grep -c \"fp4_codec|FP4Codec|m_fp4Codec\" src/core/engine/mnn_inference_engine.{hpp,cpp} (0); git grep -c fp4_codec.cpp src/core/CMakeLists.txt (1, untouched)"
        status: pass
    human_judgment: false
  - id: D3
    description: "New FP4_ULTRA/LLM integration test cases exist, correctly cite the VulkanInitMutex deadlock, and are skip-gated rather than hanging or silently omitted"
    requirement: "PROC-02"
    verification:
      - kind: unit
        ref: "test/integration/test_sgprocessing_pipeline.cpp#SGProcessingPipeline.Fp4UltraFormat_DispatchesToTensorProcessor, #SGProcessingPipeline.LlmDataType_JobReachesRegisteredProcessor"
        status: unknown
    human_judgment: true
    rationale: "Code-reviewed correct (mirrors the file's own established FloatModel_EndToEnd/TensorModel_EndToEnd GTest idiom, calls HasUsableVulkanDevice() before any ProcessingManager::Create() touch, cites the tracked sgproc-render Phase 18 bug by path), but could not be compiled/run in this environment -- the pre-existing, out-of-scope get_third_party_dir() thirdparty-extraction failure (documented by 04-01/04-03) blocks CMake configure before any target can build, on this exact checkout, independent of this plan's changes. A human (or a future agent in an environment with a resolved thirdparty build) must actually run ctest to empirically confirm both cases SKIP (on a real-Vulkan-device host) or pass (on a GPU-less host)."

duration: 40min
completed: 2026-08-18
status: complete
---

# Phase 4 Plan 04: SGProcessing NEO-SWARM Cleanup + FP4_ULTRA/LLM Test Coverage Summary

**Deleted NEO-SWARM's hand-rolled ~150-line raw-MNN sampling loop and its orphaned call sites per D-06, removed the orphaned fp4_codec member per D-13, and added two Vulkan-deadlock-skip-gated integration test cases covering FP4_ULTRA and LLM job schemas.**

## Performance

- **Duration:** ~40 min
- **Completed:** 2026-08-18T22:20:24Z
- **Tasks:** 3/3 completed
- **Files modified:** 4

## Accomplishments
- Deleted `MNNInferenceEngine::InferViaStandardInterpreter()`, `RunForward()`, `SampleToken()`, and `ApplyRepetitionPenalty()` — the hand-rolled autoregressive sampling loop D-06 targets for removal (that capability now lives in SGProcessingManager's `MNN_Llm` processor, plan 04-03)
- `Infer()`'s "interpreter" branch and `StreamInfer()`'s hand-rolled fallback both now fail closed (`Error::InferenceFailed`) when no LLM model is loaded, instead of calling the deleted functions or falling through to a silently-equivalent hidden path
- `LoadModel()`'s "standard single-file .mnn model (non-LLM)" sub-path removed as a mechanical consequence (its only reader, `RunForward()`, no longer exists); the LLM-directory-detection sub-path (`mnn_llm_`) is completely unchanged
- Removed the now-fully-orphaned `m_interpreter`/`m_session` members and `SelectBackend()`, along with their now-unused `MNN::Interpreter`/`MNN::Session` forward declarations and `<MNN/Interpreter.hpp>`/`<MNN/MNNForwardType.h>`/`<MNN/Tensor.hpp>`/`<algorithm>`/`<random>`/`<cmath>` includes (all exclusively consumed by the deleted code)
- Verified via `git diff` that `InferViaMnnLlm` and `InferViaSGProcessing` are byte-for-byte unchanged
- Removed the confirmed-orphaned `fp4::FP4Codec m_fp4Codec` member and its `(void) m_fp4Codec;` discard from `MNNInferenceEngine` per D-13; left `fp4_codec.hpp`/`.cpp` and the standalone `test_fp4_codec` target in place, flagged with a Doxygen note citing D-13 as a candidate for removal/re-justification in a future phase
- Added `SGProcessingPipeline.Fp4UltraFormat_DispatchesToTensorProcessor` (submits an FP4_ULTRA job via the existing `tensor_tiny.mnn` fixture) and `SGProcessingPipeline.LlmDataType_JobReachesRegisteredProcessor` (patches a FLOAT32 schema's type field to `"llm"` and calls `ProcessingManager::Create()` directly), both gated by `HasUsableVulkanDevice()` with an explicit `GTEST_SKIP()` message citing the tracked, out-of-scope sgproc-render Phase 18 `VulkanInitMutex` re-entrancy deadlock

## Task Commits

Each task was committed atomically:

1. **Task 1: Delete duplicate raw-MNN sampling loop and its now-orphaned call sites** - `5e3959d` (fix)
2. **Task 2: Remove orphaned fp4_codec member per D-13** - `8ee7fa4` (fix)
3. **Task 3: Add Vulkan-deadlock-documented FP4_ULTRA/LLM integration test cases** - `539427c` (test)

**Plan metadata:** this SUMMARY.md and STATE/ROADMAP/REQUIREMENTS updates are owned centrally by the orchestrator per the execution instructions for this plan — not committed by this executor.

## Files Created/Modified
- `src/core/engine/mnn_inference_engine.hpp` - Removed `InferViaStandardInterpreter`/`SelectBackend`/`RunForward`/`SampleToken`/`ApplyRepetitionPenalty` declarations, `m_interpreter`/`m_session`/`m_fp4Codec` members, the `fp4_codec.hpp` include, and now-unused `MNN::Interpreter`/`MNN::Session` forward declarations; updated class/file-level doc comments to reflect "interpreter" mode's actual (LLM-only) scope
- `src/core/engine/mnn_inference_engine.cpp` - Deleted the four sampling-loop functions and the `LoadModel()` standard-single-file-.mnn sub-path; `Infer()`/`StreamInfer()` fail closed instead of calling the deleted code; destructor no longer cleans up `m_interpreter`/`m_session`; constructor no longer discards `m_fp4Codec`; removed now-unused includes
- `src/core/fp4/fp4_codec.hpp` - Added a Doxygen `@note` flagging the class per D-13 as orphaned/predating MNN_Ultra's E2M1 target format
- `test/integration/test_sgprocessing_pipeline.cpp` - Added `#include <processingbase/ProcessingManager.hpp>` and `#include <processors/vulkan_gpu_probe.hpp>`, plus the two new Vulkan-skip-gated test cases

## Decisions Made
See `key-decisions` in frontmatter. Summary: (1) left `MNNInferenceEngine::Config`'s now-unused sampling-parameter fields (`m_temperature`/`m_topP`/`m_topK`/`m_repetitionPenalty`) in place as harmless, out-of-scope public-struct cleanup; (2) left `fp4_codec.hpp`/`.cpp` and its own test target in place per the plan's explicit instruction, only removing the one confirmed-orphaned reference; (3) built the LLM test's schema via a string-patch of the existing FLOAT32 `BuildSchemaJson()` path rather than adding new LLM-specific schema-building support to `SGProcessingBridge` (out of this plan's scope).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Task 1's `StreamInfer` fallback-replacement comment contained the literal deleted function names, failing its own acceptance-criteria grep**
- **Found during:** Task 1, post-edit acceptance-criteria verification
- **Issue:** The plan's acceptance criteria requires `git grep -c "InferViaStandardInterpreter|RunForward|SampleToken|ApplyRepetitionPenalty" ...` to return 0, but an explanatory code comment I wrote in `StreamInfer()` named those three deleted functions parenthetically, causing a false-positive match.
- **Fix:** Reworded the comment to describe the removed logic ("hand-rolled raw-MNN token-generation-loop fallback") without naming the deleted symbols literally.
- **Files modified:** `src/core/engine/mnn_inference_engine.cpp`
- **Verification:** `git grep -c "InferViaStandardInterpreter|RunForward|SampleToken|ApplyRepetitionPenalty" src/core/engine/mnn_inference_engine.{hpp,cpp}` now returns 0 for both files.
- **Committed in:** `5e3959d` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking, self-inflicted by my own comment wording — not a pre-existing plan defect)
**Impact on plan:** None on scope — purely a wording fix to satisfy the plan's own literal grep-based acceptance criteria.

## Issues Encountered

**Full CMake configure/build verification could not be executed in this environment** — the exact same pre-existing, out-of-scope blocker independently confirmed by plans 04-01 and 04-03: `cmake -S build/Windows -B build/Windows/Release -DCMAKE_BUILD_TYPE=Release` fails with `CMake Error ... Failed to extract thirdparty archive`, originating from `build/CommonCompilerOptions.cmake:237` via `get_third_party_dir()`'s sibling-walk-up (`build/cmake/functions.cmake`), which structurally cannot reach `GeniusNetwork/thirdparty` post-app-restructure. This occurs before any of this phase's SGProcessingManager code is ever reached, confirmed identical with or without this plan's changes.

I re-ran the exact configure command myself in this session (rather than assuming the blocker was still present, per this plan's environment instructions) and reproduced the identical failure, confirming it has not been resolved since 04-01/04-03.

As a result:
- Task 1/2's acceptance criteria (`git grep` checks for deleted symbols) were run directly and pass; `InferViaMnnLlm`/`InferViaSGProcessing` were confirmed byte-for-byte unchanged via `git diff` (zero lines touched inside either function body).
- Task 3's new test cases were verified by careful manual code review against the plan's exact specified pattern (mirrors `FloatModel_EndToEnd`/`TensorModel_EndToEnd`'s structure; `HasUsableVulkanDevice()` is called before any `ProcessingManager`-touching code in both new cases, matching the file's own established skip-idiom) — but the `test_sgprocessing_pipeline` binary itself could not be compiled/run to empirically confirm the SKIP behavior on this machine.
- This is a standalone, environment-wide concern (not introduced by, or specific to, this plan) that should be resolved before any of this phase's plans' test coverage can be empirically verified end-to-end.

**Fixture-data note (not a code issue):** `Fp4UltraFormat_DispatchesToTensorProcessor` reuses `tensor_tiny.mnn`/`tensor_input.raw` — a FLOAT32 model and raw FLOAT32 input bytes, not an actual FP4_ULTRA-encoded blob, since no such fixture exists in this repo (the same gap plans 04-02/04-03 already documented for FP4_ULTRA/LLM test data). This test therefore exercises the FP4_ULTRA format tag's dispatch/validation path (D-10/D-13's "wire + stub" scope), not a real FP4 decode round-trip — consistent with D-09's dequant-math-is-MNN's-job scope, and with D-08's explicit "ship what's ready" framing for this phase.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- All three of this plan's `must_haves` truths are satisfied by code inspection: the hand-rolled sampling loop is fully deleted with zero dangling references anywhere in the repo (`git grep` confirms); `InferViaMnnLlm`/`InferViaSGProcessing` are unchanged; the orphaned `fp4_codec` member is gone from `MNNInferenceEngine`; the two new test cases exist and correctly document the Vulkan deadlock as a known, skip-gated blocker.
- **Blocker for empirical verification (not this plan's to fix, and not new):** the pre-existing `get_third_party_dir()` thirdparty-resolution issue will block ANY actual build/test run in this checkout — including this plan's own changes — until a separate, dedicated fix lands. This has now been independently reproduced by three consecutive Phase 4 plans (04-01, 04-03, 04-04) and should be escalated as a standalone, high-priority concern before any further Phase 4 (or later-phase) work attempts real build verification in this environment.
- The `VulkanInitMutex` re-entrancy deadlock (sgproc-render Phase 18, tracked upstream in GeniusNetwork) will separately gate real execution (as opposed to SKIP) of this plan's two new test cases on this exact Windows machine once the build blocker above is resolved.
- This plan completes Phase 4's NEO-SWARM-side cleanup scope (PROC-01/PROC-02 consolidation directives D-06/D-13). No further NEO-SWARM-side deletions are outstanding from this phase's `must_haves`.

## Self-Check: PASSED

- FOUND: `src/core/engine/mnn_inference_engine.hpp`
- FOUND: `src/core/engine/mnn_inference_engine.cpp`
- FOUND: `src/core/fp4/fp4_codec.hpp`
- FOUND: `test/integration/test_sgprocessing_pipeline.cpp`
- FOUND: `5e3959d`
- FOUND: `8ee7fa4`
- FOUND: `539427c`

---
*Phase: 04-sgprocessing-integration*
*Completed: 2026-08-18*
