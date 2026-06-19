# Requirements: GNUS NEO SWARM

**Defined:** 2026-05-28
**Updated:** 2026-06-18 (post-refactor — re-verified all statuses against implementation)
**Core Value:** Real LLM inference on consumer hardware in a fully decentralized swarm, production-connected to the SuperGenius/GNUS network for distributed AI compute.

## v1 Requirements

Requirements for production readiness milestone. Each maps to roadmap phases.

### Security

- [x] **SEC-01**: Enable secp256k1 node identity with key generation and PeerId derivation (always-on, no compile gate)
- [x] **SEC-02**: Implement real `MessageSigning::Verify` — reject tampered signatures (replace always-true stub)
- [x] **SEC-03**: Use RFC6979 deterministic nonces for ECDSA signing to prevent nonce-reuse key recovery
- [x] **SEC-04**: Encrypt node private key at rest using AES-256-GCM with PBKDF2-derived key (implemented: `SaveEncrypted`/`LoadEncrypted` in `node_identity.cpp`)
- [x] **SEC-05**: Add nonce + timestamp replay protection to signed inter-node messages
- [x] **SEC-06**: Fail-close all security stubs — reject when crypto unavailable instead of silently accepting (all stubs removed, crypto always-on)

### SuperGenius Connectivity

- [x] **SG-01**: Implement `SGClient` component for GeniusSDK-based network dispatch (`src/network/sg_client/` — SGClient + SGChannelManager + SGJobSubmitter + SGResultCollector + SGMessageAuthenticator)
- [ ] **SG-02**: Implement `SGProcessingBridge::SubmitNetwork()` — real GeniusSDK dispatch to SuperGenius node (currently stubbed, returns NetworkError)
- [x] **SG-03**: Add `--sg-endpoint <host:port>` CLI flag for SuperGenius node address (implemented in `main.cpp` + `api_server.hpp` Config)
- [x] **SG-04**: TLS infrastructure for SuperGenius channel (`m_tlsCaPath` / `m_tlsCertPath` in SGClient::Config + SGChannelManager TLS logic)
- [ ] **SG-05**: Add dispatch deadline enforcement (120s default for inference jobs)

### SGProcessing

- [ ] **PROC-01**: Add MNN LLM text generation processor to SGProcessingManager (SuperGenius repo)
- [ ] **PROC-02**: Add FP4_ULTRA input format processor to SGProcessingManager (SuperGenius repo)
- [ ] **PROC-03**: Resolve SentencePiece/SGProcessing protobuf version conflict (unified protobuf version)

### Persistence & Reliability

- [x] **PERS-01**: RocksDB persistence for ReputationStorage (linked unconditionally, `reputation_storage.cpp` uses `rocksdb::DB::Open`/`Put`/`Get`/`Write`)
- [ ] **PERS-02**: Switch ReputationStorage serialization from manual to protobuf binary (matching SuperGenius CRDT proto: `delta.proto`, `heads.proto`, `bcast.proto`)
- [ ] **PERS-03**: Harden `ReputationStorage::Deserialize` — crash-resistant parsing for malformed data
- [x] **PERS-04**: JSON config file support (`nlohmann/json`) with CLI-override precedence (implemented in `main.cpp`)

### Fixes

- [ ] **FIX-01**: Fix FFI re-init edge case — verify no `std::call_once` / `g_init_flag` deadlock (no code found, needs test confirmation)
- [x] **FIX-02**: Remove hardcoded vocab size — use `tokenizer_->VocabSize()` dynamically (implemented in `mnn_inference_engine.cpp:510`)
- [x] **FIX-03**: Replace manual JSON parsing with `nlohmann::json::parse` in `ExtractPrompt` (implemented in `genius_elm_chat_completions.cpp:114`)
- [ ] **FIX-04**: Fix test binary linker errors with SGProcessingManager enabled (duplicate protobuf symbols — `-ld_classic` on macOS, needs cross-platform verification)

### Testing

- [ ] **TEST-01**: Security module tests — key generation, sign/verify, save/load roundtrip, tamper rejection
- [ ] **TEST-02**: FFI layer tests — init, chat completions, null handling, re-init sequence
- [ ] **TEST-03**: Knowledge module tests — FactValidation accuracy, KnowledgeRetrieval relevance
- [ ] **TEST-04**: Network integration tests — two P2PNode instances exchange a task, ResultAggregation timeout

