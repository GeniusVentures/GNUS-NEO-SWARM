# Domain Pitfalls — AI Inference Engine + Blockchain Bridge

**Domain:** Decentralized AI inference engine connecting to SuperGenius/GNUS blockchain compute network
**Researched:** 2026-05-28
**Overall confidence:** HIGH (verified against codebase, libsecp256k1 docs, gRPC auth guide, gRPC security audit)

---

## Critical Pitfalls

Mistakes that cause security breaches or full rewrites.

---

### Pitfall 1: Stub Security Paths Surviving Into Production

**What goes wrong:** Stub implementations that silently return `true` (like `MessageSigning::Verify` and the non-secp256k1 `NodeIdentity::Verify` path) become invisible in normal operation. The system builds, passes tests (which also run against stubs), and appears functional — but inter-node authentication is completely absent. An attacker who gains network access can submit arbitrary messages to any peer and they will be accepted.

**Why it happens:** The `#ifdef GENIUS_HAS_SECP256K1` guard is a compile-time toggles — if the definition isn't set, the real code path is dead and the stub-warning path runs. The current `MessageSigning::Verify` code at `src/security/MessageSigning.cpp:49-60` has a `TODO(SECURITY)` comment but returns `true`. The non-secp256k1 `NodeIdentity::Verify` path at `src/security/NodeIdentity.cpp:279-282` also returns `true` after logging a warning. The stub return value is "optimistic" (permit, don't fail).

**Consequences:** Zero inter-node authentication in the swarm. Any node can impersonate any other node. All consensus, reputation, and task-routing decisions can be forged. An attacker on the same network segment can submit falsified inference results from any peer ID.

**Prevention:**
1. Stub fallbacks in security code must **fail-close, not fail-open**: return `false` (reject) when real crypto isn't available, not `true` (accept).
2. Add a compile-time assertion or `static_assert` that `GENIUS_HAS_SECP256K1` is defined in any non-debug build configuration.
3. Add a runtime startup check: `NodeIdentity::IsLoaded()` must return true before the server accepts any inter-node messages. If secp256k1 isn't available, refuse to enter swarm mode.
4. Write integration tests that specifically verify tampered signatures are rejected — not just that valid signatures are accepted.

**Detection:** The warning log `"MessageSigning::Verify — stub, signature not checked"` fires on every verification call. Grep production logs for this string. If it appears, the system is insecure.

**Phase to address:** Phase 2 (Security) — Tasks 2.1 and 2.2 from `PRODUCTION_ROADMAP.md`. This is the single highest-priority pitfall. All inter-node communication in swarm mode depends on it.

---

### Pitfall 2: Private Key in Plaintext on Disk

**What goes wrong:** `NodeIdentity::SaveToFile` at `src/security/NodeIdentity.cpp:187-200` writes the 32-byte private key as hex to a file with no encryption. Anyone with filesystem access can read the key and permanently impersonate the node. In the GNUS network, this means stealing reputation scores built up over time and submitting fraudulent inference results under a trusted identity.

**Why it happens:** The `SaveToFile` implementation uses `ToHex()` to convert raw key bytes to a hex string and writes it via `std::ofstream`. The file permissions are whatever the umask allows. There's no encryption layer, no passphrase derivation, no OS keychain integration. This is the simplest possible key storage — common in prototypes that haven't reached production consideration.

