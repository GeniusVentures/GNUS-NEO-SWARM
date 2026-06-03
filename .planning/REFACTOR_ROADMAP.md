# Refactor Roadmap: Match SuperGenius Coding Standards

**Goal**: Rename EVERYTHING — files, classes, functions, members, macros, libs — to SuperGenius conventions.
**Strategy**: One PR per 2-3 files, max 300 lines changed per PR. Each PR must build + pass tests.

---

## Phase 0: Remove Feature-Gate #ifdefs (match SuperGenius)

**Goal**: Delete all `#ifdef GENIUS_HAS_*` / `#ifndef GENIUS_HAS_*` from source files.
**Rule**: If the library exists in thirdparty (it does), link it. If missing, CMake fails with a clear error. No runtime stubs.

**Remove from all source files**:
- `#ifdef GENIUS_HAS_SECP256K1` / `#ifndef GENIUS_HAS_SECP256K1` → just use secp256k1 code directly
- `#ifdef GENIUS_HAS_OPENSSL` → just use OpenSSL code directly
- `#ifdef GENIUS_HAS_MNN` → just use MNN code directly
- `#ifdef GENIUS_HAS_SGPROCESSING` → just use SGProcessing code directly
- `#ifdef GENIUS_HAS_ROCKSDB` → just use RocksDB code directly
- `#ifdef GENIUS_HAS_LIBP2P` → just use libp2p code directly
- `#ifdef GENIUS_HAS_SENTENCEPIECE` → just use SentencePiece code directly
- `GENIUS_SLM_CHAT_C_EXPORTS` → `NEOSWARM_CHAT_C_EXPORTS`

**CMake**: Remove `target_compile_definitions` for these macros. If `TARGET` check fails, add `message(FATAL_ERROR "...")`.

---

## Phase 1: Naming Conventions (File Renames + Member Renames)

### 1.1 Security Module
| Current | Target |
|---------|--------|
| `src/security/NodeIdentity.hpp` | `src/security/node_identity.hpp` |
| `src/security/NodeIdentity.cpp` | `src/security/node_identity.cpp` |
| `src/security/MessageSigning.hpp` | `src/security/message_signing.hpp` |
| `src/security/MessageSigning.cpp` | `src/security/message_signing.cpp` |

**Member renames**: `pub_key_` → `m_PubKey`, `loaded_` → `m_Loaded`, `impl_` → `m_Impl`
**Argument renames**: All `snake_case` → `camelCase`
**Accessors**: `PeerId()` → `GetPeerId()`, `PublicKey()` → `GetPublicKey()`, `IsLoaded()` → ok

### 1.2 Core Engine
| Current | Target |
|---------|--------|
| `src/core/engine/MNNInferenceEngine.hpp` | `src/core/engine/mnn_inference_engine.hpp` |
| `src/core/engine/MNNInferenceEngine.cpp` | `src/core/engine/mnn_inference_engine.cpp` |
| `src/core/engine/InferenceEngine.hpp` | `src/core/engine/inference_engine.hpp` |
| `src/core/tokenizer/Tokenizer.hpp` | `src/core/tokenizer/tokenizer.hpp` |
| `src/core/tokenizer/SentencePieceTokenizer.cpp` | `src/core/tokenizer/sentence_piece_tokenizer.cpp` |
| `src/core/fp4/FP4Codec.hpp` | `src/core/fp4/fp4_codec.hpp` |
| `src/core/fp4/FP4Codec.cpp` | `src/core/fp4/fp4_codec.cpp` |
| `src/core/sgprocessing/SGProcessingBridge.hpp` | `src/core/sgprocessing/sg_processing_bridge.hpp` |
| `src/core/sgprocessing/SGProcessingBridge.cpp` | `src/core/sgprocessing/sg_processing_bridge.cpp` |
| `src/core/sgprocessing/TensorInterpreter.hpp` | `src/core/sgprocessing/tensor_interpreter.hpp` |
| `src/core/sgprocessing/TensorInterpreter.cpp` | `src/core/sgprocessing/tensor_interpreter.cpp` |

**Member renames**: `cfg_` → `m_Cfg`, `loaded_` → `m_Loaded`, `model_path_` → `m_ModelPath`

### 1.3 API Server
| Current | Target |
|---------|--------|
| `src/api/GeniusAPIServer.hpp` | `src/api/api_server.hpp` |
| `src/api/GeniusAPIServer.cpp` | `src/api/api_server.cpp` |

**Class renames**: `GeniusAPIServer` → `ApiServer`, `GeniusResponse` → `InferenceResponse`
**Member renames**: `cfg_` → `m_Cfg`, `running_` → `m_Running`, `identity_` → `m_Identity`
**Log strings**: `"GeniusAPIServer"` → `"ApiServer"`
**Include guard**: `NEOSWARM_API_GENIUSAPISERVER_HPP_` → `NEOSWARM_API_API_SERVER_HPP`

