---
phase: 04-sgprocessing-integration
plan: 03
subsystem: infra
tags: [cpp, sgprocessingmanager, mnn, llm, cmake, cross-repo, gtest]

# Dependency graph
requires:
  - phase: 04-sgprocessing-integration
    provides: "FP4_ULTRA TENSOR schema validation + direct-processor GTest pattern (04-02)"
provides:
  - "DataType::LLM -- new, additive enum value with json round-trip (from_json/to_json)"
  - "sgns::sgprocessing::MNN_Llm -- new autoregressive LLM text-generation processor, calling MNN::Transformer::Llm's native API (createLLM/load/response/destroy), not a hand-rolled sampling loop"
  - "ProcessingManager::Init() registers MNN_Llm under DataType::LLM (guarded -- see Deviations)"
  - "Configure-time detection (SGPROC_HAS_MNN_LLM) of whether the vendored MNN static library was built with MNN_BUILD_LLM=ON -- new precedent for gating an MNN sub-feature that isn't universally compiled into every checkout"
affects: [poc, sgproc-render]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Forward-declare MNN::Transformer::Llm in the processor header (mirroring GNUS-NEO-SWARM's own mnn_inference_engine.hpp) so only the .cpp translation unit needs the real MNN LLM header -- keeps ProcessingManager.hpp/.cpp's own compile-time dependency on MNN_Llm limited to the class name, not its MNN internals"
    - "CMake configure-time feature detection (EXISTS check against MNN_INCLUDE_DIR) + a CACHE INTERNAL variable + two narrowly-scoped #ifdef guards (ProcessingManager.hpp's include, ProcessingManager.cpp's one registration line) -- used when an MNN sub-feature (here: MNN_BUILD_LLM) is not universally present across checkouts of the shared vendored MNN build, to keep the whole SGProcessors target linkable everywhere without gating unrelated code"

key-files:
  created:
    - "SGProcessingManager/include/processors/processing_processor_mnn_llm.hpp"
    - "SGProcessingManager/src/processors/processing_processor_mnn_llm.cpp"
    - "SGProcessingManager/test/processors/mnn_llm_test.cpp"
  modified:
    - "SGProcessingManager/generated/DataType.hpp"
    - "SGProcessingManager/generated/Generators.hpp"
    - "SGProcessingManager/include/processingbase/ProcessingManager.hpp"
    - "SGProcessingManager/src/processingbase/ProcessingManager.cpp"
    - "SGProcessingManager/src/processors/CMakeLists.txt"
    - "SGProcessingManager/test/processors/CMakeLists.txt"
    - "SGProcessingManager/test/processors/mnn_tensor_fp4_test.cpp"

key-decisions:
  - "The vendored MNN static library this build links (MNN::MNN, resolved from GeniusNetwork/thirdparty/build/Windows/Release/MNN) was confirmed, by direct inspection of its installed include tree, to have been built with MNN_BUILD_LLM=OFF (MNN's own CMake option, default OFF) -- there is no MNN/llm/ subdirectory anywhere in it, and no llm-related CMake cache entries at all. This means MNN::Transformer::Llm's API genuinely does not exist to link against in this checkout, independent of any code written in this plan."
  - "Rather than either (a) leaving the shared SGProcessingManager submodule branch (dev_rendering, which other concurrent workstreams -- sgproc-render Phases 17-19 -- also build against) broken/unlinkable, or (b) silently attempting a full MNN rebuild with MNN_BUILD_LLM=ON (a large, slow, cross-cutting, out-of-scope infrastructure change with no Windows-native build script and high risk of destabilizing the shared thirdparty build), this plan added a narrow CMake configure-time feature-detection guard (SGPROC_HAS_MNN_LLM) that conditionally compiles processing_processor_mnn_llm.cpp into SGProcessors and conditionally registers/includes MNN_Llm in ProcessingManager.hpp/.cpp. The processor's own .cpp/.hpp files contain zero #ifdefs -- the guard is confined to exactly 3 places (2 CMakeLists.txt files' EXISTS checks, and 2 #ifdef blocks in ProcessingManager.hpp/.cpp) and activates automatically, with zero further code changes needed, the moment a future checkout's MNN is rebuilt with MNN_BUILD_LLM=ON."
  - "MNN::Transformer::Llm::createLLM() requires a directory path (it expects llm_config.json + weight files on disk), unlike every other MNN processor in this codebase which uses MNN::Interpreter::createFromBuffer's in-memory API. No existing materialize-buffer-to-disk mechanism was found anywhere in SGProcessingManager (the plan's own read_first pointer to 'GetCidForProc/FileManager' materializing to disk does not describe anything that actually exists -- GetCidForProc resolves model bytes into in-memory buffers only). A new, minimal MaterializeModelToTempDir() helper was added, scoped to this processor only."
  - "Cancellation is checked as the very first statement in StartProcessing() (ahead of even the empty-modelFile check), not only after a successful load as the plan's Task 3 action literally sequenced it. This is a Rule 1 fix (see Deviations) needed both for correctness (avoid wasted materialize/load work on an already-cancelled job) and to make the CANCELLED path deterministically unit-testable without a real MNN LLM model fixture."

patterns-established:
  - "MNN sub-feature configure-time gating: when a vendored thirdparty library exposes an optional sub-component (here, MNN's MNN_BUILD_LLM) that isn't guaranteed present in every checkout of a shared build, detect it via a CMake EXISTS/find_path check against the resolved include directory, expose the result as a CACHE INTERNAL variable so sibling subdirectories (e.g. test/processors/) can read it without directory-scope propagation gymnastics, and confine any resulting #ifdef guards in source files to the minimum needed to keep symbols resolvable (an include line and a single factory-registration line here) -- never gate the feature's own implementation file internally."

requirements-completed: [PROC-01]

coverage:
  - id: D1
    description: "DataType::LLM is a new, additive enum value with a working json round-trip (from_json/to_json), with no regression to any pre-existing DataType's mapping"
    requirement: "PROC-01"
    verification:
      - kind: unit
        ref: "SGProcessingManager/test/processors/mnn_tensor_fp4_test.cpp#MnnTensorFp4Test.DataTypeLlmJsonRoundTrip"
        status: pass
    human_judgment: false
  - id: D2
    description: "MNN_Llm processor implements the 6-arg StartProcessing() interface, ports MNN::Transformer::Llm's native createLLM()/load()/response() API (not a hand-rolled sampling loop), takes VulkanInitMutex() around model load, and registers PushTeardown() for its MNN LLM object"
    requirement: "PROC-01"
    verification:
      - kind: unit
        ref: "SGProcessingManager/test/processors/mnn_llm_test.cpp#MnnLlmTest.EmptyModelFileFailsClosedWithResourceResolution"
        status: unknown
      - kind: unit
        ref: "SGProcessingManager/test/processors/mnn_llm_test.cpp#MnnLlmTest.PreCancelledTokenFailsClosedWithCancelled"
        status: unknown
      - kind: other
        ref: "Manual code review + real build attempt: mnn_llm_test target could not be compiled/linked/run in this environment because the vendored MNN static library was built with MNN_BUILD_LLM=OFF (see Deviations) -- confirmed via `cmake --build . --target mnn_llm_test` failing with 'Project file does not exist' (the guard correctly excludes the target rather than failing to link)"
        status: unknown
    human_judgment: true
    rationale: "The tests exist, are believed correct by code review, and are wired to run automatically the instant a future checkout's MNN gains MNN_BUILD_LLM=ON support, but they have never actually executed in any environment available during this plan's execution -- there is no MNN build with LLM support reachable here to prove pass/fail. A human (or a future agent with access to an LLM-enabled MNN build) must actually run `ctest -R MNNLlmTest` before this can be marked verified."
  - id: D3
    description: "ProcessingManager::Init() registers MNN_Llm under DataType::LLM; the shared SGProcessingManager submodule branch (dev_rendering) continues to build and link cleanly for concurrent workstreams in checkouts without MNN_BUILD_LLM support"
    requirement: "PROC-01"
    verification:
      - kind: unit
        ref: "Real build: `cmake --build . --target SGProcessors --config Release` and `cmake --build . --target ProcessingBase --config Release` both succeed cleanly (zero new warnings) in this environment, with SGPROC_HAS_MNN_LLM correctly evaluating false"
        status: pass
      - kind: integration
        ref: "`ctest -C Release -R \"MNNTensorFp4Test|QuantizationTest|DiffUtilsTest|OutputHashingTest|processing_conformance\"`: 10/11 processing_conformance-suite tests + MNNTensorFp4Test pass; the sole failure (OutputHashingTest.ManifestDeterministicSerialization, 5909 vs 5649 byte manifest-size mismatch) is the pre-existing, out-of-scope sgproc-render Phase 16 issue documented in this plan's own environment context, confirmed unrelated (no manifest-size code was touched)"
        status: pass
    human_judgment: false

duration: ~55min
completed: 2026-08-18
status: complete
---

# Phase 4 Plan 3: MNN LLM Autoregressive Text-Generation Processor Summary

**Added `sgns::sgprocessing::MNN_Llm`, a new SGProcessingManager processor that ports MNN's native `MNN::Transformer::Llm::createLLM()/load()/response()` API (not a hand-rolled sampling loop) behind a new, additive `DataType::LLM` dispatch key -- gated by a new CMake configure-time feature-detection guard, because the vendored MNN static library this checkout links was confirmed built with `MNN_BUILD_LLM=OFF`.**

## Performance

- **Duration:** ~55 min
- **Completed:** 2026-08-18T18:07:02-04:00
- **Tasks:** 4/4 completed
- **Files modified:** 10 (2 generated enum/json files, 2 new processor files, 2 ProcessingManager files, 3 CMakeLists.txt files, 1 new/1 edited test file)

## Accomplishments
- `DataType::LLM` added as a new, purely additive enum value (`generated/DataType.hpp`, alphabetically between `INT` and `MAT2`) with matching `from_json`/`to_json` entries in `generated/Generators.hpp` -- verified via a real, passing GTest round-trip (`MnnTensorFp4Test.DataTypeLlmJsonRoundTrip`)
- New `MNN_Llm` processor class (`include/processors/processing_processor_mnn_llm.hpp`, `src/processors/processing_processor_mnn_llm.cpp`) implementing the current 6-arg `ProcessingProcessor::StartProcessing()` interface: materializes the job's model buffer to a fresh temp directory (a new, minimal helper -- no existing materialize-to-disk mechanism was found elsewhere in this codebase), calls `MNN::Transformer::Llm::createLLM()`/`load()` under `VulkanInitMutex()`, registers teardown via `PushTeardown()`, checks `execCtx.cancelToken` before any work begins, calls `llm->response()` bounded by a schema-declared `maxNewTokens` parameter (default 512), fires `ProgressEvent::ForMNN` at each `MNNStage` boundary, and populates `ProcessingResult.hash`/`.output_buffers` via the same SHA256/output-buffer pattern `MNN_String` already uses
- `ProcessingManager::Init()` registers `MNN_Llm` under `DataType::LLM`, following the codebase's exact one-line-per-`DataType` registration style
- **Critical, previously-undocumented environment finding:** the vendored MNN static library this checkout's SGProcessingManager build actually links (`GeniusNetwork/thirdparty/build/Windows/Release/MNN`) was confirmed, by direct inspection of its installed include tree and CMake cache, to have been built with `MNN_BUILD_LLM=OFF` (MNN's own CMake option, default `OFF`) -- there is no `MNN/llm/` subdirectory or LLM-related library anywhere in it. `MNN::Transformer::Llm` genuinely does not exist to compile/link against in this environment, independent of any code correctness. This is a *new* discovery, distinct from RESEARCH.md's already-known `VulkanInitMutex` deadlock (Pitfall 4) and D-04's MNN_Ultra-completeness gate.
- Added a new CMake configure-time feature-detection guard (`SGPROC_HAS_MNN_LLM`, `CACHE INTERNAL`) so this discovery doesn't break the shared `SGProcessingManager` submodule branch (`dev_rendering`) for concurrent workstreams (`sgproc-render` Phases 17-19 build against this exact branch): `processing_processor_mnn_llm.cpp` is only added to `SGProcessors`'s sources, and `MNN_Llm`'s registration/include in `ProcessingManager.hpp`/`.cpp` only compiled in, when `MNN_INCLUDE_DIR/MNN/llm/llm.hpp` actually exists at configure time. The processor's own code has zero `#ifdef`s.
- New `test/processors/mnn_llm_test.cpp` (2 GTest cases: empty-model-buffer fails closed with `RESOURCE_RESOLUTION`, pre-cancelled token fails closed with `CANCELLED`) -- itself gated by `SGPROC_HAS_MNN_LLM` since `MNN_Llm::StartProcessing()` has no compiled definition anywhere without it
- Verified via real builds and test runs in this environment: `SGProcessors`, `ProcessingBase` both build cleanly (Release config) with the guard correctly evaluating false and excluding the new processor/test target; `mnn_tensor_fp4_test` (unconditional target, carries Task 1's round-trip test) builds and passes; broader `ctest` run across `processing_conformance_*`/`QuantizationTest`/`DiffUtilsTest`/`OutputHashingTest` shows no regressions beyond the single pre-documented, out-of-scope `OutputHashingTest.ManifestDeterministicSerialization` failure

## Task Commits

All 4 task commits landed in the `SGProcessingManager` submodule (its own branch, `dev_rendering` -- same convention plan 04-02 established), followed by a submodule-pointer-bump commit in the outer `SuperGenius` repo (`dev_childwallet`):

**SGProcessingManager submodule (`dev_rendering`):**
1. **Task 1: Add DataType::LLM enum value + JSON mapping** - `0618922` (feat)
2. **Task 2: MNN_Llm skeleton -- class scaffold, model materialization, fail-closed load path** - `d5be0be` (feat)
3. **Task 3: MNN_Llm generation loop, teardown/cancellation/progress/hash wiring, DataType::LLM registration** - `84eb2b6` (feat)
4. **Task 4: Direct-processor unit tests for MNN_Llm and DataType::LLM registration** - `507eec1` (test)

**SuperGenius outer repo (`dev_childwallet`):**
- **Submodule pointer bump** - `b88ab457` (chore) -- repoints the outer repo's `SGProcessingManager` gitlink at `507eec1`

**Plan metadata (PLANNING_REPO, GNUS-NEO-SWARM):** committed separately after this summary.

_No TDD RED/GREEN/REFACTOR sequence was applicable: plan frontmatter marks each task `tdd="true"` but the plan's own task breakdown separates enum/json (Task 1), skeleton/load-path (Task 2), generation/wiring (Task 3), and test-authoring (Task 4) into distinct tasks, with Task 4's tests proving Tasks 1-3's `<behavior>` contracts after the fact rather than before -- matching the same pattern plan 04-02 documented for this exact reason._

## Files Created/Modified
- `SGProcessingManager/generated/DataType.hpp` (submodule) - Added `LLM` to the `DataType` enum
- `SGProcessingManager/generated/Generators.hpp` (submodule) - Added `"llm"` string mapping to `from_json`/`to_json`
- `SGProcessingManager/include/processors/processing_processor_mnn_llm.hpp` (submodule, new) - `MNN_Llm` class declaration; forward-declares `MNN::Transformer::Llm`
- `SGProcessingManager/src/processors/processing_processor_mnn_llm.cpp` (submodule, new) - `MNN_Llm::StartProcessing()`/`LoadModel()` implementation
- `SGProcessingManager/src/processors/CMakeLists.txt` (submodule) - `SGPROC_HAS_MNN_LLM` configure-time detection; conditional source inclusion
- `SGProcessingManager/include/processingbase/ProcessingManager.hpp` (submodule) - Guarded include of the new processor header
- `SGProcessingManager/src/processingbase/ProcessingManager.cpp` (submodule) - Guarded `RegisterProcessorFactory(DataType::LLM, ...)` call
- `SGProcessingManager/test/processors/CMakeLists.txt` (submodule) - Guarded `mnn_llm_test` target
- `SGProcessingManager/test/processors/mnn_llm_test.cpp` (submodule, new) - 2 GTest cases for `MNN_Llm`'s fail-closed paths
- `SGProcessingManager/test/processors/mnn_tensor_fp4_test.cpp` (submodule) - Added `DataTypeLlmJsonRoundTrip` (Task 1's json mapping test; lives here since this target builds unconditionally)

## Decisions Made
See `key-decisions` in frontmatter for full detail. Summary: (1) confirmed the vendored MNN build lacks `MNN_BUILD_LLM` support in this checkout; (2) chose a narrow CMake feature-detection guard over either breaking the shared build or silently rebuilding MNN; (3) implemented a new, minimal model-materialize-to-disk helper since none existed; (4) moved the cancellation check to the very first line of `StartProcessing()` for both correctness and testability.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `MNN::Transformer::Llm`/`<MNN/llm/llm.hpp>` does not exist in this checkout's vendored MNN build**
- **Found during:** Task 2, first build attempt (before writing any code -- discovered via direct inspection of `GeniusNetwork/thirdparty/build/Windows/Release/MNN/include/MNN/`, which has no `llm/` subdirectory, and a CMakeCache/vcxproj trace confirming `MNN_INCLUDE_DIR` resolves there with no LLM-related library or cache entry anywhere)
- **Issue:** RESEARCH.md's and this plan's own read_first pointers assert `<MNN/llm/llm.hpp>` is "confirmed already used and building successfully in NEO-SWARM" -- this claim is false against the real, currently-linkable MNN build. NEO-SWARM's `mnn_inference_engine.cpp` includes this header but (per RESEARCH.md's own separate finding that NEO-SWARM's SGProcessingManager link currently resolves to "stub/headers-only mode") has apparently never actually been compiled against a real MNN library. Writing `processing_processor_mnn_llm.cpp` exactly as specified (unconditionally, with `#include <MNN/llm/llm.hpp>` and calls into `MNN::Transformer::Llm`) would break the `SGProcessors` static library's compilation -- and therefore the whole shared `SGProcessingManager` submodule branch (`dev_rendering`), which concurrent workstreams (`sgproc-render` Phases 17-19) also build against.
- **Fix:** Rebuilding MNN with `MNN_BUILD_LLM=ON` on Windows was evaluated and rejected as out of scope: MNN's own `build_lib.sh` has no Windows target at all (Android/iOS/HarmonyOS/Python only), meaning this checkout's Windows MNN build goes through a separate, unexplored top-level build pipeline; a full MNN reconfigure+rebuild is a large, slow (likely 30-90+ min), high-risk, cross-cutting infrastructure change affecting every consumer of the shared vendored MNN library, squarely outside this plan's "add a processor" scope and CLAUDE.md's minimal-diff principle. Instead: added a CMake configure-time `EXISTS` check (`MNN_INCLUDE_DIR/MNN/llm/llm.hpp`) exposed as a `CACHE INTERNAL SGPROC_HAS_MNN_LLM` variable, which conditionally (a) includes `processing_processor_mnn_llm.cpp` in `SGProcessors`'s source list, (b) includes `processing_processor_mnn_llm.hpp` and registers `MNN_Llm`'s factory in `ProcessingManager.hpp`/`.cpp` (guarded by 2 narrowly-scoped `#ifdef SGPROC_HAS_MNN_LLM` blocks -- the only `#ifdef`s introduced anywhere in this plan; `MNN_Llm`'s own implementation file has none), and (c) conditionally builds the `mnn_llm_test` target. In checkouts without LLM support (this one), `DataType::LLM` has no registered factory and falls back to `ProcessingManager`'s existing `Error::NO_PROCESSOR` path -- the same graceful-failure behavior every other unregistered `DataType` already has.
- **Files modified:** `src/processors/CMakeLists.txt`, `include/processingbase/ProcessingManager.hpp`, `src/processingbase/ProcessingManager.cpp`, `test/processors/CMakeLists.txt` (all beyond what the plan's own files_modified list anticipated for this reason)
- **Verification:** Real builds: `cmake .` (reconfigure) prints `MNN LLM engine headers NOT found under MNN_INCLUDE_DIR -- MNN_Llm processor (PROC-01) source is excluded from this build`; `cmake --build . --target SGProcessors --config Release` and `--target ProcessingBase --config Release` both succeed with zero new warnings; `cmake --build . --target mnn_llm_test --config Release` correctly fails with `Project file does not exist` (proving the target itself was never generated, not that it failed to build) -- confirming the guard, not a broken build, is what's excluding it.
- **Committed in:** `d5be0be` (Task 2), `84eb2b6` (Task 3), `507eec1` (Task 4)

**2. [Rule 1 - Bug] Cancellation check moved to the very first line of `StartProcessing()`**
- **Found during:** Task 4, while writing `mnn_llm_test.cpp`'s cancellation test
- **Issue:** Task 3's action text sequenced the cancellation check *after* a successful model load (step 3, following steps 1-2: load, register teardown). This makes the `CANCELLED` path untestable without a real, loadable MNN LLM model fixture -- none exists in this repo's test data (same gap plan 04-02 hit for FP4_ULTRA's decode path) -- and also means an already-cancelled job would still pay the cost of materializing the model buffer to disk and attempting a full `createLLM()`/`load()` call before being told it was cancelled.
- **Fix:** Added an unconditional `execCtx.cancelToken.IsCancelled()` check as the very first statement in `StartProcessing()`, ahead of even the empty-modelFile check. The original post-load cancellation check (Task 3's step 3) is retained as a second check, since `MNN::Transformer::Llm::response()` exposes no mid-generation cancellation hook and a cancellation racing with a load-in-progress should still be caught before generation begins.
- **Files modified:** `src/processors/processing_processor_mnn_llm.cpp`
- **Verification:** `mnn_llm_test.cpp`'s `PreCancelledTokenFailsClosedWithCancelled` test asserts `error->stage == CANCELLED` for a pre-cancelled token with an empty model buffer -- code-reviewed correct, but (per Deviation 1) never actually executed in this environment; see `coverage: D2`'s `human_judgment: true` rationale.
- **Committed in:** `507eec1` (Task 4)

**3. [Rule 1 - Bug] Task 1's acceptance-criteria `git grep` count did not match reality**
- **Found during:** Task 1 verification
- **Issue:** Task 1's `acceptance_criteria` expected `git grep -c "DataType::LLM" DataType.hpp Generators.hpp` to return "at least 3"; the actual result is 2 (`0` in `DataType.hpp`, since the enum declares the bare unqualified identifier `LLM`, not the qualified `DataType::LLM`; `2` in `Generators.hpp`'s `from_json`/`to_json` entries). Same category of estimation slip plan 04-02 documented for its own Task 1.
- **Fix:** No code fix needed -- verified correctness via the plan's own stated `<verify>` command (which uses the same `grep -c "DataType::LLM"` pattern and is the authoritative check) plus a real, passing GTest round-trip test, both of which confirm the enum/json mapping is genuinely correct regardless of the raw count estimate being off.
- **Files modified:** None.
- **Committed in:** `0618922` (Task 1 commit, no additional fix needed)

---

**Total deviations:** 3 auto-fixed (1 blocking/infrastructure-discovery, 2 bug/documentation-mismatch)
**Impact on plan:** Deviation 1 is the most significant finding of this plan -- it doesn't change what code was written (the `MNN_Llm` processor is implemented exactly as specified, calling MNN's real native API, no hand-rolled loop) but does mean this plan's PROC-01 deliverable is code-complete-but-not-yet-executable in any environment reachable during this session, pending a future MNN rebuild with LLM support. Deviations 2-3 are minor, non-scope-changing corrections. No scope creep: all fixes were required either for correctness (Deviation 2) or to avoid breaking the shared `dev_rendering` branch other concurrent workstreams depend on (Deviation 1).

## Issues Encountered
- **`_ITERATOR_DEBUG_LEVEL`/`RuntimeLibrary` mismatch when building test targets without `--config Release`:** `cmake --build . --target mnn_tensor_fp4_test` (no explicit config) defaults to Debug on this multi-config Visual Studio generator, but the vendored MNN/gtest static libs were only built Release -- resulting in ~554 `LNK2038` mismatches. Not a code issue; resolved by always passing `--config Release` (and `ctest -C Release`) explicitly, matching how the environment's actual Release build output is laid out. Documented here since the plan's own `<verify>` commands as literally written omit `--config`/`-C` and would hit this same mismatch verbatim if run as-is in this environment.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `DataType::LLM`'s enum/json plumbing and `ProcessingManager`'s guarded registration pattern are both real, tested, and merged -- any future phase that rebuilds the vendored MNN with `MNN_BUILD_LLM=ON` gets a fully working, registered `MNN_Llm` processor with zero additional SGProcessingManager-side code changes (the `#ifdef` guards flip on automatically the moment `MNN_INCLUDE_DIR/MNN/llm/llm.hpp` exists at configure time).
- **Blocker for full end-to-end verification of PROC-01 (not this plan's to fix):** the vendored MNN static library needs a rebuild with `MNN_BUILD_LLM=ON` before `mnn_llm_test`'s 2 GTest cases, or any real `MNN::Transformer::Llm`-backed generation, can actually execute anywhere. This is a distinct, newly-discovered gap from RESEARCH.md's already-known `VulkanInitMutex` deadlock (sgproc-render Phase 18) and D-04's MNN_Ultra-completeness question -- worth flagging to whoever owns the MNN thirdparty build pipeline (no Windows-native build script currently exists for it; `build_lib.sh` only covers Android/iOS/HarmonyOS/Python).
- No blockers for subsequent Phase 4 plans from this plan's own scope -- all 4 tasks' code changes are self-contained to the files listed above, and the shared `dev_rendering` submodule branch remains fully buildable/linkable for concurrent workstreams.

---
*Phase: 04-sgprocessing-integration*
*Completed: 2026-08-18*
