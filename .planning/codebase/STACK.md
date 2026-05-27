# Technology Stack

**Analysis Date:** 2026-05-27

## Languages

**Primary:**
- C++17 - Full project core (`src/`, `test/`), all inference, routing, networking, security, and API layers
  - Standard: `CMAKE_CXX_STANDARD 17`, extensions OFF (enforced in `build/CommonCompilerOptions.cmake:22-24`)
  - Target features: `cxx_std_17` (set in `src/common/CMakeLists.txt:12`)

**Secondary:**
- C - C-compatible FFI exports for Flutter bridge (`src/genius_slm_chat_c.h`, `src/genius_slm_chat_c.cpp`)
- Dart 3.x - Flutter UI applications and FFI bridge package
  - `ui/pubspec.yaml`: SDK `>=3.4.4 <4.0.0`
  - `flutter_app/pubspec.yaml`: SDK `^3.8.1`
  - `flutter_slm_bridge/pubspec.yaml`: SDK `^3.8.1`

## Runtime

**Environment:**
- Clang / AppleClang / GCC (cross-platform C++17 compiler required)
- Native binaries — no managed runtime or VM for the core engine

**Package Manager:**
- CMake 3.22+ with Ninja generator
- Pre-built thirdparty dependencies from `thirdparty/build/<Platform>/<BuildType>/` (fetched from GitHub releases at `GeniusVentures/thirdparty`)
- Flutter/Dart packages via `pubspec.yaml` (standard `flutter pub get`)
- Lockfile: Not detected (Dart/Flutter uses `pubspec.lock` — generated at `pub get` time)
- Git submodules: `build/` (submodule pointing to `../cmaketemplate.git`) — `.gitmodules`

## Frameworks

**Core:**
- No application framework — raw C++17 with modular static library architecture
- Boost 1.85.0 — foundational utility: ASIO, filesystem, program_options, outcome (error handling)

**Testing:**
- Google Test 1.x (gtest + gmock) — `test/CMakeLists.txt` via `find_package(GTest)`
  - Test binary pattern: `add_executable(test_{component})` with `GTest::GTest`, `GTest::Main`
  - Test suites: `test_fp4_codec`, `test_router`, `test_reputation`, `test_pipeline`, `test_sgprocessing_pipeline`
  - Mock support: `GTest::gmock_main` via `addtest_mock()` cmake function

**Build/Dev:**
- CMake 3.22+ — build configuration and dependency management
- Ninja — build generator
- Protocol Buffers (protobuf) — `.proto` compilation via `compile_proto_to_cpp()` in `build/cmake/functions.cmake`
- ffigen ^13.0.0 — Dart FFI binding generator for Flutter bridge (`flutter_slm_bridge/pubspec.yaml`)

**UI:**
- Flutter 3.x — cross-platform UI framework for mobile and desktop
  - `flutter_chat_ui: ^2.0.0` — chat UI components
  - `flutter_chat_core: ^2.0.0` — chat state management
  - `flutter_ai_toolkit: ^1.0.0` — AI toolkit integration (`flutter_app/pubspec.yaml`)

## Key Dependencies

**Critical (required for real inference):**
- MNN (Mobile Neural Network) — ML inference engine, cross-platform with Vulkan GPU acceleration
  - Located: `thirdparty/build/<Platform>/<BuildType>/MNN/`
  - Version: compiled from source in thirdparty build
  - Compile guard: `GENIUS_HAS_MNN` — without it, engine runs in stub mode
  - File: `src/core/engine/MNNInferenceEngine.hpp`, `src/core/CMakeLists.txt:28-31`

- SentencePiece — subword tokenizer for LLM text processing
  - Located: `thirdparty/build/<Platform>/<BuildType>/sentencepiece/`
  - Compile guard: `GENIUS_HAS_SENTENCEPIECE` — without it, returns space-separated numeric token IDs
  - File: `src/core/tokenizer/SentencePieceTokenizer.cpp`, `src/core/CMakeLists.txt:41-53`
  - Transitive dependency: Abseil (abseil-cpp static libs)

- libsecp256k1 — elliptic curve cryptography for node identity and message signing
  - Located: `thirdparty/build/<Platform>/<BuildType>/libsecp256k1/`
  - Compile guard: `GENIUS_HAS_SECP256K1`
  - File: `src/security/NodeIdentity.hpp`, `src/security/CMakeLists.txt:13-16`
  - Without it: peer ID is XOR hash of random bytes (non-cryptographic)

**Infrastructure:**
- Boost 1.85.0 — required components: date_time, filesystem, random, regex, system, thread, log, log_setup, program_options
  - Configured in `cmake/CommonBuildParameters.cmake:79-97` and `build/CommonCompilerOptions.cmake:1-8`
  - `boost::asio::io_context` used for async operations in `MNNInferenceEngine` and `SGProcessingBridge`

- RocksDB — persistent key-value storage for reputation data
  - Located: `thirdparty/build/<Platform>/<BuildType>/rocksdb/`
  - Compile guard: `GENIUS_HAS_ROCKSDB` — without it, reputation is in-memory only
  - Compression: Snappy (snappy)
  - File: `src/reputation/ReputationStorage.hpp`, `src/reputation/CMakeLists.txt:15-21`

- libp2p — peer-to-peer networking stack (GossipSub, Kademlia DHT, mDNS, Noise, Yamux)
  - Compile guard: `GENIUS_HAS_LIBP2P` — without it, P2P runs in stub mode
  - Transitive deps: fmt, soralog, c-ares, ed25519, xxhash, tsl_hat_trie, sqlite3, protobuf, yaml-cpp, Boost.DI
  - File: `src/network/P2PNode.hpp`, `src/network/CMakeLists.txt:20-67`

