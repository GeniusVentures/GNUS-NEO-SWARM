# Codebase Structure

**Analysis Date:** 2026-05-26

## Directory Layout

```
GNUS-NEO-SWARM/
├── src/                          # C++ source code (the engine)
│   ├── common/                   # Shared types, errors, logging
│   ├── core/                     # Inference engine, tokenizer, FP4, SGProcessing bridge
│   │   ├── engine/               # InferenceEngine abstract + MNN implementation
│   │   ├── fp4/                  # FP4 4-bit float codec
│   │   ├── sgprocessing/         # SuperGenius processing bridge
│   │   └── tokenizer/            # SentencePiece tokenizer wrapper
│   ├── router/                   # Prompt analysis and routing
│   ├── specialists/              # Domain specialist models (Math, Grammar)
│   ├── reputation/               # Node reputation, consensus, storage
│   ├── network/                  # P2P networking, result aggregation
│   ├── security/                 # Node identity, message signing
│   ├── knowledge/                # Fact retrieval, context injection, validation
│   ├── api/                      # Orchestration layer (GeniusAPIServer)
│   ├── genius_node.cpp           # CLI entry point (binary: neo-swarm)
│   ├── genius_slm_chat_c.cpp     # C FFI for Flutter/Dart bridge
│   └── genius_slm_chat_c.h       # C FFI public header
├── proto/                        # Protocol Buffer definitions
│   ├── genius_api.proto          # Client-facing gRPC service (Infer, StreamInfer)
│   ├── genius_internal.proto     # Inter-node task/result messages
│   └── genius_reputation.proto   # Reputation CRDT sync message types
├── flutter_app/                  # Flutter frontend application
│   ├── lib/main.dart             # Main app entry (currently template scaffold)
│   ├── pubspec.yaml              # Flutter dependencies (ffi, flutter_ai_toolkit)
│   ├── test/widget_test.dart     # Widget test
│   ├── android/                  # Android platform config
│   ├── ios/                      # iOS platform config
│   ├── macos/                    # macOS platform config
│   ├── linux/                    # Linux platform config
│   └── windows/                  # Windows platform config
├── flutter_slm_bridge/           # Flutter FFI plugin bridging Dart ↔ C++ dylib
│   ├── lib/
│   │   ├── flutter_slm_bridge.dart       # Public Dart API (init, chat, extract)
│   │   ├── genius_slm_bindings_generated.dart  # dart:ffi generated bindings
│   │   └── flutter_slm_bridge_bindings_generated.dart  # Plugin platform bindings
│   ├── src/
│   │   ├── flutter_slm_bridge.c         # Native C plugin code
│   │   ├── flutter_slm_bridge.h         # Native C plugin header
│   │   └── CMakeLists.txt               # Native build for plugin
│   ├── pubspec.yaml              # Plugin pubspec (ffi, ffigen)
│   ├── ffigen.yaml               # FFI code generator config
│   ├── android/                  # Android platform FFI config
│   ├── ios/                      # iOS platform FFI config
│   ├── macos/                    # macOS platform FFI config
│   ├── linux/                    # Linux platform FFI config
│   ├── windows/                  # Windows platform FFI config
│   └── example/                  # Plugin example app
├── ui/                           # Additional Flutter UI project (chat_gnus)
│   ├── lib/                      # Dart source
│   ├── pubspec.yaml
│   └── (platform dirs)
├── test/                         # C++ test suite (Google Test)
│   ├── CMakeLists.txt            # Test build config, macro, 5 test targets
│   ├── core/test_fp4_codec.cpp
│   ├── router/test_router.cpp
│   ├── reputation/test_reputation.cpp
│   ├── integration/test_pipeline.cpp
│   └── integration/test_sgprocessing_pipeline.cpp
├── build/                        # Platform-specific build configs (CMake)
│   ├── OSX/                      # macOS build directory
│   ├── Linux/                    # Linux build config
│   ├── Windows/                  # Windows build config
│   ├── Android/                  # Android build config
│   ├── iOS/                      # iOS build config
│   ├── cmake/                    # Shared build functions
│   └── README.md                 # Build system docs
├── cmake/                        # Shared CMake modules
│   ├── CommonBuildParameters.cmake
│   ├── CompilationFlags.cmake
│   ├── config.cmake.in
│   └── functions.cmake
├── cmake_genius/                 # CMake module: thirdparty discovery
│   └── FindThirdparty.cmake
├── docs/                         # Architecture and design documentation
│   ├── architecture/             # 15 architecture docs (executive summary, model, consensus, etc.)
│   ├── gnus_llm_tech_spec.md
│   └── (various design docs)
├── AgentDocs/                    # Agent-facing development docs
│   ├── PLAN.md                   # Phased implementation plan
│   ├── CHECKPOINT.md             # Current implementation checkpoint
│   └── PRODUCTION_ROADMAP.md     # Task list for production readiness
├── gnus-poc/                     # Python POC scripts
│   ├── data/                     # Test and training data
│   ├── models/                   # Model files
│   └── .venv/                    # Python virtual environment
├── CMakeLists.txt                # Root build file — defines all targets
├── README.md                     # Project overview, build instructions
├── RUN_AND_DEPLOY.md             # Run, deploy, and CLI reference guide
├── CLAUDE.md                     # AI agent development instructions & coding standards
├── .gitignore                    # Git ignore rules
└── .gitmodules                   # Submodule config
```

