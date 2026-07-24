# Phase 08: Agentic Memory (GAML v1) — Research

**Researched:** 2026-07-23
**Domain:** Structured long-term memory with RocksDB persistence for an ELM-based inference engine
**Confidence:** HIGH

## Summary

Phase 08 adds structured agentic memory to GNUS-NEO-SWARM. A 5-type `MemoryObject` model on a `CognitiveAsset` base struct replaces stateless inference. A standalone `MemoryGovernor` performs heuristic retrieval between prompt analysis and ELM chain execution. A 3-stage ingestion pipeline (Fact Extraction → Context Mapping → Write Evaluation) converts ELM outputs into scored memory facts. All objects persist to a dedicated RocksDB `memory.db` with a hierarchical key schema enabling prefix range scans without secondary indexes.

The codebase provides rich reusable patterns: `ReputationStorage` demonstrates the exact RocksDB Pimpl/Open/Close/Put/PutBatch pattern needed. `ReputationCRDT` provides the LWW-CRDT merge pattern for Phase 9 readiness. `KnowledgeRetrieval` and `ContextInjection` show how structured facts are retrieved and injected into prompts — the same injection flow that `MemoryGovernor` must follow. `ApiServer::Process()` and `ELMChainBuilder::Build()` have well-defined integration hooks. The existing test infrastructure (Google Test + `neoswarm_test` CMake macro) supports adding memory tests with zero new dependencies.

**Primary recommendation:** Clone the `ReputationStorage` Pimpl pattern exactly for `MemoryStorage`, extend `ExecutionChain` with `m_needsRetrieval` and `ELMContext` with memory fields, and follow the `AugmentPrompt` pattern for memory-in-context injection — all within a new `src/memory/` directory owning its own `neoswarm_memory` CMake library.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Memory object type definitions | API / Backend | — | `MemoryObjectType` enum and `CognitiveAsset` struct live in `common/types.hpp` — consumed everywhere |
| RocksDB persistence | API / Backend | — | Local disk I/O; `MemoryStorage` owns `memory.db` lifecycle, zero network involvement |
| Heuristic retrieval | API / Backend | — | `MemoryGovernor::Retrieve()` runs on the API server thread, no remote calls |
| Ingestion pipeline | API / Backend | — | Fact extraction, context mapping, and write evaluation are local CPU-bound transforms |
| Memory-in-context injection | API / Backend | — | Same tier as `AugmentPrompt()` — runs before inference, result fed into engine |
| needs_retrieval flag setting | API / Backend | — | `ELMChainBuilder::Build()` sets it during chain construction on the API thread |

## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** `CognitiveAsset` base struct in `common/types.hpp`. Fields: `m_id` (string UUID), `m_entity` (string), `m_type` (MemoryObjectType enum), `m_payload` (nlohmann::json), `m_timestamp` (int64 ns), `m_sourceNode` (string NodeID), `m_confidence` (float), `m_provenance` (float), `m_trustClass` (TrustClass enum).
- **D-02:** `MemoryObjectType` enum: `bridge_block`, `fact`, `policy`, `event`, `tenant_operational`. Added to `common/types.hpp` alongside existing enums.
- **D-03:** Extra fields deferred to Phase 9–11 (privacy_scope, replication_policy, training_export_policy, encryption_key_ref, graph_references). Not in Phase 8 schema.
- **D-04:** Standalone `MemoryGovernor` class in `src/memory/memory_governor.{hpp,cpp}`. Owned by `ApiServer`. Called between prompt analysis and RunELMChain.
- **D-05:** `Retrieve(task, chain)` returns `MemoryContext` — struct containing vectors of retrieved `MemoryObject` facts and policies.
- **D-06:** Heuristic retrieval: GetByPrefix on entity, filter by recency, keep top-k by confidence.
- **D-07:** Three active stages in `src/memory/`: `FactExtraction`, `ContextMapping`, `WriteEvaluation`. Each a separate class with single public method.
- **D-08:** `FactExtraction::Extract(text)` → `outcome::result<vector<MemoryObject>>`. Regex-based parsing in v1.
- **D-09:** Privacy Classification stub: all objects get `TrustClass::unverified` default. No encryption.
- **D-10:** Temporal Tracking stub: no conflict resolution or dedup in Phase 8.
- **D-11:** Memory objects store `m_timestamp` (int64 nanoseconds) and `m_sourceNode` (string NodeID). LWW-CRDT merge pattern from `ReputationCRDT` — merge logic NOT implemented until Phase 9.
- **D-12:** No IPFS-lite integration in Phase 8. All objects have implicit `ReplicationPolicy::none`.
- **D-13:** Standalone `MemoryStorage` (`src/memory/memory_storage.{hpp,cpp}`), separate `memory.db` database.
- **D-14:** Key format: `{entity}/{type}/{timestamp_ns}/{id}` — enables prefix range scans by entity+type+recency.
- **D-15:** Reuses RocksDB Pimpl/Open/Close/WriteBatch patterns from `ReputationStorage`. Header has zero RocksDB includes.
- **D-16:** `ExecutionChain::m_needsRetrieval` (bool, default false). Set by `ELMChainBuilder::Build()` when `PromptFeatures::complexity_` is high or `has_grounding_request_` is true.
- **D-17:** `ApiServer::Process()` calls `m_memoryGovernor->Retrieve(task, chain)` when `chain.m_needsRetrieval` is true. Results flow into `ELMContext::m_memoryFacts` and `m_memoryPolicies` fields.
- **D-18:** MemoryGovernor does NOT implement `IELM` — it's a standalone orchestration component.
- **D-19:** All `outcome::result<T>` returns checked. `outcome::failure()` with specific error codes on failure. No `(void)` discards.
- **D-20:** Missing RocksDB → `StorageError` (memory disabled, not fatal). Empty retrieval → empty `MemoryContext` (not an error). Failed write evaluation → `InternalError`.

