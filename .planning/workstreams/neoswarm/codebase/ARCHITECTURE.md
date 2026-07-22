<!-- refreshed: 2026-06-17 -->
# Architecture

**Analysis Date:** 2026-06-17

## System Overview

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│                          Entry Points                                         │
│  `src/main.cpp` (CLI)          `src/genius_elm_chat_completions.cpp` (FFI)   │
├──────────────────────────────────────────────────────────────────────────────┤
│                          API Layer                                            │
│  `src/api/api_server.hpp/.cpp`  —  Orchestration Facade                      │
├──────────┬────────────┬──────────────┬────────────┬────────────┬─────────────┤
│  Router  │ Core Engine│ Specialists  │ Reputation │  Network   │  Knowledge  │
│`router/` │  `core/`   │`specialists/`│`reputation/`│`network/`  │`knowledge/` │
│          │            │              │            │            │             │
│ Rule     │ MNN Infer- │ • Grammar    │ Scoring    │ P2P Node   │ Retrieval   │
│ Based    │ ence Engine│ • Math       │ Consensus  │ libp2p     │ Context Inj │
│ Router   │ Tokenizer  │ • Symbolic F │ Storage    │ SG Client  │ Fact Valid  │
│          │ FP4 Codec  │   allback    │ CRDT LWW   │ Aggreg.    │             │
│          │ SG Bridge  │              │            │            │             │
├──────────┴────────────┴──────────────┴────────────┴────────────┴─────────────┤
│                          Security Layer                                       │
│  `src/security/node_identity.hpp`  `src/security/message_signing.hpp`         │
├──────────────────────────────────────────────────────────────────────────────┤
│                          Common / Types                                       │
│  `src/common/types.hpp`  `src/common/error.hpp`  `src/common/logging.hpp`     │
└──────────────────────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| `ApiServer` | Orchestrates full inference pipeline; owns all subsystems | `src/api/api_server.hpp` |
| `RuleBasedRouter` | Analyses prompts & selects execution mode (single/specialist/swarm) | `src/router/rule_based_router.hpp` |
| `PromptAnalyzer` | Extracts routing features from prompt text (numeric density, complexity, keywords) | `src/router/prompt_analyzer.hpp` |
| `MNNInferenceEngine` | Runs LLM inference via MNN (Vulkan/CPU), or SGProcessing bridge | `src/core/engine/mnn_inference_engine.hpp` |
| `SGProcessingBridge` | Bridges to SuperGenius SGProcessingManager for GNUS network dispatch | `src/core/sgprocessing/sg_processing_bridge.hpp` |
| `TensorInterpreter` | Converts raw tensor output bytes to human-readable text | `src/core/sgprocessing/tensor_interpreter.hpp` |
| `SentencePieceTokenizer` | Token encoding/decoding; falls back to whitespace tokenizer | `src/core/tokenizer/tokenizer.hpp` |
| `FP4Codec` | FP4 4-bit floating-point quantization for model weight compression | `src/core/fp4/fp4_codec.hpp` |
| `GrammarSpecialist` | Grammar correction model, post-processes core LLM output | `src/specialists/grammar_specialist.hpp` |
| `MathSpecialist` | Math model with symbolic fallback | `src/specialists/math_specialist.hpp` |
| `SymbolicFallback` | Expression parser/evaluator triggered on low math model confidence | `src/specialists/symbolic_fallback.hpp` |
| `WeightedConsensus` | Selects winning output from swarm nodes (weighted voting or best score) | `src/reputation/weighted_consensus.hpp` |
| `ReputationScoring` | Reputation update formulas (accuracy, latency, consistency) | `src/reputation/reputation_scoring.hpp` |
| `ReputationStorage` | RocksDB-backed persistence for reputation records | `src/reputation/reputation_storage.hpp` |
| `ReputationCRDT` | Last-Write-Wins CRDT for cross-node reputation sync | `src/reputation/reputation_crdt.hpp` |
| `P2PNode` | libp2p host for task broadcasting and CRDT sync (Noise/Yamux/GossipSub) | `src/network/p2p_node.hpp` |
| `ResultAggregation` | Timeout-bounded collection of swarm node responses | `src/network/result_aggregation.hpp` |
| `SuperGeniusClient` | Client for SuperGenius blockchain compute network dispatch via PubSub gRPC | `src/network/sg_client/super_genius_client.hpp` |
| `KnowledgeRetrieval` | TF-IDF embedding + cosine similarity for Grokipedia facts | `src/knowledge/knowledge_retrieval.hpp` |
| `ContextInjection` | Prepends retrieved facts to prompts before inference | `src/knowledge/context_injection.hpp` |
| `FactValidation` | Post-generation fact checking against grounding facts | `src/knowledge/fact_validation.hpp` |
| `NodeIdentity` | secp256k1 keypair generation, encrypted storage, and PeerId derivation | `src/security/node_identity.hpp` |
| `MessageSigning` | secp256k1 sign/verify for inter-node messages | `src/security/message_signing.hpp` |

