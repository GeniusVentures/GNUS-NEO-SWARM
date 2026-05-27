# Coding Conventions

**Analysis Date:** 2026-05-27

## Language & Standard

- **Language:** C++17 (no C++20 features — e.g., no `std::coroutine`, no `consteval`)
- **Compilers:** Clang (Apple Clang), GCC; warnings enabled at high level via `cmake/CompilationFlags.cmake`

## File Naming

**Headers:**
- PascalCase with `.hpp` extension: `PromptAnalyzer.hpp`, `IRouter.hpp`, `Error.hpp`
- Interface headers follow `I` prefix convention: `IRouter.hpp`, `ISpecialist.hpp`
- Each `.hpp` has a corresponding `.cpp` in the same directory

**Source:**
- PascalCase with `.cpp` extension: `PromptAnalyzer.cpp`, `RuleBasedRouter.cpp`
- Entry-point files use snake_case: `genius_node.cpp`, `genius_slm_chat_c.cpp`

**Test files:**
- `test_<module>.cpp` in `test/<module>/` directory: `test/router/test_router.cpp`

**Include guards:**
```cpp
#ifndef NEOSWARM_<MODULE>_<FILE>_HPP_
#define NEOSWARM_<MODULE>_<FILE>_HPP_
// ...
#endif // NEOSWARM_<MODULE>_<FILE>_HPP_
```
Example: `NEOSWARM_ROUTER_IROUTER_HPP_` for `src/router/IRouter.hpp`

## Naming Patterns

**Classes & Structs:**
- PascalCase: `PromptAnalyzer`, `RuleBasedRouter`, `NodeReputation`, `GeniusAPIServer`
- Abstract interfaces prefixed with `I`: `IRouter`, `ISpecialist`
- Inner implementation structs use `Impl`: `NodeIdentity::Impl` (Pimpl idiom)

**Functions/Methods:**
- PascalCase: `Analyze()`, `ComputeNumericDensity()`, `LoadModel()`, `SelectWinner()`
- Free functions (file-local): PascalCase: `ToHex()`, `FromHex()`, `ClampScore()`

**Variables/Members:**
- camelCase with trailing underscore: `cfg_`, `loaded_`, `model_path_`, `prompt_`
- Stack/loop variables: camelCase: `numChars`, `total`, `flat_width`
- No Hungarian notation; no `m_` prefix

**Constants:**
- `ALL_CAPS` or `kPascalCase` for compile-time constants:
  ```cpp
  static constexpr size_t kMacroblockRows = 64;
  static constexpr size_t kPubKeySize     = 33;
  static constexpr uint64_t kMinTasksForHighTrust = 10;
  static constexpr int    kScaleSearchSteps = 32;
  ```

**Namespaces:**
- Deeply nested, matching directory structure:
  ```cpp
  namespace sgns::neoswarm::router { }
  namespace sgns::neoswarm::core { }
  namespace sgns::neoswarm::security { }
  namespace sgns::neoswarm::fp4 { }
  namespace sgns::neoswarm::reputation { }
  ```
- Closure comment duplicates namespace: `} // namespace sgns::neoswarm::router`

**Enums:**
- Always `enum class` with explicit underlying type:
  ```cpp
  enum class ExecutionMode : uint8_t { SingleNode = 0, Specialist = 1, Swarm = 2 };
  enum class Error : uint8_t { ModelLoadFailed = 1, InferenceFailed = 2, ... };
  ```
- Values are PascalCase

**Type Aliases:**
- `using` declarations preferred over `typedef`:
  ```cpp
  using PrivKey = std::array<uint8_t, kPrivKeySize>;
  using PubKey  = std::array<uint8_t, kPubKeySize>;
  using Logger  = std::shared_ptr<spdlog::logger>;
  ```

## Code Style

