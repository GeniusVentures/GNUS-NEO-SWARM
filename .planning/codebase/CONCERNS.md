# Codebase Concerns

**Analysis Date:** 2026-05-26

---

## Tech Debt

### Widespread Stub Mode — Core Engine, Tokenizer, Networking

- Issue: The system runs entirely in stub mode. Core inference (`MNNInferenceEngine`), tokenization (`SentencePieceTokenizer`), SGProcessing delegate (`SGProcessingBridge`), P2P networking (`P2PNode`), and reputation persistence (`ReputationStorage`) all fall back to stub/no-op implementations when their respective third-party libraries are not compiled in. The system produces placeholder/random output instead of real inference.
- Files:
  - `src/core/engine/MNNInferenceEngine.cpp` (line 137: `"MNN not compiled in — running in stub mode"`, line 156/195: hardcoded 32000-size random logits)
  - `src/core/tokenizer/SentencePieceTokenizer.cpp` (line 62: whitespace tokenizer stub, line 93: hash-based fake token IDs)
  - `src/core/sgprocessing/SGProcessingBridge.cpp` (line 341: SGProcessingManager stub, line 347: Phase 2 network stub)
  - `src/network/P2PNode.cpp` (line 73: libp2p stub)
  - `src/reputation/ReputationStorage.cpp` (line 107: in-memory fallback)
  - `src/api/GeniusAPIServer.cpp` (line 87: `"Core model load failed — continuing in stub mode"`)
- Impact: The system cannot produce real output. All 46 tests pass against stub behavior, which validates the orchestration but not the core functionality. Real inference requires linking MNN, SentencePiece, secp256k1, and RocksDB — none of which are compiled in by default.
- Fix approach: Follow the task list in `AgentDocs/PRODUCTION_ROADMAP.md`: Tasks 1.1 (MNN), 1.2 (SentencePiece), 2.1 (secp256k1), 3.1 (RocksDB) must be completed in order. Each task adds the `#define` flag and cmake linkage for the respective third-party library.

### Hardcoded Vocabulary Size = 32000

- Issue: `SentencePieceTokenizer::VocabSize()` returns `32000` as a hardcoded default (Mistral 7B). `MNNInferenceEngine::RunForward()` allocates logit vectors of exactly `32000` in the stub path.
- Files:
  - `src/core/tokenizer/SentencePieceTokenizer.cpp` line 140: `return 32000;  // Mistral 7B default`
  - `src/core/engine/MNNInferenceEngine.cpp` lines 156, 195: `std::vector<float> logits(32000, 0.0f);`
- Impact: Loading any model other than Mistral 7B (e.g., a smaller 8K vocab model or a larger 128K vocab model) will produce logit size mismatches, crashes, or incorrect sampling.
- Fix approach: After Task 1.2 (SentencePiece linked), `VocabSize()` will return the real value from the loaded model. Replace the hardcoded `32000` in `MNNInferenceEngine.cpp` with `tokenizer_->VocabSize()`. Task 5.1 in `AgentDocs/PRODUCTION_ROADMAP.md`.

### GeniusAPIServer::Serve() Is a Busy-Loop Placeholder

- Issue: `GeniusAPIServer::Serve()` is not a real gRPC server. It is a `while(running_) { sleep_for(100ms); }` busy loop. This also violates the project's own coding standard forbidding `std::this_thread::sleep_for`.
- Files:
  - `src/api/GeniusAPIServer.cpp` lines 420–429
- Impact: The `--serve` CLI flag documented in `RUN_AND_DEPLOY.md` as "Phase 5" does nothing useful. Any gRPC client would find no actual gRPC endpoint.
- Fix approach: Implement a real gRPC server using the protobuf definitions in `proto/`. Requires Protobuf to be linked (already conditionally handled in `CMakeLists.txt` line 55). Task 4.2 in the roadmap.

### SubmitNetwork() Returns NotImplemented