## Pattern Overview

**Overall:** Orchestration Pipeline with Facade pattern at the top and Strategy (polymorphic interface) pattern for pluggable subsystems.

**Key Characteristics:**
- `ApiServer` is the Facade that owns and coordinates all subsystems
- Abstract interfaces (`InferenceEngine`, `IRouter`, `ISpecialist`, `Tokenizer`) enable runtime strategy substitution
- PImpl idiom (`struct Impl`) used extensively for ABI stability and to hide heavy third-party includes (`SuperGeniusClient`, `P2PNode`, `NodeIdentity`, `ReputationStorage`, `MNNInferenceEngine`)
- Three-tier execution modes selected by the router (Single -> Specialist -> Swarm) with fallback chains
- All external dependencies degrade gracefully (stub mode when libp2p/MNN/SentencePiece/RocksDB not found)
- Cross-platform: MNN with Vulkan backend (MoltenVK on Apple), CMake + Ninja for building

## Layers

**Entry Point Layer:**
- Purpose: CLI argument parsing and bootstrap, or C FFI for Flutter integration
- Location: `src/main.cpp`, `src/genius_elm_chat_completions.h` / `src/genius_elm_chat_completions.cpp`
- Contains: `main()`, `Args` struct, argument parser, interactive REPL, JSON config loader
- Depends on: `src/api/api_server.hpp`
- Used by: External clients (terminal, Flutter app)

**API Layer:**
- Purpose: Orchestration of the full inference pipeline -- initialise all subsystems, route requests, execute inference, update reputation
- Location: `src/api/api_server.hpp` / `src/api/api_server.cpp`
- Contains: `ApiServer` class with `Initialize()`, `Process()`, `Serve()`, `Stop()`, private `RunSingleNode()`, `RunSpecialist()`, `RunSwarm()` methods
- Depends on: All other layers (router, core, specialists, reputation, network, knowledge, security)
- Used by: Entry points

**Router Layer:**
- Purpose: Analyse incoming prompt and decide which execution mode and specialist to use
- Location: `src/router/`
- Contains: `PromptAnalyzer` (feature extraction), `RuleBasedRouter` (decision tree), `IRouter` (abstract interface)
- Depends on: `src/common/types.hpp`
- Used by: API layer

**Core Inference Layer:**
- Purpose: LLM model loading, tokenization, inference, and FP4 quantization
- Location: `src/core/`
- Contains: `InferenceEngine` (abstract), `MNNInferenceEngine` (concrete), `Tokenizer` (abstract), `SentencePieceTokenizer`, `FP4Codec`, `SGProcessingBridge`, `TensorInterpreter`
- Depends on: `src/common/`, MNN library, SentencePiece (disabled), Vulkan, SGProcessingManager (optional)
- Used by: API layer, specialists

**Specialists Layer:**
- Purpose: Domain-specific post-processing models (grammar correction, math reasoning)
- Location: `src/specialists/`
- Contains: `ISpecialist` (abstract), `GrammarSpecialist`, `MathSpecialist`, `SymbolicFallback`
- Depends on: Core inference layer (uses shared `InferenceEngine`)
- Used by: API layer (Specialist mode)

**Reputation Layer:**
- Purpose: Compute, store, synchronise, and query node reputation scores for swarm consensus
- Location: `src/reputation/`
- Contains: `ReputationScoring`, `WeightedConsensus`, `ReputationStorage`, `ReputationCRDT`
- Depends on: `src/common/`, RocksDB (optional)
- Used by: API layer, network layer

