# External Integrations

**Analysis Date:** 2026-05-26

## AI/ML Inference

**MNN (Alibaba):**
- What: Lightweight deep neural network inference engine
- Used for: Running Nano Language Models (NLMs) — core inference backend
- SDK/Client: Pre-built static library at `../thirdparty/build/<Platform>/<BuildType>/MNN/lib/libMNN.a` (or `.dylib`)
- Header path: `../thirdparty/build/<Platform>/<BuildType>/MNN/include`
- Implementation: `src/core/engine/MNNInferenceEngine.cpp` and `.hpp`
- Status: Code paths in place, guarded by `#ifdef GENIUS_HAS_MNN` — currently runs in stub mode until MNN is linked (Task 1.1 in `AgentDocs/PRODUCTION_ROADMAP.md`)
- GPU backend: Vulkan (Linux/Windows) / MoltenVK (macOS) via `GENIUS_HAS_VULKAN`

**SentencePiece:**
- What: Unsupervised text tokenizer and detokenizer
- Used for: Encoding prompts to token IDs and decoding model output back to text
- Implementation: `src/core/tokenizer/SentencePieceTokenizer.hpp` — Pimpl pattern wrapping sentencepiece library
- Status: Code paths ready behind `#ifdef GENIUS_HAS_SENTENCEPIECE` — falls back to whitespace tokenizer when not compiled in (Task 1.2)

**Vulkan / MoltenVK:**
- What: GPU compute API and macOS Vulkan portability layer
- Used for: Hardware-accelerated neural network inference via MNN's Vulkan backend
- SDK: Vulkan SDK (system-installed), MoltenVK static library at `../thirdparty/build/<Platform>/<BuildType>/MoltenVK/`
- Config: `GENIUS_ENABLE_GPU=ON` (default), `Vulkan_FOUND` flag check in `src/core/CMakeLists.txt`

## P2P Networking

**libp2p (C++ implementation):**
- What: Modular peer-to-peer networking stack
- Used for: Decentralized swarm communication between nodes (`src/network/P2PNode.hpp`)
- SDK: Pre-built library at `../thirdparty/build/<Platform>/<BuildType>/libp2p/`
- Transitive deps: protobuf, yaml-cpp, ed25519, sr25519-donna, xxhash, cares, ipfs-lite-cpp, ipfs-pubsub, ipfs-bitswap-cpp, sqlite3, SQLiteModernCpp, soralog, Boost.DI, tsl_hat_trie
- Status: Optional; enabled via `GENIUS_ENABLE_NETWORK=ON` — P2P networking stub when not linked
- Ships Boost.Outcome headers — `outcome::result<T>` is aliased from libp2p's outcome

## Data Storage

**RocksDB:**
- What: Persistent key-value store (LSM-tree based)
- Used for: Reputation database — stores node reputation scores across restarts
- Implementation: `src/reputation/ReputationStorage.cpp` — falls back to in-memory `std::map` when RocksDB is not compiled in
- DB path: `--db <path>` CLI argument (default: `./reputation.db`)
- Status: Code paths ready behind `#ifdef GENIUS_HAS_ROCKSDB` (Task 3.1)

**Filesystem:**
- Model files: `.mnn` format (MNN model) loaded via CLI `--model <path>`
- Tokenizer files: `.tokenizer.model` (SentencePiece) expected next to the model file
- Facts CSV: `--knowledge <path>` — Grokipedia knowledge base in CSV format (source, content)
- Node key files: `.key` — secp256k1 private key stored as hex (plaintext); encryption planned (Task 2.3)
- Reputation DB: `reputation.db` — RocksDB database directory
- Stored in `*.key` and `*.db` — both are gitignored (see `.gitignore` lines 7-10)

## Authentication & Identity

**Custom Node Identity:**
- Implementation: `src/security/NodeIdentity.hpp` and `.cpp`
- Key algorithm: secp256k1 (Bitcoin ECDSA curve)
- Status: Stub mode generates random bytes XOR-hashed into a PeerId when secp256k1 is not linked. Real keypair generation behind `#ifdef GENIUS_HAS_SECP256K1` (Task 2.1)
- Key file: `./node.key` (default) — created on first run with `--key` flag
- Persistence: `NodeIdentity::SaveToFile()` / `LoadFromFile()` — raw hex format currently

