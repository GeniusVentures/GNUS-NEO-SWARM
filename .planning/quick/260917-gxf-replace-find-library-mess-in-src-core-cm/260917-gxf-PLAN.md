---
phase: quick-260917-gxf
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - cmake/CommonBuildParameters.cmake
  - src/core/CMakeLists.txt
  - src/core/sgprocessing/CMakeLists.txt
autonomous: true
requirements:
  - QUICK-260917-GXF-1 # both build modes configure/build after find_library removal
  - QUICK-260917-GXF-2 # SGProcessingManager chain via new src/core/sgprocessing/CMakeLists.txt
  - QUICK-260917-GXF-3 # shared deps as find_package targets in NEO CommonBuildParameters.cmake
must_haves:
  truths:
    - "Standalone configure (GNUS-NEO-SWARM/build/OSX/Debug) succeeds with real ProcessingBase, AsyncIOManager, xxHash::xxhash, ipfs-pubsub, vk-bootstrap::vk-bootstrap, shaderc::shaderc, MNN::MNN targets"
    - "Nested configure (parent GeniusCogntiveSystem/build/OSX/Debug) succeeds without re-executing find_package(SGProcessingManager) (if(NOT TARGET ProcessingBase) guard)"
    - "neoswarm_core builds in both modes with sg_processing_bridge.cpp compiled against install-tree SGProcessingManager headers (from the imported target's INTERFACE_INCLUDE_DIRECTORIES)"
    - "A target that links neoswarm_core (e.g. neo-swarm) links successfully in both modes (no duplicate-symbol regression; -ld_classic preserved)"
    - "src/core/CMakeLists.txt contains zero find_library, zero file(GLOB *.a), zero _SGPROC_ variables, and no stub-mode branch"
  artifacts:
    - path: "src/core/sgprocessing/CMakeLists.txt"
      provides: "Guarded find_package(SGProcessingManager) for the SGProcessing chain"
      min_lines: 8
    - path: "cmake/CommonBuildParameters.cmake"
      provides: "Real thirdparty targets before the _MISSING_DEPS stub block; MNN::MNN standalone fix"
    - path: "src/core/CMakeLists.txt"
      provides: "Clean neoswarm_core definition linking ProcessingBase"
  key_links:
    - from: "src/core/CMakeLists.txt"
      to: "src/core/sgprocessing/CMakeLists.txt"
      via: "add_subdirectory"
      pattern: "add_subdirectory\\(.*/sgprocessing"
    - from: "src/core/CMakeLists.txt"
      to: "ProcessingBase"
      via: "target_link_libraries PUBLIC"
      pattern: "ProcessingBase"
    - from: "src/core/sgprocessing/CMakeLists.txt"
      to: "SGProcessingManager config"
      via: "guarded find_package CONFIG REQUIRED"
      pattern: "if\\(NOT TARGET ProcessingBase\\)"
---

<objective>
Replace the find_library / file(GLOB) dependency mess in src/core/CMakeLists.txt with
imported find_package targets, per the locked user decisions:

- Shared packages get find_package entries in GNUS-NEO-SWARM's cmake/CommonBuildParameters.cmake
  (parent GeniusCognitiveSystem CBP is already complete via user WIP — verified during planning).
- The SGProcessingManager chain gets its own new src/core/sgprocessing/CMakeLists.txt, wired in
  from src/core/CMakeLists.txt.
- All find_library calls, the file(GLOB *.a), the sibling-path include detection, and the dead
  stub-mode branch are deleted. Linking one target (ProcessingBase) pulls the whole chain
  transitively.

Purpose: kill dead logic and manual path detection; make both nested and standalone builds resolve
the SGProcessing chain through proper CMake config packages (same convention as GeniusSDK).
Output: 2 modified CMake files + 1 new CMakeLists; no C++ changes.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@./CLAUDE.md
@.planning/quick/260917-gxf-replace-find-library-mess-in-src-core-cm/260917-gxf-PLAN.md

Both files being edited already carry the user's uncommitted WIP (git status: `M cmake/CommonBuildParameters.cmake`, `M src/core/CMakeLists.txt`, branch feature/app-restructure). The WIP is the intended direction — finish it, never revert it.

## Verified facts (do not re-derive)

