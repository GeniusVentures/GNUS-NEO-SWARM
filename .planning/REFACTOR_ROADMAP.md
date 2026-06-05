# Refactor Roadmap: Match SuperGenius Coding Standards

**Authoritative Sources (in priority order):**

1. **CLAUDE.md → [SuperGenius Naming Convention Overrides](../CLAUDE.md#supergenius-naming-convention-overrides)**
   — Takes precedence over the handbook for modern C++17 practices.
2. **Software Engineering Handbook → [C++ Coding Standards](
   https://docs.gnus.ai/technical-information/software-engineering-handbook/c++-coding-standards/)**
   — Baseline authority. Where CLAUDE.md is silent, the handbook rules apply.

**Key Conflicts Resolved (CLAUDE.md wins):**

| Rule | Handbook (2000-era) | CLAUDE.md (C++17) | Winner |
|------|---------------------|-------------------|--------|
| Error handling | Exceptions + `throw()` specs | `noexcept`, `outcome::result<T>` | CLAUDE.md |
| Null pointer | `NULLPTR` macro | `nullptr` | CLAUDE.md |
| Constructor init | Assignment in body | Member init lists | CLAUDE.md |
| Argument naming | `a` prefix (`String aName`) | camelCase, no prefix | CLAUDE.md |
| Line length | 78 columns | 120 columns | CLAUDE.md |
| Constants | `UPPER_CASE` | `kPascalCase` | CLAUDE.md override |
| Default ctor/dtor | Always define all 3 | Rule of Zero/Five | CLAUDE.md |
| Exception specs | `throw(Exception)` | `noexcept` | CLAUDE.md |

**Lint Gate:** Every phase must pass `scripts/pre-commit-lint.sh` with zero warnings
before merging. The `.clang-tidy` and `.clang-format` configs encode the CLAUDE.md
+ handbook conventions automatically. No more bad check-ins.

**Goal**: Rename EVERYTHING — files, classes, functions, members, macros, libs — to SuperGenius conventions.
**Strategy**: One PR per 2-3 files, max 300 lines changed per PR. Each PR must build + pass tests + pass lint.

---

## Phase 0: Lint Infrastructure (FIRST — gates all other phases)

**Goal**: Automated C++ standards enforcement so bad check-ins are impossible.
**What**: Standard clang-tidy + clang-format with YAML config matching CLAUDE.md + handbook rules.
**Why first**: No more regressions. Every subsequent phase must pass lint before merging.

### 0.1 — `.clang-tidy` config (DONE)
- Maps handbook + CLAUDE.md naming rules to clang-tidy `readability-identifier-naming` checks
- Enforces: `m_` member prefix, `k` constant prefix, PascalCase classes, camelCase variables
- No magic numbers (except 0, 1, -1), all variables initialized, braces on all control statements

### 0.2 — `.clang-format` config (DONE)
- Allman/Ullman brace style per Handbook Standard 10
- 4-space indent, 120-column limit
- Spaces inside parentheses: `if ( condition )`

### 0.3 — Pre-commit hook (DONE)
- Runs clang-tidy + clang-format on staged `.hpp`/`.cpp` files
- **Hard fail if clang-tidy or clang-format not found on PATH** (CLion bundles both)
- **Warns on violations but never blocks the commit** (lax mode — tighten after refactor)
- One-time install: `bash scripts/install-hooks.sh`

**Done when:** `scripts/install-hooks.sh` installs the hook, and a commit with a style violation produces a warning.

---

## Phase 1: Remove Feature-Gate #ifdefs (match SuperGenius)

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

## Phase 2: Naming Conventions (File Renames + Member Renames)

### 2.1 Security Module
| Current | Target |
|---------|--------|
| `src/security/NodeIdentity.hpp` | `src/security/node_identity.hpp` |
| `src/security/NodeIdentity.cpp` | `src/security/node_identity.cpp` |
| `src/security/MessageSigning.hpp` | `src/security/message_signing.hpp` |
| `src/security/MessageSigning.cpp` | `src/security/message_signing.cpp` |

**Member renames**: `pub_key_` → `m_pubKey`, `loaded_` → `m_loaded`, `impl_` → `m_impl`
**Argument renames**: All `snake_case` → `camelCase`
**Accessors**: `PeerId()` → `GetPeerId()`, `PublicKey()` → `GetPublicKey()`, `IsLoaded()` → ok

### 2.2 Core Engine
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

**Member renames**: `cfg_` → `m_cfg`, `loaded_` → `m_loaded`, `model_path_` → `m_modelPath`

### 2.3 API Server
| Current | Target |
|---------|--------|
| `src/api/GeniusAPIServer.hpp` | `src/api/api_server.hpp` |
| `src/api/GeniusAPIServer.cpp` | `src/api/api_server.cpp` |

**Class renames**: `GeniusAPIServer` → `ApiServer`, `GeniusResponse` → `InferenceResponse`
**Member renames**: `cfg_` → `m_cfg`, `running_` → `m_running`, `identity_` → `m_identity`
**Log strings**: `"GeniusAPIServer"` → `"ApiServer"`
**Include guard**: `NEOSWARM_API_GENIUSAPISERVER_HPP_` → `NEOSWARM_API_API_SERVER_HPP`

### 2.4 Network
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

### 2.5 Other Modules
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

### 2.6 Common/Shared
| Current | Target |
|---------|--------|
| `src/common/Types.hpp` | `src/common/types.hpp` |
| `src/common/Error.hpp` | `src/common/error.hpp` |
| `src/common/Error.cpp` | `src/common/error.cpp` |
| `src/common/Logging.hpp` | `src/common/logging.hpp` |

### 2.7 Test Files
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

## Phase 3: Header Guard Fixes

Remove trailing `_` from all include guards:
- `NEOSWARM_CORE_ENGINE_MNNINFERENCEENGINE_HPP_` → `NEOSWARM_CORE_ENGINE_MNNINFERENCEENGINE_HPP`

---

## Phase 4: Library Name Renames (CMake)

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

## Phase 5: Function Size Refactors

Split oversized functions into helpers (max ~100 lines per Handbook Guideline 67):
- `MNNInferenceEngine::Infer()` — 659 lines → split into `InferSgProcessing()`, `InferMnnLlm()`, `InferInterpreter()`
- `SGProcessingBridge::BuildSchemaJson()` — 242 lines → split format helpers
- `NodeIdentity::SaveEncrypted()` / `LoadEncrypted()` — 570 lines → split crypto steps
- `GeniusAPIServer::Initialize()` — 192 lines → split subsystem init
- `GeniusAPIServer::Process()` — split mode dispatch
- `GeniusAPIServer::Serve()` — replace busy-loop with real async server

---

## Phase 6: Remove Platform Ifdefs

Per Handbook Standard 114 — use `Platform.hpp` header, not `#ifdef` in source:
- Replace all `#ifdef __unix__` / `_WIN32` with `Platform.hpp`
- Replace `sleep_for(100ms)` busy-wait in `Serve()` with proper async wait

---

## Execution Order

1. **Phase 0** (Lint Infrastructure) — MUST be first; gates everything
2. Phase 1.6 (Common) — foundation, affects everything
3. Phase 1.1 (Security) — no dependencies on other Phase 1 changes
4. Phase 1.2 (Core Engine) — depends on Phase 1.6
5. Phase 1.3 (API) — depends on Phase 1.6 + Phase 1.2
6. Phase 1.4 (Network) — depends on Phase 1.6 + Phase 1.1
7. Phase 1.5 (Other Modules) — can be parallel after Phase 1.6
8. Phase 2 (Header Guards) — after all Phase 1
9. Phase 3 (Library Names) — after all Phase 1
10. Phase 4 (Function Size) — after Phase 1-3
11. Phase 5 (Platform/Stubs) — after Phase 1-3

**Each PR**: rename 2-3 files + fix internal naming → build → test → lint → commit.
