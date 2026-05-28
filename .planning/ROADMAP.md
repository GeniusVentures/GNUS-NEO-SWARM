# Roadmap: GNUS NEO SWARM

## Overview

Production readiness for the GNUS NEO SWARM decentralized AI inference engine. The journey starts with cryptographic identity and message signing (the security foundation every other phase builds on), connects the engine to the SuperGenius blockchain compute network via PubSub-based gRPC, hardens persistence and configuration, integrates SGProcessing processors, eliminates known bugs, and gates the release with automated test coverage. All 26 v1 requirements are mapped across 6 phases in dependency order.

## Phases

- [ ] **Phase 1: Security Hardening** — Real secp256k1 identity, message signing, key encryption, replay protection
- [ ] **Phase 2: SuperGenius Connectivity** — PubSub-based gRPC dispatch to SuperGenius blockchain compute network
- [ ] **Phase 3: Persistence & Reliability** — RocksDB reputation storage, protobuf serialization, JSON config
- [ ] **Phase 4: SGProcessing Integration** — MNN LLM and FP4_ULTRA processors, protobuf conflict resolution
- [ ] **Phase 5: Production Hardening** — Eliminate hardcoded values, fix re-init deadlock, robust JSON parsing
- [ ] **Phase 6: Testing & Validation** — Automated test coverage for security, FFI, knowledge, and network paths

## Phase Details

### Phase 1: Security Hardening
**Goal**: Nodes have real cryptographic identity; all inter-node messages are authenticated, tamper-protected, and replay-resistant
**Depends on**: Nothing (first phase)
**Requirements**: SEC-01, SEC-02, SEC-03, SEC-04, SEC-05, SEC-06
**Success Criteria** (what must be TRUE):
  1. Node can generate a secp256k1 keypair, derive a PeerId, and save the key encrypted at rest (AES-256-GCM with PBKDF2-derived key)
  2. Signatures are produced with deterministic RFC6979 nonces; the same message always produces an identical signature
  3. MessageSigning::Verify rejects tampered messages and fails closed (returns false) when crypto libraries are unavailable
  4. Every inter-node message includes a nonce + timestamp; replayed or expired messages (outside 30s window) are rejected
  5. Security stub code paths are unreachable in release builds — missing crypto is a hard error, not a silent acceptance
**Plans**: TBD

### Phase 2: SuperGenius Connectivity
**Goal**: The engine dispatches inference jobs to the SuperGenius blockchain compute network via TLS-protected, authenticated gRPC
**Depends on**: Phase 1 (needs real NodeIdentity and MessageSigning for signed dispatch)
**Requirements**: SG-01, SG-02, SG-03, SG-04, SG-05
**Success Criteria** (what must be TRUE):
  1. Operator can launch the engine with `--sg-endpoint <host:port>` pointing to a SuperGenius node
  2. Engine establishes a TLS-encrypted, authenticated gRPC channel to the SuperGenius node (no insecure fallback)
  3. `SubmitNetwork()` dispatches signed `Task` messages via PubSub and collects results from `results/<taskId>` channels
  4. gRPC calls time out after the configured deadline (120s default) instead of hanging indefinitely
  5. Engine reports connectivity status and gracefully degrades (falls back to local mode) when SuperGenius is unreachable
**Plans**: TBD

### Phase 3: Persistence & Reliability
**Goal**: Reputation data survives restarts via RocksDB; the engine is configurable via JSON file with CLI-override precedence
**Depends on**: Nothing (parallelizable with Phase 2)
**Requirements**: PERS-01, PERS-02, PERS-03, PERS-04
**Success Criteria** (what must be TRUE):
  1. Node reputation scores persist across process restarts via RocksDB with protobuf binary serialization
  2. Corrupted or malformed reputation data does not crash the process — deserialization recovers gracefully
  3. Operator can configure the engine via a JSON config file (`nlohmann/json`); CLI flags override config file values
  4. Reputation writes are atomic (WriteBatch with `sync=true`) for consistency on unexpected shutdown
**Plans**: TBD

### Phase 4: SGProcessing Integration
**Goal**: The SuperGenius network can execute MNN LLM and FP4_ULTRA processors without protobuf symbol conflicts
**Depends on**: Nothing (parallelizable with Phases 2-3; resolve protobuf conflict before Phase 2 links both libs)
**Requirements**: PROC-01, PROC-02, PROC-03, FIX-04
**Success Criteria** (what must be TRUE):
  1. SGProcessingManager includes an MNN LLM text generation processor usable by SuperGenius compute nodes
  2. SGProcessingManager includes an FP4_ULTRA input format processor for quantized model dispatch
  3. SentencePiece and SGProcessing coexist in the same build binary without protobuf version symbol conflicts
  4. Test binaries link successfully with `GENIUS_HAS_SGPROCESSING` enabled (no duplicate symbol errors)
**Plans**: TBD

### Phase 5: Production Hardening
**Goal**: All known bugs and hardcoded values are eliminated; the engine is robust against re-initialization and malformed input
**Depends on**: Nothing (parallelizable with Phases 2-4)
**Requirements**: FIX-01, FIX-02, FIX-03
**Success Criteria** (what must be TRUE):
  1. Calling `GeniusSlmInit` twice succeeds — the second call returns the existing instance instead of deadlocking on `std::call_once`
  2. Vocab size is read dynamically from the loaded tokenizer (`tokenizer_->VocabSize()`) — no hardcoded 32000 assumption
  3. `ExtractPrompt` parses JSON requests via `nlohmann/json` — no fragile manual string parsing
  4. All 46 existing tests continue to pass with zero regressions after fixes are applied
**Plans**: TBD

### Phase 6: Testing & Validation
**Goal**: All critical production paths have automated test coverage proving correctness, security, and integration behavior
**Depends on**: Phases 1, 2, 5 (tests for security, network, FFI, and knowledge paths)
**Requirements**: TEST-01, TEST-02, TEST-03, TEST-04
**Success Criteria** (what must be TRUE):
  1. Security tests prove: key generation, sign/verify roundtrip, tamper rejection, replay protection, and encrypted save/load cycle
  2. FFI layer tests cover: `GeniusSlmInit`, chat completions flow, null/edge-case input handling, and re-init sequence
  3. Knowledge module tests verify: fact validation accuracy meets threshold and knowledge retrieval returns relevant results
  4. Network integration tests demonstrate: two nodes exchange a signed task, result aggregation completes, and timeout triggers correctly
**Plans**: TBD

## Progress

**Execution Order:** Phases 2 and 4 depend on Phase 1 (security foundation). Phase 3 and Phase 5 are parallelizable with Phases 2/4. Phase 6 gates the release after all implementation phases.

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Security Hardening | 0/TBD | Not started | - |
| 2. SuperGenius Connectivity | 0/TBD | Not started | - |
| 3. Persistence & Reliability | 0/TBD | Not started | - |
| 4. SGProcessing Integration | 0/TBD | Not started | - |
| 5. Production Hardening | 0/TBD | Not started | - |
| 6. Testing & Validation | 0/TBD | Not started | - |