**Network Layer:**
- Purpose: P2P swarm communication via libp2p and SuperGenius blockchain compute network
- Location: `src/network/`
- Contains: `P2PNode`, `ResultAggregation`, `sg_client/` sub-directory with `SuperGeniusClient`, `SgChannelManager`, `SgJobSubmitter`, `SgResultCollector`, `SgMessageAuthenticator`
- Depends on: `src/security/`, libp2p (optional), gRPC (optional)
- Used by: API layer (Swarm mode, SuperGenius dispatch)

**Knowledge Layer:**
- Purpose: Retrieve Grokipedia facts, inject them into prompts, validate generated output
- Location: `src/knowledge/`
- Contains: `KnowledgeRetrieval`, `ContextInjection`, `FactValidation`
- Depends on: `src/common/`
- Used by: API layer

**Security Layer:**
- Purpose: Node identity (secp256k1 keys, AES-256-GCM encrypted storage), message signing and verification
- Location: `src/security/`
- Contains: `NodeIdentity`, `MessageSigning`
- Depends on: `src/common/`, secp256k1, OpenSSL (SHA-256, AES-256-GCM)
- Used by: API layer, network layer

**Common Layer:**
- Purpose: Shared types, error codes, and logging utilities
- Location: `src/common/`
- Contains: `types.hpp` (all data structs), `error.hpp` (error enum + `outcome::result` alias), `error.cpp`, `logging.hpp` (`CreateLogger` factory)
- Depends on: libp2p (for `outcome::result`), spdlog, fmt
- Used by: All other layers

## Data Flow

### Primary Request Path

1. **Entry** -- CLI (`src/main.cpp:252` `main`) parses args, loads JSON config if specified, constructs `ApiServer::Config`, calls `server.Initialize()` then `server.Process(task)`
2. **Route** -- `ApiServer::Process()` (`src/api/api_server.cpp:431`) calls `m_router->Route(t)`, which invokes `PromptAnalyzer::Analyze()` to extract features, then `RuleBasedRouter` to decide `ExecutionMode`
3. **Augment** -- `AugmentPrompt()` (`src/api/api_server.cpp:210`) calls `KnowledgeRetrieval::Retrieve()` + `ContextInjection::Inject()` to prepend Grokipedia facts to the prompt
4. **Dispatch** -- Switch on `ExecutionMode` (`src/api/api_server.cpp:454`):
   - **SingleNode**: `m_coreEngine->Infer(aug_task)` -> `RunSingleNode()` returns `InferenceResponse`
   - **Specialist**: `m_coreEngine->Infer(aug_task)` -> then `MathSpecialist::Process(output)` or `GrammarSpecialist::Process(output)` -> `FactValidation::Validate()` -> `RunSpecialist()` returns `InferenceResponse`
   - **Swarm**: `m_p2pNode->BroadcastTask(aug_task)` -> `ResultAggregation::Collect()` -> `WeightedConsensus::SelectWinner()` -> `RunSwarm()` returns `InferenceResponse`
5. **Validate** -- In Specialist mode, `FactValidation::Validate(output, facts)` checks for contradictions; failed validation increases perplexity penalty
6. **Reputation** -- `UpdateReputation()` (`src/api/api_server.cpp:228`) runs `ReputationScoring::Update()` -> `ReputationStorage::Put()` -> `ReputationCRDT::Merge()` -> `P2PNode::BroadcastCRDT()`
7. **Response** -- `InferenceResponse` returned to caller with output, mode used, latency, success flag

### Startup/Initialization Flow

1. `ApiServer::Initialize()` (`src/api/api_server.cpp:48`)
2. `NodeIdentity` -- load or generate secp256k1 keypair (try encrypted first, fallback to plaintext, then generate new), derive PeerId
3. `MNNInferenceEngine` -- create engine with config (sgprocessing or interpreter mode, vulkan or cpu backend), attach tokenizer, load model (or enter stub mode)
4. `GrammarSpecialist` / `MathSpecialist` -- create with shared engine, load specialist models if paths provided
5. `RuleBasedRouter` -- create with default rule config
6. `ReputationScoring` / `WeightedConsensus` / `ReputationCRDT` -- create cores
7. `ReputationStorage` -- open RocksDB at configured path
8. `P2PNode` / `ResultAggregation` -- start libp2p host if `m_enableNetwork` set
9. `SuperGeniusClient` -- if `GENIUS_HAS_GRPC` and endpoint configured: initialize with identity, connect, wire into engine's SGProcessingBridge
10. `KnowledgeRetrieval` / `ContextInjection` / `FactValidation` -- load facts CSV if `m_enableKnowledge` set