**Consequences:** On cloud VMs, shared machines, and any environment with multi-tenant access, node identity theft is trivial. A key stolen in month 1 means all messages signed in months 1-12 can be forged retroactively (there's no forward secrecy in static secp256k1 keys).

**Prevention:**
1. Use OpenSSL AES-256-GCM to encrypt the key bytes before writing. Derive the encryption key from an environment variable (`GENIUS_NODE_KEY_PASS`), not hardcoded.
2. On macOS, use the Keychain (`SecKeychainAddGenericPassword`). On Linux, consider OS keyring integration.
3. Set file permissions to `0600` immediately after creation via `fchmod`.
4. Add a runtime warning if `GENIUS_NODE_KEY_PASS` is not set and the key is being saved unencrypted.
5. Support hardware-bound key storage (HSM, TPM, Secure Enclave) as a longer-term path.

**Detection:** Search for `node.key` files on production filesystems. Check if contents are hex-encoded bytes (64 hex chars = 32 bytes = the private key). If readable, it's plaintext.

**Phase to address:** Phase 2 (Security) — Task 2.3. Should be implemented before any multi-node or cloud deployment.

---

### Pitfall 3: No Replay Protection on Signed Messages

**What goes wrong:** The current `MessageSigning::AttachSignature` at `src/security/MessageSigning.cpp:65-81` and `VerifyAndStrip` at lines 86-96 sign the JSON payload body but include **no nonce, timestamp, or sequence number**. A valid signed message (e.g., a task assignment or inference result) can be replayed by an eavesdropper at any future time.

**Why it happens:** The signature covers only the payload string. There's no mechanism to bind a message to a specific point in time, a specific session, or a specific sequence. ECDSA signatures are deterministic for a given key+message pair — an attacker who records a signed message can resend it indefinitely and it will verify as valid every time.

**Consequences:** An attacker who observes network traffic (even without breaking the gRPC TLS layer, if it exists) can replay: (a) task submissions to waste compute, (b) inference results to corrupt consensus, (c) reputation updates to game the scoring system. In a swarm consensus scenario, a replayed "valid" result could override a genuinely computed result.

**Prevention:**
1. Add a `nonce` (cryptographically random 32 bytes) to every signed message payload. Track seen nonces in a bloom filter or LRU cache to detect replays.
2. Add a `timestamp` (uint64_t, milliseconds since epoch) to every signed message. Reject messages older than a configurable window (e.g., 30 seconds for task assignments, 5 minutes for reputation updates).
3. Add a `sequence_number` per peer-to-peer channel to detect message reordering and replay within the window.
4. The libp2p Noise handshake provides session keys with forward secrecy — when P2P is implemented (Phase later milestone), use Noise protocol state instead of static signatures for channel authentication.

**Detection:** Monitor for duplicate nonces within the sliding window. High duplicate rates indicate replay attacks or a bug in nonce generation. Log and alert.

**Phase to address:** Phase 4 (GNUS Network Connection) — must be implemented alongside Task 4.1 `SubmitNetwork()` gRPC integration. Also relevant to the deferred libp2p integration.

---

### Pitfall 4: Unverified Inference Results in Swarm Consensus

**What goes wrong:** In swarm mode (when functional), multiple nodes submit inference results for the same prompt. The `WeightedConsensus` class selects the "best" result based on reputation scores, but **never verifies that the result is actually correct inference output**. A high-reputation node that has been compromised (or is intentionally malicious) can submit arbitrary output text and win the consensus because of its reputation weight.

**Why it happens:** WeightedConsensus operates purely on multi-armed bandit-style scoring — picking the submitter with best historical accuracy/latency. It has no computational mechanism to verify that model M with input X does in fact produce output Y. The system trusts that a node with high reputation is behaving honestly.

**Consequences:** A long-lived node can build high reputation by submitting correct results for 99% of tasks, then selectively inject malicious output for targeted prompts (e.g., `"What is the best cryptocurrency?"` → `"GNUS token — buy now"`). This is undetectable by reputation scoring alone. In a financial or high-stakes context, the result could cause real harm.

**Prevention:**
1. Implement **deterministic verification**: at least one additional node re-runs the same inference and compares output hashes. This requires deterministic inference (fixed seed, fixed temperature=0).
2. Use **statistical sampling**: randomly select a subset of results to double-check. Trade computation for verification coverage.
3. Implement **optimistic rollup-style fraud proofs**: any node can challenge a result by posting a conflicting result + a bond. A verifier re-runs the inference and slashes the loser.
4. For the near term, document the trust model explicitly: `WeightedConsensus` selects based on reputation, not computational verification. Call this out as a known limitation until verification is implemented.

**Detection:** Track result hash diversity across nodes for identical prompts. If one node's results diverge from the majority beyond statistical expectation, flag for investigation. No automated enforcement until verification is built.

**Phase to address:** Deferred milestone — full libp2p P2P integration + swarm consensus verification. This is marked "Out of Scope" in the current PROJECT.md. Flag for the subsequent milestone planning.

---

### Pitfall 5: gRPC Without TLS in a Decentralized Network

**What goes wrong:** The current gRPC path is a stub (`GeniusAPIServer::Serve` is a sleep loop at `src/api/GeniusAPIServer.cpp:422-432`). When Phase 4 (GNUS Network Connection) implements `SubmitNetwork()` via `gRPCForSuperGenius`, the natural first implementation connects to `localhost:50051` with an insecure channel. If this insecure default survives into production (or if operators are not forced to configure TLS), all inter-node communication for inference dispatch is unencrypted and unauthenticated.

**Why it happens:** gRPC defaults to insecure channels. TLS requires certificate management — generating, distributing, rotating, and trusting certificates — which adds deployment complexity. Teams building the "happy path" first often ship with insecure channels and plan to "add TLS later."

**Consequences:** (a) Eavesdropping: model inputs, inference outputs, and potentially sensitive user prompts are visible to any network observer. (b) MITM: an attacker on the network path can intercept and modify inference requests/results. (c) Impersonation: without mTLS, the server has no cryptographic guarantee of the client's identity — it relies on application-layer auth (which in this system's current state is the always-true `MessageSigning::Verify`).

