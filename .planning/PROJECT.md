# GENIUS NEO-SWARM

A C++17 local inference engine and swarm networking node for the GNUS.AI Super Genius blockchain ecosystem. Runs MNN language models, routes prompts through specialists (math, grammar), aggregates results with reputation-weighted consensus, and optionally connects to the SuperGenius network for distributed inference.

## Requirements

### Validated

- CLI entry point with arg parsing (port, max_tokens, temperature, model path) — `src/genius_node.cpp`
- OpenAI v1 chat-completions C FFI — `src/genius_slm_chat_c.cpp`
- Orchestration pipeline: Route → Infer → Specialist → Consensus → Respond — `src/api/GeniusAPIServer.cpp`
- Rule-based prompt router (CoreOnly, CorePlusMath, CorePlusGrammar) — `src/router/`
- Math specialist (GSM8K-tuned 1-3B model with symbolic fallback) — `src/specialists/MathSpecialist.cpp`
- Grammar specialist — `src/specialists/GrammarSpecialist.cpp`
- Weighted consensus aggregation for swarm results — `src/reputation/WeightedConsensus.cpp`
- Reputation scoring and storage (in-memory, optionally RocksDB) — `src/reputation/`
- Node identity key generation and signing (secp256k1 optional) — `src/security/NodeIdentity.cpp`
- P2P networking with libp2p (optional) — `src/network/P2PNode.cpp`
- Knowledge retrieval from Grokipedia CSV with fact validation — `src/knowledge/`
- FP4 weight quantization codec — `src/core/fp4/FP4Codec.hpp`
- SuperGenius SGProcessing bridge (local + network optional) — `src/core/sgprocessing/`
- Protobuf message definitions — `proto/`
- Flutter UI scaffold + Dart FFI bridge plugin — `flutter_app/`, `flutter_slm_bridge/`
- 46 passing GTest tests validating orchestration correctness — `test/`
- CMake+Ninja build system with conditional `GENIUS_HAS_*` compilation — `CMakeLists.txt`

### Active

- [ ] Fix GeniusSlmInit re-initialization race with std::call_once (`src/genius_slm_chat_c.cpp`)
- [ ] Fix ReputationStorage::Deserialize crash on corrupt CSV data (`src/reputation/ReputationStorage.cpp`)
- [ ] Add input validation to CLI ParseArgs (port, max_tokens, temperature ranges) (`src/genius_node.cpp`)
- [ ] Fix Flutter FFI bridge memory leak on exception path (`flutter_slm_bridge/lib/flutter_slm_bridge.dart`)
- [ ] Fix hardcoded absolute dylib path in Flutter bridge (`flutter_slm_bridge/lib/flutter_slm_bridge.dart`)
- [ ] Replace fragile string-search JSON parsing with nlohmann/json in FFI layer (`src/genius_slm_chat_c.cpp`)
- [ ] Fix NodeIdentity::LoadFromFile stale public key in stub mode (`src/security/NodeIdentity.cpp`)
- [ ] Add security tests (key gen, sign/verify, tampered signatures) — `test/security/`
- [ ] Add FFI layer tests (init, null safety, multiple-init, JSON handling) — `test/ffi/`
- [ ] Add knowledge/fact validation tests — `test/knowledge/`
- [ ] Remove std::this_thread::sleep_for from GeniusAPIServer::Serve() (`src/api/GeniusAPIServer.cpp`)

### Out of Scope (this phase)

- Linking MNN, SentencePiece, secp256k1, RocksDB — user-managed thirdparty build
- Real gRPC server implementation — requires Protobuf link + significant new code
- Real gRPC client for SubmitNetwork — requires SuperGenius endpoint
- Real Flutter chat UI wiring — Flutter-level feature work
- YAML config file support — new feature requiring yaml-cpp integration
- Streaming token output — new FFI API surface
- Network/P2P tests — network mode not yet functional

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Fix code-level bugs first, third-party linkage deferred | Bugs are blocking correctness; stub-mode items need user-managed libs | Phase 1: code bugs + validation |
| Add missing test directories (security, FFI, knowledge) | CONCERNS.md identified 4 untested areas as high risk | Included in Phase 1 |
| Keep scope to items achievable without third-party changes | Avoids blocking on MNN/SentencePiece/secp256k1/RocksDB linkage | 7 code fixes + 3 test suites |

---
*Last updated: 2026-05-26 after initialization*