- Shared thirdparty root for BOTH build modes:
  `/Users/Shared/SSDevelopment/Development/GeniusVentures/GeniusNetwork/thirdparty/build/OSX/Debug`
  (resolved via THIRDPARTY_BUILD_DIR). Confirmed present:
  `xxhash/lib/cmake/xxHash`, `ipfs-pubsub/lib/cmake/ipfs-pubsub`,
  `AsyncIOManager/lib/cmake/AsyncIOManager`, `vk-bootstrap/lib/cmake/vk-bootstrap`,
  `shaderc/lib/libshaderc_combined.a` + `shaderc/include`, `MNN/lib`.
- SGProcessingManager config:
  `${SUPERGENIUS_BUILD_DIR}/SuperGenius/lib/cmake/SGProcessingManager/` exists. Exported targets
  are UN-NAMESPACED: ProcessingBase, SGProcessors, DataSplitter, SGShaderCompiler, SGCapability,
  SGArtifacts, sgprocmanager{logger,types,sha,quant,diff}, sgproccapture. Linking ProcessingBase
  transitively pulls the rest plus MNN::MNN, Vulkan::Vulkan, vk-bootstrap::vk-bootstrap,
  OpenSSL::Crypto, AsyncIOManager, and Apple frameworks.
- `SGProcessingManagerTargets.cmake` sets INTERFACE_INCLUDE_DIRECTORIES to
  `include/SGProcessingManager` (and `generated/`) — headers come with the targets; the manual
  include-dir detection in core is obsolete. The generated file FATAL-errors if some-but-not-all
  of its targets are already defined (this is HAZARD 1/2).
- Parent GCS `cmake/CommonBuildParameters.cmake` is COMPLETE for nested mode (user WIP):
  Vulkan/VulkanHeaders seeding, shaderc::shaderc target, find_package(vk-bootstrap, evmrelay,
  ProofSystem, SGProcessingManager, SuperGenius), xxHash, ipfs-pubsub, AsyncIOManager, MNN::MNN.
  Parent repo needs NO changes from this plan.
- Nested entry chain: parent CBP does add_subdirectory(GNUS-NEO-SWARM) → NEO root CMakeLists.txt →
  includes NEO's own cmake/CommonBuildParameters.cmake AGAIN in nested mode. Every NEO CBP edit
  must therefore be idempotent when targets already exist (the `if(NOT TARGET ...)` /
  config-package early-return idiom used throughout this file).
- Standalone build entry: GNUS-NEO-SWARM/build/OSX/CMakeLists.txt → NEO CBP directly.
- `test/benchmark/CMakeLists.txt` links bare `MNN` — the bare name must survive the standalone
  MNN fix (as ALIAS).
- SuperGenius's own export (`supergeniusTargets.cmake`) references `ProcessingBase` — so the
  `ProcessingBase` entry in NEO CBP `_MISSING_DEPS` MUST be removed; if the stub were created
  first, the later real find_package in sgprocessing/CMakeLists.txt hits the
  "Some (but not all) targets already defined" fatal.
- Stray `${}` at src/core/CMakeLists.txt line 13 (flagged by orchestrator): NOT present in the
  current file state (grep verified during planning). Do not hunt for it; only remove it if a
  fresh `grep -n '\${}' src/core/CMakeLists.txt` matches.

## GeniusSDK canonical pattern (copy verbatim, adjusting only variable names)

From `/Users/Shared/SSDevelopment/Development/GeniusVentures/GeniusNetwork/GeniusSDK/cmake/CommonBuildParameters.cmake`:

