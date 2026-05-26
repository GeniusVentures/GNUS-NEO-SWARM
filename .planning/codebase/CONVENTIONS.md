# Coding Conventions

**Analysis Date:** 2026-05-26

## Language Ecosystems

The project spans two ecosystems with distinct conventions:

### C++ (Engine — `src/`, `test/`)

- **Standard:** C++17 (`-std=c++17`, `CMAKE_CXX_STANDARD 17`)
- **Compiler flags:** `-Wall -Wextra -Wpedantic -Wno-unused-parameter`
- **Build:** CMake 3.30+ with Ninja generator
- **Error handling:** `outcome::result<T>` (Boost.Outcome / libp2p::outcome)
- **Exception policy:** `noexcept` by default; no exceptions in hot paths

### Dart/Flutter (Frontend — `flutter_app/`, `flutter_slm_bridge/`, `ui/`)

- **SDK:** Dart `^3.8.1`
- **Linting:** `package:flutter_lints/flutter.yaml` (v5.0.0 in flutter_app/bridge, v3.0.0 in ui/)
- **Testing:** `flutter_test` SDK package

---

## Naming Patterns

### C++

**Classes, Structs, Methods:**
- PascalCase: `GeniusAPIServer`, `MathSpecialist`, `RuleBasedRouter`, `InferenceEngine`, `FP4Codec`
- Abstract interfaces prefixed with `I`: `IRouter`, `ISpecialist`

**Member Variables:**
- camelCase with trailing underscore: `cfg_`, `model_path_`, `loaded_`, `running_`, `task_count_`, `last_confidence_`
- Struct public members also use trailing underscore: `NodeReputation::global_score_`, `Task::prompt_`
- Files: `src/common/Types.hpp`, `src/api/GeniusAPIServer.hpp`, `src/specialists/MathSpecialist.hpp`

**Local Variables:**
- camelCase: `engine_cfg`, `tok_path`, `aug_task`, `median_latency`

**Function/Method Names:**
- PascalCase: `Initialize()`, `Process()`, `SelectWinner()`, `BuildPrompt()`, `ComputeWeights()`
- Getters: `IsLoaded()`, `BackendName()`, `GetName()`, `GetConfidence()`
- Private helpers: `SelectMode()`, `TrySymbolicFallback()`, `RunForward()`, `SampleToken()`

**Constants:**
- kCamelCase prefix: `kConfidenceThreshold`, `kMinTasksForHighTrust`, `kPublicKeySize`
- Source: `src/specialists/SymbolicFallback.hpp:26`, `src/common/Types.hpp:115`

**Enums:**
- Enum types: PascalCase — `ExecutionMode`, `RouteTarget`, `Error`, `Strategy`
- Enum values: PascalCase — `SingleNode`, `CorePlusMath`, `ModelLoadFailed`, `WeightedVoting`

**Scoped Enums:** All enums use `enum class` (`src/common/Error.hpp:18`, `src/router/IRouter.hpp` — via Types.hpp). Underlying type specified: `: uint8_t` for `Error`, `ExecutionMode`, `RouteTarget`, `Strategy`.

**Namespaces:**
- Nested with full indentation: `sgns::neoswarm::[module]`
- Module-level sub-namespaces: `sgns::neoswarm::api`, `sgns::neoswarm::router`, `sgns::neoswarm::reputation`, `sgns::neoswarm::specialists`, `sgns::neoswarm::core`, `sgns::neoswarm::security`, `sgns::neoswarm::network`, `sgns::neoswarm::knowledge`, `sgns::neoswarm::fp4`
- Namespace alias: `namespace outcome = libp2p::outcome` (`src/common/Error.hpp:13`)
- `using` directives only in implementation files (`.cpp`)

**Macros:**
- ALL_CAPS with project prefix: `NEOSWARM_COMMON_ERROR_HPP_`, `GENIUS_HAS_SGPROCESSING`
- `BOOST_OUTCOME_TRY` for error propagation