- Issue: `SGProcessingBridge::SubmitNetwork()` returns `Error::NotImplemented`. The Phase 2 network dispatch path to SuperGenius gRPC is completely absent.
- Files:
  - `src/core/sgprocessing/SGProcessingBridge.cpp` lines 349–355
- Impact: The "Swarm" execution mode cannot distribute tasks across the GNUS network. All swarm requests fall back to single-node local execution (see `GeniusAPIServer::RunSwarm()` line 375).
- Fix approach: Implement gRPC client call to SuperGenius using the JSON schema produced by `BuildSchemaJson()`. Task 4.1 in the roadmap.

### Flutter App Is the Default Template Scaffold

- Issue: The `flutter_app/` scaffold contains the stock Flutter "counter" demo app. It is not wired to the chat FFI bridge at all. `flutter_slm_bridge/` exposes the template `sum` API in its native implementation files, not the `GeniusSlm` C ABI.
- Files:
  - `flutter_app/lib/main.dart` — stock Flutter counter app
  - `flutter_slm_bridge/` native `.m`/`.cpp` files — still expose template `sum()` function
- Impact: The iOS/macOS Flutter frontend cannot send chat messages to the native engine. The entire mobile UI layer is non-functional.
- Fix approach: Wire `flutter_slm_bridge/` to call `GeniusSlmChatCompletionsCreate` / `GeniusSlmStringFree` via FFI; replace `flutter_app/` with a chat UI that invokes the bridge. Dependencies `ffi` and `flutter_ai_toolkit` are already in `pubspec.yaml`. Task 7.1 in the roadmap.

### Hardcoded Absolute Path in Flutter Bridge

- Issue: `flutter_slm_bridge/lib/flutter_slm_bridge.dart` hardcodes the dylib path on macOS to `/Volumes/Work/Gnus_ai/genius-llm-v1/GNUS-NEO-SWARM/build/OSX/Release/libGenius-MOS-SLM-FFI.dylib`.
- Files:
  - `flutter_slm_bridge/lib/flutter_slm_bridge.dart` lines 17–18
- Impact: The bridge fails to load on any machine other than the original developer's workstation. This makes the Flutter app unable to start on any other macOS machine.
- Fix approach: Use runtime-relative path resolution via `Platform.resolvedExecutable` or embed the dylib via the podspec's `vendored_frameworks` on Apple platforms.

### No Configuration File Support

- Issue: All configuration is CLI arguments or source code defaults. No YAML/JSON config file parsing exists.
- Files:
  - `src/genius_node.cpp` — only CLI argument parsing
  - `src/api/GeniusAPIServer.hpp` — Config struct with hardcoded defaults
- Impact: Operators cannot tune reputation coefficients (`alpha`), knowledge retrieval thresholds (`top_k`), network bootstrap peers, model paths, or other settings without recompilation or passing dozens of CLI flags.
- Fix approach: Add a `--config <path>` CLI flag and parse a YAML file with yaml-cpp (already in thirdparty). Task 5.3 in the roadmap.

---

## Known Bugs

### GeniusSlmInit Re-Initialization Race with std::call_once

- Issue: `GeniusSlmInit` resets `g_server` and calls `InitServerOnce()` directly. But `g_init_flag` (used by `std::call_once` in `GeniusSlmChatCompletionsCreate`) is never reset. The sequence: `GeniusSlmInit` → `GeniusSlmChatCompletionsCreate` → `GeniusSlmInit` (third call) → `GeniusSlmChatCompletionsCreate` — the final chat call will find `g_server == nullptr` because `call_once` is already "done" but `g_server` was reset.
- Files:
  - `src/genius_slm_chat_c.cpp` lines 176, 199–213