**State Management:**
- `ApiServer` owns all subsystems via `shared_ptr` (identity, engine, specialists, knowledge) or `unique_ptr` (router, consensus, scoring, storage, crdt, p2p, aggregation, context_inj, fact_val, sgClient)
- `ResultAggregation` holds `vector<NodeOutput>` guarded by `std::mutex` + `std::condition_variable`
- All component state is instance-local; no global mutable singletons
- `spdlog` loggers are registered globally via `spdlog::get()` but created through `CreateLogger()` per component

## Key Abstractions

**`InferenceEngine` (Abstract Interface):**
- Purpose: Decouples inference backend from routing and orchestration logic
- Examples: `src/core/engine/inference_engine.hpp` (interface), `src/core/engine/mnn_inference_engine.hpp` (implementation)
- Pattern: Strategy -- runtime selection of "sgprocessing" (SGProcessingManager) or "interpreter" (MNN direct) paths, with "vulkan" or "cpu" backends

**`IRouter` (Abstract Interface):**
- Purpose: Decouples routing strategy from the API server; enables future ML-based routers
- Examples: `src/router/i_router.hpp` (interface), `src/router/rule_based_router.hpp` (implementation)
- Pattern: Strategy -- rule-based decision tree using `PromptFeatures` extracted by `PromptAnalyzer`

**`ISpecialist` (Abstract Interface):**
- Purpose: Decouples specialist models from core pipeline; enables adding new domains without changing orchestration
- Examples: `src/specialists/i_specialist.hpp` (interface), `src/specialists/math_specialist.hpp`, `src/specialists/grammar_specialist.hpp`
- Pattern: Strategy -- each specialist wraps a shared `InferenceEngine` and defines its own prompt formatting

**`Tokenizer` (Abstract Interface):**
- Purpose: Decouples tokenization strategy; enables swapping SentencePiece for other tokenizers
- Examples: `src/core/tokenizer/tokenizer.hpp` (interface), `src/core/tokenizer/sentence_piece_tokenizer.cpp` (implementation)
- Pattern: Strategy -- `SentencePieceTokenizer` delegates to sentencepiece library or falls back to whitespace tokenizer

## Entry Points

**CLI Entry (`neo-swarm` binary):**
- Location: `src/main.cpp`
- Triggers: Command-line invocation (`./neo-swarm --model <path>`)
- Responsibilities: Parse args, load JSON config, initialize `ApiServer`, run in interactive REPL, single-shot prompt, or serve mode

**C FFI Entry (`Genius-MOS-ELM-FFI` shared library):**
- Location: `src/genius_elm_chat_completions.h` / `src/genius_elm_chat_completions.cpp`
- Triggers: Called from Flutter/Dart via `dart:ffi`
- Responsibilities: Exposes `GeniusElmInit()`, `GeniusElmChat()`, `GeniusElmStatus()`, `GeniusElmShutdown()`, `GeniusElmStringFree()` -- currently stub mode

**gRPC Entry:**
- Location: Proto definitions in `proto/genius_api.proto`
- Triggers: `GeniusAPI.Infer()`, `GeniusAPI.StreamInfer()`, `GeniusAPI.GetNodeStatus()`
- Status: Proto defined; server is busy-loop placeholder in `ApiServer::Serve()`

## Architectural Constraints

