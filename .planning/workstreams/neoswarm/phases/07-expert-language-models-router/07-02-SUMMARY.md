---
phase: 07-expert-language-models-router
plan: 02
subsystem: ai
tags: [elm, role-elm, domain-elm, prompt-templates, tdd, c++17, neoswarm]

# Dependency graph
requires:
  - phase: 07-expert-language-models-router
    plan: 01
    provides: "IELM interface, ELMRole/ELMContext types, neoswarm_elm CMake target"
provides:
  - "RoleELM class with 7 role-specific prompt templates (Planner, PrimaryDraft, Verifier, Arbiter, Refiner, Grounding, ToolSupport)"
  - "DomainELM class with dual-engine mode (shared backbone default, optional dedicated .mnn model via Load)"
  - "3 domain prompt templates: Math, Code, Science"
  - "12 passing unit tests (6 RoleELM + 6 DomainELM)"
  - "neoswarm_elm library built from role_elm.cpp + domain_elm.cpp"
affects:
  - "07-03 (SpecialistAdapter / GroundingELM / ToolSupportELM)"
  - "07-04 (ELMChainBuilder uses ELMRole)"
  - "07-05 (ApiServer orchestrates RoleELM + DomainELM in chains)"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "TDD RED/GREEN commit cycle per task"
    - "GrammarSpecialist Process() pattern replicated for both ELMs"
    - "Dual-engine mode: shared_ptr (shared backbone) + unique_ptr (own model)"
    - "Role-specific [INST] prompt templates as static switch-case constants (D-03)"
    - "Fail-close: not-loaded/no-engine → input unchanged, confidence=0.0f (D-04)"
    - "MockEngine test pattern replicated from test_grammar_specialist.cpp"

key-files:
  created:
    - "src/elm/role_elm.hpp — RoleELM class declaration (IELM implementation)"
    - "src/elm/role_elm.cpp — RoleELM with 7 prompt templates, Process following GrammarSpecialist pattern"
    - "src/elm/domain_elm.hpp — DomainELM class declaration (dual-engine mode)"
    - "src/elm/domain_elm.cpp — DomainELM with 3 domain templates, own-engine creation via MNNInferenceEngine"
    - "test/elm/test_elm.cpp — 12 ELM unit tests (6 RoleELM + 6 DomainELM) with MockEngine"
  modified:
    - "src/common/types.hpp — Removed m_lastOutput from ELMContext (WR-01 fix)"
    - "src/elm/CMakeLists.txt — Replaced elm_stub.cpp with role_elm.cpp + domain_elm.cpp, added neoswarm_core"
    - "test/CMakeLists.txt — Added test_elm target linking neoswarm_elm + neoswarm_network"
  removed:
    - "src/elm/elm_stub.cpp — Wave 1 compilation stub, no longer needed"

key-decisions:
  - "WR-01 resolved: removed m_lastOutput from ELMContext — input parameter carries prior step's output exclusively"
  - "Verifier template uses input for 'output to verify' and context.m_originalTask for the original task"
  - "TDD flow followed: separate RED (failing tests + stubs) and GREEN (full implementation) commits per task"
  - "neoswarm_network added to test_elm link to resolve transitive MNNInferenceEngine → SGClient symbols (Rule 3 fix)"

requirements-completed: [ELM-01, ELM-02]

# Metrics
duration: ~15 min
completed: 2026-07-16
---

# Phase 7 Plan 02: RoleELM + DomainELM Implementation Summary

**Concrete ELM implementations: RoleELM (7 shared-backbone role templates) and DomainELM (Math/Code/Science with optional dedicated .mnn model), both behind the IELM interface from Wave 1.**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-07-16T20:33:00Z
- **Completed:** 2026-07-16T20:39:00Z
- **Tasks:** 3 (with TDD RED/GREEN sub-commits: 6 total commits)
- **Files created/modified:** 10 (5 created, 3 modified, 2 removed)

## Accomplishments

