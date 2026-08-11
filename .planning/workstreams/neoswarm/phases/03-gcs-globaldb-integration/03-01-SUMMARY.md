---
phase: 03-gcs-globaldb-integration
plan: 01
subsystem: storage
tags: [crdt, globaldb, lifecycle, phase-3, d-01..d-17]
dependency_graph:
  requires:
    - sgns::crdt_globaldb (SuperGenius)
    - sgns::GeniusSDK_shared with GeniusSDKGetNode (GeniusSDK d550800+)
    - neoswarm_common, neoswarm_proto
  provides:
    - neoswarm_storage library target
    - sgns::neoswarm::storage::GcsGlobalDb (init-style lifecycle component)
    - Error::GcsDbError (22), Error::SdkNotInitialized (23)
    - test_gcs_global_db binary (4 lifecycle tests)
  affects:
    - Phase 8 (/gcs/memory/) and Phase 9 (/gcs/consensus/) build on this component
tech_stack:
  added:
    - sgns::crdt::GlobalDB consumption via factory + injected pubsub
    - soralog LoggingSystem test fixture (SetUpTestSuite)
    - condition_variable wait-condition template for tests
  patterns:
    - Init-style lifecycle (constructor = config store only, fallible work in Initialize)
    - Test seam via Initialize(pubsub) overload — production no-arg delegates
    - Boundary error mapping (GlobalDB::Error → Error::GcsDbError via std::error_code)
key_files:
  created:
    - src/storage/gcs_global_db.hpp
    - src/storage/gcs_global_db.cpp
    - src/storage/CMakeLists.txt
    - test/storage/test_gcs_global_db.cpp
  modified:
    - src/common/error.hpp (added GcsDbError=22, SdkNotInitialized=23)
    - src/common/error.cpp (added switch cases — resolves -Wswitch warning)
    - src/CMakeLists.txt (add_subdirectory storage)
    - test/CMakeLists.txt (register test_gcs_global_db)
decisions:
  - "Test seam: Initialize(pubsub) overload documented as test fixture path; production no-arg Initialize() acquires pubsub via GeniusSDKGetNode and delegates (per RESEARCH guidance — pubsub is the only injected dependency)"
  - "Double Initialize returns Error::GcsDbError (programmer error surfaced, not silent no-op)"
  - "Backups disabled via default BackupOptions{} (GCS CRDT backup policy independent of blockchain GlobalDB per D-01)"
  - "CMake redirect of sgns::GeniusSDK_shared IMPORTED_LOCATION to build-tree dylib — the install-prefix dylib predates GeniusSDKGetNode (d550800) and breaks the link"
metrics:
  duration_minutes: 22
  completed: 2026-08-11
  tasks: 3
  files_created: 4
  files_modified: 4
---

# Phase 3 Plan 01: GCS GlobalDB Component Skeleton Summary

**One-liner:** NEO-SWARM-owned `sgns::crdt::GlobalDB` lifecycle component (`GcsGlobalDb`) with init-style construction, shared pubsub from `GeniusSDKGetNode()->GetPubSub()`, locally-built io/scheduler/graphsync/generator, `gcs-reputation` topic wiring, and a 4-test lifecycle suite using the wait-condition template.

## What Was Built

- `src/storage/gcs_global_db.{hpp,cpp}` — the `GcsGlobalDb` component. Constructor stores `Config` only (D-13); `Initialize()` runs the 7-step init chain (pubsub acquisition → local io_context/scheduler/graphsync::Network/RequestIdGenerator → `GlobalDB::New` with `nullptr` datastore + default `BackupOptions{}` → `Start()` → `AddListenTopic` + `AddBroadcastTopic` for `gcs-reputation` → io thread spawn). `Shutdown()` is idempotent and joins the io thread.
- `src/storage/CMakeLists.txt` — `neoswarm_storage` STATIC library. Hard-required linkage on `sgns::crdt_globaldb` and `sgns::GeniusSDK_shared` (configure-time FATAL_ERROR if absent, per project Conditional Compilation rule). Adds include paths for ipfs-pubsub, ipfs-lite-cpp, libp2p, boost, GeniusSDK source tree, wallet-core, zkLLVM, evmrelay, MNN (transitive `GeniusNode.hpp` deps).
- `src/common/error.hpp` — appended `GcsDbError = 22` and `SdkNotInitialized = 23` after `NotLoaded = 21`. Existing values preserved (Boost.Outcome registration is load-bearing).
- `src/common/error.cpp` — added switch cases for the two new codes (resolves `-Wswitch` warning introduced by error.hpp change).
- `test/storage/test_gcs_global_db.cpp` — 4 TEST_F cases: default-constructed inert, SDK-missing fails with `SdkNotInitialized`, full lifecycle with injected port-0 `GossipPubSub` (db directory appears on disk under wait-condition), double-init rejected with `GcsDbError`. All waits use a `condition_variable::wait_for` polling idiom with bounded `kPollInterval{ 10 }` — zero `std::this_thread::sleep_for` anywhere.
- `test/CMakeLists.txt` — `test_gcs_global_db` registered after `test_reputation`.

