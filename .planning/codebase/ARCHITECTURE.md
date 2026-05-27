<!-- refreshed: 2026-05-27 -->
# Architecture

**Analysis Date:** 2026-05-27

## System Overview

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│                          Entry Points                                         │
│  `src/genius_node.cpp` (CLI)          `src/genius_slam_chat_c.h/.cpp` (FFI)  │
├──────────────────────────────────────────────────────────────────────────────┤
│                          API Layer                                            │
│  `src/api/GeniusAPIServer.hpp/.cpp`  —  Orchestration Façade                  │
├──────────┬────────────┬──────────────┬────────────┬────────────┬─────────────┤
│  Router  │ Core Engine│ Specialists  │ Reputation │  Network   │  Knowledge  │
│`router/` │  `core/`   │`specialists/`│`reputation/`│`network/`  │`knowledge/` │
│          │            │              │            │            │             │
│ Rule     │ MNN Infer- │ • Grammar    │ Scoring    │ P2P Node   │ Retrieval   │
│ Based    │ ence Engine│ • Math       │ Consensus  │ libp2p     │ Context Inj │
│ Router   │ Tokenizer  │ • Symbolic F │ Storage    │ Aggreg.    │ Fact Valid  │
│          │ FP4 Codec  │   allback    │ CRDT LWW   │            │             │
│          │ SG Bridge  │              │            │            │             │
├──────────┴────────────┴──────────────┴────────────┴────────────┴─────────────┤
│                          Security Layer                                       │
│  `src/security/NodeIdentity.hpp`  `src/security/MessageSigning.hpp`           │
├──────────────────────────────────────────────────────────────────────────────┤
│                          Common / Types                                       │
│  `src/common/Types.hpp`  `src/common/Error.hpp`  `src/common/Logging.hpp`     │
└──────────────────────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| `GeniusAPIServer` | Orchestrates full inference pipeline; owns all subsystems | `src/api/GeniusAPIServer.hpp` |
| `RuleBasedRouter` | Analyses prompts & selects execution mode (single/specialist/swarm) | `src/router/RuleBasedRouter.hpp` |
| `PromptAnalyzer` | Extracts routing features from prompt text (numeric density, complexity, keywords) | `src/router/PromptAnalyzer.hpp` |
| `MNNInferenceEngine` | Runs LLM inference via MNN (Vulkan/CPU), or SGProcessing bridge | `src/core/engine/MNNInferenceEngine.hpp` |
| `SGProcessingBridge` | Bridges to SuperGenius SGProcessingManager for GNUS network dispatch | `src/core/sgprocessing/SGProcessingBridge.hpp` |
| `TensorInterpreter` | Converts raw tensor output bytes to human-readable text | `src/core/sgprocessing/TensorInterpreter.hpp` |
| `SentencePieceTokenizer` | Token encoding/decoding; falls back to whitespace tokenizer | `src/core/tokenizer/Tokenizer.hpp` |
| `FP4Codec` | FP4 v3 4-bit floating-point quantization for model weight compression | `src/core/fp4/FP4Codec.hpp` |
| `GrammarSpecialist` | 200M–500M grammar correction model, post-processes core LLM output | `src/specialists/GrammarSpecialist.hpp` |
| `MathSpecialist` | 1–3B GSM8K-tuned math model with symbolic fallback | `src/specialists/MathSpecialist.hpp` |
| `SymbolicFallback` | Expression parser/evaluator triggered on low math model confidence | `src/specialists/SymbolicFallback.hpp` |
| `WeightedConsensus` | Selects winning output from swarm nodes (weighted voting or best score) | `src/reputation/WeightedConsensus.hpp` |
| `ReputationScoring` | PTDS §7.2 reputation update formulas (accuracy, latency, consistency) | `src/reputation/ReputationScoring.hpp` |
| `ReputationStorage` | RocksDB-backed persistence for reputation records | `src/reputation/ReputationStorage.hpp` |
| `ReputationCRDT` | Last-Write-Wins CRDT for cross-node reputation sync | `src/reputation/ReputationCRDT.hpp` |
| `P2PNode` | libp2p host for task broadcasting and CRDT sync (Noise/Yamux/GossipSub) | `src/network/P2PNode.hpp` |
| `ResultAggregation` | Timeout-bounded collection of swarm node responses | `src/network/ResultAggregation.hpp` |
| `KnowledgeRetrieval` | TF-IDF embedding + cosine similarity for Grokipedia facts | `src/knowledge/KnowledgeRetrieval.hpp` |
| `ContextInjection` | Prepends retrieved facts to prompts before inference | `src/knowledge/ContextInjection.hpp` |
| `FactValidation` | Post-generation fact checking against grounding facts | `src/knowledge/FactValidation.hpp` |
| `NodeIdentity` | secp256k1 keypair generation and PeerId derivation | `src/security/NodeIdentity.hpp` |
| `MessageSigning` | secp256k1 sign/verify for inter-node messages | `src/security/MessageSigning.hpp` |