- Trigger: Calling `GeniusSlmInit` multiple times followed by chat completions.
- Workaround: Do not call `GeniusSlmInit` more than once per process lifetime.
- Fix approach: Remove `std::call_once` and replace with a simple null-check inside `GeniusSlmChatCompletionsCreate`. Remove `g_init_flag`. See Task 5.2 in the roadmap (includes exact code diff).

### ReputationStorage::Deserialize Crashes on Corrupt Data

- Issue: `ReputationStorage::Deserialize` calls `std::stod()` and `std::stoull()` without surrounding try/catch. A single corrupt CSV row in RocksDB or in-memory store causes an unhandled exception and process termination.
- Files:
  - `src/reputation/ReputationStorage.cpp` lines 59–64
- Trigger: Corrupt reputation database row (bad CSV, non-numeric fields).
- Workaround: Delete the reputation database file (`./reputation.db`).
- Fix approach: Wrap each `std::stod`/`std::stoull` call in a try/catch block and skip/ignore corrupt records. Task 3.2 in the roadmap (includes exact code).

### NodeIdentity::LoadFromFile Does Not Re-derive Public Key in Stub Mode

- Issue: When `GENIUS_HAS_SECP256K1` is not defined, `LoadFromFile` reads the hex private key but never recomputes the public key (the `#ifdef GENIUS_HAS_SECP256K1` guard prevents the `secp256k1_ec_pubkey_create` call). The public key remains whatever was in `pub_key_` before the load.
- Files:
  - `src/security/NodeIdentity.cpp` lines 158–182 (especially lines 173–178)
- Trigger: Loading a key file in a build without secp256k1; the public key is stale.
- Workaround: Only use `Generate()` (not `LoadFromFile`) without secp256k1, or ensure secp256k1 is compiled in.
- Fix approach: This is automatically resolved when Task 2.1 (link secp256k1) is completed, since the `#ifdef` path will be active.

### JSON Parsing in FFI Layer Is Fragile Manual String Search

- Issue: `ExtractPrompt()` in `genius_slm_chat_c.cpp` parses the OpenAI v1 JSON request by searching for substrings like `"role"`, `"user"`, `"content"`. This is not a real JSON parser and breaks on non-standard whitespace, nested objects, or escape sequences.
- Files:
  - `src/genius_slm_chat_c.cpp` lines 47–132
- Impact: Malformed or non-standard JSON requests silently return garbage prompts instead of erroring cleanly. This is acceptable for stub mode but becomes a correctness issue once real clients connect.
- Fix approach: Replace with nlohmann/json (already used elsewhere, e.g., in `SGProcessingBridge.cpp`) once the engine moves past stub mode.

---

## Security Considerations

### MessageSigning::Verify Always Returns true

- Issue: `MessageSigning::Verify` unconditionally returns `true` — any message from any peer is accepted with any signature. The code contains an explicit `TODO(SECURITY)` comment.
- Files:
  - `src/security/MessageSigning.cpp` lines 49–60 (lines 53: `TODO(SECURITY)`, 58–59: stub warn + `return true`)
- Risk: In a multi-node deployment, any malicious node can forge messages from any other peer. Zero authentication. This is a complete bypass of the message authentication layer.
- Current mitigation: Network mode is disabled by default (`GENIUS_ENABLE_NETWORK=OFF`). P2P networking is not compiled in.
- Fix approach: After secp256k1 is linked (Task 2.1), reconstruct a `NodeIdentity` from `pub_key_hex` and call `identity.Verify(payload, signature)`. Task 2.2 in the roadmap. Write a security test confirming that tampered signatures return `false`.

### NodeIdentity Uses Cryptographically Weak Stub Keys

- Issue: Without secp256k1 compiled in, `NodeIdentity::Generate()` produces random bytes (not a valid secp256k1 keypair), `PeerId()` uses XOR hashing (not SHA-256), and `Verify()` returns `true` for all signatures.
- Files:
  - `src/security/NodeIdentity.cpp` lines 113–129 (stub Generate), lines 146–152 (XOR PeerId), lines 278–283 (stub Verify)
