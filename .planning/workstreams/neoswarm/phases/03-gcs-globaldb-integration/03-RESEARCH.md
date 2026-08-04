# Phase 3: GCS GlobalDB Integration — Research

**Date:** 2026-08-03
**Status:** Complete
**Context:** `03-CONTEXT.md` (approved 2026-08-03)

<research_summary>
## Summary

All open questions from the approved CONTEXT are resolved. SuperGenius has a complete, reusable GlobalDB test harness with two tiers (in-process CrdtDatastore unit tests with mock broadcaster/DAGSyncer, and full GlobalDB integration tests with real GossipPubSub on port 0). The wait mechanism is `waitForCondition`/`assertWaitForCondition` polling — **but it uses `std::this_thread::sleep_for` internally, which violates NEO-SWARM's testing discipline**; the pattern must be adapted to the project's wait-condition templates (condition_variable), not copied verbatim.
</research_summary>

<canonical_references>
## Canonical References (verified)

### SuperGenius CRDT test harness
- `../SuperGenius/test/src/crdt/globaldb_integration.cpp` — full GlobalDB integration fixture (`TestNodeCollection`, lines 64-188; `addNode` 85-125; `connectNodes` 127-154; teardown 166-184; logging setup 190-211)
- `../SuperGenius/test/src/crdt/crdt_datastore_test.cpp` — CrdtDatastore unit tests with mocks (fixture 46-78)
- `../SuperGenius/test/src/crdt/crdt_mirror_broadcaster.{hpp,cpp}` — `CRDTMirrorBroadcaster` loopback broadcaster with `SetMirrorCounterPart()`
- `../SuperGenius/test/src/crdt/crdt_custom_broadcaster.{hpp,cpp}` — `CustomBroadcaster` fire-and-forget queue mock
- `../SuperGenius/test/src/crdt/crdt_custom_dagsyncer.{hpp,cpp}` — `CustomDagSyncer` in-memory MerkleDag mock
- `../SuperGenius/test/testutil/storage/base_crdt_test.{hpp,cpp}` — reusable `CRDTFixture` (real GossipPubSub on port 40001)
- `../SuperGenius/test/testutil/wait_condition.hpp:75-99` — `assertWaitForCondition`
- `../SuperGenius/src/base/util.hpp:236-257` — `waitForCondition` template

### SuperGenius CRDT production API (from CONTEXT, unchanged)
- `../SuperGenius/src/crdt/globaldb/globaldb.hpp` — factory + API
- `../SuperGenius/src/account/GeniusNode.cpp:1445` — canonical `GlobalDB::New` usage
- `../SuperGenius/src/account/GeniusNode.hpp:578` — `GetPubSub()` (only relevant public accessor)

### NEO-SWARM
- `src/reputation/reputation_storage.{hpp,cpp}`, `reputation_crdt.{hpp,cpp}` — to delete
- `src/api/api_server.cpp:124`, `api_server.hpp:137` — sole `ReputationStorage` consumer
- `test/ffi/test_genius_elm_ffi.cpp` — only live FFI consumer
</canonical_references>

<findings>
## Findings

### Q-01: Test fixture (RESOLVED)

Two reusable tiers exist in SuperGenius:

**Tier 1 — CrdtDatastore unit tests (no network, fastest).** Construct `CrdtDatastore` directly with `InMemoryDatastore` + `CustomDagSyncer` + `CRDTMirrorBroadcaster` — no GossipPubSub, no io_context:
```cpp
// crdt_datastore_test.cpp:46-78
db_ = rocksdb::create(databasePath, options);
ipfsDataStore_ = std::make_shared<InMemoryDatastore>();
dagSyncer_ = std::make_shared<CustomDagSyncer>(ipfsDataStore_);
broadcaster_ = std::make_shared<CRDTMirrorBroadcaster>();
crdtDatastore_ = CrdtDatastore::New(db_, namespaceKey_, dagSyncer_, broadcaster_, CrdtOptions::DefaultOptions());
```
Two instances wired via `broadcaster1->SetMirrorCounterPart(broadcaster2)` simulate replication. Link: `crdt_datastore`, `crdt_globaldb_proto`, `rocksdb`, `ipfs-lite-cpp::ipfs_datastore_in_memory`.

**Tier 2 — GlobalDB integration tests (real libp2p).** Real `GossipPubSub` started on **port 0** (random free port, no conflicts), own io_context + scheduler + graphsync Network + generator, `GlobalDB::New(...)`, `io->run()` on a thread, nodes connected via `pubsub->AddPeers(...)`. From `globaldb_integration.cpp:86-124`. Link: `crdt_globaldb`.

**⚠️ Adaptation required:** SuperGenius tests wait via `waitForCondition` (`util.hpp:236-257`), which polls with `std::this_thread::sleep_for(check_interval)`. NEO-SWARM testing discipline forbids `sleep_for` in tests — the condition-variable-based wait-condition template must be used instead. The *predicate* patterns (poll `db->Get(key).has_value()` until replicated; `EXPECT_FALSE(waitForCondition(...))` for non-replication) transfer directly; the *wait mechanism* does not.

`PubSubBroadcasterExt` has no isolated unit test — it's exercised implicitly through GlobalDB integration tests. No action needed for Phase 3.

### Q-02: FFI init shape (ANALYSIS — decision at plan time)

Only live consumer of `GeniusElmInit(modelPath, knowledgePath)` is `test/ffi/test_genius_elm_ffi.cpp` (stub-mode init `GeniusElmInit(nullptr,nullptr)`, idempotent re-init ×3, shutdown/re-init cycle). No Dart/CLI/app links the FFI today.

