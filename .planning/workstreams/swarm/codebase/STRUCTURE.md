# Codebase Structure

**Analysis Date:** 2026-06-17

## Directory Layout

```
GNUS-NEO-SWARM/
├── src/                          # C++ source — the core engine library
│   ├── main.cpp                  #   CLI entry point (neo-swarm binary)
│   ├── genius_elm_chat_completions.h   #   C FFI header (Flutter/Dart bridge)
│   ├── genius_elm_chat_completions.cpp #   C FFI implementation
│   ├── genius_elm_chat_c.cpp     #   FFI stub implementation
│   ├── api/                      #   Orchestration / API server layer
│   ├── common/                   #   Shared types, errors, logging
│   ├── core/                     #   Inference engine, tokenizer, quantization, SGProcessing
│   │   ├── engine/               #     MNN inference engine
│   │   ├── fp4/                  #     FP4 quantization codec
│   │   ├── sgprocessing/         #     SGProcessing bridge and tensor interpreter
│   │   └── tokenizer/            #     SentencePiece tokenizer
│   ├── knowledge/                #   Grokipedia retrieval, context injection, fact validation
│   ├── network/                  #   P2P networking (libp2p), result aggregation, SG client
│   │   └── sg_client/            #     SuperGenius blockchain client (channel, job, result, auth)
│   ├── reputation/               #   Scoring, consensus, storage, CRDT sync
│   ├── router/                   #   Prompt analysis and rule-based routing
│   ├── security/                 #   Node identity, message signing
│   └── specialists/              #   Grammar and math specialist models
├── test/                         # Unit, integration, and benchmark tests
│   ├── CMakeLists.txt            #   Test build config (GTest)
│   ├── core/                     #   Core unit tests (fp4 codec)
│   ├── ffi/                      #   FFI bridge tests
│   ├── integration/              #   Pipeline integration tests
│   ├── knowledge/                #   Knowledge retrieval tests
│   ├── network/                  #   Network tests
│   ├── reputation/               #   Reputation unit tests
│   ├── router/                   #   Router unit tests
│   ├── security/                 #   Security tests (identity, signing)
│   ├── specialists/              #   Specialist tests (grammar, math)
│   └── benchmark/                #   MNN LLM benchmarks (manual, not CTest)
├── proto/                        # gRPC protocol buffer definitions
│   ├── genius_api.proto          #   Client-facing API (Infer, StreamInfer, GetNodeStatus)
│   ├── genius_internal.proto     #   Inter-node messages (TaskMessage, ResultMessage)
│   └── genius_reputation.proto   #   Reputation sync (NodeReputationProto)
├── build/                        # Platform-specific build directories (git submodule)
│   ├── OSX/                      #   macOS builds
│   ├── Linux/                    #   Linux builds
│   ├── Windows/                  #   Windows builds
│   ├── Android/                  #   Android builds
│   ├── iOS/                      #   iOS builds
│   └── cmake/                    #   Shared cmake helpers
│       ├── functions.cmake       #     Helper functions
│       ├── definition.cmake      #     Build definitions
│       ├── install.cmake         #     Install rules
│       ├── print.cmake           #     Print utilities
│       └── toolchain/            #     Toolchain files (cxx17.cmake)
├── cmake/                        # Project-level cmake config
│   └── CommonBuildParameters.cmake   # All thirdparty dependency configuration (389 lines)
├── docs/                         # Technical documentation
├── flutter_app/                  # Flutter frontend app (Dart)
├── flutter_slm_bridge/           # Flutter native bridge plugin (FFI bindings)
├── ui/                           # Chat Genius Flutter UI project
├── gnus-poc/                     # Python ML training/distillation pipeline
│   ├── config/                   #   Configuration files
│   ├── data/                     #   Datasets and analysis
│   ├── distill/                  #   Knowledge distillation
│   ├── eval/                     #   Evaluation scripts
│   ├── models/                   #   Specialist model artifacts (MLX)
│   ├── pipeline/                 #   Training pipeline runner
│   ├── quantize/                 #   FP4 quantization and export
│   ├── tests/                    #   Python tests (pytest)
│   └── training/                 #   Model training (MLX, PyTorch)
├── scripts/                      # Build/dev scripts
│   ├── install-hooks.sh          #   Git hook installation
│   └── pre-commit-lint.sh        #   Pre-commit lint script
├── AgentDocs/                    # Agent planning documents
│   ├── CHECKPOINT.md             #   Current development checkpoint
│   ├── PLAN.md                   #   Project plan
│   └── PRODUCTION_ROADMAP.md     #   Production readiness roadmap
├── .planning/                    # GSD planning directory
│   ├── codebase/                 #   Codebase analysis documents (this file)
│   ├── phases/                   #   Phase planning
│   └── research/                 #   Research notes
├── .claude/                      # Claude skill configuration
├── .gitignore                    # Git ignore rules
├── .gitmodules                   # Git submodule definitions
├── .clang-format                 # Code formatting rules (Microsoft base, 120-col, Allman)
├── .clang-tidy                   # Static analysis rules
├── CLAUDE.md                     # AI development guide
├── README.md                     # Project overview and build instructions
└── RUN_AND_DEPLOY.md             # Run and deploy instructions
```

