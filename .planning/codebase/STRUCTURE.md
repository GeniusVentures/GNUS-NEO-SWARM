# Codebase Structure

**Analysis Date:** 2026-05-27

## Directory Layout

```
GNUS-NEO-SWARM/
├── src/                          # C++ source — the core engine library
│   ├── genius_node.cpp           #   CLI entry point (neo-swarm binary)
│   ├── genius_slm_chat_c.h       #   C FFI header (Flutter/Dart bridge)
│   ├── genius_slm_chat_c.cpp     #   C FFI implementation
│   ├── api/                      #   Orchestration / API server layer
│   ├── common/                   #   Shared types, errors, logging
│   ├── core/                     #   Inference engine, tokenizer, quantization, SGProcessing
│   ├── knowledge/                #   Grokipedia retrieval, context injection, fact validation
│   ├── network/                  #   P2P networking (libp2p), result aggregation
│   ├── reputation/               #   Scoring, consensus, storage, CRDT sync
│   ├── router/                   #   Prompt analysis and rule-based routing
│   ├── security/                 #   Node identity, message signing
│   └── specialists/              #   Grammar and math specialist models
├── test/                         # Unit, integration, and benchmark tests
│   ├── CMakeLists.txt            #   Test build config (GTest)
│   ├── core/                     #   Core unit tests (fp4 codec)
│   ├── router/                   #   Router unit tests
│   ├── reputation/               #   Reputation unit tests
│   ├── integration/              #   Pipeline integration tests
│   └── benchmark/                #   MNN LLM benchmarks (manual, not CTest)
├── proto/                        # gRPC protocol buffer definitions
│   ├── genius_api.proto          #   Client-facing API (Infer, StreamInfer, GetNodeStatus)
│   ├── genius_internal.proto     #   Inter-node messages (TaskMessage, ResultMessage)
│   └── genius_reputation.proto   #   Reputation sync (NodeReputationProto)
├── build/                        # Platform-specific build directories
│   ├── OSX/                      #   macOS builds
│   ├── Linux/                    #   Linux builds
│   ├── Windows/                  #   Windows builds
│   ├── Android/                  #   Android builds
│   ├── iOS/                      #   iOS builds
│   ├── cmake/                    #   Shared cmake helpers (functions, compiler options)
│   ├── CommonBuildParameters.cmake   # Third-party dependency configuration
│   └── CommonCompilerOptions.cmake   # Compiler flags and C++17 config
├── cmake/                        # Project-level cmake config
│   └── CommonBuildParameters.cmake   # Extra build parameter overrides
├── thirdparty/                   # Pre-built third-party libraries (git submodule)
├── docs/                         # Technical documentation and architecture
│   └── architecture/             #   16 design documents (INDEX.md as TOC)
├── flutter_app/                  # Flutter frontend app (Dart)
├── flutter_slm_bridge/           # Flutter native bridge plugin (FFI bindings)
├── ui/                           # Chat Genius Flutter UI project
├── gnus-poc/                     # Proof-of-concept data and models
│   ├── data/                     #   Raw datasets
│   └── models/                   #   Specialist model artifacts
├── AgentDocs/                    # Agent planning documents for AI-assisted development
├── .planning/                    # GSD planning directory (this document's home)
├── .claude/                      # Claude skill configuration
├── .gitignore                    # Git ignore rules
├── .gitmodules                   # Git submodule definitions
├── CLAUDE.md                     # AI development guide (coding standards, build commands)
├── README.md                     # Project overview and build instructions
└── RUN_AND_DEPLOY.md             # Run and deploy instructions
```

## Directory Purposes

**`src/`:**
- Purpose: All C++17 source code for the GNUS NEO SWARM engine and its subsystems
- Contains: `.hpp` headers, `.cpp` implementations, per-directory `CMakeLists.txt` files
- Key files: `genius_node.cpp` (CLI entry), `genius_slm_chat_c.h/.cpp` (FFI), `api/GeniusAPIServer.hpp/.cpp` (orchestrator)