```cmake
# ipfs-pubsub (lines 254-257)
set(ipfs-pubsub_INCLUDE_DIR "${THIRDPARTY_BUILD_DIR}/ipfs-pubsub/include")
set(ipfs-pubsub_DIR "${THIRDPARTY_BUILD_DIR}/ipfs-pubsub/lib/cmake/ipfs-pubsub")
find_package(ipfs-pubsub CONFIG REQUIRED)

# xxhash (lines 285-289)
set(xxHash_INCLUDE_DIR "${THIRDPARTY_BUILD_DIR}/xxhash/include")
set(xxHash_LIBRARY_DIR "${THIRDPARTY_BUILD_DIR}/xxhash/lib")
set(xxHash_DIR "${THIRDPARTY_BUILD_DIR}/xxhash/lib/cmake/xxHash")
find_package(xxHash CONFIG REQUIRED)

# AsyncIOManager (lines 313-317)
set(AsyncIOManager_INCLUDE_DIR "${THIRDPARTY_BUILD_DIR}/AsyncIOManager/include")
set(AsyncIOManager_LIBRARY_DIR "${THIRDPARTY_BUILD_DIR}/AsyncIOManager/lib")
set(AsyncIOManager_DIR "${THIRDPARTY_BUILD_DIR}/AsyncIOManager/lib/cmake/AsyncIOManager")
find_package(AsyncIOManager CONFIG REQUIRED)

# vk-bootstrap (lines 63-65)
set(vk-bootstrap_DIR "${THIRDPARTY_BUILD_DIR}/vk-bootstrap/lib/cmake/vk-bootstrap")
find_package(vk-bootstrap CONFIG REQUIRED)

# shaderc (lines 446-457) — no config package; hand-rolled STATIC IMPORTED
if(NOT TARGET shaderc::shaderc)
    add_library(shaderc::shaderc STATIC IMPORTED GLOBAL)
    set_target_properties(shaderc::shaderc PROPERTIES
        IMPORTED_LOCATION "${THIRDPARTY_BUILD_DIR}/shaderc/lib/${CMAKE_STATIC_LIBRARY_PREFIX}shaderc_combined${CMAKE_STATIC_LIBRARY_SUFFIX}"
        INTERFACE_INCLUDE_DIRECTORIES "${THIRDPARTY_BUILD_DIR}/shaderc/include"
    )
endif()
```

## Current NEO CBP anchors (line numbers in cmake/CommonBuildParameters.cmake as of planning)

- Lines 218-249: MNN block. Nested branch already creates bare `MNN` as ALIAS of MNN::MNN.
  Standalone else-branch creates bare `MNN` as UNKNOWN IMPORTED (the HAZARD 3 bug — core's
  link list references MNN::MNN which does not exist standalone).
- Lines 251-262: dead sibling-source SGProcessingManager include block (to delete).
- Lines 309-336: Vulkan seeding (user WIP — complete, do not touch).
- Lines 438-481: SuperGenius block: `_MISSING_DEPS` stub list (441-465), find_package(SuperGenius)
  (467-472), messages.
</context>

<tasks>

<task type="auto">
  <name>Task 1: NEO CommonBuildParameters.cmake — real targets before stub block, MNN::MNN fix, dead block removal</name>
  <files>cmake/CommonBuildParameters.cmake</files>
  <action>
Four surgical edits to GNUS-NEO-SWARM/cmake/CommonBuildParameters.cmake (build on the user WIP already in the file; do not touch the Vulkan block or anything else):

1. Delete the sibling-source SGProcessingManager block (lines ~251-262: `set(SGPROCESSING_DIR ...)`, the `if(EXISTS "${SGPROCESSING_DIR}/generated/InputFormat.hpp")` include_directories block, and both messages). It is dead once includes arrive via the imported targets' INTERFACE_INCLUDE_DIRECTORIES, and its global source-tree include_directories can shadow the install-tree generated headers the .a files were built against.

2. Fix the standalone MNN else-branch (lines ~238-249) so the REAL target is MNN::MNN (mirroring the nested branch and GeniusSDK/parent): after the existing find_library(MNN_LIBRARY ...), create `MNN::MNN` as UNKNOWN IMPORTED with IMPORTED_LOCATION from MNN_LIBRARY and INTERFACE_INCLUDE_DIRECTORIES from MNN_INCLUDE_DIR, then `if(NOT TARGET MNN) add_library(MNN ALIAS MNN::MNN) endif()` so test/benchmark's bare `MNN` link keeps resolving. Keep the existing comments explaining the PATH-shadowing rationale; adjust wording only where it now describes the wrong target name.

