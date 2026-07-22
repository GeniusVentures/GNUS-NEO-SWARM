# Technology Stack

**Analysis Date:** 2026-06-17

## Languages

**Primary:**
- C++17 — Full project core (`src/`, `test/`), all inference, routing, networking, security, and API layers
  - Standard: `CMAKE_CXX_STANDARD 17`, extensions OFF (enforced in `build/cmake/toolchain/cxx17.cmake`)
  - Target features: `cxx_std_17` (set in `src/common/CMakeLists.txt:12`)

**Secondary:**
- C — C-compatible FFI exports for Flutter bridge (`src/genius_elm_chat_completions.h`, `src/genius_elm_chat_completions.cpp`)
- Dart 3.x — Flutter UI applications and FFI bridge package
  - `ui/pubspec.yaml`, `flutter_app/pubspec.yaml`, `flutter_slm_bridge/pubspec.yaml`
- Python 3.10+ — ML training/distillation pipeline (`gnus-poc/`)
  - Requires: `>=3.10` (set in `gnus-poc/pyproject.toml`)

## Runtime

**Environment:**
- Clang / AppleClang / GCC (cross-platform C++17 compiler required)
- Native binaries — no managed runtime or VM for the core engine

**Package Manager:**
- CMake 3.16+ with Ninja generator
- Pre-built thirdparty dependencies from `thirdparty/build/<Platform>/<BuildType>/` (managed externally)
- Flutter/Dart packages via `pubspec.yaml` (standard `flutter pub get`)
- Python: pip with `gnus-poc/requirements.txt`, build via `setuptools>=68.0` (`gnus-poc/pyproject.toml`)
- Git submodules: `build/` (submodule pointing to `../cmaketemplate.git`) — `.gitmodules`

## Frameworks

**Core:**
- No application framework — raw C++17 with modular static library architecture
- Boost 1.85.0 — foundational utility: filesystem, program_options, outcome (error handling), thread, log

**Testing:**
- Google Test 1.x (gtest + gmock) — `test/CMakeLists.txt` via `find_package(GTest)`
  - Test binary pattern: `add_executable(test_{component})` with `GTest::GTest`, `GTest::Main`
  - Test suites: `test_fp4_codec`, `test_router`, `test_reputation`, `test_pipeline`, `test_sgprocessing_pipeline`, `test_node_identity`, `test_message_signing`, `test_network`, `test_fact_validation`, `test_math_specialist`, `test_grammar_specialist`, `test_genius_slm_ffi`
- pytest — Python tests for `gnus-poc/` (`gnus-poc/tests/`)
  - Markers: `slow`, `integration`

**Build/Dev:**
- CMake 3.16+ — build configuration and dependency management
- Ninja — build generator
- Protocol Buffers (protobuf) — `.proto` compilation for gRPC messaging
- clang-format — Code formatting (Microsoft base style, `.clang-format`)
- clang-tidy — Static analysis (`.clang-tidy`)
- ffigen — Dart FFI binding generator for Flutter bridge
- Ruff — Python linter for `gnus-poc/` (line-length 120, target py310)

**UI:**
- Flutter 3.x — cross-platform UI framework for mobile and desktop
  - `flutter_chat_ui`, `flutter_chat_core`, `flutter_ai_toolkit` packages (`flutter_app/`)
  - `flutter_slm_bridge` — FFI plugin bridging Dart to C shared library

## Key Dependencies

**Critical (required for real inference):**
- MNN (Mobile Neural Network) — ML inference engine, cross-platform with Vulkan GPU acceleration
  - Located: `thirdparty/build/<Platform>/<BuildType>/MNN/`
  - Compile guard: `GENIUS_HAS_MNN` — without it, engine runs in stub mode
  - File: `src/core/engine/mnn_inference_engine.hpp`, `src/core/CMakeLists.txt:28-31`