## Directory Purposes

**`src/`:**
- Purpose: All C++17 engine source code. The core of the GNUS NEO SWARM system.
- Contains: Header and implementation files organized by subsystem module. Each module builds to a static library.
- Key files: `genius_node.cpp` (CLI entry), `genius_slm_chat_c.h` (FFI header), `api/GeniusAPIServer.hpp` (orchestrator)

**`src/common/`:**
- Purpose: Foundation layer — shared types, error codes, logging. No subsystem dependencies.
- Contains: `Types.hpp`, `Error.hpp`, `Logging.hpp`, `Error.cpp`
- Key files: `Types.hpp` (all data types: Task, GeniusResponse, RouteDecision, etc.), `Error.hpp` (17 error codes, outcome alias)
- Build target: `genius_common` (static library)

**`src/core/`:**
- Purpose: Inference engine and model support — the computational heavy lifting.
- Contains: `engine/` (InferenceEngine + MNNInferenceEngine), `fp4/` (4-bit float codec), `tokenizer/` (SentencePiece), `sgprocessing/` (SuperGenius bridge)
- Key files: `engine/InferenceEngine.hpp` (abstract interface), `engine/MNNInferenceEngine.cpp` (MNN backend with stub fallback)
- Build target: `genius_core` (static library)

**`src/router/`:**
- Purpose: Prompt classification and routing decisions. Analyzes input and selects CoreOnly, CorePlusMath, or CorePlusGrammar.
- Contains: `IRouter.hpp`, `RuleBasedRouter.cpp/.hpp`, `PromptAnalyzer.cpp/.hpp`
- Build target: `genius_router` (static library)

**`src/specialists/`:**
- Purpose: Domain-specific post-processing models that refine core LLM output.
- Contains: `ISpecialist.hpp`, `MathSpecialist`, `GrammarSpecialist`, `SymbolicFallback`
- Build target: `genius_specialists` (static library)

**`src/reputation/`:**
- Purpose: Swarm node reputation management — scoring, weighted consensus, CRDT sync, RocksDB persistence.
- Contains: `NodeReputation.hpp`, `ReputationScoring`, `WeightedConsensus`, `ReputationStorage`, `ReputationCRDT`
- Build target: `genius_reputation` (static library)

**`src/network/`:**
- Purpose: P2P networking via libp2p, inter-node task broadcast, result aggregation.
- Contains: `P2PNode`, `ResultAggregation`
- Build target: `genius_network` (static library)

**`src/security/`:**
- Purpose: Cryptographic identity and message authentication for swarm nodes.
- Contains: `NodeIdentity`, `MessageSigning`
- Build target: `genius_security` (static library)

**`src/knowledge/`:**
- Purpose: External knowledge grounding — fact retrieval from Grokipedia CSV, context injection, output validation.
- Contains: `KnowledgeRetrieval`, `ContextInjection`, `FactValidation`
- Build target: `genius_knowledge` (static library)

**`src/api/`:**
- Purpose: Top-level orchestrator that composes all subsystems into a coherent inference pipeline.
- Contains: `GeniusAPIServer`
- Build target: `genius_api` (static library) — links to all other `genius_*` libraries

**`flutter_app/`:**
- Purpose: Flutter desktop/mobile frontend application for end-user chat interface.
- Contains: `lib/main.dart` (currently template scaffold), platform configs
- Key files: `pubspec.yaml` (depends on `ffi`, `flutter_ai_toolkit`)

**`flutter_slm_bridge/`:**
- Purpose: Flutter FFI plugin that bridges Dart code to the native C++ shared library (`Genius-MOS-SLM-FFI.dylib`).
- Contains: Generated dart:ffi bindings, platform-specific native code, public Dart API
- Key files: `lib/flutter_slm_bridge.dart` (public API: `geniusSlmInit()`, `chatCompletionsCreate()`), `lib/genius_slm_bindings_generated.dart` (FFI bindings)

