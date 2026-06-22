# Testing Patterns

**Analysis Date:** 2026-05-27

## Test Framework

**Runner:**
- Google Test (GTest)
- Discovered via `find_package(GTest QUIET)` with manual fallback in `test/CMakeLists.txt`
- `gtest_main` linked for automatic `main()` entry point

**Config:** `test/CMakeLists.txt`

**Run Commands (from build directory):**
```bash
ctest                              # Run all registered tests
ctest -R test_router               # Run specific test by name
ctest --output-on-failure          # Show output on failure
```

**Build from scratch:**
```bash
cd build/OSX/Debug
cmake .. -G "Ninja" -DCMAKE_BUILD_TYPE=Debug
ninja
ctest
```

## Test Registration

Tests are registered via a custom CMake macro defined in `test/CMakeLists.txt`:

```cmake
macro(genius_test name sources libs)
    add_executable(${name} ${sources})
    target_link_libraries(${name} PRIVATE
        ${libs}
        GTest::GTest
        GTest::Main
    )
    target_compile_definitions(${name} PRIVATE
        SUPERGENIUS_TEST_DATA_DIR="${SUPERGENIUS_TEST_DATA_DIR}"
    )
    add_test(NAME ${name} COMMAND ${name})
endmacro()
```

Usage:
```cmake
genius_test(test_fp4_codec             core/test_fp4_codec.cpp                          "genius_core")
genius_test(test_router                router/test_router.cpp                           "genius_router;genius_common")
genius_test(test_reputation            reputation/test_reputation.cpp                   "genius_reputation;genius_common")
genius_test(test_pipeline              integration/test_pipeline.cpp                    "genius_api")
genius_test(test_sgprocessing_pipeline integration/test_sgprocessing_pipeline.cpp       "genius_api")
```

Each test is a standalone executable linked against the relevant platform libraries.

## Test File Organization

**Location:**
- Tests live under `test/<module>/` for unit tests and `test/integration/` for integration tests
- Tests are **not** co-located with source files — they are in a separate `test/` tree

**Naming:**
- Unit tests: `test_<module>.cpp` (e.g., `test_router.cpp`, `test_fp4_codec.cpp`, `test_reputation.cpp`)
- Integration tests: `test_<component>.cpp` (e.g., `test_pipeline.cpp`, `test_sgprocessing_pipeline.cpp`)

**Directory structure:**
```
test/
├── CMakeLists.txt              # Test registration and GTest discovery
├── benchmark/
│   ├── CMakeLists.txt          # Benchmarks (not part of CTest)
│   └── bench_mnn_llm.cpp       # MNN LLM benchmark
├── core/
│   └── test_fp4_codec.cpp      # FP4 codec unit tests
├── router/
│   └── test_router.cpp         # Router unit tests
├── reputation/
│   └── test_reputation.cpp     # Reputation unit tests
└── integration/
    ├── test_pipeline.cpp        # Full pipeline integration tests
    └── test_sgprocessing_pipeline.cpp  # SGProcessing integration tests
```

## Test Structure

### Unit Tests (Standalone)

Unit tests use `TEST()` macro directly — no fixtures when testing stateless classes:

```cpp
TEST( PromptAnalyzer, NumericDensityHigh )
{
    PromptAnalyzer analyzer;
    auto f = analyzer.Analyze( "What is 847 × 963 + 12.5 / 3?" );
    EXPECT_GT( f.numeric_density_, 0.2f );
}

TEST( FP4Codec, RoundtripSmallMatrix )
{
    FP4Codec codec;
    const size_t       rows    = 4;
    const size_t       cols    = 4;
    std::vector<float> weights = { 0.1f, -0.2f, 0.5f, -0.8f, /*...*/ };

    auto enc_res = codec.Encode( weights.data(), rows, cols );
    ASSERT_TRUE( enc_res.has_value() );  // abort if encoding fails

    std::vector<float> decoded( rows * cols );
    auto dec_res = codec.Decode( enc_res.value(), decoded.data() );
    ASSERT_TRUE( dec_res.has_value() );

    float mse = 0.0f;
    for ( size_t i = 0; i < weights.size(); ++i )
    {
        float diff = weights[i] - decoded[i];
        mse += diff * diff;
    }
    mse /= static_cast<float>( weights.size() );
    EXPECT_LT( mse, 0.05f ) << "MSE too high: " << mse;
}
```