### 1.4 Network
| Current | Target |
|---------|--------|
| `src/network/P2PNode.hpp` | `src/network/p2p_node.hpp` |
| `src/network/P2PNode.cpp` | `src/network/p2p_node.cpp` |
| `src/network/ResultAggregation.hpp` | `src/network/result_aggregation.hpp` |
| `src/network/ResultAggregation.cpp` | `src/network/result_aggregation.cpp` |
| `src/network/sg_client/SuperGeniusClient.hpp` | `src/network/sg_client/super_genius_client.hpp` |
| `src/network/sg_client/SuperGeniusClient.cpp` | `src/network/sg_client/super_genius_client.cpp` |
| `src/network/sg_client/SGChannelManager.hpp` | `src/network/sg_client/sg_channel_manager.hpp` |
| `src/network/sg_client/SGChannelManager.cpp` | `src/network/sg_client/sg_channel_manager.cpp` |
| `src/network/sg_client/SGJobSubmitter.hpp` | `src/network/sg_client/sg_job_submitter.hpp` |
| `src/network/sg_client/SGJobSubmitter.cpp` | `src/network/sg_client/sg_job_submitter.cpp` |
| `src/network/sg_client/SGResultCollector.hpp` | `src/network/sg_client/sg_result_collector.hpp` |
| `src/network/sg_client/SGResultCollector.cpp` | `src/network/sg_client/sg_result_collector.cpp` |
| `src/network/sg_client/SGMessageAuthenticator.hpp` | `src/network/sg_client/sg_message_authenticator.hpp` |
| `src/network/sg_client/SGMessageAuthenticator.cpp` | `src/network/sg_client/sg_message_authenticator.cpp` |

### 1.5 Other Modules
| Current                                 | Target                                   |
| -----------------------------------------| ------------------------------------------|
| `src/reputation/NodeReputation.hpp`     | `src/reputation/node_reputation.hpp`     |
| `src/reputation/ReputationStorage.hpp`  | `src/reputation/reputation_storage.hpp`  |
| `src/reputation/ReputationStorage.cpp`  | `src/reputation/reputation_storage.cpp`  |
| `src/reputation/ReputationScoring.hpp`  | `src/reputation/reputation_scoring.hpp`  |
| `src/reputation/ReputationScoring.cpp`  | `src/reputation/reputation_scoring.cpp`  |
| `src/reputation/ReputationCRDT.hpp`     | `src/reputation/reputation_crdt.hpp`     |
| `src/reputation/ReputationCRDT.cpp`     | `src/reputation/reputation_crdt.cpp`     |
| `src/reputation/WeightedConsensus.hpp`  | `src/reputation/weighted_consensus.hpp`  |
| `src/reputation/WeightedConsensus.cpp`  | `src/reputation/weighted_consensus.cpp`  |
| `src/knowledge/KnowledgeRetrieval.hpp`  | `src/knowledge/knowledge_retrieval.hpp`  |
| `src/knowledge/KnowledgeRetrieval.cpp`  | `src/knowledge/knowledge_retrieval.cpp`  |
| `src/knowledge/FactValidation.hpp`      | `src/knowledge/fact_validation.hpp`      |
| `src/knowledge/FactValidation.cpp`      | `src/knowledge/fact_validation.cpp`      |
| `src/knowledge/ContextInjection.hpp`    | `src/knowledge/context_injection.hpp`    |
| `src/knowledge/ContextInjection.cpp`    | `src/knowledge/context_injection.cpp`    |
| `src/router/IRouter.hpp`                | `src/router/i_router.hpp`                |
| `src/router/RuleBasedRouter.hpp`        | `src/router/rule_based_router.hpp`       |
| `src/router/RuleBasedRouter.cpp`        | `src/router/rule_based_router.cpp`       |
| `src/router/PromptAnalyzer.hpp`         | `src/router/prompt_analyzer.hpp`         |
| `src/router/PromptAnalyzer.cpp`         | `src/router/prompt_analyzer.cpp`         |
| `src/specialists/ISpecialist.hpp`       | `src/specialists/i_specialist.hpp`       |
| `src/specialists/MathSpecialist.hpp`    | `src/specialists/math_specialist.hpp`    |
| `src/specialists/MathSpecialist.cpp`    | `src/specialists/math_specialist.cpp`    |
| `src/specialists/GrammarSpecialist.hpp` | `src/specialists/grammar_specialist.hpp` |
| `src/specialists/GrammarSpecialist.cpp` | `src/specialists/grammar_specialist.cpp` |
| `src/specialists/SymbolicFallback.hpp`  | `src/specialists/symbolic_fallback.hpp`  |
| `src/specialists/SymbolicFallback.cpp`  | `src/specialists/symbolic_fallback.cpp`  |
| `src/genius_node.cpp`                   | `src/main.cpp`                           |
| `src/genius_slm_chat_c.h`               | `keep`                                   |
| `src/genius_slm_chat_c.cpp`             | `keep`                                   |

