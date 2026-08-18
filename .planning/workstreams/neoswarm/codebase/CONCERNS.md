# Codebase Concerns

**Analysis Date:** 2026-05-27

## Tech Debt

### MessageSigning::Verify — Stub That Always Returns `true`
- Issue: `MessageSigning::Verify` unconditionally returns `true`, accepting any signature from any peer. This is a `TODO(SECURITY)` in the code. No actual signature verification occurs.
- Files: `src/security/MessageSigning.cpp` (lines 49–60)
- Impact: Any node can impersonate any other node. Inter-node message authentication is completely broken. The entire swarm consensus mechanism is vulnerable to Sybil attacks.
- Fix approach: First enable `GENIUS_HAS_SECP256K1` compile definition (the library is already linked and headers available — see `cmake/CommonBuildParameters.cmake` lines 115–135), then implement real verification by reconstructing a `NodeIdentity` from the public key hex and calling `identity.Verify()`. See `AgentDocs/PRODUCTION_ROADMAP.md` Task 2.2 for the exact replacement code.

### NodeIdentity::Verify — Stub Under Non-secp256k1 Path
- Issue: When `GENIUS_HAS_SECP256K1` is not defined, `NodeIdentity::Verify` logs a warning and returns `true` without checking anything.
- Files: `src/security/NodeIdentity.cpp` (lines 277–283)
- Impact: Local identity verification is also broken in stub mode. Same security implications as MessageSigning but scoped to single-node identity checks.
- Fix approach: Same as above — enable secp256k1. The real implementation path already exists in the `#ifdef GENIUS_HAS_SECP256K1` block (lines 254–277).

### Private Key Stored as Plain Hex on Disk
- Issue: `NodeIdentity::SaveToFile` writes the private key as plain hex to disk with no encryption. The key file is human-readable and can be exfiltrated.
- Files: `src/security/NodeIdentity.cpp` (lines 187–200)
- Impact: On shared/cloud machines, the node's identity can be stolen trivially. Could lead to reputation theft in swarm scenarios.
- Fix approach: Encrypt the key using OpenSSL AES-256-GCM before writing. Derive encryption key from an environment variable (`GENIUS_NODE_KEY_PASS`) or OS keychain. See `AgentDocs/PRODUCTION_ROADMAP.md` Task 2.3.

### ReputationStorage::Deserialize — No Parse Error Protection
- Issue: `ReputationStorage::Deserialize` calls `std::stod()` and `std::stoull()` on CSV fields without a `try/catch` block. A single corrupt or maliciously crafted row in the DB crashes the entire process.
- Files: `src/reputation/ReputationStorage.cpp` (lines 48–67)
- Impact: Any corruption in the RocksDB or in-memory reputation store causes an unrecoverable abort. In production, a disk error or bit flip in the DB leads to process termination.
- Fix approach: Wrap `std::stod`/`std::stoull` calls in try/catch blocks. On parse failure, skip the corrupt record and log a warning. See `AgentDocs/PRODUCTION_ROADMAP.md` Task 3.2.

### Hardcoded Vocab Size 32000
- Issue: `SentencePieceTokenizer::VocabSize()` returns `32000` (Mistral 7B assumption) when SentencePiece is not compiled in or not loaded. `MNNInferenceEngine::RunForward` also allocates logit vectors of size `32000` in stub/fallback paths.
- Files: `src/core/tokenizer/SentencePieceTokenizer.cpp` (line 140), `src/core/engine/MNNInferenceEngine.cpp` (lines 506, 545)
- Impact: Any model with a different vocabulary size produces incorrect logit distributions or allocation mismatches. Hardcoded assumption breaks with non-Mistral models.
- Fix approach: Return `0` for unknown vocab size; use `tokenizer_->VocabSize()` dynamically in `RunForward` instead of the literal `32000`. See `AgentDocs/PRODUCTION_ROADMAP.md` Task 5.1.