### Integration Tests (Fixture-based)

Integration tests that need setup/configuration use `::testing::Test` fixtures:

```cpp
class PipelineTest : public ::testing::Test
{
protected:
    void SetUp() override
    {
        GeniusAPIServer::Config cfg;
        cfg.model_path_         = "";  // stub mode
        cfg.enable_network_     = false;
        cfg.enable_knowledge_   = true;
        cfg.reputation_db_path_ = ":memory:";
        cfg.node_key_file_      = "/tmp/test_genius_node.key";

        server_ = std::make_unique<GeniusAPIServer>( cfg );
        ASSERT_TRUE( server_->Initialize().has_value() );
    }

    std::unique_ptr<GeniusAPIServer> server_;
};

TEST_F( PipelineTest, SingleNodeMode )
{
    Task task;
    task.prompt_     = "Tell me about the history of Rome.";
    task.mode_       = ExecutionMode::SingleNode;
    task.max_tokens_ = 32;

    auto res = server_->Process( task );
    ASSERT_TRUE( res.has_value() );
    EXPECT_EQ( res.value().mode_used_, ExecutionMode::SingleNode );
    EXPECT_FALSE( res.value().task_id_.empty() );
}
```

## Assertion Patterns

**For `outcome::result<T>` checking:**
```cpp
ASSERT_TRUE( result.has_value() );    // fatal if error — use when subsequent code depends on value
EXPECT_TRUE( result.has_value() );    // non-fatal — use when test can continue
EXPECT_FALSE( result.has_value() );   // expect failure (e.g., invalid input)
```

**For value comparison:**
```cpp
EXPECT_GT( f.numeric_density_, 0.2f );     // greater than
EXPECT_LT( mse, 0.02f );                   // less than
EXPECT_EQ( res.value().target_, RouteTarget::CorePlusMath );   // equality
EXPECT_NE( res.value().route_used_, RouteTarget::CoreOnly );    // inequality
```

**For floating-point:**
```cpp
EXPECT_NEAR( v, 0.0f, 1e-5f );              // near with absolute error
EXPECT_DOUBLE_EQ( got->global_score_, 0.8 ); // exact double equality (use sparingly)
```

**For range checks:**
```cpp
EXPECT_GE( res.value().confidence_, 0.0f );  // greater or equal
EXPECT_LE( res.value().confidence_, 1.0f );  // less or equal
```

**With messages:**
```cpp
EXPECT_LT( mse, 0.05f ) << "MSE too high: " << mse;
```

## Mocking

- **No mocking framework detected** (no Google Mock, no trompeloeil, no FakeIt)
- Tests use **real instances** of components with stub configuration:
  - `model_path_ = ""` or `enable_network_ = false` for stub/inactive modes
  - In-memory databases: `reputation_db_path_ = ":memory:"`
  - Temp file paths: `/tmp/test_genius_node.key`
  - `SetStubMode()` method on `MNNInferenceEngine` to bypass model loading

**Stub pattern used in production code:**
```cpp
#ifdef GENIUS_HAS_SGPROCESSING
    // real implementation
#else
    BridgeLogger()->warn( "SGProcessingManager not compiled in — stub mode" );
    return outcome::success( std::vector<uint8_t>{} );
#endif
```

**What to mock:** External services (network, databases), heavy models, hardware-dependent code
**What NOT to mock:** Pure logic (routers, analyzers, scoring algorithms) — test with real instances

## Fixtures and Factories

**Test data creation:**
- Inline data: Simple vectors and structs constructed directly in test bodies
- Random data: `std::mt19937` with fixed seed (42) for reproducibility:
  ```cpp
  std::mt19937                    rng( 42 );
  std::normal_distribution<float> dist( 0.0f, 0.5f );
  for ( auto &w : weights ) w = dist( rng );
  ```

**Unique test resources:**
```cpp
static std::string UniqueDbPath( const std::string &tag )
{
    return "/tmp/genius_test_" + tag + "_"
           + std::to_string(
               std::chrono::steady_clock::now().time_since_epoch().count() );
}
```

**Pre-existing test data:**
- SGProcessing integration tests load binary test data from `SuperGenius/test/src/processing_datatypes/` directory, referenced via `SUPERGENIUS_TEST_DATA_DIR` compile definition