## Pattern Overview

**Overall:** Orchestration Pipeline with Façade pattern at the top and Strategy (polymorphic interface) pattern for pluggable subsystems.

**Key Characteristics:**
- `GeniusAPIServer` is the Façade that owns and coordinates all subsystems
- Abstract interfaces (`InferenceEngine`, `IRouter`, `ISpecialist`, `Tokenizer`) enable runtime strategy substitution
- PIMPL idiom (`struct Impl`) used extensively for ABI stability and to hide heavy third-party includes
- Three-tier execution modes selected by the router (Single → Specialist → Swarm) with fallback chains
- All external dependencies degrade gracefully (stub mode when libp2p/MNN/SentencePiece/RocksDB not found)
- Cross-platform: MNN with Vulkan backend (MoltenVK on Apple), CMake + Ninja for building

## Layers

**Entry Point Layer:**
- Purpose: CLI argument parsing and bootstrap, or C FFI for Flutter integration
- Location: `src/genius_node.cpp`, `src/genius_slm_chat_c.h` / `src/genius_slm_chat_c.cpp`
- Contains: `main()`, `Args` struct, argument parser, interactive REPL, gRPC serve mode
- Depends on: `src/api/GeniusAPIServer.hpp`
- Used by: External clients (terminal, Flutter app)

**API Layer:**
- Purpose: Orchestration of the full inference pipeline — initialise all subsystems, route requests, execute inference, update reputation
- Location: `src/api/GeniusAPIServer.hpp` / `src/api/GeniusAPIServer.cpp`
- Contains: `GeniusAPIServer` class with `Initialize()`, `Process()`, `Serve()`, `Stop()`, private `RunSingleNode()`, `RunSpecialist()`, `RunSwarm()` methods
- Depends on: All other layers (router, core, specialists, reputation, network, knowledge, security)
- Used by: Entry points

**Router Layer:**
- Purpose: Analyse incoming prompt and decide which execution mode and specialist to use
- Location: `src/router/`
- Contains: `PromptAnalyzer` (feature extraction), `RuleBasedRouter` (decision tree), `IRouter` (abstract interface)
- Depends on: `src/common/Types.hpp`
- Used by: API layer

**Core Inference Layer:**
- Purpose: LLM model loading, tokenization, inference, and FP4 quantization
- Location: `src/core/`
- Contains: `InferenceEngine` (abstract), `MNNInferenceEngine` (concrete), `Tokenizer` (abstract), `SentencePieceTokenizer`, `FP4Codec`, `SGProcessingBridge`, `TensorInterpreter`
- Depends on: `src/common/`, MNN library, SentencePiece, Vulkan, SGProcessingManager (optional)
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
- Contains: `ReputationScoring`, `WeightedConsensus`, `ReputationStorage`, `ReputationCRDT`, `NodeReputation` (type alias)
- Depends on: `src/common/`, RocksDB (optional)
- Used by: API layer, network layer

**Network Layer:**
- Purpose: P2P swarm communication via libp2p — task broadcast, result collection, CRDT sync
- Location: `src/network/`
- Contains: `P2PNode`, `ResultAggregation`
- Depends on: `src/security/`, libp2p (optional, stub when absent)
- Used by: API layer (Swarm mode)

