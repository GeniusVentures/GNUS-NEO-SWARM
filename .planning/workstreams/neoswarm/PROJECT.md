# GNUS NEO SWARM

## What This Is

GNUS NEO SWARM is the decentralized peer-to-peer swarm AI engine powering the GNUS ecosystem.
A Micro LLM router intelligently orchestrates specialist Nano Language Models (NLMs) into emergent
ultra-smart intelligence via routed micro-nodes — running on consumer hardware with no central point
of control.

The engine is a C++17 shared library (`libGenius-MOS-SLM-FFI`) with a Flutter chat UI, exposing
an OpenAI v1-compatible chat completions API. It targets macOS, Linux, Windows, Android, and iOS,
and integrates with the **SuperGenius** blockchain compute network for production-scale distributed
inference via gRPC.

## Core Value

Real LLM inference on consumer hardware in a fully decentralized swarm, production-connected to the
SuperGenius/GNUS network for distributed AI compute.

## Requirements

### Validated

- ✓ Real Mistral-7B inference via MNN LLM API with Metal GPU acceleration — existing
- ✓ MNN model loading, SentencePiece tokenization, autoregressive token generation — existing
- ✓ FP4 v3 codec for 4-bit weight quantization / decompression — existing
- ✓ Rule-based router: SingleNode / Specialist / Swarm execution modes — existing
- ✓ Reputation scoring, weighted consensus, CRDT-based sync — existing
- ✓ Knowledge retrieval (TF-IDF stub), context injection, fact validation — existing
- ✓ Grammar and Math specialist post-processing — existing
- ✓ FFI layer for Flutter/Dart chat app integration — existing
- ✓ CLI interface (`neo-swarm`) with REPL, single-shot, and serve modes — existing
- ✓ Cross-platform CMake + Ninja build with stub fallbacks for all optional deps — existing
- ✓ **PROC-01**: MNN LLM text generation processor (`MNN_Llm`, `DataType::LLM`) in SGProcessingManager — Phase 4
- ✓ **PROC-02**: FP4_ULTRA input-format validation + dispatch plumbing in SGProcessingManager (decode delegated to MNN) — Phase 4
- ✓ **FIX-04**: Test binaries link cleanly with SGProcessingManager enabled (bare `MNN` target PATH-resolution bug fixed) — Phase 4

### Active

- [ ] **SG-01**: SGProcessingBridge::SubmitNetwork dispatches inference jobs to SuperGenius via gRPC
- [ ] **SG-02**: Add `--sg-endpoint` CLI flag for SuperGenius node address
- [ ] **SEC-01**: Enable GENIUS_HAS_SECP256K1 — real secp256k1 node identity (library already linked)
- [ ] **SEC-02**: Implement real MessageSigning::Verify (replace always-true stub)
- [ ] **SEC-03**: Encrypt node private key at rest (AES-256-GCM)
- [ ] **PERS-01**: RocksDB persistence for ReputationStorage (library already linked)
- [ ] **PERS-02**: Fix ReputationStorage::Deserialize crash (wrap stod/stoull in try/catch)
- [ ] **FIX-01**: Fix GeniusSlmInit re-init bug (std::call_once deadlock)
- [ ] **FIX-02**: Remove hardcoded vocab size 32000 (use tokenizer_->VocabSize())
- [ ] **FIX-03**: Add JSON config file support (replace CLI-only config)
- [ ] **TEST-01**: Security module tests (NodeIdentity, MessageSigning)
- [ ] **TEST-02**: FFI layer tests (GeniusSlmInit, chat completions, re-init)
- [ ] **TEST-03**: Knowledge module tests (FactValidation, KnowledgeRetrieval)

### Out of Scope

- OAuth / social login for swarm nodes — not relevant to engine layer
- Real-time streaming token output in Flutter (Task 7.2) — UX polish, not production-blocking
- Full libp2p P2P network integration (GossipSub, mDNS) — complex, deferred to later milestone
- iOS/Android device deployment — macOS proven, mobile is separate platform task
- Semantic embeddings for KnowledgeRetrieval (replace TF-IDF stub) — nice-to-have

