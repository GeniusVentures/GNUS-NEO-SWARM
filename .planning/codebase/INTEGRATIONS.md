# External Integrations

**Analysis Date:** 2026-05-27

## APIs & External Services

**SuperGenius gRPC (GNUS Network):**
- Service: SuperGenius — decentralized compute network for distributed AI task processing
  - SDK/Client: gRPC (native C++ via `gRPCForSuperGenius`, referenced in `AgentDocs/PRODUCTION_ROADMAP.md`)
  - Interface: `SGProcessingBridge::SubmitNetwork()` in `src/core/sgprocessing/SGProcessingBridge.hpp:86`
  - Status: **Not yet implemented** — currently returns `Error::NotImplemented` (stub)
  - Auth: None documented yet
  - Connection: Via `--sg-endpoint <host:port>` CLI flag (planned, Task 4.2)
  - Endpoint: Configurable, default `localhost:50051`

**gRPC API Server (Self-hosted):**
- Service: GeniusAPI — serves client-facing gRPC on port 50051 (default)
  - Protocol: `proto/genius_api.proto` (proto3, `package genius.api`)
  - RPCs:
    - `Infer(InferRequest) returns (InferResponse)` — synchronous inference
    - `StreamInfer(InferRequest) returns (stream InferToken)` — streaming token-by-token
    - `GetNodeStatus(Empty) returns (NodeStatus)` — node health and status
  - Compile guard: `GENIUS_HAS_GRPC` (`src/api/CMakeLists.txt:22-25`)
  - Status: **Stub mode** — gRPC linkage not yet complete; server runs busy-loop placeholder (`RUN_AND_DEPLOY.md`)

**IPFS (InterPlanetary File System):**
- Service: IPFS — decentralized content-addressed storage
  - SDK: ipfs-lite-cpp, ipfs-bitswap-cpp, ipfs-pubsub (linked in `src/core/CMakeLists.txt:120-137`)
  - Used for: model URI and data URI addressing in SGProcessing schema JSON (`SGProcessingBridge::BuildSchemaJson()`, `src/core/sgprocessing/SGProcessingBridge.hpp:53-57`)
  - Status: Linked via transitive SGProcessingManager dependencies when available; fallback to local paths when not

**Hugging Face Hub:**
- Service: Model distribution
  - Used via: `huggingface_hub` Python CLI (documented in `RUN_AND_DEPLOY.md:199-220`)
  - Purpose: Download Mistral-7B GGUF model and SentencePiece tokenizer
  - Not a runtime dependency — used only during model setup

## Data Storage

**Databases:**
- RocksDB — persistent key-value store for node reputation scores
  - Connection: Filesystem path (default: `./reputation.db`)
  - Client: Direct C++ API via `RocksDB::rocksdb` target
  - File: `src/reputation/ReputationStorage.hpp`, `src/reputation/CMakeLists.txt:15-21`
  - Compile guard: `GENIUS_HAS_ROCKSDB`
  - Fallback: In-memory `std::unordered_map` when RocksDB not linked
  - Operations: `Put`, `Get`, `Remove`, `GetAll` for `NodeReputation` records
  - Serialization: Custom text format (pipe-delimited fields), deserialized by `Deserialize()`
  - Compression: Snappy

- SQLite3 — embedded SQL database (used by libp2p/soralog deps, not directly by app)

**File Storage:**
- Local filesystem only — no cloud storage integration
- Key files:
  - `node.key` — secp256k1 private key (hex-encoded, stored on disk)
  - `reputation.db/` — RocksDB database directory
  - `models/*.mnn` — MNN format model files
  - `models/*.tokenizer.model` — SentencePiece tokenizer models
  - `models/facts.csv` — Grokipedia knowledge base (CSV format: `category,fact`)
  - `mnn_cachefile.bin` — MNN runtime cache

**Caching:**
- MNN internal cache: `mnn_cachefile.bin` — model runtime cache file
- No external caching service (Redis, Memcached) detected
- ReputationStorage uses in-memory map as hot cache when RocksDB is unavailable

## Authentication & Identity

**Auth Provider:**
- Custom — self-sovereign node identity via cryptographic keypairs
  - Implementation: `src/security/NodeIdentity.hpp`
  - Algorithm: secp256k1 (ECDSA on secp256k1 curve)
  - Key sizes: 32-byte private, 33-byte public (compressed), 32-byte PeerId (SHA-256 of public key)
  - Key storage: Hex-encoded file on disk (`node.key`) — currently plain text, planned AES-256-GCM encryption (Task 2.3)
  - Key generation: Auto-generated on first run (`NodeIdentity::Generate()`), persisted via `SaveToFile()`
  - Identity: PeerId = hex(SHA-256(compressed_public_key))
  - Compile guard: `GENIUS_HAS_SECP256K1` — fallback uses XOR hash of random bytes (non-cryptographic, `src/security/NodeIdentity.cpp`)

**Message Signing:**
- Implementation: `src/security/MessageSigning.hpp`, `src/security/MessageSigning.cpp`
- Algorithm: ed25519 (EdDSA) for inter-node message signing
- Proto fields: `TaskMessage.signature`, `ResultMessage.signature` (`proto/genius_internal.proto`)
- Status: **Stub** — `MessageSigning::Verify` currently always returns `true` (Task 2.2: `TODO(SECURITY)` in `src/security/MessageSigning.cpp`)

