# Project Research Summary

**Project:** GNUS NEO SWARM (production readiness + SuperGenius dispatch)
**Domain:** Decentralized AI inference engine with blockchain compute network dispatch
**Researched:** 2026-05-28
**Confidence:** HIGH

## Executive Summary

GNUS NEO SWARM is a decentralized AI inference engine that runs LLMs (primarily Mistral-7B) locally via MNN and dispatches compute workloads to the SuperGenius blockchain network. The project is a prototype that has the right technology bones — MNN, secp256k1, RocksDB, OpenSSL, spdlog, protobuf — but nearly every subsystem operates in stub/fallback mode. The production gap is not a technology-selection problem; it is an **activation and hardening** problem. Every critical dependency is already linked; what's missing is real implementations behind the `#ifdef` guards.

The recommended approach is a security-first, phased build-out: cryptographic identity and message signing must come before any network connectivity, because connecting to a blockchain compute network without real authentication is worse than not connecting at all. A new `SuperGeniusClient` component must encapsulate all communication with the SuperGenius network, using its PubSub room-based dispatch model (not simple unary gRPC). Persistence hardening (RocksDB for reputation, JSON for config) and production fixes (hardcoded values, re-init bugs) then complete the production baseline.

**Key risks:** (1) stub security paths surviving into production create a false sense of security — `MessageSigning::Verify()` always returns `true`; (2) private keys stored as plaintext hex on disk; (3) the SentencePiece/protobuf version conflict means real tokenization and network dispatch cannot coexist in a single binary without dependency resolution; (4) insecure gRPC defaults exposing inference traffic. All are preventable with the specific mitigations prescribed in the research.

## Key Findings

### Recommended Stack

The existing stack (MNN, secp256k1, RocksDB v10.6.x, OpenSSL 3.3.x, spdlog, nlohmann/json, Boost 1.85.0, C++17) is correct and should not be changed. The production additions are targeted and reuse existing dependencies. **Do not** upgrade Boost, require C++20, introduce coroutines for gRPC dispatch, or productionize libp2p — all remain as-is or deferred.

**Core technologies to add or harden:**

- **gRPC v1.78.1 (Callback API):** For SuperGenius network dispatch via PubSub. Use `grpc::experimental::CallbackGenericService`, not the raw CompletionQueue API (300+ line state machines). One channel per CPU, persistent across jobs.
- **Protocol Buffers v29.x:** For dispatch message serialization and replacing the fragile CSV reputation format. Already a project dependency; new `sg_dispatch.proto` defines the SuperGenius compute interface.
- **secp256k1 (real, not stub):** Enable `GENIUS_HAS_SECP256K1`, implement real `MessageSigning::Verify` with `secp256k1_ecdsa_verify`, switch to RFC6979 deterministic nonces to prevent nonce-reuse private key leaks.
- **AES-256-GCM via OpenSSL EVP:** For key-at-rest encryption. Derive keys from passphrase via PBKDF2-HMAC-SHA256 (600K iterations). Self-describing binary file format.
- **RocksDB v10.6.2 (C++17 ceiling):** Replace CSV with protobuf binary serialization. Enable `WriteBatch` for atomic multi-key writes, `sync=true` for critical reputation updates. v10.7+ requires C++20 — avoid.
- **JSON config (nlohmann/json):** Already available. CLI-overrides-config precedence. Never store passphrase in config.

**What NOT to change:** Boost 1.85.0, MNN, SentencePiece, spdlog, OpenSSL 3.3.x, C++17 standard, libp2p (keep stub), existing build infrastructure.

### Expected Features

**Must have (table stakes — P0):**
- Real LLM inference via MNN + SentencePiece (both linked, code paths exist)
- Cryptographic node identity with secp256k1 (single-line cmake fix)
- Message signing and verification (currently always `true` — highest-risk gap)
- gRPC network dispatch to SuperGenius (`SubmitNetwork` returns `NotImplemented`)
- Crash-safe persistent reputation (RocksDB, fix `stod`/`stoull` crash on corrupt data)
- Proper error handling in all production code paths (stop swallowing errors)
- Remove hardcoded vocab size 32000 (read from tokenizer)
- Fix FFI re-init bug (`std::call_once` flag never reset)
- Health/readiness endpoint for operators