**Knowledge Layer:**
- Purpose: Retrieve Grokipedia facts, inject them into prompts, validate generated output
- Location: `src/knowledge/`
- Contains: `KnowledgeRetrieval`, `ContextInjection`, `FactValidation`
- Depends on: `src/common/`
- Used by: API layer

**Security Layer:**
- Purpose: Node identity (secp256k1 keys), message signing and verification
- Location: `src/security/`
- Contains: `NodeIdentity`, `MessageSigning`
- Depends on: `src/common/`, secp256k1, OpenSSL (SHA-256)
- Used by: API layer, network layer

**Common Layer:**
- Purpose: Shared types, error codes, and logging utilities
- Location: `src/common/`
- Contains: `Types.hpp` (all data structs), `Error.hpp` (error enum + `outcome::result` alias), `Error.cpp`, `Logging.hpp` (`CreateLogger` factory)
- Depends on: libp2p (for `outcome::result`), spdlog, fmt
- Used by: All other layers

## Data Flow

### Primary Request Path

1. **Entry** — CLI (`src/genius_node.cpp:162` `main`) parses args, constructs `GeniusAPIServer::Config`, calls `server.Initialize()` then `server.Process(task)`
2. **Route** — `GeniusAPIServer::Process()` calls `router_->Route(t)` (`src/api/GeniusAPIServer.cpp:395`), which invokes `PromptAnalyzer::Analyze()` to extract features, then `RuleBasedRouter::SelectMode()` to decide `ExecutionMode`
3. **Augment** — `AugmentPrompt()` calls `KnowledgeRetrieval::Retrieve()` + `ContextInjection::Inject()` to prepend Grokipedia facts to the prompt
4. **Dispatch** — Switch on `ExecutionMode`:
   - **SingleNode**: `core_engine_->Infer(aug_task)` → `RunSingleNode()` returns `GeniusResponse`
   - **Specialist**: `core_engine_->Infer(aug_task)` → then `MathSpecialist::Process(output)` or `GrammarSpecialist::Process(output)` → `RunSpecialist()` returns `GeniusResponse`
   - **Swarm**: `p2p_node_->BroadcastTask(aug_task)` → `ResultAggregation::Collect()` → `WeightedConsensus::SelectWinner()` → `RunSwarm()` returns `GeniusResponse`
5. **Validate** — In Specialist mode, `FactValidation::Validate(output, facts)` checks for contradictions
6. **Reputation** — `UpdateReputation()` runs `ReputationScoring::Update()` → `ReputationStorage::Put()` → `ReputationCRDT::Merge()` → `P2PNode::BroadcastCRDT()`
7. **Response** — `GeniusResponse` returned to caller with output, mode used, latency, grounding facts

### Startup/Initialization Flow

1. `GeniusAPIServer::Initialize()` (`src/api/GeniusAPIServer.cpp:45`)
2. `NodeIdentity` — load or generate secp256k1 keypair, derive PeerId
3. `MNNInferenceEngine` — create engine with config, attach tokenizer, load model (or enter stub mode)
4. `GrammarSpecialist` / `MathSpecialist` — create with shared engine, load specialist models if paths provided
5. `RuleBasedRouter` — create with default rule config
6. `ReputationScoring` / `WeightedConsensus` / `ReputationCRDT` — create cores
7. `ReputationStorage` — open RocksDB at configured path
8. `P2PNode` / `ResultAggregation` — start libp2p host if `enable_network_` set
9. `KnowledgeRetrieval` / `ContextInjection` / `FactValidation` — load facts CSV if `enable_knowledge_` set

**State Management:**
- `GeniusAPIServer` owns all subsystems via `shared_ptr` (identity, engines, specialists, knowledge) or `unique_ptr` (router, consensus, scoring, storage, CRDT, p2p, aggregation, context_inj, fact_val)
- `ReputationCRDT` holds mutable `unordered_map<string, NodeReputation>` guarded by `std::mutex`
- `ResultAggregation` holds `vector<NodeOutput>` guarded by `std::mutex` + `std::condition_variable`
- All component state is instance-local; no global mutable singletons
- `spdlog` loggers are registered globally via `spdlog::get()` but created through `CreateLogger()` per component