### Network (Promoted from v2)

- [x] **NET-01**: libp2p P2P network with GossipSub pubsub (implemented: `P2PNode` in `src/network/p2p_node.*` — Noise encryption, Yamux multiplexing)

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Network

- **NET-02**: CRDT-based reputation sync across multiple swarm nodes
- **NET-03**: mDNS peer discovery + Kademlia DHT

### Flutter

- **FLUT-01**: Streaming token output in Flutter chat UI (SSE/WebSocket)
- **FLUT-02**: iOS/Android deployment with real device testing

### Knowledge

- **KNOW-01**: Replace TF-IDF stub with real semantic embeddings (Sentence-BERT or MiniLM)
- **KNOW-02**: Knowledge graph integration for verified fact retrieval

### Operations

- **OPS-01**: Health/readiness HTTP endpoint with metrics export
- **OPS-02**: Rate limiting at the engine level

## Out of Scope

| Feature | Reason |
|---------|--------|
| Full libp2p DHT / mDNS peer discovery | GossipSub pubsub sufficient; DHT/mDNS are v2 |
| Semantic embeddings for KnowledgeRetrieval | TF-IDF stub sufficient for current use case |
| Multi-model hot-swapping | Single-model focus for this milestone |
| Mobile (iOS/Android) deployment | macOS proven; mobile is separate platform task |
| Web dashboard / admin UI | CLI sufficient for operators at this stage |
| Model training / fine-tuning | Inference-only engine |
| OAuth / social login for swarm nodes | Not relevant to engine layer |
| Real-time streaming tokens in Flutter | UX polish, not blocking production connectivity |

## Traceability

Which phases cover which requirements. Updated 2026-06-18 after refactor.

| Requirement | Phase | Status |
|-------------|-------|--------|
| SEC-01 | Phase 1 | ✅ Done (01-01) |
| SEC-02 | Phase 1 | ✅ Done (01-02) |
| SEC-03 | Phase 1 | ✅ Done (01-02) |
| SEC-04 | Phase 1 | ✅ Done (implemented, needs test) |
| SEC-05 | Phase 1 | ✅ Done (01-02) |
| SEC-06 | Phase 1 | ✅ Done (01-01) |
| SG-01 | Phase 2 | ✅ Done (SGClient implemented) |
| SG-02 | Phase 2 | Pending (SubmitNetwork stubbed) |
| SG-03 | Phase 2 | ✅ Done (CLI flag exists) |
| SG-04 | Phase 2 | ✅ Done (TLS config exists) |
| SG-05 | Phase 2 | Pending |
| PROC-01 | Phase 4 | Pending (SuperGenius repo) |
| PROC-02 | Phase 4 | Pending (SuperGenius repo) |
| PROC-03 | Phase 4 | Pending |
| PERS-01 | Phase 3 | ✅ Done (RocksDB linked + used) |
| PERS-02 | Phase 3 | Pending (manual → protobuf) |
| PERS-03 | Phase 3 | Pending |
| PERS-04 | Phase 3 | ✅ Done (JSON + CLI override) |
| FIX-01 | Phase 5 | Pending (needs test) |
| FIX-02 | Phase 5 | ✅ Done (dynamic vocab size) |
| FIX-03 | Phase 5 | ✅ Done (nlohmann::json) |
| FIX-04 | Phase 4 | Pending |
| TEST-01 | Phase 6 | Pending |
| TEST-02 | Phase 6 | Pending |
| TEST-03 | Phase 6 | Pending |
| TEST-04 | Phase 6 | Pending |
| NET-01 | Phase 2 | ✅ Done (libp2p GossipSub) |

**Coverage:**
- v1 requirements: 27 total (26 original + NET-01 promoted)
- Done: 16 (59%)
- Pending: 11 (41%)
- Unmapped: 0

---
*Requirements defined: 2026-05-28*
*Last updated: 2026-06-18 — post-REFACTOR_ROADMAP verification, NET-01 promoted from v2*
