<!-- refreshed: 2026-05-26 -->
# Architecture

**Analysis Date:** 2026-05-26

## System Overview

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                        ENTRY POINTS (CLI / FFI)                              │
├──────────────────────────┬──────────────────────┬───────────────────────────┤
│  genius_node.cpp (CLI)   │ genius_slm_chat_c.cpp │  Flutter App / gRPC      │
│  `src/genius_node.cpp`   │ (C FFI to Dart)      │                           │
│                          │ `src/genius_slm_     │                           │
│                          │  chat_c.cpp`          │                           │
└──────────┬───────────────┴──────────┬───────────┴─────────────┬────────────┘
           │                          │                         │
           ▼                          ▼                         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     ORCHESTRATION LAYER (API)                                │
│  `src/api/GeniusAPIServer.cpp` — GeniusAPIServer                             │
│  Owns pipeline: Route → Infer → (Specialist) → (Consensus) → Respond         │
└───┬───────┬───────┬───────┬───────┬───────┬───────┬───────┬─────────────────┘
    │       │       │       │       │       │       │       │
    ▼       ▼       ▼       ▼       ▼       ▼       ▼       ▼
┌───┴───┬───┴───┬───┴───┬───┴───┬───┴───┬───┴───┬───┴───┬───┴─────────────┐
│Router │ Core  │ Special. │Reput. │Network│ Knowl.│Security│ Common         │
│`src/  │`src/  │`src/     │`src/  │`src/  │`src/  │`src/   │`src/common/`   │
│router/│core/  │special.` │reput.`│network│knowl.`│security│                 │
│       │       │          │       │ /`     │edge/` │ /`     │                 │
└───┬───┴───┬───┴───┬──────┴───┬───┴───────┴───┬───┴───┬───┴─────────────────┘
    │       │       │          │               │       │
    ▼       ▼       ▼          ▼               ▼       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                   EXTERNAL / OPTIONAL DEPENDENCIES                            │
│  MNN .mnn │ SentencePiece │ Vulkan/MoltenVK │ secp256k1 │ RocksDB │ libp2p  │
│  ProtoBuf  │ SuperGenius   │ SGProcessingMgr │ NL/J       │ OpenSSL │ ASIO   │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| `genius_node.cpp` | CLI entry point, arg parsing, REPL loop, server mode | `src/genius_node.cpp` |
| `genius_slm_chat_c.cpp` | C FFI bridge for Flutter/Dart, OpenAI v1 chat-compatible JSON API | `src/genius_slm_chat_c.cpp` |
| `GeniusAPIServer` | Orchestrates entire inference pipeline, owns all subsystems, manages lifecycle | `src/api/GeniusAPIServer.hpp` |
| `InferenceEngine` | Abstract LLM inference backend (MNN real + stub) | `src/core/engine/InferenceEngine.hpp` |
| `RuleBasedRouter` | Prompt analysis and routing decision: CoreOnly, CorePlusMath, CorePlusGrammar | `src/router/RuleBasedRouter.hpp` |
| `PromptAnalyzer` | Feature extraction from raw prompt (numeric density, code syntax, complexity) | `src/router/PromptAnalyzer.hpp` |
| `MathSpecialist` | GSM8K-tuned 1–3B math model with symbolic fallback | `src/specialists/MathSpecialist.hpp` |
| `GrammarSpecialist` | Grammar correction specialist model | `src/specialists/GrammarSpecialist.hpp` |
| `WeightedConsensus` | Aggregates outputs from swarm nodes using reputation-weighted voting | `src/reputation/WeightedConsensus.hpp` |
| `ReputationScoring` | Updates per-node reputation scores from inference results | `src/reputation/ReputationScoring.hpp` |
| `ReputationStorage` | Persistence layer for reputation (RocksDB or in-memory fallback) | `src/reputation/ReputationStorage.hpp` |
| `ReputationCRDT` | Conflict-free replicated reputation data type for P2P sync | `src/reputation/ReputationCRDT.hpp` |
| `P2PNode` | libp2p-based peer-to-peer networking (optional) | `src/network/P2PNode.hpp` |
| `ResultAggregation` | Aggregates results from multiple swarm nodes within timeout | `src/network/ResultAggregation.hpp` |
| `NodeIdentity` | secp256k1 node keypair generation, peer ID derivation, sign/verify | `src/security/NodeIdentity.hpp` |
| `MessageSigning` | Message authentication for inter-node communication | `src/security/MessageSigning.hpp` |
| `KnowledgeRetrieval` | Retrieves relevant facts from Grokipedia CSV for prompt grounding | `src/knowledge/KnowledgeRetrieval.hpp` |
| `ContextInjection` | Injects retrieved facts into the prompt context | `src/knowledge/ContextInjection.hpp` |
| `FactValidation` | Validates inference output against known facts | `src/knowledge/FactValidation.hpp` |
| `FP4Codec` | FP4 (4-bit floating point) encode/decode for efficient model weights | `src/core/fp4/FP4Codec.hpp` |
| `SGProcessingBridge` | Bridge to SuperGenius SGProcessingManager for Phase 1 (local) and Phase 2 (network) | `src/core/sgprocessing/SGProcessingBridge.hpp` |
| `SentencePieceTokenizer` | Tokenizer wrapping SentencePiece library (optional, stub fallback) | `src/core/tokenizer/SentencePieceTokenizer.cpp` |
| `Types.hpp` | All shared data types: Task, InferenceResponse, RouteDecision, etc. | `src/common/Types.hpp` |
| `Error.hpp` | Error code enum (17 codes) + outcome::result alias | `src/common/Error.hpp` |

## Pattern Overview

**Overall:** Layered monolith with strategy/interface abstractions at subsystem boundaries, composed into a single orchestrator.

**Key Characteristics:**
- **Interface-based polymorphism:** Core abstractions (`IRouter`, `ISpecialist`, `InferenceEngine`) are abstract base classes with virtual methods, enabling swapping implementations without changing orchestration code.
- **Ownership via `std::unique_ptr`/`std::shared_ptr`:** The `GeniusAPIServer` owns all subsystems as members. Singleton engines (`InferenceEngine`, tokenizer) use `shared_ptr` to allow sharing with specialists. All other subsystems use `unique_ptr` for exclusive ownership.
- **Error propagation via `outcome::result<T>`:** All functions that can fail return `outcome::result<T>` using the `BOOST_OUTCOME_TRY` macro for early returns — no exceptions in hot paths.
- **`noexcept` by default:** All functions declared `noexcept` unless explicitly required to throw per project standards.
- **CMake static library composition:** Each `src/<module>/` compiles into a named static library (`genius_common`, `genius_core`, `genius_router`, etc.) with explicit dependency links.
- **Optional features via `#ifdef` guards:** MNN, SentencePiece, Vulkan, secp256k1, RocksDB, libp2p, Protobuf, and SGProcessingManager are all conditionally compiled behind `GENIUS_HAS_*` macros.
- **Stub-mode operation:** When optional libraries are absent, every component provides stub/placeholder behavior. The entire system runs end-to-end in stub mode for development and testing without real model inference.

