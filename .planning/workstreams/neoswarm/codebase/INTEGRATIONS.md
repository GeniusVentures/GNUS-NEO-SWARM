# External Integrations

**Analysis Date:** 2026-06-17

## APIs & External Services

**SuperGenius Blockchain Compute Network:**
- Service: SuperGenius — decentralized compute network for distributed AI task processing
  - SDK/Client: `src/network/sg_client/super_genius_client.hpp` (PImpl pattern)
  - Sub-components:
    - `src/network/sg_client/sg_channel_manager.hpp` — gRPC channel lifecycle
    - `src/network/sg_client/sg_job_submitter.hpp` — Task signing and PubSub publishing
    - `src/network/sg_client/sg_result_collector.hpp` — Timeout-bounded result collection
    - `src/network/sg_client/sg_message_authenticator.hpp` — secp256k1 message signing
  - Protocol: gRPC with PubSub for job submission and per-job result channels
  - Auth: secp256k1 message signing via `src/security/message_signing.hpp`
  - TLS: Optional CA certificate and client certificate (`--sg-tls-ca`, `--sg-tls-cert`)
  - Config: `SuperGeniusClient::Config` struct (endpoint, TLS paths, channel timeout 30s, result timeout 300s)
  - Compile guard: `GENIUS_HAS_GRPC` (`src/api/CMakeLists.txt:22-25`)
  - Status: Implemented — requires gRPC library at link time

**gRPC API Server (Self-hosted):**
- Service: GeniusAPI — client-facing gRPC on port 50051 (default)
  - Protocol: `proto/genius_api.proto` (proto3, `package genius.api`)
  - RPCs:
    - `Infer(InferRequest) returns (InferResponse)` — synchronous inference
    - `StreamInfer(InferRequest) returns (stream InferToken)` — streaming token-by-token
    - `GetNodeStatus(Empty) returns (NodeStatus)` — node health and status
  - Status: Proto defined, gRPC server is currently a busy-loop placeholder in `ApiServer::Serve()` (`src/api/api_server.cpp:469-479`)

**Grokipedia Knowledge Base:**
- Service: Grokipedia — fact retrieval for prompt grounding and validation
  - Client: `src/knowledge/knowledge_retrieval.hpp`
  - Format: CSV file with source/content columns
  - Features: TF-IDF bag-of-words + cosine similarity retrieval
  - Post-processing: Context injection (`src/knowledge/context_injection.hpp`), fact validation (`src/knowledge/fact_validation.hpp`)
  - Config: `--knowledge <path>` CLI flag

**IPFS (InterPlanetary File System):**
- Service: IPFS — decentralized content-addressed storage
  - SDK: ipfs-lite-cpp, ipfs-bitswap-cpp, ipfs-pubsub (linked via SGProcessingManager transitive deps)
  - Used for: Model URI and data URI addressing in SGProcessing schema JSON
  - Status: Linked when SGProcessingManager is available

## Data Storage

**Databases:**
- RocksDB — persistent key-value store for node reputation scores
  - Connection: Filesystem path (default: `./reputation.db`)
  - Client: Direct C++ API via `RocksDB::rocksdb` target
  - File: `src/reputation/reputation_storage.hpp`, `src/reputation/CMakeLists.txt:15-21`
  - Compile guard: `GENIUS_HAS_ROCKSDB`
  - Fallback: In-memory store when RocksDB not linked
  - Operations: `Put`, `Get`, `Remove`, `GetAll` for `NodeReputation` records
  - Serialization: Custom format via `Serialize`/`Deserialize` static methods
  - Compression: Snappy

- SQLite3 — embedded SQL database (used by libp2p/soralog deps, not directly by app)

**File Storage:**
- Local filesystem only — no cloud storage integration
- Key files:
  - `node.key` — secp256k1 private key (AES-256-GCM encrypted, or hex-encoded legacy)
  - `reputation.db/` — RocksDB database directory
  - `models/*.mnn` — MNN format model files
  - `models/facts.csv` — Grokipedia knowledge base (CSV format)