3. Insert ONE contiguous block immediately BEFORE the `if(SUPERGENIUS_BUILD_DIR AND NOT "${SUPERGENIUS_BUILD_DIR}" STREQUAL "")` stub/SuperGenius block (~line 438, after the SUPERGENIUS_BUILD_DIR auto-detection). Content, in this order, verbatim from the GeniusSDK pattern in the context section: ipfs-pubsub, xxHash, AsyncIOManager, vk-bootstrap, then the guarded shaderc::shaderc STATIC IMPORTED GLOBAL target. Precede with a short comment: these must resolve before the `_MISSING_DEPS` stub block below and before find_package(SGProcessingManager) in src/core/sgprocessing/CMakeLists.txt, because SuperGenius/SGProcessingManager exported link interfaces reference them by name. In nested mode the parent CBP already found them — config packages early-return on all-targets-defined, and shaderc is TARGET-guarded, so re-running here is safe (same idiom as the rest of this file).

4. Remove exactly five entries from `_MISSING_DEPS`: `MNN::MNN`, `xxHash::xxhash`, `ipfs-pubsub`, `ProcessingBase`, `AsyncIOManager`. Keep every other entry (ProofSystem::ProofSystem, evmrelay::evmrelay, Boost::json, Boost::unit_test_framework, gnus_upnp, TrustWalletCore, wallet_core_rs, TrezorCrypto, rapidjson, LLVM*) untouched — they remain unresolvable stub fallbacks exactly as today and are out of scope. `ProcessingBase` removal is mandatory: SuperGenius's export references it, and the stub would collide with the real find_package that runs later in sgprocessing/CMakeLists.txt (fatal "already defined" error).

If any find_package fails at configure because a thirdparty package is stale/missing: per project memory, thirdparty builds are user-managed — report it, wait for the user's rebuild, do not investigate or work around it.
  </action>
  <verify>
    <automated>grep -c 'SGPROCESSING_DIR' cmake/CommonBuildParameters.cmake | grep -qx 0 && grep -q 'MNN::MNN UNKNOWN IMPORTED' cmake/CommonBuildParameters.cmake && grep -q 'add_library(MNN ALIAS MNN::MNN)' cmake/CommonBuildParameters.cmake && ! grep -q 'add_library(MNN UNKNOWN IMPORTED)' cmake/CommonBuildParameters.cmake && grep -q 'find_package(vk-bootstrap CONFIG REQUIRED)' cmake/CommonBuildParameters.cmake && grep -q 'shaderc::shaderc STATIC IMPORTED GLOBAL' cmake/CommonBuildParameters.cmake && grep -q 'find_package(AsyncIOManager CONFIG REQUIRED)' cmake/CommonBuildParameters.cmake && grep -q 'find_package(xxHash CONFIG REQUIRED)' cmake/CommonBuildParameters.cmake && grep -q 'find_package(ipfs-pubsub CONFIG REQUIRED)' cmake/CommonBuildParameters.cmake && ! grep -qE '"ProcessingBase"|"AsyncIOManager"|"xxHash::xxhash"|"ipfs-pubsub"|"MNN::MNN"' cmake/CommonBuildParameters.cmake && cd build/OSX/Debug && cmake .. -G Ninja -DCMAKE_BUILD_TYPE=Debug && echo TASK1-OK</automated>
  </verify>
  <done>
Standalone configure passes with all five real packages found before the stub block; MNN::MNN is the real standalone target with bare MNN as ALIAS; the dead sibling-source include block and the five stub entries are gone. Core CMakeLists is untouched at this point (its old find_library path still configures).
  </done>
</task>

<task type="auto">
  <name>Task 2: New src/core/sgprocessing/CMakeLists.txt + strip find_library mess from src/core/CMakeLists.txt</name>
  <files>src/core/sgprocessing/CMakeLists.txt, src/core/CMakeLists.txt</files>
  <action>
1. Create src/core/sgprocessing/CMakeLists.txt with ONLY the guarded package find (comment + guard + DIR set + find_package): comment explaining this chain is consumed solely by neoswarm_core's sgprocessing bridge so it lives here, not in CommonBuildParameters.cmake; then `if(NOT TARGET ProcessingBase)` guarding `set(SGProcessingManager_DIR "${SUPERGENIUS_BUILD_DIR}/SuperGenius/lib/cmake/SGProcessingManager" CACHE PATH "SGProcessingManager cmake config")` and `find_package(SGProcessingManager CONFIG REQUIRED)` with a closing endif. The guard is mandatory: in nested builds the parent CBP already ran this find_package, and the generated targets file fatal-errors on partial target redefinition. SUPERGENIUS_BUILD_DIR is set in both modes (parent CBP / NEO CBP auto-detect). Nothing else goes in this file — includes and the whole chain arrive via the targets' interfaces.

