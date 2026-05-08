# GNUS-NEO-SWARM — Production Readiness Roadmap
> Last updated: May 2026
> Current state: Prototype — all modules implemented, running in stub mode.
> All 46 tests pass. Zero build errors.

---

## How to read this doc

Each task has:
- **What** — exactly what to do
- **File(s)** — which files to touch
- **Done when** — how you know it's complete
- **Priority** — Critical / High / Medium / Low

Tasks are ordered by dependency — do them top to bottom.

---

## SGProcessing Phases

**Phase 1 — Local (development/testing)**
`Neo Swarm → Input + .mnn → SGProcessingManager → Output → Neo Swarm → Human readable`
Use `SGProcessingManager/dev_proc_data_types`. Reference: `SuperGenius/test/src/processing_datatypes/`

**Phase 2 — Network (production)**
`Neo Swarm → Input + .mnn → SuperGenius → GNUS network → Output → Neo Swarm → Human readable`
SuperGenius is already built at `SuperGenius/build/OSX/Release/`. Phase 2 requires a running SuperGenius node.

The `SGProcessingBridge` (`src/core/sgprocessing/SGProcessingBridge.hpp`) has
two distinct operating modes:

**Phase 1** — `network_mode_ = false` (default)
Calls `ProcessingManager::Create()` + `Process()` locally. No network required.

**Phase 2** — `network_mode_ = true`
Dispatches via `gRPCForSuperGenius` to a SuperGenius node. Requires Phase 1 complete first.

---

## Phase 1 — Real Inference (makes the system produce actual text)

These two tasks are the most important. Nothing else matters until the system
produces real output instead of random tokens.

---

### Task 1.1 — Link MNN and load a real model
**Priority: Critical**

**What:**
MNN is already in the thirdparty build. The `MNNInferenceEngine` has the full
MNN code path written and guarded by `#ifdef GENIUS_HAS_MNN`. You just need to
define that flag and link the library.

**Files:**
- `cmake/CommonBuildParameters.cmake` — add MNN find_package and define flag
- `src/core/engine/MNNInferenceEngine.cpp` — no changes needed, code is ready

**Steps:**
1. Add to `cmake/CommonBuildParameters.cmake`:
```cmake
set(MNN_DIR "${_THIRDPARTY_BUILD_DIR}/MNN/lib/cmake/MNN")
find_package(MNN CONFIG QUIET)
if(MNN_FOUND)
    add_compile_definitions(GENIUS_HAS_MNN)
    message(STATUS "MNN found — real inference enabled")
else()
    message(STATUS "MNN not found — stub mode")
endif()
```
2. Link MNN to `genius_core` in `src/core/CMakeLists.txt`:
```cmake
if(MNN_FOUND)
    target_link_libraries(genius_core PRIVATE MNN::MNN)
endif()
```
3. Get a model file — Mistral 7B `.mnn` or any smaller model converted with
   MNN's `MNNConvert` tool. Place it at a known path.
4. Run: `GeniusSlmInit("/path/to/model.mnn", nullptr)`

**Done when:** `GeniusAPIServer` logs `"Core model loaded"` instead of
`"continuing in stub mode"` and inference returns real text.

---

### Task 1.2 — Link SentencePiece tokenizer
**Priority: Critical**

**What:**
Without SentencePiece, the tokenizer returns space-separated numeric IDs
instead of real tokens. The code is ready behind `#ifdef GENIUS_HAS_SENTENCEPIECE`.

**Files:**
- `cmake/CommonBuildParameters.cmake`
- `src/core/CMakeLists.txt`

**Steps:**
1. Add to `cmake/CommonBuildParameters.cmake`:
```cmake
find_library(SENTENCEPIECE_LIB sentencepiece
    PATHS "${_THIRDPARTY_BUILD_DIR}/sentencepiece/lib" NO_DEFAULT_PATH)
if(SENTENCEPIECE_LIB)
    add_compile_definitions(GENIUS_HAS_SENTENCEPIECE)
    message(STATUS "SentencePiece found")
endif()
```
2. Link in `src/core/CMakeLists.txt`:
```cmake
if(SENTENCEPIECE_LIB)
    target_link_libraries(genius_core PRIVATE ${SENTENCEPIECE_LIB})
    target_include_directories(genius_core PRIVATE
        "${_THIRDPARTY_BUILD_DIR}/sentencepiece/include")
endif()
```
3. The tokenizer model file (`.tokenizer.model`) must sit next to the `.mnn`
   model file — `GeniusAPIServer::Initialize()` already looks for it there.

