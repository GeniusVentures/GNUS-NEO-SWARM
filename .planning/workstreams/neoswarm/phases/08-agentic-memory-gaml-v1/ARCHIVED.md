# ARCHIVED — Phase 8 Planning Artifacts Discarded

**Date:** 2026-07-26
**Reason:** Planning artifacts were generated from unapproved assumptions that contradicted the canonical GAML architecture. See audit trail below.

## What Was Wrong

1. **08-CONTEXT.md** marked "Status: Discussion" but was treated as approved by downstream agents
2. **08-RESEARCH.md** explicitly dismissed the canonical GAML spec (`docs/architecture/agentic-memory-layer.md`) as "not needed"
3. All 6 plans (08-01 through 08-06) had `autonomous: true` — execution proceeded without human approval
4. Architecture chose direct RocksDB wrapper (`MemoryStorage`) instead of SuperGenius `GlobalDB`
5. TrustClass enum wrong: `{unverified, verified, premium, replica}` instead of canonical `{higher_trust, lower_trust, unverified}`
6. Privacy/replication fields deferred to Phase 9+ instead of being first-class per canonical spec
7. CRDT replication deferred to Phase 9 despite ROADMAP.md saying Phase 8 includes it

## What's Kept

- `src/common/types.hpp` — MemoryObjectType, CognitiveAsset, MemoryContext, ExecutionChain/ELMContext extensions (08-01 output). Types need updating but the file itself is shared with Phase 7.
- `src/common/error.hpp` — Memory error codes (18, 19, 20)
- `src/memory/CMakeLists.txt` — neoswarm_memory target scaffold
- `src/memory/memory_init.cpp` — placeholder

## What's Discarded

All files in this directory. New planning starts fresh from the canonical GAML spec and SuperGenius GlobalDB interfaces.

## Replacement Approach

Phase 8 planning will be regenerated based on:
- Canonical spec: `docs/architecture/agentic-memory-layer.md` §8.4
- Storage: `sgns::crdt::GlobalDB` with `/gcs/memory/` namespace (separate instance from blockchain GlobalDB)
- Full CRDT replication with privacy-scoped topics per canonical §8.4.10
- 5-stage ingestion pipeline per canonical §8.4.5 (privacy classification NOT a stub)
- 8-stage retrieval per canonical §8.4.6
- TrustClass = `{higher_trust, lower_trust, unverified}` per canonical §8.4.3

---

*Phase 8 artifacts archived: 2026-07-26*
