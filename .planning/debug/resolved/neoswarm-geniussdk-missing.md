---
status: resolved
trigger: "gcs_global_db.cpp(17,10): error C1083: Cannot open include file: 'GeniusSDK.hpp': No such file or directory, in neoswarm_storage.vcxproj, during a full outer build (cmake --build build/Windows/Release --parallel 8 --config Release from W:\\gnus\\GeniusCognitiveSystem)."
created: 2026-08-19
updated: 2026-08-19T03:10:00Z
---

## Symptoms

**Expected behavior:** `src/storage/gcs_global_db.cpp` compiles cleanly as part of the `neoswarm_storage` target — `GeniusSDK.hpp` should resolve via whatever include path GeniusSDK is normally exposed through in this outer build.

**Actual behavior:**
```
W:\gnus\GeniusCognitiveSystem\GNUS-NEO-SWARM\src\storage\gcs_global_db.cpp(17,10): error C1083: Cannot open include file: 'GeniusSDK.hpp': No such file or directory [W:\gnus\GeniusCognitiveSystem\build\Windows\Release\src\storage\neoswarm_storage.vcxproj]
```

**Error messages:** Exact compiler output above.

**Timeline:** First seen in a full outer-build attempt on 2026-08-18/19, after fixing an unrelated, earlier-blocking MNN header/linkage issue that had prevented the build from reaching this target before. This session's earlier CMake-configure fix (see resolved `neoswarm-mnn-llm-header` session's Context) ported ~25 `find_package()` blocks including GeniusSDK from `GeniusNetwork/GeniusSDK/cmake/CommonBuildParameters.cmake` into `GeniusCognitiveSystem/cmake/CommonBuildParameters.cmake` — worth checking whether that port is missing an include-directory propagation step specifically for GeniusSDK's headers, or whether `neoswarm_storage`'s own CMakeLists.txt simply never links/includes the GeniusSDK target that provides this header.

**Reproduction:**
```
cd W:\gnus\GeniusCognitiveSystem
cmake --build build/Windows/Release --target neoswarm_storage --config Release
```

## Context

This is a fresh debug session split out from a broader `neoswarm-mnn-llm-header` debug session (now resolved and archived) that surfaced several distinct, unrelated build failures in the same full-build log. This one is scoped ONLY to this missing-include issue in `src/storage/gcs_global_db.cpp`. Do not touch MNN-related files, the Boost.Test linkage issue, the C++20 designated-initializer issue, or the `dllimport` issue in `test_genius_elm_ffi.vcxproj` — those are separate, independently-tracked debug sessions.

Given this session's history of finding CMake include/link wiring gaps (the MNN bare-target-shadowing bug, the wrong llm.hpp include path), this is plausibly another instance of the same general category: a missing or misconfigured include-directory/target-link wiring for GeniusSDK specifically for the `neoswarm_storage` target, rather than a genuinely absent file. Verify whether `GeniusSDK.hpp` exists anywhere in the GeniusSDK checkout/build output before assuming a deeper problem.

## Current Focus

