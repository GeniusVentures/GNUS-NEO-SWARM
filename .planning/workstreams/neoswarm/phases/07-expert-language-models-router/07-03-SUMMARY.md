---
phase: 07-expert-language-models-router
plan: 03
subsystem: elm
tags: [c++17, composition-adapter, knowledge-pipeline, stub-pattern, outcome-result, ielm]

# Dependency graph
requires:
  - phase: 07-01
    provides: "IELM interface, ELMRole/ELMContext types, neoswarm_elm CMake target"
provides:
  - "SpecialistAdapter — composition-based ISpecialist → IELM wrapper (D-06, D-07)"
  - "GroundingELM — 4-stage knowledge pipeline ELM: Retrieve→Inject→Infer→Validate (D-17)"
  - "ToolSupportELM — interface-conforming pass-through stub with confidence=0 (D-18)"
  - "Updated elm/CMakeLists.txt linking against neoswarm_knowledge + neoswarm_specialists"
affects: [07-05-api-server-integration, 10-tool-intermediary]

# Tech tracking
tech-stack:
  added: []
  patterns: ["composition-adapter (has-a ISpecialist, not inheritance)", "knowledge-pipeline-elm (Retrieve→Inject→Infer→Validate)", "stub-elm (pass-through with confidence=0)", "fail-close (return input unchanged on error)"]

key-files:
  created:
    - "src/elm/specialist_adapter.hpp"
    - "src/elm/specialist_adapter.cpp"
    - "src/elm/grounding_elm.hpp"
    - "src/elm/grounding_elm.cpp"
    - "src/elm/tool_support_elm.hpp"
    - "src/elm/tool_support_elm.cpp"
  modified:
    - "src/elm/CMakeLists.txt"

key-decisions:
  - "SpecialistAdapter is generic for any ISpecialist — no includes of concrete specialist headers (grammar_specialist, math_specialist)"
  - "ELMContext parameter is dropped when forwarding to ISpecialist::Process(string) per D-06 legacy mapping"
  - "GroundingELM::Process() pipeline stages use manual has_value() checks (not BOOST_OUTCOME_TRY) for graceful degradation at each stage"
  - "GroundingELM returns input unchanged with confidence=0.5f when Retrieve returns empty (not full inference — differs from RoleELM fallback)"
  - "ToolSupportELM is a minimal stub (~15 lines) with no engine dependency — real implementation deferred to Phase 10"

patterns-established:
  - "fail-close: all Process() methods return input unchanged on error, confidence=0"
  - "composition-adapter: specialist_adapter has-a ISpecialist (not is-a)"
  - "knowledge-pipeline: GroundingELM composes Retrieve+Inject+Infer+Validate in strict order"
  - "stub-elm: ToolSupportELM serves as interface placeholder for deferred implementation"

requirements-completed: [ELM-04, ELM-07, ELM-08]

# Metrics
duration: 193s
completed: 2026-07-17
---

# Phase 07 Plan 03: SpecialistAdapter, GroundingELM, and ToolSupportELM Summary

**SpecialistAdapter (composition-based ISpecialist→IELM), GroundingELM (4-stage knowledge pipeline: Retrieve→Inject→Infer→Validate), and ToolSupportELM (interface-conforming pass-through stub)**

## Performance

- **Duration:** 3 min 13 sec
- **Started:** 2026-07-17T12:56:39Z
- **Completed:** 2026-07-17T12:59:52Z
- **Tasks:** 4
- **Files created:** 6
- **Files modified:** 1

## Accomplishments
- SpecialistAdapter wraps any ISpecialist behind IELM via composition (has-a, not is-a) — drops ELMContext per D-06 legacy mapping
- GroundingELM implements 4-stage pipeline: Retrieve facts from Grokipedia → Inject into prompt → Infer via shared engine → Validate output against facts, adjusting confidence
- ToolSupportELM provides a minimal interface-conforming stub (pass-through with confidence=0, IsLoaded=false) for deferred Phase 10 implementation
- All 3 ELM .cpp files compile into libneoswarm_elm.a with zero warnings; 16/17 existing tests pass (1 pre-existing FFI failure unrelated)

## Task Commits

Each task was committed atomically:

1. **task 1: create SpecialistAdapter class** - `cb757da` (feat)
2. **task 2: create GroundingELM class** - `93f752b` (feat)
3. **task 3: create ToolSupportELM stub** - `36423e0` (feat)
4. **task 4: register new .cpp files in elm/CMakeLists.txt** - `fcc3841` (feat)

