# Requirements: GNUS NEO SWARM

**Defined:** 2026-05-28
**Core Value:** Real LLM inference on consumer hardware in a fully decentralized swarm, production-connected to the SuperGenius/GNUS network for distributed AI compute.

## v1 Requirements

Requirements for production readiness milestone. Each maps to roadmap phases.

### Security

- [x] **SEC-01**: Enable `GENIUS_HAS_SECP256K1` — real secp256k1 node identity with key generation and PeerId derivation
- [x] **SEC-02**: Implement real `MessageSigning::Verify` — reject tampered signatures (replace always-true stub)
- [x] **SEC-03**: Use RFC6979 deterministic nonces for ECDSA signing to prevent nonce-reuse key recovery
- [ ] **SEC-04**: Encrypt node private key at rest using AES-256-GCM with PBKDF2-derived key
- [x] **SEC-05**: Add nonce + timestamp replay protection to signed inter-node messages
- [x] **SEC-06**: Fail-close all security stubs — reject when crypto unavailable instead of silently accepting

### SuperGenius Connectivity

- [ ] **SG-01**: Implement `SuperGeniusClient` component for PubSub-based network dispatch
- [ ] **SG-02**: Implement `SGProcessingBridge::SubmitNetwork()` — real gRPC dispatch to SuperGenius node
- [ ] **SG-03**: Add `--sg-endpoint <host:port>` CLI flag for SuperGenius node address
- [ ] **SG-04**: Require TLS from first `SubmitNetwork()` implementation (no insecure channel)
- [ ] **SG-05**: Add gRPC deadline enforcement (120s default for inference jobs)

### SGProcessing

- [ ] **PROC-01**: Add MNN LLM text generation processor to SGProcessingManager (SuperGenius repo)
- [ ] **PROC-02**: Add FP4_ULTRA input format processor to SGProcessingManager (SuperGenius repo)
- [ ] **PROC-03**: Resolve SentencePiece/SGProcessing protobuf version conflict (unified protobuf version)

### Persistence & Reliability

- [ ] **PERS-01**: Enable `GENIUS_HAS_ROCKSDB` — real RocksDB persistence for ReputationStorage (library already linked)
- [ ] **PERS-02**: Switch ReputationStorage from CSV to protobuf binary serialization
- [ ] **PERS-03**: Fix `ReputationStorage::Deserialize` crash — wrap stod/stoull in try/catch
- [ ] **PERS-04**: Add JSON config file support (nlohmann/json) with CLI-override precedence

### Fixes

- [ ] **FIX-01**: Fix `GeniusSlmInit` re-init bug — remove dead `std::call_once` / `g_init_flag` code
- [ ] **FIX-02**: Remove hardcoded vocab size 32000 — use `tokenizer_->VocabSize()` dynamically
- [ ] **FIX-03**: Replace manual JSON parsing in `ExtractPrompt` with nlohmann/json
- [ ] **FIX-04**: Fix test binary linker errors with SGProcessingManager enabled (duplicate protobuf symbols)

### Testing

- [ ] **TEST-01**: Security module tests — key generation, sign/verify, save/load roundtrip, tamper rejection
- [ ] **TEST-02**: FFI layer tests — GeniusSlmInit, chat completions, null handling, re-init sequence
- [ ] **TEST-03**: Knowledge module tests — FactValidation accuracy, KnowledgeRetrieval relevance
- [ ] **TEST-04**: Network integration tests — two P2PNode instances exchange a task, ResultAggregation timeout

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Network

- **NET-01**: Full libp2p P2P network integration (GossipSub, mDNS, Kademlia DHT)
- **NET-02**: CRDT-based reputation sync across multiple swarm nodes

### Flutter

- **FLUT-01**: Streaming token output in Flutter chat UI (SSE/WebSocket)
- **FLUT-02**: iOS/Android deployment with real device testing

### Knowledge

- **KNOW-01**: Replace TF-IDF stub with real semantic embeddings (Sentence-BERT or MiniLM)
- **KNOW-02**: Knowledge graph integration for verified fact retrieval

### Operations

- **OPS-01**: gRPC serve mode implementation (real server, not sleep loop)
- **OPS-02**: Health/readiness HTTP endpoint with metrics export
- **OPS-03**: Rate limiting at the engine level

## Out of Scope

| Feature | Reason |
|---------|--------|
| Full libp2p P2P swarm (GossipSub, DHT) | Route through SuperGenius gRPC first; complex, deferred to later milestone |
| Semantic embeddings for KnowledgeRetrieval | TF-IDF stub sufficient for current use case; adds operational complexity |
| Multi-model hot-swapping | Single-model (Mistral-7B) focus for this milestone |
| Mobile (iOS/Android) deployment | macOS proven; mobile is separate platform task |
| Web dashboard / admin UI | CLI sufficient for operators at this stage |
| Model training / fine-tuning | Inference-only engine; not in scope |
| OAuth / social login for swarm nodes | Not relevant to engine layer |
| Real-time streaming tokens in Flutter | UX polish, not blocking production connectivity |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| SEC-01 | Phase 1 | Done (01-01) |
| SEC-02 | Phase 1 | Done (01-02) |
| SEC-03 | Phase 1 | Done (01-02) |
| SEC-04 | Phase 1 | Pending |
| SEC-05 | Phase 1 | Done (01-02) |
| SEC-06 | Phase 1 | Done (01-01) |
| SG-01 | Phase 2 | Pending |
| SG-02 | Phase 2 | Pending |
| SG-03 | Phase 2 | Pending |
| SG-04 | Phase 2 | Pending |
| SG-05 | Phase 2 | Pending |
| PROC-01 | Phase 4 | Pending |
| PROC-02 | Phase 4 | Pending |
| PROC-03 | Phase 4 | Pending |
| PERS-01 | Phase 3 | Pending |
| PERS-02 | Phase 3 | Pending |
| PERS-03 | Phase 3 | Pending |
| PERS-04 | Phase 3 | Pending |
| FIX-01 | Phase 5 | Pending |
| FIX-02 | Phase 5 | Pending |
| FIX-03 | Phase 5 | Pending |
| FIX-04 | Phase 4 | Pending |
| TEST-01 | Phase 6 | Pending |
| TEST-02 | Phase 6 | Pending |
| TEST-03 | Phase 6 | Pending |
| TEST-04 | Phase 6 | Pending |

**Coverage:**
- v1 requirements: 26 total
- Mapped to phases: 26 ✓
- Unmapped: 0

---
*Requirements defined: 2026-05-28*
*Last updated: 2026-05-28 after roadmap creation — traceability complete*