reasoning_checkpoint:
  hypothesis: "`GeniusSDK.hpp` is not a misplaced/unpropagated include-directory problem. It is a file that has NEVER existed anywhere in the GeniusSDK repository (any branch, any commit), and the function it was supposed to declare — `GeniusSDKGetNode()` returning a `GeniusNode*`/`shared_ptr` for `->GetPubSub()` — also has never existed anywhere in that repo. `src/storage/CMakeLists.txt` already contains fully-correct, deliberate include-directory wiring for `${GENIUS_SDK_DIR}/src` (plus 4 more transitive-include fixes for WalletCore/zkLLVM/evmrelay/MNN) — added by an earlier phase (03-01, commit bc6ab3c) specifically to consume `GeniusSDK.hpp` 'from the GeniusSDK source tree' — but that source tree only ever contained `GeniusSDK.h` (the plain-C API), never a `.hpp` C++ facade. The prior phase's own SUMMARY.md documentation of this (claiming `GeniusSDKGetNode()` was 'already on GeniusSDK develop', citing a build-tree dylib symbol `__Z16GeniusSDKGetNodev`, and a commit hash `d550800`) does not match reality and appears to be fabricated/unverified, matching a pattern already found once this session in the resolved `neoswarm-mnn-llm-header` debug session (false claims about vendored build state that were never actually checked)."
  confirming_evidence:
    - "`find` across the entire GeniusSDK checkout (`W:\\gnus\\GeniusNetwork\\GeniusSDK`), its thirdparty build output, and the CMake build tree for a file named `GeniusSDK.hpp` (any case) returns zero results. Only `GeniusSDK.h` (36KB, plain C API, `extern \"C\"` blocks) exists in `GeniusSDK/src/`."
    - "`grep -r GeniusSDKGetNode` (word boundary, function-call form `GeniusSDKGetNode(`) across the entire GeniusSDK repo returns zero matches. The only similarly-named symbol is `GeniusSDKGetNodeState()` (declared `GeniusSDK.h:503`, defined `GeniusSDK.cpp:988`), which returns a `GeniusNodeState_t` enum, not a node pointer — cannot support `->GetPubSub()`."
    - "`git log --all --oneline` in the GeniusSDK repo (searches every branch/commit, not just current `dev_childwallet`) contains zero commits matching `GeniusSDKGetNode` or `d550800` (the commit hash cited in NEO-SWARM's own CMakeLists.txt comments and 03-01-SUMMARY.md as having added this function). The hash does not exist in this repository at all."
    - "`git status --short` in GeniusSDK is clean — this is not an uncommitted-local-changes or stale-checkout situation; the function was never committed on any branch."
    - "GeniusSDK.h contains zero occurrences of `PubSub`/`pubsub` anywhere — no C API surface for pubsub access exists at all today."
    - "The real pubsub owner is `sgns::GeniusNode::GetPubSub()` (SuperGenius/src/account/GeniusNode.hpp:742, a normal public member function on a real, existing C++ class) — but the only live instance of `GeniusNode` in GeniusSDK.cpp is `GeniusNodeInstance`, a `std::shared_ptr<sgns::GeniusNode>` declared inside an anonymous namespace (GeniusSDK.cpp:36-208) — internal linkage, invisible outside that translation unit, not exposed via `GeniusSDK.h` or any other header."
    - "GENIUS_SDK_DIR resolves, exactly as GNUS-NEO-SWARM/cmake/CommonBuildParameters.cmake computes it, to `W:/gnus/GeniusNetwork/GeniusSDK` — confirmed directly via the configured build's `CMakeCache.txt` (`GENIUSSDK_DIR:STRING=W:/gnus/GeniusNetwork/GeniusSDK`, `PROJECT_SUPER_ROOT:UNINITIALIZED=W:\\gnus\\GeniusNetwork\\`). This is the correct, intended directory — there is no path-resolution bug. The `target_include_directories(neoswarm_storage PUBLIC \"${GENIUS_SDK_DIR}/src\")` line in storage/CMakeLists.txt is already wired correctly; it just points at a directory that genuinely does not contain the header being included."
    - "No other NEO-SWARM code (api_server.hpp, super_genius_client.hpp/SGClient) accesses a raw `GeniusNode*`/`GeniusSDKGetNode()`-style handle anywhere — the only existing, working integration pattern with GeniusSDK across the rest of the codebase is the plain-C API (`GeniusSDKInitWithKey` etc.), never a C++ object accessor. This is consistent with `GeniusNodeInstance` genuinely never having been exposed — `gcs_global_db.cpp` is the ONLY call site in the entire dependency graph that assumes this API exists."
  falsification_test: "If `GeniusSDK.hpp` or a `GeniusSDKGetNode(` definition existed anywhere in the GeniusSDK repo (any branch/commit) or in the configured build tree, this hypothesis would be false and the bug would instead be a path/propagation issue as originally suspected. Exhaustive filesystem `find` and full-history `git log --all` search both came back empty — this is direct, repeatable observation, not inference from a single grep."
  fix_rationale: "N/A — no fix applied. The correct fix (adding a real `GeniusSDKGetNode()` public accessor + `GeniusSDK.hpp` header to GeniusSDK, OR redesigning `GcsGlobalDb::Initialize()`'s pubsub-acquisition strategy in NEO-SWARM to use a mechanism that actually exists) both cross this task's explicit STOP condition: fixing this requires either editing a shared/vendored file outside GNUS-NEO-SWARM's own repo (GeniusSDK, a sibling project with its own commit history/ownership), or unilaterally redeciding a prior architecture decision (D-15/D-16/D-16a) that assumed an API surface which was never implemented. Neither is a minimal CMake-wiring diff — both are real feature/design work belonging to someone else's call."
  blind_spots: "Have not checked whether there is a WIP/uncommitted branch of GeniusSDK on a different machine (e.g., the original phase-3 author's own checkout) that might have actually implemented this and simply never got pushed/merged — cannot verify this remotely, would need to ask the user. Have not proposed a NEO-SWARM-side workaround (e.g., temporarily stubbing pubsub acquisition or excluding neoswarm_storage's production init path) since that would itself be a non-trivial design call requiring the same kind of user sign-off — deferred to the checkpoint below rather than assumed."