**Should have (differentiators — P1):**
- Swarm routing with reputation-weighted consensus (already implemented, needs persistence)
- CRDT-based reputation sync (needs RocksDB snapshots)
- SGProcessing bridge for compute offload (real `SubmitNetwork` implementation)
- FP4 v3 quantization processor (SGProcessingManager path currently missing)
- Encrypted node key file at rest (AES-256-GCM)
- Config file support (JSON, operators can tune without recompiling)
- Security tests proving signatures reject tampering

**Defer to subsequent milestones (anti-features for this milestone):**
- Full libp2p P2P network (GossipSub, mDNS, DHT) — route through SuperGenius gRPC first
- Streaming token output (SSE/WebSocket) — batch responses sufficient
- Semantic embeddings for knowledge retrieval — TF-IDF stub works
- Multi-model hot-swapping — single-model focus
- Mobile (iOS/Android) deployment — macOS first
- Web dashboard / admin UI — CLI sufficient
- Model training / fine-tuning — inference-only engine

### Architecture Approach

A new `SuperGeniusClient` component (six new files in `src/network/sg_client/`) encapsulates all communication with the SuperGenius blockchain compute network. It manages a persistent gRPC channel, publishes signed `Task` messages to the grid channel via PubSub, and subscribes to per-job result channels for `TaskResult` aggregation. The component integrates into the existing `SGProcessingBridge`, which acts as a dispatch router: local mode → `SGProcessingManager`, network mode → `SuperGeniusClient`.

The SuperGenius network uses a room-based GossipPubSub model, not simple unary gRPC. Neo Swarm must join the processing grid channel, publish `Task` messages with secp256k1 signatures, and collect results from `results/<taskId>` channels. This enables SuperGenius's distributed processing infrastructure: queue management, ProcessingNode coordination, subtask splitting, and result aggregation.

**Major components (production state):**

1. **SuperGeniusClient** (NEW) — Channel lifecycle, keepalive, reconnect, PubSub publish/subscribe
2. **SGProcessingBridge** (REFACTORED) — Dispatch router: local MNN path vs. network SuperGenius path
3. **NodeIdentity** (HARDENED) — Real secp256k1 key generation, RFC6979 signing, AES-256-GCM encrypted save/load
4. **MessageSigning** (HARDENED) — Real signature verification, nonce+timestamp replay protection
5. **ReputationStorage** (HARDENED) — RocksDB + protobuf binary serialization, crash-safe deserialization
6. **GeniusAPIServer** (UNCHANGED) — Orchestration façade, single-threaded blocking `Process()` (acceptable for CLI mode)

**Design decisions:**
- PubSub not unary gRPC (matches SuperGenius architecture)
- Single persistent gRPC channel per node (not new connection per job)
- MetadataCredentialsPlugin for identity headers on every call
- Timeout-bounded result collection via condition_variable (not async callbacks)
- Fail-close security stubs: reject when crypto unavailable, don't silently accept
- Every signed message includes nonce + timestamp for replay protection

### Critical Pitfalls

1. **Stub security surviving into production** — `MessageSigning::Verify` always returns `true`. Fix: fail-close (return `false` when secp256k1 unavailable), add `static_assert` that `GENIUS_HAS_SECP256K1` is defined in release builds, runtime check before entering swarm mode. **Address in Phase 1.**

2. **Private key in plaintext on disk** — `SaveToFile` writes 32-byte hex without encryption. Fix: AES-256-GCM encryption with PBKDF2-derived key, file permissions `0600`, passphrase via environment variable `GENIUS_NODE_KEY_PASS`. **Address in Phase 1.**

3. **No replay protection on signed messages** — Signatures cover payload only, no nonce/timestamp. Fix: add 32-byte random nonce + uint64 timestamp to every signed message, track seen nonces in bloom/LRU filter, reject messages outside 30s window. **Address in Phase 2 (network).**