**`src/api/`:**
- Purpose: The top-level orchestration layer — `GeniusAPIServer` initialises and coordinates all subsystems
- Contains: `GeniusAPIServer.hpp`, `GeniusAPIServer.cpp`, `CMakeLists.txt` (builds `genius_api` library)
- Key files: `GeniusAPIServer.hpp` (class definition with all component members), `GeniusAPIServer.cpp` (442 lines — init, process, three execution modes)

**`src/common/`:**
- Purpose: Foundation types, error handling, and logging used by every other module
- Contains: `Types.hpp` (145 lines — all data structs), `Error.hpp` (error enum + outcome alias), `Error.cpp`, `Logging.hpp` (spdlog factory), `CMakeLists.txt`
- Key files: `Types.hpp` (defines `Task`, `InferenceResponse`, `RouteDecision`, `NodeOutput`, `NodeReputation`, `GeniusResponse`, `PromptFeatures`, `KnowledgeFact`)

**`src/core/`:**
- Purpose: LLM inference engine, tokenization, FP4 quantization, and SGProcessing bridge
- Contains: Four subdirectories — `engine/`, `tokenizer/`, `fp4/`, `sgprocessing/`. Builds `genius_core` static library.
- Key files: `engine/MNNInferenceEngine.hpp` (152 lines, two inference paths), `tokenizer/Tokenizer.hpp` (abstract + SentencePiece impl), `fp4/FP4Codec.hpp` (NF4-style 4-bit quantization), `sgprocessing/SGProcessingBridge.hpp` (bridges to SuperGenius)

**`src/router/`:**
- Purpose: Prompt analysis and rule-based routing to select execution mode
- Contains: `IRouter.hpp` (abstract interface), `PromptAnalyzer.hpp/.cpp` (feature extraction), `RuleBasedRouter.hpp/.cpp` (decision tree), `CMakeLists.txt`
- Key files: `RuleBasedRouter.hpp` (threshold-based routing: numeric_density → Math, grammar_request → Grammar, else → CoreOnly)

**`src/specialists/`:**
- Purpose: Domain-specific post-processing models for grammar and math
- Contains: `ISpecialist.hpp` (abstract interface), `GrammarSpecialist.hpp/.cpp`, `MathSpecialist.hpp/.cpp`, `SymbolicFallback.hpp/.cpp`, `CMakeLists.txt`
- Key files: `MathSpecialist.hpp` (uses shared `InferenceEngine`, includes symbolic fallback when confidence < 0.6)

**`src/reputation/`:**
- Purpose: Node reputation computation, consensus selection, persistent storage, and CRDT-based sync
- Contains: `NodeReputation.hpp` (type alias), `ReputationScoring.hpp/.cpp`, `WeightedConsensus.hpp/.cpp`, `ReputationStorage.hpp/.cpp`, `ReputationCRDT.hpp/.cpp`, `CMakeLists.txt`
- Key files: `ReputationScoring.hpp` (4-component update: accuracy, latency, consistency, consensus), `WeightedConsensus.hpp` (2 strategies: WeightedVoting, BestWeightedScore)

**`src/network/`:**
- Purpose: P2P communication via libp2p — task broadcast and result aggregation
- Contains: `P2PNode.hpp/.cpp` (libp2p host), `ResultAggregation.hpp/.cpp` (timeout-bounded collector), `CMakeLists.txt`
- Key files: `P2PNode.hpp` (GossipSub broadcast, Noise encryption, Yamux multiplexing, stub when libp2p absent)

**`src/knowledge/`:**
- Purpose: Grokipedia knowledge retrieval, prompt augmentation, and post-generation fact validation
- Contains: `KnowledgeRetrieval.hpp/.cpp`, `ContextInjection.hpp/.cpp`, `FactValidation.hpp/.cpp`, `CMakeLists.txt`
- Key files: `KnowledgeRetrieval.hpp` (TF-IDF bag-of-words + cosine similarity), `FactValidation.hpp` (numeric claim extraction + contradiction detection)

**`src/security/`:**
- Purpose: Node identity management and inter-node message signing
- Contains: `NodeIdentity.hpp/.cpp` (secp256k1 keypair), `MessageSigning.hpp/.cpp` (sign/verify), `CMakeLists.txt`
- Key files: `NodeIdentity.hpp` (PeerId = hex(SHA-256(compressed_pubkey)), key load/save from hex files)