hypothesis: (superseded by reasoning_checkpoint above) The originally-suspected 'missing include-directory propagation for one target' theory is REFUTED — see Eliminated below.

test: Confirmed via direct filesystem search (`find`), full-repo/full-history grep, and `git log --all`/`git status` inspection of the actual GeniusSDK checkout — no build experiment was needed or would help, since the header/function genuinely do not exist anywhere to find.

expecting: N/A — confirmed via direct evidence, not a predictive experiment.

next_action: DECISION RECEIVED from user via coordinator: implement Option A (add a narrow, real accessor to GeniusSDK). Implemented, built, installed, and verified — see updated Resolution below. Awaiting human confirmation that this is acceptable before archiving (a NEW, distinct, pre-existing compile error — C2039 'AsioSchedulerBackend' not a member of 'libp2p::basic' at gcs_global_db.cpp:123 — has now surfaced further into the same file; it was always there but unreachable while the C1083 blocked compilation earlier in the file. This is out of scope for this session per the original single-issue-per-session convention; recommend a new debug session for it, matching how the resolved neoswarm-mnn-llm-header session staged its own cascading discoveries).

## Evidence

- timestamp: 2026-08-19T01:45:00Z
  checked: "Filesystem search (`find -iname GeniusSDK.hpp`) across W:\\gnus\\GeniusNetwork\\GeniusSDK, W:\\gnus\\GeniusNetwork\\thirdparty, W:\\gnus\\GeniusCognitiveSystem\\build, and the entire W:\\gnus tree."
  found: "Zero matches anywhere on disk. Only `GeniusSDK.h` (plain C header, 36KB) exists at W:\\gnus\\GeniusNetwork\\GeniusSDK\\src\\GeniusSDK.h."
  implication: "GeniusSDK.hpp is not misplaced or unbuilt — it has never been created."

- timestamp: 2026-08-19T01:47:00Z
  checked: "src/storage/CMakeLists.txt (the neoswarm_storage target) — full read."
  found: "Already contains deliberate, well-commented include-directory wiring: `target_include_directories(neoswarm_storage PUBLIC \"${GENIUS_SDK_DIR}/src\")` (to consume GeniusSDK.hpp 'from the GeniusSDK source tree' per an existing comment), PLUS four more explicit include additions for WalletCore, zkLLVM/crypto3, evmrelay, and MNN — all added specifically to support GeniusSDK.hpp's assumed include chain (per comments and cross-referenced 03-01-SUMMARY.md deviations 6-7). Also links `sgns::GeniusSDK_shared`/`sgns::GeniusSDK` correctly with a build-tree-dylib IMPORTED_LOCATION redirect for a symbol (`GeniusSDKGetNode`) that turns out not to exist."
  implication: "The CMake wiring this task was scoped to investigate is already fully, correctly implemented — by a prior phase, specifically for this exact header. It is not the problem. The problem is one level up: the header/function being wired for do not exist in the dependency."

- timestamp: 2026-08-19T01:50:00Z
  checked: "grep for `GeniusSDKGetNode\\(` across W:\\gnus\\GeniusNetwork\\GeniusSDK (source, headers, .cpp)."
  found: "Zero matches. Only `GeniusSDKGetNodeState()` exists (GeniusSDK.h:503, GeniusSDK.cpp:988) — a different function returning an enum, not a node pointer."
  implication: "The specific function `gcs_global_db.cpp`/`gcs_global_db.hpp` depend on (per D-15/D-16/D-16a and inline doc comments referencing 'GeniusSDKGetNode() == nullptr -> Error::SdkNotInitialized') does not exist under any name close to what's expected."