Options:
- **(a) New variant** `GeniusElmInitWithSwarm(modelPath, knowledgePath, swarmConfigJson)` — existing init untouched (network stays off), swarm path explicit, test-compatible by construction. Cleanly expresses the D-20 init chain (ApiServer → GeniusSDK → GCS GlobalDB).
- **(b) Optional params** on `GeniusElmInit` — C ABI callers pass NULL; breaks source compat for anyone with the old 2-arg declaration (none exist outside the test, which is updated either way).

Lean (a): FFI functions are cheap, the two modes (local-only vs. swarm) are semantically distinct, and it avoids overloading a 2-arg signature with swarm config it never had. Final call at plan time.

### GeniusSDK dependency (from CONTEXT D-16a, confirmed)

`GeniusNodeInstance` is anonymous-namespace — symbol `__ZN12_GLOBAL__N_118GeniusNodeInstanceE` is local (`b` type) in `libGeniusSDK_shared.dylib`, not exported. NEO-SWARM links `sgns::GeniusSDK_shared` preferentially (`src/network/CMakeLists.txt:25`). Required GeniusSDK-side addition (separate commit in GeniusSDK repo):

```cpp
// GeniusSDK.cpp — outside the anonymous namespace
std::shared_ptr<sgns::GeniusNode> GeniusSDKGetNode()
{
    const std::lock_guard<std::recursive_mutex> lock( GeniusSDKMutex );
    return GeniusNodeInstance;
}
```
With a `GNUS_VISIBILITY_DEFAULT` declaration in `GeniusSDK.h`. Returns shared_ptr copy under the existing mutex; one GeniusNode regardless of static/shared link mode.

### GeniusNode member reuse (from CONTEXT D-17, confirmed)

Only `GetPubSub()` is public. `io_` (`GeniusNode.hpp:754`), `scheduler_` (`:1040`), `graphsyncnetwork_` (`:1042`), `generator_` (`:1041`) are private, no getters. GCS component constructs the last three locally (mirroring `GeniusNode.cpp:1366` + `:252`); reuses pubsub via `GeniusSDKGetNode()->GetPubSub()`.

### RocksDB removal blast radius (confirmed by grep)

- `src/reputation/CMakeLists.txt:18-21` — direct `RocksDB::rocksdb`/`rocksdb` link
- `src/memory/CMakeLists.txt:17-21` — same pattern
- `src/core/CMakeLists.txt:113` — `find_library(_ROCKSDB_LIB rocksdb ...)`
- `src/reputation/reputation_storage.cpp:10-13` — `rocksdb/db.h`, `options.h`, `slice.h`, `write_batch.h` includes
- `src/api/api_server.cpp:124` + `api_server.hpp:137` — `ReputationStorage` construction/member

RocksDB remains available transitively via `crdt_globaldb` — constraint #9 bans *direct* use in NEO-SWARM source only.
</findings>

<implementation_guidance>
## Implementation Guidance (for planner)

### Suggested wave structure

1. **Wave 1 — GeniusSDK accessor + GCS component skeleton.** Add `GeniusSDKGetNode()` to GeniusSDK (separate commit/PR in that repo). Create `src/storage/gcs_global_db.{hpp,cpp}` + `neoswarm_storage` CMake target with init-style lifecycle (`Initialize(pubsub, io, config)` → `GlobalDB::New` → `Start` → topic wiring → `Shutdown`). No consumers rewired yet.
2. **Wave 2 — Reputation on GlobalDB.** Typed ops (`PutReputation`/`GetReputation`/`QueryReputations`) under `/gcs/reputation/<node_key>`; `NodeReputation` Buffer serialization; CRDT listen+broadcast topic `gcs-reputation`; element callbacks for convergence. Unit tests (Tier 1 pattern adapted to wait-condition templates).
3. **Wave 3 — Consumer rewiring + deletion.** Rewire `api_server.cpp:124,137` to the GCS component; delete `reputation_storage.*`, `reputation_crdt.*`; strip the 3 direct RocksDB CMake linkages; delete `flutter_slm_bridge/` (D-24).
4. **Wave 4 — FFI + integration.** GCSSDK init chain extension (D-20/D-22, likely `GeniusElmInitWithSwarm`); FFI test updates; GlobalDB integration test (Tier 2 pattern, two-node reputation convergence) adapted to wait-condition templates.

### Acceptance tests (from CONTEXT + audit lessons)

- No `rocksdb::DB` / `#include <rocksdb/` anywhere in NEO-SWARM `src/` (grep gate)
- No direct RocksDB linkage in any NEO-SWARM CMakeLists
- `ReputationStorage`/`ReputationCRDT` symbols gone
- GCS GlobalDB constructs from `GeniusSDKGetNode()->GetPubSub()` — no second pubsub/host/port
- Reputation Put on node A observable via `Get` on node B (two-instance convergence test, wait-condition template, no `sleep_for`)
- All keys under `/gcs/` root

### Constraints

- C++17 ceiling; `outcome::result<T>` with specific error codes; no `(void)` discards; no exceptions in hot paths (`noexcept` by default)
- Init-style lifecycle (constructor stores config; `Initialize()` does fallible work)
- No `#ifdef` platform gates; no magic numbers; spdlog logging
- GeniusSDK change is a separate commit/PR in the GeniusSDK repo — do not mix into NEO-SWARM commits
</implementation_guidance>