## Key Abstractions

**`InferenceEngine` (Abstract Interface):**
- Purpose: Decouples inference backend from routing and orchestration logic
- Examples: `src/core/engine/InferenceEngine.hpp` (interface), `src/core/engine/MNNInferenceEngine.hpp` (implementation)
- Pattern: Strategy — runtime selection of "sgprocessing" (SGProcessingManager) or "interpreter" (MNN direct) paths, with "vulkan" or "cpu" backends

**`IRouter` (Abstract Interface):**
- Purpose: Decouples routing strategy from the API server; enables future ML-based routers
- Examples: `src/router/IRouter.hpp` (interface), `src/router/RuleBasedRouter.hpp` (implementation)
- Pattern: Strategy — rule-based decision tree using `PromptFeatures` extracted by `PromptAnalyzer`

**`ISpecialist` (Abstract Interface):**
- Purpose: Decouples specialist models from core pipeline; enables adding new domains without changing orchestration
- Examples: `src/specialists/ISpecialist.hpp` (interface), `src/specialists/MathSpecialist.hpp`, `src/specialists/GrammarSpecialist.hpp`
- Pattern: Strategy — each specialist wraps a shared `InferenceEngine` and defines its own prompt formatting

**`Tokenizer` (Abstract Interface):**
- Purpose: Decouples tokenization strategy; enables swapping SentencePiece for other tokenizers
- Examples: `src/core/tokenizer/Tokenizer.hpp` (interface), `src/core/tokenizer/SentencePieceTokenizer.cpp` (implementation)
- Pattern: Strategy — `SentencePieceTokenizer` delegates to sentencepiece library or falls back to whitespace tokenizer

## Entry Points

**CLI Entry (`neo-swarm` binary):**
- Location: `src/genius_node.cpp`
- Triggers: Command-line invocation (`./neo-swarm --model <path>`)
- Responsibilities: Parse args, initialize `GeniusAPIServer`, run in interactive REPL, single-shot prompt, or gRPC serve mode

**C FFI Entry (`Genius-MOS-SLM-FFI` shared library):**
- Location: `src/genius_slm_chat_c.h` / `src/genius_slm_chat_c.cpp`
- Triggers: Called from Flutter/Dart via `dart:ffi`
- Responsibilities: Exposes `GeniusSlmInit()`, `GeniusSlmChatCompletionsCreate()`, `GeniusSlmGetStatus()`, `GeniusSlmStringFree()` for OpenAI-compatible chat completions

**gRPC Entry:**
- Location: Proto definitions in `proto/genius_api.proto`
- Triggers: `GeniusAPI.Infer()`, `GeniusAPI.StreamInfer()`, `GeniusAPI.GetNodeStatus()`
- Responsibilities: Client-facing gRPC interface for synchronous/streaming inference and node health; `Serve()` in `GeniusAPIServer` is currently stub (polling loop)

## Architectural Constraints

- **Threading:** Single-threaded orchestration in `GeniusAPIServer::Process()` — one request at a time. `ResultAggregation` uses `std::condition_variable` for timeout-bounded collection. `ReputationCRDT` guards state with `std::mutex`. No thread pooling in core pipeline.
- **Global state:** `spdlog` loggers are globally registered via `spdlog::get()` but created per-component through `CreateLogger()`. No other global mutable state.
- **Circular imports:** Not detected — layers flow top-down: API → (router, core, specialists, reputation, network, knowledge) → common. Specialists depend on core (shared_ptr to `InferenceEngine`). Security is used by API and network.
- **Exception handling:** Functions are not explicitly noexcept in most code; the CLAUDE.md style guide specifies noexcept for all functions by default. Error handling uses `outcome::result<T>` with `BOOST_OUTCOME_TRY` for propagation.
- **C++ standard:** C++17 required; no C++20 features permitted.
- **Stub/fallback mode:** Every optional third-party dependency (MNN, libp2p, SentencePiece, RocksDB, Vulkan, SGProcessingManager) has a stub fallback when not available at link time.

