# Phase 3: GCS GlobalDB Integration - Context

**Gathered:** 2026-07-27
**Status:** Approved 2026-08-03 (user) — ready for research → planning

<domain>
## Phase Boundary

Replace the direct-RocksDB `ReputationStorage` with a NEO-SWARM-owned `sgns::crdt::GlobalDB` instance (the **GCS GlobalDB**) so all persistent cognitive state flows through SuperGenius's existing CRDT storage. Phase 3 delivers the storage foundation that Phase 8 (GAML Memory, `/gcs/memory/`) and Phase 9 (Swarm Consensus, `/gcs/consensus/`) build on.

In scope for Phase 3:
- GCS GlobalDB lifecycle component (construction from `GeniusSDKGetNode()->GetPubSub()` — accessor already on GeniusSDK develop, no SDK-side work)
- GCSSDK FFI init extension — `GeniusElmInit` chain drives GeniusSDK init + GCS GlobalDB init (D-20..D-22)
- `/gcs/reputation/` namespace via `HierarchicalKey`
- CRDT broadcast/listen topics so reputation **converges across swarm nodes** (hard requirement — divergent reputation breaks Phase 9 consensus)
- Rewire existing reputation consumers (`api_server.cpp`, reputation scoring code) to GlobalDB
- Delete `reputation_storage.{hpp,cpp}`, `reputation_crdt.{hpp,cpp}`, and all direct RocksDB linkage in NEO-SWARM
- Delete `flutter_slm_bridge/` (D-24)

Out of scope (later phases):
- `/gcs/memory/` (Phase 8), `/gcs/consensus/` (Phase 9)
- Consensus logic (Phase 9)
- Graphsync-based large-object replication / IPFS-lite DAG sync tuning (Phase 8 evaluates)
</domain>

<decisions>
## Implementation Decisions

### GCS GlobalDB Instance
- **D-01:** NEO-SWARM creates and owns its own `sgns::crdt::GlobalDB` via `GlobalDB::New(...)`. The blockchain GlobalDB buried inside GeniusSDK is **untouched** — two independent instances, independent RocksDB directories, independent topics.
- **D-02:** The GCS GlobalDB gets its own database path, default `./gcs.db` (replacing `--reputation-db-path` / `m_reputationDbPath` which default to `./reputation.db`). Config field: `m_gcsDbPath`, CLI override `--gcs-db-path`.
- **D-03:** Pass `datastore = nullptr` to `GlobalDB::New` — it constructs its own RocksDB from `databasePath` (verified: `globaldb.hpp:61`, parameter doc "If not defined, created using databasePath").
- **D-04:** Factory args follow the `GeniusNode::InitDatabase()` pattern (`SuperGenius/src/account/GeniusNode.cpp:1445`): `io_context`, `databasePath`, `pubsub`, `CrdtOptions::DefaultOptions()`, graphsync network, scheduler, request-id generator, `nullptr` datastore, default `BackupOptions`.