## Directory Purposes

**`src/`:**
- Purpose: All C++17 source code for the GNUS NEO SWARM engine and its subsystems
- Contains: `.hpp` headers, `.cpp` implementations, per-directory `CMakeLists.txt` files
- Key files: `main.cpp` (CLI entry), `genius_elm_chat_completions.h/.cpp` (FFI), `api/api_server.hpp/.cpp` (orchestrator)

**`src/api/`:**
- Purpose: The top-level orchestration layer -- `ApiServer` initialises and coordinates all subsystems
- Contains: `api_server.hpp`, `api_server.cpp`, `CMakeLists.txt` (builds `neoswarm_api` library)
- Key files: `api_server.hpp` (class definition with all component members), `api_server.cpp` (504 lines -- init, process, three execution modes, serve, stop)

**`src/common/`:**
- Purpose: Foundation types, error handling, and logging used by every other module
- Contains: `types.hpp` (all data structs), `error.hpp` (error enum + outcome alias), `error.cpp`, `logging.hpp` (spdlog factory), `CMakeLists.txt`
- Key files: `types.hpp` (defines `Task`, `InferenceResponse`, `RouteDecision`, `NodeOutput`, `NodeReputation`, `PromptFeatures`, `KnowledgeFact`)

**`src/core/`:**
- Purpose: LLM inference engine, tokenization, FP4 quantization, and SGProcessing bridge
- Contains: Four subdirectories -- `engine/`, `tokenizer/`, `fp4/`, `sgprocessing/`. Builds `neoswarm_core` static library.
- Key files: `engine/mnn_inference_engine.hpp` (dual inference paths), `engine/inference_engine.hpp` (abstract interface), `tokenizer/tokenizer.hpp` (abstract + SentencePiece impl), `fp4/fp4_codec.hpp` (4-bit quantization), `sgprocessing/sg_processing_bridge.hpp` (bridges to SuperGenius)

**`src/router/`:**
- Purpose: Prompt analysis and rule-based routing to select execution mode
- Contains: `i_router.hpp` (abstract interface), `prompt_analyzer.hpp/.cpp` (feature extraction), `rule_based_router.hpp/.cpp` (decision tree), `CMakeLists.txt`
- Key files: `rule_based_router.hpp` (threshold-based routing: numeric_density -> Math, grammar_request -> Grammar, else -> CoreOnly)