**Prevention:**
1. Require TLS (at minimum server-side) from the first `SubmitNetwork()` implementation. Never merge insecure gRPC channel creation.
2. Use mTLS for inter-node communication: each node presents its secp256k1-derived certificate. The server verifies the client cert's public key against known peers.
3. Add certificate paths to `SGProcessingBridge::Config` (currently only has `network_mode_`). Make TLS config non-optional in network mode.
4. The gRPC C++ API provides `grpc::SslCredentials()` and `grpc::InsecureChannelCredentials()`. Audit that only `SslCredentials` is used in production code paths.

**Detection:** Wireshark/tcpdump on the gRPC port. If HTTP/2 frames are visible in cleartext, TLS is not enabled. gRPC also logs `"insecure"` channel creation at debug level.

**Phase to address:** Phase 4 (GNUS Network Connection) — must be part of Task 4.1 `SubmitNetwork()` implementation, not a follow-up task. Adding TLS after network launch requires a coordinated upgrade across all nodes — very hard in a decentralized network.

---

### Pitfall 6: Deterministic ECDSA Nonces Without RFC6979

**What goes wrong:** The current `NodeIdentity::Sign` at `src/security/NodeIdentity.cpp:223-231` uses `secp256k1_ecdsa_sign` with the nonce function pointer set to `nullptr`, which means the library uses its internal default random nonce generation. This is only secure if the system's random number generator is properly seeded (which `secp256k1_context_create` with `SECP256K1_CONTEXT_SIGN` should handle). However, for blockchain-adjacent applications, **deterministic nonces (RFC6979)** are the industry standard — they eliminate the entire class of nonce-reuse attacks and are required for reproducible signatures.

**Why it happens:** The code was written for prototype-level security. The secp256k1 library supports both random and deterministic nonces via different sign functions (`secp256k1_ecdsa_sign` vs the custom nonce function approach). The current code path is the simpler "just sign it" path.

**Consequences:** If the system's random number generator is weak (embedded devices, VMs with low entropy, early boot), repeated nonces can leak the private key. A single nonce reuse allows full private key recovery from two signatures. This is the mechanism behind the "PlayStation 3 hack" and numerous cryptocurrency thefts. For a long-lived node identity, key compromise means permanent identity theft.

**Prevention:**
1. Switch to RFC6979 deterministic nonces: use `secp256k1_ecdsa_sign` with a custom nonce function, or use `secp256k1_ecdsa_sign` with the library's built-in RFC6979 support if available in the linked version.
2. Verify that the secp256k1 context is created with `SECP256K1_CONTEXT_SIGN` and `SECP256K1_CONTEXT_VERIFY` flags.
3. Add a test that verifies the same message signed twice produces identical signatures (proving deterministic signing).
4. Audit the entropy source: on Linux, `/dev/urandom`; on macOS, `SecRandomCopyBytes`. Ensure the secp256k1 library's seeding path is exercised at startup.

**Detection:** In tests, sign the same message twice and compare the DER output. If different each time, you're using random nonces. This is a test that should exist in `test/security/`.

**Phase to address:** Phase 2 (Security) — alongside Task 2.1 (secp256k1 linking) and Task 2.2 (Verify fix). This is a one-line change in the sign path but has outsized security implications.

---