**Caching:**
- MNN internal cache: `mnn_cachefile.bin` — model runtime cache file
- No external caching service (Redis, Memcached) detected

## Authentication & Identity

**Node Identity (secp256k1):**
- Provider: Custom implementation using libsecp256k1
- Implementation: `src/security/node_identity.hpp` (PImpl pattern)
- Algorithm: secp256k1 (ECDSA)
- Key sizes: 32-byte private, 33-byte public (compressed), 32-byte PeerId (SHA-256 of public key)
- Key storage: AES-256-GCM encrypted binary format
  - Key derivation: PBKDF2-HMAC-SHA256 with 600,000 iterations and random salt
  - Binary format: `[4-byte salt length][salt][12-byte IV][ciphertext][16-byte GCM tag]`
  - Fallback: Plaintext hex file for backward compatibility
- Identity: PeerId = hex(SHA-256(compressed_public_key))
- Config: `--key <path>` CLI flag (default: `./node.key`)
- Compile guard: `GENIUS_HAS_SECP256K1`

**Message Signing:**
- Implementation: `src/security/message_signing.hpp`
- Algorithm: secp256k1 ECDSA (DER-encoded signatures)
- Purpose: Sign Task and Result messages for inter-node trust
- Proto fields: `TaskMessage.signature`, `ResultMessage.signature` (`proto/genius_internal.proto`)

**Transport Security:**
- P2P: Noise protocol for transport encryption (via libp2p)
- P2P: Yamux for stream multiplexing (via libp2p)
- gRPC: OpenSSL TLS (when `GENIUS_HAS_OPENSSL` defined)
- SuperGenius: Optional TLS CA + client certificate

## Monitoring & Observability

**Error Tracking:**
- None — no external error tracking service
- Errors propagate via `outcome::result<T>` pattern (`src/common/error.hpp` — 17 error codes)
- Error enum: `ModelLoadFailed`, `InferenceFailed`, `TokenizerFailed`, `FP4DecodeFailed`, `RoutingFailed`, `NetworkError`, `PeerNotFound`, `BroadcastTimeout`, `StorageError`, `ReputationNotFound`, `KnowledgeUnavailable`, `FactValidationFailed`, `IdentityError`, `SignatureInvalid`, `InvalidArgument`, `NotImplemented`, `InternalError`

**Logs:**
- Framework: spdlog (structured C++ logging library)
- File: `src/common/logging.hpp` — `CreateLogger(tag)` factory function
- Output: stdout (colorized), pattern: `[YYYY-MM-DD HH:MM:SS.ms] [LEVEL] [NeoSwarm/Component] message`
- Levels: debug (via `--verbose` CLI flag), info, warn, error, critical
- Component loggers: Created per component via `CreateLogger("ApiServer")`, etc.

**Health Check:**
- gRPC RPC: `GetNodeStatus(Empty) returns (NodeStatus)` — returns `node_id`, `is_running`, `connected_peers`, `reputation_score`, `model_loaded`, `backend`
- C FFI: `GeniusElmStatus()` returns JSON with `model_loaded`, `mode`, `backend`, `node_id`, `supergenius_connected`, `fallback_active`

## CI/CD & Deployment

**Hosting:**
- Self-hosted — native binary deployment, no cloud platform
- Server mode: `neo-swarm --serve` starts long-running server
- macOS: LaunchAgent for auto-start on boot (`RUN_AND_DEPLOY.md:286-331`)
- Binary: `build/<Platform>/<BuildType>/neo-swarm`

**CI Pipeline:**
- Git hooks: `scripts/install-hooks.sh`, `scripts/pre-commit-lint.sh`
- Pre-commit linting via clang-format and clang-tidy
- No CI configuration files detected (`.github/workflows/`, `.gitlab-ci.yml`, etc.)