## Layers

**Common Layer:**
- Purpose: Shared types, error codes, logging facade. No external module dependencies except spdlog and outcome.
- Location: `src/common/`
- Contains: `Types.hpp`, `Error.hpp`, `Logging.hpp`, `Error.cpp`
- Depends on: spdlog, libp2p::outcome, fmt
- Used by: Every other module

**Core Layer:**
- Purpose: Inference engine abstraction, MNN backend, tokenizer, FP4 codec, SGProcessing bridge. The "heavy lifting" layer.
- Location: `src/core/`
- Contains: `engine/`, `fp4/`, `tokenizer/`, `sgprocessing/`
- Depends on: `genius_common`, optional MNN, SentencePiece, Vulkan, SGProcessingManager
- Used by: `genius_api`, `genius_specialists`

**Router Layer:**
- Purpose: Prompt feature analysis and routing decisions. Determines which specialist (if any) should process the prompt.
- Location: `src/router/`
- Contains: `IRouter.hpp`, `RuleBasedRouter`, `PromptAnalyzer`
- Depends on: `genius_common`
- Used by: `genius_api`

**Specialists Layer:**
- Purpose: Domain-specific post-processing models (Math, Grammar). Takes core LLM output and refines it.
- Location: `src/specialists/`
- Contains: `ISpecialist.hpp`, `MathSpecialist`, `GrammarSpecialist`, `SymbolicFallback`
- Depends on: `genius_common`, `genius_core` (shares InferenceEngine)
- Used by: `genius_api`