- `RoleELM` implements `IELM` for 7 role-based ELMs with `[INST]` prompt templates: Planner, PrimaryDraft, Verifier, Arbiter, Refiner, Grounding, ToolSupport
- `DomainELM` implements `IELM` for 3 domain ELMs (Math, Code, Science) with dual-engine mode: shared backbone by default, own MNNInferenceEngine when `Load(path)` receives a non-empty path
- `BuildPrompt()` dispatches on `ELMRole` via switch — templates are named constants in implementation per D-03
- Fail-close per D-04: not-loaded or no engine → input returned unchanged with confidence=0.0f
- Confidence formula: `1.0f - min(perplexity / 10.0f, 1.0f)` — matches existing GrammarSpecialist pattern
- 12 unit tests (6 RoleELM + 6 DomainELM) all passing
- Wave 1 `elm_stub.cpp` removed (no longer needed)
- 17/18 ctest pass (1 pre-existing GeniusELM FFI teardown failure unchanged)

## Task Commits

| # | Commit | Type | Description |
|---|--------|------|-------------|
| Pre | 17b2204 | fix | Remove redundant ELMContext::m_lastOutput per review WR-01 |
| 1a | 342c828 | test | Add failing RoleELM tests (TDD RED) |
| 1b | 82fce1d | feat | Implement RoleELM with 7 role prompt templates (TDD GREEN) |
| 2a | 4266d2a | test | Add failing DomainELM tests (TDD RED) |
| 2b | cdb8f11 | feat | Implement DomainELM with dual-engine mode (TDD GREEN) |
| 3 | 7a15489 | chore | Remove Wave 1 elm_stub.cpp, finalize CMake configuration |

## Deviations from Plan

### Pre-Approved Fix

**WR-01: Removed redundant ELMContext::m_lastOutput**
- **Found during:** Pre-task fix (from 07-REVIEW.md, approved by review)
- **Fix:** Removed `m_lastOutput` from `ELMContext` struct in `src/common/types.hpp`. Updated Doxygen to document that the `input` parameter carries the previous step's output exclusively.
- **Files modified:** `src/common/types.hpp`
- **Commit:** 17b2204
- **Impact on plan templates:** None — no RoleELM/DomainELM template actually used `context.m_lastOutput`. The Verifier template uses `input` for "output to verify" and `context.m_originalTask` for the original task — both remain available.

### Auto-fixed Issues

**1. [Rule 3 — Blocking] test_elm link failure: unresolved MNNInferenceEngine symbols**
- **Found during:** Task 2 GREEN phase (DomainELM implementation)
- **Issue:** DomainELM.cpp includes `mnn_inference_engine.hpp` which transitively pulls in SGProcessingBridge, SGClient, and ProcessingManager symbols. The test_elm target only linked against `neoswarm_core` which contains MNNInferenceEngine, but MNNInferenceEngine's dependencies (SGClient from `neoswarm_network`) were not linked.
- **Fix:** Added `neoswarm_network` to the `test_elm` link libraries in `test/CMakeLists.txt`. This resolves the transitive symbol chain through SGClient without impacting the lightweight test design (the test only exercises the shared-backbone path via MockEngine, not the own-engine MNN path).
- **Files modified:** `test/CMakeLists.txt`
- **Commit:** Included in cdb8f11

### TDD Execution Notes

The plan specified `tdd="true"` for tasks 1 and 2. The TDD RED/GREEN cycle was followed with separate commits per phase:
- RED: Test file + stub implementation + CMake registration → tests compile but fail at runtime
- GREEN: Full implementation → tests pass

This resulted in 2 commits per TDD task instead of 1, which is compliant with the TDD execution specification.

## Known Stubs

None — all implementations are complete. The `elm_stub.cpp` Wave 1 compilation stub has been removed.

## Threat Flags

None — the threat model's three threats (T-07-02-01 prompt injection, T-07-02-02 path traversal, T-07-02-03 output sanitization) are all dispositioned as per the plan's threat register:
- T-07-02-01: Mitigated via `[INST]...[/INST]` structural delimiting — user input is placed AFTER the role instruction
- T-07-02-02: Accepted for Phase 7 (config-sourced paths)
- T-07-02-03: Accepted for Phase 7 (local-only)

No new threat surface introduced beyond what was registered.

---

*Phase: 07-expert-language-models-router*
*Completed: 2026-07-16*