- timestamp: 2026-08-19T01:55:00Z
  checked: "git log --all --oneline and git status --short in W:\\gnus\\GeniusNetwork\\GeniusSDK; also searched GeniusCognitiveSystem/GNUS-NEO-SWARM's own repo/history for the commit hash 'd550800' cited in storage/CMakeLists.txt comments and 03-01-SUMMARY.md as having added GeniusSDKGetNode."
  found: "GeniusSDK's full commit history (all branches) contains zero commits touching GeniusSDKGetNode; the cited hash `d550800` does not exist in the repo at all. Working tree is clean (no uncommitted local changes hiding the function)."
  implication: "This isn't a stale-checkout or wrong-branch issue — the function was never committed anywhere in this repository's real history. The prior phase's SUMMARY.md claim ('accessor already on GeniusSDK develop... build-tree dylib contains __Z16GeniusSDKGetNodev symbol... commit d550800') does not correspond to anything verifiable and appears fabricated — the same class of false, unverified claim already caught once this session in the resolved neoswarm-mnn-llm-header debug session."

- timestamp: 2026-08-19T02:00:00Z
  checked: "SuperGenius/src/account/GeniusNode.hpp (the real class providing GetPubSub()) and GeniusSDK.cpp's internal GeniusNodeInstance variable (line 208, inside the anonymous namespace starting line 36)."
  found: "`sgns::GeniusNode::GetPubSub()` is a real, existing public member function (GeniusNode.hpp:742) returning `std::shared_ptr<ipfs_pubsub::GossipPubSub>`. The one live instance in the running SDK, `GeniusNodeInstance` (a `std::shared_ptr<sgns::GeniusNode>`), is declared inside an anonymous namespace in GeniusSDK.cpp — internal linkage, not accessible from any other translation unit, and never exposed via GeniusSDK.h or any other header."
  implication: "The underlying capability (a running node with a pubsub) genuinely exists at runtime inside GeniusSDK's shared library, but there is currently no public API — C or C++ — to reach it from outside GeniusSDK.cpp. Exposing it requires adding new, real API surface to GeniusSDK itself, not a CMake or include-path fix."

- timestamp: 2026-08-19T02:05:00Z
  checked: "GENIUS_SDK_DIR resolution — grepped GNUS-NEO-SWARM/cmake/CommonBuildParameters.cmake's GeniusSDK block and cross-checked against the actual configured build/Windows/Release/CMakeCache.txt."
  found: "GENIUSSDK_DIR:STRING=W:/gnus/GeniusNetwork/GeniusSDK and PROJECT_SUPER_ROOT:UNINITIALIZED=W:\\gnus\\GeniusNetwork\\ — both correct, intended values; GeniusSDK_DIR (the CONFIG package var) is GeniusSDK_DIR-NOTFOUND, but that's a separate, non-blocking find_package(CONFIG) fallback path, irrelevant to the include-directory fix already present in storage/CMakeLists.txt."
  implication: "Confirms there is no path-resolution/propagation bug of any kind — GENIUS_SDK_DIR points exactly where it should, and neoswarm_storage's CMakeLists.txt already includes that exact directory. Ruled out the entire 'wiring gap' branch of investigation."

- timestamp: 2026-08-19T02:10:00Z
  checked: "Searched GNUS-NEO-SWARM's own src/ tree (api_server.hpp, super_genius_client.hpp, and all other consumers) for any existing, working pattern of accessing a raw GeniusNode/pubsub handle across the GeniusSDK boundary."
  found: "No other code anywhere in NEO-SWARM does this. The only established, working integration pattern with GeniusSDK across the whole codebase is the plain-C API (GeniusSDKInitWithKey, etc.) — never a C++ object accessor. gcs_global_db.cpp/hpp are the sole call site assuming a GeniusSDKGetNode()-shaped API."
  implication: "This is not 'other targets already resolve this fine, just this one is missing wiring' — no other target in the entire build has ever successfully used this API, because it doesn't exist. This explains why the error is only seen now: neoswarm_storage is the first (and only) target to attempt it."