### P2P Network — libp2p Integration Is Almost Entirely Stubbed
- Issue: `P2PNode` includes libp2p headers and has skeleton logic under `#ifdef GENIUS_HAS_LIBP2P`, but the actual libp2p initialization code (BasicHost, GossipSub, mDNS) is commented out. `BroadcastTask` and `BroadcastCRDT` call the local handler directly in stub mode — real gossip protocol is not implemented.
- Files: `src/network/P2PNode.cpp` (lines 63–74, 138–147, 161–168)
- Impact: Swarm mode cannot function with real multi-node deployments. All "swarm" operations are effectively local-only, falling through to `RunSingleNode` in `GeniusAPIServer::RunSwarm` (line 377–378 in `src/api/GeniusAPIServer.cpp`).
- Fix approach: Implement the full libp2p initialization: BasicHost with Noise handshake and Yamux muxer, GossipSub topic subscription, mDNS peer discovery. The skeleton comments in the code describe the intended architecture.

### Knowledge Retrieval — Bag-of-Words TF-IDF Stub
- Issue: `KnowledgeRetrieval::Embed` uses a simple bag-of-words with `std::hash` bucketing into 128-dimensional vectors. This is not a real semantic embedding — it hashes words to random dimensions without any learned similarity.
- Files: `src/knowledge/KnowledgeRetrieval.cpp` (lines 113–142)
- Impact: Knowledge retrieval returns factually unrelated facts for many queries. The grounding/fact-checking pipeline is unreliable because retrieval quality is poor.
- Fix approach: Replace with a real embedding model (Sentence-BERT, MiniLM, or similar) or integrate with an external vector DB. The current code comment calls this a "TF-IDF stub" — it was always intended as a placeholder.

### Manual JSON Parsing in ExtractPrompt
- Issue: `ExtractPrompt` in the FFI layer uses manual string searching (`find`, `rfind`, `compare`) to parse OpenAI v1 JSON request bodies. This is fragile, doesn't handle whitespace variations, and silently falls back to returning the raw JSON as the prompt if parsing fails.
- Files: `src/genius_slm_chat_c.cpp` (lines 46–131)
- Impact: Slightly malformed but valid JSON (e.g., with extra whitespace or different field ordering) can silently produce incorrect prompts. The raw JSON fallback feeds garbage text to the inference engine.
- Fix approach: Use `nlohmann/json` (already available as a thirdparty dependency — see `cmake/CommonBuildParameters.cmake` lines 102–110) for proper JSON parsing. This would add robustness and eliminate the manual escape-handling code.

### Reputation Storage — "Replace with Protobuf in Production"
- Issue: `ReputationStorage::Serialize` uses simple CSV formatting. A comment above it says "replace with protobuf in production". CSV is fragile (commas in identity keys break parsing), not versioned, and has no schema validation.
- Files: `src/reputation/ReputationStorage.cpp` (line 33 comment, lines 34–67)
- Impact: Identity keys containing commas cause deserialization failures. No forward/backward compatibility when fields are added. Data corruption is hard to detect.
- Fix approach: Replace CSV serialization with Protocol Buffers. Protobuf is already in the dependency chain (via libp2p). Define a `.proto` schema for `NodeReputation` records.

### GeniusAPIServer::Serve — gRPC Stub Loop
- Issue: `Serve()` runs an infinite loop calling `std::this_thread::sleep_for(100ms)` — a pure stub. There is no actual gRPC server or HTTP listener. The `--serve` CLI flag effectively blocks the process doing nothing useful.
- Files: `src/api/GeniusAPIServer.cpp` (lines 422–432)
- Impact: The system cannot accept external API requests in server mode. `--serve` is non-functional.
- Fix approach: Implement a proper gRPC or HTTP server that accepts inference tasks. The `GeniusAPIServer::Config` already has `grpc_port_` configured.

### SubmitNetwork — Phase 2 Not Implemented
- Issue: `SGProcessingBridge::SubmitNetwork` always returns `Error::NotImplemented`. The code path for dispatching jobs to the SuperGenius network via gRPC does not exist.
- Files: `src/core/sgprocessing/SGProcessingBridge.cpp` (lines 340–346)
- Impact: Phase 2 (network dispatch) is completely blocked. Jobs can only be processed locally via `SubmitDirect`. No `--sg-endpoint` CLI flag exists to configure the SuperGenius node address.
- Fix approach: Implement gRPC client code using `gRPCForSuperGenius` (already in SuperGenius) to send the JSON schema from `BuildSchemaJson()` to a remote SuperGenius node. See `AgentDocs/PRODUCTION_ROADMAP.md` Task 4.1.