**`test/`:**
- Purpose: Unit, integration, and benchmark tests using Google Test
- Contains: `CMakeLists.txt` (defines `genius_test` macro), `core/test_fp4_codec.cpp`, `router/test_router.cpp`, `reputation/test_reputation.cpp`, `integration/test_pipeline.cpp`, `integration/test_sgprocessing_pipeline.cpp`, `benchmark/`
- Key files: `CMakeLists.txt` (5 test targets + 1 benchmark subtarget)

**`proto/`:**
- Purpose: gRPC service definitions for client API, inter-node messaging, and reputation sync
- Contains: `genius_api.proto` (60 lines), `genius_internal.proto` (25 lines), `genius_reputation.proto` (23 lines)
- Key files: `genius_api.proto` (defines `GeniusAPI` service with `Infer`, `StreamInfer`, `GetNodeStatus`)

**`build/`:**
- Purpose: Platform-specific CMake entry points and build artifacts
- Contains: `OSX/`, `Linux/`, `Windows/`, `Android/`, `iOS/` directories; shared cmake modules in `build/cmake/`
- Key files: `build/OSX/CMakeLists.txt` (32 lines, sets macOS toolchain), `build/CommonBuildParameters.cmake` (345 lines, configures all third-party deps)

**`docs/architecture/`:**
- Purpose: Comprehensive architecture documentation (16 Markdown files)
- Contains: Executive summary, system overview, model/router design, reputation/consensus, grounding, agentic memory, performance, roadmap, AI safety, distributed swarm thinking, secure agent architecture, eggroll retraining, cognitive retaining, epistemic arbitration
- Key files: `INDEX.md` (table of contents)

**`AgentDocs/`:**
- Purpose: AI agent planning documents — checkpoint, project board, roadmap
- Contains: `CHECKPOINT.md`, `PLAN.md`, `LLM_INTEGRATION.md`, `PRODUCTION_ROADMAP.md`, `PROJECT_BOARD_ISSUES.md`

**`flutter_app/` and `ui/`:**
- Purpose: Flutter frontend applications (Dart) — mobile and desktop UIs
- Contains: Flutter project boilerplate, `lib/` Dart source, platform-specific folders

**`flutter_slm_bridge/`:**
- Purpose: Flutter platform plugin bridging Dart FFI to the `Genius-MOS-SLM-FFI` C shared library
- Contains: `lib/` Dart FFI bindings, `src/` C bridge code, platform-specific build configs

**`gnus-poc/`:**
- Purpose: Proof-of-concept artifacts — datasets and specialist model files
- Contains: `data/` (analysis, specialist datasets), `models/` (specialist MLX models)

## Key File Locations

**Entry Points:**
- `src/genius_node.cpp`: CLI entry — main function, argument parsing, interactive REPL, gRPC serve
- `src/genius_slm_chat_c.h`: C FFI entry — exported C functions for Flutter integration
- `src/genius_slm_chat_c.cpp`: FFI implementation — wraps `GeniusAPIServer`

**Configuration:**
- `build/CommonBuildParameters.cmake`: All third-party dependency configuration (MNN, Vulkan, libp2p, RocksDB, etc.)
- `build/<Platform>/CMakeLists.txt`: Platform-specific build config (toolchain, deployment target)
- `cmake/CommonBuildParameters.cmake`: Additional build parameter overrides
- `.gitmodules`: Third-party submodule definitions

**Core Logic:**
- `src/api/GeniusAPIServer.cpp`: The orchestrator — initialisation sequence (9 subsystems), three execution mode implementations
- `src/core/engine/MNNInferenceEngine.cpp`: The inference engine — dual-path (interpreter + SGProcessing), Vulkan GPU dispatch
- `src/router/RuleBasedRouter.cpp`: Routing decision tree using `PromptAnalyzer` features
- `src/reputation/ReputationScoring.cpp`: Reputation update mathematics
- `src/reputation/WeightedConsensus.cpp`: Swarm consensus winner selection

**Shared Types:**
- `src/common/Types.hpp`: All data structures used across the codebase
- `src/common/Error.hpp`: Error enum (17 codes) and `outcome::result` alias