- timestamp: 2026-08-19T02:30:00Z
  checked: "Confirmed sgns::GeniusSDK_shared / sgns::GeniusSDK imported targets' actual INTERFACE_INCLUDE_DIRECTORIES (GeniusSDKTargets.cmake) and whether GeniusSDK.h is genuinely installed to that path (find on disk)."
  found: "Both imported targets already carry INTERFACE_INCLUDE_DIRECTORIES=\"${_IMPORT_PREFIX}/include\" (== ${GENIUS_SDK_BUILD_DIR}/GeniusSDK/include), and GeniusSDK.h is genuinely installed there. GeniusSDK.h itself has zero C++ header dependencies (only stdint.h/stdbool.h)."
  implication: "Once gcs_global_db.cpp switches from the fictional GeniusSDK.hpp to the real GeniusSDK.h, the manual `target_include_directories(neoswarm_storage PUBLIC \"${GENIUS_SDK_DIR}/src\")` and the 4 downstream transitive-include workarounds (wallet-core, zkLLVM, evmrelay, MNN — all added solely to support GeniusSDK.hpp's assumed account/GeniusNode.hpp chain) become unnecessary and were removed from storage/CMakeLists.txt."
  timestamp: 2026-08-19T02:30:00Z

- timestamp: 2026-08-19T02:35:00Z
  checked: "storage/CMakeLists.txt's existing sgns::GeniusSDK_shared IMPORTED_LOCATION redirect block (macOS-only .dylib path check) against the actual Windows-side linking properties (IMPORTED_IMPLIB_RELEASE) in the generated GeniusSDKTargets-release.cmake."
  found: "On Windows, MSVC's linker actually consumes IMPORTED_IMPLIB_RELEASE=\"${_IMPORT_PREFIX}/lib/GeniusSDK_shared.lib\", not IMPORTED_LOCATION. The existing redirect block only ever sets IMPORTED_LOCATION* properties, and only checks for a `.dylib` file that can never exist on Windows (wrong extension/prefix/directory for this platform) — it is completely inert here and always was. It never actually explains any Windows link outcome."
  implication: "On this Windows build, rebuilding GeniusSDK.cpp is NOT enough by itself — the installed .lib/.dll copies at ${GENIUS_SDK_BUILD_DIR}/GeniusSDK/{lib,bin} must be refreshed via `cmake --install` for neoswarm_storage to link the new symbol. Confirmed and executed this explicitly rather than relying on the (inert-on-Windows) redirect mechanism."

## Eliminated

- hypothesis: "GeniusSDK.hpp exists somewhere in the GeniusSDK checkout or its thirdparty build output but is simply not on neoswarm_storage's include path (a missing target_include_directories/target_link_libraries wiring gap, in the same family as the MNN bare-target-shadowing bug and wrong llm.hpp include path found earlier this session)."
  evidence: "Exhaustive filesystem search for GeniusSDK.hpp across the GeniusSDK checkout, GeniusNetwork/thirdparty, and the CMake build tree returns zero matches anywhere. storage/CMakeLists.txt already contains correct, deliberate include-directory wiring for exactly this header (added by phase 03-01, commit bc6ab3c) pointing at the correct, verified GENIUS_SDK_DIR/src location — the wiring is not missing or wrong, the file simply is not there to be found by any wiring."
  timestamp: 2026-08-19T01:50:00Z

- hypothesis: "CommonBuildParameters.cmake's freshly-ported GeniusSDK find_package block (from this session's ~25-block port) is missing an include-directory propagation step, similar to the MNN debug session's root causes."
  evidence: "The include-directory propagation for GeniusSDK.hpp specifically was NOT part of the generic ~25-block find_package port — it's bespoke, hand-added logic already present in GNUS-NEO-SWARM's OWN src/storage/CMakeLists.txt (not the outer CommonBuildParameters.cmake), written by an earlier phase (03-01) specifically to work around GeniusSDK.hpp not being in the install include dir. That workaround is already correctly wired; it just can't work because the header it targets doesn't exist at the source-tree path either."
  timestamp: 2026-08-19T01:50:00Z

## Resolution