## Anti-Patterns

### Restrained Orchestrator owns all dependencies

**What happens:** `GeniusAPIServer` has member pointers for every single subsystem — `core_engine_`, `grammar_spec_`, `math_spec_`, `router_`, `consensus_`, `scoring_`, `rep_storage_`, `rep_crdt_`, `p2p_node_`, `aggregation_`, `knowledge_`, `context_inj_`, `fact_val_` — all as explicit members.
**Why it's wrong:** Adding a new subsystem requires modifying the `GeniusAPIServer` class definition, constructor, `Initialize()`, `Process()`, and three mode methods. Every change touches the central orchestrator.
**Do this instead:** Maintain the Façade pattern but consider a `ComponentRegistry` or dependency injection container (Boost.DI is already configured as a transitive dependency) to reduce the orchestrator's member surface.

### Raw pointer to MNN::Session

**What happens:** `MNNInferenceEngine` stores `MNN::Session *session_ = nullptr` as a raw pointer alongside `shared_ptr<MNN::Interpreter>`.
**Why it's wrong:** Lifetime is linked to the interpreter but not enforced by the type system. If the interpreter is destroyed before the session pointer is cleared, it becomes dangling.
**Do this instead:** Store `session_` as `unique_ptr<MNN::Session, SessionDeleter>` or ensure `session_` is always cleared in the destructor before `interpreter_`.

### Busy-wait gRPC serve loop

**What happens:** `GeniusAPIServer::Serve()` (`src/api/GeniusAPIServer.cpp:422`) implements a busy-wait polling loop with `sleep_for(100ms)` checking an atomic flag.
**Why it's wrong:** This is a stub implementation — the real gRPC server is not integrated. The busy-wait wastes CPU and introduces unnecessary latency.
**Do this instead:** Integrate the actual gRPC server using `grpc::ServerBuilder::BuildAndStart()` with proper blocking `server->Wait()` semantics.

## Error Handling

**Strategy:** `outcome::result<T>` (Boost.Outcome via libp2p) for all return types. `BOOST_OUTCOME_TRY` macro for propagation.

**Patterns:**
- All subsystem `Initialize()`, `Load()`, `Start()`, `Open()` methods return `outcome::result<void>`
- All inference/routing/processing methods return `outcome::result<T>` with typed errors
- The top-level `GeniusAPIServer::Process()` returns `outcome::result<GeniusResponse>` — callers check `res.has_value()`
- Stub fallbacks are used instead of throwing: when a dependency is unavailable, the component enters a degraded mode (e.g., `MNNInferenceEngine::SetStubMode()`)

**Error enum** (`src/common/Error.hpp`):
- Core: `ModelLoadFailed` (1), `InferenceFailed` (2), `TokenizerFailed` (3), `FP4DecodeFailed` (4)
- Router: `RoutingFailed` (5)
- Network: `NetworkError` (6), `PeerNotFound` (7), `BroadcastTimeout` (8)
- Reputation: `StorageError` (9), `ReputationNotFound` (10)
- Knowledge: `KnowledgeUnavailable` (11), `FactValidationFailed` (12)
- Security: `IdentityError` (13), `SignatureInvalid` (14)
- General: `InvalidArgument` (15), `NotImplemented` (16), `InternalError` (17)

## Cross-Cutting Concerns

**Logging:** `spdlog` via `CreateLogger("ComponentName")` factory in `src/common/Logging.hpp`. Pattern: `[YYYY-MM-DD HH:MM:SS.ms] [LEVEL] [NeoSwarm/ComponentName] message`. Can be set to `spdlog::level::debug` via `--verbose` CLI flag.

**Validation:** `FactValidation` (post-generation fact checking), `PromptAnalyzer` (input feature extraction), `ReputationScoring::Update()` (score clamping to [0,1]).

**Authentication:** `NodeIdentity` (secp256k1 keypairs, PeerId = SHA-256 of compressed public key), `MessageSigning` (secp256k1 signatures on inter-node messages, JSON signature attachment/stripping).

---

*Architecture analysis: 2026-05-27*