### PubSub & Graphsync Wiring (resolved 2026-08-03)
- **D-15:** **The pubsub is `GeniusNode::GetPubSub()`** — the one `ipfs_pubsub::GossipPubSub` the in-process GeniusSDK already owns (`GeniusNode.hpp:578`, singleton instance at `GeniusSDK.cpp:164`). One host, one port, zero new network construction. Phase 3 flow is exactly: GeniusNode instantiation → `GlobalDB::New` for GCS → wire topics. Nothing else.
- **D-16:** The GCS GlobalDB component receives the pubsub `shared_ptr` (plus io_context, scheduler, graphsync network, generator) in its `Initialize()` — injected from the GeniusNode instance, never constructed locally.
- **D-16a (GeniusNode access — verified 2026-08-03):** `GeniusNodeInstance` is in an **anonymous namespace** (`GeniusSDK.cpp:164`) — symbol `__ZN12_GLOBAL__N_118GeniusNodeInstanceE` is local (`b` type) in `libGeniusSDK_shared.dylib`, NOT exported. NEO-SWARM links `sgns::GeniusSDK_shared` preferentially (`src/network/CMakeLists.txt:25`), so the singleton is unreachable via extern. **Resolution (DONE — no Phase 3 work):** GeniusSDK develop already exposes `std::shared_ptr<sgns::GeniusNode> GeniusSDKGetNode()` — implementation at `GeniusSDK.cpp:179`, exported declaration at `GeniusSDK.hpp:22` (C++ header, `GNUS_VISIBILITY_DEFAULT`), added in GeniusSDK commit `d550800 "Expose GeniusNode instance for C++ FFI consumers"`. Phase 3 consumes it; no GeniusSDK-side changes required.
- **D-17:** Graphsync network + generator construction follows GeniusNode: `graphsync::Network(pubsub->GetHost(), scheduler)` (`GeniusNode.cpp:1366`), `std::make_shared<graphsync::RequestIdGenerator>()` (`GeniusNode.cpp:252`). GlobalDB internally builds `GraphsyncImpl` + `GraphsyncDAGSyncer` on the same host (`globaldb.cpp:296-310`). **Reuse analysis (2026-08-03):** only the pubsub is publicly reusable — `GetPubSub()` is the sole relevant accessor on GeniusNode; `io_` (`:754`), `scheduler_` (`:1040`), `graphsyncnetwork_` (`:1042`), `generator_` (`:1041`) are all private with no getters. Decision: reuse pubsub via `GetPubSub()`, construct the other three locally in the GCS component (3 lines; `graphsync::Network` is just host+scheduler and GlobalDB builds its own `GraphsyncImpl` internally anyway, so there is no sharing benefit to widening the GeniusNode/SDK API with more getters).
- **D-18:** `P2PNode` is **out of Phase 3 scope entirely.** It is used only by `api_server.cpp:263-264,478` (task broadcast). Migrating it onto GeniusNode's pubsub (or deleting it) is a later decision for Phase 9 task broadcast — NOT a prerequisite for GCS GlobalDB. No changes to `p2p_node.*` in this phase.

