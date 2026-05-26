# Technology Stack

**Analysis Date:** 2026-05-26

## Languages

**Primary:**
- C++17 - Core inference engine, router, networking, reputation, security, CLI entry point, FFI bridge

**Secondary:**
- Dart 3.8 - Flutter UI application (`flutter_app/`) and FFI bridge plugin (`flutter_slm_bridge/`)
- Protocol Buffers 3 - API and internal message serialization (`proto/`)
- Python 3 - POC utilities and model conversion scripts (`gnus-poc/`, `.venv`)

## Runtime

**Environment:**
- Native C++ binary (`neo-swarm`) — no managed runtime, compiles to platform-native executable
- Flutter Dart VM — for UI on iOS, Android, macOS, Linux, Windows
- `gnus-poc/.venv/` — Python virtual environment for proof-of-concept work

**Package Manager:**
- Dart: `pub` (pubspec.yaml present in `flutter_app/` and `flutter_slm_bridge/`)
- C++: No package manager — thirdparty dependencies are pre-built in a sibling `thirdparty/` repository located via `FindThirdparty.cmake`
- Lockfiles: `pubspec.lock` present in both Flutter projects

## Frameworks

**Core:**
- C++17 STL — primary standard library, no external application framework
- Boost 1.85.0 — async I/O (ASIO), filesystem, threading, date_time, random, regex, program_options, log, outcome (via libp2p)

**Inference:**
- MNN (Alibaba) — lightweight deep learning inference engine; loads `.mnn` models with Vulkan/MoltenVK GPU backend or CPU fallback
- Custom FP4Codec — 4-bit floating point weight decompression at load time (`src/core/fp4/FP4Codec.hpp`)

**UI:**
- Flutter 3.x — cross-platform UI (`flutter_app/`)
  - `flutter_ai_toolkit: ^1.0.0` — LLM chat UI components
  - `cupertino_icons: ^1.0.8`
  - `ffi: ^2.2.0` — Dart FFI to call into native C++ shared library

**FFI Bridge:**
- `flutter_slm_bridge` plugin (`flutter_slm_bridge/`) — Dart FFI to C shared library `Genius-MOS-SLM-FFI`
  - `ffi: ^2.1.3`
  - `plugin_platform_interface: ^2.0.2`
  - `ffigen: ^13.0.0` — auto-generates Dart bindings from C header

**Testing:**
- Google Test (GTest) — unit and integration tests (`test/`)
- `flutter_test` — Flutter widget tests (`flutter_app/test/`, `flutter_slm_bridge/test/`)

**Build/Dev:**
- CMake 3.30+ — build system configuration
- Ninja — build executor
- clang-format — code formatting (Microsoft-based with modifications, configured via `CLAUDE.md`)
- `flutter_lints: ^5.0.0` — Dart linting

## Key Dependencies

**Critical (required for real inference):**
- MNN (pre-built static/dynamic library) — inference engine backend (`src/core/engine/MNNInferenceEngine.hpp`)
- SentencePiece — tokenizer library (`src/core/tokenizer/Tokenizer.hpp`, `SentencePieceTokenizer.cpp`)
- OpenSSL — cryptography for message signing, key file encryption (`src/security/`)
- secp256k1 — elliptic curve keypair generation for node identity (`src/security/NodeIdentity.hpp`)

**Infrastructure:**
- spdlog — structured logging framework (`src/common/Logging.hpp`)
- fmt — C++ formatting library (used by spdlog)
- nlohmann/json — JSON parsing, header-only
- RocksDB — persistent key-value store for reputation data (`src/reputation/ReputationStorage.hpp`)
- libp2p — P2P networking stack (`src/network/P2PNode.hpp`)
- gRPC — client-facing API server and inter-node communication
- Protobuf — message serialization for gRPC and gossip (`proto/`)
- Vulkan SDK / MoltenVK — GPU acceleration for inference
- Microsoft GSL — Guidelines Support Library
- Boost.Outcome (via libp2p) — `outcome::result<T>` error handling (`src/common/Error.hpp`)

