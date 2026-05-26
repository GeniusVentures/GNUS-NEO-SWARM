# Roadmap: GNUS-NEO-SWARM — Full System Realization

## Overview

This roadmap maps the GNUS-NEO-SWARM submodule from its current stub-mode foundation toward the full GeniusCognitiveSystem vision described in `docs/architecture/`. The architecture specifies a distributed, reputation-weighted cognitive platform with: Semantic Core + Role/Domain Expert Language Models (ELMs), structured memory (GAML), grounding, verification, secure tool intermediation, swarm thinking, and epistemic arbitration.

**Current state:** The submodule has 46 passing tests validating stub-mode orchestration, but every core subsystem (inference, tokenization, identity, networking, persistence) runs in stub/no-op mode. 7 of the 16 architecture-defined subsystems have zero code.

## Phases

- [ ] **Phase 1: Critical Bug Fixes** — Resolve 8 code-level bugs/tech-debt without third-party deps
- [ ] **Phase 2: Test Coverage** — Add 3 missing GTest suites (security, FFI, knowledge)
- [ ] **Phase 3: Third-Party Integration** — Link MNN, SentencePiece, secp256k1, RocksDB; enable real inference & crypto
- [ ] **Phase 4: ELM Expansion** — Add role-based ELMs (Planner, Verifier, Arbiter, Refiner) + domain ELMs (Code, Science)
- [ ] **Phase 5: Memory Layer (GAML v1)** — Structured memory service with ingestion, retrieval, and swarm consensus
- [ ] **Phase 6: Swarm & Security Hardening** — Real libp2p networking, gRPC server, consensus messages, Byzantine tolerance
- [ ] **Phase 7: Tool Intermediary & AI Safety** — Dry-run sandbox, sanitization, capability enforcement, safety profiles
- [ ] **Phase 8: Advanced Cognitive** — EGGROLL retraining, HCTS critics, Epistemic Arbitration (GQHSM), cognitive twin

## Phase Details

### Phase 1: Critical Bug Fixes
**Goal**: All known code-level bugs resolved without third-party library changes.
**Depends on**: Nothing
**Requirements**: BUG-01 through BUG-08

Plans:
- [ ] 01-01: FFI Layer Fixes — Re-init race, JSON parsing, memory leak (`src/genius_slm_chat_c.cpp`, `flutter_slm_bridge/lib/`)
- [ ] 01-02: Core Bug Fixes — CSV crash, CLI validation, stale public key (`src/reputation/`, `src/genius_node.cpp`, `src/security/`)
- [ ] 01-03: Flutter & API Cleanup — Dylib path, Serve busy-wait (`flutter_slm_bridge/lib/`, `src/api/`)

### Phase 2: Test Coverage
**Goal**: 3 new GTest suites for previously untested subsystems.
**Depends on**: Phase 1

Plans:
- [ ] 02-01: Security Tests — `test/security/` (NodeIdentity, MessageSigning)
- [ ] 02-02: FFI Tests — `test/ffi/` (init, JSON handling, null safety)
- [ ] 02-03: Knowledge Tests — `test/knowledge/` (fact validation, edge cases)

### Phase 3: Third-Party Integration
**Goal**: Link all conditionally-compiled libraries so stub mode becomes real execution.
**Depends on**: Phase 1, 2
**Prerequisite**: User manages third-party builds (`thirdparty/`)

Plans:
- [ ] 03-01: MNN Integration — `GENIUS_HAS_MNN`, real inference replacing hardcoded random logits
- [ ] 03-02: SentencePiece Integration — `GENIUS_HAS_SENTENCEPIECE`, real tokenizer replacing whitespace/hash stub
- [ ] 03-03: secp256k1 Integration — `GENIUS_HAS_SECP256K1`, real key generation, signing, and verification
- [ ] 03-04: RocksDB Integration — `GENIUS_HAS_ROCKSDB`, persistent reputation storage replacing in-memory map
- [ ] 03-05: gRPC & Protobuf Integration — Real gRPC server replacing busy-loop, protobuf message serialization

### Phase 4: ELM Expansion
**Goal**: Expand specialist roster beyond Math/Grammar to the full role-based and domain-specific ELM typology described in architecture docs 03, 11, and 12.
**Depends on**: Phase 3 (real inference needed for ELM execution)

Plans:
- [ ] 04-01: Role-Based ELMs — Planner, Primary Draft, Verifier, Arbiter, Refiner/Formatter, Grounding, Tool-Support (`src/specialists/`)
- [ ] 04-02: Domain ELMs — Code, Science (`src/specialists/`)
- [ ] 04-03: ELM Invocation Patterns — Sequential chain, parallel swarm, arbiter-mediated (`src/api/GeniusAPIServer.cpp`)
- [ ] 04-04: Execution Plan Schema — Signed plan with selected ELMs, constraints, tool policy, privacy mode

### Phase 5: Memory Layer (GAML v1)
**Goal**: Implement structured memory service (`src/memory/`) with the GAML object model described in docs 06 and 12.
**Depends on**: Phase 3