### FFI Layering — GCSSDK wraps GeniusSDK (resolved 2026-08-03)
- **D-20:** NEO-SWARM's C FFI (`genius_elm_chat_completions.h`, the GCSSDK surface) becomes the single entry point consumers use. `GeniusElmInit` is extended to drive the full init chain: ApiServer init → SGClient init (`GeniusSDKInitWithKey`) → GCS GlobalDB component init. Consumers never call GeniusSDK directly — GCSSDK owns the ordering (SDK before GlobalDB, hard dependency per D-16a).
- **D-21:** GCS-specific FFI functions are added to the GCSSDK header as needed (e.g. status exposing GCS GlobalDB state, reputation queries for consumers). Exact function list is plan-time; the principle is FFI extension lives in GCSSDK (`genius_elm_chat_completions.h`), not by exposing GeniusSDK internals.
- **D-22 (init shape — resolved 2026-08-03):** Extend `GeniusElmInit` with optional params (single entry point; NULL = local-only stub mode, preserving current behavior). Existing `GeniusElmInit(modelPath, knowledgePath)` sets `m_enableNetwork = false` (`genius_elm_chat_completions.cpp:158`); the extended signature adds swarm config (e.g. JSON or explicit params — exact shape at plan time). Only live caller is the FFI test, which is updated in Wave 4.
- **D-23 (FFI family — resolved 2026-08-03):** `GeniusElm*` is the ONE surviving FFI family — it is the WIP CLI which will eventually be wrapped in a Flutter UI (user directive). **`GeniusSlm*` is old and deprecated** — do NOT revive, extend, or alias it. The stale `flutter_slm_bridge` Dart bindings that look up `GeniusSlmInit`/`GeniusSlmChatCompletionsCreate`/etc. will be regenerated against `GeniusElm*` when the Flutter wrapper work happens (not Phase 3 scope). **Consumer inventory:** the only live `GeniusElm*` consumer is `test/ffi/test_genius_elm_ffi.cpp` (stub-mode init, idempotent re-init expectations) — no other app links the FFI today, so D-22's compat constraint is the FFI test only. Note: `genius_elm_chat_c.cpp` (unreferenced stub impl of the same header, not in any CMakeLists) is NOT dead — it's the WIP CLI entry; it stays.
- **D-24 (flutter_slm_bridge deletion — confirmed 2026-08-03):** Delete `flutter_slm_bridge/` entirely. It is an abandoned parallel attempt (Subaskar, 2026-05) that violates the architecture three ways: (1) references a `GeniusSlm*` FFI family that was never implemented (its ffigen entry-point `src/genius_slm_chat_c.h` doesn't exist in the repo); (2) wired to a `GeniusAPIServer` class that does not exist anywhere in the architecture; (3) treats the GCS API as a linkable C++ object. Per MASTER_ARCHITECTURE (`documentation/docs/technical-information/MASTER_ARCHITECTURE.md:50,348,483-495`), the GCS API is an **OpenAI-compatible orchestration ingress boundary** — remote clients reach it through an edge proxy (Cloudflare or similar), and embedded Flutter uses the GCSSDK `GeniusElm*` FFI directly. Not referenced by any CMakeLists; native shim is a 1-line include of an empty header. When the Flutter wrapper is built, fresh ffigen bindings are generated against `genius_elm_chat_completions.h`.

### Namespacing & Key Layout
- **D-05:** All GCS keys live under the `/gcs/` HierarchicalKey root. Phase 3 uses `/gcs/reputation/<node_identity_key>` — one key per node reputation record (replaces `ReputationStorage`'s flat `identity_key` string keys).
- **D-06:** `GetAll()` (currently a full RocksDB iterator in `reputation_storage.cpp:187`) becomes `GlobalDB::QueryKeyValues("/gcs/reputation/")` — tombstone-aware prefix query, verified in the GlobalDB API.

### CRDT Convergence for Reputation
- **D-07:** Reputation writes use a dedicated CRDT broadcast topic (e.g. `"gcs-reputation"`). Topic wiring at component init, per `globaldb.cpp`: `AddListenTopic(topic)` — subscribes the broadcaster AND registers the name in the CRDT datastore (`AddTopicName`) so incoming deltas merge — plus `AddBroadcastTopic(topic)` so local `Put`s publish. Every node does both; that's what makes reputation converge. Reputation MUST converge across nodes — divergent reputation makes Phase 9 weighted consensus meaningless (user directive 2026-07-26).
- **D-08:** Incoming remote reputation updates are surfaced through `RegisterNewElementCallback` / `RegisterDeletedElementCallback` filtered on the `/gcs/reputation/` prefix, so local consumers (scoring, consensus weight tables) react to convergence without polling.

### ReputationStorage & Local CRDT Removal
- **D-09:** Delete `src/reputation/reputation_storage.{hpp,cpp}` outright — no adapter shim, no "keep it behind an interface." The class IS the architectural bug; the fix is replacement, not wrapping. Consumers (`api_server.cpp:124,137`) are rewired to the GCS GlobalDB component.
- **D-19:** Delete `src/reputation/reputation_crdt.{hpp,cpp}` (user directive 2026-08-03: "we don't need that at all, it's stored in GlobalDB which is autosynced"). Any convergence behavior it provided is inherited from GlobalDB's CRDT machinery + topics. Callers of `ReputationCRDT` are rewired to the GCS GlobalDB component's typed ops.
- **D-10:** Remove all direct RocksDB linkage from NEO-SWARM CMake: `src/reputation/CMakeLists.txt:18-21`, `src/memory/CMakeLists.txt:17-21`, `src/core/CMakeLists.txt:113`. RocksDB still arrives **transitively** via SuperGenius libs — that's fine; the constraint is no direct `rocksdb::DB` use in NEO-SWARM source (ROADMAP constraint #9).
- **D-11:** Serialization of `NodeReputation` for storage moves to the format GlobalDB consumers use (protobuf or Buffer-encoded, decided at plan time from `reputation_scoring` needs) — NOT a hand-rolled RocksDB `WriteBatch` (that's what `reputation_storage.cpp:210` does today).

### Component Shape
- **D-12:** New component `src/storage/gcs_global_db.{hpp,cpp}` (+ CMake target `neoswarm_storage`) owns the GlobalDB shared_ptr, topic registration, and callback wiring. Exposes narrow typed operations (`PutReputation`, `GetReputation`, `QueryReputations`) — callers never touch `HierarchicalKey` or `Buffer` directly. Program-to-interface per project design rules.
- **D-13:** Construction is deferred/init-style (like `SGClient::Initialize()`), not constructor-does-everything — `GlobalDB::New` + `Start()` can fail and must surface `outcome::result`, never throw.

### Error Handling
- **D-14:** All operations return `outcome::result<T>` with specific codes from `src/common/error.hpp`. Map GlobalDB's `Error` enum (`globaldb.hpp:80-89`) to NEO-SWARM error codes at the component boundary. No `(void)` discards of results.

### OpenCode's Discretion
- Exact topic string name(s)
- Buffer serialization detail for `NodeReputation`
- Where `RegisterElementFilter` predicates live (inside component vs. passed in)
- io_context ownership (shared with existing node loop vs. dedicated thread) — follow what `SGClient`/`P2PNode` already do
</decisions>

<specifics>
## Specific Ideas

- "It should have never wrapped RocksDB directly ever" — `ReputationStorage` is deleted, not salvaged
- "Reputation cannot be divergent or else it doesn't work for consensus" — CRDT topics are Phase 3 scope, NOT deferred
- GCS GlobalDB is the single persistence home for Phases 3, 8, 9 — one instance, three namespaces
- Two-GlobalDB separation: blockchain state (GeniusSDK) vs. cognitive state (NEO-SWARM) never share a store
</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### SuperGenius CRDT API (verified 2026-07-26/27)
- `../SuperGenius/src/crdt/globaldb/globaldb.hpp` — factory + full API surface (Put/Get/Remove/QueryKeyValues/BeginTransaction/topics/callbacks)
- `../SuperGenius/src/crdt/crdt_datastore.hpp` — CRDT storage primitives, filter/new/deleted callback types
- `../SuperGenius/src/crdt/hierarchical_key.hpp` — `/`-delimited key namespaces, `ChildString()`
- `../SuperGenius/src/crdt/atomic_transaction.hpp` — batch/transaction API
- `../SuperGenius/src/account/GeniusNode.cpp:1440-1465` — canonical `GlobalDB::New` + `Start()` construction pattern
- `../SuperGenius/src/migration/Migration1_0_0To3_4_0.cpp:220` — second construction example (simpler, no backup options)
- `../thirdparty/ipfs-pubsub/src/ipfs_pubsub/gossip_pubsub.hpp` — `GossipPubSub` constructors (needed by factory)

### NEO-SWARM code being replaced/rewired
- `src/reputation/reputation_storage.{hpp,cpp}` — the direct RocksDB wrapper to delete
- `src/reputation/reputation_crdt.{hpp,cpp}` — local simplified CRDT, deleted (D-19); GlobalDB autosync replaces it
- `src/api/api_server.cpp:124` + `api_server.hpp:137` — sole production consumer of `ReputationStorage`
- `src/reputation/reputation_scoring.{hpp,cpp}`, `weighted_consensus.{hpp,cpp}`, `node_reputation.hpp` — data model consumers (interfaces preserved where possible)
- `../SuperGenius/src/account/GeniusNode.hpp:578` — `GetPubSub()` accessor (source of the shared pubsub)
- `../GeniusSDK/src/GeniusSDK.cpp:164` — in-process GeniusNode singleton

### Planning context
- `.planning/workstreams/neoswarm/ROADMAP.md` § Phase 3 + constraint #9
- `.planning/workstreams/neoswarm/REQUIREMENTS.md` — PERS-01..03, NET-02
- `phases/03-gcs-globaldb-integration/ARCHIVED.md` — why the prior approach was discarded
- `../../documentation/docs/technical-information/MASTER_ARCHITECTURE.md` — system boundaries: GeniusSDK native API boundary (§:120,219), GCS OpenAI-compatible orchestration ingress (§:50,348,483-495). Authoritative for "which layer owns what" questions.
</canonical_refs>

<open_questions>
## Open Questions for Research (NOT decided here)

- **Q-01 (test fixture):** Find SuperGenius's existing GlobalDB/CRDT test harness (likely under `SuperGenius/test/` — look for test pubsub fixtures, `GlobalDB::New` in tests) to reuse for Phase 3 unit tests. Must use wait-condition templates, never `sleep_for`.
- **Q-02 (FFI init shape):** New-variant vs. optional-params for the swarm-enabled init (D-22). Only live caller is the FFI test — decide at plan time from API cleanliness, not consumer pressure.
</open_questions>