### OpenCode's Discretion

- Exact heuristic thresholds for retrieval relevance scoring
- Write evaluation scoring formula (novelty, utility weights)
- Fact extraction regex patterns
- Key format delimiter conventions
- File layout within `src/memory/`

### Deferred Ideas (OUT OF SCOPE)

- Full CognitiveAsset model (20+ types) — Phases 9–11
- CRDT-backed IPFS-lite replication — Phase 9
- Full privacy classification — Phase 10
- Temporal tracking — Phase 9
- ML-assisted memory retrieval — post-Phase 8
- Private/enterprise/tenant scoping — Phase 10
- Swarm memory consensus — Phase 9

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| GAML-01 | Structured memory object model — bridge blocks, facts, policies, events, tenant operational | §CognitiveAsset + MemoryObjectType, §Integration Pattern 1 |
| GAML-02 | Memory Governor — retrieval prefiltering, relevance selection, temporal resolution | §MemoryGovernor Design, §Integration Pattern 2 |
| GAML-03 | Ingestion pipeline — fact extraction, context mapping, write evaluation with provenance scoring | §Ingestion Pipeline Design |
| GAML-04 | RocksDB local persistence + CRDT-ready fields | §RocksDB Persistence Pattern (verified against ReputationStorage) |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| RocksDB | v10.6.2 (pinned) | Memory object persistence | Already linked in project (`reputation_storage.cpp`), Pimpl pattern verified |
| nlohmann::json | 3.11.x (bundled) | Memory payload serialization | Already used in `main.cpp`, `p2p_node.cpp`, `sg_processing_bridge.cpp`, `genius_elm_chat_completions.cpp` |
| libp2p::outcome | bundled with libp2p | Error propagation | Project-wide standard for all Service/Storage returns |
| spdlog | bundled with fmt | Structured logging | Used in every module via `CreateLogger("Tag")` |
| std::regex | C++17 stdlib | Fact extraction patterns | Used in `PromptAnalyzer` for code/grounding detection |
| std::mutex | C++17 stdlib | Thread-safe retrieval | Pattern from `ReputationCRDT::m_mutex` |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| GTest | bundled (thirdparty) | Unit testing | All test files |
| `<chrono>` | C++17 stdlib | Timestamp (ns) generation | `std::chrono::steady_clock::now().time_since_epoch().count()` |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| RocksDB Pimpl | In-memory `std::unordered_map` | Persistence lost on restart — fails GAML-04 |
| nlohmann::json payload | protobuf binary | JSON is self-describing for variable schema across 5 types; protobuf needs compiled schema per type change |
| Separate `memory.db` | Shared `reputation.db` | Namespace isolation; separate lifecycle; Phase 9 replication has different policies per DB |

**Installation:**
No new dependencies. All libraries are already linked in the project. The `src/memory/` CMakeLists needs to add `RocksDB::rocksdb` and `nlohmann_json::nlohmann_json` targets.

**Version verification:** RocksDB is pinned at v10.6.2 per `STATE.md` (C++17 ceiling — v10.7+ requires C++20). nlohmann/json is provided via `THIRDPARTY_BUILD_DIR/json/include` (bundled in the thirdparty build, not version-tracked in CMake).

## Architecture Patterns

### System Architecture Diagram