**Done when:** Tokenizer logs `"SentencePiece loaded"` and decoded output is
real words, not `"1234 5678 9012"`.

---

### Task 1.3 — Add FP4_ULTRA processor to SGProcessingManager
**Priority: High**

`FP4_ULTRA` is already in the `InputFormat` enum and `Generators.hpp` on `dev_proc_data_types`. Missing: a processor class in `SGProcessingManager/src/processors/`.

**Steps:**
1. Add `processing_processor_mnn_fp4ultra.cpp/.hpp` following the pattern of existing processors
2. Register it in `ProcessingManager.cpp` for `DataType::FP4_ULTRA`
3. PR into `SGProcessingManager/dev_proc_data_types`
4. Update `SGProcessingBridge.cpp`: `case InputFormat::FP4_ULTRA: return "fp4_ultra";`

**Done when:** FP4_ULTRA input passes through `ProcessingManager::Create()` + `Process()`.

---

## Phase 2 — Security (required before any multi-node deployment)

---

### Task 2.1 — Link secp256k1 for real node identity
**Priority: High**

**What:**
`NodeIdentity` generates a real secp256k1 keypair and derives a proper PeerId
when `GENIUS_HAS_SECP256K1` is defined. Without it, the peer ID is an XOR hash
of random bytes — not cryptographically secure.

**Files:**
- `cmake/CommonBuildParameters.cmake`
- `src/security/CMakeLists.txt`

**Steps:**
1. Add to cmake:
```cmake
set(libsecp256k1_DIR "${_THIRDPARTY_BUILD_DIR}/libsecp256k1/lib/cmake/libsecp256k1")
find_package(libsecp256k1 CONFIG QUIET)
if(libsecp256k1_FOUND)
    add_compile_definitions(GENIUS_HAS_SECP256K1)
endif()
```
2. Link in `src/security/CMakeLists.txt`:
```cmake
if(libsecp256k1_FOUND)
    target_link_libraries(genius_security PRIVATE libsecp256k1::secp256k1)
endif()
```

**Done when:** `NodeIdentity` logs `"secp256k1 key generated"` and `PeerId()`
returns a proper SHA-256 hash of the public key.

---

### Task 2.2 — Fix MessageSigning::Verify
**Priority: High**

**What:**
`MessageSigning::Verify` currently always returns `true` — any message from
any peer is accepted. This is a `TODO(SECURITY)` in the code.

**File:** `src/security/MessageSigning.cpp`

**Steps:**
After Task 2.1 is done (secp256k1 linked), replace the stub body:
```cpp
// Current stub — REMOVE THIS:
( void )payload;
( void )signature;
( void )pub_key_hex;
SigningLogger()->warn( "MessageSigning::Verify — stub, signature not checked" );
return true;

// Replace with:
auto identity = security::NodeIdentity::FromPublicKeyHex( pub_key_hex );
if ( !identity.has_value() )
{
    return false;
}
return identity.value().Verify( payload, signature );
```

**Done when:** A message with a tampered signature returns `false` from `Verify`.
Write a test in `test/security/` to confirm.

---

### Task 2.3 — Encrypt node key file at rest
**Priority: Medium**

**What:**
`NodeIdentity::SaveToFile` writes the private key as plain hex to disk.
On a shared or cloud machine this is a risk.

**File:** `src/security/NodeIdentity.cpp`

**Steps:**
Use OpenSSL AES-256-GCM to encrypt the key bytes before writing.
Derive the encryption key from a passphrase (env var `GENIUS_NODE_KEY_PASS`
or a system keychain call via `ISecureStorage`).