Plans:
- [ ] 05-01: Memory Object Model — `MemoryObject` with UUID, entity, type, payload, timestamps, trust classes
- [ ] 05-02: Memory Classes — Bridge Blocks, Facts, Policies, Events
- [ ] 05-03: Ingestion Pipeline — Fact extraction, context mapping, temporal tracking, write evaluation
- [ ] 05-04: Agentic Retrieval — Metadata prefiltering, semantic matching, memory governor selection
- [ ] 05-05: Swarm Memory Consensus — CRDT-based replication (`src/memory/MemoryCRDT.hpp`)

### Phase 6: Swarm & Security Hardening
**Goal**: Real distributed execution with authenticated P2P networking, Byzantine-tolerant consensus, and message authentication.
**Depends on**: Phase 3, 4

Plans:
- [ ] 06-01: Real libp2p Networking — `src/network/P2PNode.cpp` with `GENIUS_ENABLE_NETWORK=ON`
- [ ] 06-02: Real gRPC Client — `SubmitNetwork()` with SuperGenius endpoint (`src/core/sgprocessing/`)
- [ ] 06-03: Consensus Messages — TASK_PROPOSAL, TASK_RESULT, VERIFICATION_RESULT, CONSENSUS_FINAL
- [ ] 06-04: Byzantine Tolerance — Malicious output detection, latency manipulation, non-response handling
- [ ] 06-05: Role-Aware Reputation — Expanded scores for planner, verifier, arbiter, formatter, grounding, synthesis
- [ ] 06-06: Key File Encryption — AES-256-GCM passphrase from `GENIUS_NODE_KEY_PASS` env var

### Phase 7: Tool Intermediary & AI Safety
**Goal**: Secure agent execution boundary with mandatory dry-run/sanitization before tool execution, plus AI safety profiles.
**Depends on**: Phase 3, 4

Plans:
- [ ] 07-01: Tool Intermediary Service — `src/intermediary/` with dry-run engine, sanitizer, capability enforcement
- [ ] 07-02: Tool Attestation — Execution attestation schema, 100% attestation target
- [ ] 07-03: AI Safety Layer — `src/safety/` with profiles, screening, policy enforcement
- [ ] 07-04: Safety-Aware Scoring — Safety dimension in reputation update formula

### Phase 8: Advanced Cognitive (Long-Term)
**Goal**: EGGROLL swarm retraining, HCTS critic layers, epistemic arbitration, and cognitive twin.
**Depends on**: Phase 5, 6, 7
**Note**: These are architecture-defined future capabilities; not expected in near-term execution.

Plans:
- [ ] 08-01: EGGROLL Retraining — Deterministic perturbation, fitness packets, beehive aggregation (`src/retraining/`)
- [ ] 08-02: HCTS Critics — 7-layer Hierarchical Critical Thinking Specialists (`src/critics/`)
- [ ] 08-03: Epistemic Arbitration — GQHSM runtime with Sanskrit/Kripke pipelines (`src/arbitration/`)
- [ ] 08-04: Cognitive Twin — Predicted user responses, historical patterns, bias priors

## Architecture Gap Summary

| Subsystem | Source Dir | Status |
|-----------|-----------|--------|
| Router | `src/router/` | Partial (keyword-only, no planner) |
| Core/Model | `src/core/` | Stub (MNN/SentencePiece not linked) |
| Specialists | `src/specialists/` | Partial (Math/Grammar only) |
| Reputation | `src/reputation/` | Stub (in-memory, no RocksDB) |
| Grounding | `src/knowledge/` | Partial (CSV only, no live index) |
| Security | `src/security/` | Stub (weak keys, Verify() always true) |
| Network | `src/network/` | Stub (libp2p not linked) |
| sgprocessing | `src/core/sgprocessing/` | Stub (SubmitNetwork NotImplemented) |
| API | `src/api/` | Stub (sleep_for loop, no gRPC) |
| **Memory/GAML** | — | **Gap — no src/memory/** |
| **Tool Intermediary** | — | **Gap — no src/intermediary/** |
| **AI Safety** | — | **Gap — no src/safety/** |
| **EGGROLL Retraining** | — | **Gap — no src/retraining/** |
| **HCTS Critics** | — | **Gap — no src/critics/** |
| **Epistemic Arbitration** | — | **Gap — no src/arbitration/** |
| **Thinking Trace** | — | **Gap — no trace recording** |

## Progress

| Phase | Plans Complete | Status |
|-------|----------------|--------|
| 1. Critical Bug Fixes | 0/3 | Not started |
| 2. Test Coverage | 0/3 | Not started |
| 3. Third-Party Integration | 0/5 | Not started |
| 4. ELM Expansion | 0/4 | Not started |
| 5. Memory Layer (GAML) | 0/5 | Not started |
| 6. Swarm & Security | 0/6 | Not started |
| 7. Tool Intermediary & Safety | 0/4 | Not started |
| 8. Advanced Cognitive | 0/4 | Not started |

---
*Last updated: 2026-05-26 — synthesized from codebase audit + docs/architecture/ ingestion*