```
                      ┌─────────────────────────────────────┐
                      │           ApiServer                  │
                      │         (composition root)            │
                      │                                      │
  Task ──────────────►│  1. Route(task) ──► RouteDecision    │
                      │           │                          │
                      │  2. ELMChainBuilder.Build()          │
                      │     └─ sets needs_retrieval          │
                      │           │                          │
                      │  3. IF needs_retrieval:              │
                      │     m_memoryGovernor →────────────────┼────► MemoryGovernor
                      │     .Retrieve(task, chain)           │        │
                      │     └─ MemoryContext ←────────────────┼────────┘
                      │           │                          │
                      │  4. AugmentPrompt() ─── context      │
                      │     └─ memory facts injected          │
                      │           │                          │
                      │  5. RunELMChain(chain, context)      │
                      │     └─ InferenceResponse             │
                      │           │                          │
                      │  6. Ingestion Pipeline:              │
                      │     └─ FactExtraction →──────────────┼────► src/memory/
                      │        ContextMapping →              │        │
                      │        WriteEvaluation ──► Put() ────┼────► MemoryStorage
                      │                                      │        │   (RocksDB)
                      └──────────────────────────────────────┘        │
                                                                      │
  MemoryGovernor                                                      │
  ┌──────────────────────────────────────────────────┐               │
  │  Retrieve(task, chain) → MemoryContext            │               │
  │    │                                              │               │
  │    ├─ Determine entity from task (regex/heuristic)│               │
  │    ├─ m_storage→GetByPrefix(entity, topK)         │───────────────┘
  │    ├─ Filter by recency, rank by confidence        │
  │    └─ Build MemoryContext { facts, policies }     │
  └──────────────────────────────────────────────────┘

  Ingestion Pipeline (Post-Inference)
  ┌──────────────────────────────────────────────────┐
  │  InferenceResponse + ELMContext                   │
  │    │                                              │
  │    ├─ FactExtraction::Extract(output)             │
  │    │   └─ Regex patterns → vector<MemoryObject>   │
  │    ├─ ContextMapping::Map(facts, task)            │
  │    │   └─ Set entity, provenance, trustClass      │
  │    └─ WriteEvaluation::Evaluate(facts)            │
  │        └─ Score novelty/utility → filter/keep     │
  │              │                                    │
  │        m_storage→PutBatch(accepted)               │
  └──────────────────────────────────────────────────┘
```

### Recommended Project Structure

```
src/
├── memory/                    # NEW — Phase 8 additions
│   ├── CMakeLists.txt         # neoswarm_memory STATIC library
│   ├── memory_object.hpp      # CognitiveAsset struct (if not in types.hpp)
│   ├── memory_storage.hpp     # RocksDB Pimpl — zero RocksDB includes
│   ├── memory_storage.cpp     # Impl struct, rocksdb includes, serialization
│   ├── memory_governor.hpp    # Standalone retrieval orchestrator
│   ├── memory_governor.cpp    # Heuristic retrieval implementation
│   ├── fact_extraction.hpp    # Stage 1: regex-based fact extraction
│   ├── fact_extraction.cpp
│   ├── context_mapping.hpp    # Stage 2: entity/provenance mapping
│   ├── context_mapping.cpp
│   ├── write_evaluation.hpp   # Stage 3: novelty/utility scoring
│   └── write_evaluation.cpp
├── common/
│   └── types.hpp              # MODIFIED — add MemoryObjectType, TrustClass,
│                              #   CognitiveAsset, MemoryContext, extend
│                              #   ExecutionChain + ELMContext
├── elm/
│   └── elm_chain_builder.cpp  # MODIFIED — set m_needsRetrieval
├── api/
│   └── api_server.hpp         # MODIFIED — add m_memoryGovernor,
│   └── api_server.cpp         #   m_memoryStorage; retrieve + ingest
├── CMakeLists.txt             # MODIFIED — add_subdirectory(memory)
```

### Pattern 1: RocksDB Pimpl (Clone from ReputationStorage)

**What:** Zero-RocksDB-includes header with `struct Impl` forward declaration, all RocksDB types in .cpp.

**When to use:** Every RocksDB-backed storage class. This is the project standard.

**Example:**
```cpp
// memory_storage.hpp — ZERO RocksDB includes
#include "common/error.hpp"
#include "common/types.hpp"
#include <memory>
#include <string>
#include <vector>

namespace sgns::neoswarm::memory
{
    class MemoryStorage
    {
    public:
        explicit MemoryStorage(const std::string& db_path);
        ~MemoryStorage();

        outcome::result<void> Open();
        void Close();
        bool IsOpen() const { return m_open; }

        // Key: {entity}/{type}/{timestamp_ns}/{id}
        outcome::result<void> Put(const CognitiveAsset& obj);
        outcome::result<void> PutBatch(const std::vector<CognitiveAsset>& objects);
        outcome::result<std::vector<CognitiveAsset>> GetByPrefix(
            const std::string& prefix, int maxResults = 10) const;
        outcome::result<CognitiveAsset> Get(const std::string& key) const;

    private:
        struct Impl;
        std::unique_ptr<Impl> m_impl;
        std::string m_dbPath;
        bool m_open = false;

        static std::string Serialize(const CognitiveAsset& obj);
        static outcome::result<CognitiveAsset> Deserialize(const std::string& data);
    };
}
```
[VERIFIED: `src/reputation/reputation_storage.hpp` lines 23–90 — exact same pattern]

