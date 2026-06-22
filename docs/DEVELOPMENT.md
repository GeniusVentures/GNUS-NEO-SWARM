<!-- GSD: generated 2026-06-17 -->
# Development

## Project Layout

```
├── src/                    # Source code
│   ├── main.cpp            # CLI entry point
│   ├── api/                # ApiServer (composition root)
│   ├── common/             # Shared types, errors, logging
│   ├── core/               # MNN engine, FP4, tokenizer, SGProcessing
│   ├── knowledge/          # Knowledge retrieval and validation
│   ├── network/            # P2P networking, SuperGenius client
│   ├── reputation/         # Peer reputation system
│   ├── router/             # Task routing
│   ├── security/           # Crypto identity and signing
│   └── specialists/        # Domain-specific models
├── test/                   # Tests (mirrors src/ structure)
├── build/                  # Platform-specific build dirs
├── cmake/                  # CMake helpers
├── thirdparty/             # Pre-built dependencies
└── docs/                   # Documentation
```

## Code Style

Based on Microsoft style with modifications (see `.clang-format`):

- **Indent:** 4 spaces
- **Line length:** 120 characters max
- **Naming:** PascalCase for classes/methods, camelCase for variables
- **Constants:** `kCamelCase` for `constexpr`, `ALL_CAPS` for macros
- **Braces:** Allman style (each on own line)
- **Parentheses:** Space after `(` and before `)`: `if ( condition )`
- **Member variables:** `m_` prefix: `m_modelPath`, `m_running`

## Building

```bash
cd build/<Platform>/<BuildType>
cmake .. -G "Ninja" -DCMAKE_BUILD_TYPE=<BuildType>
ninja
```

### AddressSanitizer

```bash
cd build/OSX/Debug
cmake .. -G "Ninja" -DCMAKE_BUILD_TYPE=Debug -DSANITIZE_ADDRESS=ON
ninja
```

## Module Structure

Each module under `src/` is a static library (`neoswarm_<module>`):

```
src/<module>/
├── CMakeLists.txt          # Build definition
├── <component>.hpp         # Public header
├── <component>.cpp         # Implementation
└── test/                   # (optional) module-specific tests
```

## Adding a New Module

1. Create `src/<module>/` directory
2. Add `CMakeLists.txt` with `add_library(neoswarm_<module> STATIC ...)`
3. Add `add_subdirectory(src/<module>)` to `src/CMakeLists.txt`
4. Link against `neoswarm_common` and any other dependencies
5. Add to `neoswarm_api` target_link_libraries in `src/api/CMakeLists.txt`

## Error Handling

Uses `outcome::result<T>` for error propagation (no exceptions in hot paths):

```cpp
outcome::result<int> ProcessInput( const std::string& input )
{
    if ( input.empty() )
    {
        return outcome::failure( Error::InvalidInput );
    }
    return outcome::success( 42 );
}

// Caller uses BOOST_OUTCOME_TRY
auto result = BOOST_OUTCOME_TRY( ProcessInput( data ) );
```

Error codes are defined in `src/common/error.hpp`.

## Logging

All diagnostic output uses spdlog:

```cpp
#include "common/logging.hpp"

auto logger = neoswarm::CreateLogger( "MyModule" );
logger->info( "Processing request: {}", requestId );
logger->debug( "Token count: {}", tokens.size() );
logger->error( "Failed to load model: {}", path );
```

Debug output is enabled with `--verbose` at runtime.

## Testing

Tests use Google Test in `test/`:

```bash
cd build/OSX/Debug
ninja test
```

### Test Structure

```
test/
├── security/           # NodeIdentity, MessageSigning tests
├── router/             # RuleBasedRouter tests
├── knowledge/          # KnowledgeRetrieval, FactValidation tests
├── network/            # P2P, SuperGeniusClient tests
├── reputation/         # ReputationScoring, Storage tests
├── ffi/                # FFI layer tests
├── integration/        # End-to-end integration tests
└── benchmark/          # Performance benchmarks
```

### Writing Tests

```cpp
#include <gtest/gtest.h>
#include "router/rule_based_router.hpp"

TEST( RuleBasedRouterTest, RoutesGrammarToSpecialist )
{
    neoswarm::router::RuleBasedRouter router;
    neoswarm::Task task;
    task.prompt = "Fix the grammar: he go to store";

    auto decision = router.Route( task );

    EXPECT_EQ( decision.target, neoswarm::RouteTarget::GrammarSpecialist );
}
```

## Dependencies

All dependencies are in `thirdparty/`. Do not use system-installed libraries. When adding a new dependency:

1. Add it to the thirdparty build system
2. Add `find_package()` or `find_library()` in `cmake/CommonBuildParameters.cmake`
3. Link against the imported target in your module's `CMakeLists.txt`

## Pull Requests

- Max 300 lines changed per PR
- Functions max ~100 lines
- No deep nesting (>3 levels): extract a helper function
- Single exit point per function
- No magic numbers — use named constants
- Run tests, linter, and formatter before committing
