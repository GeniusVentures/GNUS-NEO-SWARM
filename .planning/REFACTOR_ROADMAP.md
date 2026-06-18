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

## Phase 0: Lint Infrastructure ✅ DONE

**Goal**: Automated C++ standards enforcement so bad check-ins are impossible.
**What**: Standard clang-tidy + clang-format with YAML config matching CLAUDE.md + handbook rules.
**Why first**: No more regressions. Every subsequent phase must pass lint before merging.

### 0.1 — `.clang-tidy` config ✅
- Maps handbook + CLAUDE.md naming rules to clang-tidy `readability-identifier-naming` checks
- Enforces: `m_` member prefix, `k` constant prefix, PascalCase classes, camelCase variables
- No magic numbers (except 0, 1, -1), all variables initialized, braces on all control statements

### 0.2 — `.clang-format` config ✅
- Allman/Ullman brace style per Handbook Standard 10
- 4-space indent, 120-column limit
- Spaces inside parentheses: `if ( condition )`

### 0.3 — Pre-commit hook ✅
- Runs clang-tidy + clang-format on staged `.hpp`/`.cpp` files
- **Hard fail if clang-tidy or clang-format not found on PATH** (CLion bundles both)
- **Warns on violations but never blocks the commit** (lax mode — tighten after refactor)
- One-time install: `bash scripts/install-hooks.sh`

---

## Phase 1: Remove Feature-Gate #ifdefs ✅ DONE

**Goal**: Delete all `#ifdef GENIUS_HAS_*` / `#ifndef GENIUS_HAS_*` from source files.
**Rule**: If the library exists in thirdparty (it does), link it. If missing, CMake fails with a clear error. No runtime stubs.

**History:** The bulk shipped via PR #65 (`fix/zero-guards-cleanup`, merged to `develop`).
This branch removed the remaining tail (dead `SECP256K1`/`OPENSSL`/`ROCKSDB` compile defs,
the unused `set(GENIUS_HAS_SGPROCESSING)` var, the final `SGPROCESSING` test gate, and a
stale comment). Zero `GENIUS_HAS_*` references now remain anywhere in `src/` or `test/`.

### 1.1 — #ifdefs from source files ✅
All macros removed (`SECP256K1`, `OPENSSL`, `MNN`, `ROCKSDB`, `LIBP2P`, `SENTENCEPIECE`, `GRPC`, `VULKAN`, `SGPROCESSING`).