**Files:**
- Headers: PascalCase `.hpp` — `GeniusAPIServer.hpp`, `MathSpecialist.hpp`, `IRouter.hpp`
- Implementation: PascalCase `.cpp` — `GeniusAPIServer.cpp`, `MathSpecialist.cpp`
- Test files: `test_[name].cpp` — `test_fp4_codec.cpp`, `test_router.cpp`, `test_reputation.cpp`
- C FFI header: `genius_slm_chat_c.h` (C-compatible, snake_case)

### Dart/Flutter

**Files:**
- snake_case: `flutter_slm_bridge.dart`, `widget_test.dart`, `main.dart`
- Generated bindings: `*_generated.dart` (`flutter_slm_bridge_bindings_generated.dart`, `genius_slm_bindings_generated.dart`)

**Classes:**
- PascalCase: `GeniusSwarmApp`, `GeniusChatScreen`, `FlutterSlmBridgeBindings`

**Methods/Functions:**
- camelCase: `geniusSlmInit()`, `chatCompletionsCreate()`, `extractContent()`
- Private: `_sum`, `_incrementCounter`

**Variables:**
- camelCase: `_chatController`, `_isThinking`
- Private with `_` prefix: `_counter`, `_libName`, `_dylib`, `_bindings`
- Top-level constants: camelCase — `_libName`, `_dylib`

---

## Code Style

### C++

**Formatting:**
- Style based on Microsoft with modifications (`.clang-format` referenced in `CLAUDE.md` but not present in repo)
- Indentation: **4 spaces**
- Line length: **120 characters** maximum
- Brace style: **Allman/Ullman** — each brace on its own line

```cpp
// From src/router/RuleBasedRouter.cpp
if ( features.numeric_density_ > cfg_.numeric_density_threshold_
     || features.has_math_keywords_ )
{
    decision.target_     = RouteTarget::CorePlusMath;
    decision.confidence_ = 0.85f + features.numeric_density_ * 0.15f;
}
```

**Parentheses:** Space after opening `( ` and before closing ` )`:
```cpp
if ( condition )           // not if(condition)
while ( running_.load() )  // not while(running_.load())
func( arg1, arg2 );        // not func(arg1, arg2);
```

**Always braces** on control structures even for single statements:
```cpp
// From src/router/RuleBasedRouter.cpp:31-38
if ( requested == ExecutionMode::Swarm )
{
    return ExecutionMode::Swarm;
}
if ( requested == ExecutionMode::Specialist )
{
    return ExecutionMode::Specialist;
}
```

**Header Guards:**
```cpp
#ifndef NEOSWARM_[MODULE]_[NAME]_HPP_
#define NEOSWARM_[MODULE]_[NAME]_HPP_
// ...
#endif // NEOSWARM_[MODULE]_[NAME]_HPP_
```
Examples: `NEOSWARM_ROUTER_RULEBASEDROUTER_HPP_`, `NEOSWARM_COMMON_TYPES_HPP_`, `NEOSWARM_API_GENIUSAPISERVER_HPP_`

**Section Dividers:**
```cpp
// -----------------------------------------------------------------------
// Section Name
// -----------------------------------------------------------------------
```

**Initialization:**
- All variables initialized at declaration: `bool loaded_ = false;`, `float last_confidence_ = 0.0f;`
- Member initialization lists in constructor (declaration order): `MathSpecialist.cpp:23-26`
- Prefer `{}` initialization

**Type Aliases:**
```cpp
using Logger = std::shared_ptr<spdlog::logger>;          // src/common/Logging.hpp:17
using neoswarm::NodeReputation;                           // src/reputation/NodeReputation.hpp:16
```
- Prefer `using` over `typedef`

### Dart/Flutter

**Formatting:**
- Trailing commas for auto-formatting (`flutter_app/lib/main.dart:119`)
- `const` constructors where possible (`const MyApp({super.key})`)
- `@override` on all overridden methods
- `required` for named parameters (`required this.title`)