**Reputation Layer:**
- Purpose: Node reputation scoring, weighted consensus aggregation, CRDT sync, persistent storage.
- Location: `src/reputation/`
- Contains: `ReputationScoring`, `WeightedConsensus`, `ReputationStorage`, `ReputationCRDT`, `NodeReputation`
- Depends on: `genius_common`, optional RocksDB + snappy + zlib
- Used by: `genius_api`

**Network Layer:**
- Purpose: P2P node communication via libp2p, result aggregation from multiple swarm nodes.
- Location: `src/network/`
- Contains: `P2PNode`, `ResultAggregation`
- Depends on: `genius_common`, `genius_security`, optional libp2p + nlohmann/json + fmt + soralog
- Used by: `genius_api`

**Knowledge Layer:**
- Purpose: Fact retrieval from Grokipedia CSV, context injection into prompts, fact validation of responses.
- Location: `src/knowledge/`
- Contains: `KnowledgeRetrieval`, `ContextInjection`, `FactValidation`
- Depends on: `genius_common`
- Used by: `genius_api`

**Security Layer:**
- Purpose: Node identity (secp256k1 keypair), message signing/verification for inter-node trust.
- Location: `src/security/`
- Contains: `NodeIdentity`, `MessageSigning`
- Depends on: `genius_common`, optional secp256k1 + OpenSSL
- Used by: `genius_api`, `genius_network`

**API / Orchestration Layer:**
- Purpose: Wires all subsystems together. Provides `Initialize()`, `Process()`, `Serve()` lifecycle methods. The single entry point for all request flow.
- Location: `src/api/`
- Contains: `GeniusAPIServer`
- Depends on: All other modules (links to all)
- Used by: `genius_node.cpp`, `genius_slm_chat_c.cpp`, gRPC clients

**Entry Points / Frontends:**
- Purpose: CLI binary (`neo-swarm`) and C FFI shared library (`Genius-MOS-SLM-FFI.dylib`) for Flutter integration.
- Location: `src/genius_node.cpp`, `src/genius_slm_chat_c.cpp`, `src/genius_slm_chat_c.h`
- Depends on: `genius_api`
- Used by: End users (CLI), Flutter app via `flutter_slm_bridge` (FFI)

## Data Flow

### Primary Request Path (SingleNode Mode)

1. **Entry:** `genius_node.cpp:162 main()` parses CLI args, builds `GeniusAPIServer::Config`, creates server, calls `Initialize()`
2. **Orchestration:** `GeniusAPIServer::Process()` at `src/api/GeniusAPIServer.cpp` receives `Task`
3. **Route:** `RuleBasedRouter::Route()` at `src/router/RuleBasedRouter.cpp` analyzes prompt via `PromptAnalyzer`, returns `RouteDecision`
4. **Context Injection:** `ContextInjection` at `src/knowledge/ContextInjection.cpp` augments prompt with Grokipedia facts
5. **Inference:** `InferenceEngine::Infer()` at `src/core/engine/MNNInferenceEngine.cpp` runs model (stub if no MNN), returns `InferenceResponse`
6. **Response:** `GeniusResponse` returned with output text, latency, grounding facts

### Specialist Mode Path (Mode 2)

1. Steps 1–5 as above (Core engine runs first)
2. **Specialist Processing:** `MathSpecialist::Process()` or `GrammarSpecialist::Process()` at `src/specialists/` refines core output
3. **Symbolic Fallback:** `SymbolicFallback` at `src/specialists/SymbolicFallback.cpp` kicks in when model confidence < threshold
4. **Response:** Combined core+specialist output returned

### Swarm Mode Path (Mode 3 — future/prototype)