**Done when:** The key file on disk is not readable as plain hex.

---

## Phase 3 — Persistence (required for reputation and knowledge to survive restarts)

---

### Task 3.1 — Link RocksDB for reputation storage
**Priority: High**

**What:**
`ReputationStorage` falls back to in-memory storage when RocksDB is not
compiled in. Reputation scores are lost on every restart.

**Files:**
- `cmake/CommonBuildParameters.cmake`
- `src/reputation/CMakeLists.txt`

**Steps:**
1. Add to cmake:
```cmake
set(RocksDB_DIR "${_THIRDPARTY_BUILD_DIR}/rocksdb/lib/cmake/rocksdb")
find_package(RocksDB CONFIG QUIET)
if(RocksDB_FOUND)
    add_compile_definitions(GENIUS_HAS_ROCKSDB)
endif()
```
2. Link in `src/reputation/CMakeLists.txt`.

**Done when:** `ReputationStorage` logs `"RocksDB opened"` and scores persist
across process restarts.

---

### Task 3.2 — Fix ReputationStorage deserialize crash
**Priority: Medium**

**What:**
`ReputationStorage::Deserialize` calls `std::stod` and `std::stoull` without
a try/catch. A single corrupt row in the DB crashes the process.

**File:** `src/reputation/ReputationStorage.cpp`

**Steps:**
Wrap the parse calls:
```cpp
try
{
    rep.global_score_ = std::stod( fields[2] );
}
catch ( const std::exception &e )
{
    StorageLogger()->error( "Corrupt reputation record, skipping: {}", e.what() );
    continue;
}
```

**Done when:** A test with a deliberately corrupt DB row is skipped cleanly
without crashing.

---

## Phase 4 — GNUS Network Connection

---

### Task 4.1 — Implement SubmitNetwork() to call SuperGenius via gRPC
**Priority: High**

**What:**
`SGProcessingBridge::SubmitNetwork()` currently returns `Error::NotImplemented`.
The SuperGenius network already runs — GNUS-NEO-SWARM connects to it as a client.
Once Phase 1 works locally, it is a matter of sending the same job through SuperGenius.

**Files:**
- `src/core/sgprocessing/SGProcessingBridge.cpp` — implement `SubmitNetwork()`
- `src/core/sgprocessing/SGProcessingBridge.hpp` — add `endpoint_` to `Config`

**Steps:**
1. Add `endpoint_` to `SGProcessingBridge::Config`: `std::string endpoint_ = "localhost:50051";`
2. Use `gRPCForSuperGenius` (already in `SuperGenius/gRPCForSuperGenius/`) to send the JSON schema from `BuildSchemaJson()` to the SuperGenius node
3. Return the raw output bytes

**Done when:** `SubmitNetwork()` returns real output bytes from a SuperGenius node.

---

### Task 4.2 — Add --sg-endpoint CLI flag
**Priority: Medium**

**File:** `src/genius_node.cpp`

Add `--sg-endpoint <host:port>` to set `SGProcessingBridge::Config::endpoint_`.

**Done when:** `neo-swarm --network --sg-endpoint 192.168.1.10:50051` dispatches to the specified node.

---

## Phase 5 — Hardcoded Values (clean up before release)

---

### Task 5.1 — Remove hardcoded vocab size 32000
**Priority: Medium**

**What:**
`SentencePieceTokenizer::VocabSize()` returns `32000` (Mistral 7B assumption)
and `MNNInferenceEngine` allocates logit vectors of size `32000` in stub mode.
This breaks with any other model.

**Files:**
- `src/core/tokenizer/SentencePieceTokenizer.cpp` line 140
- `src/core/engine/MNNInferenceEngine.cpp` lines 156, 195

**Steps:**
After Task 1.2 (SentencePiece linked), `VocabSize()` returns the real value
from the loaded model. Remove the hardcoded fallback or make it configurable:
```cpp
// Replace:
return 32000;  // Mistral 7B default
// With:
return 0;  // unknown until model is loaded
```
Update `MNNInferenceEngine` stub to use `tokenizer_->VocabSize()` instead of
the literal `32000`.