4. **gRPC without TLS in decentralized network** — First implementation likely insecure localhost. Fix: require TLS from first `SubmitNetwork()` implementation, use mTLS with secp256k1-derived certificates. **Address in Phase 2.**

5. **Protobuf version conflict (SentencePiece vs. SGProcessing)** — Both libraries bundle conflicting protobuf versions. Fix: resolve at the dependency level (upgrade/downgrade to shared version), OR use MNN's built-in tokenizer as alternative, OR add CMake hard error when both flags defined simultaneously. **Address in Phase 1 or early Phase 2.**

6. **Reputation storage corruption crashing the process** — Unwrapped `std::stod`/`std::stoull` throw on corrupt CSV. Fix: switch to protobuf binary serialization (eliminates the problem class), or wrap in try/catch with corrupt-record skipping. **Address in Phase 3.**

7. **Deterministic ECDSA nonces (RFC6979) not used** — Random nonces risk private key leak on weak entropy. Fix: switch to `secp256k1_ecdsa_sign` with deterministic nonce function, add test verifying same message produces identical signatures. **Address in Phase 1.**

## Implications for Roadmap

### Phase 1: Security Hardening

**Rationale:** All inter-node communication depends on cryptographic identity. Without real signatures, connecting to SuperGenius is impossible. This phase must complete before any network code ships. The pattern is standard and well-documented — minimal research needed, the code is written (STACK.md §3, ARCHITECTURE.md §Phase 1).

**Delivers:** Real secp256k1 node identity, deterministic RFC6979 signatures, real `MessageSigning::Verify` (fail-close), AES-256-GCM encrypted key storage, security test suite proving rejection of bad signatures.

**Addresses:** P0 features: secp256k1 identity, message signing/verification, encrypted key storage. P0 fixes: enable `GENIUS_HAS_SECP256K1`.

**Avoids:** Pitfalls #1 (stub security), #2 (plaintext keys), #6 (deterministic nonces), #7 partly (protobuf conflict — resolve dependency before network phase).

### Phase 2: Core SuperGenius Connectivity

**Rationale:** This is the system's raison d'être. The `SuperGeniusClient` is the critical new architectural component. It cannot ship without Phase 1 (needs real identity for signed dispatch). The PubSub integration pattern requires understanding SuperGenius's internal architecture — this phase likely needs deeper research during planning. Must resolve the protobuf version conflict before this phase completes (Pitfall #7).

**Delivers:** `SuperGeniusClient` (channel manager, job submitter, result collector, message authenticator), real `SubmitNetwork()` via PubSub, `--sg-endpoint` CLI flag, gRPC with TLS credentials, replay-protected signed messages, request-id for idempotency.

**Uses:** gRPC v1.78.1 Callback API, protobuf v29.x, sg_dispatch.proto, OpenSSL for TLS credentials.

**Implements:** `src/network/sg_client/` (6 new files), refactored `SGProcessingBridge::SubmitNetwork`.

**Avoids:** Pitfalls #3 (replay protection), #4 (unverified results — accept limitation, document trust model), #5 (insecure gRPC), #12 (duplicate job execution).

### Phase 3: Persistence & Reliability

**Rationale:** Reputation data must survive restarts and corrupt data must not crash the process. This phase is independent of Phases 1-2 and can be developed in parallel, but should complete before multi-node deployment. The CSV→protobuf migration is a well-understood pattern documented in STACK.md.

**Delivers:** RocksDB-backed reputation storage with protobuf binary serialization, crash-safe deserialization, atomic multi-key writes (WriteBatch), config file support (JSON via nlohmann/json), health/readiness endpoint, validated config on startup.

**Addresses:** P0 features: crash-safe reputation, config file. P1 features: CRDT sync enablement.

**Avoids:** Pitfall #8 (corrupt DB crashing process), Pitfall #10 (monolithic init swallowing failures — add IsHealthy() and required-vs-optional subsystem distinction).

