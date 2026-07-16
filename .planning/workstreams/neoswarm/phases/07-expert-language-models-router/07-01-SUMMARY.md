---
phase: 07-expert-language-models-router
plan: 01
subsystem: ai
tags: [elm, ielm, types, interface, cmake, c++17, neoswarm]

# Dependency graph
requires:
  - phase: 07-expert-language-models-router
    provides: "Context decisions D-05, D-08, D-09, D-12; analog patterns from ISpecialist and types.hpp"
provides:
  - "ELMRole enum (10 values: Planner=0 through Science=9)"
  - "ELMContext, ChainStep, ExecutionChain structs in common/types.hpp"
  - "ExecutionMode::ElmAssisted=3 execution mode"
  - "IELM abstract interface with 6 pure virtuals (GetName, GetRole, IsLoaded, Load, Process, GetConfidence)"
  - "neoswarm_elm CMake STATIC library target"
  - "PromptFeatures extensions: has_grounding_request_, has_formatting_request_"
affects:
  - "07-02 (RoleELM + DomainELM implement IELM)"
  - "07-03 (SpecialistAdapter, GroundingELM, ToolSupportELM)"
  - "07-04 (ELMChainBuilder uses types)"
  - "07-05 (ApiServer RunELMChain orchestration)"
  - "07-06 (ELM tests)"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "I-prefix abstract interface pattern (IELM modeled after ISpecialist)"
    - "enum class with uint8_t underlying type for extensible role system"
    - "m_-prefixed member naming throughout new structs"
    - "Doxygen @brief/@param/@return on all public interface methods"
    - "outcome::result<T> error propagation (no exceptions)"

key-files:
  created:
    - "src/elm/i_elm.hpp — IELM abstract interface (6 pure virtuals)"
    - "src/elm/CMakeLists.txt — neoswarm_elm STATIC library target"
    - "src/elm/elm_stub.cpp — Wave 1 CMake compilation stub (removed in Wave 2)"
  modified:
    - "src/common/types.hpp — ELMRole, ELMContext, ChainStep, ExecutionChain, ElmAssisted=3, PromptFeatures extensions"
    - "src/CMakeLists.txt — add_subdirectory for elm/"

key-decisions:
  - "IELM::Process takes (input, ELMContext) — not just input (D-05)"
  - "ExecutionChain is a flat ordered list (D-09); DAG extension reserved for Phase 9"
  - "ELM structs placed after KnowledgeFact in types.hpp (forward-reference issue with std::vector<KnowledgeFact>)"
  - "CMake empty STATIC library rejected — added elm_stub.cpp as compilation verification stub (removed in Wave 2)"

patterns-established:
  - "IELM interface: 6 pure virtuals with GetRole() between GetName() and IsLoaded()"
  - "ELMContext carries originalTask, lastOutput, stepConfidences, groundingFacts"
  - "ChainStep has optional domain field for domain ELM routing"
  - "ExecutionChain has m_reasoning and m_chainConfidence for transparency"

requirements-completed: [ELM-03, ELM-05, ELM-core]

# Metrics
duration: 5 min
completed: 2026-07-16
---

# Phase 7 Plan 01: ELM Core Types, Interface, and CMake Scaffolding Summary

**Foundation types (ELMRole, ELMContext, ChainStep, ExecutionChain), IELM swappable interface (modeled on ISpecialist), and neoswarm_elm CMake library for Wave 1 of the Expert Language Models + Router phase.**

## Performance

- **Duration:** 5 min
- **Started:** 2026-07-16T02:23:25Z
- **Completed:** 2026-07-16T02:28:30Z
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments

- `ELMRole` enum with 10 distinct values (Planner=0 through Science=9) in `common/types.hpp`
- `ExecutionMode::ElmAssisted=3` added for multi-step ELM chain execution
- `ELMContext` struct carrying original task, last output, step confidences, and grounding facts
- `ChainStep` + `ExecutionChain` flat-list chain representation with reasoning string
- `IELM` abstract interface with 6 pure virtuals including `GetRole()` and `Process(input, ELMContext)`
- `neoswarm_elm` CMake STATIC library target registered in the build system
- 16/17 existing tests pass with zero regressions (1 pre-existing GeniusSDK FFI failure unchanged)

## Task Commits

Each task was committed atomically:

