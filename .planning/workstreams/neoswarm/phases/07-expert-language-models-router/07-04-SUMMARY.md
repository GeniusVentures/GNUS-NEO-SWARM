---
phase: 07-expert-language-models-router
plan: 04
subsystem: router
tags: [prompt-analysis, grounding-detection, formatting-detection, chain-builder, heuristic-triggers]

# Dependency graph
requires:
  - phase: 07-01
    provides: "ELMRole enum, ChainStep, ExecutionChain, PromptFeatures (incl. has_grounding_request_, has_formatting_request_)"
provides:
  - "PromptAnalyzer extended with HasGroundingRequest and HasFormattingRequest feature detectors"
  - "ELMChainBuilder class mapping RouteDecision + PromptFeatures to ExecutionChain via 6 heuristic triggers"
affects: [07-05, 07-06]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Keyword-detection pattern for feature extraction (replicated from HasGrammarRequest)"
    - "Stateless decision-tree pattern for chain building (analogous to RuleBasedRouter)"
    - "TDD RED→GREEN cycle with explicit test coverage for all heuristic triggers"

key-files:
  created:
    - "src/elm/elm_chain_builder.hpp - ELMChainBuilder class declaration with Config struct"
    - "src/elm/elm_chain_builder.cpp - 6-trigger decision tree implementation"
    - "test/elm/test_chain_builder.cpp - 8 tests covering all triggers + defaults"
  modified:
    - "src/router/prompt_analyzer.hpp - added HasGroundingRequest, HasFormattingRequest declarations"
    - "src/router/prompt_analyzer.cpp - added 2 detector implementations + Analyze() integration"
    - "src/elm/CMakeLists.txt - added elm_chain_builder.cpp to neoswarm_elm library"
    - "test/CMakeLists.txt - registered test_chain_builder target"
    - "test/router/test_router.cpp - added 6 tests for grounding/formatting features"

key-decisions:
  - "Used static const vector<string> keyword lists for detectors (matching HasGrammarRequest pattern)"
  - "Chain builder is stateless — no initialization needed, no ELM dependency"
  - "Trigger priority: domain triggers (Math, Code) > quality triggers (Grounding, Formatting) > complexity-based"
  - "CMakeLists.txt kept backward-compatible with elm_stub.cpp (other Wave 2/3 files not on this branch)"

patterns-established:
  - "Keyword-detection: static keyword list → lowercase input → linear scan (O(n·k))"
  - "Chain building: if/else-if priority tree → push_back ChainSteps → set reasoning → log"
  - "TDD: RED test file → RED commit → GREEN implementation → GREEN commit"

requirements-completed: [ELM-05, ELM-10]

# Metrics
duration: 6min
completed: 2026-07-17
---

# Phase 7 Plan 4: ELMChainBuilder + PromptAnalyzer Extension Summary

**PromptAnalyzer gains grounding/formatting detectors; ELMChainBuilder maps 6 heuristic triggers to deterministic ExecutionChains**

## Performance

- **Duration:** 6 min
- **Started:** 2026-07-17T18:24:41Z
- **Completed:** 2026-07-17T18:31:08Z
- **Tasks:** 3
- **Files created:** 3
- **Files modified:** 5

## Accomplishments
- PromptAnalyzer extended with `HasGroundingRequest` and `HasFormattingRequest` — 2 new keyword-detection methods following the exact pattern of `HasGrammarRequest` (14 grounding keywords, 19 formatting keywords)
- `Analyze()` now sets all 8 `PromptFeatures` fields (was 6); new fields consumed by ELMChainBuilder trigger 3 and trigger 4
- ELMChainBuilder implemented as a stateless decision-tree class with `Build(RouteDecision, PromptFeatures) → ExecutionChain` — 6 triggers in priority order with a default single-step fallback
- All 17 existing router tests pass unchanged; 8 new chain builder tests cover every trigger path including reasoning verification

## Task Commits

Each task committed atomically (TDD for tasks 1-2):

1. **task 1 (RED): add failing tests for grounding/formatting detectors** - `349d59d` (test)
2. **task 1 (GREEN): implement HasGroundingRequest + HasFormattingRequest** - `5cee1a9` (feat)
3. **task 2 (RED): add failing tests for ELMChainBuilder heuristic triggers** - `6c9133a` (test)
4. **task 2 (GREEN): implement ELMChainBuilder with 6 heuristic triggers** - `3252d4f` (feat)
5. **task 3**: CMakeLists.txt registration was handled during task 2 RED phase (no separate commit needed)