## Test Types

### Unit Tests
- **Scope:** Single class or component
- **Location:** `test/<module>/test_<module>.cpp`
- **Examples:** `test_fp4_codec.cpp` — tests `FP4Codec` in isolation; `test_router.cpp` — tests `PromptAnalyzer` and `RuleBasedRouter`
- **Pattern:** Instantiate class directly, call methods, verify results
- **Covers:** Happy path, error cases, edge cases (zero weights, null input, empty input)

### Integration Tests
- **Scope:** Multiple components working together through the `GeniusAPIServer` pipeline
- **Location:** `test/integration/test_pipeline.cpp`, `test/integration/test_sgprocessing_pipeline.cpp`
- **Fixture:** `PipelineTest` sets up a configured `GeniusAPIServer` in stub mode
- **Covers:** Mode routing (single/specialist/swarm), task ID generation, latency tracking, routing auto-detection

### Benchmarks
- **Location:** `test/benchmark/bench_mnn_llm.cpp`
- **Not part of CTest** — run manually: `./build/OSX/Debug/test/benchmark/bench_mnn_llm`
- **Measures:** Prefill latency, decode throughput (tokens/sec), peak memory usage

## Coverage

- **No coverage tooling detected** — no `gcov`, `lcov`, or `--coverage` flag in test build configuration
- No explicit coverage target or threshold enforced

## Testing Practices

**Test naming convention:**
```
TEST( ClassName, DescriptiveTestName )
TEST_F( FixtureClassName, DescriptiveTestName )
```
Names describe behavior: `NumericDensityHigh`, `RoundtripSmallMatrix`, `ScoreClampedToRange`, `LWWKeepsLatest`, `SwarmFallsBackToSingleWithoutNetwork`

**Test independence:**
- Each test creates its own instances (no shared state)
- Tests in `test_reputation.cpp` create unique DB paths per test using `UniqueDbPath()` to avoid cross-test contamination

**Error path testing:**
```cpp
TEST( FP4Codec, InvalidInput )
{
    FP4Codec codec;
    auto res = codec.Encode( nullptr, 4, 4 );
    EXPECT_FALSE( res.has_value() );
}
```

**Property-based checks:**
```cpp
TEST( RuleBasedRouter, ConfidenceInRange )
{
    RuleBasedRouter router;
    Task            task;
    task.prompt_ = "What is 2 + 2?";
    task.mode_   = ExecutionMode::SingleNode;

    auto res = router.Route( task );
    ASSERT_TRUE( res.has_value() );
    EXPECT_GE( res.value().confidence_, 0.0f );
    EXPECT_LE( res.value().confidence_, 1.0f );
}
```

**CRDT/LWW (Last-Write-Wins) testing pattern:**
```cpp
TEST( ReputationCRDT, LWWKeepsLatest )
{
    ReputationCRDT crdt;
    // Merge older entry, then newer entry
    // Verify newer wins
}

TEST( ReputationCRDT, LWWIgnoresOlder )
{
    ReputationCRDT crdt;
    // Merge newer entry, then older entry
    // Verify newer still wins
}
```

## Adding New Tests

1. **Create file:** `test/<module>/test_<module>.cpp` for unit tests or `test/integration/test_<feature>.cpp` for integration tests
2. **Include GTest:** `#include <gtest/gtest.h>` plus the header(s) under test
3. **Use namespaces:** `using namespace sgns::neoswarm;` and sub-namespaces as needed
4. **Write tests:** `TEST()` for stateless, `TEST_F()` with fixture for shared setup
5. **Register in CMake:** Add a `genius_test()` call in `test/CMakeLists.txt`:
   ```cmake
   genius_test(test_new_feature test/new_module/test_new_feature.cpp "genius_new_module;genius_common")
   ```
6. **Run:** Build with `ninja` and run with `ctest -R test_new_feature`

**Mandatory (from CLAUDE.md):**
- Use `ASSERT_TRUE( result.has_value() )` before accessing `.value()` on `outcome::result`
- Never use `std::this_thread::sleep_for` in tests — if wait conditions are needed, use the project's condition_variable/polling patterns
- Target ≥80% coverage on new code

---

*Testing analysis: 2026-05-27*