- Risk: Node identities are forgeable. Any peer can impersonate any other peer. Signatures are not cryptographically verified.
- Current mitigation: Network mode is disabled. The stub is clearly logged.
- Fix approach: Link libsecp256k1 (Task 2.1). The real code path already exists behind `#ifdef GENIUS_HAS_SECP256K1`.

### Private Key Stored as Plain Hex on Disk

- Issue: `NodeIdentity::SaveToFile` writes the 32-byte private key as a plain hex string to disk with no encryption or file permissions enforcement.
- Files:
  - `src/security/NodeIdentity.cpp` lines 187–200
- Risk: On a shared or cloud machine, any process/user that can read the key file can steal the node's identity and impersonate it on the GNUS network.
- Current mitigation: None.
- Fix approach: Encrypt with AES-256-GCM using a passphrase from env var `GENIUS_NODE_KEY_PASS` or a system keychain. Task 2.3 in the roadmap.

### No Input Validation on CLI Argument Parsing

- Issue: `ParseArgs()` in `genius_node.cpp` calls `std::stoi()` and `std::stof()` (lines 97, 101, 102) without validating input ranges. Port numbers, token counts, and temperatures are not validated.
- Files:
  - `src/genius_node.cpp` lines 97, 101, 102
- Risk: Negative token counts, zero temperature, or out-of-range port numbers produce undefined behavior or crashes downstream.
- Fix approach: Add range validation after parsing: `port` in [1, 65535], `max_tokens` in [1, 65536], `temperature` in [0.01, 5.0].

---

## Performance Bottlenecks

### Serve() Busy-Waits at 10 Hz

- Issue: The `Serve()` loop burns CPU with `sleep_for(100ms)` in a tight loop on the main thread. No I/O multiplexing, no event loop, no gRPC listener — just spinning.
- Files:
  - `src/api/GeniusAPIServer.cpp` lines 425–427
- Impact: In `--serve` mode, one CPU core is pegged at ~100% doing nothing. Real gRPC serving must replace this entirely.
- Fix approach: Replace with a proper gRPC async server on an `io_context`. Will be addressed when the real gRPC server is implemented.

### No Streaming Token Output — UI Blocks During Inference

- Issue: `GeniusSlmChatCompletionsCreate` is a synchronous blocking call that returns the full response at once. The Flutter UI freezes during inference.
- Files:
  - `src/genius_slm_chat_c.cpp` — blocking call
  - `flutter_slm_bridge/lib/flutter_slm_bridge.dart` — main isolate sync call
- Impact: Poor user experience — the chat UI is unresponsive for the entire inference duration (seconds to minutes with real models).
- Fix approach: Add `GeniusSlmChatCompletionsStream` to the C FFI with a token callback, and expose it in Flutter as a `Stream<String>`. Task 7.2 in the roadmap. The `chatCompletionsCreateAsync` helper on a separate isolate mitigates but does not solve this — true streaming is preferable.

---

## Fragile Areas

### SentencePieceTokenizer — Stub Encode/Decode Are Not Invertible

- Issue: In stub mode, `Encode` generates hash-based integer IDs, and `Decode` converts them back to space-separated int strings (`"1234 5678 9012"`). The input text is unrecoverable from the output.
- Files:
  - `src/core/tokenizer/SentencePieceTokenizer.cpp` lines 87–97 (Encode stub), lines 119–126 (Decode stub)
- Why fragile: Any code path that relies on `Encode → Decode` round-trip correctness (e.g., prompt processing, context window management) will silently produce garbage.
- Safe modification: Do not attempt to fix the stub — just link real SentencePiece (Task 1.2).
- Test coverage: The round-trip is not directly tested. Tests only validate stub behavior (encoding produces expected IDs, decoding produces expected int strings).

### RuleBasedRouter — Single Hardcoded Routing Strategy