**`src/specialists/`:**
- Purpose: Domain-specific post-processing models for grammar and math
- Contains: `i_specialist.hpp` (abstract interface), `grammar_specialist.hpp/.cpp`, `math_specialist.hpp/.cpp`, `symbolic_fallback.hpp/.cpp`, `CMakeLists.txt`
- Key files: `math_specialist.hpp` (uses shared `InferenceEngine`, includes symbolic fallback when confidence < 0.6)

**`src/reputation/`:**
- Purpose: Node reputation computation, consensus selection, persistent storage, and CRDT-based sync
- Contains: `node_reputation.hpp` (type), `reputation_scoring.hpp/.cpp`, `weighted_consensus.hpp/.cpp`, `reputation_storage.hpp/.cpp`, `reputation_crdt.hpp/.cpp`, `CMakeLists.txt`
- Key files: `reputation_scoring.hpp` (4-component update: accuracy, latency, consistency, consensus), `weighted_consensus.hpp` (2 strategies: WeightedVoting, BestWeightedScore)

**`src/network/`:**
- Purpose: P2P communication via libp2p and SuperGenius blockchain compute network client
- Contains: `p2p_node.hpp/.cpp` (libp2p host), `result_aggregation.hpp/.cpp` (timeout-bounded collector), `sg_client/` sub-directory, `CMakeLists.txt`
- Key files: `p2p_node.hpp` (GossipSub broadcast, Noise encryption, Yamux multiplexing), `sg_client/super_genius_client.hpp` (PubSub gRPC dispatch)

**`src/network/sg_client/`:**
- Purpose: SuperGenius blockchain compute network client (decomposed into sub-components)
- Contains: `super_genius_client.hpp/.cpp` (facade), `sg_channel_manager.hpp/.cpp`, `sg_job_submitter.hpp/.cpp`, `sg_result_collector.hpp/.cpp`, `sg_message_authenticator.hpp/.cpp`
- Key files: `super_genius_client.hpp` (PImpl pattern, owns sub-components)

**`src/knowledge/`:**
- Purpose: Grokipedia knowledge retrieval, prompt augmentation, and post-generation fact validation
- Contains: `knowledge_retrieval.hpp/.cpp`, `context_injection.hpp/.cpp`, `fact_validation.hpp/.cpp`, `CMakeLists.txt`
- Key files: `knowledge_retrieval.hpp` (TF-IDF bag-of-words + cosine similarity), `fact_validation.hpp` (numeric claim extraction + contradiction detection)

**`src/security/`:**
- Purpose: Node identity management and inter-node message signing
- Contains: `node_identity.hpp/.cpp` (secp256k1 keypair), `message_signing.hpp/.cpp` (sign/verify), `CMakeLists.txt`
- Key files: `node_identity.hpp` (PImpl pattern, AES-256-GCM encrypted storage, PeerId derivation)

**`test/`:**
- Purpose: Unit, integration, and benchmark tests using Google Test
- Contains: `CMakeLists.txt` (defines `neoswarm_test` macro), per-module subdirectories mirroring `src/`
- Key files: `CMakeLists.txt` (12 test targets + 1 benchmark subtarget)

**`proto/`:**
- Purpose: gRPC service definitions for client API, inter-node messaging, and reputation sync
- Contains: `genius_api.proto` (60 lines), `genius_internal.proto` (25 lines), `genius_reputation.proto` (23 lines)
- Key files: `genius_api.proto` (defines `GeniusAPI` service with `Infer`, `StreamInfer`, `GetNodeStatus`)

**`build/`:**
- Purpose: Platform-specific CMake entry points and build artifacts
- Contains: `OSX/`, `Linux/`, `Windows/`, `Android/`, `iOS/` directories; shared cmake modules in `build/cmake/`
- Key files: `cmake/CommonBuildParameters.cmake` (referenced from platform CMakeLists), `cmake/toolchain/cxx17.cmake`

**`cmake/`:**
- Purpose: Project-level cmake configuration
- Contains: `CommonBuildParameters.cmake` (389 lines, configures all thirdparty dependencies)
- Key files: `CommonBuildParameters.cmake` (the central dependency configuration file)

