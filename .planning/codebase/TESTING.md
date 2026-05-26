# Testing Patterns

**Analysis Date:** 2026-05-26

## Test Framework

### C++ — Google Test (GTest)

**Runner:** Google Test (bundled as thirdparty dependency)
- Discovery: `find_package(GTest QUIET)` with fallback to `thirdparty/GTest/googletest`
- Config: `test/CMakeLists.txt`
- Link targets: `GTest::GTest` + `GTest::Main` (auto-provides `main()`)

**Assertion Library:** Built-in GTest assertions:
- `ASSERT_TRUE` / `ASSERT_FALSE` — fatal on failure
- `EXPECT_EQ` / `EXPECT_NE` / `EXPECT_GT` / `EXPECT_LT` / `EXPECT_GE` / `EXPECT_LE` / `EXPECT_NEAR` — non-fatal
- `EXPECT_DOUBLE_EQ` — for floating-point exact match
- `GTEST_SKIP()` — conditional skip (e.g., missing test data)

**Run Commands:**
```bash
# Build with tests enabled (default ON)
cd build/<Platform>/<BuildType>
cmake .. -G "Ninja" -DCMAKE_BUILD_TYPE=Debug
ninja

# Run all tests
ctest --test-dir build/<Platform>/<BuildType>

# Run specific test binary
./test_fp4_codec
./test_router
./test_reputation
./test_pipeline
```

**Enable/Disable Tests:**
```cmake
option(GENIUS_BUILD_TESTS "Build unit and integration tests" ON)
```

**CMake Test Registration Macro** (from `test/CMakeLists.txt:42-53`):
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

### Dart/Flutter — flutter_test

**Runner:** Built-in `flutter_test` SDK package
**Assertion Library:** `package:flutter_test/flutter_test.dart`
- `expect(actual, matcher)` — primary assertion
- Matchers: `findsOneWidget`, `findsNothing`, `isNotNull`, etc.

**Run Commands:**
```bash
cd flutter_app && flutter test
```

---

## Test File Organization

### C++

**Location:** `test/` directory mirroring source structure:
```
test/
├── CMakeLists.txt              # Test build config + genius_test() macro
├── core/
│   └── test_fp4_codec.cpp      # Unit: FP4 codec
├── router/
│   └── test_router.cpp         # Unit: PromptAnalyzer + RuleBasedRouter
├── reputation/
│   └── test_reputation.cpp     # Unit: Scoring, Consensus, CRDT, Storage
└── integration/
    ├── test_pipeline.cpp        # Integration: Full pipeline in stub mode
    └── test_sgprocessing_pipeline.cpp  # Integration: SGProcessing flow
```

**Naming:** `test_[component].cpp` within `test/[module]/` directory.
- Unit tests: `test/core/test_fp4_codec.cpp`, `test/router/test_router.cpp`
- Integration tests: `test/integration/test_pipeline.cpp`

**CMake Library Links** (from `test/CMakeLists.txt:55-59`):
```cmake
genius_test(test_fp4_codec             core/test_fp4_codec.cpp              "genius_core")
genius_test(test_router                router/test_router.cpp               "genius_router;genius_common")
genius_test(test_reputation            reputation/test_reputation.cpp       "genius_reputation;genius_common")
genius_test(test_pipeline              integration/test_pipeline.cpp        "genius_api")
genius_test(test_sgprocessing_pipeline integration/test_sgprocessing_pipeline.cpp  "genius_api")
```

**Test count:** 5 test executables, ~45 individual test cases.

### Dart/Flutter

**Location:**
- `flutter_app/test/widget_test.dart` — Widget test for counter app
- `ui/test/` — Expected structure but files not observed

**Naming:** `[name]_test.dart` in `test/` directory (standard Dart convention).

---

## Test Structure

### C++ — GTest Styles

**Simple test cases** (`test/core/test_fp4_codec.cpp`):
```cpp
TEST( FP4Codec, RoundtripSmallMatrix )
{
    FP4Codec codec;
    const size_t       rows    = 4;
    const size_t       cols    = 4;
    std::vector<float> weights = { 0.1f, -0.2f, 0.5f, -0.8f, /* ... */ };

    auto enc_res = codec.Encode( weights.data(), rows, cols );
    ASSERT_TRUE( enc_res.has_value() );

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

**Test Fixtures** (`test/integration/test_pipeline.cpp`):
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
    task.prompt_      = "Tell me about the history of Rome.";
    task.mode_        = ExecutionMode::SingleNode;
    task.max_tokens_  = 32;
    task.temperature_ = 0.7f;

    auto res = server_->Process( task );
    ASSERT_TRUE( res.has_value() );
    EXPECT_EQ( res.value().mode_used_, ExecutionMode::SingleNode );
    EXPECT_FALSE( res.value().task_id_.empty() );
}
```