### Phase 4: Production Polish & Integration

**Rationale:** Fixes the remaining known defects and hardcodes that affect correctness and robustness. These are individually small tasks but collectively gate the production release. Most are low-complexity, well-understood fixes. The FP4_ULTRA processor is the notable exception — it involves GPU compute and quantization logic that may need deeper research.

**Delivers:** Removed hardcoded vocab size 32000, fixed `GeniusSlmInit` re-init race condition, FFI layer bounds checking (64KB request limit, nlohmann/json replacement), network integration tests against SuperGenius test node, FP4_ULTRA processor in SGProcessingManager, production logging with structured fields and rotation, compile-time feature flag hardening (CI matrix).

**Addresses:** P0 fixes: re-init bug, hardcoded vocab size. P1 features: FP4_ULTRA processor. P2 features: FFI tests, network integration tests.

**Avoids:** Pitfalls #9 (hardcoded vocab), #11 (FFI no bounds), #14 (Metal shader warm-up), #15 (OOM on low RAM), #16 (FFI race), #17 (untested build configs).

### Phase 5: Flutter UI Integration

**Rationale:** End-user experience. Depends on the real engine (Phase 1-4) being stable. macOS-only for this milestone. This is application-layer work that doesn't affect the C++ engine architecture.

**Delivers:** Flutter macOS app wired to real `.dylib`, end-to-end chat with real inference, health status display from `IsHealthy()`.

### Phase Ordering Rationale

- **Security MUST come first** — every subsequent phase produces signed messages that would be trivially forgeable without it. The dependency chain is non-negotiable: no real signatures → no authenticated gRPC → no SuperGenius dispatch.
- **SuperGenius connectivity follows security** — the new `SuperGeniusClient` depends on the hardened `NodeIdentity` and `MessageSigning` from Phase 1. It's the largest new code artifact and should be built while persistence work happens in parallel.
- **Persistence is parallelizable** — Phases 2 and 3 do not share code paths. RocksDB reputation work can proceed independently of the gRPC client. If team size permits, these should run concurrently.
- **Polish gates the release** — Phase 4 addresses the long tail of known issues. These are individually small but collectively critical for production quality. The FP4_ULTRA processor within this phase is the riskiest item due to GPU compute complexity.
- **Flutter is the final integration** — depends on a stable, tested C++ engine. Should not be started before Phase 4 is complete.

### Research Flags

**Phases needing deeper research during planning:**
- **Phase 2 (SuperGenius Connectivity):** The PubSub room-based dispatch pattern is unique to SuperGenius. The `gRPCForSuperGenius` service interface, room join/acl semantics, and result channel lifecycle need detailed API research. A spike with the actual SuperGenius test node is recommended before implementing `SuperGeniusClient`.
- **Phase 4 (FP4_ULTRA processor):** FP4 v3 is a proprietary quantization codec. The `FP4Transport` encoding/decoding + MNN forward pass for quantized models has sparse documentation. Research needed on MNN's quantized inference API and the existing `FP4Codec` in the codebase.

**Phases with standard patterns (skip research-phase):**
- **Phase 1 (Security Hardening):** secp256k1, AES-256-GCM, and RFC6979 are all well-documented standard protocols with official library APIs. The STACK.md provides exact implementation patterns. Skip research — go directly to plan-phase.
- **Phase 3 (Persistence & Reliability):** RocksDB + protobuf is a standard pattern with Context7-verified APIs. nlohmann/json config file parsing is trivial. Skip research.
- **Phase 5 (Flutter UI):** Application-layer integration outside the C++ engine scope. Standard Flutter macOS patterns. Skip research.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All recommendations verified against Context7 official docs (gRPC, RocksDB, libsecp256k1, OpenSSL), GitHub release pages, project thirdparty headers, and existing source files. Version pins confirmed (RocksDB v10.6.2 C++17 ceiling, gRPC v1.78.1 stable). |
| Features | HIGH | Current state verified by direct codebase inspection (stub implementations, passing tests, `#ifdef` guards). Industry patterns validated against Context7: Bittensor (420 snippets), vLLM (58K snippets), LiteLLM (16K snippets). Board issues validated against actual code. |
| Architecture | HIGH | Primary sources: actual `SGProcessing.proto`, `SGProcessing-OpenAPI.yaml`, `SGProcessingBridge.cpp`, `MessageSigning.cpp`, `NodeIdentity.cpp`. gRPC auth and channel management patterns verified against gRPC official docs (keepalive, MetadataCredentialsPlugin, TLS credentials). |
| Pitfalls | HIGH | Every critical pitfall cross-referenced against exact source file and line number. Stub behavior confirmed by reading actual implementations. Industry attack vectors (PS3 hack, Bitcoin nonce reuse) are well-documented. Phase warnings mapped to specific PRODUCTION_ROADMAP tasks. |

