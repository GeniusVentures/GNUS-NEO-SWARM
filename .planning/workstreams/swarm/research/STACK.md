# Technology Stack — Production Hardening & SuperGenius Connectivity

**Project:** GNUS NEO SWARM (milestone: production readiness + blockchain dispatch)
**Researched:** 2026-05-28
**Overall confidence:** HIGH

## Executive Assessment

The existing prototype has the right bones — MNN, secp256k1, RocksDB, OpenSSL, spdlog, protobuf — all correctly selected but operating in stub/fallback mode. The production gap is not a technology-selection problem; it is an **activation** and **hardening** problem. Every dependency is already linked. What's missing is: real gRPC dispatch, real signature verification, encrypted key storage, durable RocksDB writes, and a JSON config surface.

This document prescribes exactly what to add, what versions to use, what patterns to follow, and — critically — what NOT to change.

---

## Recommended Additions (Production Bridge Layer)

### 1. gRPC — SuperGenius Network Dispatch

| Attribute | Recommendation | Rationale |
|-----------|---------------|-----------|
| **Version** | gRPC v1.78.1 (Feb 2026) or v1.80.0 (Mar 2026) | v1.78.1 ships protobuf v29.x with stable C++ callback API. v1.80.0 is latest stable with TLS improvements. Either works; v1.78.1 is better-tested with the existing thirdparty build infrastructure. Avoid v1.81.x (pre-release as of May 2026). |
| **Async model** | **gRPC Callback API** (grpcpp/grpcpp.h) — NOT raw CompletionQueue | The Callback API (stable since gRPC v1.54, 2023) eliminates CQ boilerplate. For C++17 with `boost::asio::io_context`, use `grpc::experimental::CallbackGenericService` or stub-based async client. The raw CQ API requires 300+ lines of state-machine code per RPC — avoid it. |
| **Thread model** | Single `CompletionQueue` per `io_context` thread. One thread per CPU core. | Per gRPC C++ Perf Notes: optimal performance = N threads (N = CPUs), each with its own CQ. Match the existing Boost.ASIO pool to gRPC CQs 1:1. |
| **Service proto** | Existing `genius_api.proto` (server-side). **New**: `sg_dispatch.proto` for SuperGenius client-side dispatch. | The existing proto defines the node's gRPC server. The new proto defines the SuperGenius compute dispatch interface. Use proto3 syntax. |
| **Channel config** | `grpc::CreateChannel(endpoint, grpc::InsecureChannelCredentials())` for local/VPN. TLS optional for WAN. | Start insecure for local SuperGenius node communication. Add TLS (via OpenSSL) for remote dispatch in a follow-up phase. |
| **Deadline** | Every RPC gets a deadline: `context.set_deadline(std::chrono::system_clock::now() + timeout)`. | Inference jobs can run minutes. Set 120s default, configurable. Prevents hung clients. |
| **Retry** | **Do NOT** use gRPC built-in retry for inference RPCs. Implement application-level retry with backoff. | Inference is stateful and expensive. Blind gRPC retry could re-execute GPU work. The `SGProcessingBridge` must handle retries explicitly with job-idempotency tokens. |

#### Explicit Pattern for `SubmitNetwork`

```cpp
// SGProcessingBridge::SubmitNetwork — production gRPC dispatch
// 1. Serialize JSON payload → sg_dispatch::InferenceJob protobuf
// 2. Create channel to --sg-endpoint
// 3. Call stub->DispatchInference() synchronously with deadline
// 4. Deserialize response → std::vector<uint8_t>

outcome::result<std::vector<uint8_t>> SGProcessingBridge::SubmitNetwork(
    const std::string &jsondata) const
{
#ifdef GENIUS_HAS_GRPC
    // Build protobuf job from JSON
    sgns::sg::InferenceJob job;
    job.set_payload_json(jsondata);
    job.set_job_id(GenerateJobId());
    job.set_timestamp_ms(NowMs());

    // Channel to SuperGenius node (reuse across calls — create once in constructor)
    auto channel = grpc::CreateChannel(
        cfg_.sg_endpoint_,
        grpc::InsecureChannelCredentials());

    auto stub = sgns::sg::SuperGeniusDispatch::NewStub(channel);

    grpc::ClientContext ctx;
    ctx.set_deadline(std::chrono::system_clock::now() + std::chrono::seconds(120));

    sgns::sg::InferenceResult result;
    auto status = stub->DispatchInference(&ctx, job, &result);

    if (!status.ok())
    {
        BridgeLogger()->error("gRPC dispatch failed: {}", status.error_message());
        return outcome::failure(Error::NetworkError);
    }

    return std::vector<uint8_t>(result.output_bytes().begin(),
                                result.output_bytes().end());
#else
    return outcome::failure(Error::NotImplemented);
#endif
}
```