**Done when:** A non-Mistral model loads without logit size mismatch errors.

---

### Task 5.2 — Fix GeniusSlmInit re-init bug
**Priority: Medium**

**What:**
`GeniusSlmInit` resets `g_server` and calls `InitServerOnce()` directly.
But `g_init_flag` (used by `std::call_once`) is never reset. If
`GeniusSlmChatCompletionsCreate` is called after a second `GeniusSlmInit`,
`call_once` is already "done" and won't re-run — but `g_server` was already
set by `GeniusSlmInit` directly, so it works. However if `GeniusSlmInit` is
called a third time after a chat call, the server is reset but `call_once`
won't fire again. The result is `g_server == nullptr` on the next chat call.

**File:** `src/genius_slm_chat_c.cpp`

**Steps:**
Remove `std::call_once` from `GeniusSlmChatCompletionsCreate` and use a
simple null check instead:
```cpp
char *GeniusSlmChatCompletionsCreate( const char *request_json ) noexcept
{
    // Lazy init on first call if GeniusSlmInit was never called
    if ( g_server == nullptr )
    {
        InitServerOnce();
    }
    // ... rest unchanged
}
```
Remove `g_init_flag` entirely.

**Done when:** Calling `GeniusSlmInit` multiple times followed by chat calls
works correctly every time. Add a test for this sequence.

---

### Task 5.3 — Add config file support (YAML/JSON)
**Priority: Low**

**What:**
All configuration is CLI args or code defaults. No config file means operators
can't tune reputation coefficients, knowledge retrieval thresholds, or network
settings without recompiling.

**File:** `src/genius_node.cpp`, `src/api/GeniusAPIServer.hpp`

**Steps:**
Add a `--config path/to/config.yaml` CLI flag. Parse it with yaml-cpp
(already in thirdparty) and populate `GeniusAPIServer::Config` from it.

**Done when:** A YAML file can set `reputation.alpha`, `knowledge.top_k`,
`network.bootstrap_peer`, etc. without touching code.

---

## Phase 6 — Test Coverage (fill the gaps)

---

### Task 6.1 — Add security tests
**Priority: High** (after Task 2.1 and 2.2)

**File:** `test/security/test_node_identity.cpp` (create)

**What to test:**
- Key generation produces a valid secp256k1 keypair
- `SaveToFile` / `LoadFromFile` roundtrip
- `Sign` + `Verify` with correct key returns true
- `Verify` with wrong key returns false
- `Verify` with tampered payload returns false

---

### Task 6.2 — Add FFI layer tests
**Priority: Medium**

**File:** `test/ffi/test_genius_slm_ffi.cpp` (create)

**What to test:**
- `GeniusSlmInit(nullptr, nullptr)` returns 0 (stub mode)
- `GeniusSlmChatCompletionsCreate` with valid JSON returns valid JSON
- `GeniusSlmChatCompletionsCreate` with null returns error JSON (not crash)
- `GeniusSlmStringFree(nullptr)` does not crash
- Multiple `GeniusSlmInit` calls followed by chat calls work correctly

---

### Task 6.3 — Add fact validation tests
**Priority: Medium**

**File:** `test/knowledge/test_fact_validation.cpp` (create)

**What to test:**
- A claim `"The speed of light is 300000 km/s"` validated against a fact
  `"speed of light: 299792 km/s"` passes (within tolerance)
- A claim `"The speed of light is 100 km/s"` fails validation
- Empty facts list always passes

---

### Task 6.4 — Add network tests
**Priority: Low** (after Task 4.1)

**File:** `test/network/test_p2p_node.cpp` (create)

**What to test:**
- Two `P2PNode` instances in stub mode exchange a task via local handler
- `ResultAggregation` collects responses within timeout
- `ResultAggregation` times out cleanly when no responses arrive

---

## Phase 7 — Flutter (complete the UI)

---

### Task 7.1 — Wire flutter_slm_bridge to real dylib on iOS/macOS
**Priority: High**

