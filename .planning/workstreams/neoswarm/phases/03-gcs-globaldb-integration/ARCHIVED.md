# ARCHIVED — Phase 3 Planning Artifacts Discarded

**Date:** 2026-07-26
**Reason:** Phase 3 planned a direct RocksDB wrapper (`ReputationStorage`) instead of using SuperGenius's existing CRDT-backed `GlobalDB`. This violated the architectural principle that no NEO-SWARM code should wrap RocksDB directly — all persistent cognitive state goes through a GCS GlobalDB instance.

## What Was Wrong

1. **03-CONTEXT.md** scoped Phase 3 as "Persistence & Reliability" centered on the existing `ReputationStorage` direct RocksDB wrapper — treating it as the foundation rather than the bug
2. **03-01-PLAN.md** planned protobuf migration for `ReputationStorage` — schema work on top of the wrong storage abstraction
3. Never inspected SuperGenius `GlobalDB`/`CrdtDatastore`/`HierarchicalKey` — the existing CRDT storage infrastructure that already provides exactly what was needed
4. Reputation was planned as local-only — but reputation **must** converge across nodes via CRDT or consensus cannot work (user correction 2026-07-26)

## What's Kept (Production Code — Pending Phase 3 Rework)

- `src/reputation/reputation_storage.{hpp,cpp}` — direct RocksDB PIMPL wrapper (Open/Close/Put/PutBatch/Get/Remove/GetAll). **Slated for replacement** by GCS GlobalDB operations under `/gcs/reputation/` namespace.
- `src/reputation/reputation_crdt.*` — local simplified CRDT; superseded by GlobalDB's CRDT machinery.
- Existing reputation consumers (`src/reputation/reputation_manager.*` etc.) — their interfaces will be rewired to GlobalDB, not rewritten.

## Replacement Approach

Phase 3 regenerated as **"GCS GlobalDB Integration"**:

- Storage: dedicated `sgns::crdt::GlobalDB` instance owned by NEO-SWARM (separate from the blockchain GlobalDB buried inside GeniusSDK), with its own RocksDB directory
- Namespace: `/gcs/reputation/` via `HierarchicalKey`
- Replication: CRDT broadcast/listen topics so reputation converges across swarm nodes (required for Phase 9 consensus)
- Atomicity: `GlobalDB::BeginTransaction()` / `AtomicTransaction` replaces hand-rolled WriteBatch logic
- Acceptance: no `rocksdb::DB` references anywhere in NEO-SWARM source

## Canonical References

- `SuperGenius/src/crdt/globaldb/globaldb.hpp` — `GlobalDB::New(context, databasePath, pubsub, crdtOptions, ...)`, `Put(HierarchicalKey, Buffer, topics)`, `Get`, `Remove`, `QueryKeyValues(prefix)`, `BeginTransaction()`, topic registration, element callbacks
- `SuperGenius/src/crdt/crdt_datastore.hpp` — CRDT storage primitives
- `SuperGenius/src/crdt/hierarchical_key.hpp` — `/`-delimited key namespaces

---

*Phase 3 artifacts archived: 2026-07-26 (same audit that discarded Phase 8 artifacts)*