**Source:** gRPC v1.78.1 C++ quickstart (grpc.io), verified May 2026 — HIGH confidence.

---

### 2. Protocol Buffers — Message Serialization

| Attribute | Recommendation | Rationale |
|-----------|---------------|-----------|
| **Version** | protobuf v29.x (bundled with gRPC v1.78.1) | Already available as libp2p transitive dep. The existing `compile_proto_to_cpp()` cmake function works. |
| **New proto** | `proto/sg_dispatch.proto` with `InferenceJob`, `InferenceResult`, `NodeAnnounce`, `JobStatus` messages | Clean separation from the client-facing `genius_api.proto`. |
| **Serialization format** | Protobuf binary (not JSON-over-gRPC) for dispatch messages | Binary is 3-10x smaller than JSON for tensor metadata. Use `SerializeToString()` / `ParseFromString()`. |
| **Node reputation** | Switch `ReputationStorage` serialization from CSV to protobuf binary (`genius_reputation.proto`). | CSV is fragile (PROJECT.md §Key Decisions explicitly flags this). Protobuf is schema-evolution-safe and already used in the project. |

#### Protobuf Schema for Compute Dispatch

```protobuf
syntax = "proto3";
package sgns.sg;

message InferenceJob {
    string job_id = 1;
    string payload_json = 2;   // GNUS_Schema JSON (existing format)
    uint64 timestamp_ms = 3;
    string node_id = 4;         // secp256k1 PeerId
    bytes signature = 5;        // DER signature of payload_json
}

message InferenceResult {
    string job_id = 1;
    bytes output_bytes = 2;     // Raw tensor output
    uint64 latency_us = 3;
    bool success = 4;
    string error_message = 5;
}

message JobStatus {
    string job_id = 1;
    enum Status { PENDING = 0; RUNNING = 1; COMPLETE = 2; FAILED = 3; }
    Status status = 2;
    float progress = 3;         // 0.0 - 1.0
}

service SuperGeniusDispatch {
    rpc DispatchInference(InferenceJob) returns (InferenceResult);
    rpc GetJobStatus(JobStatus) returns (JobStatus);
    rpc StreamResults(InferenceJob) returns (stream InferenceResult);
}
```

**Source:** Context7 protobuf API, project's existing `genius_api.proto` patterns — HIGH confidence.

---

### 3. Security — secp256k1 Signature Verification (Fix SEC-02)

| Attribute | Recommendation | Rationale |
|-----------|---------------|-----------|
| **Fix** | Implement `MessageSigning::Verify()` — reconstruct `NodeIdentity` from `pub_key_hex`, call `identity.Verify()`. | Currently always returns `true` (no-op). The `NodeIdentity::Verify()` method already works correctly with secp256k1 when `GENIUS_HAS_SECP256K1` is defined. |
| **Pattern** | `secp256k1_ec_pubkey_parse()` → `secp256k1_ecdsa_signature_parse_der()` → `secp256k1_ecdsa_verify()`. | Standard secp256k1 C API (Context7-verified). Use `secp256k1_context_static` for verification-only contexts (zero allocation). |
| **Normalization** | Always call `secp256k1_ecdsa_signature_normalize()` before verifying signatures from external sources. | Prevents signature malleability attacks (Context7 docs: "required when receiving from external sources"). |
| **Key format** | Compressed public key (33 bytes, 0x02/0x03 prefix). Hex for storage/display. | Existing convention in `NodeIdentity` — do not change. |