### GeniusSlmInit Re-init Bug (Already Partially Fixed)
- Issue: The `PROJECT_BOARD_ISSUES.md` Issue #7 describes a bug where `std::call_once` flag is never reset after re-initialization. The current code has been modified to use a null check (`if (g_server == nullptr)`) instead of `std::call_once`, but the global `g_init_flag` still exists as dead code from the old implementation.
- Files: `src/genius_slm_chat_c.cpp` (lines 199–206 init, 211–215 lazy init)
- Impact: The remaining `call_once` pattern was replaced with a direct null check, but the re-init still calls `InitServer()` directly after `g_server.reset()`. If `InitServer()` fails silently, the second null check wouldn't catch it immediately. The `g_server` pointer is not thread-safe — concurrent access from `GeniusSlmInit` and `GeniusSlmChatCompletionsCreate` could race.
- Fix approach: Add a mutex around `g_server` access, or document that `GeniusSlmInit` and `GeniusSlmChatCompletionsCreate` must not be called concurrently. Consider making `g_server` a `std::atomic<std::unique_ptr>` or using a proper singleton pattern.

## Known Bugs

### Test Binaries Fail to Link with SGProcessingManager
- Symptoms: Test executables fail with duplicate protobuf symbol errors when SGProcessingManager is linked. The main library builds fine, suggesting the test CMakeLists don't use the same `-ld_classic` workaround.
- Files: `test/CMakeLists.txt` (and subdirectory CMakeLists)
- Trigger: Build with SGProcessingManager linked, run `ninja` in a test-enabled build.
- Workaround: The `-ld_classic` linker flag is applied via `target_link_options(neoswarm_core PUBLIC ...)` (PUBLIC/INTERFACE) on `neoswarm_core` in `src/core/CMakeLists.txt` — it propagates transitively to every `neoswarm_test()`-built test binary via normal CMake target-property propagation, since every test target links `neoswarm_core` (directly or transitively). Status: re-verify empirically per D-12 once relinked against GeniusNetwork's SuperGenius build output (Phase 4, plan 04-01) — not yet confirmed fixed on this checkout.

### SentencePiece/SGProcessing Protobuf Conflict — CORRECTED (2026-08-18)
- Prior claim (as of 2026-05-27): both SentencePiece and SGProcessingManager depend on protobuf, and linking both when their respective legacy compile-time feature flags were simultaneously active caused symbol conflicts.
- Correction: SentencePiece does not exist anywhere in the current source tree as of Phase 4 research (2026-08-18) — no implementation file, no compile flag of any kind (those legacy flags predate the current no-`#ifdef` architecture). There is no active protobuf conflict to resolve.
- The remaining protobuf-consolidation concern is that NEO-SWARM must link a single, consistent SGProcessingManager build — resolved by Phase 4's CMake relink to GeniusNetwork's SuperGenius build output (plan 04-01), which pulls one consistent protobuf version through the whole SGProcessing dependency chain.

## Security Considerations

### No Real Signature Verification
- Risk: Any node in the network can forge messages. The `MessageSigning::Verify` always returns `true`, meaning there is effectively zero inter-node authentication. A malicious node could submit false inference results, corrupt reputation scores, or impersonate any peer.
- Files: `src/security/MessageSigning.cpp` (lines 49–60), `src/security/NodeIdentity.cpp` (lines 277–283)
- Current mitigation: The system currently runs in single-node or "swarm falls back to single node" mode, so the verification path is effectively never exercised in practice. The swarm path is not functional without libp2p anyway.
- Recommendations: Enable `GENIUS_HAS_SECP256K1` immediately (the library is already compiled and linked — only the compile definition is missing from `cmake/CommonBuildParameters.cmake` lines 115–135). Then implement real `MessageSigning::Verify` as described in Task 2.2 of `PRODUCTION_ROADMAP.md`.

### Unencrypted Private Key at Rest
- Risk: Private key file (`node.key`) is stored as plain hex. Anyone with filesystem access can read the key and impersonate the node.
- Files: `src/security/NodeIdentity.cpp` (lines 187–200)
- Current mitigation: None. The key is always written in plain hex.
- Recommendations: Encrypt with AES-256-GCM. Derive key from `GENIUS_NODE_KEY_PASS` environment variable. Use OS keychain on Apple platforms (`ISecureStorage`).

