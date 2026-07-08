# Phase 3: Persistence & Reliability - Context

**Gathered:** 2026-07-06
**Status:** Ready for planning

<domain>
## Phase Boundary

Reputation data survives restarts via RocksDB with protobuf binary serialization and atomic writes. Replace JSON serialization with protobuf, add crash-safe WriteBatch, and ensure corrupt data recovery. JSON config with CLI override already works — no changes needed for that success criterion.
</domain>

<decisions>
## Implementation Decisions

### Protobuf Schema
- **D-01:** Use existing `NodeReputationProto` from `proto/genius_reputation.proto`. All 8 fields (identity_key, global_score, math_score, grammar_score, latency_score, consistency_score, task_count, last_updated_ms) already defined and compiled.
- **D-02:** No new proto file needed. Replace `nlohmann::json` serialization with `NodeReputationProto::SerializeToArray()` / `ParseFromArray()`.

### Migration Strategy
- **D-03:** Wipe and rebuild. No backward compatibility code for old JSON records. Reputation scores are recalculable from scratch.
- **D-04:** Delete old `reputation.db/` directory on first protobuf Open(). Log warning, start fresh.

### Atomic Writes
- **D-05:** Single-key writes use `rocksdb::WriteOptions().sync = true` for crash safety per record.
- **D-06:** Bulk writes use `rocksdb::WriteBatch`. Add `PutBatch(const std::vector<NodeReputation>&)` for atomic multi-record updates (e.g., scoring round).
- **D-07:** `WriteBatch` is committed with `sync=true`. On failure, no partial writes.

### OpenCode's Discretion
- Exact protobuf buffer size allocation
- WriteBatch error handling (rollback on partial failure)
- Whether to expose `PutBatch` or `PutAll` naming
</decisions>

<canonical_refs>
## Canonical References

### Protobuf Schema
- `proto/genius_reputation.proto` — NodeReputationProto message (8 fields), already compiled in build

### Existing Code
- `src/reputation/reputation_storage.hpp` — Public interface (Open, Put, Get, Remove, GetAll, IsOpen)
- `src/reputation/reputation_storage.cpp` — Current JSON serialization, RocksDB CRUD
- `src/reputation/node_reputation.hpp` — NodeReputation struct definition
- `src/reputation/CMakeLists.txt` — Library target, already links RocksDB

### Requirements
- `.planning/workstreams/neoswarm/REQUIREMENTS.md` — PERS-01, PERS-02, PERS-03, PERS-04
</canonical_refs>

<code_context>
## Existing Code Insights

### What stays
- RocksDB CRUD operations (Open, Get, Remove, GetAll, Close) — unchanged
- PIMPL pattern, error handling, logging — unchanged
- ReputationStorage interface — add PutBatch, no other changes

### What changes
- Serialize() → protobuf binary (was JSON)
- Deserialize() → protobuf parse (was JSON). Corrupt data returns empty record (PERS-02).
- Put() → add sync=true to WriteOptions
- New: PutBatch() with WriteBatch + sync

### Established Patterns
- outcome::result<T> for all error propagation
- PIMPL idiom, m_ prefix, Allman braces, C++17
- RocksDB linked unconditionally (no #ifdef)
</code_context>

<deferred>
## Deferred Ideas

- Backward compatibility for old JSON DB — n/a (wipe and rebuild)
- CRDT sync proto integration (delta.proto, heads.proto) — Phase 9 (Swarm Networking)
- ReputationMigration tool — future if needed
</deferred>

---

*Phase: 03-persistence-reliability*
*Context gathered: 2026-07-06*