## Files Created/Modified
- `src/elm/elm_chain_builder.hpp` - ELMChainBuilder class with Config struct (thresholds: numeric=0.30, high=5.0, low=2.0, confidence=0.6)
- `src/elm/elm_chain_builder.cpp` - 6-trigger decision tree: numeric→Math+Verifier, code→Planner+Code, grounding→Grounding+Draft+Verify, formatting→Draft+Refiner, low→Draft, high→Planner+Draft+Verify+Refine
- `test/elm/test_chain_builder.cpp` - 8 GTest cases: 6 triggers + default + reasoning validation
- `src/router/prompt_analyzer.hpp` - 2 new private method declarations (HasGroundingRequest, HasFormattingRequest)
- `src/router/prompt_analyzer.cpp` - 2 new detector implementations + Analyze() integration (2 lines)
- `src/elm/CMakeLists.txt` - Added `elm_chain_builder.cpp` alongside existing `elm_stub.cpp`
- `test/CMakeLists.txt` - Registered `test_chain_builder` target linking `neoswarm_elm;neoswarm_common`
- `test/router/test_router.cpp` - 6 new PromptAnalyzer tests (grounding/formatting positive/negative + via verify/rewrite)

## Decisions Made
- Used `static const std::vector<std::string>` keyword lists matching the exact `HasGrammarRequest` pattern — no new pattern introduced
- Grounding keywords: "is it true", "verify", "according to", "fact check", "factual", "evidence", "source", "citation", "validate", "cross-reference", etc.
- Formatting keywords: "format as", "make this look", "structure this", "organize", "rewrite in", "bullet", "outline", "markdown", "json format", "polish this", etc.
- Chain builder uses explicit `std::nullopt` for domain-less steps to prevent `-Wmissing-field-initializers` warnings
- All 6 triggers produce unique chain structures with `m_reasoning` populated

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] CMakeLists.txt registration handled early for compilation**
- **Found during:** task 2 (ELMChainBuilder TDD RED phase)
- **Issue:** Plan lists Task 3 as CMakeLists.txt update, but Task 2 TDD requires compilation. Without `elm_chain_builder.cpp` in the library, neither tests nor implementation can compile.
- **Fix:** Added `elm_chain_builder.cpp` to `src/elm/CMakeLists.txt` during Task 2 RED phase alongside `test/elm/` directory creation and `test/CMakeLists.txt` registration.
- **Files modified:** `src/elm/CMakeLists.txt`, `test/CMakeLists.txt`, `test/elm/test_chain_builder.cpp`
- **Verification:** ninja succeeds, all 8 tests pass
- **Committed in:** `6c9133a` (task 2 RED commit)

**2. [Rule 3 - Blocking] Plan CMakeLists.txt references non-existent Wave 2/3 source files**
- **Found during:** task 3 verification
- **Issue:** Plan's CMakeLists.txt template lists 6 source files (role_elm.cpp, domain_elm.cpp, grounding_elm.cpp, specialist_adapter.cpp, tool_support_elm.cpp) — these exist in Wave 2/3 branches but NOT on this branch (Wave 4, off develop).
- **Fix:** Kept existing `elm_stub.cpp` (Wave 1 placeholder) and added only `elm_chain_builder.cpp`. The other files will be added by their respective wave PRs.
- **Files modified:** `src/elm/CMakeLists.txt`
- **Verification:** `ninja neoswarm_elm` succeeds; `test_chain_builder` links and runs
- **Committed in:** `6c9133a` (already handled)

**3. [Rule 1 - Bug] Fixed 13 `-Wmissing-field-initializers` warnings in chain builder**
- **Found during:** task 2 GREEN build
- **Issue:** `ChainStep` has two fields (`m_role`, `m_domain`); brace-initializing with only `m_role` triggered compiler warnings.
- **Fix:** Added explicit `std::nullopt` for domain-less steps and `std::string{"domain"}` for domain steps.
- **Files modified:** `src/elm/elm_chain_builder.cpp`
- **Verification:** Zero warnings on rebuild
- **Committed in:** `3252d4f` (task 2 GREEN commit)

---

**Total deviations:** 3 auto-fixed (2 blocking, 1 bug)
**Impact on plan:** All deviations necessary for correctness and compilation. No scope creep. The core logic (6-trigger decision tree, 2 feature detectors) matches the plan exactly.

## Issues Encountered
- None — all challenges resolved inline via deviation rules.

## Test Results

```
17/18 tests pass (94%)
  - test_chain_builder: 8/8 PASS (new)
  - test_router: 17/17 PASS (5 original + 6 new + 6 RuleBasedRouter)
  - test_genius_elm_ffi: FAIL (pre-existing FIX-01, PR #93)
```

## Next Phase Readiness
- ELMChainBuilder ready for integration into ApiServer::RunELMChain (Phase 07-05/07-06)
- PromptAnalyzer now covers 6/6 heuristic trigger inputs (was 4/6)
- Chain builder is stateless — no initialization dependency on ELM registry
- `test/elm/` directory and test infrastructure ready for future ELM tests

## Known Stubs
None — all implemented code is functional and test-verified.

---

*Phase: 07-expert-language-models-router*
*Completed: 2026-07-17*