**Testing:**
- `test/CMakeLists.txt`: Test definitions using `genius_test` macro
- `test/core/test_fp4_codec.cpp`: FP4 quantization/roundtrip tests
- `test/router/test_router.cpp`: Prompt routing tests
- `test/reputation/test_reputation.cpp`: Reputation scoring/storage tests
- `test/integration/test_pipeline.cpp`: End-to-end pipeline tests
- `test/integration/test_sgprocessing_pipeline.cpp`: SGProcessing integration tests

**Protocol:**
- `proto/genius_api.proto`: Client gRPC service definition
- `proto/genius_internal.proto`: Inter-node broadcast messages
- `proto/genius_reputation.proto`: Reputation sync data types

**Documentation:**
- `README.md`: Project overview, build instructions, core concepts
- `CLAUDE.md`: AI development guide with coding standards
- `docs/architecture/INDEX.md`: Architecture documentation index
- `AgentDocs/CHECKPOINT.md`: Current development checkpoint

## Naming Conventions

**Files:**
- Header files: `PascalCase.hpp` (e.g., `GeniusAPIServer.hpp`, `InferenceEngine.hpp`, `NodeIdentity.hpp`)
- Source files: `PascalCase.cpp` (e.g., `GeniusAPIServer.cpp`, `WeightedConsensus.cpp`)
- CMake: `CMakeLists.txt` (standard CMake naming)
- Test files: `test_<lowercase_name>.cpp` (e.g., `test_fp4_codec.cpp`, `test_router.cpp`, `test_pipeline.cpp`)
- Proto files: `snake_case.proto` (e.g., `genius_api.proto`, `genius_internal.proto`)
- Documentation: `UPPER_SNAKE_CASE.md` for agent docs, `kebab-case-numbered.md` for architecture docs

**Directories:**
- Source modules: `lowercase` (e.g., `api/`, `core/`, `router/`, `knowledge/`)
- Source subdirectories: `lowercase` (e.g., `core/engine/`, `core/fp4/`, `core/tokenizer/`)
- Test modules: mirror source structure (e.g., `test/core/`, `test/router/`, `test/reputation/`)
- Build: `build/<Platform>/<BuildType>/` (e.g., `build/OSX/Debug/`)

**Namespaces:**
- Top-level: `sgns::neoswarm`
- Sub-namespaces map 1:1 to source directories: `sgns::neoswarm::api`, `::core`, `::fp4`, `::router`, `::specialists`, `::reputation`, `::network`, `::knowledge`, `::security`
- Proto packages: `genius.api`, `genius.internal`, `genius.reputation`

**Classes/Structs:**
- Classes: `PascalCase` (e.g., `GeniusAPIServer`, `InferenceEngine`, `RuleBasedRouter`)
- Structs/data types: `PascalCase` (e.g., `Task`, `InferenceResponse`, `NodeOutput`, `RouteDecision`)
- Abstract interfaces: Prefixed with `I` (e.g., `IRouter`, `ISpecialist`)
- PIMPL inner: `struct Impl` (used in `P2PNode`, `ReputationStorage`, `KnowledgeRetrieval`, `SentencePieceTokenizer`, `NodeIdentity`)
- Config structs: `Config` nested inside the class they configure

**Members:**
- Data members: `snake_case_` with trailing underscore (e.g., `model_path_`, `running_`, `cfg_`, `loaded_`)
- Function parameters: `snake_case` without trailing underscore (e.g., `model_path`, `max_tokens`, `pub_key_hex`)
- Constants: `kCamelCase` or `UPPER_CASE` (e.g., `kPrivKeySize`, `kMacroblockRows`, `kFP4LUT[]`, `kMinTasksForHighTrust`)
- Enums: `PascalCase` values inside `PascalCase` enums (e.g., `ExecutionMode::SingleNode`, `Error::ModelLoadFailed`)

**Functions:**
- Public methods: `PascalCase` (e.g., `Initialize()`, `LoadModel()`, `SelectWinner()`, `GetName()`)
- Private helpers: `PascalCase` (e.g., `RunSingleNode()`, `AugmentPrompt()`, `ComputeWeights()`)

## Where to Add New Code