### No gRPC TLS/Authentication
- Risk: When the gRPC server is eventually implemented, there is no mention of TLS or mutual TLS in the configuration or code. SuperGenius network communication would be unencrypted.
- Files: `src/api/GeniusAPIServer.hpp` (Config struct), `src/api/GeniusAPIServer.cpp`
- Current mitigation: The gRPC server is a stub (sleep loop) — no real network communication occurs.
- Recommendations: Add TLS configuration to `GeniusAPIServer::Config` (certificate paths, CA bundle). Use mutual TLS for inter-node communication.

### No Input Sanitization in FFI Layer
- Risk: `GeniusSlmChatCompletionsCreate` accepts arbitrary C strings from Flutter/Dart callers and passes them through a manual JSON parser. No length limits or content validation are applied before inference.
- Files: `src/genius_slm_chat_c.cpp` (lines 209–241)
- Current mitigation: The `DuplicateString` helper uses null pointer checks. The `ExtractPrompt` parser has null checks but no length limits.
- Recommendations: Add a maximum request JSON size limit (e.g., 64KB). Validate that the input is well-formed JSON before parsing.

## Performance Bottlenecks

### Metal Shader Compilation on First Run
- Problem: First LLM inference after a fresh install takes 30–120 seconds while Metal compiles GPU shaders. This is an MNN/Metal limitation, not a code bug, but operators need to know about it.
- Files: `src/core/engine/MNNInferenceEngine.cpp` (LLM load path, lines 162–188)
- Cause: Metal compiles shaders lazily on first use. The MNN LLM engine uses many custom GPU operations that need compilation.
- Improvement path: Pre-warm the MNN cache during `GeniusSlmInit` by running a minimal forward pass. Alternatively, ship a pre-compiled Metal shader cache (`mnn_cachefile.bin`) with the app.

### Large Model Memory Footprint
- Problem: The Mistral-7B model weights file is 5.3GB (`llm.mnn.weight`). Loading the model requires allocating that much RAM plus KV cache and workspace tensors, easily exceeding 8GB.
- Files: `src/core/engine/MNNInferenceEngine.cpp` (model loading)
- Cause: MNN loads the entire weight file into memory. No memory mapping or streaming support exists in the current integration.
- Improvement path: Use memory-mapped file I/O (`mmap`) for the weight file instead of full read. Investigate MNN's partial loading or CPU/GPU memory tiering.

### ResultAggregation Uses std::mutex with Wait
- Problem: `ResultAggregation::Collect` holds `mutex_` with `wait_for` — under high swarm load with many concurrent tasks, all aggregation operations serialize on this single mutex.
- Files: `src/network/ResultAggregation.cpp` (lines 49–66)
- Cause: Single mutex protects both the results vector and the condition variable. Multiple concurrent `Collect` calls block each other.
- Improvement path: Use a per-aggregation-instance design (each task creates its own `ResultAggregation`), which the code already does via `aggregation_->Reset()` in `GeniusAPIServer::RunSwarm` (line 312). The bottleneck only matters if the same instance is reused concurrently.

## Fragile Areas

### MNNInferenceEngine — 633-line Multi-mode File
- Files: `src/core/engine/MNNInferenceEngine.cpp` (633 lines), `src/core/engine/MNNInferenceEngine.hpp` (152 lines)
- Why fragile: The engine supports five distinct code paths (SGProcessing, MNN LLM native, MNN Interpreter, direct MNN fallback, and stub mode), all interleaved with `#ifdef` guards and runtime config checks. Changes to one path can easily break another. The `Infer()` method alone contains 160 lines spanning SGProcessing, LLM, Interpreter, and stub logic.
- Safe modification: Any change to the engine should be tested across all paths. The LLM native path (`mnn_llm_`) and Interpreter path (`session_`) use completely different APIs — don't assume shared types.
- Test coverage: The engine is covered indirectly through integration tests (`test/integration/test_pipeline.cpp`), but only in stub mode. No unit tests exist for the MNN LLM or SGProcessing paths.

### GeniusAPIServer::Initialize — Monolithic Setup Function
- Files: `src/api/GeniusAPIServer.cpp` (lines 45–153)
- Why fragile: `Initialize()` creates 10 subsystem objects (identity, engine, tokenizer, 2 specialists, router, 5 reputation objects, network, knowledge). If any single step fails silently (e.g., key generation, storage open), the server continues in a partially broken state with only log warnings.
- Safe modification: Each subsystem initialization should be in its own method with clear success/failure handling. Consider a builder pattern or dependency injection to make the initialization sequence more transparent.
- Test coverage: Integration tests call `Initialize()` in stub mode (`test/integration/test_pipeline.cpp`), but specialized paths (with real models, network, knowledge files) are not tested.