**`gnus-poc/`:**
- Purpose: Python ML training and distillation pipeline for specialist models
- Contains: `training/` (MLX/PyTorch training), `distill/` (knowledge distillation), `quantize/` (FP4 export), `eval/` (evaluation), `pipeline/` (runner), `tests/` (pytest), `config/`, `data/`, `models/`
- Key files: `pyproject.toml` (project config), `requirements.txt` (dependencies), `training/train_specialists_mlx.py` (Apple Silicon training)

**`scripts/`:**
- Purpose: Build and development scripts
- Contains: `install-hooks.sh`, `pre-commit-lint.sh`

**`AgentDocs/`:**
- Purpose: AI agent planning documents -- checkpoint, project board, roadmap
- Contains: `CHECKPOINT.md`, `PLAN.md`, `PRODUCTION_ROADMAP.md`

**`docs/`:**
- Purpose: Technical documentation, architecture specs, patent drafts
- Contains: `ARCHITECTURE.md`, `CONFIGURATION.md`, `DEVELOPMENT.md`, `TESTING.md`, `GETTING-STARTED.md`, FP4 patent docs, protocol specs

## Key File Locations

**Entry Points:**
- `src/main.cpp`: CLI entry -- main function, argument parsing, interactive REPL, JSON config loading
- `src/genius_elm_chat_completions.h`: C FFI entry -- exported C functions for Flutter integration
- `src/genius_elm_chat_completions.cpp`: FFI stub implementation

**Configuration:**
- `cmake/CommonBuildParameters.cmake`: All third-party dependency configuration (MNN, Vulkan, libp2p, RocksDB, etc.)
- `build/<Platform>/CMakeLists.txt`: Platform-specific build config
- `.clang-format`: Formatting rules (Microsoft base, 120-col, Allman braces, 4-space indent)
- `.clang-tidy`: Static analysis checks and naming conventions

**Core Logic:**
- `src/api/api_server.cpp`: The orchestrator -- initialisation sequence (10 subsystems), three execution mode implementations
- `src/core/engine/mnn_inference_engine.cpp`: The inference engine -- dual-path (interpreter + SGProcessing), Vulkan GPU dispatch
- `src/router/rule_based_router.cpp`: Routing decision tree using `PromptAnalyzer` features
- `src/reputation/reputation_scoring.cpp`: Reputation update mathematics
- `src/reputation/weighted_consensus.cpp`: Swarm consensus winner selection
- `src/network/sg_client/super_genius_client.cpp`: SuperGenius blockchain network client

**Shared Types:**
- `src/common/types.hpp`: All data structures used across the codebase
- `src/common/error.hpp`: Error enum (17 codes) and `outcome::result` alias

**Testing:**
- `test/CMakeLists.txt`: Test definitions using `neoswarm_test` macro
- `test/core/test_fp4_codec.cpp`: FP4 quantization/roundtrip tests
- `test/router/test_router.cpp`: Prompt routing tests
- `test/reputation/test_reputation.cpp`: Reputation scoring/storage tests
- `test/integration/test_pipeline.cpp`: End-to-end pipeline tests
- `test/security/test_node_identity.cpp`: Node identity key generation, sign/verify, encrypted save/load
- `test/security/test_message_signing.cpp`: Message signing tests
- `test/specialists/test_math_specialist.cpp`: Math specialist tests
- `test/specialists/test_grammar_specialist.cpp`: Grammar specialist tests

**Protocol:**
- `proto/genius_api.proto`: Client gRPC service definition
- `proto/genius_internal.proto`: Inter-node broadcast messages
- `proto/genius_reputation.proto`: Reputation sync data types

## Naming Conventions