**Optional integration points:**
- SGProcessingManager — data processing pipeline for GNUS network dispatch (`src/core/sgprocessing/SGProcessingBridge.hpp`, `SGProcessingManager/` submodule)
- yaml-cpp — for future config file support
- boost::coroutines — referenced in code style but currently disallowed (C++20 only)

**Submodules:**
- `build/` — CMake build templates (`../cmaketemplate.git`)
- `SGProcessingManager/` — processing manager library (`https://github.com/GeniusVentures/SGProcessingManager.git`)

## Configuration

**Build Configuration:**
- `CMakeLists.txt` (root) — project definition, build options, source tree, install rules
- `cmake/CommonBuildParameters.cmake` — thirdparty dependency discovery and linking
- `cmake_genius/FindThirdparty.cmake` — locates pre-built thirdparty libs from `../thirdparty/`
- `cmake/functions.cmake` — utility functions
- `cmake/config.cmake.in` — install config template
- `cmake/CompilationFlags.cmake` — compiler flags (referenced by build platform CMakeLists)

**Build Options (CMake):**
| Option | Default | Purpose |
|--------|---------|---------|
| `GENIUS_BUILD_TESTS` | ON | Build unit/integration test executables |
| `GENIUS_BUILD_BENCHMARKS` | OFF | Build benchmarks |
| `GENIUS_ENABLE_NETWORK` | OFF | Enable libp2p P2P networking |
| `GENIUS_ENABLE_GPU` | ON | Enable Vulkan/MoltenVK GPU acceleration |
| `GENIUS_ENABLE_SGPROCESSING` | OFF | Enable SGProcessingManager integration |

**Compile-time Feature Flags:**
| Flag | Enables |
|------|---------|
| `GENIUS_HAS_MNN` | Real inference via MNN (vs. stub mode) |
| `GENIUS_HAS_SENTENCEPIECE` | Real tokenizer (vs. whitespace fallback) |
| `GENIUS_HAS_VULKAN` | GPU-accelerated inference |
| `GENIUS_HAS_SPDLOG` | Structured logging |
| `GENIUS_HAS_GRPC` | gRPC server and client |
| `GENIUS_HAS_SECP256K1` | Real cryptographic node identity |
| `GENIUS_HAS_ROCKSDB` | Persistent reputation storage |
| `GENIUS_HAS_SGPROCESSING` | SGProcessingManager integration |

**Runtime Configuration:**
- CLI arguments only (no config file support yet — planned in Task 5.3): `--model`, `--port`, `--db`, `--key`, `--network`, `--knowledge`, `--max-tokens`, `--temperature`, `--serve`, `--verbose`
- Environment: No `.env` files detected in the project
- Key file: `--key <path>` (default `./node.key`) — secp256k1 keypair for node identity
- Reputation DB: `--db <path>` (default `./reputation.db`) — RocksDB database

**Flutter Configuration:**
- `flutter_app/pubspec.yaml` — SDK ^3.8.1, Flutter dependencies
- `flutter_slm_bridge/pubspec.yaml` — SDK ^3.8.1, FFI plugin configuration (all platforms)
- `analysis_options.yaml` — Dart analysis rules (both projects)

## Platform Requirements

**Development:**
- Xcode 16.x+ (macOS)
- C++17-compatible compiler (Clang 10+, GCC 8+)
- CMake 3.30+
- Ninja build tool
- Pre-built thirdparty libraries in `../thirdparty/build/<Platform>/<BuildType>/`
- Flutter SDK 3.8.1+

**Production:**
- macOS (ARM64/x86_64) — primary development and deployment target
- Linux — server deployment
- Windows — desktop deployment
- Android — mobile deployment via Flutter
- iOS — mobile deployment via Flutter

**Build Outputs:**
- `neo-swarm` — CLI binary (installed to `bin/`)
- `libGenius-MOS-SLM-FFI.dylib` (macOS) / `.so` (Linux) / `.dll` (Windows) — FFI shared library for Flutter (installed to `lib/`)
- `genius_api`, `genius_core`, etc. — static libraries for internal linking

---

*Stack analysis: 2026-05-26*