**`proto/`:**
- Purpose: Protocol Buffer schema definitions for gRPC services and inter-node messaging.
- Contains: `genius_api.proto`, `genius_internal.proto`, `genius_reputation.proto`
- Build target: `genius_proto` (static library, generated from `.proto` files when Protobuf is found)

**`test/`:**
- Purpose: C++ unit and integration tests using Google Test.
- Contains: 5 test files covering fp4 codec, router, reputation, pipeline integration, SGProcessing pipeline
- Build target: Individual test executables registered via `genius_test()` macro

**`build/`:**
- Purpose: Platform-specific CMake build directories. Each platform has its own `CMakeLists.txt` that points back to `src/`.
- Generated: Yes (build artifacts)
- Committed: Partially — build config CMakeLists.txt files are committed; build artifacts (Debug/Release/) are not

**`docs/`:**
- Purpose: Architecture documentation, tech specs, design documents. 15 architecture docs in `docs/architecture/`.
- Contains: Markdown and docx files covering system design, model architecture, reputation, grounding, security, AI safety

**`AgentDocs/`:**
- Purpose: AI agent-facing development documentation — plans, checkpoints, production roadmap.
- Contains: `PLAN.md`, `CHECKPOINT.md`, `PRODUCTION_ROADMAP.md`
- Key: `PRODUCTION_ROADMAP.md` is the master task list for bringing the prototype to production

**`cmake/` and `cmake_genius/`:**
- Purpose: Shared CMake modules for build parameters, compiler flags, and thirdparty library discovery.
- Key files: `cmake_genius/FindThirdparty.cmake` (locates MNN, boost, spdlog, RocksDB, etc.)

**`gnus-poc/`:**
- Purpose: Python proof-of-concept scripts for data analysis and specialist model experiments.
- Contains: `data/`, `models/`, `.venv/`

## Key File Locations

**Entry Points:**
- `src/genius_node.cpp`: CLI binary entry (`neo-swarm`) — REPL, single-prompt, `--serve` modes
- `src/genius_slm_chat_c.cpp`: C FFI entry — `GeniusSlmInit()`, `GeniusSlmChatCompletionsCreate()`, `GeniusSlmStringFree()`
- `src/genius_slm_chat_c.h`: Public C FFI header — defines `GENIUS_SLM_CHAT_C_API` export macros
- `flutter_app/lib/main.dart`: Flutter app entry (currently template — not yet wired to FFI)

**Configuration:**
- `CMakeLists.txt`: Root project definition, build options (`GENIUS_BUILD_TESTS`, `GENIUS_ENABLE_GPU`, etc.), target declarations
- `cmake/CommonBuildParameters.cmake`: Shared build parameters across platforms
- `cmake/CompilationFlags.cmake`: Compiler warnings, optimization flags
- `cmake_genius/FindThirdparty.cmake`: Thirdparty library discovery module
- `flutter_app/pubspec.yaml`: Flutter app dependencies
- `flutter_slm_bridge/pubspec.yaml`: FFI plugin dependencies
- `flutter_slm_bridge/ffigen.yaml`: FFI code generator configuration

**Core Logic:**
- `src/api/GeniusAPIServer.hpp`: Central orchestrator — all pipeline modes
- `src/common/Types.hpp`: All shared data structures
- `src/core/engine/InferenceEngine.hpp`: Abstract inference interface
- `src/router/IRouter.hpp`: Abstract routing interface
- `src/specialists/ISpecialist.hpp`: Abstract specialist interface

**Testing:**
- `test/CMakeLists.txt`: Test build config with `genius_test()` macro
- `test/core/test_fp4_codec.cpp`: FP4 encode/decode unit test
- `test/router/test_router.cpp`: Prompt analysis and routing unit test
- `test/reputation/test_reputation.cpp`: Reputation scoring and consensus test
- `test/integration/test_pipeline.cpp`: End-to-end pipeline integration test
- `test/integration/test_sgprocessing_pipeline.cpp`: SGProcessing pipeline integration test

**Documentation:**
- `README.md`: Project overview, build instructions
- `RUN_AND_DEPLOY.md`: Complete run/deploy guide with all CLI flags
- `CLAUDE.md`: AI agent coding standards (276 lines of C++ rules)
- `AgentDocs/PRODUCTION_ROADMAP.md`: 22 tasks for production readiness
- `docs/architecture/INDEX.md`: Architecture documentation index