- Issue: The router is a simple rule-based classifier (`RuleBasedRouter`) that checks for math/grammar keywords. No ML-based routing, no confidence calibration, no multi-armed bandit exploration.
- Files:
  - `src/router/RuleBasedRouter.cpp`, `src/router/PromptAnalyzer.cpp`
- Why fragile: Routing decisions are binary and keyword-dependent. A prompt like "calculate my tax" (no math keyword) routes to CoreOnly; "help me parse a grammar" (contains "grammar") routes to CorePlusGrammar even for non-grammar tasks.
- Safe modification: Add rules or expand keyword lists, but the underlying approach limits accuracy. A future ML-based router should replace `IRouter`.
- Test coverage: `test_router` passes with stub data. Real routing accuracy against diverse prompts is not measured.

### Flutter FFI Bridge — Unsafe Memory Management

- Issue: The Flutter bridge manually allocates/frees native C strings using `malloc.free()`. If `GeniusSlmStringFree` is not called for every `GeniusSlmChatCompletionsCreate` result, memory leaks occur. The `chatCompletionsCreate` method does call `GeniusSlmStringFree` but does not protect against exceptions between `_bindings.GeniusSlmChatCompletionsCreate` and `_bindings.GeniusSlmStringFree`.
- Files:
  - `flutter_slm_bridge/lib/flutter_slm_bridge.dart` lines 73–85
- Why fragile: Any Dart exception thrown between the native call and the free call leaks the returned C string. No try/finally guards the allocation.
- Safe modification: Wrap the call in a try/finally block:
  ```dart
  final ptr = requestJson.toNativeUtf8().cast<Char>();
  try {
    final result = _bindings.GeniusSlmChatCompletionsCreate(ptr);
    // ... extract and return
  } finally {
    malloc.free(ptr);
  }
  ```
  Do NOT call `GeniusSlmStringFree` inside the finally block — it needs its own try/finally.

---

## Scaling Limits

### Reputation Database — In-Memory Only Without RocksDB

- Issue: Without RocksDB linked (`GENIUS_HAS_ROCKSDB` not defined), `ReputationStorage` uses an `std::unordered_map` in memory. All reputation data is lost on process restart.
- Files:
  - `src/reputation/ReputationStorage.cpp` line 78: `std::unordered_map<std::string, std::string> store_;`
- Current capacity: Zero persistence. In-memory only. Suitable for development/testing only.
- Limit: Cannot survive restarts. Cannot handle more data than available RAM.
- Scaling path: Link RocksDB (Task 3.1). The RocksDB code path already exists behind `#ifdef GENIUS_HAS_ROCKSDB`.

### Single-Node Inference Only Without SGProcessingManager

- Issue: Without `GENIUS_HAS_SGPROCESSING` compiled in, `SubmitDirect()` in `SGProcessingBridge` returns empty bytes. The SGProcessingManager pipeline (schema JSON → ProcessingManager::Create → Process) is not available.
- Files:
  - `src/core/sgprocessing/SGProcessingBridge.cpp` lines 341–342
- Current capacity: Single-node MNN inference only (once MNN is linked). No distributed processing pipeline.
- Limit: Cannot leverage the SGProcessingManager for multi-GPU or distributed inference.
- Scaling path: Enable `GENIUS_ENABLE_SGPROCESSING` in CMake and ensure the `SGProcessingManager` submodule is initialized (`git submodule update --init SGProcessingManager`).

---

## Dependencies at Risk

### build/ Submodule at Divergent Commit

- Issue: The `build/` directory is itself a git submodule at commit `f66e97d` (branch `TestNet-Phase-3.58-11-gf66e97d`), which is different from the main submodule commit `4206d9a`. This indicates a potentially unsynchronized build configuration.
- Impact: The `build/OSX/CMakeLists.txt`, `build/CommonBuildParameters.cmake`, and other build configurations may not match the current source tree. Build failures or missing third-party find packages are possible.
- Migration plan: Verify that `build/` submodule is at the correct commit for the current source tree. Run `git submodule update --recursive` to synchronize.