**Overall confidence:** HIGH — all four research files achieved HIGH confidence independently. The codebase was examined directly, not inferred.

### Gaps to Address

- **SuperGenius service interface details:** The specific internal design of the `gRPCForSuperGenius` service was not examined (it's in the sibling SuperGenius repo). A spike during Phase 2 planning should verify the PubSub room join flow, auth requirements, and result channel lifecycle against the actual SuperGenius implementation.
- **GNUS token economics:** Staking amounts, slashing conditions, and reward distribution parameters were not researched. Pitfall #13 (Sybil attack prevention via PoS) recommendations are generic until these parameters are known. Defer to the milestone where on-chain identity/reputation integration is scoped.
- **MNN LLM API for model warm-up:** Shader compilation and model memory behavior is inferred from MNN docs and GPU patterns, not from testing the actual MNN version in thirdparty. Add a warm-up inference test during Phase 1 to verify.
- **FP4_ULTRA processor details:** The SGProcessingManager FP4 path (`SGProcessors.json`) needs mapping to the existing `FP4Codec`. This is flagged as a research item in Phase 4 (see Research Flags above).

## Sources

### Primary (HIGH confidence — verified against codebase + official docs)
- Context7: gRPC (`/grpc/grpc`) — Callback API, CompletionQueue thread model, keepalive config
- Context7: RocksDB (`/facebook/rocksdb`) — WriteBatch, WAL options, pipelined writes, v10.7.0 C++20 requirement
- Context7: libsecp256k1 (`/bitcoin-core/secp256k1`) — Sign/verify API, normalization, context creation, RFC6979
- Context7: OpenSSL (`/openssl/openssl`) — EVP AES-256-GCM patterns, PBKDF2 key derivation
- Context7: Bittensor (`/latent-to/bittensor`) — Neuron wallet auth, axon/dendrite patterns, stake-weighted sybil resistance
- Context7: vLLM (`/vllm-project/vllm`) — Health endpoints, API key auth, security deployment patterns
- Context7: LiteLLM (`/berriai/litellm`) — Gateway request flow, retry/fallback patterns
- gRPC official docs (grpc.io) — Auth guide, IMQ keepalive, MetadataCredentialsPlugin, interceptors
- Project source files — All stub implementations, `#ifdef` guards, `NodeIdentity` PIMPL, `Error.hpp` codes, `SGProcessing.proto`, `SGProcessing-OpenAPI.yaml`, `genius_api.proto`
- Project planning docs — `PRODUCTION_ROADMAP.md`, `PROJECT_BOARD_ISSUES.md`, `PROJECT.md`, `CONCERNS.md`

### Secondary (MEDIUM confidence — synthesized from multiple sources)
- Industry standards: TLS for inter-node communication (vLLM + community consensus)
- Circuit breakers and graceful degradation patterns (LiteLLM + general gateway practice)
- libsecp256k1 safegcd implementation (informative, not directly actionable)

### Tertiary (LOW confidence — needs validation)
- MNN LLM API behavior for shader caching and model warm-up (inferred, not tested)

---
*Research completed: 2026-05-28*
*Ready for roadmap: yes*