### ExtractPrompt — Manual JSON Parser
- Files: `src/genius_slm_chat_c.cpp` (lines 46–131)
- Why fragile: The parser uses `rfind`, `find`, and `compare` to manually extract JSON fields. It doesn't handle nested objects, escaped quotes within strings correctly, or Unicode escape sequences. JSON like `{"messages": [{"content": "He said \"hello\"", "role": "user"}]}` could break the quote-matching logic.
- Safe modification: Replace with `nlohmann/json` parsing. The library is already in the dependency chain.
- Test coverage: No direct tests — only exercised through integration pipeline tests.

### Compile-time Conditional Features (historical — pre-2026-06-18 refactor)
- Note: This entry describes the codebase as of 2026-05-27, before the 2026-06-18 REFACTOR_ROADMAP work removed all `#ifdef` feature gates project-wide (see STATE.md decisions log). The flags below — including the SentencePiece-tokenizer flag referenced elsewhere in this file — no longer exist in the current architecture; CMake now links-or-fails-at-configure-time unconditionally (`if(TARGET ...)` pattern) instead of gating via compile-time flags.
- Files (historical): Throughout the codebase — `#ifdef GENIUS_HAS_MNN`, `#ifdef GENIUS_HAS_SECP256K1`, `#ifdef GENIUS_HAS_ROCKSDB`, a SentencePiece-tokenizer flag, `#ifdef GENIUS_HAS_SGPROCESSING`, `#ifdef GENIUS_HAS_LIBP2P`, `#ifdef GENIUS_HAS_MNN_LLM`, `#ifdef GENIUS_HAS_OPENSSL`
- Why fragile: The code supports 8 different feature flags, each with a stub fallback. The combination matrix (2^8 = 256 possible build configurations) is never tested. Many stubs silently return success (e.g., `MessageSigning::Verify`, `NodeIdentity::Verify`, `ReputationStorage::Open`, `SGProcessingBridge::SubmitDirect`), masking the fact that real functionality is missing.
- Safe modification: When adding a new `#ifdef` path, always ensure the stub fallback returns an explicit error or at minimum logs at `warn` level so operators know a feature is missing.
- Test coverage: Only the stub modes are tested in CI. The real implementations (with libraries linked) require manual testing.

## Scaling Limits

### Single Machine Architecture
- Current capacity: The system is designed as a single binary (`neo-swarm`) with optional P2P swarm mode. In practice, only single-node mode works because P2P is stubbed.
- Limit: One process = one inference engine. No horizontal scaling without completing the P2P/libp2p integration and Phase 2 network dispatch.
- Scaling path: Complete libp2p integration (P2PNode actual implementation), then implement SubmitNetwork gRPC to SuperGenius for distributed job dispatch.

### Model Size vs Memory
- Current capacity: Mistral 7B with ~5.3GB weights requires 8GB+ RAM on device.
- Limit: Larger models (Llama 13B, 70B) are infeasible without model sharding or CPU/GPU memory tiering.
- Scaling path: FP4_ULTRA quantization (already has enum value and bridge mapping) could reduce memory footprint. Integrate MNN's model parallel features for multi-GPU setups.

### Vocabulary Size Assumption
- Current capacity: Hardcoded to 32000 tokens (Mistral 7B).
- Limit: Any model with vocab size > 32000 (e.g., Llama 3 with 128K vocab) results in buffer overflows or truncated logits in the Interpreter path.
- Scaling path: Make vocab size dynamic via `tokenizer_->VocabSize()` and remove all hardcoded references.

## Dependencies at Risk