root_cause: "`GNUS-NEO-SWARM/src/storage/gcs_global_db.cpp` and `.hpp` `#include \"GeniusSDK.hpp\"` and call `GeniusSDKGetNode()->GetPubSub()` in `GcsGlobalDb::Initialize()` — an API that has NEVER existed anywhere in the GeniusSDK dependency (no such header, no such function, on any branch or commit, confirmed via exhaustive filesystem search and `git log --all`). This was designed and implemented in NEO-SWARM Phase 3 (plan 03-01, decisions D-15/D-16/D-16a) based on a claim — recorded in that phase's own SUMMARY.md — that the accessor was 'already on GeniusSDK develop' and that a build-tree dylib contained the symbol `__Z16GeniusSDKGetNodev`, citing commit `d550800`. That commit does not exist in the GeniusSDK repository, and the symbol/function do not exist in its source. The claim was never true or was never actually verified at the time. NEO-SWARM's own CMake wiring for this header (target_include_directories pointing at ${GENIUS_SDK_DIR}/src, plus 4 transitive-include fixes, plus a build-tree-dylib IMPORTED_LOCATION redirect for the phantom symbol) was already complete and correct for the API AS DESIGNED — it was not an include-path/propagation bug. The real capability this code needed (the running GeniusNode's pubsub) existed internally inside GeniusSDK's shared library at runtime, but was held in a translation-unit-local variable (GeniusSDK.cpp:208, anonymous namespace) with no public accessor exposed anywhere."
fix: "APPLIED (user selected Option A: add a real, narrow accessor to GeniusSDK). Two-repo change:

**GeniusSDK repo (W:\\gnus\\GeniusNetwork\\GeniusSDK — shared/vendored sibling project, user-authorized):**
- `src/GeniusSDK.h`: added `GNUS_VISIBILITY_DEFAULT void *GeniusSDKGetPubSub();` inside the existing extern-\"C\" block, immediately after `GeniusSDKGetNodeState()`, matching the header's existing plain-C, opaque-handle style (mirrors the existing `GeniusSDKFree(void *ptr)` precedent). Returns an OPAQUE handle, not a raw `GeniusNode*` or a C++ template return type — kept narrow and C-ABI-safe per the coordinator's explicit guidance, since every other NEO-SWARM/consumer integration with GeniusSDK goes through this plain-C surface only.
- `src/GeniusSDK.cpp`: implemented `GeniusSDKGetPubSub()` — takes the existing `GeniusSDKMutex` lock, returns `nullptr` if `GeniusNodeInstance` (the existing anonymous-namespace singleton) is unset, otherwise returns `static_cast<void *>(GeniusNodeInstance->GetPubSub().get())`. Matches the exact style/locking pattern of `GeniusSDKGetNodeState()`/`GeniusSDKGetTransactionManagerState()` immediately above it. No changes to `GeniusNodeInstance`'s existing encapsulation (still anonymous-namespace/internal-linkage) — only this one new function reaches into it, from within the same translation unit.