## Test Results

```
[==========] 4 tests from 1 test suite ran. (3327 ms total)
[  PASSED  ] 4 tests.
```

Regression check: `test_reputation` (16 tests) still passes.

## Commits

| Hash | Type | Message |
|------|------|---------|
| `0bb1d7e` | feat | wire neoswarm_storage CMake target and Phase 3 GCS error codes |
| `bc6ab3c` | feat | implement GcsGlobalDb init-style lifecycle component |
| `7b98fce` | test | lifecycle tests for GcsGlobalDb using Tier 2 fixture + wait-condition template |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking] GeniusSDK install-prefix dylib predates `GeniusSDKGetNode` (d550800)**
- **Found during:** Task 3 link
- **Issue:** The imported `sgns::GeniusSDK_shared` target points at `${GENIUS_SDK_BUILD_DIR}/GeniusSDK/lib/libGeniusSDK_shared.dylib` (built Jul 23). The newer dylib at `${GENIUS_SDK_BUILD_DIR}/src/libGeniusSDK_shared.dylib` (built Aug 3, includes d550800) contains the `__Z16GeniusSDKGetNodev` symbol. Without the newer dylib the test fails to link with `Undefined symbols: GeniusSDKGetNode`.
- **Fix:** In `src/storage/CMakeLists.txt`, when the build-tree dylib exists, override `IMPORTED_LOCATION` on `sgns::GeniusSDK_shared` to point at it. This keeps the change local to NEO-SWARM (does not modify the GeniusSDK repo or its install prefix) and self-heals when the user next runs `ninja install` in GeniusSDK (the install-prefix dylib will then match).
- **Files modified:** `src/storage/CMakeLists.txt`
- **Commit:** `7b98fce`

**2. [Rule 2 — Missing critical functionality] soralog LoggingSystem not initialized in test fixture**
- **Found during:** Task 3 first run
- **Issue:** `GossipPubSub` construction asserts `libp2p::log::setLoggingSystem()` has been called. The SuperGenius `globaldb_integration.cpp` fixture handles this in `SetUpTestSuite`; our test fixture did not.
- **Fix:** Added `static void SetUpTestSuite()` to `GcsGlobalDbTest` that builds a minimal `soralog::LoggingSystem` from an inline YAML config and registers it via `libp2p::log::setLoggingSystem`.
- **Files modified:** `test/storage/test_gcs_global_db.cpp`
- **Commit:** `7b98fce`

**3. [Rule 1 — Bug] `-Wswitch` warning in `src/common/error.cpp`**
- **Found during:** Task 2 build (warning emitted after Task 1 added new enum values)
- **Issue:** The `OUTCOME_CPP_DEFINE_CATEGORY_3` switch on `Error` did not handle `GcsDbError` or `SdkNotInitialized`.
- **Fix:** Added two case arms returning the appropriate message strings.
- **Files modified:** `src/common/error.cpp`
- **Commit:** `bc6ab3c`

**4. [Rule 1 — Bug] `outcome::result<shared_ptr<GlobalDB>>::error()` returns `std::error_code`, not `GlobalDB::Error`**
- **Found during:** Task 2 first compile
- **Issue:** Plan pseudocode `static_cast<unsigned>( dbResult.error() )` does not compile — outcome wraps enum errors as `std::error_code`.
- **Fix:** Added `ExtractGlobalDbError( const std::error_code& )` helper that recovers the enum value via `ec.value()`. Log line uses `dbError.message()` for readability and `dbError.value()` for the enum int.
- **Files modified:** `src/storage/gcs_global_db.cpp`
- **Commit:** `bc6ab3c`