---

## Import Organization

### C++

**Order (observed):**
1. Corresponding header (in `.cpp`): `#include "MathSpecialist.hpp"`
2. Project internal headers: `#include "common/Logging.hpp"`
3. Standard library headers: `#include <functional>`, `#include <string>`

**Include Paths:**
- Relative to `src/`: `#include "common/Error.hpp"`, `#include "core/engine/InferenceEngine.hpp"`
- Single-quoted `"..."` for project headers

### Dart

**Order:**
1. `dart:` imports (`dart:convert`, `dart:ffi`, `dart:io`, `dart:isolate`)
2. Package imports (`package:flutter/material.dart`, `package:ffi/ffi.dart`)
3. Project imports (`package:flutter_slm_bridge/flutter_slm_bridge.dart`)

---

## Error Handling

### C++ — `outcome::result<T>` Pattern

**Core mechanism:** All fallible functions return `outcome::result<T>`.

**Success:**
```cpp
return outcome::success();                    // src/specialists/MathSpecialist.cpp:40
return outcome::success( std::move( resp ) ); // src/api/GeniusAPIServer.cpp:232
return outcome::success( symbolic.value() );  // src/specialists/MathSpecialist.cpp:80
```

**Failure:**
```cpp
return outcome::failure( Error::ModelLoadFailed );      // src/specialists/MathSpecialist.cpp:35
return outcome::failure( Error::InternalError );        // src/api/GeniusAPIServer.cpp:386
return outcome::failure( route_res.error() );           // error chaining
```

**Propagation macro:**
```cpp
BOOST_OUTCOME_TRY( engine_->LoadModel( model_path ) );  // src/specialists/MathSpecialist.cpp:37
BOOST_OUTCOME_TRY( identity_->Generate() );             // src/api/GeniusAPIServer.cpp:63
```

**Checking results:**
```cpp
if ( !res.has_value() ) { /* handle */ }           // check for error
auto val = res.value();                             // unwrap (must have checked)
```

**Error codes:** Defined as scoped enum in `src/common/Error.hpp:18-44` — values like `ModelLoadFailed`, `InferenceFailed`, `RoutingFailed`, `NetworkError`, etc. Error messages registered in `src/common/Error.cpp` via `OUTCOME_CPP_DEFINE_CATEGORY_3`.

**No exceptions in hot paths.** Functions default `noexcept` unless explicitly required to throw. Only `src/genius_node.cpp` uses `try/catch` with `std::exception` for argument parsing.

### Dart — Standard Patterns

- Try/catch: Used minimally — `flutter_slm_bridge.dart:133` catches general errors in `extractContent()`
- Error returns: `geniusSlmInit()` returns `-1` on failure, `0` on success
- FFI null checks: Returns error JSON string on null pointer from native code (`flutter_slm_bridge.dart:78-79`)

---

## Logging

**Framework:** `spdlog` via `src/common/Logging.hpp`

**Patterns:**
- Each translation unit creates a private logger via anonymous namespace:
```cpp
// From src/api/GeniusAPIServer.cpp:23-26
namespace
{
    auto ServerLogger()
    {
        return neoswarm::CreateLogger( "GeniusAPIServer" );
    }
}
```

**Usage:**
- `info()`: lifecycle events — `ServerLogger()->info( "Initializing GeniusAPIServer..." );`
- `warn()`: non-fatal issues — `ServerLogger()->warn( "Core model load failed — continuing in stub mode" );`
- `debug()`: detailed routing/reputation — `RouterLogger()->debug( "Route: target={} mode={} confidence={:.2f}", ... );`
- `error()`: not observed in codebase (fatal handled via `outcome::failure`)

**Log format:** `[YYYY-MM-DD HH:MM:SS.ms] [LEVEL] [NeoSwarm/Component] message` (`src/common/Logging.hpp:34`)