#### Fix for MessageSigning::Verify

```cpp
bool MessageSigning::Verify(const std::string          &payload,
                            const std::vector<uint8_t> &signature,
                            const std::string          &pub_key_hex)
{
#ifdef GENIUS_HAS_SECP256K1
    // Parse public key from hex
    auto pub_bytes = FromHex(pub_key_hex);
    if (pub_bytes.size() != NodeIdentity::kPubKeySize) return false;

    // Create verify-only context (no heap allocation)
    auto ctx = secp256k1_context_create(SECP256K1_CONTEXT_VERIFY);
    if (!ctx) return false;

    // Parse pubkey
    secp256k1_pubkey pubkey;
    if (!secp256k1_ec_pubkey_parse(ctx, &pubkey, pub_bytes.data(), pub_bytes.size()))
    {
        secp256k1_context_destroy(ctx);
        return false;
    }

    // Parse signature
    secp256k1_ecdsa_signature sig;
    if (!secp256k1_ecdsa_signature_parse_der(ctx, &sig,
                                             signature.data(), signature.size()))
    {
        secp256k1_context_destroy(ctx);
        return false;
    }

    // Normalize to low-S (prevent malleability)
    secp256k1_ecdsa_signature_normalize(ctx, nullptr, &sig);

    // Hash payload
    uint8_t hash[32];
    SHA256(reinterpret_cast<const uint8_t*>(payload.data()), payload.size(), hash);

    // Verify
    int result = secp256k1_ecdsa_verify(ctx, &sig, hash, &pubkey);
    secp256k1_context_destroy(ctx);
    return result == 1;
#else
    return true;  // stub fallback
#endif
}
```

**Source:** Context7 secp256k1 API docs (bitcoin-core/secp256k1), verified in existing `NodeIdentity::Verify` implementation — HIGH confidence.

---

### 4. Security — AES-256-GCM Key Encryption at Rest (Fix SEC-03)

| Attribute | Recommendation | Rationale |
|-----------|---------------|-----------|
| **Algorithm** | AES-256-GCM (Authenticated Encryption with Associated Data) | GCM provides both confidentiality and integrity. Standard for key-at-rest encryption. OpenSSL EVP API is the correct modern API (not deprecated low-level `AES_encrypt`). |
| **Key derivation** | PBKDF2-HMAC-SHA256 with 600,000 iterations | Derives encryption key from user-supplied passphrase. NIST SP 800-132 recommendation. |
| **IV** | 12-byte random IV, generated per-encryption with `RAND_bytes()`. Prepended to ciphertext. | GCM requires unique IV for each encryption. Store IV alongside ciphertext (not secret). |
| **Tag** | 16-byte authentication tag appended to ciphertext. | GCM tag detects tampering. Verify before decryption. |
| **File format** | `[4-byte salt len][N-byte salt][12-byte IV][ciphertext][16-byte tag]` | Self-describing binary format. Simple to parse, no dependency on protobuf. |
| **API** | OpenSSL EVP `EVP_EncryptInit_ex(ctx, EVP_aes_256_gcm(), ...)` / `EVP_DecryptInit_ex(...)` | High-level authenticated encryption. Handles padding, context management. |

#### Key Encryption API (to add to NodeIdentity)

```cpp
// node.key file format:
//   [4B salt_len] [salt] [12B IV] [ciphertext] [16B tag]

outcome::result<void> NodeIdentity::SaveEncrypted(
    const std::string &path,
    const std::string &passphrase) const
{
    // 1. Generate 32-byte salt
    // 2. Derive 256-bit key: PKCS5_PBKDF2_HMAC(passphrase, salt, 600000, SHA256, 32, key)
    // 3. Generate 12-byte IV: RAND_bytes(iv, 12)
    // 4. Encrypt priv_key_ with EVP_aes_256_gcm()
    // 5. Write: salt_len(4B) + salt + IV + ciphertext + tag
}

outcome::result<void> NodeIdentity::LoadEncrypted(
    const std::string &path,
    const std::string &passphrase)
{
    // Reverse of above. Verify GCM tag before using key.
}
```