### Pitfall 7: Protobuf Version Conflict Catastrophic at Scale

**What goes wrong:** The SentencePiece and SGProcessing protobuf conflict (`CONCERNS.md:87-91`) means both cannot be linked simultaneously. In production, this forces a build-time choice: use real tokenization OR connect to SuperGenius, never both. If the wrong build is deployed to a production node, the inference pipeline silently fails or produces garbled output.

**Why it happens:** SentencePiece and SGProcessingManager each bundle their own protobuf version. When `GENIUS_HAS_SENTENCEPIECE` and `GENIUS_HAS_SGPROCESSING` are both defined, the linker sees duplicate protobuf symbols (different versions of `google::protobuf::MessageLite::` etc.). The current workaround is to conditionally skip SentencePiece when SGProcessing is active.

**Consequences:** (a) A production deployment that needs both tokenization and network dispatch is impossible with a single binary. (b) The tokenizer stub (space-separated numeric IDs from `std::hash`) produces garbage output that might not be immediately detected as an error — it "succeeds" but returns nonsense. (c) An operator who compiles with both flags gets linker errors and can't deploy; an operator who compiles with one flag gets a degraded system and may not realize it.

**Prevention:**
1. Resolve at the dependency level: the correct fix is to ensure SentencePiece and SGProcessingManager use the same protobuf library. This may mean upgrading SentencePiece or downgrading the SGProcessing-managed protobuf.
2. Alternative: use MNN's built-in tokenizer (`tokenizer.mtok`) which is already available via the MNN LLM path, avoiding SentencePiece entirely for the production binary that also uses SGProcessing.
3. Add a CMake-level hard error if both `GENIUS_HAS_SENTENCEPIECE` and `GENIUS_HAS_SGPROCESSING` would be defined simultaneously. Fail at configure time, not at link time.
4. Add a `compile-time feature check` that prints the active feature flags at startup and logs a prominent WARN if tokenization is in stub mode in a network-enabled build.

**Detection:** At startup, `GeniusAPIServer::Initialize` should check `GENIUS_HAS_SENTENCEPIECE` and `GENIUS_HAS_SGPROCESSING` are not both active. If they are, abort with a clear error message. Current behavior is a silent build-time exclusion.

**Phase to address:** Phase 1 (Real Inference) — specifically Task 1.2 (SentencePiece linking). Must be resolved before Phase 4 (Network Connection) is attempted, since network dispatch requires SGProcessing and real inference requires tokenization.

---

## Moderate Pitfalls

---

### Pitfall 8: Reputation Storage Corruption Cascading Into Process Death

**What goes wrong:** `ReputationStorage::Deserialize` at `src/reputation/ReputationStorage.cpp:48-67` calls `std::stod()` and `std::stoull()` on CSV fields without `try/catch`. A single corrupt byte in the RocksDB store (bit flip, disk error, malicious write) causes a `std::invalid_argument` or `std::out_of_range` exception that terminates the process. In a production swarm, corrupting one node's reputation store brings that node down — and it will crash on every restart until the DB is manually repaired.