1. **Broadcast:** Task sent to peer nodes via `P2PNode` at `src/network/P2PNode.cpp`
2. **Aggregation:** `ResultAggregation` collects responses from swarm within timeout
3. **Consensus:** `WeightedConsensus::ComputeConsensus()` at `src/reputation/WeightedConsensus.cpp` applies reputation-weighted voting
4. **Validation:** `FactValidation` at `src/knowledge/FactValidation.cpp` ground-truth check
5. **Reputation Update:** `ReputationScoring` updates node scores based on contribution quality

### FFI / Flutter Path

1. **Dart side:** `flutter_slm_bridge/lib/flutter_slm_bridge.dart` loads `Genius-MOS-SLM-FFI.dylib` via `dart:ffi`
2. **C FFI:** `GeniusSlmInit()` initializes singleton `GeniusAPIServer` at `src/genius_slm_chat_c.cpp`
3. **Chat call:** `GeniusSlmChatCompletionsCreate()` parses OpenAI v1 JSON request, extracts user prompt, calls `server.Process()`, formats response as OpenAI v1 JSON
4. **Dart response:** Response string parsed, content extracted via `extractContent()`, displayed in Flutter chat UI (`flutter_app/lib/main.dart`)

**State Management:**
- `GeniusAPIServer` owns all subsystem state as member variables
- FFI singleton: `g_server` (`std::unique_ptr<GeniusAPIServer>`) + `std::call_once` — global mutable state in `genius_slm_chat_c.cpp` (see CONCERNS.md for re-init bug)
- No global state in other modules

## Key Abstractions

**`IRouter` — Abstract routing interface:**
- Purpose: Decouples routing strategy from orchestration. Currently only `RuleBasedRouter` implements it, but ML-based routers can be added.
- Location: `src/router/IRouter.hpp`
- Pattern: Strategy pattern — clean interface with single `Route(Task) → RouteDecision` method

**`ISpecialist` — Abstract specialist interface:**
- Purpose: Decouples specialist models from routing. Math and Grammar specialists share the same interface; new domains (Code, Translation) added by implementing `ISpecialist`.
- Location: `src/specialists/ISpecialist.hpp`
- Pattern: Strategy + Template Method — `Load()`, `Process()`, `GetConfidence()` lifecycle

**`InferenceEngine` — Abstract inference backend:**
- Purpose: Decouples model backend from orchestration. `MNNInferenceEngine` is the real implementation; stub mode is built-in when MNN unavailable.
- Location: `src/core/engine/InferenceEngine.hpp`
- Pattern: Bridge pattern — separates engine abstraction from MNN-specific implementation

**`NodeIdentity` — Cryptographic identity:**
- Purpose: secp256k1 keypair management, PeerId derivation, signing. Stub mode uses random XOR hash when secp256k1 unavailable.
- Location: `src/security/NodeIdentity.hpp`
- Pattern: Entity + RAII — key material loaded from/saved to file

**`GeniusAPIServer::Config` — Designated initializer struct:**
- Purpose: Single configuration struct with all subsystem settings passed by `const&`. Uses named members for self-documenting initialization.
- Location: `src/api/GeniusAPIServer.hpp`

## Entry Points

**CLI Binary (`neo-swarm`):**
- Location: `src/genius_node.cpp`
- Triggers: Command line invocation with `--model <path> [options]`
- Responsibilities: Argument parsing, server init, REPL or single-prompt or `--serve`

**FFI Shared Library (`Genius-MOS-SLM-FFI`):**
- Location: `src/genius_slm_chat_c.cpp`
- Triggers: Dynamically loaded by Dart/Flutter via `dart:ffi`
- Responsibilities: Singleton server management, JSON parsing, OpenAI v1 format translation
- Build target: `Genius-MOS-SLM-FFI` shared library (`.dylib`/`.so`/`.dll`)

**gRPC Service (optional/prototype):**
- Location: Defined in `proto/genius_api.proto`
- Triggers: gRPC client connecting to port 50051
- Operations: `Infer`, `StreamInfer`, `GetNodeStatus`

## Architectural Constraints