### Pattern 2: Json Serialization (Replace proto for Flexibility)

**What:** Use `nlohmann::json` for `m_payload` serialization instead of protobuf.

**When to use:** CognitiveAsset has variable-typed `m_payload` across 5 `MemoryObjectType` values. JSON allows self-describing schemas.

**Example:**
```cpp
// Source: verified from src/genius_elm_chat_completions.cpp:115 + src/main.cpp:98
#include <nlohmann/json.hpp>

std::string MemoryStorage::Serialize(const CognitiveAsset& obj)
{
    nlohmann::json j;
    j["id"] = obj.m_id;
    j["entity"] = obj.m_entity;
    j["type"] = static_cast<int>(obj.m_type);
    j["payload"] = obj.m_payload;  // nlohmann::json native
    j["timestamp"] = obj.m_timestamp;
    j["source_node"] = obj.m_sourceNode;
    j["confidence"] = obj.m_confidence;
    j["provenance"] = obj.m_provenance;
    j["trust_class"] = static_cast<int>(obj.m_trustClass);
    return j.dump();
}
```
[VERIFIED: nlohmann/json usage in `src/genius_elm_chat_completions.cpp:115`, `src/main.cpp:98`, `src/core/sgprocessing/sg_processing_bridge.cpp:15`]

### Pattern 3: Config Struct with Defaults

**What:** Every class has a nested `Config` struct with sensible defaults, passed via constructor.

**When to use:** All new classes. Follows `KnowledgeRetrieval::Config`, `ELMChainBuilder::Config`, `RuleBasedRouter::Config`.

**Example:**
```cpp
// Source: src/knowledge/knowledge_retrieval.hpp lines 27–34
struct Config
{
    std::string m_dbPath = "./memory.db";
    int m_topK = 10;
    float m_minConfidence = 0.3f;
    int64_t m_maxAgeNs = 86400LL * 1000000000LL; // 24h
    bool m_enabled = true;
};
```

### Pattern 4: Logger Setup (Module-Level)

**What:** Each .cpp file creates a logger via `CreateLogger("Tag")`.

**When to use:** Any class with runtime diagnostic output.

**Example:**
```cpp
// Source: src/reputation/reputation_storage.cpp lines 20–25
namespace {
    auto StorageLogger() {
        return neoswarm::CreateLogger("MemoryStorage");
    }
}
```
[VERIFIED: used in `reputation_storage.cpp`, `reputation_crdt.cpp`, `knowledge_retrieval.cpp`, `api_server.cpp`, etc.]

### Anti-Patterns to Avoid

- **RocksDB `std::string` keys with embedded null bytes:** RocksDB uses byte-lexicographic ordering. `{entity}/{type}/{timestamp_ns}/{id}` with `/` delimiter works because all components are printable strings and `/` sorts lower than all alphanumeric characters. Test key ordering after serialization.
- **Calling RocksDB::Get without checking `IsNotFound()`:** ReputationStorage correctly checks `status.IsNotFound()` before `!status.ok()`. Do the same — "not found" is an expected condition, not an error.
- **Leaking `rocksdb::Iterator*`:** ReputationStorage `GetAll()` uses raw `new` → `delete it`. Wrap in `std::unique_ptr<rocksdb::Iterator, void(*)(rocksdb::Iterator*)>` or use a scoped guard for exception safety.
- **Storing secrets in `m_payload` as plain JSON:** Phase 8 has no encryption. Flag this in the Privacy stub comment.
- **Sleep in memory tests:** Use the same `ASSERT_TRUE`/`EXPECT_TRUE` pattern. No `std::this_thread::sleep_for`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Key-value store | Custom file format, SQLite, `std::unordered_map` | RocksDB (already linked) | ACID writes, range scans, compression, crash recovery — hundreds of edge cases already solved |
| JSON serialization | Manual string building, CSV | nlohmann::json | Already in project; handles nesting, escaping, encoding. D-01 payload is `nlohmann::json` |
| Prefix range scans | `GetAll()` + client-side filter | RocksDB `NewIterator` + `Seek(prefix)` | Fails at scale; Iterator is O(results) not O(total) |
| Thread safety | No synchronization | `std::mutex` on retrieval (pattern from `ReputationCRDT`) | ApiServer may process concurrent requests |
| UUID generation | Platform-specific APIs | `std::hash` timestamp+thread (pattern from `ApiServer::GenerateId()`) or simple random hex | Cross-platform, no new dependency |
| Key encoding | Arbitrary string concat | Fixed delimiter `/` with string components | RocksDB byte-order; `/` sorts before `0-9a-z` |