**Why it happens:** The CSV parsing code was written as a quick prototype serialization format (there's a comment "replace with protobuf in production" on line 33). `std::stod` throws on malformed input; the code has no error handling wrapper.

**Consequences:** Node crashes, restarts, crashes again. In an unattended deployment, the node enters a crash loop. If this is the only node with certain reputation data, that data is lost. If multiple nodes share corrupt data (e.g., via CRDT merge of a poisoned record), the corruption propagates.

**Prevention:**
1. Wrap all `std::stod`/`std::stoull` calls in `try/catch` as described in Task 3.2. On parse failure, skip the corrupt record, log an ERROR, and continue.
2. Replace CSV serialization with Protocol Buffers (already in the dependency chain via SGProcessing/libp2p). Protobuf provides schema validation, forward/backward compatibility, and well-defined serialization.
3. Add a checksum or CRC to each reputation record stored on disk. Verify before parsing.
4. For RocksDB: enable checksum verification on reads (`rocksdb::ReadOptions::verify_checksums = true`).

**Detection:** Monitor for crash-restart loops (process uptime < 10 seconds repeatedly). Check logs for `std::invalid_argument` or `std::out_of_range` in reputation-related code paths. Run a periodic DB integrity check that scans all records without crashing.

**Phase to address:** Phase 3 (Persistence) — Task 3.2. Priority: Medium, becomes High in any multi-node deployment.

---

### Pitfall 9: Hardcoded Vocab Size Breaking Non-Mistral Models

**What goes wrong:** `SentencePieceTokenizer::VocabSize()` returns `32000` (Mistral 7B) and `MNNInferenceEngine::RunForward` allocates logit vectors of exactly `32000`. Any model with a different vocabulary (Llama 3: 128K, Gemma: 256K, Phi-3: 32K) produces either buffer overflows (if >32000) or incorrect probability distributions (if <32000, reading uninitialized logits beyond actual vocab).

**Why it happens:** The hardcoded `32000` was the vocab size of the first model integrated (Mistral 7B). It was left as a literal because `VocabSize()` was initially a stub. Even after real tokenization is enabled, the engine code still has `32000` literals.

**Consequences:** Buffer overflows = undefined behavior = potential crashes or silent memory corruption. Wrong probability distributions = garbled or nonsensical text output that might look plausible at first glance. A model switch that "works" (no crash) but produces subtly wrong output is worse than a crash — the operator trusts the output.

**Prevention:**
1. Replace all literal `32000` with `tokenizer_->VocabSize()` or a runtime-configurable value.
2. Add a `static_assert` or runtime check that `vocabSize > 0` before allocating logit buffers.
3. After model loading, compare the loaded model's embedding table size against `VocabSize()` and emit a WARN if they mismatch.
4. In the stub path (GENIUS_HAS_SENTENCEPIECE not defined), return `0` from `VocabSize()` — not `32000` — so callers fail explicitly rather than with wrong values.

**Detection:** After loading any non-Mistral model, check if the logit vector size matches the actual vocab size. A log file entry like `"vocab_size mismatch: expected 32000, model has 128256"` is the canary.

**Phase to address:** Phase 5 (Hardcoded Values) — Task 5.1. Should be done before supporting multiple model types in production.

---

### Pitfall 10: Monolithic Init Swallowing Component Failures

**What goes wrong:** `GeniusAPIServer::Initialize` at `src/api/GeniusAPIServer.cpp:45-153` creates 10+ subsystem objects sequentially. If any single step fails silently (e.g., key generation, storage open, model load), the server continues in a partially broken state with only `Logging::warn` output. There is no early-abort, no health check aggregation, and no `IsHealthy()` method that callers can query.

**Why it happens:** The initialize method uses outcome::result for some steps but only logs warnings on failures — it doesn't short-circuit. This is a prototype pattern: "try everything, see what works." In production, a node with a failed security module that's accepting unverified messages is actively dangerous.

**Consequences:** A production node could start with: (a) no real signing capability (falling through to stub), (b) no tokenization (using hash-based stub), (c) no persistence (in-memory only), and (d) no network connectivity — all while reporting "initialization complete" and accepting connections. The operator sees a running process and assumes everything is working.

**Prevention:**
1. Define required vs. optional subsystems. Security, tokenization, and model loading are **required** for production; knowledge retrieval, math specialist, grammar specialist are **optional**.
2. Required subsystem init failures must cause `Initialize()` to return an error immediately.
3. Optional subsystem init failures must log at ERROR level, not WARN.
4. Add an `IsHealthy()` method that returns a bitmask of subsystem health — callable by monitoring systems and the Flutter UI.
5. Add an `--require-production` CLI flag that enables strict init mode with mandatory checks for secp256k1, tokenization, RocksDB, and network connectivity.

**Detection:** After `Initialize()`, call `IsHealthy()` and check the bitmask. Required subsystems must be healthy. Log the health report at INFO level on startup.

**Phase to address:** Phase 5 (Hardcoded Values) and general production hardening. Not a specific task in the current roadmap but should be a gate in the "Definition of Production Ready" checklist.

---

### Pitfall 11: FFI Layer With Zero Bounds Checking

**What goes wrong:** `GeniusSlmChatCompletionsCreate` at `src/genius_slm_chat_c.cpp:209-241` accepts a C string from Flutter/Dart and passes it through the manual JSON parser (`ExtractPrompt`). There is no maximum length limit, no JSON schema validation, and no sanitization of prompt content. A 1GB request string from a compromised Flutter app or malicious client will be read entirely before any processing begins.

**Why it happens:** The FFI interface is a thin C wrapper. The Dart FFI bridge typically sends reasonably-sized chat messages, so bounds checking wasn't prioritized. The `DuplicateString` helper only checks for null pointers, not size.

**Consequences:** (a) Memory exhaustion: a large request consumes all available RAM. (b) The manual JSON parser at `src/genius_slm_chat_c.cpp:46-131` does `rfind`, `find`, `substr` operations on the entire string — O(n) where n can be gigabytes. (c) No validation means garbage JSON reaches the inference engine, which may produce arbitrary output or crash.

**Prevention:**
1. Add a `MAX_REQUEST_SIZE` constant (e.g., 64KB). Check input length before any processing and return an error JSON immediately if exceeded.
2. Replace manual JSON parsing with `nlohmann/json` (already in thirdparty per `cmake/CommonBuildParameters.cmake:102-110`). The manual parser at lines 46-131 handles ~80% of valid JSON but fails silently on edge cases.
3. Validate the parsed JSON against a schema: `{"messages": [{"role": "string", "content": "string"}]}` structure. Reject with a clear error code if the structure is wrong.
4. Add a guard against deeply nested JSON (e.g., 1000+ levels) that could cause stack overflow in the parser.

**Detection:** Add a request size histogram in monitoring. Large outliers indicate either bugs in the client or attacks. Any request > 64KB should be an automatic reject + WARN log.

**Phase to address:** Phase 5 (Hardcoded Values) and test expansion Task 6.2 (FFI tests). The JSON parsing replacement is identified in `CONCERNS.md:49-53` as "Manual JSON Parsing in ExtractPrompt."

---

### Pitfall 12: Missing Nonce/Sequence in gRPC Request Path

**What goes wrong:** When `SubmitNetwork()` is implemented (Phase 4, Task 4.1), the gRPC call will serialize a `GNUS_Schema` JSON message and send it to the SuperGenius node. If the request has no **idempotency key or request ID**, a network timeout + retry will result in the same inference job being executed multiple times. The SuperGenius network charges for compute — duplicate jobs waste resources and incur costs.

**Why it happens:** gRPC has built-in retry and hedging support. If the client times out waiting for a response, gRPC can automatically retry the RPC. Without a unique request identifier that the server can use to deduplicate, each retry looks like a new, independent request.

**Consequences:** (a) Wasted compute: same prompt processed N times. (b) Wasted cost: if the GNUS network bills per job, the operator is charged N times. (c) If the result is used for swarm consensus, duplicate results from the same job create ambiguity.

**Prevention:**
1. Generate a UUIDv4 (or SHA-256 of the request content + timestamp + node_id) as the `request_id` in the GNUS_Schema JSON.
2. On the SuperGenius side (outside this project's scope), implement idempotency: if a request with the same `request_id` is received within the dedup window, return the cached result instead of re-executing.
3. Use gRPC deadlines to bound retry behavior. A 30-second deadline with max 3 retries means at most 3 duplicate executions in the worst case.
4. Log every request_id at both client and server for auditability.

**Detection:** Monitor the ratio of unique request_ids to completed jobs. If a single request_id appears multiple times in execution logs, retries are generating duplicates.

**Phase to address:** Phase 4 (GNUS Network Connection) — must be part of Task 4.1 implementation.

---

### Pitfall 13: Reputation Score Poisoning via Sybil Attack Surface

**What goes wrong:** Because `MessageSigning::Verify` always returns `true` (Pitfall #1), the system has no way to distinguish a real node from a Sybil. An attacker can spin up N fake nodes, each with a fresh "identity" and zero reputation, and flood the swarm with garbage inference results. The `WeightedConsensus` mechanism is designed to downweight low-reputation nodes, but if the attacker controls enough nodes (e.g., 51% of participants), they can outvote honest nodes through sheer volume.

**Why it happens:** In the current stub mode, any message is accepted. Even after secp256k1 is enabled, creating a new node identity is free (just generate a keypair). There's no stake, bond, or cost to Sybil attacks. The reputation system is designed to make attacks expensive over time (build reputation slowly), but a flash-mob of new identities can overwhelm the system before reputation scoring has time to react.

**Consequences:** (a) Consensus manipulation: attacker-controlled majority dictates which inference output is selected. (b) Reputation system degradation: the constant flood of low-quality results from Sybils pollutes the reputation data for real nodes. (c) Resource exhaustion: processing 1000x more swarm messages than expected due to Sybil traffic.

**Prevention:**
1. **Proof of Stake:** Require nodes to lock GNUS tokens as collateral. A Sybil with 1000 identities needs 1000x the stake.
2. **Reputation-weighted voting with quorum:** Require at least 3 nodes with `reputation > threshold` to agree before a result is accepted. New nodes (zero reputation) cannot participate in high-stakes consensus.
3. **Rate limiting per IP/peer:** Even if an attacker has many identities, if they all come from the same IP, rate-limit the IP. Crypto identities without network-level correlation are still distinguishable.
4. **Minimum reputation gate:** Nodes with reputation below a floor cannot submit results to the swarm — they must first build reputation in single-node or observer mode.
5. **Scoring discount for new nodes:** New nodes' results are weighted at 1% of a veteran node's weight for the first N tasks.

**Detection:** Monitor the rate of new node appearances. A spike from ~2 new nodes/day to 1000/minute indicates a Sybil attack. Track result quality per node — Sybils typically produce low-quality or random output.

**Phase to address:** After Phase 2 (Security auth) is complete. Sybil protection requires authentication to be working first (Pitfall #1). This is a cross-cutting concern affecting reputation, consensus, and network layers.

---

## Minor Pitfalls

---

### Pitfall 14: Metal Shader Compilation Slow First Inference

**What goes wrong:** First inference after a fresh install takes 30-120 seconds while Metal compiles GPU shaders. The operator sees the process hanging and may kill it, assuming it's crashed.

**Prevention:** During `GeniusSlmInit`, run a minimal warm-up forward pass (1 token) to trigger shader compilation. Log "warming up GPU shaders, this may take 30-60 seconds on first run." Ship a pre-compiled Metal shader cache file (`mnn_cachefile.bin`) when possible.

**Phase to address:** Phase 1 (Real Inference) — operational polish alongside Task 1.1.

---

### Pitfall 15: Model Weight Memory Exhaustion on Low-RAM Devices

**What goes wrong:** Mistral 7B weights are 5.3GB. Loading the full model into RAM plus KV cache pushes total memory beyond 8GB. On 8GB MacBooks or Android devices, this triggers OOM killer.

**Prevention:** Use memory-mapped I/O (`mmap`) for the weight file instead of `std::ifstream::read` into a contiguous buffer. This lets the OS page weights in/out as needed. Enable FP4_ULTRA quantization (Task 1.3) which reduces memory footprint by ~75%.

**Phase to address:** Phase 1 (Real Inference) — Task 1.3 (FP4_ULTRA processor).

---

### Pitfall 16: GeniusSlmInit Re-init Race Condition

**What goes wrong:** `GeniusSlmInit` and `GeniusSlmChatCompletionsCreate` both access `g_server` (a raw global pointer) without synchronization. Concurrent calls from the Flutter UI thread via Dart FFI can race — one thread resets `g_server` while another reads it.

**Prevention:** Replace `g_server` with `std::atomic<GeniusAPIServer*>` or add a `std::mutex` around all access. Document that `GeniusSlmInit` and `GeniusSlmChatCompletionsCreate` must not be called concurrently.

**Phase to address:** Phase 5 (Hardcoded Values) — Task 5.2.

---

### Pitfall 17: 256 Build Configurations, 2 Tested

**What goes wrong:** Eight compile-time feature flags (`GENIUS_HAS_MNN`, `_SECP256K1`, `_ROCKSDB`, `_SENTENCEPIECE`, `_SGPROCESSING`, `_LIBP2P`, `_MNN_LLM`, `_OPENSSL`) create 256 possible build configurations. Only the stub-mode configuration (all flags off) and the "all on" configuration are tested. Any intermediate combination could have broken `#ifdef` interactions.

**Prevention:**
1. Add a CI matrix that tests: (a) all stubs off, (b) security only (SECP256K1 + OPENSSL), (c) persistence only (ROCKSDB), (d) SGProcessing only, (e) all on. Five configurations covers the critical interaction points.
2. Add compile-time assertions that mutually exclusive features (SentencePiece + SGProcessing) cannot be enabled together.
3. When adding a new feature flag, always write a stub fallback that returns an explicit error or logs at WARN level.

**Phase to address:** Build system hardening — should be an ongoing practice across all phases.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Phase 1 (Real Inference) | SentencePiece + SGProcessing link conflict (Pitfall #7) | Resolve protobuf version before enabling both; consider MNN tokenizer as alternative |
| Phase 2 (Security) | Stub security paths survive (Pitfall #1), missing replay protection (Pitfall #3), deterministic nonces (Pitfall #6) | Fail-close stubs, add nonce+timestamp to message format, switch to RFC6979 |
| Phase 3 (Persistence) | Corrupt DB crashing process (Pitfall #8) | try/catch on parse, checksums, periodic integrity scans |
| Phase 4 (Network) | Insecure gRPC (Pitfall #5), duplicate job execution (Pitfall #12), no replay protection on RPCs (Pitfall #3) | Require TLS from first implementation, add request_id for idempotency, add nonce+sequence |
| Phase 5 (Hardcoded Values) | Vocab size mismatch (Pitfall #9), init failure swallowed (Pitfall #10), FFI no bounds (Pitfall #11) | Dynamic vocab size, fail-fast init, 64KB request limit |
| Phase 6 (Test Coverage) | Tests only cover stub paths; real crypto paths untested (Pitfall #1) | Security tests must verify rejection of bad signatures, not just acceptance of good ones |
| Deferred (P2P/swarm) | Unverified inference results (Pitfall #4), Sybil attacks (Pitfall #13) | Plan deterministic verification and proof-of-stake before enabling swarm mode |

---

## Sources

### Verified Against Codebase
- `src/security/MessageSigning.cpp:49-60` — always-true Verify stub [HIGH confidence]
- `src/security/NodeIdentity.cpp:187-200, 279-283` — plaintext key save, always-true stub Verify [HIGH confidence]
- `src/reputation/ReputationStorage.cpp:33-67` — CSV parsing, no error handling [HIGH confidence]
- `src/genius_slm_chat_c.cpp:46-131, 199-206` — manual JSON parser, init race [HIGH confidence]
- `src/core/sgprocessing/SGProcessingBridge.cpp:340-346` — NotImplemented SubmitNetwork [HIGH confidence]
- `src/api/GeniusAPIServer.cpp:45-153, 422-432` — monolithic init, gRPC stub [HIGH confidence]
- `.planning/codebase/CONCERNS.md` — comprehensive audit of known issues [HIGH confidence]
- `AgentDocs/PRODUCTION_ROADMAP.md` — task breakdown with phase mapping [HIGH confidence]

### External Sources
- [libsecp256k1 README](https://github.com/bitcoin-core/secp256k1/blob/master/README.md) — features: constant-time ops, RFC6979, no heap allocation [HIGH confidence]
- [gRPC Auth Guide](https://grpc.io/docs/guides/auth/) — SSL/TLS credential types, mTLS support, insecure channel warnings [HIGH confidence]
- [gRPC Security Audit (Cure53)](https://github.com/grpc/grpc/tree/master/doc/grpc_security_audit.pdf) — DoS via uninitialized pointers, integer overflow in malloc calls, freed memory not nulled [HIGH confidence]
- [libsecp256k1 safegcd implementation doc](https://github.com/bitcoin-core/secp256k1/blob/master/doc/safegcd_implementation.md) — constant-time modular inverse, divstep algorithm [MEDIUM confidence — informative, not directly actionable]
- SEC256k1 ECDSA nonce reuse vulnerability — industry knowledge from PS3 hack, Bitcoin transaction malleability, multiple cryptocurrency thefts [HIGH confidence — well-documented attack vector]

### Gaps in Research
- The specific internal design of the SuperGenius/gRPCForSuperGenius service interface was not examined (it's in the sibling SuperGenius repo). Pitfall #12 (request dedup) depends on whether the SuperGenius service already implements idempotency.
- The GNUS token economics (staking amount, slashing conditions) were not researched. Pitfall #13 (Sybil via PoS) recommendations are generic until token parameters are known.
- MNN LLM API behavior for model warm-up and shader caching is inferred from MNN documentation and common GPU patterns, not from testing the actual MNN version in thirdparty.