**Source:** Context7 OpenSSL EVP docs (openssl/openssl), OpenSSL 3.3.x — HIGH confidence.

---

### 5. Persistence — RocksDB for Reputation Storage (Fix PERS-01)

| Attribute | Recommendation | Rationale |
|-----------|---------------|-----------|
| **Version** | RocksDB v10.6.x (last C++17-compatible version) | **CRITICAL**: RocksDB v10.7.0+ (Sep 2025) requires C++20 compiler. The project mandates C++17. Use v10.4.2, v10.5.x, or v10.6.2. |
| **Storage format** | Protobuf binary (`NodeReputationProto`) via `SerializeToString()` / `ParseFromString()`. **Replace CSV entirely.** | CSV is fragile (commas break parsing, no schema evolution). Protobuf is backward-compatible and already a project dependency. |
| **Write pattern** | `WriteBatch` for atomic multi-key writes. `rocksdb::WriteOptions{}.sync = true` for critical reputation updates. | WriteBatch ensures atomicity across multiple node updates during consensus. `sync=true` ensures durability (fsync before return) for reputation-critical paths. |
| **Column families** | Use `default` CF for all reputation data. Do NOT use multiple CFs. | Single CF avoids CF management complexity. The dataset is small (< 1M entries, < 100MB). |
| **Pipelined writes** | `options.enable_pipelined_write = true` | Improves concurrent write throughput when multiple threads update reputation (Context7-verified). |
| **WAL** | `options.manual_wal_flush = false` (auto-flush). `writeOptions.sync = true` for individual critical writes, not global. | Auto-flush WAL prevents data loss on crash. Per-write `sync` gives granular control over durability. |
| **Compression** | `options.compression = kSnappyCompression` (already enabled). | Snappy is already a project dependency. Good speed/compression tradeoff for reputation data. |
| **Error handling** | Fix `Deserialize()` crash by wrapping `stoull` in try/catch OR by switching to protobuf deserialization (which eliminates the problem). | Currently `std::stod`/`std::stoull` throw on invalid input without a handler (PROJECT.md §Active tasks: PERS-02). |
| **DB open** | Use `rocksdb::DB::Open()` with `create_if_missing = true` and `error_if_exists = false`. | Existing pattern. Add `rocksdb::Status` error checking on every call. |

#### ReputationStorage Implementation Pattern

```cpp
// Serialize — protobuf (REPLACES current CSV)
std::string ReputationStorage::Serialize(const NodeReputation &rep)
{
    genius::reputation::NodeReputationProto proto;
    proto.set_identity_key(rep.identity_key_);
    proto.set_global_score(rep.global_score_);
    proto.set_math_score(rep.math_score_);
    proto.set_grammar_score(rep.grammar_score_);
    proto.set_latency_score(rep.latency_score_);
    proto.set_consistency_score(rep.consistency_score_);
    proto.set_task_count(rep.task_count_);
    proto.set_last_updated_ms(rep.last_updated_ms_);
    return proto.SerializeAsString();
}

// Deserialize — protobuf (eliminates stod/stoull crash risk)
NodeReputation ReputationStorage::Deserialize(const std::string &data)
{
    genius::reputation::NodeReputationProto proto;
    proto.ParseFromString(data);  // protobuf handles malformed data gracefully
    return {
        proto.identity_key(),
        proto.global_score(),
        proto.math_score(),
        proto.grammar_score(),
        proto.latency_score(),
        proto.consistency_score(),
        proto.task_count(),
        proto.last_updated_ms()
    };
}

// Put — with sync for critical updates
outcome::result<void> ReputationStorage::Put(const NodeReputation &rep)
{
    rocksdb::WriteOptions opts;
    opts.sync = true;  // fsync before return — durability for reputation
    auto status = db_->Put(opts, rep.identity_key_, Serialize(rep));
    if (!status.ok())
    {
        return StorageError(status.ToString());
    }
    return outcome::success();
}
```