**5. [Rule 3 — Blocking] Header-path corrections during Task 2**
- **Found during:** Task 2 first compile
- **Issue:** Plan referenced `ipfs_lite/ipfs/graphsync/impl/network.hpp` and `impl/request_id_generator.hpp`. Actual locations are `impl/network/network.hpp` and `impl/local_requests.hpp`.
- **Fix:** Corrected include paths.
- **Files modified:** `src/storage/gcs_global_db.cpp`
- **Commit:** `bc6ab3c`

**6. [Rule 2 — Missing critical functionality] `GeniusSDK.hpp` not in install include dir**
- **Found during:** Task 2 first compile
- **Issue:** The C++ header (added in d550800) is not installed to `${GENIUS_SDK_BUILD_DIR}/GeniusSDK/include` (only the C header `GeniusSDK.h` is). `#include "GeniusSDK.hpp"` failed.
- **Fix:** Added `${GENIUS_SDK_DIR}/src` to the target's include directories (consume from source tree). This is consistent with the way `GeniusSDK.hpp` is currently consumed — the install rule update is a GeniusSDK-side concern.
- **Files modified:** `src/storage/CMakeLists.txt`
- **Commit:** `bc6ab3c`

**7. [Rule 3 — Blocking] Cascading transitive include paths for `GeniusNode.hpp`**
- **Found during:** Task 2 compile iterations
- **Issue:** `GeniusSDK.hpp` includes `account/GeniusNode.hpp`, which transitively requires WalletCore (`wallet-core/include`), crypto3 (`${ZKLLVM_BUILD_DIR}/zkLLVM/include`), evmrelay (`${SUPERGENIUS_BUILD_DIR}/SuperGenius/include/evmrelay`), and MNN (`${MNN_INCLUDE_DIR}`) headers. None of these flow through the imported targets' `INTERFACE_INCLUDE_DIRECTORIES` because the corresponding targets are stubs (`INTERFACE IMPORTED`) in `cmake/CommonBuildParameters.cmake`.
- **Fix:** Added the four include directories explicitly to `neoswarm_storage`. Each addition is documented with the header chain that requires it.
- **Files modified:** `src/storage/CMakeLists.txt`
- **Commit:** `bc6ab3c`

## Auth Gates
None.

## Threat Flags
None — no new network endpoints, auth paths, file access patterns, or schema changes beyond what the plan's `<threat_model>` registers (T-03-01..T-03-04 all mitigated per plan).

## Known Stubs
None — no hardcoded empty values, placeholder text, or unwired data sources in the plan's deliverables. The component is functional end-to-end against a real GossipPubSub.

## Acceptance Criteria Met

- [x] `Error::GcsDbError` (22) and `Error::SdkNotInitialized` (23) added without renumbering existing codes
- [x] `neoswarm_storage` target builds; configure fails hard when `sgns::crdt_globaldb` or GeniusSDK targets are absent
- [x] `GcsGlobalDb` constructor stores config only (D-13); `Initialize()` performs all fallible work
- [x] PubSub acquired via `GeniusSDKGetNode()->GetPubSub()` with null-checks at both steps (D-15/D-16/D-16a)
- [x] io_context, scheduler, graphsync::Network, RequestIdGenerator constructed locally per D-17
- [x] `GlobalDB::New` receives `datastore = nullptr` (D-03) and default BackupOptions, following GeniusNode::InitDatabase pattern (D-04)
- [x] `gcs-reputation` topic wired with AddListenTopic + AddBroadcastTopic (D-07)
- [x] GlobalDB::Error mapped to NEO-SWARM codes at the boundary (D-14); no `(void)` discards
- [x] 4 lifecycle tests pass using wait-condition template; zero `sleep_for` in component and test
- [x] No changes to api_server.cpp/hpp, reputation/*, or any consumer (rewiring is Wave 3)

## Self-Check: PASSED

- FOUND: `src/storage/gcs_global_db.hpp`
- FOUND: `src/storage/gcs_global_db.cpp`
- FOUND: `src/storage/CMakeLists.txt`
- FOUND: `test/storage/test_gcs_global_db.cpp`
- FOUND: commit `0bb1d7e` (Task 1)
- FOUND: commit `bc6ab3c` (Task 2)
- FOUND: commit `7b98fce` (Task 3)
- Test binary `test/test_gcs_global_db` runs and passes 4/4 tests.