- **C++17 only:** No C++20 features allowed. Boost.coroutines explicitly forbidden.
- **Threading:** The system runs single-threaded in stub mode. P2P networking (libp2p) and GPU inference (Vulkan) introduce their own threading when enabled. Flutter FFI calls run on Dart isolates.
- **Global state:** One global mutable singleton (`g_server` + `g_init_flag` in `src/genius_slm_chat_c.cpp`) for the FFI path. CLI path creates server on the stack — no global state.
- **Circular imports:** None detected. Dependency graph is a strict DAG: `common → {core, router, security, knowledge, reputation, specialists} → network → api`.
- **No exceptions in hot paths:** All inference, routing, and scoring functions use `outcome::result<T>` return types. Exceptions only in argument parsing (CLI) and fatal shutdown.
- **Stub-first design:** Every optional dependency has a `#ifdef`-guarded real path and a fallback stub. The system compiles and runs with zero optional libraries.

## Anti-Patterns

### `std::call_once` re-init bug

**What happens:** `GeniusSlmChatCompletionsCreate()` at `src/genius_slm_chat_c.cpp:213` uses `std::call_once(g_init_flag, InitServerOnce)`. If `GeniusSlmInit()` is called multiple times (it resets `g_server` and manually calls `InitServerOnce`), the next `GeniusSlmChatCompletionsCreate()` — which also lazy-inits — will see `call_once` already consumed and won't re-init, leaving `g_server == nullptr`.

**Why it's wrong:** `call_once` becomes stale after re-init; the flag should be reset when `g_server` is reset.

**Do this instead:** Replace `std::call_once` with a simple `if (g_server == nullptr)` null check in `GeniusSlmChatCompletionsCreate`. Remove `g_init_flag`. See `AgentDocs/PRODUCTION_ROADMAP.md` Task 5.2.

### Hardcoded vocab size 32000

**What happens:** `SentencePieceTokenizer::VocabSize()` returns `32000` and `MNNInferenceEngine` allocates logit vectors of size `32000` in stub mode — hardcoded for Mistral 7B.

**Why it's wrong:** Any other model with a different vocab size will have logit size mismatches.

**Do this instead:** Read vocab size from the loaded model once SentencePiece is linked. Return `0` until then to signal "unknown". See `AgentDocs/PRODUCTION_ROADMAP.md` Task 5.1.

### Stub-only `MessageSigning::Verify`

**What happens:** `MessageSigning::Verify` at `src/security/MessageSigning.cpp` always returns `true` — any message from any peer is accepted, with a `TODO(SECURITY)` comment.

**Why it's wrong:** No cryptographic verification of inter-node messages. Any peer can impersonate any other.

**Do this instead:** Implement real secp256k1 signature verification after linking secp256k1 (Task 2.1 in `PRODUCTION_ROADMAP.md`).

## Error Handling

**Strategy:** `outcome::result<T>` for all fallible operations. The `BOOST_OUTCOME_TRY` macro provides early-return-on-error propagation.

**Patterns:**
- All module functions return `outcome::result<void>` or `outcome::result<SomeType>`
- 17 error codes defined in `src/common/Error.hpp` covering all subsystems
- No exceptions in core inference or routing code paths
- CLI argument parsing uses `std::runtime_error` for user-facing errors (acceptable at entry point)

## Cross-Cutting Concerns

**Logging:** spdlog via `sgns::neoswarm::CreateLogger(tag)` factory in `src/common/Logging.hpp`. Named loggers per component: `"NeoSwarm/Router"`, `"NeoSwarm/P2PNode"`, etc. Level controlled by `--verbose` flag.

**Validation:** Prompt analysis in `PromptAnalyzer`, fact validation in `FactValidation`, and `ReputationScoring` all provide validation at their respective layers. No centralized validation framework.

**Authentication:** Stub identity in stub mode; real secp256k1 keypairs when `GENIUS_HAS_SECP256K1`. Message signing stubbed. Not yet suitable for multi-node deployment.

**Configuration:** CLI args and struct-based config (`GeniusAPIServer::Config`, `RuleBasedRouter::Config`, `SGProcessingBridge::Config`). No config file support (YAML/JSON config planned — `PRODUCTION_ROADMAP.md` Task 5.3). No environment variable reading detected in current code.

---

*Architecture analysis: 2026-05-26*