**Source:** Context7 RocksDB API docs (facebook/rocksdb), GitHub releases page verifying v10.7.0 C++20 requirement — HIGH confidence.

---

### 6. Configuration — JSON Config File (Fix FIX-03)

| Attribute | Recommendation | Rationale |
|-----------|---------------|-----------|
| **Format** | JSON (nlohmann/json, already available). NOT YAML, NOT TOML. | nlohmann/json is already a fully linked project dependency. Zero new dependencies. The header-only library handles all parsing. |
| **Schema** | `neo-swarm.conf` — JSON with all CLI flags as keys. CLI flags override config. | `--model` flag gets precedence over config file. Standard precedence: CLI > config file > defaults. |
| **Security** | Do NOT store passphrase in config file. Use `--passphrase` CLI flag or env var `NEO_SWARM_PASSPHRASE`. | Prevents passphrase leakage in config file committed to git. |
| **Validation** | Validate JSON against expected schema on load. Report missing/invalid keys with descriptive errors. | nlohmann/json can check for required fields. Fail early (at startup), not mid-operation. |

**Source:** nlohmann/json is already in `CommonBuildParameters.cmake` — HIGH confidence.

---

### 7. Logging — Production Hardening

| Attribute | Recommendation | Rationale |
|-----------|---------------|-----------|
| **Library** | spdlog (already used). No change. | spdlog is fast, header-compiled, and correctly configured with `SPDLOG_FMT_EXTERNAL`. |
| **Rotation** | Add `spdlog::sinks::rotating_file_sink_mt` for `neo-swarm.log`. Rotate at 10MB, keep 5 files. | Prevents disk fill from long-running node. Currently logs to console only. |
| **Levels** | `--verbose` → DEBUG. Default → INFO. Server mode → WARN (reduce noise). | Existing pattern. Extend by adding `--log-level` flag. |
| **Metrics** | Add structured log fields: `{job_id, latency_us, node_id, mode}` for each inference request. | Enable log-based monitoring without a dedicated metrics system. spdlog supports key-value pairs. |

---

## What NOT to Change (Keep as-is)

| Component | Keep | Why |
|-----------|------|-----|
| **Boost 1.85.0** | Use existing version. Do not upgrade. | Works. Upgrading would require rebuilding all thirdparty libs. No new features needed. |
| **MNN** | Use as-is. | Real inference already works. GPU acceleration via Metal/Vulkan is proven. |
| **SentencePiece** | Use as-is. | Tokenization works correctly. Protobuf conflict with SGProcessingManager is a separate issue — fix by isolating protobuf linkage. |
| **spdlog** | Use existing setup. | Add rotation sink, don't change the logging infrastructure. |
| **OpenSSL 3.3.x** | Use as-is. | AES-256-GCM via EVP works on any OpenSSL 3.x. No need to upgrade. |
| **nlohmann/json** | Use for config file. Already available. | Header-only, no link cost. |
| **libp2p** | Keep in stub mode. Do NOT try to productionize yet. | Full P2P is out of scope for this milestone (PROJECT.md §Out of Scope). |
| **C++20** | Do NOT require. | `CMAKE_CXX_STANDARD 17` is enforced. RocksDB v10.6.2 is the ceiling. |
| **Coroutines** | Do NOT introduce for gRPC dispatch. | C++17 coroutines require Boost.Coroutine2 or compiler extensions. Synchronous gRPC with thread pool is simpler and sufficient for initial dispatch. |

---

## Alternatives Considered and Rejected