**Key insight:** Every "simple" storage problem (crash recovery, atomic writes, range scans, compaction, thread safety) is already solved by RocksDB. The `ReputationStorage` implementation is 225 lines for the full CRUD surface — it's the gold standard for copying.

## Common Pitfalls

### Pitfall 1: RocksDB Raw Pointer Leak

**What goes wrong:** `rocksdb::DB*` is managed by raw `new`/`delete` in `ReputationStorage::Impl`. If an exception occurs between `Open()` and `Close()`, the pointer leaks.

**Why it happens:** RocksDB C++ API predates C++11 smart pointers. The project uses raw pointers because thirdparty RocksDB is compiled without C++20.

**How to avoid:** Always call `Close()` in destructor (as `ReputationStorage` does). Use RAII wrapper or at minimum guarantee `Close()` in all exit paths.

**Warning signs:** Valgrind/memory sanitizer reports on test exit; `memory.db` lock files left behind.

### Pitfall 2: Key Format Ordering Breaks Prefix Scans

**What goes wrong:** The key format `{entity}/{type}/{timestamp_ns}/{id}` works because `/` sorts before digits/letters. If any component contains `/`, prefix scans break.

**Why it happens:** Entity names or IDs from external input could contain `/`.

**How to avoid:** Sanitize entity names and IDs: replace `/` with `_` before constructing keys. Alternatively URL-encode components. ReporterationStorage avoids this by using `m_identityKey` directly (which is hex-encoded).

**Warning signs:** `GetByPrefix("entity/")` returns records from wrong entities.

### Pitfall 3: `ExecutionChain::m_needsRetrieval` Set But ELMChainBuilder Not Linked

**What goes wrong:** Phase 7's `elm_chain_builder.cpp` is NOT in the elm CMakeLists (verified: `src/elm/CMakeLists.txt` only lists `role_elm.cpp`, `domain_elm.cpp`, `specialist_adapter.cpp`, `grounding_elm.cpp`, `tool_support_elm.cpp`). Plan 07-05 (ApiServer orchestration) is also not implemented.

**Why it happens:** Phase 7 is partially complete — core ELM types exist but the chain builder and RunELMChain integration are absent.

**How to avoid:** Phase 8 Wave 5 (Integration) must either: (a) add `elm_chain_builder.cpp` to the elm CMakeLists and wire it into ApiServer, OR (b) set `m_needsRetrieval` directly in ApiServer by checking `PromptFeatures` inline. Option (b) is simpler and avoids cross-phase dependency on incomplete Phase 7 work. Per D-16, the check is `complexity_ >= high_threshold || has_grounding_request_`.

### Pitfall 4: Concurrent RocksDB Access Without Mutex

**What goes wrong:** If ApiServer processes multiple requests concurrently (future), two threads calling `MemoryStorage::Put()` or `GetByPrefix()` simultaneously may corrupt RocksDB state.

**Why it happens:** RocksDB is thread-safe for reads but concurrent write batches to the same key range need external synchronization for consistency.

**How to avoid:** Guard `Put()` and `PutBatch()` with a mutex. Reads (`Get`, `GetByPrefix`) typically don't need it for RocksDB's internal snapshot isolation, but the in-memory `MemoryGovernor` cache should be mutex-protected (pattern: `ReputationCRDT::m_mutex`).

## Code Examples

Verified patterns from official codebase sources:

### RocksDB Open/Close with Pimpl

```cpp
// Source: src/reputation/reputation_storage.cpp lines 67–113
struct MemoryStorage::Impl
{
    rocksdb::DB* m_db = nullptr;
    rocksdb::Options m_options;
};

MemoryStorage::MemoryStorage(const std::string& db_path)
    : m_impl(std::make_unique<Impl>())
    , m_dbPath(db_path)
{}

MemoryStorage::~MemoryStorage() { Close(); }

outcome::result<void> MemoryStorage::Open()
{
    m_impl->m_options.create_if_missing = true;
    rocksdb::Status status = rocksdb::DB::Open(
        m_impl->m_options, m_dbPath, &m_impl->m_db);
    if (!status.ok())
        return outcome::failure(Error::StorageError);
    m_open = true;
    return outcome::success();
}

void MemoryStorage::Close()
{
    if (m_impl && m_impl->m_db)
    {
        delete m_impl->m_db;
        m_impl->m_db = nullptr;
    }
    m_open = false;
}
```

### Prefix Range Scan with Iterator