**New Specialist (e.g., CodeSpecialist):**
- Primary code: `src/specialists/CodeSpecialist.hpp` + `src/specialists/CodeSpecialist.cpp`
- Register in: `src/specialists/CMakeLists.txt` (add to `genius_specialists` library)
- Route target: Add `CorePlusCode = 3` to `RouteTarget` enum in `src/common/Types.hpp`
- Router rule: Add `has_code_syntax_` check in `src/router/RuleBasedRouter.cpp`
- Orchestrator: Add `std::shared_ptr<specialists::CodeSpecialist> code_spec_` to `GeniusAPIServer.hpp`, init in `GeniusAPIServer.cpp::Initialize()`, use in `RunSpecialist()`
- Tests: `test/specialists/test_code_specialist.cpp`

**New Router Strategy (e.g., ML-based router):**
- Primary code: `src/router/MLRouter.hpp` + `src/router/MLRouter.cpp` (implement `IRouter`)
- Register in: `src/router/CMakeLists.txt`
- Swap in: Change `GeniusAPIServer::Initialize()` to construct `MLRouter` instead of `RuleBasedRouter`
- Tests: `test/router/test_ml_router.cpp`

**New Inference Engine (e.g., ONNX backend):**
- Primary code: `src/core/engine/ONNXInferenceEngine.hpp` + `src/core/engine/ONNXInferenceEngine.cpp` (implement `InferenceEngine`)
- Register in: `src/core/CMakeLists.txt`
- Swap in: Change `GeniusAPIServer::Initialize()` to construct `ONNXInferenceEngine` instead of `MNNInferenceEngine`
- Tests: `test/core/test_onnx_engine.cpp`

**New Knowledge Source:**
- Primary code: `src/knowledge/WikipediaRetrieval.hpp/.cpp` (new retriever alongside `KnowledgeRetrieval`)
- Register in: `src/knowledge/CMakeLists.txt`
- Wire in: `GeniusAPIServer::Initialize()` to create and load the new retriever

**New gRPC Service:**
- Primary code: `proto/genius_<name>.proto`
- Generated code: handled by CMake protobuf integration
- Server impl: Add service implementation class in `src/api/`

**Unit Tests for Existing Module:**
- Location: `test/<module>/test_<feature>.cpp`
- Example: For a new `SymbolicFallback` feature, add `test/specialists/test_symbolic_fallback.cpp`
- Register: Add `genius_test(...)` call in `test/CMakeLists.txt`

**Build Config for New Third-Party Dependency:**
- Location: `build/CommonBuildParameters.cmake` (find package + set include/lib paths)
- Module CMake: `src/<module>/CMakeLists.txt` (add target_link_libraries)

## Special Directories

**`build/`:**
- Purpose: Platform-specific build entry points and generated build artifacts
- Generated: Yes — `build/<Platform>/<BuildType>/` contains compiled objects, binaries, and cmake cache
- Committed: No — `.gitignore` excludes build artifacts; only `CMakeLists.txt` and cmake helpers are committed

**`thirdparty/`:**
- Purpose: Git submodule pointing to pre-built third-party libraries (MNN, Boost, libp2p, RocksDB, etc.)
- Generated: No — managed externally by the user
- Committed: As a git submodule reference

**`reputation.db/`:**
- Purpose: Default RocksDB database for reputation storage (created at runtime)
- Generated: Yes — created at runtime by `ReputationStorage`
- Committed: No — listed in `.gitignore`

**`node.key`:**
- Purpose: Hex-encoded secp256k1 private key for node identity
- Generated: Yes — created at runtime on first launch
- Committed: No — listed in `.gitignore`

**`proto/`:**
- Purpose: gRPC protocol buffer definitions
- Generated: No — source of truth for protobuf code generation
- Committed: Yes

**`docs/architecture/`:**
- Purpose: Comprehensive architecture documentation
- Generated: No — hand-written design documents
- Committed: Yes

**`.planning/`:**
- Purpose: GSD workflow planning, codebase maps, and tracking artifacts
- Generated: Yes — produced by GSD commands (`/gsd-map-codebase`, `/gsd-plan-phase`, etc.)
- Committed: Yes (by GSD workflow convention)

---

*Structure analysis: 2026-05-27*
