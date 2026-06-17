<!-- GSD: generated 2026-06-17 -->
# Testing

## Overview

Tests use Google Test and are organized by module in `test/`. The project targets ≥80% coverage on new code. Tests must be isolated, fast, and deterministic — never use `std::this_thread::sleep_for`.

## Running Tests

```bash
cd build/OSX/Debug
ninja test
```

To run a specific test binary:

```bash
./test/security/test_node_identity
./test/router/test_rule_based_router
```

## Test Structure

```
test/
├── CMakeLists.txt              # Test build definitions
├── security/                   # NodeIdentity, MessageSigning
│   └── test_node_identity.cpp
├── router/                     # RuleBasedRouter
├── knowledge/                  # KnowledgeRetrieval, FactValidation
├── network/                    # P2P, SuperGeniusClient
├── reputation/                 # ReputationScoring, Storage
├── ffi/                        # FFI layer (Flutter bridge)
├── integration/                # End-to-end flows
└── benchmark/                  # Performance benchmarks
```

## Writing Tests

### Basic Test

```cpp
#include <gtest/gtest.h>
#include "security/node_identity.hpp"

TEST( NodeIdentityTest, GeneratesValidKeypair )
{
    neoswarm::security::NodeIdentity identity;

    auto result = identity.Generate();

    ASSERT_TRUE( result.has_value() );
    EXPECT_FALSE( identity.GetPeerId().empty() );
}
```

### Wait Condition Pattern

Instead of `sleep_for`, use condition variables or polling:

```cpp
TEST( P2PNodeTest, ReceivesMessage )
{
    std::mutex mtx;
    std::condition_variable cv;
    bool received = false;

    node.OnMessage( [&]( const auto& msg )
    {
        std::lock_guard<std::mutex> lock( mtx );
        received = true;
        cv.notify_one();
    } );

    sender.Send( testMessage );

    std::unique_lock<std::mutex> lock( mtx );
    ASSERT_TRUE( cv.wait_for( lock, std::chrono::seconds( 5 ),
                              [&] { return received; } ) );
}
```

### Error Testing

```cpp
TEST( NodeIdentityTest, RejectsWrongPassphrase )
{
    neoswarm::security::NodeIdentity identity;
    identity.Generate();
    identity.SaveEncrypted( "/tmp/test.key", "correct-passphrase" );

    neoswarm::security::NodeIdentity loaded;
    auto result = loaded.LoadEncrypted( "/tmp/test.key", "wrong-passphrase" );

    EXPECT_FALSE( result.has_value() );
    EXPECT_EQ( result.error(), neoswarm::Error::IdentityError );
}
```

## Test Categories

| Category | Directory | What It Tests |
|----------|-----------|---------------|
| Security | `test/security/` | Key generation, signing, verification, encryption |
| Router | `test/router/` | Task routing decisions |
| Knowledge | `test/knowledge/` | Fact retrieval, validation, context injection |
| Network | `test/network/` | P2P messaging, SuperGenius client |
| Reputation | `test/reputation/` | Scoring, storage, CRDT sync |
| FFI | `test/ffi/` | Flutter bridge layer |
| Integration | `test/integration/` | End-to-end inference flows |
| Benchmark | `test/benchmark/` | Performance measurements |

## Adding Tests for a New Module

1. Create `test/<module>/` directory
2. Add test source files: `test_<component>.cpp`
3. Add `CMakeLists.txt` with `add_executable` and `target_link_libraries` against `GTest::gtest_main`
4. Add `add_subdirectory(test/<module>)` to `test/CMakeLists.txt`
5. Use `gtest_discover_tests()` for CTest integration

## macOS Keychain

Tests use in-memory secure storage (`MemorySecureStorage`) instead of macOS keychain. This is enabled automatically when `BUILD_TESTING=ON` via the `SGNS_USE_MEMORY_SECURE_STORAGE` compile flag. No keychain prompts should appear during test runs.

## CI/CD

Tests run on every PR. The build matrix covers:

- macOS (clang++)
- Linux (g++)
- Debug and Release builds

AddressSanitizer runs in CI for memory leak detection.