- SentencePiece — subword tokenizer for LLM text processing
  - Located: `thirdparty/build/<Platform>/<BuildType>/sentencepiece/`
  - Compile guard: `GENIUS_HAS_SENTENCEPIECE` — **currently disabled** due to protobuf symbol conflicts with SGProcessingManager
  - File: `src/core/tokenizer/sentence_piece_tokenizer.cpp`, `src/core/CMakeLists.txt:43-57`
  - When skipped: tokenizer falls back to whitespace mode; MNN's built-in tokenizer (tokenizer.mtok) used instead

- libsecp256k1 — elliptic curve cryptography for node identity and message signing
  - Located: `thirdparty/build/<Platform>/<BuildType>/libsecp256k1/`
  - Compile guard: `GENIUS_HAS_SECP256K1`
  - File: `src/security/node_identity.hpp`, `src/security/CMakeLists.txt:13-16`

**Infrastructure:**
- Boost 1.85.0 — required components: date_time, filesystem, random, regex, system, thread, log, log_setup, program_options
  - Configured in `cmake/CommonBuildParameters.cmake:19-24, 158-173`

- RocksDB + Snappy — persistent key-value storage for reputation data
  - Compile guard: `GENIUS_HAS_ROCKSDB` — without it, reputation is in-memory only
  - File: `src/reputation/reputation_storage.hpp`, `src/reputation/CMakeLists.txt:15-21`

- libp2p — peer-to-peer networking stack (GossipSub, Kademlia DHT, mDNS, Noise, Yamux)
  - Compile guard: `GENIUS_HAS_LIBP2P` — without it, P2P runs in stub mode
  - Transitive deps: fmt, soralog, c-ares, ed25519, xxhash, tsl_hat_trie, sqlite3, protobuf, yaml-cpp, Boost.DI
  - File: `src/network/p2p_node.hpp`, `src/network/CMakeLists.txt:26-81`

- OpenSSL — SSL/TLS and cryptographic primitives (AES-256-GCM for key encryption)
  - Compile guard: `GENIUS_HAS_OPENSSL`
  - File: `src/security/CMakeLists.txt:27-31`

- Vulkan — GPU acceleration for inference
  - MoltenVK on macOS/iOS (Vulkan-to-Metal translation layer)
  - Compile guard: `GENIUS_HAS_VULKAN`
  - File: `src/core/CMakeLists.txt:62-83`

**Serialization & Data:**
- Protocol Buffers (protobuf) — message serialization for gRPC and inter-node communication
  - Proto files: `proto/genius_api.proto`, `proto/genius_reputation.proto`, `proto/genius_internal.proto`
  - Syntax: proto3

- nlohmann/json — JSON parsing (header-only)
  - Configured: `cmake/CommonBuildParameters.cmake:192-195`

- yaml-cpp — YAML parsing (available in thirdparty)

**Logging & Formatting:**
- spdlog — structured logging with compile-time format checking
  - Compile guard: `GENIUS_HAS_SPDLOG`, `SPDLOG_FMT_EXTERNAL`
  - File: `src/common/logging.hpp` — wraps spdlog directly
  - Log pattern: `[%Y-%m-%d %H:%M:%S.%e] [%^%l%$] [%n] %v`

- fmt — string formatting (used by spdlog and libp2p)
  - Configured: `cmake/CommonBuildParameters.cmake:111-114`

**Storage & Compression:**
- Snappy — fast compression (RocksDB dependency)
- zlib — general-purpose compression
- SQLite3 — embedded SQL database (used by libp2p deps)
- xxhash — fast non-cryptographic hashing

**Other:**
- Microsoft.GSL — Guidelines Support Library
- Boost.DI — Dependency injection framework
- SGProcessingManager — SuperGenius processing library (external, pre-built)
  - Components: ProcessingBase, SGProcessors, DataSplitter, sgprocmanagerlogger, sgprocmanagertypes, sgprocmanagersha
  - IPFS stack: ipfs-bitswap-cpp, ipfs-lite-cpp, ipfs-pubsub
  - AsyncIOManager