**Message Signing:**
- Implementation: `src/security/MessageSigning.hpp` and `.cpp`
- Algorithm: ed25519 signatures on task/result messages (see proto `genius_internal.proto` — `bytes signature`)
- Status: `MessageSigning::Verify()` currently returns `true` always (stub) — designated `TODO(SECURITY)` (Task 2.2)

## External Network Services (gRPC)

**SuperGenius — GNUS Blockchain Compute Network:**
- What: Decentralized compute layer for the GNUS ecosystem
- Protocol: gRPC (Protobuf-defined services)
- Endpoint: `--sg-endpoint <host:port>` (planned, Task 4.2)
- Implementation: `src/core/sgprocessing/SGProcessingBridge.cpp` — `SubmitNetwork()` method dispatches via `gRPCForSuperGenius`
- Status: Not yet implemented — `SubmitNetwork()` returns `Error::NotImplemented` (Task 4.1)
- Two-phase architecture:
  - Phase 1 (Local): Neo Swarm → SGProcessingManager (local library) → Output
  - Phase 2 (Network): Neo Swarm → SuperGenius gRPC → GNUS Network → Output

**gRPC Server (node-local):**
- What: Client-facing inference API
- Protocol: gRPC / Protobuf, service `genius.api.GeniusAPI` defined in `proto/genius_api.proto`
- Endpoints:
  - `Infer(InferRequest) → InferResponse` — synchronous inference
  - `StreamInfer(InferRequest) → stream InferToken` — streaming token-by-token
  - `GetNodeStatus(Empty) → NodeStatus` — health and status
- Port: `--port <n>` (default: `50051`)
- Server: `--serve` flag starts gRPC server (blocking)
- Implementation: `src/api/GeniusAPIServer.hpp` — `Serve()` method
- Status: Optional; gRPC code guarded by `GENIUS_HAS_GRPC` — Serve mode currently busy-loop placeholder until wired (Task in roadmap phase 5)

## FFI / Flutter Bridge

**Genius-MOS-SLM-FFI Shared Library:**
- What: C-ABI shared library compiled from `src/genius_slm_chat_c.cpp`
- Used for: Flutter/Dart integration — exposes OpenAI v1 chat/completions API surface via Dart FFI
- Library name: `Genius-MOS-SLM-FFI` → `libGenius-MOS-SLM-FFI.dylib` (macOS), `.so` (Linux), `.dll` (Windows)
- Platform-specific loading: `flutter_slm_bridge/lib/flutter_slm_bridge.dart` — dynamic library resolution per platform
- Public API (C header at `src/genius_slm_chat_c.h`):
  - `GeniusSlmInit(const char* modelPath, const char* knowledgePath) → int`
  - `GeniusSlmChatCompletionsCreate(const char* requestJson) → char*` (caller must free with `GeniusSlmStringFree`)
  - `GeniusSlmStringFree(char* value) → void`
- Dart bindings: Auto-generated by `ffigen` from the C header (`flutter_slm_bridge/lib/genius_slm_bindings_generated.dart`)
- macOS linking: Uses `-force_load` linker flag to ensure all `genius_api` symbols are exported from the dylib (`CMakeLists.txt` line 119-123)

**OpenAI v1 Chat/Completions Protocol:**
- What: JSON API mimicking OpenAI's `/v1/chat/completions`
- Used for: `GeniusSlmChatCompletionsCreate` accepts standard OpenAI-format request JSON
- Request format: `{"messages": [{"role": "user", "content": "text"}], "model": "...", ...}`
- Response format: OpenAI v1 chat completion response JSON with `choices[].message.content`
- Implementation: Parsed and routed through the full GeniusAPIServer pipeline (router → inference → specialist → response)

## Inter-Node Messaging (Protobuf)