- **Threading:** Single-threaded orchestration in `ApiServer::Process()` -- one request at a time. `ResultAggregation` uses `std::condition_variable` for timeout-bounded collection. `ReputationCRDT` guards state with `std::mutex`. No thread pooling in core pipeline.
- **Global state:** `spdlog` loggers are globally registered via `spdlog::get()` but created per-component through `CreateLogger()`. No other global mutable state.
- **Circular imports:** Not detected -- layers flow top-down: API -> (router, core, specialists, reputation, network, knowledge) -> common. Specialists depend on core (shared_ptr to `InferenceEngine`). Security is used by API and network.
- **Exception handling:** Error handling uses `outcome::result<T>` with `BOOST_OUTCOME_TRY` for propagation. The CLAUDE.md style guide specifies noexcept for all functions by default.
- **C++ standard:** C++17 required; no C++20 features permitted. No designated initializers, no boost::coroutines.
- **Stub/fallback mode:** Every optional third-party dependency (MNN, libp2p, SentencePiece, RocksDB, Vulkan, SGProcessingManager, gRPC) has a stub fallback when not available at link time.
- **Conditional compilation:** Minimal `#ifdef` usage -- most dependencies checked via CMake `if(TARGET ...)` at build time. `GENIUS_HAS_GRPC` is the main compile guard in source files.

## Anti-Patterns

### Orchestrator owns all dependencies

**What happens:** `ApiServer` has member pointers for every single subsystem -- `m_coreEngine`, `m_grammarSpec`, `m_mathSpec`, `m_router`, `m_consensus`, `m_scoring`, `m_repStorage`, `m_repCrdt`, `m_p2pNode`, `m_aggregation`, `m_knowledge`, `m_contextInj`, `m_factVal`, `m_sgClient` -- all as explicit members.
**Why it's wrong:** Adding a new subsystem requires modifying the `ApiServer` class definition, constructor, `Initialize()`, `Process()`, and three mode methods.
**Do this instead:** Consider a `ComponentRegistry` or dependency injection container (Boost.DI is available) to reduce the orchestrator's member surface.

### Busy-wait serve loop

**What happens:** `ApiServer::Serve()` (`src/api/api_server.cpp:469`) implements a busy-wait polling loop with `sleep_for(100ms)` checking an atomic flag.
**Why it's wrong:** This is a stub implementation -- the real gRPC server is not integrated. The busy-wait wastes CPU.
**Do this instead:** Integrate the actual gRPC server using `grpc::ServerBuilder::BuildAndStart()` with proper blocking `server->Wait()` semantics.

## Error Handling

**Strategy:** `outcome::result<T>` (Boost.Outcome via libp2p) for all return types. `BOOST_OUTCOME_TRY` macro for propagation.

**Patterns:**
- All subsystem `Initialize()`, `Load()`, `Start()`, `Open()` methods return `outcome::result<void>`
- All inference/routing/processing methods return `outcome::result<T>` with typed errors
- The top-level `ApiServer::Process()` returns `outcome::result<InferenceResponse>` -- callers check `res.has_value()`
- Stub fallbacks are used instead of throwing: when a dependency is unavailable, the component enters a degraded mode (e.g., `MNNInferenceEngine::SetStubMode()`)

**Error enum** (`src/common/error.hpp`):
- Core: `ModelLoadFailed` (1), `InferenceFailed` (2), `TokenizerFailed` (3), `FP4DecodeFailed` (4)
- Router: `RoutingFailed` (5)
- Network: `NetworkError` (6), `PeerNotFound` (7), `BroadcastTimeout` (8)
- Reputation: `StorageError` (9), `ReputationNotFound` (10)
- Knowledge: `KnowledgeUnavailable` (11), `FactValidationFailed` (12)
- Security: `IdentityError` (13), `SignatureInvalid` (14)
- General: `InvalidArgument` (15), `NotImplemented` (16), `InternalError` (17)

## Cross-Cutting Concerns

**Logging:** `spdlog` via `CreateLogger("ComponentName")` factory in `src/common/logging.hpp`. Pattern: `[YYYY-MM-DD HH:MM:SS.ms] [LEVEL] [NeoSwarm/ComponentName] message`. Can be set to `spdlog::level::debug` via `--verbose` CLI flag.

**Validation:** `FactValidation` (post-generation fact checking), `PromptAnalyzer` (input feature extraction), `ReputationScoring::Update()` (score clamping to [0,1]).

**Authentication:** `NodeIdentity` (secp256k1 keypairs, AES-256-GCM encrypted storage, PeerId = SHA-256 of compressed public key), `MessageSigning` (secp256k1 signatures on inter-node messages).

---

*Architecture analysis: 2026-06-17*