### 1.2 — target_compile_definitions from CMakeLists ✅
All removed. Note: `GENIUS_HAS_SGPROCESSING` had been a dead test gate (macro never defined
after PR #65), so the real SGProcessing end-to-end tests were silently uncompiled — now fixed;
`FloatModel_EndToEnd` / `TensorModel_EndToEnd` are live again (self-skip when test data absent).

---

## Phase 2: File Renames (PascalCase → snake_case) ✅ DONE

All files have been renamed. Remaining work is in Phases 2a–2e below.

### 2.1 Security Module ✅
| Current (was) | Target (now) | Done |
|---------------|-------------|------|
| `src/security/NodeIdentity.hpp` | `src/security/node_identity.hpp` | ✅ |
| `src/security/NodeIdentity.cpp` | `src/security/node_identity.cpp` | ✅ |
| `src/security/MessageSigning.hpp` | `src/security/message_signing.hpp` | ✅ |
| `src/security/MessageSigning.cpp` | `src/security/message_signing.cpp` | ✅ |

### 2.2 Core Engine ✅
| Current (was) | Target (now) | Done |
|---------------|-------------|------|
| `src/core/engine/MNNInferenceEngine.hpp` | `src/core/engine/mnn_inference_engine.hpp` | ✅ |
| `src/core/engine/MNNInferenceEngine.cpp` | `src/core/engine/mnn_inference_engine.cpp` | ✅ |
| `src/core/engine/InferenceEngine.hpp` | `src/core/engine/inference_engine.hpp` | ✅ |
| `src/core/tokenizer/Tokenizer.hpp` | `src/core/tokenizer/tokenizer.hpp` | ✅ |
| `src/core/tokenizer/SentencePieceTokenizer.cpp` | `src/core/tokenizer/sentence_piece_tokenizer.cpp` | ✅ |
| `src/core/fp4/FP4Codec.hpp` | `src/core/fp4/fp4_codec.hpp` | ✅ |
| `src/core/fp4/FP4Codec.cpp` | `src/core/fp4/fp4_codec.cpp` | ✅ |
| `src/core/sgprocessing/SGProcessingBridge.hpp` | `src/core/sgprocessing/sg_processing_bridge.hpp` | ✅ |
| `src/core/sgprocessing/SGProcessingBridge.cpp` | `src/core/sgprocessing/sg_processing_bridge.cpp` | ✅ |
| `src/core/sgprocessing/TensorInterpreter.hpp` | `src/core/sgprocessing/tensor_interpreter.hpp` | ✅ |
| `src/core/sgprocessing/TensorInterpreter.cpp` | `src/core/sgprocessing/tensor_interpreter.cpp` | ✅ |

### 2.3 API Server ✅
| Current (was) | Target (now) | Done |
|---------------|-------------|------|
| `src/api/GeniusAPIServer.hpp` | `src/api/api_server.hpp` | ✅ |
| `src/api/GeniusAPIServer.cpp` | `src/api/api_server.cpp` | ✅ |

### 2.4 Network ✅
| Current (was) | Target (now) | Done |
|---------------|-------------|------|
| `src/network/P2PNode.hpp` | `src/network/p2p_node.hpp` | ✅ |
| `src/network/P2PNode.cpp` | `src/network/p2p_node.cpp` | ✅ |
| `src/network/ResultAggregation.hpp` | `src/network/result_aggregation.hpp` | ✅ |
| `src/network/ResultAggregation.cpp` | `src/network/result_aggregation.cpp` | ✅ |
| `src/network/sg_client/SuperGeniusClient.hpp` | `src/network/sg_client/super_genius_client.hpp` | ✅ |
| `src/network/sg_client/SuperGeniusClient.cpp` | `src/network/sg_client/super_genius_client.cpp` | ✅ |
| `src/network/sg_client/SGChannelManager.hpp` | `src/network/sg_client/sg_channel_manager.hpp` | ✅ |
| `src/network/sg_client/SGChannelManager.cpp` | `src/network/sg_client/sg_channel_manager.cpp` | ✅ |
| `src/network/sg_client/SGJobSubmitter.hpp` | `src/network/sg_client/sg_job_submitter.hpp` | ✅ |
| `src/network/sg_client/SGJobSubmitter.cpp` | `src/network/sg_client/sg_job_submitter.cpp` | ✅ |
| `src/network/sg_client/SGResultCollector.hpp` | `src/network/sg_client/sg_result_collector.hpp` | ✅ |
| `src/network/sg_client/SGResultCollector.cpp` | `src/network/sg_client/sg_result_collector.cpp` | ✅ |
| `src/network/sg_client/SGMessageAuthenticator.hpp` | `src/network/sg_client/sg_message_authenticator.hpp` | ✅ |
| `src/network/sg_client/SGMessageAuthenticator.cpp` | `src/network/sg_client/sg_message_authenticator.cpp` | ✅ |

### 2.5 Other Modules ✅
| Current (was) | Target (now) | Done |
|---------------|-------------|------|
| `src/reputation/NodeReputation.hpp` | `src/reputation/node_reputation.hpp` | ✅ |
| `src/reputation/ReputationStorage.hpp` | `src/reputation/reputation_storage.hpp` | ✅ |
| `src/reputation/ReputationStorage.cpp` | `src/reputation/reputation_storage.cpp` | ✅ |
| `src/reputation/ReputationScoring.hpp` | `src/reputation/reputation_scoring.hpp` | ✅ |
| `src/reputation/ReputationScoring.cpp` | `src/reputation/reputation_scoring.cpp` | ✅ |
| `src/reputation/ReputationCRDT.hpp` | `src/reputation/reputation_crdt.hpp` | ✅ |
| `src/reputation/ReputationCRDT.cpp` | `src/reputation/reputation_crdt.cpp` | ✅ |
| `src/reputation/WeightedConsensus.hpp` | `src/reputation/weighted_consensus.hpp` | ✅ |
| `src/reputation/WeightedConsensus.cpp` | `src/reputation/weighted_consensus.cpp` | ✅ |
| `src/knowledge/KnowledgeRetrieval.hpp` | `src/knowledge/knowledge_retrieval.hpp` | ✅ |
| `src/knowledge/KnowledgeRetrieval.cpp` | `src/knowledge/knowledge_retrieval.cpp` | ✅ |
| `src/knowledge/FactValidation.hpp` | `src/knowledge/fact_validation.hpp` | ✅ |
| `src/knowledge/FactValidation.cpp` | `src/knowledge/fact_validation.cpp` | ✅ |
| `src/knowledge/ContextInjection.hpp` | `src/knowledge/context_injection.hpp` | ✅ |
| `src/knowledge/ContextInjection.cpp` | `src/knowledge/context_injection.cpp` | ✅ |
| `src/router/IRouter.hpp` | `src/router/i_router.hpp` | ✅ |
| `src/router/RuleBasedRouter.hpp` | `src/router/rule_based_router.hpp` | ✅ |
| `src/router/RuleBasedRouter.cpp` | `src/router/rule_based_router.cpp` | ✅ |
| `src/router/PromptAnalyzer.hpp` | `src/router/prompt_analyzer.hpp` | ✅ |
| `src/router/PromptAnalyzer.cpp` | `src/router/prompt_analyzer.cpp` | ✅ |
| `src/specialists/ISpecialist.hpp` | `src/specialists/i_specialist.hpp` | ✅ |
| `src/specialists/MathSpecialist.hpp` | `src/specialists/math_specialist.hpp` | ✅ |
| `src/specialists/MathSpecialist.cpp` | `src/specialists/math_specialist.cpp` | ✅ |
| `src/specialists/GrammarSpecialist.hpp` | `src/specialists/grammar_specialist.hpp` | ✅ |
| `src/specialists/GrammarSpecialist.cpp` | `src/specialists/grammar_specialist.cpp` | ✅ |
| `src/specialists/SymbolicFallback.hpp` | `src/specialists/symbolic_fallback.hpp` | ✅ |
| `src/specialists/SymbolicFallback.cpp` | `src/specialists/symbolic_fallback.cpp` | ✅ |
| `src/genius_node.cpp` | `src/main.cpp` | ✅ |

### 2.6 Common/Shared ✅
| Current (was) | Target (now) | Done |
|---------------|-------------|------|
| `src/common/Types.hpp` | `src/common/types.hpp` | ✅ |
| `src/common/Error.hpp` | `src/common/error.hpp` | ✅ |
| `src/common/Error.cpp` | `src/common/error.cpp` | ✅ |
| `src/common/Logging.hpp` | `src/common/logging.hpp` | ✅ |

### 2.7 ELM/FFI Files (not renamed — keep as-is)
These files post-date the original roadmap and use the ELM (Edge Language Model) naming:
| File | Notes |
|------|-------|
| `src/genius_elm_chat_c.cpp` | FFI thin wrapper |
| `src/genius_elm_chat_completions.cpp` | FFI implementation |
| `src/genius_elm_chat_completions.h` | FFI header (C ABI — consumers depend on names) |

**Decision needed**: The `Genius` prefix in FFI function names (`GeniusElmInit`, `GeniusElmChatCompletionsCreate`, etc.) is a C ABI contract. Renaming is a breaking change for the Flutter bridge. Keep for now; address in a separate FFI modernization phase.

### 2.8 Test Files ✅ (mostly keep)
| File | Done |
|------|------|
| `test/security/test_node_identity.cpp` | ✅ |
| `test/security/test_message_signing.cpp` | ✅ |
| `test/ffi/test_genius_slm_ffi.cpp` | ⚠️ **ORPHANED** — exists on disk but not built by CMake; replaced by `test_genius_elm_ffi.cpp` |
| `test/ffi/test_genius_elm_ffi.cpp` | ✅ New file, not in original roadmap |
| `test/knowledge/test_fact_validation.cpp` | ✅ |
| `test/network/test_network.cpp` | ✅ |
| `test/reputation/test_reputation.cpp` | ✅ |
| `test/router/test_router.cpp` | ✅ |
| `test/core/test_fp4_codec.cpp` | ✅ |
| `test/specialists/test_grammar_specialist.cpp` | ✅ New file, not in original roadmap |
| `test/specialists/test_math_specialist.cpp` | ✅ New file, not in original roadmap |
| `test/integration/test_pipeline.cpp` | ✅ |
| `test/integration/test_sgprocessing_pipeline.cpp` | ✅ |
| `test/benchmark/bench_mnn_llm.cpp` | ✅ |
| `test/CMakeLists.txt` | ✅ (library names updated) |

**Action**: Delete orphaned `test/ffi/test_genius_slm_ffi.cpp`. Fix `test/CMakeLists.txt:62` — target `test_genius_slm_ffi` uses source `ffi/test_genius_elm_ffi.cpp` (name mismatch).

---

## Phase 2a: Member Variable Naming ⚠️ IN PROGRESS

Fix all member variables to `m_` prefix + camelCase convention.

### 2a.1 Security Module ⚠️
| Class | Current | Target | Status |
|-------|---------|--------|--------|
| `NodeIdentity` | `pub_key_` | `m_pubKey` | ⚠️ |
| `NodeIdentity` | `loaded_` | `m_loaded` | ⚠️ |
| `NodeIdentity` | `impl_` | `m_impl` | ⚠️ |

### 2a.2 Core Engine ⚠️
| Class | Current | Target | Status |
|-------|---------|--------|--------|
| `MNNInferenceEngine` | `cfg_` | `m_cfg` | ⚠️ |
| `MNNInferenceEngine` | `loaded_` | `m_loaded` | ⚠️ |
| `MNNInferenceEngine` | `model_path_` | `m_modelPath` | ⚠️ |

### 2a.3 API Server — Config struct naming bugs ❌
| Member | Problem | Should be |
|--------|---------|-----------|
| `grammar_m_modelPath` | `m_` in middle of name | `m_grammarModelPath` |
| `math_m_modelPath` | `m_` in middle of name | `m_mathModelPath` |
| `m_knowledgefacts_` | trailing `_` after `m_` | `m_knowledgeFacts` |
| `sg_processing_m_networkMode` | mixed conventions | `m_sgProcessingNetworkMode` |
| `sg_m_endpoint` | mixed conventions | `m_sgEndpoint` |

### 2a.4 API Server — other members ⚠️
| Current | Target |
|---------|--------|
| `cfg_` | `m_cfg` |
| `running_` | `m_running` |
| `identity_` | `m_identity` |

### 2a.5 Function Argument Renames
All `snake_case` arguments → `camelCase` throughout. Spot-check and fix incrementally.

### 2a.6 Accessor Method Renames ⚠️
| Class | Current | Target |
|-------|---------|--------|
| `NodeIdentity` | `PeerId()` | `GetPeerId()` |
| `NodeIdentity` | `PublicKey()` | `GetPublicKey()` |
| `NodeIdentity` | `IsLoaded()` | ✅ OK |

---

## Phase 2b: Class/Type Name Renames ⚠️ IN PROGRESS

### 2b.1 API Server ⚠️
| Current | Target | Status |
|---------|--------|--------|
| `GeniusAPIServer` | `ApiServer` | ⚠️ Class rename not done |
| `GeniusResponse` | `InferenceResponse` | ⚠️ Not done |
| Log strings: `"GeniusAPIServer"` | `"ApiServer"` | ❌ |
| Include guard: `NEOSWARM_API_GENIUSAPISERVER_HPP` | `NEOSWARM_API_API_SERVER_HPP` | ❌ |

### 2b.2 SuperGeniusClient ⚠️
| Current | Target | Status |
|---------|--------|--------|
| `SuperGeniusClient` class | TBD — `SgClient` or keep? | ⚠️ **DECISION NEEDED** — appears in ~80+ locations across 8 files |

This is the largest remaining class rename. The file was renamed to `super_genius_client.hpp` but the class inside still uses `SuperGeniusClient`. If the "Genius" prefix must go, this class needs renaming. However, it bridges to the SuperGenius blockchain, so the name may be intentional.

### 2b.3 FFI Macros
| Current | Target |
|---------|--------|
| `GENIUS_ELM_CHAT_C_API` | `NEOSWARM_ELM_CHAT_C_API` |
| `GENIUS_ELM_CHAT_C_NOEXCEPT` | `NEOSWARM_ELM_CHAT_C_NOEXCEPT` |

**Note:** This is a C ABI — coordinate with Flutter bridge consumers before renaming.

### 2b.4 Log/String Literals with "Genius"
| File | Line | Current Text |
|------|------|-------------|
| `src/core/sgprocessing/sg_processing_bridge.cpp` | 194 | `"GeniusNeoSwarm inference job"` |
| `src/genius_elm_chat_completions.cpp` | 17 | `"genius-elm-stub"` (model name) |
| `src/genius_elm_chat_completions.cpp` | 23 | `"Genius ELM is running in stub mode."` |

---

## Phase 3: Header Guard Fixes ✅ DONE

All include guards use `NEOSWARM_*_HPP` without trailing underscores.

**One exception**: `src/api/api_server.hpp` guard is `NEOSWARM_API_GENIUSAPISERVER_HPP` — still
references the old `GeniusAPIServer` class name. Fixed as part of Phase 2b.1.

---

## Phase 4: Library Name Renames (CMake) ✅ DONE

All library targets already use the `neoswarm_` prefix. No `genius_` prefixed targets remain.

| Was | Now | Done |
|-----|-----|------|
| `genius_security` | `neoswarm_security` | ✅ |
| `genius_core` | `neoswarm_core` | ✅ |
| `genius_network` | `neoswarm_network` | ✅ |
| `genius_api` | `neoswarm_api` | ✅ |
| `genius_reputation` | `neoswarm_reputation` | ✅ |
| `genius_knowledge` | `neoswarm_knowledge` | ✅ |
| `genius_router` | `neoswarm_router` | ✅ |
| `genius_specialists` | `neoswarm_specialists` | ✅ |
| `genius_common` | `neoswarm_common` | ✅ |

---

## Phase 5: Function Size Refactors ❌ NOT STARTED

Split oversized functions into helpers (max ~100 lines per Handbook Guideline 67):

| File | Function | Lines | Split Into |
|------|----------|-------|------------|
| `src/core/engine/mnn_inference_engine.cpp` | `MNNInferenceEngine::Infer()` | ~659 | `InferSgProcessing()`, `InferMnnLlm()`, `InferInterpreter()` |
| `src/core/sgprocessing/sg_processing_bridge.cpp` | `SGProcessingBridge::BuildSchemaJson()` | ~242 | Format helpers |
| `src/security/node_identity.cpp` | `SaveEncrypted()` / `LoadEncrypted()` | ~570 | Crypto step helpers |
| `src/api/api_server.cpp` | `ApiServer::Initialize()` | ~192 | Subsystem init helpers |
| `src/api/api_server.cpp` | `ApiServer::Process()` | TBD | Mode dispatch |
| `src/api/api_server.cpp` | `ApiServer::Serve()` | TBD | Replace busy-loop with proper async server |

---

## Phase 6: Remove Platform Ifdefs & Busy-Waits ❌ NOT STARTED

Per Handbook Standard 114 — use `Platform.hpp` header, not `#ifdef` in source.

### 6.1 — Source files (production code)
No `#ifdef __unix__` / `#ifdef _WIN32` found in `src/`. ✅

### 6.2 — Test/benchmark files
| File | Pattern | Action |
|------|---------|--------|
| `test/benchmark/bench_mnn_llm.cpp:30` | `#ifdef __APPLE__` | Wrap in `Platform.hpp` or leave (benchmark only) |
| `test/benchmark/bench_mnn_llm.cpp:52` | `#ifdef __APPLE__` | Wrap in `Platform.hpp` or leave (benchmark only) |

### 6.3 — Busy-wait replacements
| File | Location | Issue | Fix |
|------|----------|-------|-----|
| `src/api/api_server.cpp:476` | `Serve()` method | `sleep_for(100ms)` busy-loop | Replace with condition_variable / async wait |
| `src/network/sg_client/sg_channel_manager.cpp:109` | Retry loop | `sleep_for(backoff)` | OK — retry backoff, not a busy-wait |

---

## Phase 7: Cleanup & Debt ✅ DONE

### 7.1 — Delete orphaned files ✅
- `test/ffi/test_genius_slm_ffi.cpp` — deleted (was orphaned, not built, superseded by `test_genius_elm_ffi.cpp`)

### 7.2 — Fix CMake target name mismatch ✅
- `test/CMakeLists.txt:62` — target already renamed to `test_genius_elm_ffi`

### 7.3 — Fix `GENIUS_HAS_ROCKSDB` double definition ✅
- Only one `target_compile_definitions` for `GENIUS_HAS_ROCKSDB` exists (line 17)
- The `elseif(TARGET rocksdb)` block (line 18-19) links but intentionally does not define the macro

### 7.4 — Test names still using old conventions ✅
| Test CMake Target | Status |
|-------------------|--------|
| `test_genius_elm_ffi` | Matches source file `test_genius_elm_ffi.cpp` |

---

## Execution Order (Updated)

| Order | Phase | Description | Status | Dependencies |
|-------|-------|-------------|--------|-------------|
| 1 | 0 | Lint Infrastructure | ✅ DONE | — |
| 2 | 2 | File Renames (PascalCase → snake_case) | ✅ DONE | Phase 0 |
| 3 | 4 | Library Name Renames (CMake) | ✅ DONE | Phase 2 |
| 4 | 3 | Header Guard Fixes | ✅ DONE | Phase 2 |
| 5 | 1 | Remove Feature-Gate #ifdefs | ✅ DONE | Phase 0 |
| 6 | 2a | Member Variable Naming | ⚠️ IN PROGRESS | Phase 2 |
| 7 | 2b | Class/Type Name Renames | ⚠️ IN PROGRESS | Phase 2a |
| 8 | 7 | Cleanup & Debt | ✅ DONE | — |
| 9 | 5 | Function Size Refactors | ❌ | Phases 1–2b |
| 10 | 6 | Remove Platform Ifdefs & Busy-Waits | ❌ | Phase 5 |

**Each PR**: rename 2-3 files + fix internal naming → build → test → lint → commit.