**Figma / Design:**
- `docs/architecture/`: 15 architecture design documents
- `docs/Chat Genius - MVP.docx`: MVP design spec

## Naming Conventions

**Files:**
- PascalCase for class files: `GeniusAPIServer.cpp`, `GeniusAPIServer.hpp`, `RuleBasedRouter.hpp`
- Interface files prefixed with `I`: `IRouter.hpp`, `ISpecialist.hpp`
- Lowercase with underscores for non-class files: `genius_node.cpp`, `genius_slm_chat_c.cpp`
- Test files: `test_<component>.cpp` (e.g., `test_fp4_codec.cpp`, `test_router.cpp`)

**Directories:**
- Lowercase with underscores for multi-word: `flutter_app/`, `flutter_slm_bridge/`, `gnus-poc/`
- Single lowercase word for modules: `core/`, `router/`, `api/`, `common/`
- Build config directories use Platform capitalization: `OSX/`, `Linux/`, `Windows/`, `Android/`, `iOS/`

**Code level (across all C++ files):**
- Classes/Methods: PascalCase (e.g., `GeniusAPIServer`, `Process`, `Initialize`)
- Variables: camelCase (e.g., `modelPath`, `numericDensity`)
- Constants: ALL_CAPS (e.g., `kMinTasksForHighTrust`, `GENIUS_HAS_MNN`)
- Namespaces: `sgns::neoswarm::<module>` (nested, full indentation)
- Build targets: `genius_<module>` (e.g., `genius_core`, `genius_router`)
- Binary target: `neo-swarm`
- FFI library target: `Genius-MOS-SLM-FFI`

**Proto files:**
- `genius_<domain>.proto` (e.g., `genius_api.proto`, `genius_reputation.proto`)

**Dart files (Flutter):**
- Lowercase with underscores: `flutter_slm_bridge.dart`, `genius_slm_bindings_generated.dart`

## Where to Add New Code

**New specialist model (e.g., CodeSpecialist):**
- Primary code: `src/specialists/CodeSpecialist.cpp`, `CodeSpecialist.hpp`
- Interface: Implement `ISpecialist` from `src/specialists/ISpecialist.hpp`
- Register in: `src/api/GeniusAPIServer.cpp` (add member, initialize, wire in `RunSpecialist()`)
- Build: Add to `src/specialists/CMakeLists.txt`
- Router update: Add `CorePlusCode` to `RouteTarget` enum in `src/common/Types.hpp`
- Tests: `test/specialists/test_code_specialist.cpp`

**New routing strategy (e.g., ML-based router):**
- Implementation: `src/router/MLRouter.cpp`, `MLRouter.hpp`
- Interface: Implement `IRouter` from `src/router/IRouter.hpp`
- Build: Add to `src/router/CMakeLists.txt`
- Tests: `test/router/test_ml_router.cpp`

**New subsystem module (e.g., caching):**
- Directory: `src/cache/`
- Build: `src/cache/CMakeLists.txt` → `genius_cache` static library
- Wire into: `src/api/GeniusAPIServer.hpp` (add `std::unique_ptr` member)
- Link in: `src/api/CMakeLists.txt` (add `genius_cache` to dependencies)
- Tests: `test/cache/`

**New gRPC service:**
- Proto: `proto/genius_<service>.proto`
- Generated: Automatically built into `genius_proto` library
- Server-side: Add to `src/api/GeniusAPIServer.cpp`

**Flutter UI feature:**
- Widget code: `flutter_app/lib/` (add new `.dart` files or modify `main.dart`)
- Tests: `flutter_app/test/`
- If it needs native C++: Wire through existing `flutter_slm_bridge` or extend the FFI surface in `src/genius_slm_chat_c.cpp`/`.h`

## Special Directories

**`build/`:**
- Purpose: Platform-specific CMake build configurations. Build artifacts (`Debug/`, `Release/`, `RelWithDebInfo/`) are generated here.
- Generated: Yes (build artifacts) / Partially committed (CMakeLists.txt configs)
- Committed: Platform CMakeLists.txt files are committed; build outputs are not

**`gnus-poc/.venv/` and `gnus-poc/data/` and `gnus-poc/models/`:**
- Purpose: Python virtual environment, data, and model files for proof-of-concept experiments
- Generated: Yes (.venv, some data)
- Committed: Partially — `.venv` is gitignored; data and models partially committed

**`ui/build/`:**
- Purpose: Flutter build artifacts for the secondary `ui/` project
- Generated: Yes
- Committed: No

**`.idea/`:**
- Purpose: JetBrains IDE project settings
- Generated: Yes
- Committed: Yes

---

*Structure analysis: 2026-05-26*