```cpp
// Pattern: extends ReputationStorage::GetAll() (lines 180–199)
// with prefix seek instead of full scan
outcome::result<std::vector<CognitiveAsset>> MemoryStorage::GetByPrefix(
    const std::string& prefix, int maxResults) const
{
    if (!m_open)
        return outcome::failure(Error::StorageError);

    std::vector<CognitiveAsset> results;
    rocksdb::ReadOptions opts;
    auto* it = m_impl->m_db->NewIterator(opts);

    for (it->Seek(prefix);
         it->Valid() && it->key().starts_with(prefix) && 
         static_cast<int>(results.size()) < maxResults;
         it->Next())
    {
        auto obj = Deserialize(it->value().ToString());
        if (obj.has_value())
            results.push_back(std::move(obj.value()));
    }
    delete it;
    return outcome::success(std::move(results));
}
```
[VERIFIED: Iterator pattern from `src/reputation/reputation_storage.cpp:187–198`]

### WriteBatch for Atomic Multi-Put

```cpp
// Source: src/reputation/reputation_storage.cpp lines 204–223
outcome::result<void> MemoryStorage::PutBatch(
    const std::vector<CognitiveAsset>& objects)
{
    if (!m_open)
        return outcome::failure(Error::StorageError);

    rocksdb::WriteBatch batch;
    for (const auto& obj : objects)
    {
        std::string key = BuildKey(obj);  // {entity}/{type}/{ts}/{id}
        batch.Put(key, Serialize(obj));
    }
    rocksdb::WriteOptions opts;
    opts.sync = true;
    auto status = m_impl->m_db->Write(opts, &batch);
    if (!status.ok())
        return outcome::failure(Error::StorageError);
    return outcome::success();
}
```

### Outcome Error Checking Pattern

```cpp
// Source: src/api/api_server.cpp — consistent pattern throughout
auto result = m_storage->Open();
if (!result.has_value())
{
    ServerLogger()->warn("Memory storage open failed — memory disabled");
    // NOT fatal per D-20
}
// For retrieval:
auto memCtx = m_memoryGovernor->Retrieve(task, chain);
// Empty context is NOT an error — just continue without memory
```

### AugmentPrompt Injection Pattern (Adapt for MemoryContext)

