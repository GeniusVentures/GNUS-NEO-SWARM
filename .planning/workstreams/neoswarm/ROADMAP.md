# Roadmap: GNUS NEO SWARM

## Overview

Production readiness for the GNUS NEO SWARM decentralized AI inference engine. The engine runs MNN-based inference locally, routes through a specialist system (grammar, math), and connects to the SuperGenius blockchain compute network via GeniusSDK for distributed job dispatch. Connectivity uses libp2p GossipSub for pubsub messaging with protobuf-serialized payloads (matching SuperGenius's CRDT and SGProcessing proto schemas). Transport-layer gRPC lives in SuperGenius's `gRPCForSuperGenius` — GNUS-NEO-SWARM consumes it through GeniusSDK, not raw gRPC.

**Storage architecture:** All persistent cognitive state (reputation, memory, consensus records) lives in a dedicated **GCS GlobalDB instance** — a separate `sgns::crdt::GlobalDB` from the blockchain GlobalDB buried inside GeniusSDK. The GCS instance has its own RocksDB directory, its own HierarchicalKey namespace (`/gcs/`), and its own broadcast/listen topics for selective CRDT replication. No phase wraps RocksDB directly.

## Phases

- [~] **Phase 1: Security Hardening** — Real secp256k1 identity, message signing, key encryption, replay protection
- [~] **Phase 2: SuperGenius Connectivity** — GeniusSDK dispatch to SuperGenius compute network via libp2p GossipSub pubsub
- [ ] **Phase 3: GCS GlobalDB Integration** — Dedicated GlobalDB instance with `/gcs/` namespaces; reputation state migrated from direct RocksDB to CRDT-backed GlobalDB
- [ ] **Phase 4: SGProcessing Integration** — MNN LLM and FP4_ULTRA processors, protobuf symbol conflict resolution
- [ ] **Phase 5: Production Hardening** — Eliminate hardcoded values, fix re-init edge cases, robust JSON parsing (mostly complete — fold remaining into Phase 6)
- [ ] **Phase 6: Testing & Validation** — Automated test coverage for security, FFI, knowledge, network, and Phase 5 verification remnants

## Phase Details

### Phase 1: Security Hardening
**Goal**: Nodes have real cryptographic identity; all inter-node messages are authenticated, tamper-protected, and replay-resistant
**Depends on**: Nothing (first phase)
**Requirements**: SEC-01, SEC-02, SEC-03, SEC-04, SEC-05, SEC-06
**Success Criteria** (what must be TRUE):
  1. Node can generate a secp256k1 keypair, derive a PeerId, and save the key encrypted at rest (AES-256-GCM with PBKDF2-derived key)
  2. Signatures are produced with deterministic RFC6979 nonces; the same message always produces an identical signature
  3. `MessageSigning::Verify` rejects tampered messages and fails closed (returns false) when crypto libraries are unavailable
  4. Every inter-node message includes a nonce + timestamp; replayed or expired messages (outside 30s window) are rejected
  5. Key encryption uses AES-256-GCM with random salt + random IV per save, PBKDF2 600k iterations
**Plans**: 4 plans (3 executed, 1 remaining)

**State note (2026-07-26):** SEC-01 through SEC-06 are implemented in source. Key encryption at rest (`SaveEncrypted`/`LoadEncrypted`) is implemented. Remaining work: 01-04 (security tests) not yet executed.

### Phase 2: SuperGenius Connectivity
**Goal**: The engine dispatches inference jobs to the SuperGenius blockchain compute network via GeniusSDK, using libp2p GossipSub for pubsub messaging with protobuf-serialized payloads
**Depends on**: Phase 1 (needs real NodeIdentity and MessageSigning for signed dispatch)
**Requirements**: SG-01, SG-02, SG-03, SG-04, SG-05
**Success Criteria** (what must be TRUE):
  1. Operator can launch the engine with `--sg-base-path` pointing to a GeniusSDK data directory
  2. Engine establishes in-process SDK node via `GeniusSDKInitWithKey()` — no remote endpoint, no gRPC
  3. `SGProcessingBridge::SubmitNetwork()` dispatches signed `Task` messages via `GeniusSDKProcess()` and collects results via `GeniusSDKGetProcessingStatus()` polling
  4. Dispatch times out after the configured deadline (120s default) instead of hanging indefinitely
  5. Engine reports connectivity status and gracefully degrades (falls back to local mode) when SDK is unreachable
**Plans**: 8 plans (Waves 1–3 complete, Waves 4–5 remaining)

**State note (2026-07-26):** SGClient is implemented in `src/network/sg_client/` using GeniusSDK C FFI (`GeniusSDKInit`, `GeniusSDKProcess`, `GeniusSDKGetProcessingStatus`). gRPC channel manager removed. `SubmitNetwork()` is wired to `SGClient::SubmitJob()` → `GeniusSDKProcess()`. Remaining: Wave 4 (result collector SDK polling), Wave 5 (tests).

### Phase 3: GCS GlobalDB Integration
**Goal**: A dedicated `sgns::crdt::GlobalDB` instance provides CRDT-backed persistence for all cognitive state. Reputation records live under `/gcs/reputation/` with CRDT topics for swarm-wide score convergence. No direct RocksDB wrappers.
**Depends on**: Phase 2 (needs GeniusSDK in-process for libp2p/GossipSub/Graphsync infrastructure)
**Requirements**: PERS-01, PERS-02, PERS-03, NET-02
**Success Criteria** (what must be TRUE):
  1. A GCS GlobalDB instance is created via `GlobalDB::New()` with its own RocksDB directory (separate from the blockchain GlobalDB inside GeniusSDK)
  2. All GCS keys are HierarchicalKey paths under `/gcs/` (e.g., `/gcs/reputation/<node_id>`, `/gcs/memory/fact/<id>`)
  3. Reputation records persist via `GlobalDB::Put()` / `Get()` / `QueryKeyValues()` — no `rocksdb::DB` calls in NEO-SWARM source
  4. Reputation scores converge across nodes via CRDT topics (broadcast + listen on `/gcs/reputation/` namespace)
  5. `ReputationStorage` class is deleted; `ReputationCRDT` merge logic is replaced by GlobalDB's built-in CRDT convergence
  6. JSON config via `nlohmann/json` with CLI override remains unchanged (PERS-04 already done)
**Plans**: TBD

**State note (2026-07-26):** `ReputationStorage` (direct RocksDB wrapper) and `ReputationCRDT` (local-only merge) exist but are architecturally wrong — they must be replaced with GlobalDB operations. The prior Phase 3 CONTEXT and 03-01-PLAN are discarded.

### Phase 4: SGProcessing Integration
**Goal**: The SuperGenius network can execute MNN LLM and FP4_ULTRA processors via SGProcessingManager, with protobuf symbol conflicts resolved
**Depends on**: Nothing (parallelizable with Phases 2-3; resolve protobuf conflict before linking both libs)
**Requirements**: PROC-01, PROC-02, PROC-03, FIX-04
**Success Criteria** (what must be TRUE):
  1. SGProcessingManager includes an MNN LLM text generation processor usable by SuperGenius compute nodes
  2. SGProcessingManager includes an FP4_ULTRA input format processor for quantized model dispatch
  3. SentencePiece and SGProcessing coexist in the same build binary without protobuf version symbol conflicts
  4. Test binaries link successfully with SGProcessingManager enabled (no duplicate symbol errors)
**Plans**: TBD

**State note (2026-07-26):** SGProcessingManager is linked from `src/core/CMakeLists.txt`. `SGProcessingBridge` builds JSON schema and calls `ProcessingManager::Create() + Process()` locally. MNN processors exist in SuperGenius (18 types). FP4_ULTRA processor does not yet exist in SuperGenius — PROC-02 is SuperGenius-side work requiring coordination. SentencePiece/protobuf conflict handled via `-ld_classic` on macOS; Linux/Windows paths TBD.

### Phase 5: Production Hardening
**Goal**: All known bugs and hardcoded values are eliminated; the engine is robust against re-initialization and malformed input
**Depends on**: Nothing (parallelizable with Phases 2-4)
**Requirements**: FIX-01, FIX-02, FIX-03
**Success Criteria** (what must be TRUE):
  1. Calling the FFI init function twice succeeds — the second call returns the existing instance instead of deadlocking
  2. Vocab size is read dynamically from the loaded tokenizer (`tokenizer_->VocabSize()`)
  3. `ExtractPrompt` parses JSON requests via `nlohmann::json`
  4. All existing tests continue to pass with zero regressions
**Plans**: TBD

**State note (2026-07-26):** FIX-02 and FIX-03 are done. FIX-01 (re-init) needs verification. FIX-04 (linker) partially handled. Remaining items fold into Phase 6.

### Phase 6: Testing & Validation
**Goal**: All critical production paths have automated test coverage proving correctness, security, and integration behavior
**Depends on**: Phases 1, 2, 3, 5
**Requirements**: TEST-01, TEST-02, TEST-03, TEST-04
**Success Criteria** (what must be TRUE):
  1. Security tests prove: key generation, sign/verify roundtrip, tamper rejection, replay protection, and encrypted save/load cycle
  2. FFI layer tests cover: init, chat completions flow, null/edge-case input handling, and re-init sequence
  3. Knowledge module tests verify: fact validation accuracy meets threshold and knowledge retrieval returns relevant results
  4. Network integration tests demonstrate: two nodes exchange a signed task, result aggregation completes, and timeout triggers correctly
  5. GlobalDB integration tests prove: reputation CRDT convergence across two instances, key prefix queries, tombstone handling
**Plans**: TBD

---

## Cognitive System Phases (7–11)

These phases evolve GNUS-NEO-SWARM from a production-hardened single-node inference engine into a **distributed cognitive swarm** with ELM orchestration, structured memory, reputation-weighted consensus, secure tool intermediation, and advanced cognition. They implement the GeniusCognitiveSystem architecture defined in `GeniusCogntiveSystem/docs/architecture/`.

**Architecture reference (authoritative):**

| Doc | Covers |
|-----|--------|
| 01 Executive Summary | System objectives, primary/secondary goals |
| 02 System Overview | 7-layer cognitive stack, component mapping |
| 03 Model and Router | Semantic Core, ELM taxonomy, router design |
| 04 Reputation and Consensus | Reputation model, weighted consensus, byzantine tolerance |
| 05 Grounding and Retrieval | Grokipedia integration, private knowledge grounding |
| 06 GAML Agentic Memory | Structured memory objects, bridge blocks, CRDT convergence |
| 07 Execution and Performance | Execution patterns, latency budgets |
| 08 Roadmap and Risks | Phase sequencing, risk analysis |
| 10 AI Safety | Decentralized safety model, reputation-enforced, node-sovereign |
| 11 Distributed Swarm Thinking | Thinking context model, specialist taxonomy, routing rules |
| 12 Secure Agent Architecture | Tool Intermediary boundary, capability-scoped execution |
| 13 EGGROLL Swarm Retraining | Evolutionary optimization, swarm-native adaptation |
| 14 Cognitive Retaining System | HCTS, targeted retraining |
| 15 Epistemic Arbitration | Cognitive OS extensions, epistemic arbitration |
| 16 SGFP4 Format | Adaptive quantization format specification |

### Scope Boundary with gnus-poc

| Layer | Owned By | Workstream |
|-------|----------|-----------|
| Specialist training + distillation | gnus-poc | `poc` (Python) |
| SGFP4 quantization export | gnus-poc | `poc` (Python) |
| Benchmark evaluation gate | gnus-poc | `poc` (Python) |
| C++ inference engine (MNN runtime) | GNUS-NEO-SWARM | `neoswarm` (C++) |
| ELM role orchestration | GNUS-NEO-SWARM | `neoswarm` (C++) |
| Router/Planner (rule-based → learned) | GNUS-NEO-SWARM | `neoswarm` (C++) |
| GAML memory layer | GNUS-NEO-SWARM | `neoswarm` (C++) |
| Distributed swarm execution (libp2p, IPFS-lite) | GNUS-NEO-SWARM | `neoswarm` (C++) |
| Reputation-weighted consensus | GNUS-NEO-SWARM | `neoswarm` (C++) |
| Tool Intermediary / secure agent boundary | GNUS-NEO-SWARM | `neoswarm` (C++) |
| AI safety (node-local enforcement) | GNUS-NEO-SWARM | `neoswarm` (C++) |
| EGGROLL retraining orchestration | GNUS-NEO-SWARM | `neoswarm` (C++) |
| Epistemic arbitration / GQHSM | GNUS-NEO-SWARM | `neoswarm` (C++) |
| SGFP4 GPU decode shaders (Vulkan/MoltenVK) | GNUS-NEO-SWARM | `neoswarm` (C++) |

### Phases

- [x] **Phase 7: Expert Language Models + Router** — Role-based and domain-specific ELM orchestration with rule-based routing
- [ ] **Phase 8: Agentic Memory (GAML v1)** — Structured long-term memory with bridge blocks, facts, policies, events, CRDT convergence via GlobalDB
- [ ] **Phase 9: Swarm Consensus** — Reputation-weighted consensus logic on existing transport and CRDT storage
- [ ] **Phase 10: AI Safety + Secure Agent Architecture** — Node-local safety, policy profiles, Tool Intermediary boundary
- [ ] **Phase 11: Advanced Cognition** — EGGROLL retraining, epistemic arbitration, hierarchical critical thinking

### Phase 7: Expert Language Models + Router

**Goal:** Deploy role-based and domain-specific ELMs with a rule-based router that decomposes, routes, and chains specialist execution.

**Architecture reference:** Docs 03, 11

**Depends on:** Phases 1–6 (production-hardened engine), gnus-poc Phase 3 (quantized specialists)

**Scope:**
- Seven role-based ELMs: Planner, Verifier, Arbiter, Refiner, Grounding, Tool-Support, Primary Draft
- Domain-specific ELMs: Code, Math, Science (loaded from gnus-poc quantized exports)
- Rule-based router extending existing `RuleBasedRouter` with heuristics from doc 11 §10
- Sequential execution chains (Planner → Domain ELM → Verifier → Refiner)
- Router evolution path: heuristic MVP → lightweight classifier → cognitive planner
- All ELMs behind abstract interfaces — implementations are swappable per architecture doc 03 §5.2.1

**Plans:** 6 plans in 6 waves — all complete

### Phase 8: Agentic Memory (GAML v1)

**Goal:** Replace stateless inference with structured long-term memory.

**Architecture reference:** Doc 06

**Depends on:** Phase 7, Phase 3 (GCS GlobalDB)

**Scope:**
- Structured memory object model (bridge blocks, facts, policies, events, tenant operational) matching canonical GAML spec fields
- Memory Governor: staged retrieval pipeline (identity/auth → privacy-scope filter → replication-boundary filter → policy checks → trust/provenance filter → metadata prefilter → temporal resolution → semantic matching → Governor selection)
- 5-stage ingestion pipeline: Fact Extraction → Context Mapping → Privacy Classification → Temporal Tracking → Write Evaluation
- Local persistence via GCS GlobalDB under `/gcs/memory/` namespace with CRDT topics for selective replication within authorized boundaries
- Privacy scopes and replication policies as first-class fields (not deferred)

### Phase 9: Swarm Consensus

**Goal:** Reputation-weighted consensus logic for multi-node cognitive task execution.

**Architecture reference:** Docs 04, 11

**Depends on:** Phase 7, Phase 8, Phase 3 (reputation CRDT convergence)

**Scope:**
- Weighted consensus with dual output selection modes (accuracy-prioritized, latency-prioritized)
- Role-aware reputation scoring (Planner, Math, Verification, Formatting, Grounding, Safety) — reputation data already converged via Phase 3 CRDT
- Byzantine tolerance via reputation decay, consistency penalties, exclusion gates
- Arbiter-mediated synthesis fallback for conflicting results
- Consensus records persisted under `/gcs/consensus/` in GCS GlobalDB

**Note:** Transport (libp2p GossipSub) already exists from Phase 2/NET-01. CRDT sync already provided by Phase 3 GlobalDB. This phase is the consensus *logic* only.

### Phase 10: AI Safety + Secure Agent Architecture

**Goal:** Node-local safety screening, cryptographically declared safety profiles, mandatory Tool Intermediary boundary.

**Architecture reference:** Docs 10, 12

**Depends on:** Phase 7, Phase 9

**Scope:**
- Node-level safety screening — no centralized gateway, no GeoIP enforcement
- Safety profiles: versioned, cryptographically signed, IPFS-distributed
- Client-side policy preference filtering
- Tool Intermediary boundary: dry-run → sanitization → capability check → approval gate → attestation → side-effect gating
- 100% tool execution attestation; zero direct side-effect paths from ELM workers

### Phase 11: Advanced Cognition

**Goal:** EGGROLL swarm retraining, epistemic arbitration, hierarchical critical thinking.

**Architecture reference:** Docs 13, 14, 15

**Depends on:** Phases 7–10

**Scope:**
- **EGGROLL Retraining:** Evolutionary optimization of ELM adapters using swarm execution traces
- **Epistemic Arbitration:** Evidence-chain-based arbitration beyond weighted voting
- **Cognitive OS Extensions:** Task scheduling, resource allocation, cognitive budget management
- **Hierarchical Critical Thinking:** Multi-pass critique with escalating scrutiny levels

### Cognitive Phase Dependencies

```
gnus-poc Phase 3 (quantized specialists)
    │
    ▼
Phase 7: ELMs + Router ──────────────────────┐
    │                                          │
    ▼                                          │
Phase 3: GCS GlobalDB ────────────────────┐   │
    │                                      │   │
    ▼                                      ▼   ▼
Phase 8: GAML Memory ───────────────── Phase 9: Swarm Consensus
                                              │
                                              ▼
                                    Phase 10: AI Safety
                                              │
                                              ▼
                                    Phase 11: Advanced Cognition
```

### Cognitive Phase Progress

| Phase | SPEC | PLAN | Status |
|-------|------|------|--------|
| 7. ELMs + Router | ✗ | ✓ | Complete (6/6 plans) |
| 8. GAML Memory | ✗ | ✗ | Regenerating (prior artifacts discarded) |
| 9. Swarm Consensus | ✗ | ✗ | Not started (re-scoped from Swarm Networking) |
| 10. AI Safety + Secure Agents | ✗ | ✗ | Not started |
| 11. Advanced Cognition | ✗ | ✗ | Not started |

### Key Architectural Constraints

From the parent PTDS — every phase plan must respect these:

1. **Program to interfaces, not implementations.** ELM roles, memory stores, consensus engines — all behind abstract interfaces.
2. **No centralized safety gateway.** Safety is node-local, reputation-enforced, client-selectable.
3. **Requestor-Orchestrator, not permanent leader.** Each request defines its own temporary orchestration context.
4. **Memory is structured, not transcript replay.** GAML stores typed objects with provenance metadata.
5. **Tool Intermediary is mandatory.** No ELM or Semantic Core worker may directly cause side effects.
6. **Reputation is role-aware and CRDT-converged.** Scores track domain-specific and role-specific performance, replicated via GlobalDB CRDT topics.
7. **Liveness over perfection.** Consensus terminates within bounded time; insufficient quorum degrades gracefully.
8. **Adapters over standalone models.** Per gnus-poc Decision 1, specialists are LoRA adapters on a shared backbone.
9. **No direct RocksDB wrappers.** All persistent cognitive state goes through the GCS GlobalDB instance. RocksDB is an implementation detail of GlobalDB, not a NEO-SWARM dependency.

### GSD Workflow

Each cognitive phase follows the standard GSD pipeline:

```
/gsd:discuss-phase  →  SPEC.md
/gsd:plan-phase     →  PLAN.md
/gsd:execute-phase  →  Implementation with atomic commits
/gsd:verify-work    →  UAT against SPEC.md
```

---

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11
Phases 4, 5, 6 are parallelizable with 2, 3.

| Phase | Plans Complete | Status | Notes |
|-------|----------------|--------|-------|
| 1. Security Hardening | 3/4 | Source done | 01-04 (tests) pending |
| 2. SuperGenius Connectivity | 5/8 | Waves 1–3 done | Waves 4–5 remaining |
| 3. GCS GlobalDB Integration | 0/TBD | **Reworked** | Prior approach discarded |
| 4. SGProcessing Integration | 0/TBD | Planned | PROC-02 is SuperGenius-side |
| 5. Production Hardening | 0/TBD | Mostly done | Fold remnants into Phase 6 |
| 6. Testing & Validation | 0/TBD | Planned | Absorbs Phase 5 verification |
| 7. ELMs + Router | 6/6 | Complete | — |
| 8. GAML Memory | 0/TBD | **Regenerating** | Prior 6 plans discarded |
| 9. Swarm Consensus | 0/TBD | **Re-scoped** | Was "Swarm Networking" |
| 10. AI Safety | 0/TBD | Not started | — |
| 11. Advanced Cognition | 0/TBD | Not started | — |

---

**Refactor work (2026-06-18):** All 10 REFACTOR_ROADMAP.md phases complete — zero `#ifdef` gates, all members `m_`-prefixed, all functions under 100 lines, `SuperGeniusClient` → `SGClient`, FFI macros renamed, Genius string literals cleaned, busy-wait removed, platform abstractions created.

**Storage architecture correction (2026-07-26):** Direct RocksDB wrappers (`ReputationStorage`, `MemoryStorage`) replaced with GCS GlobalDB pattern. Phase 3 reworked, Phase 8 regenerating, Phase 9 re-scoped.

*Roadmap updated: 2026-07-26*
