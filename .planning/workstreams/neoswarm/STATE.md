# Project State

## Project Reference

See: PROJECT.md (created 2026-06-18, updated 2026-06-22)

**Core value:** Real LLM inference on consumer hardware in a fully decentralized swarm, production-connected to the SuperGenius/GNUS network for distributed AI compute.
**Current focus:** Phase 2 — SuperGenius Connectivity (GeniusSDK + libp2p GossipSub)

## Current Position

Phase: 2 of 6 (SuperGenius Connectivity)
Prior phase: 1 (Security Hardening) — source complete, tests remaining
Status: Phase 7 active — 6/6 plans complete (Wave 6 complete — all ELM + Router plans done)
Last activity: 2026-07-23 — Phase 7 Wave 6 complete (ELM test suite: 22 unit + 6 type + 2 integration tests)

Progress: [████████████░░░░░░░░░░░░] 64% (22 of 27 v1 requirements done)

## Performance Metrics

**Velocity:**
- Total plans completed: 12 (Phase 1: 3 source-complete, Phase 7: 5)
- Refactor work: 22 commits across 6 phases (Phase 1,2a,2b,5,6,7 cleanup)

**By Phase:**

| Phase | Plans | Total | Status |
|-------|-------|-------|--------|
| 1. Security Hardening | 3/4 | ~18 min | Source done, 01-04 (tests) pending |
| 2. SuperGenius Connectivity | 0/TBD | - | SGClient implemented, needs plans |
| 3. Persistence & Reliability | 0/TBD | - | RocksDB linked, needs plans |
| 4. SGProcessing Integration | 0/TBD | - | SGProcessing linked, needs plans |
| 5. Production Hardening | 0/TBD | - | Refactored, needs verification |
| 6. Testing & Validation | 0/TBD | - | Needs plans |
| 7. ELMs + Router | 6/6 | ~41 min | Complete — all 6 plans done (Wave 6: test suite) |

**Recent Trend:**
- 2026-07-23: Phase 7 Wave 6 complete — ELM test suite (22 unit + 6 type + 2 integration tests), full CTest green, all requirements ELM-01 through ELM-10 verified (~6 min)
- 2026-07-22: Phase 7 Wave 5 complete — ApiServer ELM integration (10 ELM registry + RunELMChain) + elms JSON config parsing (~7.5 min)
- 2026-07-16: Phase 7 Wave 2 complete — RoleELM (7 role templates) + DomainELM (dual-engine mode), 12 tests passing (~15 min)
- 2026-07-16: Phase 7 Wave 1 complete — ELM core types, IELM interface, CMake scaffolding (3 tasks, ~5 min)
- 2026-06-22: Workstream bifurcation — C++ docs moved from root .planning/ into neoswarm/
- 2026-06-18: Full SuperGenius coding-standards refactor complete — 24 source files, 10 roadmap phases
- 2026-06-18: .planning/ documentation overhaul — ROADMAP corrected for GeniusSDK/libp2p, REQUIREMENTS re-verified, MLX artifacts purged
- 2026-05-28: Plans 01-01 (~10 min) and 01-02 (~8 min) completed — security foundation active

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Refactor 2026-06-18]: All 10 REFACTOR_ROADMAP phases complete — zero `#ifdef` gates in source, all members `m_`-prefixed, all functions under 100 lines, `SuperGeniusClient` → `SGClient`
- [Architecture]: Connectivity uses GeniusSDK + libp2p GossipSub pubsub, NOT raw gRPC. Transport-layer gRPC lives in SuperGenius's `gRPCForSuperGenius/`
- [Architecture]: CRDT serialization follows SuperGenius protobuf schema (`src/crdt/proto/` — delta.proto, heads.proto, bcast.proto)
- [07-05]: ELMContext carries only m_originalTask, m_stepConfidences, m_groundingFacts — step output flows via input parameter per WR-01 review
- [07-05]: ELMChainBuilder::Build() returns ExecutionChain directly (no outcome::result wrapper) — mirrors Wave 4 design
- [07-05]: ParseELMRole unknown role → PrimaryDraft safe default per T-07-05-03
- [Roadmap]: libp2p P2P with GossipSub is already implemented (NET-01 promoted from v2 to v1, done)
- [Roadmap]: Security MUST come first — real secp256k1 identity and MessageSigning are prerequisites for all network connectivity
- [Roadmap]: SGClient component (`src/network/sg_client/`) encapsulates all SuperGenius communication
- [Roadmap]: Persistence (RocksDB) and Production Hardening are parallelizable with SuperGenius Connectivity
- [Roadmap]: SGProcessing protobuf conflict (PROC-03/FIX-04) must be resolved before SentencePiece and SGProcessing coexist in one binary

### Pending Todos

None yet. Capture with `/gsd:capture`.

### Blockers/Concerns

- [Phase 2]: `SubmitNetwork()` is stubbed — needs real GeniusSDK dispatch implementation
- [Phase 2]: GeniusSDK integration pattern needs research during planning — how does GNUS-NEO-SWARM consume GeniusSDK for job dispatch?
- [Phase 4]: FP4_ULTRA processor integration depends on understanding FP4 v3 codec and MNN quantized inference API
- [Phase 4]: Protobuf symbol conflict between SentencePiece and SGProcessing needs cross-platform verification (macOS uses `-ld_classic`; Linux/Windows paths TBD)
- [Phase 3]: RocksDB v10.7+ requires C++20 — must pin to v10.6.2 (C++17 ceiling)

## Cognitive Phases (7–11)

Post-production cognitive system evolution. Defined in ROADMAP.md, referencing `GeniusCogntiveSystem/docs/architecture/`.

| Phase | SPEC | PLAN | Status |
|-------|------|------|--------|
| 7. ELMs + Router | ✗ | ✓ | Complete (6/6 plans — Wave 6 test suite done) |
| 8. GAML Memory | ✗ | ✗ | Not started |
| 9. Swarm Networking | ✗ | ✗ | Not started |
| 10. AI Safety + Secure Agents | ✗ | ✗ | Not started |
| 11. Advanced Cognition | ✗ | ✗ | Not started |

## Deferred Items

Items acknowledged and carried forward from previous milestone close:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| Flutter | Streaming token output in chat UI | Deferred to v2 | 2026-05-28 |
| Knowledge | Semantic embeddings (replace TF-IDF stub) | Deferred to v2 | 2026-05-28 |
| Operations | Health/readiness HTTP endpoint | Deferred to v2 | 2026-05-28 |
| Operations | Rate limiting at engine level | Deferred to v2 | 2026-05-28 |
| Mobile | iOS/Android deployment | Deferred to v2 | 2026-05-28 |
| Network | mDNS peer discovery + Kademlia DHT | Deferred to v2 | 2026-05-28 |

## Session Continuity

Last session: 2026-07-23
Stopped at: Completed 07-06-PLAN.md (ELM test suite — 22 unit + 6 type + 2 integration tests)
Resume file: .planning/workstreams/neoswarm/phases/07-expert-language-models-router/07-06-SUMMARY.md
