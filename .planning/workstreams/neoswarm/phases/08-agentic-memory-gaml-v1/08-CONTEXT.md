# Phase 8: Agentic Memory (GAML v1) — Discussion Context

**Phase**: 08 — Agentic Memory (GAML v1)  
**Status**: Discussion  
**Date**: 2026-07-22  
**Workstream**: neoswarm

---

## Phase Boundary

Replace stateless inference with structured long-term memory. Deploy GAML v1: a 5-type MemoryObject model on a CognitiveAsset base, a standalone MemoryGovernor for staged retrieval, a 3-stage ingestion pipeline, and local RocksDB persistence with CRDT-ready fields. Local-only — swarm memory consensus and IPFS-lite replication are Phase 9.

---

## Architecture Reference

- **Primary**: `docs/architecture/agentic-memory-layer.md` §8.4 — GAML v1 specification
- **Secondary**: `docs/architecture/distributed-swarm-thinking-context.md` §16.7 — Memory and context construction
- **Depends on**: Phase 7 (ELMs + Router, especially types.hpp types and the Planner+Memory Governor deferred item from doc 11 §16.8.1.1)
- **Requirements**: GAML-01, GAML-02, GAML-03, GAML-04

---

## Scope

### In-Scope

**Memory Object Model (5 types on CognitiveAsset base)**:
- `CognitiveAsset` base struct: id, entity, type, payload, timestamp, sourceNode, confidence, provenance, trustClass
- Five subtypes: `bridge_block`, `fact`, `policy`, `event`, `tenant_operational`
- Full 20+ CognitiveAsset types (EIS claims, verdicts, calibration, distillation) are Phase 9–11

**Memory Governor**:
- Standalone class in `src/memory/`, owned by ApiServer
- Called between prompt analysis and RunELMChain — returns `MemoryContext`
- Heuristic v1 retrieval using existing patterns (entity match, recency-based ranking)
- Retrieval flag on ExecutionChain (not individual steps)

**Ingestion Pipeline (3 stages)**:
- Fact Extraction → Context Mapping → Write Evaluation
- Privacy Classification: stub (defaults to unverified, local_only)
- Temporal Tracking: stub (no time-based dedup in Phase 8)

**RocksDB Persistence**:
- Standalone `MemoryStorage`, separate `memory.db`
- Key format: `{entity}/{type}/{timestamp_ns}/{id}` — range scans without secondary indexes
- CRDT-ready fields (`m_timestamp`, `m_sourceNode`); no replication in Phase 8

**Planner Integration**:
- `ExecutionChain::m_needsRetrieval` flag set by ELMChainBuilder
- MemoryGovernor is NOT an ELM — orchestration component

### Out-of-Scope

- Full CognitiveAsset model beyond 5 types — Phase 9–11
- CRDT-backed IPFS-lite replication — Phase 9
- Full privacy classification (encryption keys, policy scoping) — Phase 10
- Temporal tracking with conflict resolution — Phase 9
- ML-assisted retrieval — post-Phase 8 enhancement

---

## Implementation Decisions

### Memory object model
- **D-01:** `CognitiveAsset` base struct in `common/types.hpp`. Fields: `m_id` (string UUID), `m_entity` (string), `m_type` (MemoryObjectType enum), `m_payload` (nlohmann::json), `m_timestamp` (int64 ns), `m_sourceNode` (string NodeID), `m_confidence` (float), `m_provenance` (float), `m_trustClass` (TrustClass enum).
- **D-02:** `MemoryObjectType` enum: `bridge_block`, `fact`, `policy`, `event`, `tenant_operational`. Added to `common/types.hpp` alongside existing enums.
- **D-03:** Extra fields deferred to Phase 9–11 (privacy_scope, replication_policy, training_export_policy, encryption_key_ref, graph_references). Not in Phase 8 schema.

### Memory Governor
- **D-04:** Standalone `MemoryGovernor` class in `src/memory/memory_governor.{hpp,cpp}`. Owned by `ApiServer`. Called between prompt analysis and RunELMChain.
- **D-05:** `Retrieve(task, chain)` returns `MemoryContext` — struct containing vectors of retrieved `MemoryObject` facts and policies.
- **D-06:** Heuristic retrieval: GetByPrefix on entity, filter by recency, keep top-k by confidence. ML-assisted retrieval deferred.