**Files (snake_case -- SuperGenius convention):**
- Header files: `snake_case.hpp` (e.g., `api_server.hpp`, `inference_engine.hpp`, `node_identity.hpp`)
- Source files: `snake_case.cpp` (e.g., `api_server.cpp`, `weighted_consensus.cpp`)
- CMake: `CMakeLists.txt` (standard CMake naming)
- Test files: `test_<snake_case>.cpp` (e.g., `test_fp4_codec.cpp`, `test_router.cpp`, `test_pipeline.cpp`)
- Proto files: `snake_case.proto` (e.g., `genius_api.proto`, `genius_internal.proto`)
- Python files: `snake_case.py` (e.g., `train_specialists.py`, `fp4_exporter.py`)

**Directories (snake_case):**
- Source modules: `snake_case` lowercase (e.g., `api/`, `core/`, `router/`, `knowledge/`, `sg_client/`)
- Source subdirectories: `snake_case` (e.g., `core/engine/`, `core/fp4/`, `core/tokenizer/`)
- Test modules: mirror source structure (e.g., `test/core/`, `test/router/`, `test/security/`)
- Build: `build/<Platform>/<BuildType>/` (e.g., `build/OSX/Debug/`)

**Namespaces:**
- Top-level: `sgns::neoswarm`
- Sub-namespaces map 1:1 to source directories: `sgns::neoswarm::api`, `::core`, `::router`, `::specialists`, `::reputation`, `::network`, `::knowledge`, `::security`
- Proto packages: `genius.api`, `genius.internal`, `genius.reputation`

**Classes/Structs (PascalCase):**
- Classes: `PascalCase` (e.g., `ApiServer`, `InferenceEngine`, `RuleBasedRouter`, `MNNInferenceEngine`)
- Abstract interfaces: Prefixed with `I` (e.g., `IRouter`, `ISpecialist`)
- Structs/data types: `PascalCase` (e.g., `Task`, `InferenceResponse`, `NodeOutput`, `RouteDecision`)
- PIMPL inner: `struct Impl` (used in `SuperGeniusClient`, `P2PNode`, `NodeIdentity`, `ReputationStorage`, `MNNInferenceEngine`)
- Config structs: `Config` nested inside the class they configure

**Members (m_ prefix + camelCase):**
- Data members: `m_camelCase` prefix (e.g., `m_modelPath`, `m_running`, `m_cfg`, `m_loaded`, `m_identity`, `m_coreEngine`)
- Some legacy members use `snake_case_` trailing underscore (e.g., `running_`, `open_`, `db_path_` in `ReputationStorage`)
- Constants: `kCamelCase` prefix (e.g., `kPrivKeySize`, `kPubKeySize`, `kPeerIdSize`, `kMinTasksForHighTrust`, `kDefaultMaxTokens`)
- Enums: `PascalCase` values inside `PascalCase` enums (e.g., `ExecutionMode::SingleNode`, `Error::ModelLoadFailed`)

**Functions (PascalCase):**
- Public methods: `PascalCase` (e.g., `Initialize()`, `LoadModel()`, `SelectWinner()`, `GetName()`, `Process()`)
- Private helpers: `PascalCase` (e.g., `RunSingleNode()`, `AugmentPrompt()`)

**Accessors:**
- Get prefix: `GetPeerId()`, `GetName()`, `GetConfidence()`
- Set prefix: `SetTokenizer()`, `SetStubMode()`, `SetSuperGeniusClient()`
- Is prefix: `IsLoaded()`, `IsRunning()`, `IsConnected()`, `IsOpen()`, `IsAvailable()`

**Library names (CMake):**
- Pattern: `neoswarm_` prefix + snake_case (e.g., `neoswarm_core`, `neoswarm_security`, `neoswarm_api`)

## Where to Add New Code