**Key patterns:**
- `SetUp()` for test initialization (no `TearDown()` currently observed)
- `ASSERT_TRUE` for critical setup checks; `EXPECT_*` for assertions
- Message suffix with `<<` for diagnostic output: `<< "MSE too high: " << mse`
- `GTEST_SKIP()` for conditional test skip: `GTEST_SKIP() << "Test data not found at: " << data_dir;`
- Direct construction of test subjects (no mocking framework)

**File header (Doxygen block):**
```cpp
/**
 * @file       test_pipeline.cpp
 * @brief      Integration tests — full pipeline in stub mode
 * @date       2026-05-08
 * @author     Subaskar S (ssivakumar@gnus.ai)
 */
```

**Namespace usage in tests:**
```cpp
using namespace sgns::neoswarm;
using namespace sgns::neoswarm::router;
```
Namespace `using` directives at file scope within test files only.

### Dart/Flutter

```dart
void main() {
  testWidgets('Counter increments smoke test', (WidgetTester tester) async {
    await tester.pumpWidget(const MyApp());
    expect(find.text('0'), findsOneWidget);
    expect(find.text('1'), findsNothing);

    await tester.tap(find.byIcon(Icons.add));
    await tester.pump();

    expect(find.text('0'), findsNothing);
    expect(find.text('1'), findsOneWidget);
  });
}
```

---

## Mocking

### C++

**No mocking framework detected.** The codebase currently uses:
- **Stub mode:** `MNNInferenceEngine::SetStubMode()` for testing without real models (`test/integration/test_pipeline.cpp:20`)
- **In-memory stores:** `cfg.reputation_db_path_ = ":memory:"` for ReputationStorage testing
- **Direct construction:** Test subjects created directly without dependency injection fakes

**Stub mode pattern:**
```cpp
cfg.model_path_ = "";  // empty path triggers stub mode
engine->SetStubMode();  // explicit stub enable
```

**When a mock would be needed:** For testing network interaction (`P2PNode`), SGProcessingManager integration, and streaming inference — these currently have limited or conditional test coverage (guarded by `#ifdef GENIUS_HAS_SGPROCESSING`).

**CLAUDE.md guidance:** "Prefer Google Test + the project's 'wait condition testing templates' (condition_variable / polling patterns) in tests. NEVER use std::this_thread::sleep_for in tests." — wait-condition templates not yet observed in the actual test files; current tests are synchronous.

### Dart/Flutter

**No mocking framework detected.** `flutter_app/test/widget_test.dart` uses `WidgetTester` directly. The `flutter_slm_bridge` has no test files.

---

## Fixtures and Factories

### C++

**Test data patterns:**
- **Inline literals:** `test_fp4_codec.cpp` — hardcoded float vectors
- **Random with fixed seed:** `std::mt19937 rng( 42 );` for reproducible random data
- **In-memory DB:** `":memory:"` for SQLite-backed ReputationStorage tests
- **Helper functions in anonymous namespace:** `UniqueDbPath()`, `TestDataPath()`, `FileExists()`, `ReadFloatFile()` in `test/integration/test_sgprocessing_pipeline.cpp:52-79`
- **External test data:** `SUPERGENIUS_TEST_DATA_DIR` macro points to `SuperGenius/test/src/processing_datatypes/`

**Fixture-less setup (in-test):**
```cpp
// From test/reputation/test_reputation.cpp:202-217
TEST( ReputationStorage, PutAndGet )
{
    ReputationStorage storage( UniqueDbPath( "putget" ) );
    ASSERT_TRUE( storage.Open().has_value() );

    NodeReputation r;
    r.identity_key_ = "test-node";
    r.global_score_ = 0.65;
    r.task_count_   = 10;
    ASSERT_TRUE( storage.Put( r ).has_value() );

    auto got = storage.Get( "test-node" );
    ASSERT_TRUE( got.has_value() );
    EXPECT_DOUBLE_EQ( got.value().global_score_, 0.65 );
}
```

---

## Coverage

**Requirements:** Target ≥80% coverage on new code (per CLAUDE.md:31).

**Coverage tooling:** Not configured in CMakeLists.txt. No coverage reporting targets currently defined.

**View coverage:** Not yet instrumented. Would require adding `--coverage` flags or similar compiler instrumentation.

---

## Test Types

### Unit Tests

**Scope:** Individual modules tested in isolation:
- `test_fp4_codec.cpp` — FP4 quantization encode/decode, macroblock count, error handling
- `test_router.cpp` — `PromptAnalyzer` feature extraction + `RuleBasedRouter` routing decisions
- `test_reputation.cpp` — Scoring formulas, weighted consensus, CRDT merge semantics, DB storage

**Approach:** Direct instantiation, call method, assert result. No stubs needed for IO-less components.

### Integration Tests

