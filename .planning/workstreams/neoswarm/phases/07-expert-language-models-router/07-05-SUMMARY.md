---
phase: 07-expert-language-models-router
plan: 05
subsystem: api-server-config
tags: [elm, chain-execution, config-parsing, integration, composition-root]
requires: [07-02, 07-03, 07-04]
provides: [ApiServer::RunELMChain, elms JSON config]
affects: [src/api, src/main.cpp, build/install]
tech-stack:
  added: []
  patterns:
    - "Sequential chain execution via ELMRegistry + ELMChainBuilder"
    - "JSON config parsing following existing LoadConfigFile patterns"
    - "Eager/lazy loading with fallback to shared backbone"
key-files:
  created: []
  modified:
    - src/api/api_server.hpp
    - src/api/api_server.cpp
    - src/main.cpp
    - src/elm/CMakeLists.txt
    - src/api/CMakeLists.txt
    - cmake/CommonBuildParameters.cmake
decisions:
  - "ELMContext carries only m_originalTask, m_stepConfidences, m_groundingFacts — step output flows via input parameter per WR-01 review"
  - "ELMChainBuilder::Build() returns ExecutionChain directly (not outcome::result) — mirrors Wave 4 design"
  - "ParseELMRole unknown role → PrimaryDraft safe default per T-07-05-03"
metrics:
  duration: "~7.5 minutes"
  completed: "2026-07-22T17:22:17Z"
---

# Phase 7 Plan 5: ApiServer ELM Integration + elms Config Summary

Wire the ELM subsystem into the composition root (`ApiServer`) and parse the `elms` JSON configuration section. All 10 ELMs are registered at `Initialize()`, `Process()` gains an `ElmAssisted` execution path, and `RunELMChain` executes chain steps sequentially with lazy loading and confidence tracking.

## Tasks Completed

| # | Name | Status |
|---|------|--------|
| 1 | Extend ApiServer header with ELM registry + RunELMChain declaration | ✅ |
| 2 | Implement Initialize() ELM registration + Process() Chain case + RunELMChain | ✅ |
| 3 | Parse elms JSON config section in main.cpp | ✅ |

## Commits

| Hash | Type | Message |
|------|------|---------|
| 3ae0cf7 | feat | Extend ApiServer header with ELM registry + RunELMChain declaration |
| 53cff26 | feat | Implement ELM initialization, Process() chain case, RunELMChain |
| 48e0602 | feat | Parse elms JSON config section in main.cpp |
| 6e5437d | fix | Auto-fix nested type references and missing export target |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Missing source] Added elm_chain_builder.cpp to neoswarm_elm library**
- **Found during:** Task 1 (pre-build review)
- **Issue:** `src/elm/CMakeLists.txt` did not include `elm_chain_builder.cpp` (Wave 4 artifact)
- **Fix:** Added to source list
- **Files modified:** `src/elm/CMakeLists.txt`
- **Commit:** 3ae0cf7

**2. [Rule 3 - Missing link dep] Added neoswarm_elm to neoswarm_api link libraries**
- **Found during:** Task 1 (pre-build review)
- **Issue:** `neoswarm_api` includes ELM headers but did not link against `neoswarm_elm`
- **Fix:** Added `neoswarm_elm` to `target_link_libraries`
- **Files modified:** `src/api/CMakeLists.txt`
- **Commit:** 3ae0cf7

**3. [Rule 3 - Missing export target] Added neoswarm_elm to install TARGETS export list**
- **Found during:** Build (cmake configure failed)
- **Issue:** `neoswarm_api` depends on `neoswarm_elm` but `neoswarm_elm` was not in the CMake install/export set
- **Fix:** Added to `install(TARGETS ...)` list in `cmake/CommonBuildParameters.cmake`
- **Files modified:** `cmake/CommonBuildParameters.cmake`
- **Commit:** 6e5437d

**4. [Rule 1 - Bug] Fixed nested type qualification in main.cpp**
- **Found during:** Build (compilation error)
- **Issue:** `ElmConfigEntry` is nested inside `Args` struct and `ElmEntry` is nested inside `ApiServer::Config`, but plan used unqualified names
- **Fix:** Used `Args::ElmConfigEntry` and `api::ApiServer::Config::ElmEntry`
- **Files modified:** `src/main.cpp`
- **Commit:** 6e5437d

**5. [Plan adjustment] ELMContext has no m_lastOutput field (per WR-01 review)**
- **Found during:** Task 2 implementation
- **Issue:** Plan's RunELMChain template set `context.m_lastOutput = currentOutput`, but actual struct has no such field — step output flows exclusively via `input` parameter
- **Fix:** Tracked `currentOutput` as local variable only; passed to next step as `elm->Process(currentOutput, context)`
- **Files modified:** `src/api/api_server.cpp`

**6. [Plan adjustment] ELMChainBuilder::Build() returns ExecutionChain directly**
- **Found during:** Task 2 implementation
- **Issue:** Plan used `chainResult.has_value()` pattern expecting `outcome::result<ExecutionChain>`, but the actual signature returns `ExecutionChain` directly (removed in Wave 4 per D-11)
- **Fix:** Used `chain.m_steps.empty()` as fallback trigger
- **Files modified:** `src/api/api_server.cpp`

**7. [Minor] RunELMChain is 114 lines (plan limit: ≤100)**
- **Found during:** Task 2 implementation
- **Issue:** The plan's idealized template was ~100 lines; concrete implementation with error handling, logging, and lazy-loading expanded to 114 lines
- **Resolution:** Accepted as minor deviation — function is readable linear flow; extracting helpers would reduce clarity

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: model-path-validation | src/api/api_server.cpp:207-213 | GroundingELM eager-load uses `Load("")` — empty path triggers shared-backbone mode per D-04; covered by existing load-path validation in MNNInferenceEngine |
| threat_flag: unknown-role-fallback | src/api/api_server.cpp:48 | ParseELMRole maps unknown strings → PrimaryDraft per T-07-05-03 |

## Known Stubs

- **ToolSupportELM** (D-18): Registered in Initialize() as pass-through stub with `IsLoaded()=false` and `GetConfidence()=0.0f`. Intentional per architecture decision — real tool-call formatting requires Phase 10's Tool Intermediary boundary.

## Verification

- ✅ `ninja neo-swarm` succeeds with zero warnings
- ✅ `ctest --output-on-failure`: 18/18 tests pass (zero regressions)
- ✅ Config parsing: `echo '{"elms":[{"role":"verifier","model":"v.mnn","eager":true}]}'` → "Loaded 1 ELM config(s)"
- ✅ No new CLI flags (`--elm` returns 0 per D-15)
- ✅ ApiServer::Initialize() registers all 10 ELMs (D-01, D-06, D-17, D-18)
- ✅ Process() handles `ExecutionMode::ElmAssisted` → RunELMChain
- ✅ RunELMChain executes steps sequentially with ELMContext accumulation
- ✅ Lazy loading default; eager opt-in via config (D-16)
- ✅ `elms` JSON config parsed and flowed to ApiServer::Config (D-14)
