# Roadmap: GNUS NEO SWARM

## Overview

Production readiness for the GNUS NEO SWARM decentralized AI inference engine. The engine runs MNN-based inference locally, routes through a specialist system (grammar, math), and connects to the SuperGenius blockchain compute network via GeniusSDK for distributed job dispatch. Connectivity uses libp2p GossipSub for pubsub messaging with protobuf-serialized payloads (matching SuperGenius's CRDT and SGProcessing proto schemas). Transport-layer gRPC lives in SuperGenius's `gRPCForSuperGenius` — GNUS-NEO-SWARM consumes it through GeniusSDK, not raw gRPC. All 26 v1 requirements are mapped across 6 phases in dependency order.

## Phases

- [ ] **Phase 1: Security Hardening** — Real secp256k1 identity, message signing, key encryption, replay protection
- [ ] **Phase 2: SuperGenius Connectivity** — GeniusSDK dispatch to SuperGenius compute network via libp2p GossipSub pubsub
- [ ] **Phase 3: Persistence & Reliability** — RocksDB reputation storage with protobuf-serialized CRDT state
- [ ] **Phase 4: SGProcessing Integration** — MNN LLM and FP4_ULTRA processors, protobuf symbol conflict resolution
- [ ] **Phase 5: Production Hardening** — Eliminate hardcoded values, fix re-init edge cases, robust JSON parsing
- [ ] **Phase 6: Testing & Validation** — Automated test coverage for security, FFI, knowledge, and network paths

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
**Plans**: 4 plans (2 executed, 2 remaining)

**Plans**:
- [x] 01-01-PLAN.md — Enable secp256k1 linkage, fail-close all security stubs
- [x] 01-02-PLAN.md — RFC6979 deterministic nonces, real MessageSigning::Verify, nonce+timestamp replay protection
- [x] 01-03-PLAN.md — AES-256-GCM key encryption at rest (`SaveEncrypted`/`LoadEncrypted`) — already implemented in `node_identity.cpp`, needs test coverage
- [ ] 01-04-PLAN.md — Automated security tests for NodeIdentity and MessageSigning

**Cross-cutting constraints**:
- All inter-node messages must include nonce + timestamp (30s replay window)
- Security stubs must fail-closed (return false, never true)
- Node private key must be encrypted at rest

**State note (2026-06-18):** SEC-01 through SEC-06 are implemented in source. REFACTOR_ROADMAP.md Phase 1 removed all `GENIUS_HAS_SECP256K1` feature gates — crypto is always on. Key encryption at rest (`SaveEncrypted`/`LoadEncrypted`) is implemented. Remaining work: 01-03 plan needs a SUMMARY.md, 01-04 (security tests) is not yet executed.

### Phase 2: SuperGenius Connectivity
**Goal**: The engine dispatches inference jobs to the SuperGenius blockchain compute network via GeniusSDK, using libp2p GossipSub for pubsub messaging with protobuf-serialized payloads
**Depends on**: Phase 1 (needs real NodeIdentity and MessageSigning for signed dispatch)
**Requirements**: SG-01, SG-02, SG-03, SG-04, SG-05
**Success Criteria** (what must be TRUE):
  1. Operator can launch the engine with `--sg-endpoint <host:port>` pointing to a SuperGenius node
  2. Engine establishes an authenticated channel to the SuperGenius node via GeniusSDK (gRPC transport handled by SuperGenius's `gRPCForSuperGenius`)
  3. `SGProcessingBridge::SubmitNetwork()` dispatches signed `Task` messages via SGClient → SGChannelManager → libp2p GossipSub and collects results via SGResultCollector
  4. Dispatch times out after the configured deadline (120s default) instead of hanging indefinitely
  5. Engine reports connectivity status and gracefully degrades (falls back to local mode) when SuperGenius is unreachable
**Plans**: TBD

**State note (2026-06-18):** `SGClient` is implemented in `src/network/sg_client/` (with SGChannelManager, SGJobSubmitter, SGResultCollector, SGMessageAuthenticator sub-components). `--sg-endpoint` CLI flag exists. `SubmitNetwork()` is stubbed — needs real GeniusSDK dispatch. `P2PNode` with libp2p GossipSub is implemented in `src/network/p2p_node.*`. REFACTOR_ROADMAP.md Phase 2b renamed `SuperGeniusClient` → `SGClient`.

### Phase 3: Persistence & Reliability
**Goal**: Reputation data survives restarts via RocksDB with protobuf-serialized CRDT state (following SuperGenius's `src/crdt/proto/` schema); the engine is configurable via JSON file with CLI-override precedence
**Depends on**: Nothing (parallelizable with Phase 2)
**Requirements**: PERS-01, PERS-02, PERS-03, PERS-04
**Success Criteria** (what must be TRUE):
  1. Node reputation scores persist across process restarts via RocksDB with protobuf binary serialization (matching SuperGenius CRDT proto: `delta.proto`, `heads.proto`, `bcast.proto`)
  2. Corrupted or malformed reputation data does not crash the process — deserialization recovers gracefully
  3. Operator can configure the engine via a JSON config file (`nlohmann/json`); CLI flags override config file values
  4. Reputation writes are atomic (WriteBatch with `sync=true`) for consistency on unexpected shutdown
**Plans**: TBD

**State note (2026-06-18):** RocksDB is linked unconditionally in `src/reputation/CMakeLists.txt` and `src/core/CMakeLists.txt` (REFACTOR_ROADMAP.md Phase 1 removed the `GENIUS_HAS_ROCKSDB` compile gate). JSON config via `nlohmann/json` with CLI override is implemented in `main.cpp`. `ReputationStorage` exists but uses CSV — needs protobuf switch.

### Phase 4: SGProcessing Integration
**Goal**: The SuperGenius network can execute MNN LLM and FP4_ULTRA processors via SGProcessingManager, with protobuf symbol conflicts resolved
**Depends on**: Nothing (parallelizable with Phases 2-3; resolve protobuf conflict before linking both libs)
**Requirements**: PROC-01, PROC-02, PROC-03, FIX-04
**Success Criteria** (what must be TRUE):
  1. SGProcessingManager includes an MNN LLM text generation processor usable by SuperGenius compute nodes
  2. SGProcessingManager includes an FP4_ULTRA input format processor for quantized model dispatch
  3. SentencePiece and SGProcessing coexist in the same build binary without protobuf version symbol conflicts (linker uses `-ld_classic` on macOS to allow duplicate protobuf symbols)
  4. Test binaries link successfully with SGProcessingManager enabled (no duplicate symbol errors)
**Plans**: TBD

**State note (2026-06-18):** SGProcessingManager is linked from `src/core/CMakeLists.txt` when the pre-built libraries are found. `SGProcessingBridge` is implemented — builds JSON schema matching SuperGenius's `processing_datatypes`, calls `ProcessingManager::Create() + Process()` locally. `TensorInterpreter` exists. The SentencePiece/protobuf conflict is handled via linker flag on macOS. `SGProcessingManager/generated/` headers (`SGNSProcMain.hpp`, etc.) are included.

### Phase 5: Production Hardening
**Goal**: All known bugs and hardcoded values are eliminated; the engine is robust against re-initialization and malformed input
**Depends on**: Nothing (parallelizable with Phases 2-4)
**Requirements**: FIX-01, FIX-02, FIX-03
**Success Criteria** (what must be TRUE):
  1. Calling the FFI init function twice succeeds — the second call returns the existing instance instead of deadlocking
  2. Vocab size is read dynamically from the loaded tokenizer (`tokenizer_->VocabSize()`) — no hardcoded value assumption
  3. `ExtractPrompt` parses JSON requests via `nlohmann/json` — no fragile manual string parsing
  4. All existing tests continue to pass with zero regressions after fixes are applied
**Plans**: TBD

**State note (2026-06-18):** REFACTOR_ROADMAP.md Phase 5 split `Infer()`, `StreamInfer()`, and `Initialize()` into private helpers — all functions now under 100 lines. `m_geniusSlmInit` / `g_init_flag` patterns need verification. Hardcoded vocab size check needed. JSON parsing in `ExtractPrompt` needs verification.

### Phase 6: Testing & Validation
**Goal**: All critical production paths have automated test coverage proving correctness, security, and integration behavior
**Depends on**: Phases 1, 2, 5 (tests for security, network, FFI, and knowledge paths)
**Requirements**: TEST-01, TEST-02, TEST-03, TEST-04
**Success Criteria** (what must be TRUE):
  1. Security tests prove: key generation, sign/verify roundtrip, tamper rejection, replay protection, and encrypted save/load cycle
  2. FFI layer tests cover: init, chat completions flow, null/edge-case input handling, and re-init sequence
  3. Knowledge module tests verify: fact validation accuracy meets threshold and knowledge retrieval returns relevant results
  4. Network integration tests demonstrate: two nodes exchange a signed task, result aggregation completes, and timeout triggers correctly
**Plans**: TBD

## Progress

**Execution Order:** Phase 1 is the security foundation (must complete first). Phase 2 needs Phase 1 for signed dispatch. Phase 3 and Phase 5 are parallelizable with Phases 2/4. Phase 4 needs protobuf conflict resolution. Phase 6 gates the release after all implementation phases.

| Phase | Plans Executed | Remaining | Status |
|-------|----------------|-----------|--------|
| 1. Security Hardening | 3/4 | 01-04 (tests) | Source done, tests pending |
| 2. SuperGenius Connectivity | 0/TBD | All | Implementation exists, needs plans |
| 3. Persistence & Reliability | 0/TBD | All | RocksDB linked, needs plans |
| 4. SGProcessing Integration | 0/TBD | All | SGProcessing linked, needs plans |
| 5. Production Hardening | 0/TBD | All | Refactored, needs verification |
| 6. Testing & Validation | 0/TBD | All | Needs plans |

---

**Refactor work (2026-06-18):** All 10 REFACTOR_ROADMAP.md phases complete — zero `#ifdef` gates, all members `m_`-prefixed, all functions under 100 lines, `SuperGeniusClient` → `SGClient`, FFI macros renamed, Genius string literals cleaned, busy-wait removed, platform abstractions created.

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

- [~] **Phase 7: Expert Language Models + Router** — Role-based and domain-specific ELM orchestration with rule-based routing
- [ ] **Phase 8: Agentic Memory (GAML v1)** — Structured long-term memory with bridge blocks, facts, policies, CRDT convergence
- [ ] **Phase 9: Swarm Networking + Distributed Execution** — Multi-node execution with reputation-weighted consensus
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

**Plans:** 6 plans in 6 waves

Plans:
- [x] 07-01-PLAN.md — Core types (ELMRole, ELMContext, ExecutionChain) + IELM interface + CMake scaffolding
- [x] 07-02-PLAN.md — RoleELM (7 shared-backbone role templates) + DomainELM (Math/Code/Science, dual engine mode)
- [ ] 07-03-PLAN.md — SpecialistAdapter (legacy Grammar→Refiner, Math→Math) + GroundingELM (knowledge pipeline) + ToolSupportELM (stub)
- [x] 07-04-PLAN.md — PromptAnalyzer extension (grounding/formatting features) + ELMChainBuilder (6 heuristic triggers)
- [ ] 07-05-PLAN.md — ApiServer RunELMChain orchestration + ELM registry + main.cpp elms JSON config
- [ ] 07-06-PLAN.md — ELM unit tests (18 tests) + types tests + pipeline integration tests

### Phase 8: Agentic Memory (GAML v1)

**Goal:** Replace stateless inference with structured long-term memory.

**Architecture reference:** Doc 06

**Depends on:** Phase 7

**Scope:**
- Structured memory object model (bridge blocks, facts, policies, events, tenant operational)
- Memory Governor: retrieval prefiltering, relevance selection, temporal resolution
- Ingestion pipeline: fact extraction, context mapping, write evaluation with provenance
- Local storage via RocksDB, CRDT-backed replication via IPFS-lite

### Phase 9: Swarm Networking + Distributed Execution

**Goal:** Execute cognitive tasks across multiple GNUS nodes with reputation-weighted consensus.

**Architecture reference:** Docs 04, 11

**Depends on:** Phase 7, Phase 8

**Scope:**
- Requestor-Orchestrator model (no permanent leader)
- Task broadcast via libp2p, signed result collection, consensus finalization
- Reputation model: role-aware scores (Planner, Math, Verification, Formatting, Grounding, Safety)
- Weighted consensus with arbiter-mediated synthesis fallback
- Byzantine tolerance via reputation decay, consistency penalties, exclusion gates

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
Phase 8: GAML Memory ─────────────────────┐   │
    │                                      │   │
    ▼                                      ▼   ▼
Phase 9: Swarm Networking ◄──────── Phase 7 + 8
    │
    ▼
Phase 10: AI Safety + Secure Agents ◄── Phase 7 + 9
    │
    ▼
Phase 11: Advanced Cognition ◄────────── Phases 7–10
```

### Cognitive Phase Progress

| Phase | SPEC | PLAN | Status |
|-------|------|------|--------|
| 7. ELMs + Router | ✗ | ✓ | Planned (6 plans, 6 waves) |
| 8. GAML Memory | ✗ | ✗ | Requirements traced (GAML-01–04) |
| 9. Swarm Networking | ✗ | ✗ | Requirements traced (REP-01–03, SWARM-01–02) |
| 10. AI Safety + Secure Agents | ✗ | ✗ | Requirements traced (SAFE-01–05) |
| 11. Advanced Cognition | ✗ | ✗ | Requirements traced (COG-01–04) |

### Key Architectural Constraints

From the parent PTDS — every phase plan must respect these:

1. **Program to interfaces, not implementations.** ELM roles, memory stores, consensus engines — all behind abstract interfaces.
2. **No centralized safety gateway.** Safety is node-local, reputation-enforced, client-selectable.
3. **Requestor-Orchestrator, not permanent leader.** Each request defines its own temporary orchestration context.
4. **Memory is structured, not transcript replay.** GAML stores typed objects with provenance metadata.
5. **Tool Intermediary is mandatory.** No ELM or Semantic Core worker may directly cause side effects.
6. **Reputation is role-aware.** Scores track domain-specific and role-specific performance.
7. **Liveness over perfection.** Consensus terminates within bounded time; insufficient quorum degrades gracefully.
8. **Adapters over standalone models.** Per gnus-poc Decision 1, specialists are LoRA adapters on a shared backbone.

### GSD Workflow

Each cognitive phase follows the standard GSD pipeline:

```
/gsd:discuss-phase  →  SPEC.md
/gsd:plan-phase     →  PLAN.md
/gsd:execute-phase  →  Implementation with atomic commits
/gsd:verify-work    →  UAT against SPEC.md
```

*Roadmap updated: 2026-06-22*