### MNN Version Coupling
- Risk: `MNNInferenceEngine` uses `MNN::Transformer::Llm` (LLM-specific API) and `MNN::Interpreter` (generic API). These are tightly coupled to the MNN version in thirdparty. If MNN's LLM API changes (class renamed, method signatures modified), the engine breaks at compile time.
- Impact: MNN upgrades require careful testing of both engine paths. The LLM engine sources from `thirdparty/MNN/transformers/llm/engine/src/*.cpp` are compiled directly into `genius_core`, not as a separate library.
- Migration plan: Pin MNN to a known-good version. Abstract the LLM interface behind `IInferenceEngine` so the engine implementation can be swapped without affecting the rest of the system. (Note: `InferenceEngine.hpp` exists at `src/core/engine/InferenceEngine.hpp` but appears to be a typedef/alias, not a full abstraction.)

### SentencePiece / Protobuf Conflict — CORRECTED (2026-08-18)
- Prior claim (as of 2026-05-27): SentencePiece and SGProcessingManager both link protobuf, and enabling both of their (now-removed) legacy compile-time feature flags simultaneously caused duplicate protobuf symbols.
- Correction: SentencePiece does not exist anywhere in the current source tree — no implementation file, no compile flag. There is no active conflict, and nothing to migrate. The system already uses MNN's built-in `tokenizer.mtok` in the LLM path. The only remaining protobuf-consolidation concern is linking a single, consistent SGProcessingManager build (resolved by Phase 4's CMake relink to GeniusNetwork's SuperGenius build output, plan 04-01).

### Boost Version
- Risk: The project pins Boost 1.85.0 (see `cmake/CommonBuildParameters.cmake` line 19). CMake 4.x has removed `FindBoost` and requires CONFIG mode, which the build already uses (line 84), but this is a known friction point.
- Impact: Upgrading Boost requires updating the build CMake to match new CONFIG paths.
- Migration plan: Document the Boost dependency version explicitly. Test with CMake 4.x in CI.

## Missing Critical Features

### No LLM Text Generation Processor in SGProcessingManager
- Problem: SGProcessingManager is linked and functional, but there is no processor registered for autoregressive LLM text generation. The system can do single-pass tensor inference via MNN but not the iterative token generation LLMs require.
- Blocks: Real text output through the SGProcessing pipeline. The MNN native LLM path (`mnn_llm_`) bypasses SGProcessing entirely and uses `MNN::Transformer::Llm` directly.
- See: `AgentDocs/PROJECT_BOARD_ISSUES.md` Issue #1 (Critical priority)

### No FP4_ULTRA Processor
- Problem: `InputFormat::FP4_ULTRA` exists in the enum and `SGProcessingBridge` already maps it, but no processor implementation exists in SGProcessingManager.
- Blocks: Using FP4_ULTRA quantized models (which would reduce memory footprint by ~75% vs float32).
- See: `AgentDocs/PROJECT_BOARD_ISSUES.md` Issue #2 (High priority)

### No Config File Support
- Problem: All configuration is through CLI arguments or hardcoded defaults. Operators cannot tune reputation coefficients, knowledge retrieval thresholds, or network settings without modifying source code.
- Blocks: Production deployment flexibility. Every parameter change requires a recompile.
- See: `AgentDocs/PRODUCTION_ROADMAP.md` Task 5.3 (Low priority)

### No Streaming Token Output in Flutter
- Problem: The native `StreamInfer` method exists in `MNNInferenceEngine` but the FFI layer (`genius_slm_chat_c.h`/`.cpp`) only exposes `GeniusSlmChatCompletionsCreate` (batch) — no streaming C API for Flutter to consume.
- Blocks: Real-time token streaming UX in the Flutter chat app.
- See: `AgentDocs/PRODUCTION_ROADMAP.md` Task 7.2 (Low priority)

## Test Coverage Gaps

### Security Module — Untested
- What's not tested: `NodeIdentity` key generation, save/load roundtrip, signing, verification. `MessageSigning` sign/verify/strip operations.
- Files: `src/security/NodeIdentity.cpp`, `src/security/MessageSigning.cpp`
- Risk: The entire security subsystem has zero test coverage. The stubs always return `true`, making bugs invisible. When real secp256k1 implementation is enabled, there are no tests to validate correctness.
- Priority: High — after `GENIUS_HAS_SECP256K1` is enabled (see `AgentDocs/PRODUCTION_ROADMAP.md` Task 6.1)