## Files Created/Modified
- `src/elm/specialist_adapter.hpp` - Composition-based adapter: ISpecialist → IELM, drops ELMContext
- `src/elm/specialist_adapter.cpp` - Delegates Process/Load/IsLoaded to wrapped ISpecialist, fail-close on null
- `src/elm/grounding_elm.hpp` - 4-stage knowledge pipeline ELM with shared engine + knowledge components
- `src/elm/grounding_elm.cpp` - Retrieve→Inject→Infer→Validate pipeline with graceful degradation
- `src/elm/tool_support_elm.hpp` - Minimal stub ELM, no engine dependency, always IsLoaded=false
- `src/elm/tool_support_elm.cpp` - Pass-through Process() with logged warning, confidence always 0.0f
- `src/elm/CMakeLists.txt` - Added 3 new sources + neoswarm_knowledge + neoswarm_specialists link deps; removed Wave 1 elm_stub.cpp

## Decisions Made
- SpecialistAdapter is generic for any ISpecialist — no includes of concrete specialist headers (grammar_specialist, math_specialist), ensuring the adapter works with any future ISpecialist implementation
- ELMContext parameter is explicitly dropped (named `/*ctx*/`) when forwarding to ISpecialist::Process(string) — legacy specialists don't accept context
- GroundingELM::Process() uses manual `has_value()` checks at each pipeline stage (not BOOST_OUTCOME_TRY) to enable graceful degradation — each stage can fail independently without aborting the pipeline
- GroundingELM returns input unchanged with confidence=0.5f when Retrieve returns empty (not full inference) — differs from the shared-backbone RoleELM::Grounding fallback template; GroundingELM takes precedence when a knowledge pipeline is configured
- ToolSupportELM is a minimal stub (~15 lines of actual code) with no engine dependency — real tool-call formatting is deferred to Phase 10

## Deviations from Plan

### Auto-fixed Issues

None — plan executed exactly as written.

### Design Deviations

**1. CMakeLists.txt: did not include role_elm.cpp/domain_elm.cpp from plan 07-02 template**
- **Found during:** task 4 (CMakeLists.txt registration)
- **Issue:** Plan template showed `role_elm.cpp` and `domain_elm.cpp` in source list, but those files are from plan 07-02 which has not been executed yet. Including non-existent source files would cause CMake configure failure.
- **Fix:** Registered only the 3 new files from this plan (specialist_adapter.cpp, grounding_elm.cpp, tool_support_elm.cpp). role_elm.cpp/domain_elm.cpp will be added when 07-02 is executed.
- **Files modified:** `src/elm/CMakeLists.txt`
- **Verification:** `ninja neoswarm_elm` succeeds — all 3 files compile and link

**2. Removed Wave 1 elm_stub.cpp placeholder**
- **Found during:** task 4
- **Issue:** elm_stub.cpp comment says "This file will be removed in Wave 2 when real .cpp implementations are added." With 3 real source files now present, the stub is no longer needed.
- **Fix:** Deleted `src/elm/elm_stub.cpp` — replaced by real ELM implementations.
- **Files modified:** `src/elm/elm_stub.cpp` (deleted), `src/elm/CMakeLists.txt`

---

**Total deviations:** 2 (minor CMake adjustments for inter-plan dependency ordering)

## Issues Encountered
- cmake reconfigure required path `..` not `../..` from `build/OSX/Debug/` (platform-specific build dir layout)
- `test_genius_elm_ffi` pre-existing failure (subprocess abort) — unrelated to ELM changes, documented as known issue in plan

## Known Stubs

| File | Stub | Reason |
|------|------|--------|
| `src/elm/tool_support_elm.cpp:29-34` | `Process()` always returns input unchanged, confidence=0 | Intentional per D-18 — real tool-call formatting deferred to Phase 10 (Tool Intermediary boundary) |
| `src/elm/tool_support_elm.hpp:42-45` | `IsLoaded()` always returns false | Intentional — stub has no model to load |
| `src/elm/tool_support_elm.cpp:27` | `Load()` is a no-op that returns success | Intentional — no model file needed for stub |

## Next Phase Readiness
- SpecialistAdapter, GroundingELM, and ToolSupportELM ready for ELM registry registration in ApiServer (plan 07-05)
- GroundingELM's knowledge pipeline dependency (neoswarm_knowledge) is already linked — ready for integration test
- Plan 07-02 (RoleELM/DomainELM) should be executed next to complete the ELM implementations before 07-04 (ELM tests)
- ToolSupportELM remains a stub until Phase 10 — consumers must check confidence before treating output as augmented

---

*Phase: 07-expert-language-models-router*
*Plan: 03*
*Completed: 2026-07-17*