**Internal Protocol:**
- `proto/genius_internal.proto` — `TaskMessage` and `ResultMessage` for inter-node gossip
- Both include ed25519 signature fields for message authentication
- `ResultMessage` includes `perplexity` and `latency_ms` for reputation scoring

**Reputation Protocol:**
- `proto/genius_reputation.proto` — `NodeReputationProto` and `ReputationSyncMessage` for CRDT-based reputation sync
- Fields: `global_score`, per-category scores (`math`, `grammar`, `latency`, `consistency`), `task_count`, `last_updated_ms`

**API Protocol:**
- `proto/genius_api.proto` — External client-facing gRPC service
- `InferRequest`: `task_id`, `prompt`, `mode` (SingleNode/Specialist/Swarm), `max_tokens`, `temperature`
- `InferResponse`: `output`, `mode_used`, `route_used`, `total_latency_ms`, `success`, `error_message`, `grounding_facts`
- `GroundingFact`: `source`, `content`, `relevance_score`

## Monitoring & Observability

**Logging:**
- Framework: spdlog (via `GENIUS_HAS_SPDLOG`)
- Pattern: Module-specific loggers via `sgns::base::Logger` in `src/common/Logging.hpp`
- CLI: `--verbose` flag sets spdlog level to `debug`
- Runtime logs: stdout by default; macOS LaunchAgent redirects to `/tmp/neo-swarm.log` / `/tmp/neo-swarm-error.log`

**Error Tracking:**
- No external error tracking service detected
- Error propagation: `outcome::result<T>` pattern throughout — no exceptions in hot paths
- Error codes: Defined in `src/common/Error.hpp` as `enum class Error : uint8_t` (17 error codes covering Core, Router, Network, Reputation, Knowledge, Security, General)

## CI/CD & Deployment

**Hosting:**
- Platform: Self-hosted / on-premises
- macOS LaunchAgent plist (`RUN_AND_DEPLOY.md`) for running as a system service
- CLI binary: `neo-swarm` installed to `bin/`
- No containerization detected (no Dockerfile)

**CI Pipeline:**
- No CI configuration files detected in the project root

## Environment Configuration

**Secrets Management:**
- Node private key: stored in `--key` file (currently plain hex; encryption planned via OpenSSL AES-256-GCM in Task 2.3)
- Key passphrase: planned env var `GENIUS_NODE_KEY_PASS`
- No `.env` files detected — all configuration via CLI arguments

**Required External Paths:**
| Resource | Path Pattern | Set Via |
|----------|-------------|---------|
| Thirdparty libraries | `../thirdparty/build/<Platform>/<BuildType>/` | Resolved by `cmake_genius/FindThirdparty.cmake` |
| SuperGenius (Phase 2) | `../SuperGenius/` | CMake variables, `SUPERGENIUS_TEST_DATA_DIR` |
| SGProcessingManager (Phase 1) | `SGProcessingManager/` (submodule) | `src/core/CMakeLists.txt` |
| MNN model file | User-specified path | CLI `--model <path>` |
| SentencePiece tokenizer | Same dir as model | Auto-detected by `GeniusAPIServer::Initialize()` |
| Facts CSV | User-specified path | CLI `--knowledge <path>` |

## Webhooks & Callbacks

**Incoming:**
- gRPC server on `--port` (default `50051`) — accepts `GeniusAPI.Infer` and `GeniusAPI.StreamInfer` calls
- FFI calls from Flutter: `GeniusSlmChatCompletionsCreate(requestJson)`

**Outgoing:**
- Phase 2: SuperGenius gRPC dispatch via `SGProcessingBridge::SubmitNetwork()` (not yet implemented)
- P2P task broadcast and result aggregation via libp2p (not yet fully implemented without real model)

**Streaming:**
- gRPC server-streaming: `StreamInfer(InferRequest) → stream InferToken` for token-by-token output (planned)
- FFI streaming: `GeniusSlmChatCompletionsStream` callback API (planned, Task 7.2)

---

*Integration audit: 2026-05-26*