### GTest — Custom Find Logic Brittle

- Issue: `test/CMakeLists.txt` implements custom GTest find logic (lines 3–26) with hardcoded paths to `_THIRDPARTY_BUILD_DIR` and parent-directory-relative fallback (`../thirdparty/GTest/`). This bypasses CMake's standard `find_package(GTest)` and is fragile across build environments.
- Files:
  - `test/CMakeLists.txt` lines 3–26
- Impact: Tests may silently skip if GTest headers/libraries are at unexpected paths, even if GTest is installed on the system.
- Fix approach: After `FindThirdparty` is properly configured, use standard `find_package(GTest REQUIRED)` and remove the custom find logic.

---

## Missing Critical Features

### No gRPC Server or Client Implementation

- Problem: The system has protobuf definitions in `proto/` and conditional protobuf compilation in `CMakeLists.txt` (lines 55–66), but no gRPC server or client code exists. The `--serve` flag runs a busy loop, and the `--network` flag does nothing.
- Files: `proto/` (definitions exist), `src/api/GeniusAPIServer.cpp` (no gRPC), `src/network/` (libp2p stub, no gRPC client)
- Blocks: Multi-node deployment, swarm mode dispatch, server-mode operation, SuperGenius network connection.

### No Real Node Identity

- Problem: Without secp256k1, every node has a cryptographically weak, forgeable identity. PeerId is XOR of random bytes, not SHA-256 of a real public key.
- Files: `src/security/NodeIdentity.cpp` lines 146–152
- Blocks: Multi-node security, reputation accuracy, secure multi-node deployments.

### Streaming Token Output Not Implemented

- Problem: The C FFI has no streaming API. The Flutter UI blocks during inference.
- Files: `src/genius_slm_chat_c.h` (no stream function), `src/genius_slm_chat_c.cpp` (no stream implementation)
- Blocks: Good mobile UX, ChatGPT-like token-by-token display.

---

## Test Coverage Gaps

### No Security Tests

- What's not tested: Key generation, key save/load roundtrip, sign/verify correctness, verify rejection of tampered signatures, `MessageSigning::Verify` correctness.
- Files: `test/security/` — directory does not exist
- Risk: Security-critical code (NodeIdentity, MessageSigning) has zero test coverage. The `Verify`-always-true bug was only caught by code review, not by tests.
- Priority: High (after Task 2.1 and 2.2 are complete). See Task 6.1.

### No FFI Layer Tests

- What's not tested: `GeniusSlmInit` return values, `GeniusSlmChatCompletionsCreate` valid/invalid JSON handling, `GeniusSlmStringFree(nullptr)` resilience, multiple-init behavior.
- Files: `test/ffi/` — directory does not exist
- Risk: The C FFI boundary is the integration point between Flutter and C++. A crash in this layer (e.g., null pointer dereference) kills the entire Flutter app.
- Priority: Medium. See Task 6.2.

### No Knowledge/Fact Validation Tests

- What's not tested: `FactValidation::Validate()` accuracy — whether a claim is correctly validated against a fact. Empty facts list handling. Relevance score ordering.
- Files: `test/knowledge/` — directory does not exist
- Risk: Fact-grounded responses may silently pass incorrect information.
- Priority: Medium. See Task 6.3.

### No Network/P2P Tests

- What's not tested: Two P2PNode instances exchanging tasks, ResultAggregation collecting responses, timeout behavior, BroadcastTask/OnTask handler interaction.
- Files: `test/network/` — directory does not exist
- Risk: Swarm mode correctness is completely untested. Multi-node bugs will only surface in production.
- Priority: Low (network is not yet functional). See Task 6.4.

---

*Concerns audit: 2026-05-26*