### FFI Layer — Untested
- What's not tested: `GeniusSlmInit`, `GeniusSlmChatCompletionsCreate`, `GeniusSlmStringFree`, `GeniusSlmGetStatus`. Null handling, re-init behavior, concurrent access.
- Files: `src/genius_slm_chat_c.cpp`, `src/genius_slm_chat_c.h`
- Risk: The Flutter app depends on this FFI layer. Any regression silently breaks the chat UI. The re-initialization bug (PROJECT_BOARD_ISSUES.md Issue #7) was only caught by manual testing.
- Priority: Medium (see `AgentDocs/PRODUCTION_ROADMAP.md` Task 6.2)

### Knowledge Module — Untested
- What's not tested: `FactValidation::Validate`, `FactValidation::Contradicts`, `KnowledgeRetrieval::Retrieve`, `KnowledgeRetrieval::Load`, `ContextInjection::Inject`.
- Files: `src/knowledge/FactValidation.cpp`, `src/knowledge/KnowledgeRetrieval.cpp`, `src/knowledge/ContextInjection.cpp`
- Risk: Fact validation and knowledge retrieval are critical for output grounding. No tests mean we don't know if validation actually catches contradictions or if retrieval returns relevant facts.
- Priority: Medium (see `AgentDocs/PRODUCTION_ROADMAP.md` Task 6.3)

### Network Module — Untested
- What's not tested: `P2PNode::BroadcastTask`, `P2PNode::BroadcastCRDT`, `ResultAggregation::Collect`, `ResultAggregation::Submit` with timeout, multi-node task exchange.
- Files: `src/network/P2PNode.cpp`, `src/network/ResultAggregation.cpp`
- Risk: When libp2p integration is completed, there are no tests for the P2P behavior. The stub implementations mask all real networking bugs.
- Priority: Low (after Phase 2 network) — see `AgentDocs/PRODUCTION_ROADMAP.md` Task 6.4

### Tokenizer — No Unit Tests
- What's not tested: `SentencePieceTokenizer::Encode`, `Decode`, `VocabSize` under both real SentencePiece and stub modes. EOS/BOS token handling.
- Files: `src/core/tokenizer/SentencePieceTokenizer.cpp`
- Risk: The stub mode generates random IDs from `std::hash` — this is not deterministic. Tests would catch regressions when real SentencePiece is enabled.
- Priority: Low

### Specialists — No Tests
- What's not tested: `MathSpecialist`, `GrammarSpecialist`, `SymbolicFallback` evaluation. The SymbolicFallback parser handles division by zero and unknown functions, but these error paths are untested.
- Files: `src/specialists/MathSpecialist.cpp`, `src/specialists/GrammarSpecialist.cpp`, `src/specialists/SymbolicFallback.cpp`
- Risk: Mathematical expression evaluation errors could produce incorrect results without detection.
- Priority: Low

### Existing Test Coverage Map
| Module | Test File | Coverage |
|--------|-----------|----------|
| FP4Codec | `test/core/test_fp4_codec.cpp` | ✅ Good (6 tests: roundtrip, dimensions, zero, invalid, macroblock) |
| ReputationScoring | `test/reputation/test_reputation.cpp` | ✅ Good (5 tests: accuracy, latency, consistency, clamping, task count) |
| WeightedConsensus | `test/reputation/test_reputation.cpp` | ✅ Good (4 tests: selection, single, empty, weighted strategy) |
| ReputationCRDT | `test/reputation/test_reputation.cpp` | ✅ Good (4 tests: merge, LWW latest, LWW ignores older, serialize) |
| ReputationStorage | `test/reputation/test_reputation.cpp` | ✅ Good (3 tests: put/get, not found, get all) |
| PromptAnalyzer | `test/router/test_router.cpp` | ✅ Good (5 tests: numeric density, math keywords, grammar, code) |
| RuleBasedRouter | `test/router/test_router.cpp` | ✅ Good (5 tests: math route, keyword route, grammar, core, confidence) |
| GeniusAPIServer Pipeline | `test/integration/test_pipeline.cpp` | ✅ Partial (7 tests: all modes, stub only) |
| SGProcessingBridge + TensorInterpreter | `test/integration/test_sgprocessing_pipeline.cpp` | ✅ Partial (13 tests, SGProcessing conditional) |
| Security | — | ❌ None |
| FFI | — | ❌ None |
| Knowledge | — | ❌ None |
| Network | — | ❌ None |
| Specialists | — | ❌ None |
| Tokenizer | — | ❌ None |

---

*Concerns audit: 2026-05-27*