**Formatting (derived from CLAUDE.md — "Based on Microsoft with modifications"):**
- **Indentation:** 4 spaces (no tabs)
- **Line length:** 120 characters maximum
- **Braces:** Allman/Ullman style — each on its own line:
  ```cpp
  if ( condition )
  {
      // body
  }
  else
  {
      // body
  }
  ```
- **Parentheses:** Space after opening and before closing:
  ```cpp
  if ( condition )          // NOT if(condition)
  for ( auto &w : weights ) // NOT for(auto &w : weights)
  ```
- **Always use braces** even for single statements:
  ```cpp
  if ( total == 0 )
  {
      return 0.0f;
  }
  ```
- **No `.clang-format` file** detected in the repository

**Member variable declarations:**
- One member per line, right-aligned types (column alignment):
  ```cpp
  std::string   id_;
  std::string   prompt_;
  ExecutionMode mode_        = ExecutionMode::SingleNode;
  uint32_t      max_tokens_  = 512;
  float         temperature_ = 0.7f;
  ```
- Struct members are `public` by default, no getters/setters for POD-like structs

## Compilation & Warnings

Defined in `cmake/CompilationFlags.cmake`:
- **Enabled:** `-Wall`, `-Wextra`, `-Woverloaded-virtual`, `-Wformat=2`, `-Wmisleading-indentation`,
  `-Wduplicated-cond`, `-Wduplicated-branches`, `-Wnull-dereference`, `-Wsign-compare`,
  `-Wtype-limits`, `-Wnon-virtual-dtor`
- **Disabled (too noisy):** `-Wno-unused-variable`, `-Wno-unused-parameter`, `-Wno-unused-function`,
  `-Wno-double-promotion`, `-Wno-unused-command-line-argument`, `-Wno-format-nonliteral`,
  `-Wno-gnu-zero-variadic-macro-arguments`

## Doxygen Comments

**Every file** starts with a Doxygen header block:
```cpp
/**
 * @file       PromptAnalyzer.cpp
 * @brief      Prompt feature extraction implementation
 * @date       2026-05-06
 * @author     Subaskar S (ssivakumar@gnus.ai)
 */
```

**Every public method** has a Doxygen comment:
```cpp
/**
 * @brief Compute the ratio of tokens that are numeric.
 * @param prompt  Input string.
 * @return        Numeric density in [0, 1].
 */
float ComputeNumericDensity( const std::string &prompt ) const;
```

**Section separators** use dashed comment lines:
```cpp
// -----------------------------------------------------------------------
// Analyze
// -----------------------------------------------------------------------
```

## Error Handling

- **Primary mechanism:** `outcome::result<T>` from libp2p/Boost.Outcome (aliased as `sgns::neoswarm::outcome`)
- **Error type:** `sgns::neoswarm::Error` enum class registered via `OUTCOME_CPP_DEFINE_CATEGORY_3`
- **Propagation:** `BOOST_OUTCOME_TRY` macro:
  ```cpp
  BOOST_OUTCOME_TRY( engine_->LoadModel( model_path ) );
  ```
- **Manual checking:**
  ```cpp
  auto enc_res = codec.Encode( weights.data(), rows, cols );
  ASSERT_TRUE( enc_res.has_value() );
  ```
- **Return values:** `outcome::success( value )` or `outcome::failure( Error::SomeCode )`
- **No exceptions** thrown in hot paths (per CLAUDE.md directive); exceptions used only in argument parsing (`throw std::runtime_error`)
- Functions are expected to be `noexcept` unless required to throw (per CLAUDE.md)

## Logging

**Framework:** spdlog via `src/common/Logging.hpp`

**Pattern:**
- Each component creates a named logger via a file-local factory function in an anonymous namespace:
  ```cpp
  namespace
  {
      auto RouterLogger()
      {
          return neoswarm::CreateLogger( "Router" );
      }
  }
  ```