### 1.6 Common/Shared
| Current | Target |
|---------|--------|
| `src/common/Types.hpp` | `src/common/types.hpp` |
| `src/common/Error.hpp` | `src/common/error.hpp` |
| `src/common/Error.cpp` | `src/common/error.cpp` |
| `src/common/Logging.hpp` | `src/common/logging.hpp` |

### 1.7 Test Files
| Current                                           | Target                 |
| ---------------------------------------------------| ------------------------|
| `test/security/test_node_identity.cpp`            | (keep)                 |
| `test/security/test_message_signing.cpp`          | (keep)                 |
| `test/ffi/test_genius_slm_ffi.cpp`                | (keep)                 |
| `test/knowledge/test_fact_validation.cpp`         | (keep)                 |
| `test/network/test_network.cpp`                   | (keep)                 |
| `test/reputation/test_reputation.cpp`             | (keep)                 |
| `test/router/test_router.cpp`                     | (keep)                 |
| `test/core/test_fp4_codec.cpp`                    | (keep)                 |
| `test/integration/test_pipeline.cpp`              | (keep)                 |
| `test/integration/test_sgprocessing_pipeline.cpp` | (keep)                 |
| `test/benchmark/bench_mnn_llm.cpp`                | (keep)                 |
| `test/CMakeLists.txt`                             | (update library names) |

---

## Phase 2: Header Guard Fixes

Remove trailing `_` from all include guards:
- `NEOSWARM_CORE_ENGINE_MNNINFERENCEENGINE_HPP_` → `NEOSWARM_CORE_ENGINE_MNNINFERENCEENGINE_HPP`

---

## Phase 3: Library Name Renames (CMake)

| Current | Target |
|---------|--------|
| `genius_security` | `neoswarm_security` |
| `genius_core` | `neoswarm_core` |
| `genius_network` | `neoswarm_network` |
| `genius_api` | `neoswarm_api` |
| `genius_reputation` | `neoswarm_reputation` |
| `genius_knowledge` | `neoswarm_knowledge` |
| `genius_router` | `neoswarm_router` |
| `genius_specialists` | `neoswarm_specialists` |
| `genius_common` | `neoswarm_common` |

**CMakeLists files to update:**
- `src/CMakeLists.txt`
- `src/api/CMakeLists.txt`
- `src/common/CMakeLists.txt`
- `src/core/CMakeLists.txt`
- `src/knowledge/CMakeLists.txt`
- `src/network/CMakeLists.txt`
- `src/reputation/CMakeLists.txt`
- `src/router/CMakeLists.txt`
- `src/security/CMakeLists.txt`
- `src/specialists/CMakeLists.txt`
- `test/CMakeLists.txt`

---

## Phase 4: Function Size Refactors

Split oversized functions into helpers (max ~100 lines):
- `MNNInferenceEngine::Infer()` — 659 lines → split into `InferSgProcessing()`, `InferMnnLlm()`, `InferInterpreter()`
- `SGProcessingBridge::BuildSchemaJson()` — 242 lines → split format helpers
- `NodeIdentity::SaveEncrypted()` / `LoadEncrypted()` — 570 lines → split crypto steps
- `GeniusAPIServer::Initialize()` — 192 lines → split subsystem init
- `GeniusAPIServer::Process()` — split mode dispatch
- `GeniusAPIServer::Serve()` — replace busy-loop with real async server

---

## Phase 5: Remove Platform Ifdefs

- Replace all `#ifdef __unix__` / `_WIN32` with `Platform.hpp`
- Replace `sleep_for(100ms)` busy-wait in `Serve()` with proper async wait

---

## Execution Order

1. Phase 1.6 (Common) — foundation, affects everything
2. Phase 1.1 (Security) — no dependencies on other Phase 1 changes
3. Phase 1.2 (Core Engine) — depends on Phase 1.6
4. Phase 1.3 (API) — depends on Phase 1.6 + Phase 1.2
5. Phase 1.4 (Network) — depends on Phase 1.6 + Phase 1.1
6. Phase 1.5 (Other Modules) — can be parallel after Phase 1.6
7. Phase 2 (Header Guards) — after all Phase 1
8. Phase 3 (Library Names) — after all Phase 1
9. Phase 4 (Function Size) — after Phase 1-3
10. Phase 5 (Platform/Stubs) — after Phase 1-3

**Each PR**: rename 2-3 files + fix internal naming → build → test → commit.