**What:**
The Dart bridge loads `Genius-MOS-SLM-FFI.framework/Genius-MOS-SLM-FFI` on
Apple platforms. The framework needs to be built and embedded in the Flutter
app bundle.

**Files:**
- `flutter_slm_bridge/ios/flutter_slm_bridge.podspec`
- `flutter_slm_bridge/macos/flutter_slm_bridge.podspec`

**Steps:**
1. Build the iOS framework: `cmake -DPLATFORM=OS64 ...`
2. Add the `.xcframework` output path to the podspec `vendored_frameworks`.
3. Run `flutter pub get` and `flutter run` on a real device.

**Done when:** The chat UI on a real iPhone sends a message and gets a
response from the native engine.

---

### Task 7.2 — Add streaming token output
**Priority: Low**

**What:**
Long inference blocks the UI until the full response is ready. Streaming
tokens gives a much better UX.

**Files:**
- `src/genius_slm_chat_c.h` — add `GeniusSlmChatCompletionsStream`
- `src/genius_slm_chat_c.cpp` — implement with token callback
- `flutter_slm_bridge/lib/flutter_slm_bridge.dart` — add `Stream<String>`

**Steps:**
Add to the C header:
```c
typedef void (*GeniusSlmTokenCallback)(const char* token, void* userdata);

GENIUS_SLM_CHAT_C_API void GeniusSlmChatCompletionsStream(
    const char*           requestJson,
    GeniusSlmTokenCallback callback,
    void*                 userdata
) GENIUS_SLM_CHAT_C_NOEXCEPT;
```
In Flutter, use a `StreamController<String>` and call `setState` on each token.

**Done when:** The chat UI shows tokens appearing one by one as they are
generated, like ChatGPT.

---

## Summary — Priority Order

| # | Task | Priority | Blocks |
|---|------|----------|--------|
| 1.1 | Link MNN + load model | **Critical** | Real inference |
| 1.2 | Link SentencePiece | **Critical** | Real text output |
| 1.3 | FP4_ULTRA processor in SGProcessingManager | **High** | Neo Swarm data type |
| 2.1 | Link secp256k1 | **High** | Real node identity |
| 2.2 | Fix MessageSigning::Verify | **High** | Message auth |
| 3.1 | Link RocksDB | **High** | Persistent reputation |
| 4.1 | Connect SubmitNetwork() to SuperGenius gRPC | **High** | GNUS network dispatch |
| 4.2 | Add --sg-endpoint CLI flag | **Medium** | Operator config |
| 3.2 | Fix deserialize crash | **Medium** | Stability |
| 5.2 | Fix GeniusSlmInit re-init | **Medium** | FFI correctness |
| 6.1 | Security tests | **High** | After 2.1/2.2 |
| 6.2 | FFI tests | **Medium** | After 5.2 |
| 5.1 | Remove hardcoded 32000 | **Medium** | Multi-model support |
| 7.1 | Wire Flutter on device | **High** | Mobile release |
| 2.3 | Encrypt key file | **Medium** | Security hardening |
| 5.3 | Config file support | **Low** | Ops convenience |
| 6.3 | Fact validation tests | **Medium** | Coverage |
| 6.4 | Network tests | **Low** | After 4.1 |
| 7.2 | Streaming tokens | **Low** | UX polish |

---

## Definition of "Production Ready"

The system is production ready when:

- [ ] `GeniusAPIServer` logs `"Core model loaded"` (not stub mode)
- [ ] Chat responses contain real natural language (not numeric token IDs)
- [ ] FP4_ULTRA handled natively by SGProcessingManager
- [ ] SGProcessingManager on `dev_proc_data_types` ✅ (done)
- [ ] `NodeIdentity` uses a real secp256k1 keypair
- [ ] `MessageSigning::Verify` rejects tampered messages
- [ ] `ReputationStorage` persists to RocksDB across restarts
- [ ] `SubmitNetwork()` dispatches to SuperGenius gRPC
- [ ] All test suites pass including security and FFI tests
- [ ] Flutter app runs on a real device and gets real responses
- [ ] No hardcoded vocab size, no sleep loops, no always-true Verify