## Context

**Current State:** Prototype with Mistral-7B producing real inference output via MNN LLM API.
All 46 tests pass, zero build errors. Most subsystems implemented but using stub/fallback mode
for optional dependencies (secp256k1, RocksDB, SGProcessing network path).

**SuperGenius Connection:** The sibling `SuperGenius/` repository contains the blockchain compute
network. GNUS-NEO-SWARM connects as a client via `SGProcessingBridge`:
- **Phase 1 (Local):** Direct processing via SGProcessingManager — working, stub mode
- **Phase 2 (Network):** Dispatch via gRPCForSuperGenius to a SuperGenius node — NOT YET IMPLEMENTED

`SGProcessingBridge::SubmitNetwork()` returns `Error::NotImplemented`. This is the gap to close.

**Technical Environment:**
- C++17, CMake 3.22+, Ninja, Boost 1.85.0 (outcome::result for error handling)
- MNN with LLM support (Metal/Vulkan GPU), SentencePiece tokenizer
- RocksDB, secp256k1, OpenSSL, libp2p, protobuf in thirdparty
- Flutter 3.x UI with flutter_chat_ui, dart:ffi bridge
- 8 compile-time feature flags (GENIUS_HAS_MNN, _SECP256K1, _ROCKSDB, etc.)

**Known Issues:**
- MessageSigning::Verify always returns true — zero inter-node auth
- NodeIdentity private key stored as plain hex on disk
- ~~SentencePiece and SGProcessing have protobuf symbol conflict (cannot link both)~~ — CORRECTED (Phase 4 research, 2026-08-18): this conflict does not exist in the current codebase. SentencePiece was never actually integrated (no implementation file, no compile flag). The real historical concern was informal, undocumented protobuf-version consolidation across the SGProcessing dependency chain, now resolved by linking a single SGProcessingManager build (Phase 4, plan 04-01).
- ExtractPrompt uses manual JSON parsing (fragile, no nlohmann/json)
- gRPC serve mode is a busy-wait sleep loop (stub)
- P2P libp2p integration is skeleton code, swarm falls back to single-node

## Constraints

- **Language:** C++17 only — no C++20 features permitted
- **Platforms:** macOS (primary), Linux, Windows, Android, iOS
- **Dependencies:** Pre-built thirdparty from `thirdparty/build/<Platform>/<BuildType>/`
- **Style:** Microsoft-based with modifications (.clang-format), 120 char limit, Allman bracing
- **Error Handling:** outcome::result<T>, noexcept by default, no exceptions in hot paths
- **Testing:** Google Test, wait-condition templates, no sleep_for in tests
- **SuperGenius:** Must work with existing SuperGenius/gRPCForSuperGenius interface
- **Memory:** Mistral-7B requires 8GB+ RAM (5.3GB weights + KV cache)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| MNN LLM API over raw Interpreter | LLMs need autoregressive generation with KV-cache; Interpreter only does single-pass tensor inference | ✓ Good |
| Stub fallbacks for all optional deps | Enables build/testing without all libraries available; graceful degradation | ✓ Good |
| Single Façade orchestrator (GeniusAPIServer) | Simple, explicit control flow; knows all component dependencies | — Pending |
| CSV serialization for reputation (not protobuf) | Quick to implement, but fragile (commas in keys break parsing) | ⚠️ Revisit |
| Manual JSON parsing in FFI layer | Avoids nlohmann/json dependency in FFI surface, but fragile and incomplete | ⚠️ Revisit |
| All MNN calls consolidated into SGProcessingManager (Phase 4) | It already owns Vulkan locking/coexistence; SuperGenius network nodes automatically gain LLM-serving capability too | ✓ Good |
| Reuse `MNN::MNN` via `add_library(MNN ALIAS MNN::MNN)` when nested (Phase 4) | NEO-SWARM's own unguarded `find_library(MNN...)` picked up an unrelated `C:\MNNTools\MNN.lib` from PATH instead of the vendored, LLM-enabled build — root-caused a link-stage LNK2005/LNK2019 pair | ✓ Good |

---
*Last updated: 2026-08-21 after Phase 4*
