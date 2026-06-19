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

*Roadmap updated: 2026-06-18*
