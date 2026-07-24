# Phase 8: Agentic Memory (GAML v1) — Discussion Log

**Date:** 2026-07-22
**Mode:** User-delegated ("from previous analyse choose best")
**Prior context:** Phase 7 decisions (outcome::failure, no void discards, stub patterns), deferred Planner+Memory Governor, all available types from Waves 1-4

---

## Areas Presented

1. Memory object model scope
2. Memory Governor integration
3. Ingestion pipeline depth
4. CRDT sync timing
5. RocksDB schema
6. Planner + Memory Governor extension

User selected: all, delegated final choice ("from previous analyse choose best")

---

## Area 1: Memory object model

Selected: 5 MemoryObject types (bridge_block, fact, policy, event, tenant_operational) on CognitiveAsset base struct. Full 20+ types deferred to Phase 9-11 per subsystem availability. Rationale: ROADMAP scope is 5 types; base struct future-proofs without over-scoping Phase 8.

## Area 2: Memory Governor

Selected: Standalone MemoryGovernor class in src/memory/, owned by ApiServer. Called between prompt analysis and execution. Returns MemoryContext. Heuristic v1 retrieval. Rationale: doc 06 architectural diagram shows Governor between Router and Execution; not an ELM per D-18.

## Area 3: Ingestion pipeline

Selected: 3 active stages (Fact Extraction, Context Mapping, Write Evaluation), 2 stubs (Privacy Classification, Temporal Tracking). Rationale: Privacy needs Phase 10 encryption keys; Temporal needs Phase 9 CRDT consensus. Stubs explicitly authorized.

## Area 4: CRDT sync

Selected: CRDT-ready fields (m_timestamp, m_sourceNode), no replication. Actual IPFS-lite sync deferred to Phase 9. Rationale: Phase 8 is local-only; CRDT-ready schema avoids rewrite later.

## Area 5: RocksDB schema

Selected: Standalone MemoryStorage, separate memory.db, hierarchical key format for range scans. Reuses ReputationStorage patterns but different schema. Rationale: Different access patterns (range scan vs point lookup).

## Area 6: Planner integration

Selected: ExecutionChain::m_needsRetrieval flag set by ELMChainBuilder. MemoryGovernor called by ApiServer, not inside PlannerELM. Research correction: flag goes in ELMChainBuilder::Build() not BuildPrompt() since BuildPrompt lacks complexity data.

---

## Deferred Ideas

- Full CognitiveAsset model — Phase 9-11
- CRDT IPFS-lite — Phase 9
- Full privacy — Phase 10
- Temporal tracking — Phase 9
- ML-assisted retrieval — future