- OpenSSL — SSL/TLS and cryptographic primitives
  - File: `src/security/CMakeLists.txt:18-22`
  - Compile guard: `GENIUS_HAS_OPENSSL`

- Vulkan — GPU acceleration for inference
  - MoltenVK on macOS/iOS (Vulkan-to-Metal translation layer)
  - File: `src/core/CMakeLists.txt:57-79`
  - Apple frameworks linked for MoltenVK: Metal, Foundation, QuartzCore, IOSurface, CoreGraphics, IOKit, AppKit, CoreFoundation

**Serialization & Data:**
- Protocol Buffers (protobuf) — message serialization for gRPC and inter-node communication
  - Proto files: `proto/genius_api.proto`, `proto/genius_reputation.proto`, `proto/genius_internal.proto`
  - Syntax: proto3

- nlohmann/json — JSON parsing (header-only)
  - Configured: `cmake/CommonBuildParameters.cmake:100-110`

- rapidjson — JSON parsing (used by thirdparty deps)
  - Located: `thirdparty/build/<Platform>/<BuildType>/rapidjson/`

- yaml-cpp — YAML parsing (available in thirdparty, planned for config file support — Task 5.3)

**Logging & Formatting:**
- spdlog — structured logging with compile-time format checking
  - Compile guard: `GENIUS_HAS_SPDLOG`, `SPDLOG_FMT_EXTERNAL`
  - File: `src/common/Logging.hpp` — wraps spdlog directly
  - Log pattern: `[%Y-%m-%d %H:%M:%S.%e] [%^%l%$] [%n] %v`

- fmt — string formatting (used by spdlog and libp2p)
  - Configured: `cmake/CommonBuildParameters.cmake:62-65`

**Storage & Compression:**
- Snappy — fast compression (RocksDB dependency)
- zlib — general-purpose compression (`thirdparty/zlib/`)
- SQLite3 — embedded SQL database (used by libp2p deps)
- xxhash — fast non-cryptographic hashing

**Other:**
- Microsoft.GSL — Guidelines Support Library
- SGProcessingManager — SuperGenius processing library (external, pre-built)
  - Components: ProcessingBase, SGProcessors, DataSplitter, sgprocmanagerlogger, sgprocmanagertypes, sgprocmanagersha
  - IPFS stack: ipfs-bitswap-cpp, ipfs-lite-cpp, ipfs-pubsub
  - AsyncIOManager

## Configuration

**Environment:**
- No `.env` file detected — configuration is CLI-based
- CLI flags parsed in `src/genius_node.cpp` via manual `ParseArgs()` loop
- All configuration options:
  - `--model <path>` — core MNN model file
  - `--grammar-model <path>` — grammar specialist model
  - `--math-model <path>` — math specialist model
  - `--mode single|specialist|swarm` — execution mode
  - `--port <n>` — gRPC port (default: 50051)
  - `--db <path>` — reputation DB path (default: `./reputation.db`)
  - `--key <path>` — node key file (default: `./node.key`)
  - `--network` — enable P2P networking
  - `--knowledge <path>` — Grokipedia facts CSV path
  - `--max-tokens <n>` — max tokens to generate (default: 512)
  - `--temperature <f>` — sampling temperature (default: 0.7)
  - `--serve` — start gRPC server (blocking)
  - `--verbose` — enable debug logging
  - `--sg-endpoint <host:port>` — (planned, Task 4.2) SuperGenius gRPC endpoint

- Runtime files (`.gitignore` excluded):
  - `node.key` — secp256k1 private key (plain hex, planned AES-256-GCM encryption)
  - `reputation.db/` — RocksDB database directory
  - `mnn_cachefile.bin` — MNN model cache

**Build:**
- CMake configuration files:
  - `build/<Platform>/CMakeLists.txt` — platform entry point
  - `build/CommonCompilerOptions.cmake` — global compiler settings, C++17 standard, thirdparty setup
  - `cmake/CommonBuildParameters.cmake` — all thirdparty dependency find_package declarations
  - `cmake/CompilationFlags.cmake` — warning flags (`-Wall`, `-Wextra`, etc.)
  - `cmake/functions.cmake` — helper functions (protobuf compilation, test registration, etc.)
  - `cmake/config.cmake.in` — package config template
- Build targets:
  - `neo-swarm` — CLI binary (`src/genius_node.cpp`)
  - `Genius-MOS-SLM-FFI` — shared library for Flutter FFI (`src/genius_slm_chat_c.cpp`)
  - Static libraries: `genius_common`, `genius_core`, `genius_specialists`, `genius_router`, `genius_reputation`, `genius_security`, `genius_network`, `genius_knowledge`, `genius_api`
- Sanitizer support: `-DSANITIZE_ADDRESS=code` enables AddressSanitizer
- Test flag: `-DGENIUS_BUILD_TESTS=ON` enables test binaries build

## Platform Requirements

**Development:**
- macOS (primary): Xcode 16.x+, CMake 3.22+, Ninja, C++17 compiler
- Linux: CMake 3.22+, Ninja, GCC/Clang with C++17, `libuuid-dev`
- Windows: CMake 3.22+, Ninja, MSVC or Clang with C++17

**Production:**
- Native deployment: macOS, Linux, Windows, Android, iOS
- Supported: `build/OSX/`, `build/Linux/`, `build/Windows/`, `build/Android/`, `build/iOS/`
- macOS minimum: deployment target 13.0 (set in `build/OSX/CMakeLists.txt:18`)
- macOS: universal binary (x86_64 + arm64) via `MAC_UNIVERSAL` platform
- Server mode: long-running gRPC server on port 50051 (macOS LaunchAgent supported via `RUN_AND_DEPLOY.md`)

---

*Stack analysis: 2026-05-27*