**Type alias:** `using Logger = std::shared_ptr<spdlog::logger>` (`src/common/Logging.hpp:17`)

---

## Comments

### C++ — Doxygen

**Every file:** Doxygen header with `@file`, `@brief`, and optionally `@date`, `@author`:
```cpp
/**
 * @file       MathSpecialist.hpp
 * @brief      GSM8K-tuned math specialist model (PTDS §5.2)
 * @date       2026-05-06
 * @author     Subaskar S (ssivakumar@gnus.ai)
 */
```

**Every class:** Doxygen block with `@brief` and behavior description:
```cpp
/**
 * @brief 1-3B parameter GSM8K-tuned math model (PTDS §5.2).
 *
 * Activated by the router when numeric density > threshold.
 * Includes symbolic fallback when model confidence < kConfidenceThreshold.
 */
class MathSpecialist : public ISpecialist
```

**Every public method:** Doxygen with `@param`, `@return`:
```cpp
/**
 * @brief Process input (typically Core LLM output) and return refined output.
 * @param input  Text to process.
 * @return       Refined text or InferenceFailed.
 */
virtual outcome::result<std::string> Process( const std::string &input ) = 0;
```

**Section dividers:** `// ----- Name -----`
```cpp
// -----------------------------------------------------------------------
// BuildPrompt
// -----------------------------------------------------------------------
```

### Dart

- Inline comments for explanations (`flutter_app/lib/main.dart` has extensive Flutter template comments)
- Documentation comments: Not consistently Doxygen; `flutter_slm_bridge.dart` uses `///` for public API

---

## Function Design

### C++

**Size:** Functions are generally small (~10-40 lines). Largest are initialization (`Initialize`: 106 lines) and pipeline methods (`RunSwarm`: 79 lines).

**Parameters:**
- Objects passed by `const&`: `Process( const Task &task )`, `Update( const NodeReputation &old, ... )`
- Built-ins passed by value: `int a, int b`, `double score`
- `std::string` by `const&`: `SetTokenizer( const std::string &model_path )`
- `std::optional` for nullable: `std::optional<std::string> ground_truth`
- No in-out parameters (const + return results pattern)

**Return Values:**
- `outcome::result<T>` for fallible operations
- `void` for guaranteed side-effects
- Direct types for pure functions: `std::string`, `double`

**Modifiers:**
- `const` on member functions not modifying state
- `override` on all virtual overrides
- `explicit` on single-argument constructors
- `= default` for virtual destructors
- `noexcept` specified in FFI C API (`genius_slm_chat_c.h`)

### Dart

- `Future<T>` for async operations
- Named parameters with `{}` for configuration
- Short single-purpose functions

---

## Module Design

### C++

**Exports:** One class per header file (with related Config struct):
- `src/router/RuleBasedRouter.hpp` exports `RuleBasedRouter` + nested `Config`
- `src/specialists/MathSpecialist.hpp` exports `MathSpecialist` (interfaces in separate header: `ISpecialist.hpp`)

**CMake library-per-module:** Each `src/[module]/CMakeLists.txt` defines a STATIC library:
- `genius_common`, `genius_core`, `genius_api`, `genius_router`, `genius_reputation`, etc.

**Config structs:** Every class with configurable behavior has a nested `Config` struct:
```cpp
class RuleBasedRouter : public IRouter
{
public:
    struct Config
    {
        float numeric_density_threshold_ = 0.30f;
        float complexity_swarm_threshold_ = 5.0f;
        bool  enable_swarm_mode_         = true;
    };
    RuleBasedRouter();
    explicit RuleBasedRouter( Config cfg );
    // ...
};
```
Sources: `src/router/RuleBasedRouter.hpp`, `src/api/GeniusAPIServer.hpp`, `src/reputation/WeightedConsensus.hpp`, `src/reputation/ReputationScoring.hpp`, `src/core/engine/MNNInferenceEngine.hpp`