**Transport Security:**
- P2P: Noise protocol for transport encryption (via libp2p)
- P2P: Yamux for stream multiplexing (via libp2p)
- gRPC: OpenSSL TLS (when linked)
- Compile guard: `GENIUS_HAS_OPENSSL` for SSL/TLS support

## Monitoring & Observability

**Error Tracking:**
- None — no external error tracking service (Sentry, Bugsnag, etc.)
- Errors propagate via `outcome::result<T>` pattern (`src/common/Error.hpp` — 17 error codes)
- Error codes: ModelLoadFailed, InferenceFailed, TokenizerFailed, FP4DecodeFailed, RoutingFailed, NetworkError, PeerNotFound, BroadcastTimeout, StorageError, ReputationNotFound, KnowledgeUnavailable, FactValidationFailed, IdentityError, SignatureInvalid, InvalidArgument, NotImplemented, InternalError

**Logs:**
- Framework: spdlog (structured C++ logging library)
- File: `src/common/Logging.hpp` — wraps spdlog with namespace convention
- Output: stdout (colorized), pattern: `[YYYY-MM-DD HH:MM:SS.ms] [level] [NeoSwarm/Component] message`
- Levels: debug (via `--verbose` CLI flag), info, warn, error, critical
- Component loggers: Router, P2PNode, Storage, Signing, etc.
- No log aggregation or external log shipping

**Health Check:**
- gRPC RPC: `GetNodeStatus(Empty) returns (NodeStatus)` — returns `node_id`, `is_running`, `connected_peers`, `reputation_score`, `model_loaded`, `backend`
- C FFI: `GeniusSlmGetStatus()` returns JSON with `model_loaded`, `mode`, `backend`, `node_id`

## CI/CD & Deployment

**Hosting:**
- Self-hosted — native binary deployment, no cloud platform
- Server mode: `neo-swarm --serve` starts long-running gRPC server
- macOS: LaunchAgent for auto-start on boot (`RUN_AND_DEPLOY.md:283-331`)
- Binary: `build/<Platform>/<BuildType>/neo-swarm`

**CI Pipeline:**
- None detected — no CI configuration files (`.github/workflows/`, `.gitlab-ci.yml`, `Jenkinsfile`, etc.)
- Builds performed locally with manual `cmake` + `ninja` commands
- Pre-built thirdparty dependencies fetched from GitHub releases at `GeniusVentures/thirdparty`

**Build & Test:**
- Build: `cmake -S build/<Platform> -B build/<Platform>/<BuildType> -DCMAKE_BUILD_TYPE=<Type> -G Ninja`
- Tests: `ctest --test-dir build/<Platform>/<BuildType> -C <Type> --output-on-failure --parallel`
- Test output: xUnit XML format to `build/<Platform>/<BuildType>/xunit/`

**Flutter Deployment:**
- Platforms: Android, iOS, Linux, macOS, Windows (via `flutter_slm_bridge` FFI plugin)
- Bridge: Dart FFI loads `libGenius-MOS-SLM-FFI.dylib` (macOS), `.so` (Linux), `.dll` (Windows), `.framework` (iOS)
- Build: Flutter standard toolchain (`flutter build`), native lib built via CMake + linked via FFI

## Environment Configuration

**Required runtime files (not env vars):**
- `--model <path>` — MNN model file (required for real inference)
- `--key <path>` — node key file (auto-created at `./node.key` if missing)
- `--db <path>` — reputation database (auto-created at `./reputation.db` if missing)

**Optional runtime files:**
- `--knowledge <path>` — Grokipedia facts CSV
- `--grammar-model <path>` — grammar specialist model
- `--math-model <path>` — math specialist model
- Model-related: `tokenizer.model` (auto-detected alongside the `.mnn` model file)

**Secrets location:**
- `node.key` — private key file on local disk (excluded from git via `.gitignore`)
- `reputation.db/` — database directory (excluded from git via `.gitignore`)
- No environment variable or secrets manager integration detected

**Planned configuration:**
- Task 5.3: YAML/JSON config file support via `--config <path>` (using yaml-cpp, already in thirdparty)

## Webhooks & Callbacks

**Incoming:**
- None — no webhook endpoints exposed. Client interaction is via gRPC (`Infer`, `StreamInfer`) or direct CLI.

**Outgoing:**
- None — no outgoing webhook calls. The system processes tasks either locally or dispatches via gRPC to SuperGenius nodes (planned).

## P2P Network Integration

**Protocol Stack:**
- Transport: TCP (`/ip4/0.0.0.0/tcp/0` — random port by default)
- Encryption: Noise protocol
- Multiplexing: Yamux
- PubSub: GossipSub (for task broadcasting and CRDT sync)
- Peer Discovery: Kademlia DHT + mDNS (local network discovery)
- Identity: libp2p PeerId derived from secp256k1 public key
- File: `src/network/P2PNode.hpp` — `P2PNode` class wraps libp2p host
- Compile guard: `GENIUS_HAS_LIBP2P` — falls back to local stub

**Message Types (proto-defined):**
- `genius_internal.proto`: `TaskMessage` (task_id, prompt, mode, signature) and `ResultMessage` (task_id, node_id, output, perplexity, latency, signature)
- `genius_reputation.proto`: `NodeReputationProto` (identity_key, scores) and `ReputationSyncMessage` (CRDT sync)

**CRDT Sync:**
- Purpose: Distributed reputation state synchronization across swarm nodes
- Implementation: `src/reputation/ReputationCRDT.hpp`
- Transport: GossipSub via `P2PNode::BroadcastCRDT()`

---

*Integration audit: 2026-05-27*