### Ingestion pipeline
- **D-07:** Three active stages in `src/memory/`: `FactExtraction`, `ContextMapping`, `WriteEvaluation`. Each a separate class with single public method.
- **D-08:** `FactExtraction::Extract(text)` → `outcome::result<vector<MemoryObject>>`. Regex-based parsing in v1, model-assisted deferred.
- **D-09:** Privacy Classification stub: all objects get `TrustClass::unverified` default. No encryption, no policy evaluation.
- **D-10:** Temporal Tracking stub: no conflict resolution or dedup in Phase 8.

### CRDT readiness
- **D-11:** Memory objects store `m_timestamp` (int64 nanoseconds) and `m_sourceNode` (string NodeID). LWW-CRDT merge pattern from `ReputationCRDT` — but merge logic NOT implemented until Phase 9.
- **D-12:** No IPFS-lite integration in Phase 8. All objects have implicit `ReplicationPolicy::none`.

### RocksDB schema
- **D-13:** Standalone `MemoryStorage` (`src/memory/memory_storage.{hpp,cpp}`), separate `memory.db` database.
- **D-14:** Key format: `{entity}/{type}/{timestamp_ns}/{id}` — enables prefix range scans by entity+type+recency.
- **D-15:** Reuses RocksDB Pimpl/Open/Close/WriteBatch patterns from `ReputationStorage`. Header has zero RocksDB includes.

### Planner + Memory Governor integration
- **D-16:** `ExecutionChain::m_needsRetrieval` (bool, default false). Set by `ELMChainBuilder::Build()` when PromptFeatures::complexity_ is high or has_grounding_request_ is true. (Note: per research correction, this is in ELMChainBuilder not PlannerELM since BuildPrompt lacks complexity data.)
- **D-17:** `ApiServer::Process()` calls `m_memoryGovernor->Retrieve(task, chain)` when chain.m_needsRetrieval is true. Results flow into `ELMContext::m_memoryFacts` and `m_memoryPolicies` fields.
- **D-18:** MemoryGovernor does NOT implement `IELM` — it's a standalone orchestration component per doc 06's architectural diagram.

### Error handling (per CLAUDE.md)
- **D-19:** All `outcome::result<T>` returns checked. `outcome::failure()` with specific error codes on failure. No `(void)` discards.
- **D-20:** Missing RocksDB → `StorageError` (memory disabled, not fatal). Empty retrieval → empty `MemoryContext` (not an error). Failed write evaluation → `InternalError`.

### OpenCode's Discretion
- Exact heuristic thresholds for retrieval relevance scoring
- Write evaluation scoring formula (novelty, utility weights)
- Fact extraction regex patterns
- Key format delimiter conventions
- File layout within `src/memory/`

---

## Canonical References

### GAML architecture
- `docs/architecture/agentic-memory-layer.md` §8.4 — Full GAML v1 specification
- `docs/architecture/distributed-swarm-thinking-context.md` §16.7 — Memory and context construction
- `docs/architecture/distributed-swarm-thinking-context.md` §16.8.1.1 — Planner and Memory Governor

### Existing contracts
- `src/common/types.hpp` — `ELMRole`, `ELMContext`, `ExecutionChain`, `ChainStep`
- `src/api/api_server.hpp` — ApiServer integration point
- `src/reputation/reputation_storage.hpp` — RocksDB Pimpl pattern
- `src/reputation/reputation_crdt.hpp` — LWW-CRDT merge pattern for Phase 9
- `src/knowledge/knowledge_retrieval.hpp` — KnowledgeFact model analog
- `src/common/error.hpp` — Error codes

---

## Existing Code Insights

### Reusable Assets
- `ReputationStorage`: RocksDB Open/Close/WriteBatch/Get/Put pattern
- `ReputationCRDT`: LWW-CRDT merge (timestamp comparison) for Phase 9
- `KnowledgeRetrieval` + `KnowledgeFact`: structured fact model
- `ApiServer::AugmentPrompt()`: knowledge injection pattern for MemoryGovernor

### Integration Points
- `ApiServer::Initialize()`: creates MemoryGovernor + MemoryStorage
- `ApiServer::Process()`: MemoryGovernor::Retrieve() between prompt analysis and execution
- `ELMChainBuilder::Build()`: sets m_needsRetrieval on complex/grounding tasks
- `RunELMChain`: receives MemoryContext via ELMContext

---

## Deferred Ideas

- Full CognitiveAsset model (20+ types) — Phases 9–11
- CRDT-backed IPFS-lite replication — Phase 9
- Full privacy classification — Phase 10
- Temporal tracking — Phase 9
- ML-assisted memory retrieval — post-Phase 8
- Private/enterprise/tenant scoping — Phase 10
- Swarm memory consensus — Phase 9

---

*Phase: 08-agentic-memory-gaml-v1*  
*Context gathered: 2026-07-22*