**Private logger factory pattern:** Each `.cpp` file has anonymous-namespace logger factory:
```cpp
namespace
{
    auto RouterLogger()
    {
        return neoswarm::CreateLogger( "Router" );
    }
}
```
Sources: `src/router/RuleBasedRouter.cpp:13-19`, `src/reputation/ReputationScoring.cpp:16-22`, `src/specialists/MathSpecialist.cpp:15-21`, `src/api/GeniusAPIServer.cpp:21-33`

**Abstract interfaces:** Used for pluggable components:
- `src/core/engine/InferenceEngine.hpp` — `class InferenceEngine` (pure virtual, `= default` destructor)
- `src/router/IRouter.hpp` — `class IRouter` with single `Route()` pure virtual
- `src/specialists/ISpecialist.hpp` — `class ISpecialist` with 4 pure virtual methods

---

## Memory Management

**Unique ownership:** `std::unique_ptr` for exclusive ownership (preferred per CLAUDE.md)
```cpp
std::unique_ptr<router::RuleBasedRouter>   router_;     // src/api/GeniusAPIServer.hpp:98
std::unique_ptr<reputation::WeightedConsensus> consensus_; // :99
```

**Shared ownership:** `std::shared_ptr` for components used by multiple owners:
```cpp
std::shared_ptr<core::InferenceEngine> engine_;           // MathSpecialist.hpp:39
std::shared_ptr<knowledge::KnowledgeRetrieval> knowledge_; // GeniusAPIServer.hpp:105
```
Note: CLAUDE.md guideline says "unique_ptr throughout, no shared_ptr" but in practice `shared_ptr` is used where multiple components reference the same engine instance.

**No raw new/delete:** All allocation via `std::make_unique` / `std::make_shared`:
```cpp
router_  = std::make_unique<router::RuleBasedRouter>();          // GeniusAPIServer.cpp:112
engine   = std::make_shared<core::MNNInferenceEngine>( engine_cfg ); // GeniusAPIServer.cpp:72
identity_ = std::make_shared<security::NodeIdentity>();          // GeniusAPIServer.cpp:50
```

**Destructors:** Virtual in polymorphic bases; use `= default`:
```cpp
virtual ~ISpecialist() = default;       // src/specialists/ISpecialist.hpp:24
~GeniusAPIServer();                      // non-default when cleanup needed
```

---

## Design Patterns Observed

| Pattern | Where | Example |
|---------|-------|---------|
| Strategy (via interface) | Router, InferenceEngine | `IRouter` → `RuleBasedRouter` |
| Strategy (enum dispatch) | Consensus | `Strategy::WeightedVoting` vs `BestWeightedScore` |
| Config struct | All major classes | `RuleBasedRouter::Config`, `WeightedConsensus::Config` |
| RAII | All resource management | `ReputationStorage` opens/closes DB |
| Pimpl (forward declaration) | MNNInferenceEngine | Forward-declares `MNN::Interpreter`, `MNN::Session` |
| Factory (logger) | Per-TU anonymous ns | `RouterLogger()`, `ServerLogger()` |
| Template Method | Abstract interfaces | `ISpecialist::Process()` → Math/Grammar implementations |
| CRDT (LWW) | Reputation sync | `ReputationCRDT` with Last-Writer-Wins merge |

---

## Special Directories

**`gnus-poc/`:** Proof-of-concept artifacts — not part of the main build. Contains exploration scripts/models.

**`build/`:** Build output directory. Platform/configuration subdirectories: `build/OSX/Debug/`, `build/OSX/Release/`.

**`proto/`:** Protobuf definitions (`.proto` files). Compiled at build time if Protobuf found.

**`cmake_genius/`:** Custom CMake modules (e.g., `FindThirdparty.cmake`).

**`AgentDocs/`:** AI agent guidance documents (SPRINT_PLAN.md, Architecture.md, etc.).

---

*Convention analysis: 2026-05-26*