2. Edit src/core/CMakeLists.txt:
   a. Keep the add_library block and both target_include_directories blocks exactly as-is (boost/json includes, the sgns::GeniusSDK TokenID conditional include). Run `grep -n '\${}' src/core/CMakeLists.txt` — if it matches anything, delete the stray token; the orchestrator-flagged line-13 occurrence does not exist in the current file state, so expect no match.
   b. Add `add_subdirectory(${CMAKE_CURRENT_LIST_DIR}/sgprocessing ${CMAKE_CURRENT_BINARY_DIR}/sgprocessing)` immediately after the add_library block (before the link libraries call, so the dependency is visibly in scope).
   c. In target_link_libraries(neoswarm_core PUBLIC ...), append `ProcessingBase` after `AsyncIOManager` (keep the user's WIP list otherwise exactly as written — it is the intended final list).
   d. Delete the ENTIRE "SGProcessingManager integration" section (current lines ~35-123): the _SGPROC_* path variables, the CI release-fallback include detection, all six find_library calls, the conditional include/link block, the file(GLOB _IPFS_PUBSUB_LIBS ...) plus soralog/cares/xxhash/tsl/sqlite3/rocksdb/snappy find_library calls and their foreach wiring, and the headers-only stub-mode else branch. All of it is replaced transitively by ProcessingBase's interface plus the find_package targets from Task 1.
   e. Preserve the duplicate-protobuf-symbol linker tolerance the deleted block carried: an unconditional `if(APPLE) target_link_options(neoswarm_core PUBLIC "LINKER:-ld_classic") endif()` with the original explanatory comment. It stays PUBLIC because consumers (neo-swarm, api/FFI targets) link the same static chain transitively.

No C++ source changes. Do not touch any other src/*/CMakeLists.txt.
  </action>
  <verify>
    <automated>grep -cE 'find_library|file\(GLOB|_SGPROC_|stub mode' src/core/CMakeLists.txt | grep -qx 0 && grep -q 'add_subdirectory(${CMAKE_CURRENT_LIST_DIR}/sgprocessing' src/core/CMakeLists.txt && grep -q 'ProcessingBase' src/core/CMakeLists.txt && grep -q 'LINKER:-ld_classic' src/core/CMakeLists.txt && grep -q 'if(NOT TARGET ProcessingBase)' src/core/sgprocessing/CMakeLists.txt && grep -q 'find_package(SGProcessingManager CONFIG REQUIRED)' src/core/sgprocessing/CMakeLists.txt && cd build/OSX/Debug && cmake .. -G Ninja -DCMAKE_BUILD_TYPE=Debug && ninja neoswarm_core && echo TASK2-OK</automated>
  </verify>
  <done>
Core CMakeLists contains no find_library/GLOB/stub logic, links ProcessingBase (chain pulled transitively), preserves -ld_classic, and compiles sg_processing_bridge.cpp + tensor_interpreter.cpp successfully in the standalone build against install-tree headers.
  </done>
</task>

<task type="auto">
  <name>Task 3: Dual-mode build verification (standalone + nested) and commit handoff</name>
  <files></files>
  <action>
Verify both locked build modes end-to-end:

1. Standalone (already configured in Task 2): `cd /Users/Shared/SSDevelopment/Development/GeniusVentures/GeniusNetwork/GeniusCogntiveSystem/GNUS-NEO-SWARM/build/OSX/Debug && ninja neo-swarm Genius-MOS-ELM-FFI` — exercises full link of the chain through neoswarm_api into executables/shared libs; watch for duplicate-symbol errors (if any appear, the -ld_classic option regressed — fix root cause, do not add workarounds).

2. Nested: `cd /Users/Shared/SSDevelopment/Development/GeniusVentures/GeniusNetwork/GeniusCogntiveSystem/build/OSX/Debug && cmake .. -G Ninja -DCMAKE_BUILD_TYPE=Debug` — this reconfigure proves the if(NOT TARGET ProcessingBase) guard prevents the re-execution fatal in nested mode. Then build the NEO core target and one parent-side consumer that links it: run `ninja -t targets all | grep -i neoswarm_core` and pick the parent app/test target that links it (or `ninja neoswarm_core` plus a discovered consumer such as the GCS app binary). If the nested configure reveals a gap in the PARENT's cmake/CommonBuildParameters.cmake, STOP and report it to the user — the parent repo is out of scope for edits (its CBP was verified complete; per project rules ask before expanding scope).

3. Commits (only with explicit user approval, per CLAUDE.md): present the diff summary, then commit the GNUS-NEO-SWARM changes as a single commit (both cmake/CommonBuildParameters.cmake and src/core/CMakeLists.txt plus the new sgprocessing/CMakeLists.txt belong together), suggested message: `build(core): replace find_library chain with find_package SGProcessingManager targets`. No parent-repo commit is expected (no parent changes). If the user wants the planning artifacts committed too, commit them separately as `docs(quick): plan 260917-gxf find_library cleanup`. Never commit without permission.
  </action>
  <verify>
    <automated>cd /Users/Shared/SSDevelopment/Development/GeniusVentures/GeniusNetwork/GeniusCogntiveSystem/GNUS-NEO-SWARM/build/OSX/Debug && ninja neo-swarm Genius-MOS-ELM-FFI && cd /Users/Shared/SSDevelopment/Development/GeniusVentures/GeniusNetwork/GeniusCogntiveSystem/build/OSX/Debug && cmake .. -G Ninja -DCMAKE_BUILD_TYPE=Debug && ninja neoswarm_core && echo TASK3-OK</automated>
  </verify>
  <done>
Both modes configure and build: standalone links neo-swarm and Genius-MOS-ELM-FFI cleanly; nested reconfigure passes the ProcessingBase guard and builds neoswarm_core. Changes are pending commit with user approval (single NEO-repo commit; parent repo untouched).
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| build inputs → CMake configure | THIRDPARTY_BUILD_DIR and SUPERGENIUS_BUILD_DIR contents are trusted local build artifacts |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-01 | Tampering | thirdparty/SuperGenius prebuilt archives | accept | Same local trusted build trees consumed as before; this change only alters HOW targets are resolved, not which files are linked |
| T-02 | Tampering | existing curl download of GeniusSDK releases in NEO CBP (lines ~380-404) | accept | Pre-existing code, explicitly out of scope; do not modify |
| T-03 | Spoofing | find_library picking wrong MNN from PATH | mitigate (already) | Task 1 keeps the NO_DEFAULT_PATH find_library and the MNN::MNN-as-real-target direction; no regression |
</threat_model>

<verification>
- `grep -cE 'find_library|file\(GLOB|_SGPROC_|stub mode' src/core/CMakeLists.txt` returns 0 (grep gate filtered to the file, not raw grep -c on comments-only matches — the tokens cannot appear in surviving comments because the whole section is deleted).
- Standalone: configure + `ninja neoswarm_core neo-swarm Genius-MOS-ELM-FFI` green in GNUS-NEO-SWARM/build/OSX/Debug.
- Nested: reconfigure + `ninja neoswarm_core` green in parent GeniusCogntiveSystem/build/OSX/Debug (guard holds; no "already defined" fatal).
- `git diff --stat` in NEO repo touches exactly: cmake/CommonBuildParameters.cmake, src/core/CMakeLists.txt, src/core/sgprocessing/CMakeLists.txt (new).
</verification>

<success_criteria>
- All five locked decisions hold: both build modes work; shared packages (xxHash, ipfs-pubsub, AsyncIOManager, vk-bootstrap, shaderc) as find_package/hand-rolled targets in the NEO CBP matching the GeniusSDK pattern; SGProcessingManager chain isolated in the new src/core/sgprocessing/CMakeLists.txt wired from src/core; zero find_library/file(GLOB) left in src/core/CMakeLists.txt; user WIP direction preserved and finished.
- No C++ source changes; no changes outside the three listed CMake files in the NEO repo; parent repo unmodified.
- Builds verified in both modes; commits only after explicit user approval, NEO repo only.
</success_criteria>

<output>
Create `.planning/quick/260917-gxf-replace-find-library-mess-in-src-core-cm/260917-gxf-SUMMARY.md` when done
</output>