**GNUS-NEO-SWARM repo:**
- `src/storage/gcs_global_db.cpp`: `#include \"GeniusSDK.hpp\"` -> `#include \"GeniusSDK.h\"`. `Initialize()` (no-arg) now calls `GeniusSDKGetPubSub()` (returns `void*`), null-checks it once (collapsing the previous two-step node/pubsub null-check — both mapped to the same `Error::SdkNotInitialized` anyway, so behavior is unchanged), then wraps the raw pointer in a non-owning `std::shared_ptr<sgns::ipfs_pubsub::GossipPubSub>` with a no-op deleter (true ownership stays with GeniusSDK's internal node instance, whose lifetime is guaranteed by D-20 ordering to outlive this component) before delegating to the existing `Initialize(pubsub)` overload — unchanged.
- `src/storage/gcs_global_db.hpp`: updated doc comments referencing `GeniusSDKGetNode()` to `GeniusSDKGetPubSub()` (3 locations: class-level Lifecycle/Error-mapping comment, `Initialize()` production-init doc comment).
- `src/storage/CMakeLists.txt`: (1) corrected the fabricated-claim comment on the pre-existing `sgns::GeniusSDK_shared` IMPORTED_LOCATION redirect block (removed the false `d550800`/`GeniusSDKGetNode` rationale; also documented that this redirect is inert on Windows — it only handles a macOS `.dylib` path and never touches `IMPORTED_IMPLIB`, which is what MSVC's linker actually uses — so on Windows the GeniusSDK install step must be re-run manually after any GeniusSDK source change); (2) removed the now-unnecessary `target_include_directories(neoswarm_storage PUBLIC \"${GENIUS_SDK_DIR}/src\")` block and the 4 downstream transitive-include workarounds (wallet-core, zkLLVM, evmrelay, MNN_INCLUDE_DIR) that existed solely to support the fictional `GeniusSDK.hpp -> account/GeniusNode.hpp` chain — `GeniusSDK.h` has zero C++ header dependencies and is already available via `sgns::GeniusSDK_shared`'s own `INTERFACE_INCLUDE_DIRECTORIES` (confirmed installed at `${GENIUS_SDK_BUILD_DIR}/GeniusSDK/include`).

**Build/install steps executed (required on Windows since the pre-existing redirect mechanism is inert here):**
- `cmake --build W:\\gnus\\GeniusNetwork\\GeniusSDK\\build\\Windows\\Release --target GeniusSDK_shared --config Release` — succeeded.
- `cmake --build W:\\gnus\\GeniusNetwork\\GeniusSDK\\build\\Windows\\Release --target GeniusSDK --config Release` (static) — succeeded.
- `cmake --install W:\\gnus\\GeniusNetwork\\GeniusSDK\\build\\Windows\\Release --config Release` — refreshed the installed GeniusSDK.h / GeniusSDK.lib / GeniusSDK_shared.lib / GeniusSDK_shared.dll at the paths GeniusCognitiveSystem's build actually consumes.
- Confirmed via `strings` on the installed DLL that `GeniusSDKGetPubSub` is present in the export-name table alongside the pre-existing `GeniusSDKGetNodeState`.

No commits made in either repo — both left as uncommitted working-tree changes per instructions."
verification: "`cmake --build build/Windows/Release --target neoswarm_storage --config Release` from W:\\gnus\\GeniusCognitiveSystem: CMake reconfigured cleanly (picked up the changed storage/CMakeLists.txt), logged 'GeniusSDK linked to neoswarm_storage', and `gcs_global_db.cpp` now compiles PAST line 17 — the original `error C1083: Cannot open include file: 'GeniusSDK.hpp'` is CONFIRMED GONE.

The build then hit a DIFFERENT, later line in the same file: `gcs_global_db.cpp(123,45): error C2039: 'AsioSchedulerBackend' is not a member of 'libp2p::basic'` (plus 2 cascading errors) — inside the (untouched-by-this-fix) `Initialize(pubsub)` overload's 'Step 3: Local construction' block. The investigating agent's claim that this symbol 'does not exist anywhere in the installed libp2p headers' was WRONG — the coordinator's own follow-up check found it immediately: `libp2p/basic/scheduler/asio_scheduler_backend.hpp` (installed at `W:\gnus\GeniusNetwork\thirdparty\build\Windows\Release\libp2p\include\libp2p\basic\scheduler\asio_scheduler_backend.hpp`) declares `libp2p::basic::AsioSchedulerBackend` in full. `gcs_global_db.cpp` included `libp2p/basic/scheduler.hpp` and `libp2p/basic/scheduler/scheduler_impl.hpp` but never this third header — a plain missing `#include`, not a deeper libp2p/link problem. Fixed directly (one line, `#include <libp2p/basic/scheduler/asio_scheduler_backend.hpp>` added at gcs_global_db.cpp:15) and verified: `cmake --build build/Windows/Release --target neoswarm_storage --config Release` now produces `neoswarm_storage.vcxproj -> ...neoswarm_storage.lib` with zero errors.

Both the original C1083 (GeniusSDK.hpp) and this newly-surfaced AsioSchedulerBackend gap are now resolved. `neoswarm_storage` builds clean end-to-end. Checked for the same missing-include pattern elsewhere in the codebase (grep for files including scheduler_impl.hpp without asio_scheduler_backend.hpp) — none found; gcs_global_db.cpp was the only occurrence."
files_changed:
  - W:\gnus\GeniusNetwork\GeniusSDK\src\GeniusSDK.h (sibling repo — new GeniusSDKGetPubSub() declaration)
  - W:\gnus\GeniusNetwork\GeniusSDK\src\GeniusSDK.cpp (sibling repo — new GeniusSDKGetPubSub() implementation)
  - GNUS-NEO-SWARM/src/storage/gcs_global_db.cpp (GeniusSDK.h include/accessor swap, plus added missing libp2p/basic/scheduler/asio_scheduler_backend.hpp include)
  - GNUS-NEO-SWARM/src/storage/gcs_global_db.hpp
  - GNUS-NEO-SWARM/src/storage/CMakeLists.txt