- Log levels used: `info`, `debug`, `warn`, `error`
- Logger name format: `NeoSwarm/<Tag>` (auto-prefixed by `CreateLogger`)
- Pattern: `[YYYY-MM-DD HH:MM:SS.ms] [LEVEL] [NeoSwarm/Tag] message`
- Log calls use spdlog format strings (`{}`-style):
  ```cpp
  RouterLogger()->debug( "Route: target={} mode={} confidence={:.2f}", ... );
  ```

## Import Organization

**Include order:**
1. Own header (matching `.cpp` to `.hpp`)
2. Project headers (with relative paths from `src/` root)
3. Standard library headers
4. Third-party headers

Example from `PromptAnalyzer.cpp`:
```cpp
#include "PromptAnalyzer.hpp"        // own header
// (other project headers are in .hpp)
#include <algorithm>                 // stdlib
#include <cctype>
#include <cmath>
```

## Function/Method Design

**Parameters:**
- Large types passed by `const&`: `const std::string &prompt`, `const NodeReputation &old`
- Primitive types passed by value: `float temperature`, `size_t rows`
- No output parameters — results returned by value or `outcome::result<T>`

**Const-correctness:**
- All read-only member functions marked `const`
- All input parameters `const` where possible
- `static constexpr` for compile-time constants

**Struct design:**
- Plain data with public members (like PODs)
- Named initialization (designated initializers where supported):
  ```cpp
  NodeReputation rep;
  rep.identity_key_ = "test-node";
  rep.global_score_ = 0.99;
  ```

## Modular Design

**Module structure:** One CMake `STATIC` library per directory:
```
src/core/CMakeLists.txt       → genius_core
src/router/CMakeLists.txt     → genius_router
src/reputation/CMakeLists.txt → genius_reputation
src/common/CMakeLists.txt     → genius_common
src/api/CMakeLists.txt        → genius_api
```

**Dependency pattern:** `genius_common` is the leaf dependency; all others depend on it:
```cmake
target_link_libraries(genius_router PUBLIC genius_common)
target_link_libraries(genius_core PUBLIC genius_common)
```

## Smart Pointer Usage

- `std::unique_ptr` — default for ownership: `std::unique_ptr<Impl> impl_;`
- `std::shared_ptr` — for shared resources (inference engines, loggers, node identity):
  ```cpp
  std::shared_ptr<core::InferenceEngine>  core_engine_;
  std::shared_ptr<security::NodeIdentity> identity_;
  ```
- **No `shared_ptr`** observed in test code — tests use stack objects

## Platform & Feature Flags

- Compile-time feature toggles use `#ifdef`:
  ```cpp
  #ifdef GENIUS_HAS_SECP256K1
  #ifdef GENIUS_HAS_SGPROCESSING
  #ifdef GENIUS_HAS_OPENSSL
  #ifdef GENIUS_HAS_VULKAN
  ```
- Stub implementations provided in `#else` blocks:
  ```cpp
  #else
      BridgeLogger()->warn( "SGProcessingManager not compiled in — stub mode" );
      return outcome::success( std::vector<uint8_t>{} );
  #endif
  ```

## Patterns to Follow When Adding Code

1. **New class:** Create `<ClassName>.hpp` and `<ClassName>.cpp` in the appropriate `src/<module>/` directory
2. **New interface:** Prefix with `I`, declare pure virtual methods, virtual destructor
3. **New struct:** Use public members with trailing underscores, default member initializers, no constructors unless needed
4. **Error cases:** Return `outcome::result<T>`, use `BOOST_OUTCOME_TRY` for propagation, register new error codes in `common/Error.hpp`
5. **Logging:** Add a file-local logger factory function in an anonymous namespace at the top of `.cpp` files
6. **Doxygen:** Add `@file`, `@brief`, `@date`, `@author` to every file header; document every public method with `@param` and `@return`
7. **CMake:** Add source files to the appropriate `STATIC` library, link against `genius_common`
8. **Config structs:** Use nested `Config` struct with default member initializers, trailing underscores

---

*Convention analysis: 2026-05-27*