```cpp
// Source: src/api/api_server.cpp lines 204–217 + src/knowledge/context_injection.cpp
// Phase 8 adaptation: inject memory facts into ELMContext instead of prompt string
ELMContext ctx;
if (chain.m_needsRetrieval)
{
    MemoryContext memCtx = m_memoryGovernor->Retrieve(task, chain);
    ctx.m_memoryFacts = memCtx.m_facts;       // NEW field
    ctx.m_memoryPolicies = memCtx.m_policies; // NEW field
}
// ctx flows into IELM::Process(input, ctx) — RoleELM::BuildPrompt can
// incorporate memory facts the same way GroundingELM uses grounding facts
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Stateless inference (no memory) | GAML v1 — 5 type MemoryObject model | Phase 8 (planned) | Enables contextual recall across sessions |
| KnowledgeRetrieval only (static Grokipedia) | KnowledgeRetrieval + MemoryGovernor (dynamic) | Phase 8 | Two-tier retrieval: static facts + learned memory |
| ReputationStorage CSV serialization | ReputationStorage protobuf (done), MemoryStorage JSON | Phase 3/8 | JSON chosen for MemoryObject due to variable payload schemas |

**Deprecated/outdated:**
- CSV serialization for reputation objects (replaced by protobuf in Phase 3)
- Manual `nlohmann::json::parse` in `ExtractPrompt` (replaced by `nlohmann::json` native in Phase 5)

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | nlohmann::json is available via `nlohmann_json::nlohmann_json` CMake target (same as network module) | Standard Stack | MEDIUM — if the target name differs, CMake configure will fail; fallback is to use include path directly as core module does |
| A2 | `elm_chain_builder.cpp` is not yet compiled/tested — Phase 8 may need to complete its integration | Common Pitfalls #3 | LOW — setting `m_needsRetrieval` in ApiServer inline is a 3-line alternative |
| A3 | Phase 7 source code for `ExecutionChain` exists in `common/types.hpp` but `m_needsRetrieval` field does not yet exist | Integration Pattern 1 | NONE — adding a bool field with default `false` is a 1-line change; no existing code references it |
| A4 | RocksDB `it->key().starts_with()` is available (C++20); may need `it->key().ToString().find(prefix) == 0` for C++17 | Code Examples | LOW — `ToString().compare(0, prefix.size(), prefix) == 0` is the C++17 equivalent |

## Open Questions (RESOLVED)

1. **ELMChainBuilder integration status:**
   - What we know: `elm_chain_builder.cpp` exists in source but is NOT in `src/elm/CMakeLists.txt`. ApiServer does not call `ELMChainBuilder::Build()`. Plan 07-05 is not executed.
   - What's unclear: Will Phase 7 Wave 5 be completed before Phase 8 starts? If not, Phase 8 Plan 08-05 should include inline `m_needsRetrieval` logic directly in `ApiServer::Process()`.
   - Recommendation: Plan 08-05 should support BOTH paths — a conditional that works when ELMChainBuilder is wired and when it isn't.

2. **UUID generation strategy:**
   - What we know: `ApiServer::GenerateId()` uses `steady_clock count + thread_id hash`. No Boost.UUID, no platform-specific UUID API in current code.
   - What's unclear: Should memory objects use the same scheme or a proper UUID library?
   - Recommendation: Use the same `GenerateId()` pattern — it's sufficient for local-only Phase 8 and can be upgraded in Phase 9.

3. **Fact extraction regex library:**
   - What we know: `PromptAnalyzer` uses `std::regex` for code/grounding detection. D-08 says regex-based.
   - What's unclear: Complexity of the regex patterns needed for fact extraction from LLM output.
   - Recommendation: Start with simple sentence-splitting + keyword matching (same complexity as PromptAnalyzer patterns). Advanced NLP can be added post-Phase 8.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| CMake | Build system | ✓ | 4.3.1 | — |
| Ninja | Build system | ✓ | 1.13.2 | — |
| RocksDB | MemoryStorage persistence | ✓ (linked in reputation) | v10.6.2 | In-memory fallback (D-20: not fatal) |
| nlohmann::json | Payload serialization | ✓ (THIRDPARTY_BUILD_DIR) | bundled | — |
| GTest | Unit tests | ✓ (bundled in thirdparty) | bundled | — |
| C++17 compiler | Language features | ✓ (Apple Clang) | — | — |

**Missing dependencies with no fallback:**
- None — all dependencies are already linked in the project.

**Missing dependencies with fallback:**
- None — all dependencies are available.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | Google Test (bundled via thirdparty) |
| Config file | `test/CMakeLists.txt` — `neoswarm_test()` macro |
| Quick run command | `cd build/OSX/Debug && ctest -R test_memory --output-on-failure` |
| Full suite command | `cd build/OSX/Debug && ctest --output-on-failure` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| GAML-01 | CognitiveAsset default construction, MemoryObjectType enum distinct, TrustClass enum | unit | `ctest -R test_memory_types` | ❌ Wave 0 |
| GAML-01 | CognitiveAsset JSON serialization roundtrip | unit | `ctest -R test_memory_types` | ❌ Wave 0 |
| GAML-04 | MemoryStorage::Open/Close, Put/Get roundtrip, GetByPrefix filtering, PutBatch atomicity, GetNotFound returns error | unit | `ctest -R test_memory_storage` | ❌ Wave 0 |
| GAML-02 | MemoryGovernor::Retrieve returns MemoryContext, entity extraction from task, confidence-ranked results, empty DB returns empty context | unit | `ctest -R test_memory_governor` | ❌ Wave 0 |
| GAML-03 | FactExtraction::Extract regex patterns, ContextMapping entity assignment, WriteEvaluation scoring/filtering, pipeline end-to-end | unit | `ctest -R test_memory_ingestion` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `ctest -R test_memory --output-on-failure` (all 4 test binaries)
- **Per wave merge:** `ctest --output-on-failure` (full suite)
- **Phase gate:** All 21 tests green (as specified in ROADMAP.md Phase 8 success criteria #6)

### Wave 0 Gaps

- [ ] `test/memory/test_memory_types.cpp` — covers GAML-01 (CognitiveAsset, enums, serialization)
- [ ] `test/memory/test_memory_storage.cpp` — covers GAML-04 (CRUD, GetByPrefix, PutBatch, errors)
- [ ] `test/memory/test_memory_governor.cpp` — covers GAML-02 (Retrieve, ranking, empty context)
- [ ] `test/memory/test_memory_ingestion.cpp` — covers GAML-03 (pipeline stages, scoring)
- [ ] `test/CMakeLists.txt` — add 4 `neoswarm_test()` entries for memory tests
- [ ] Mock InjectionEngine for MemoryGovernor tests (pattern from `test/elm/test_elm.cpp:22–56`)

*(All test infrastructure is missing — Phase 8 tests are net-new.)*

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — (local node memory, no auth boundary) |
| V3 Session Management | no | — |
| V4 Access Control | no | — (local storage only in Phase 8) |
| V5 Input Validation | yes | Key sanitization: strip/replace `/` from entity names before constructing RocksDB keys; JSON parse must catch `nlohmann::json::exception` |
| V6 Cryptography | no | — (no encryption in Phase 8 per D-09 stub) |

### Known Threat Patterns for RocksDB + JSON

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Crafted JSON payload causes stack overflow in `nlohmann::json::parse()` | Denial of Service | Wrap all `parse()` calls in try/catch; fail with `InvalidArgument` error |
| Path traversal via entity name (e.g., `../../../etc/passwd`) | Information Disclosure | Sanitize entity name: allow only `[a-zA-Z0-9_.-]`, reject `/` `\` `..` |
| Key collision from unsanitized IDs (two objects share key) | Tampering | Verify `m_id` uniqueness during `Put()`; log warning and overwrite on collision |
| RocksDB WAL corruption on hard shutdown | Information Disclosure | `WriteOptions.sync = true` already set (verified in ReputationStorage); RocksDB auto-recovery from WAL |

## Sources

### Primary (HIGH confidence — verified against project source code)

- `src/reputation/reputation_storage.hpp` — RocksDB Pimpl pattern (exact template for MemoryStorage)
- `src/reputation/reputation_storage.cpp` — RocksDB Open/Close/Put/Get/PutBatch/GetAll implementations
- `src/reputation/reputation_crdt.hpp` — LWW-CRDT Merge pattern (for Phase 9 reference)
- `src/reputation/reputation_crdt.cpp` — LWW merge implementation (timestamp comparison)
- `src/knowledge/knowledge_retrieval.hpp` — Config struct, Pimpl, structured fact retrieval pattern
- `src/knowledge/knowledge_retrieval.cpp` — Impl struct, Embed, CosineSimilarity, Retrieve top-k
- `src/knowledge/context_injection.hpp` — Inject pattern (template for memory context injection)
- `src/knowledge/context_injection.cpp` — AugmentPrompt injection implementation
- `src/api/api_server.hpp` — Composition root, Config, Initialize, Process, AugmentPrompt, member variables
- `src/api/api_server.cpp` — Full Process flow, GenerateId, RunSingleNode/RunSpecialist/RunSwarm
- `src/router/prompt_analyzer.hpp` — PromptFeatures struct (complexity_, has_grounding_request_)
- `src/router/prompt_analyzer.cpp` — Regex patterns, HasGroundingRequest, EstimateComplexity
- `src/elm/elm_chain_builder.hpp` — Build signature, Config
- `src/elm/elm_chain_builder.cpp` — 6-trigger decision tree (where m_needsRetrieval gets set)
- `src/common/types.hpp` — ExecutionChain, ELMContext, KnowledgeFact structs (targets for extension)
- `src/common/error.hpp` — Error enum (need additions for memory errors)
- `src/common/logging.hpp` — CreateLogger pattern
- `test/reputation/test_reputation.cpp` — Storage test patterns (UniqueDbPath, PutGet, PutBatch, GetAll)
- `test/knowledge/test_knowledge_retrieval.cpp` — Retrieval error test patterns
- `test/elm/test_elm.cpp` — MockEngine pattern for testing without real MNN
- `test/CMakeLists.txt` — `neoswarm_test()` macro, test library linking
- `src/reputation/CMakeLists.txt` — CMake library definition + RocksDB conditional linking
- `src/network/CMakeLists.txt` — nlohmann_json CMake target linking
- `src/CMakeLists.txt` — `add_subdirectory()` list (insertion point for memory/)
- `src/proto/CMakeLists.txt` — Proto library pattern (not needed for Phase 8, JSON used instead)

### Secondary (MEDIUM confidence — CONTEXT.md decisions verified against codebase)

- `.planning/workstreams/neoswarm/phases/08-agentic-memory-gaml-v1/08-CONTEXT.md` — All D-01 through D-20 decisions verified as compatible with existing code
- `.planning/workstreams/neoswarm/ROADMAP.md` §Phase 8 — Success criteria, plan structure (6 plans, 5 waves), cross-cutting constraints
- `.planning/workstreams/neoswarm/REQUIREMENTS.md` — GAML-01 through GAML-04 traced
- `.planning/workstreams/neoswarm/STATE.md` — RocksDB v10.6.2 pinned, Phase 7 status (partially complete)
- `docs/ARCHITECTURE.md` — Current subsystem diagram, module list (memory/ to be added)
- `CLAUDE.md` — Coding standards (naming conventions, outcome::result, C++17 ceiling, no sleep in tests)

### Tertiary (LOW confidence — not verified against external docs)

- `docs/architecture/agentic-memory-layer.md` §8.4 — Referenced in CONTEXT.md but does NOT exist in this repository. All GAML v1 specification details are captured in CONTEXT.md D-01 through D-20. The full architecture spec lives in the sibling `GeniusCognitiveSystem` repo and is not needed for Phase 8 implementation.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already linked, versions verified in CMakeLists
- Architecture: HIGH — integration points (ApiServer, ELMChainBuilder, ExecutionChain) identified with exact file:line references
- Pitfalls: HIGH — verified against actual source code (unlinked ELMChainBuilder, concurrent access patterns)
- Test patterns: HIGH — `neoswarm_test` macro, MockEngine, UniqueDbPath patterns all verified

**Research date:** 2026-07-23
**Valid until:** 2026-08-23 (30 days — stable codebase, no external API dependencies)