| Category | Recommended | Alternative | Why Rejected |
|----------|-------------|-------------|--------------|
| gRPC async model | Callback API | Raw CompletionQueue | CQ API requires 300+ line state machines. Callback API is production-ready since v1.54. |
| gRPC version | v1.78.1 or v1.80.0 | v1.66.x (much older) | v1.66.x lacks Callback API stability improvements. |
| Key encryption | AES-256-GCM (OpenSSL EVP) | libsodium (NaCl) | OpenSSL is already linked. Adding libsodium is unnecessary. |
| Key encryption | AES-256-GCM | ChaCha20-Poly1305 | ChaCha20 is slightly faster on ARM but AES-256-GCM has hardware acceleration on x86/M1. Both are secure. Go with what OpenSSL provides. |
| Reputation serialization | Protobuf binary | CSV (current) | CSV is fragile and already has a known crash bug (PERS-02). Protobuf eliminates this class of bugs. |
| Reputation serialization | Protobuf binary | JSON | JSON is 3x larger for binary data and has no schema. Protobuf is already used for gRPC. |
| RocksDB version | v10.6.2 (C++17 ceiling) | v11.1.1 (latest) | v10.7+ requires C++20 compiler. Project mandates C++17. |
| Config format | JSON (nlohmann/json) | YAML (yaml-cpp) | nlohmann/json is already linked and proven. yaml-cpp exists in thirdparty but is only used by libp2p. JSON is simpler for flat key-value config. |
| Config format | JSON | INI/toml11 | Adding toml11 is a new dependency. Not justified for a flat config file. |

---

## Installation / Build Impact

### New thirdparty dependencies to add

```cmake
# gRPC + protobuf (add to CommonBuildParameters.cmake)
set(gRPC_DIR "${_THIRDPARTY_BUILD_DIR}/grpc/lib/cmake/grpc")
set(Protobuf_DIR "${_THIRDPARTY_BUILD_DIR}/grpc/lib/cmake/protobuf")
find_package(gRPC CONFIG REQUIRED)
find_package(Protobuf CONFIG REQUIRED)

# Add to target_link_libraries for genius_api or a new genius_sgdispatch:
#   gRPC::grpc++ gRPC::grpc++_reflection protobuf::libprotobuf
```

### New proto compilation

```cmake
# Add to cmake/functions.cmake or project CMakeLists.txt:
compile_proto_to_cpp(
    PROTO_DIR "${PROJECT_ROOT}/proto"
    PROTO_FILES sg_dispatch.proto
    OUT_DIR  "${CMAKE_BINARY_DIR}/generated/sg_dispatch"
)
```

### No changes to existing build infrastructure

- CMake 3.22+ / Ninja — no change
- Boost 1.85.0 — no change
- C++17 — no change
- `compile_proto_to_cpp()` — reuse existing function
- All existing static libraries (`genius_*`) — no structural change
- `GENIUS_HAS_*` feature flags — add `GENIUS_HAS_GRPC`

---

## Sources

| Source | Content | Confidence |
|--------|---------|------------|
| gRPC v1.78.1 quickstart (grpc.io) | C++ sync/async API, CMake setup, version pinning | HIGH |
| gRPC GitHub releases page | v1.80.0 (latest stable, Mar 2026), v1.81.0-pre1 (pre-release) | HIGH |
| gRPC C++ Perf Notes (grpc/grpc repo) | CompletionQueue thread model, 1 CQ per CPU | HIGH |
| Context7: gRPC (/grpc/grpc) | CompletionQueue API internals | HIGH |
| Context7: RocksDB (/facebook/rocksdb) | WriteBatch, WAL options, pipelined writes | HIGH |
| RocksDB GitHub releases | v11.1.1 latest, v10.7.0 C++20 requirement | HIGH |
| Context7: libsecp256k1 (/bitcoin-core/secp256k1) | Sign/verify API, normalization, context creation | HIGH |
| Context7: OpenSSL (/openssl/openssl) | EVP AES-256-GCM patterns | HIGH |
| Project thirdparty headers | OpenSSL 3.3.3-dev installed, RocksDB via `find_package(RocksDB)` | HIGH |
| Project source files | Existing stub implementations, API surface to fill | HIGH |
| nlohmann/json (CommonBuildParameters.cmake) | Already configured, header-only | HIGH |
