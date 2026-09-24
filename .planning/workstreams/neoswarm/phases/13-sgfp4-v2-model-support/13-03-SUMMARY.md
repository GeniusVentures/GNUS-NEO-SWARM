---
phase: 13-sgfp4-v2-model-support
plan: 03
subsystem: testing
tags: [dead-code-removal, nf4, cmake, gtest, schema-contract, fp4-ultra]

requires:
  - phase: 4-sgprocessing-integration
    provides: "BuildSchemaJson FP4_ULTRA -> type=tensor/format=FP4_ULTRA contract and the 04-04 removal of fp4_codec's only consumer"
provides:
  - "NEO-SWARM free of the orphaned NF4 fp4_codec implementation, test, and CMake entries (SGF-03)"
  - "SGConnectivity.BuildSchemaJsonFP4UltraFormatEmitsFP4Type asserting the real schema contract (SGF-04b)"
affects: [13-02 (E2E fixture plan — clean slate), neoswarm_core consumers]

tech-stack:
  added: []
  patterns: ["Canonical-assertion mirroring: connectivity schema test now byte-mirrors test_sgprocessing_pipeline.cpp's BuildSchemaJson_Fp4Ultra"]

key-files:
  created: []
  modified:
    - "src/core/CMakeLists.txt"
    - "test/CMakeLists.txt"
    - "test/integration/test_sg_connectivity.cpp"
  deleted:
    - "src/core/fp4/fp4_codec.hpp"
    - "src/core/fp4/fp4_codec.cpp"
    - "test/core/test_fp4_codec.cpp"

key-decisions:
  - "Deleted fp4_codec outright per Research Finding 7 (self-contained: zero non-owning references after 04-04) rather than keeping it behind a CMake option"
  - "Schema assertion mirrors the pipeline test exactly (type present, format present, lowercase literal absent) instead of inventing a third variant"

patterns-established: []

requirements-completed: [SGF-03, SGF-04]

coverage:
  - id: D1
    description: "Orphaned NF4 fp4_codec implementation, unit test, and both owning CMake entries removed with zero residual references"
    requirement: SGF-03
    verification:
      - kind: command
        ref: "git grep -n 'fp4_codec|FP4Codec' -- src test (exit 1 = no matches)"
        status: pass
      - kind: command
        ref: "cmake --build build-tree --target neoswarm_core test_sg_connectivity (exit 0, no errors)"
        status: pass
    human_judgment: false
  - id: D2
    description: "FP4_ULTRA connectivity regression asserts real schema contract: type=tensor present, format=FP4_ULTRA present, lowercase fp4_ultra absent"
    requirement: SGF-04
    verification:
      - kind: integration
        ref: "test/integration/test_sg_connectivity.cpp#SGConnectivity.BuildSchemaJsonFP4UltraFormatEmitsFP4Type (RED: stale inverse assertion failed; GREEN: pass)"
        status: pass
      - kind: integration
        ref: "test_sg_connectivity.exe full suite 8/8 passed"
        status: pass
    human_judgment: false

duration: 14min
completed: 2026-09-02
status: complete
---

# Phase 13 Plan 03: NF4 Dead-Code Removal + Stale Schema Test Fix Summary

**Deleted the orphaned NF4 fp4_codec (458 lines across 3 files + 2 CMake entries) and flipped the stale FP4_ULTRA connectivity assertion from the inverse of the real contract to a mirror of the canonical pipeline assertions.**

## Performance

- **Duration:** ~14 min
- **Started:** 2026-09-02T22:59Z
- **Completed:** 2026-09-02T23:05Z
- **Tasks:** 2
- **Files:** 3 deleted, 3 modified

## Accomplishments

- SGF-03: removed `src/core/fp4/fp4_codec.{hpp,cpp}` and `test/core/test_fp4_codec.cpp` (the header carried its own Phase-4-D-13 orphan flag since 04-04 removed `MNNInferenceEngine`'s reference); dropped the `fp4/fp4_codec.cpp` source-list entry and the `neoswarm_test(test_fp4_codec ...)` target. `git grep fp4_codec|FP4Codec -- src test` returns nothing.
- SGF-04b: rewrote `SGConnectivity.BuildSchemaJsonFP4UltraFormatEmitsFP4Type` — RED first (the stale lowercase-literal assertion failed against the real schema, `npos vs npos`), then GREEN with the three canonical assertions (`"type":"tensor"` present, `"format":"FP4_ULTRA"` present, `fp4_ultra` absent).
- Build gate: `neoswarm_core` + `test_sg_connectivity` build clean from the workspace root tree; full `test_sg_connectivity` suite passes 8/8.

## Task Commits

1. **Task 1** - `ac20e27` (refactor: delete orphaned NF4 fp4_codec + CMake entries)
2. **Task 2 RED** - `9d8c89b` (test: RED evidence — stale assertion is the inverse of the real contract)
3. **Task 2 GREEN** - `c06e8f5` (test: fix stale FP4_ULTRA schema assertion to mirror canonical contract)

## Files Created/Modified

- `src/core/CMakeLists.txt` — `neoswarm_core` source list without `fp4/fp4_codec.cpp`
- `test/CMakeLists.txt` — `test_fp4_codec` target removed
- `test/integration/test_sg_connectivity.cpp` — canonical FP4_ULTRA schema assertions

## Decisions Made

- Straight deletion (no deprecation shim) — Research Finding 7 verified zero non-owning references, and the file header itself flagged the class as a removal candidate since Phase 4.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Build-tree discovery: the plan's verify commands assume `build/Windows/Release` inside GNUS-NEO-SWARM, but that path holds only an incomplete Ninja configure stub; the actual configured tree (VS2022) is the workspace root `W:\gnus\GeniusCognitiveSystem\build\Windows\Release`, which adds GNUS-NEO-SWARM via `cmake/CommonBuildParameters.cmake` line 498. Builds/tests were run there. 13-02 should use the same tree.
- ctest registration: `ctest -N` in the root tree reports "Total Tests: 0" (tests are registered per-subdirectory in this layout), so GTest binaries were executed directly — equivalent verification.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Wave 2 (13-02) unblocked: depends_on [13-01 ✓, 13-03 ✓].
- Fresh SuperGenius libs (13-01) + clean NEO-SWARM core are in place; use the workspace-root build tree for 13-02's new integration tests.

## Self-Check: PASSED

---
*Phase: 13-sgfp4-v2-model-support*
*Completed: 2026-09-02*