**Flutter Deployment:**
- Platforms: Android, iOS, Linux, macOS, Windows (via `flutter_slm_bridge` FFI plugin)
- Bridge: Dart FFI loads `libGenius-MOS-ELM-FFI.dylib` (macOS), `.so` (Linux), `.dll` (Windows)
- Build: Flutter standard toolchain, native lib built via CMake + linked via FFI

## Environment Configuration

**Required runtime files:**
- `--model <path>` — MNN model file (required for non-stub inference)
- `--key <path>` — node key file (auto-created on first run, encrypted with default passphrase)

**Optional runtime files:**
- `--config <path>` — JSON config file (CLI flags override file values)
- `--knowledge <path>` — Grokipedia facts CSV
- `--grammar-model <path>` — grammar specialist model
- `--math-model <path>` — math specialist model
- `--db <path>` — reputation database (default: `./reputation.db`)
- `--sg-endpoint <host:port>` — SuperGenius node address (default: `localhost:50051`)
- `--sg-tls-ca <path>` — TLS CA certificate for SuperGenius
- `--sg-tls-cert <path>` — TLS client certificate for SuperGenius

**Secrets location:**
- `node.key` — encrypted private key file on local disk (excluded from git via `.gitignore`)
- Default passphrase: `"gnus-neo-swarm-default"` (in `ApiServer::Config::m_nodeKeyPassphrase`)
- No environment variable or secrets manager integration detected

## Webhooks & Callbacks

**Incoming:**
- None — no webhook endpoints exposed. Client interaction is via gRPC, CLI, or FFI.

**Outgoing:**
- Task broadcast to P2P peers via GossipSub (`P2PNode::BroadcastTask()`)
- CRDT reputation sync broadcast to peers (`P2PNode::BroadcastCRDT()`)
- Job submission to SuperGenius via gRPC PubSub (`SuperGeniusClient::SubmitJob()`)

## P2P Network Integration

**Protocol Stack:**
- Transport: TCP (`/ip4/0.0.0.0/tcp/0` — random port by default)
- Encryption: Noise protocol
- Multiplexing: Yamux
- PubSub: GossipSub (for task broadcasting and CRDT sync)
- Peer Discovery: Kademlia DHT + mDNS (local network discovery)
- Identity: libp2p PeerId derived from secp256k1 public key
- File: `src/network/p2p_node.hpp` (PImpl pattern)
- Compile guard: `GENIUS_HAS_LIBP2P` — falls back to local stub

**Message Types (proto-defined):**
- `proto/genius_internal.proto`: `TaskMessage` (task_id, prompt, mode, signature) and `ResultMessage` (task_id, node_id, output, perplexity, latency, signature)
- `proto/genius_reputation.proto`: `NodeReputationProto` (identity_key, scores) and `ReputationSyncMessage` (CRDT sync)

**CRDT Sync:**
- Purpose: Distributed reputation state synchronization across swarm nodes
- Implementation: `src/reputation/reputation_crdt.hpp`
- Transport: GossipSub via `P2PNode::BroadcastCRDT()`

## Protobuf Service Definitions

**`proto/genius_api.proto`:**
- Service: `GeniusAPI` — Client-facing gRPC (Infer, StreamInfer, GetNodeStatus)
- Messages: InferRequest, InferResponse, InferToken, GroundingFact, NodeStatus

**`proto/genius_internal.proto`:**
- Messages: TaskMessage, ResultMessage — Inter-node task broadcast and result aggregation
- Includes ed25519 signature fields for message authentication

**`proto/genius_reputation.proto`:**
- Messages: NodeReputationProto, ReputationSyncMessage — CRDT reputation synchronization

## FFI Bridge (Flutter)

**`src/genius_elm_chat_completions.cpp`:**
- C ABI exported functions for Flutter FFI
- Functions: GeniusElmInit, GeniusElmChat, GeniusElmStatus, GeniusElmShutdown, GeniusElmStringFree
- Current status: Stub mode returning hardcoded JSON responses
- Shared library: `Genius-MOS-ELM-FFI`
- Note: `neoswarm_api` not linked yet — stub returns hardcoded responses

---

*Integration audit: 2026-06-17*