1. **Task 1: add ELM types to common/types.hpp** — `4a414a0` (feat)
2. **Task 2: create IELM abstract interface** — `e57de82` (feat)
3. **Task 3: create elm CMake library + register in src/CMakeLists.txt** — `dab6271` (feat)

## Files Created/Modified

- `src/common/types.hpp` — Added ELMRole enum, ELMContext/ChainStep/ExecutionChain structs, ElmAssisted=3 mode, PromptFeatures grounding/formatting fields
- `src/elm/i_elm.hpp` — IELM abstract interface (6 pure virtuals, sgns::neoswarm::elm namespace)
- `src/elm/CMakeLists.txt` — neoswarm_elm STATIC library (PUBLIC link neoswarm_common)
- `src/elm/elm_stub.cpp` — Wave 1 compilation stub (removed in Wave 2 when real .cpp files arrive)
- `src/CMakeLists.txt` — Added `add_subdirectory` for `elm/`

## Decisions Made

- **IELM::Process signature:** Takes `(const std::string& input, const ELMContext& context)` per D-05 — context carries original task and prior step outputs for chain execution
- **Struct placement:** ELMContext/ChainStep/ExecutionChain placed after KnowledgeFact in types.hpp (not before NodeOutput as planned) because `std::vector<KnowledgeFact>` requires a complete type definition — the plan's forward-reference assumption was incorrect
- **CMake stub:** The plan expected empty STATIC libraries to work in CMake, but this CMake version requires at least one source file. Added `elm_stub.cpp` as a compile-check stub (will be removed in Wave 2 when real .cpp implementations arrive)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking] CMake rejected empty STATIC library**

- **Found during:** Task 3 (create elm CMake library)
- **Issue:** `add_library(neoswarm_elm STATIC)` with empty source list failed with "No SOURCES given to target". The plan stated "The empty STATIC library is valid CMake" — this CMake version (3.x on macOS) requires at least one source file.
- **Fix:** Created `src/elm/elm_stub.cpp` — a minimal compilation unit that includes `i_elm.hpp` and does a `sizeof(IELM)` check to verify the abstract interface compiles correctly. This file is documented to be removed in Wave 2.
- **Files modified:** `src/elm/CMakeLists.txt` (added elm_stub.cpp to source list), `src/elm/elm_stub.cpp` (new)
- **Verification:** `ninja neoswarm_elm` succeeds, `libneoswarm_elm.a` produced
- **Committed in:** `dab6271` (part of Task 3 commit)

**2. [Rule 1 — Bug] Plan acceptance criteria expected 2 `ELMContext` grep matches but only 1 exists**

- **Found during:** Task 2 (acceptance criteria check)
- **Issue:** Plan AC said `grep -c "ELMContext" src/elm/i_elm.hpp` should return 2 (one in include, one in Process). The `#include "common/types.hpp"` line does not contain the literal string "ELMContext", so grep finds only 1 occurrence (in the Process signature).
- **Fix:** This is a plan-documentation error, not a code bug. The single occurrence in `Process()` is correct and sufficient.
- **Files modified:** None (code is correct as written)
- **Verification:** The interface compiles and all 6 pure virtuals are correctly declared

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 bug)
**Impact on plan:** Both deviations were necessary to complete the plan. The CMake stub is a temporary workaround documented for removal in Wave 2. The grep count issue was a plan acceptance-criteria error with zero impact on correctness.

## Threat Flags

None — Wave 1 is data types and abstract interface only. No data flow, no user input processed, no trust boundaries crossed.

## Issues Encountered

- CMake empty STATIC library not supported (resolved with elm_stub.cpp — see deviation #1)
- `test_genius_elm_ffi` pre-existing failure (GeniusSDK ELM FFI, unrelated to these changes) — 16/17 tests pass, unchanged from baseline

## Known Stubs

- `src/elm/elm_stub.cpp` — Temporary compilation unit for CMake source requirement. Contains a dead-code `sizeof(IELM)` verification function. **Planned removal in Wave 2** when real `.cpp` ELM implementations are added to `neoswarm_elm`.

## Next Phase Readiness

- ELM types and interface are ready for Wave 2 implementation (07-02-PLAN.md: RoleELM + DomainELM)
- `IELM` interface provides the contract all concrete ELMs must implement
- `ELMContext` carries all required chain execution state
- `neoswarm_elm` library is linked and ready for source additions

---

*Phase: 07-expert-language-models-router*
*Completed: 2026-07-16*