**New Specialist (e.g., CodeSpecialist):**
- Primary code: `src/specialists/code_specialist.hpp` + `src/specialists/code_specialist.cpp`
- Interface: Implement `src/specialists/i_specialist.hpp`
- Register in: `src/specialists/CMakeLists.txt` (add to `neoswarm_specialists` library)
- Route target: Add `CorePlusCode = 3` to `RouteTarget` enum in `src/common/types.hpp`
- Router rule: Add code syntax check in `src/router/rule_based_router.cpp`
- Orchestrator: Add `std::shared_ptr<specialists::CodeSpecialist> m_codeSpec` to `api_server.hpp`, init in `api_server.cpp::Initialize()`, use in `RunSpecialist()`
- Tests: `test/specialists/test_code_specialist.cpp`, register in `test/CMakeLists.txt`

**New Router Strategy (e.g., ML-based router):**
- Primary code: `src/router/ml_router.hpp` + `src/router/ml_router.cpp` (implement `IRouter`)
- Register in: `src/router/CMakeLists.txt`
- Swap in: Change `ApiServer::Initialize()` to construct `MLRouter` instead of `RuleBasedRouter`
- Tests: `test/router/test_ml_router.cpp`

**New Inference Engine (e.g., ONNX backend):**
- Primary code: `src/core/engine/onnx_inference_engine.hpp` + `src/core/engine/onnx_inference_engine.cpp` (implement `InferenceEngine`)
- Register in: `src/core/CMakeLists.txt`
- Swap in: Change `ApiServer::Initialize()` to construct `ONNXInferenceEngine` instead of `MNNInferenceEngine`
- Tests: `test/core/test_onnx_engine.cpp`

**New Knowledge Source:**
- Primary code: `src/knowledge/wikipedia_retrieval.hpp/.cpp` (new retriever alongside `KnowledgeRetrieval`)
- Register in: `src/knowledge/CMakeLists.txt`
- Wire in: `ApiServer::Initialize()` to create and load the new retriever

**New gRPC Service:**
- Primary code: `proto/genius_<name>.proto`
- Generated code: handled by CMake protobuf integration
- Server impl: Add service implementation class in `src/api/`

**Unit Tests for Existing Module:**
- Location: `test/<module>/test_<feature>.cpp`
- Register: Add `neoswarm_test(...)` call in `test/CMakeLists.txt`
- Pattern: Use GTest with `TEST(SuiteName, TestName)`, use `outcome::result` assertions

**Build Config for New Third-Party Dependency:**
- Location: `cmake/CommonBuildParameters.cmake` (find package + set include/lib paths)
- Module CMake: `src/<module>/CMakeLists.txt` (add target_link_libraries)

## Special Directories

**`build/`:**
- Purpose: Platform-specific build entry points and generated build artifacts
- Generated: Yes -- `build/<Platform>/<BuildType>/` contains compiled objects, binaries, and cmake cache
- Committed: Only `CMakeLists.txt` and cmake helpers; build artifacts are gitignored

**`thirdparty/`:**
- Purpose: Pre-built third-party libraries (managed externally)
- Generated: No -- managed by user
- Committed: Not present in this repo (expected at sibling path)

**`gnus-poc/`:**
- Purpose: Python ML training and distillation pipeline
- Generated: No -- source code
- Committed: Yes
- Key: `pyproject.toml`, `requirements.txt`, `tests/` (pytest), `training/` (MLX/PyTorch)

**`reputation.db/`:**
- Purpose: Default RocksDB database for reputation storage (created at runtime)
- Generated: Yes -- created at runtime by `ReputationStorage`
- Committed: No -- listed in `.gitignore`

**`node.key`:**
- Purpose: Encrypted secp256k1 private key for node identity
- Generated: Yes -- created at runtime on first launch
- Committed: No -- listed in `.gitignore`

**`proto/`:**
- Purpose: gRPC protocol buffer definitions
- Generated: No -- source of truth for protobuf code generation
- Committed: Yes

**`.planning/`:**
- Purpose: GSD workflow planning, codebase maps, and tracking artifacts
- Generated: Yes -- produced by GSD commands
- Committed: Yes (by GSD workflow convention)

---

*Structure analysis: 2026-06-17*