**Scope:** Cross-module pipeline verification:
- `test_pipeline.cpp` — `GeniusAPIServer` in stub mode testing all three execution modes (SingleNode, Specialist, Swarm)
- `test_sgprocessing_pipeline.cpp` — NeoSwarm → SGProcessingManager → TensorInterpreter end-to-end flow

**Approach:** Test fixture creates `GeniusAPIServer` with stub config, tests real pipeline orchestration paths. SGProcessing tests conditionally compiled (`#ifdef GENIUS_HAS_SGPROCESSING`) and auto-skipped if test data unavailable.

### E2E Tests

**Not used.** No end-to-end tests detected. The `genius_node.cpp` CLI entry point has no corresponding test.

---

## Common Patterns

### C++ — Async/Outcome Testing

No async testing patterns observed. All current tests are synchronous.

### Outcome Error Testing:
```cpp
// Testing error cases
TEST( FP4Codec, InvalidInput )
{
    FP4Codec codec;
    auto res = codec.Encode( nullptr, 4, 4 );
    EXPECT_FALSE( res.has_value() );
}

// Testing NOT_FOUND
TEST( ReputationStorage, GetNotFound )
{
    ReputationStorage storage( UniqueDbPath( "notfound" ) );
    ASSERT_TRUE( storage.Open().has_value() );
    EXPECT_FALSE( storage.Get( "nonexistent" ).has_value() );
}
```

### Bound/range Testing:
```cpp
TEST( RuleBasedRouter, ConfidenceInRange )
{
    RuleBasedRouter router;
    Task task;
    task.prompt_ = "What is 2 + 2?";
    task.mode_   = ExecutionMode::SingleNode;

    auto res = router.Route( task );
    ASSERT_TRUE( res.has_value() );
    EXPECT_GE( res.value().confidence_, 0.0f );
    EXPECT_LE( res.value().confidence_, 1.0f );
}
```

### Serialization Roundtrip Testing:
```cpp
TEST( ReputationCRDT, SerializeDeserializeRoundtrip )
{
    ReputationCRDT crdt1;
    NodeReputation r;
    r.identity_key_    = "node-X";
    r.global_score_    = 0.75;
    r.task_count_      = 42;
    r.last_updated_ms_ = 99999;
    crdt1.Merge( r );

    ReputationCRDT crdt2;
    crdt2.DeserializeAndMerge( crdt1.Serialize() );

    auto got = crdt2.Get( "node-X" );
    ASSERT_TRUE( got.has_value() );
    EXPECT_DOUBLE_EQ( got->global_score_, 0.75 );
    EXPECT_EQ( got->task_count_, 42u );
}
```

### Large-scale / Stress Testing (FP4 codec):
```cpp
TEST( FP4Codec, RoundtripLargeMatrix )
{
    // 128×128 matrix with normal-distributed weights, deterministic RNG
    std::mt19937               rng( 42 );
    std::normal_distribution<float> dist( 0.0f, 0.5f );
    // ...
    EXPECT_LT( mse, 0.02f );
}
```

### Conditional / Skip Testing:
```cpp
if ( !FileExists( data_dir + "float_model.mnn" ) )
{
    GTEST_SKIP() << "Test data not found at: " << data_dir;
}
```

---

## Test Counts (Observed)

| Test Executable | Test Cases | Type |
|----------------|-----------|------|
| `test_fp4_codec` | 6 | Unit |
| `test_router` | 11 | Unit |
| `test_reputation` | 16 | Unit |
| `test_pipeline` | 7 | Integration |
| `test_sgprocessing_pipeline` | 10 (7 unconditional + 3 conditional) | Integration |
| **Total C++** | **~50** | |
| `widget_test.dart` | 1 | Widget (Dart) |
| **Total Dart** | **1** | |

---

## Testing Gaps

1. **No C++ test for core engine** (`MNNInferenceEngine`) — only FP4 codec tested; inference loop unverified
2. **No C++ test for specialists** (`MathSpecialist`, `GrammarSpecialist`) — tested only indirectly via integration pipeline
3. **No C++ test for API server initialization** — `Initialize()` only called via fixture setup, no error-path tests
4. **No C++ test for network layer** (`P2PNode`, `ResultAggregation`) — untested; network disabled in integration tests
5. **No C++ test for knowledge layer** (`KnowledgeRetrieval`, `ContextInjection`, `FactValidation`) — untested
6. **No C++ test for security** (`NodeIdentity`, `MessageSigning`) — untested
7. **No Dart test for flutter_slm_bridge** — FFI bridge has zero tests
8. **No Dart test for ui/ chat application** — only template `widget_test.dart` in flutter_app
9. **No benchmarks** — `GENIUS_BUILD_BENCHMARKS` option exists (`CMakeLists.txt:20`) but no `bench/` directory found
10. **No coverage instrumentation** — coverage target stated but no tooling configured

---

*Testing analysis: 2026-05-26*