- GeniusSDK — Shared library for SuperGenius integration (`GeniusSDK_shared`)

**Python dependencies (gnus-poc/):**
- ML/Training: mlx, mlx-lm, mlx-metal (Apple Silicon), torch, transformers, datasets, scikit-learn, nltk
- API & Config: openai, tenacity, python-dotenv, PyYAML, rich
- Evaluation: mlflow
- Testing: pytest, pytest-mock, pytest-cov, pytest-timeout

## Configuration

**Environment:**
- No `.env` file detected — configuration is CLI-based
- CLI flags parsed in `src/main.cpp` via manual `ParseArgs()` loop
- JSON config file support via `--config <path>` flag (parsed with nlohmann/json)
- All configuration options:
  - `--model <path>` — core MNN model file
  - `--grammar-model <path>` — grammar specialist model
  - `--math-model <path>` — math specialist model
  - `--mode single|specialist|swarm` — execution mode
  - `--port <n>` — gRPC port (default: 50051)
  - `--db <path>` — reputation DB path (default: `./reputation.db`)
  - `--key <path>` — node key file (default: `./node.key`)
  - `--config <path>` — JSON config file (CLI flags override file values)
  - `--network` — enable P2P networking
  - `--knowledge <path>` — Grokipedia facts CSV path
  - `--max-tokens <n>` — max tokens to generate (default: 512)
  - `--temperature <f>` — sampling temperature (default: 0.7)
  - `--sg-endpoint <host:port>` — SuperGenius node address (default: `localhost:50051`)
  - `--sg-tls-ca <path>` — TLS CA certificate for SuperGenius
  - `--sg-tls-cert <path>` — TLS client certificate for SuperGenius
  - `--serve` — start gRPC server (blocking)
  - `--verbose` — enable debug logging

**Build:**
- CMake configuration files:
  - `build/<Platform>/CMakeLists.txt` — platform entry point
  - `cmake/CommonBuildParameters.cmake` — all thirdparty dependency find_package declarations (389 lines)
  - `build/cmake/functions.cmake` — helper functions (protobuf compilation, test registration)
  - `build/cmake/definition.cmake` — build definitions
  - `build/cmake/toolchain/cxx17.cmake` — C++17 toolchain enforcement
  - `cmake/config.cmake.in` — package config template
- Build targets:
  - `neo-swarm` — CLI binary (`src/main.cpp`)
  - `Genius-MOS-ELM-FFI` — shared library for Flutter FFI (`src/genius_elm_chat_completions.cpp`)
  - Static libraries: `neoswarm_common`, `neoswarm_core`, `neoswarm_specialists`, `neoswarm_router`, `neoswarm_reputation`, `neoswarm_security`, `neoswarm_network`, `neoswarm_knowledge`, `neoswarm_api`
- Compile definitions: `GENIUS_HAS_MNN`, `GENIUS_HAS_LIBP2P`, `GENIUS_HAS_ROCKSDB`, `GENIUS_HAS_SECP256K1`, `GENIUS_HAS_OPENSSL`, `GENIUS_HAS_VULKAN`, `GENIUS_HAS_SGPROCESSING`, `GENIUS_HAS_GRPC`, `SPDLOG_FMT_EXTERNAL`

## Platform Requirements

**Development:**
- macOS (primary): Xcode 16.x+, CMake 3.16+, Ninja, C++17 compiler
- Linux: CMake 3.16+, Ninja, GCC/Clang with C++17, `libuuid-dev`
- Windows: CMake 3.16+, Ninja, MSVC or Clang with C++17

**Production:**
- Native deployment: macOS, Linux, Windows, Android, iOS
- Supported: `build/OSX/`, `build/Linux/`, `build/Windows/`, `build/Android/`, `build/iOS/`
- Build types: `Debug`, `Release`, `RelWithDebInfo`
- Server mode: long-running process on port 50051 (macOS LaunchAgent supported via `RUN_AND_DEPLOY.md`)

---

*Stack analysis: 2026-06-17*
