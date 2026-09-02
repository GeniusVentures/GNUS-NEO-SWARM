# Phase 13: SGFP4 v2 Model Support - Pattern Map

**Mapped:** 2026-09-02
**Files analyzed:** 8 (4 modified + 1 deleted-set + 1 new test + 2 CMake wiring points)
**Analogs found:** 8 / 8

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `SGProcessingManager/src/processors/processing_processor_mnn_tensor.cpp` (SGF-02 null-check + backend resolver) | service (MNN processor) | request-response (per-window batch transform) | same file, `ResolveQuantScale(parameters)` convention at line 194 + existing `nullptr` early-return idiom at lines 202/232/244/258 | exact (self-analog: fixing/extending this exact file using its own established conventions) |
| `SGProcessingManager/test/processors/mnn_tensor_fp4_test.cpp` (SGF-04a rewrite + new negative test SGF-02/D-11) | test (unit) | request-response | same file, `Fp4UltraRecognizedButDecodeUnavailable` TEST + `CallStartProcessing()` helper | exact |
| `GNUS-NEO-SWARM/test/integration/test_sg_connectivity.cpp` (SGF-04b literal fix) | test (integration) | request-response | `test/integration/test_sgprocessing_pipeline.cpp`'s `BuildSchemaJson_Fp4Ultra` (correct reference assertion) | exact |
| `GNUS-NEO-SWARM/src/core/fp4/fp4_codec.hpp` / `.cpp` (SGF-03 delete) | utility (dead code) | transform | n/a — deletion target, no analog needed | n/a |
| `GNUS-NEO-SWARM/test/core/test_fp4_codec.cpp` (SGF-03 delete) | test (unit) | transform | n/a — deletion target | n/a |
| `GNUS-NEO-SWARM/src/core/CMakeLists.txt` (SGF-03: remove line 2) / `GNUS-NEO-SWARM/test/CMakeLists.txt` (SGF-03: remove line 59) | config (CMake) | n/a | same files — single-line removals, no analog needed | n/a |
| New SGFP4 E2E test cases (SGF-01, D-04/D-05/D-07), appended to `test/integration/test_sgprocessing_pipeline.cpp` | test (integration, real-model E2E) | request-response | `Fp4UltraFormat_DispatchesToTensorProcessor` (same file) for dispatch/skip-gate shape; `thirdparty/MNN/test/op/SGFP4ClassicAPITest.cpp` for explicit-CPU-session classic API | role-match (dispatch shape) + exact (classic API mechanics) |
| Committed `.mnn` test asset + recipe doc (D-06) wiring | config (CMake test-fixture vendoring) | file-I/O | `test/CMakeLists.txt`'s existing `add_custom_command(TARGET test_sgprocessing_pipeline POST_BUILD COMMAND copy_if_different ...)` block for `processing_datatypes/*` | exact |

## Pattern Assignments

### `SGProcessingManager/src/processors/processing_processor_mnn_tensor.cpp` (service, request-response)

**Analog:** itself — extend two existing, already-established conventions in the same file.

**Imports pattern** (lines 1-11):
```cpp
#include "processors/processing_processor_mnn_tensor.hpp"
#include "processingbase/vulkan_init_guard.hpp"

#include <algorithm>
#include <cstdint>
#include <cstring>
#include <mutex>
#include <openssl/sha.h>
#include <MNN/FP4DequantUtils.hpp>
#include "util/sha256.hpp"
#include "util/quantization.hpp"
```
No new includes required for SGF-02 (null-check uses existing `ProcessingResult`/`ProcessingError` types already used elsewhere in the file). The backend resolver should live in `include/util/quantization.hpp`'s file family (or a new sibling header) and be included the same way `util/quantization.hpp` is.

**Existing schema-parameter-resolution pattern to mirror for the new backend resolver** (line 194, inside `StartProcessing()`):
```cpp
const float scale = sgprocmanagerquant::ResolveQuantScale( parameters );
```
`ResolveQuantScale`'s full doc/contract (from `include/util/quantization.hpp` lines 1-30):
```cpp
namespace sgns::sgprocmanagerquant
{
    /// ... resolves a job schema-declared "quantScale" entry from the generic
    /// `parameters` array, mirroring the existing find-by-name-in-parameters
    /// convention (ParseLayout / ResolveUniforms).
    /// Falls back to the exact v2.1 constant 32768.0f ... when `parameters` is
    /// null, no entry named "quantScale" of type FLOAT exists, ...
    ///
    /// @param parameters Job schema's generic parameters array, or nullptr.
    /// @return The validated, schema-declared scale, or 32768.0f on any
    ///         invalid/missing declaration.
    float ResolveQuantScale( const std::vector<sgns::Parameter> *parameters );

    int ResolveByteQuantMode( const std::vector<sgns::Parameter> *parameters );
```
**New resolver to add, following this exact shape** (find-by-name-in-`parameters`, safe fallback to today's behavior):
```cpp
// New, analogous resolver (naming at implementer's discretion, e.g. in
// util/quantization.hpp or a new util/backend.hpp):
//   MNNForward ResolveMnnBackend( const std::vector<sgns::Parameter> *parameters );
// Falls back to MNN_FORWARD_VULKAN (today's exact hardcoded behavior) when
// absent/invalid/unrecognized string -- additive, non-breaking for every
// existing caller/test that doesn't pass the new "backend" parameter.
```
Call site to update in `StartProcessing()` (line 194, alongside the existing `scale` resolution):
```cpp
const float scale = sgprocmanagerquant::ResolveQuantScale( parameters );
const MNN::MNNForwardType backendType = sgprocmanagerquant::ResolveMnnBackend( parameters ); // NEW
```
`Process()`'s signature needs the resolved type threaded through (currently `Process( patch, modelFileBytes, patchLength )` at line ~334) and its body updated at the single hardcoded line:
```cpp
// Current (line ~478 in this excerpt, "config.type = MNN_FORWARD_VULKAN;"):
MNN::ScheduleConfig config;
config.type = MNN_FORWARD_VULKAN;
config.numThread = 4;
config.backendConfig = nullptr;
// New: config.type = backendType; (parameter threaded in from StartProcessing)
```

**Existing null-check / early-return idiom to mirror for SGF-02** (representative examples already in this file):
```cpp
if ( !proc.get_dimensions() || !proc.get_dimensions()->get_width() )
{
    m_logger->error( "Tensor input missing width" );
    return ProcessingResult{};
}
```
and the structured-error variant (used for the `CANCELLED` case):
```cpp
return ProcessingResult{ {}, nullptr, {}, ProcessingError{ ProcessingErrorStage::CANCELLED, "Tensor pass cancelled" } };
```
**The unchecked call site to fix** (inside the per-window loop, currently no null-check):
```cpp
auto procresults = Process( patch, modelFileBytes, patchLength );
const float *data = procresults->host<float>();          // <-- add null-check before this line
size_t dataSize = procresults->elementSize() * sizeof( float );
```
**Fix shape, mirroring the file's own structured-error convention:**
```cpp
auto procresults = Process( patch, modelFileBytes, patchLength );
if ( !procresults )
{
    RunTeardown();
    return ProcessingResult{ {}, nullptr, {},
        ProcessingError{ ProcessingErrorStage::FORMAT_UNSUPPORTED,
                         "MNN_Tensor::Process returned null (malformed or incompatible model)" } };
}
const float *data = procresults->host<float>();
```
(Exact `ProcessingErrorStage` value and message text are implementer's discretion per RESEARCH.md Finding 6 — `FORMAT_UNSUPPORTED` shown above matches the stage already used by `mnn_tensor_fp4_test.cpp`'s existing FP4_ULTRA test for a comparable "structured failure, no crash" case.)

**`Process()`'s 4 null-return paths** (full function body, lines 466-518 — needed context for placing the `config.type` change and understanding all 4 places a null can originate):
```cpp
std::unique_ptr<MNN::Tensor> MNN_Tensor::Process( const std::vector<float> &signalData,
                                                  std::vector<uint8_t>    &modelFile,
                                                  int                      length )
{
    auto interpreter = std::shared_ptr<MNN::Interpreter>(
        MNN::Interpreter::createFromBuffer( modelFile.data(), modelFile.size() ) );
    if ( !interpreter )
    {
        m_logger->error( "Failed to create MNN interpreter from buffer" );
        return nullptr;                                    // (1) malformed model bytes -- SGF-02's negative test target
    }

    MNN::ScheduleConfig config;
    config.type = MNN_FORWARD_VULKAN;                       // <-- Finding 3: make configurable
    config.numThread = 4;
    config.backendConfig = nullptr;

    MNN::Session *session = nullptr;
    {
        std::lock_guard<std::mutex> lock( sgns::sgprocessing::VulkanInitMutex() );
        session = interpreter->createSession( config );
    }
    if ( !session )
    {
        m_logger->error( "Failed to create MNN session" );
        return nullptr;                                     // (2) session creation failure
    }

    PushTeardown( [interpreter, session]() { interpreter->releaseSession( session ); } );

    auto inputTensor = interpreter->getSessionInput( session, nullptr );
    if ( !inputTensor )
    {
        m_logger->error( "Failed to get input tensor" );
        return nullptr;                                     // (3) no input tensor
    }

    MNN::Tensor inputTensorUser( inputTensor, inputTensor->getDimensionType() );
    auto inputPtr = inputTensorUser.host<float>();
    std::memcpy( inputPtr, signalData.data(), static_cast<size_t>( length ) * sizeof( float ) );
    inputTensor->copyFromHostTensor( &inputTensorUser );

    interpreter->runSession( session );

    auto outputTensor = interpreter->getSessionOutput( session, nullptr );
    if ( !outputTensor )
    {
        m_logger->error( "Failed to get output tensor" );
        return nullptr;                                     // (4) no output tensor
    }

    MNN::Tensor::DimensionType outputDimType = outputTensor->getDimensionType();
    auto outputUserTensor = std::make_unique<MNN::Tensor>( outputTensor, outputDimType );
    outputTensor->copyToHostTensor( outputUserTensor.get() );

    return outputUserTensor;
}
```
Case (1) — `createFromBuffer` returning null on malformed bytes — is the realistic trigger for D-11's negative regression test (feed a truncated/garbage byte buffer as `modelFile`).

---

### `SGProcessingManager/test/processors/mnn_tensor_fp4_test.cpp` (test, request-response)

**Analog:** itself — reuse the file's own helper + isolation property (never touches `ProcessingManager::Create()`/`VulkanInitMutex`/a real Vulkan device).

**File header + isolation contract** (lines 1-6):
```cpp
// MNN_Tensor FP4_ULTRA unit tests (Phase 04-sgprocessing-integration, Plan 04-02, PROC-02)
//
// Exercises MNN_Tensor::StartProcessing() directly -- never via
// ProcessingManager::Create() -- so these tests are fully deterministic and
// do not hit the known, out-of-scope VulkanInitMutex re-entrancy deadlock
// (sgproc-render Phase 18) or require a real Vulkan device/model file.
```
Preserve this isolation property for both SGF-04a's rewrite and SGF-02's new negative test — neither should need a real Vulkan device.

**Reusable helpers** (lines 17-58):
```cpp
sgns::IoDeclaration MakeTensorDeclaration( sgns::InputFormat format, int64_t width )
{
    sgns::Dimensions dims;
    dims.set_width( width );

    sgns::IoDeclaration decl;
    decl.set_type( sgns::DataType::TENSOR );
    decl.set_format( format );
    decl.set_dimensions( dims );
    return decl;
}

struct CallResult
{
    ProcessingResult result;
    double           elapsedMs = 0.0;
};

CallResult CallStartProcessing( sgns::InputFormat format, int64_t width, std::vector<char> tensorData )
{
    MNN_Tensor                              processor;
    std::vector<std::vector<uint8_t>>       chunkhashes;
    sgns::IoDeclaration                     decl = MakeTensorDeclaration( format, width );
    std::vector<char>                       modelFile; // intentionally empty ...
    auto                                     execCtx = ExecutionContext::NoOp();

    const auto t0 = std::chrono::steady_clock::now();
    auto       result = processor.StartProcessing( chunkhashes, decl, tensorData, modelFile, nullptr, *execCtx );
    const auto t1 = std::chrono::steady_clock::now();

    CallResult callResult;
    callResult.result    = result;
    callResult.elapsedMs = std::chrono::duration<double, std::milli>( t1 - t0 ).count();
    return callResult;
}
```
**Existing test to rewrite (SGF-04a)** — the stale assertion (currently asserts decode UNAVAILABLE, must assert successful decode per Finding 8):
```cpp
TEST( MnnTensorFp4Test, Fp4UltraRecognizedButDecodeUnavailable )
{
    constexpr int64_t kWidth = 64;
    std::vector<char> tensorData( 32, 0 );

    auto callResult = CallStartProcessing( sgns::InputFormat::FP4_ULTRA, kWidth, std::move( tensorData ) );

    ASSERT_TRUE( callResult.result.error.has_value() );
    // ... (old body asserted FORMAT_UNSUPPORTED + "MNN_Ultra" pending message — replace
    //      with an assertion of successful decode / no error, since decode is now live
    //      via MNN::dequant_fp4_packed_cpu, per Finding 8)
}
```
**New negative test (SGF-02/D-11)**, using the same `CallStartProcessing`-style pattern but exercising `Process()`'s malformed-model path (case 1 above) — since `CallStartProcessing` passes an intentionally-empty `modelFile` today for FP4_ULTRA's early-return path, the new negative test needs a **non-empty but invalid** `modelFile` (e.g. a few garbage bytes) with a valid `FLOAT32` format/width so control flow reaches `Process()` and hits `MNN::Interpreter::createFromBuffer`'s null-return, asserting the new structured error from the SGF-02 fix (not a crash):
```cpp
TEST( MnnTensorFp4Test, MalformedModelBufferReturnsCleanErrorNoCrash )
{
    // Valid tensor input framing (FLOAT32, small width) but a modelFile buffer
    // that is not a valid MNN flatbuffer -- exercises Process()'s
    // createFromBuffer(...) == nullptr path (case 1) and StartProcessing()'s
    // new SGF-02 null-check, asserting a structured ProcessingError instead
    // of a crash.
    MNN_Tensor                        processor;
    std::vector<std::vector<uint8_t>> chunkhashes;
    sgns::IoDeclaration               decl = MakeTensorDeclaration( sgns::InputFormat::FLOAT32, 4 );
    std::vector<char>                 tensorData( 4 * sizeof( float ), 0 );
    std::vector<char>                 modelFile{ 'n', 'o', 't', 'a', 'm', 'o', 'd', 'e', 'l' };
    auto                               execCtx = ExecutionContext::NoOp();

    auto result = processor.StartProcessing( chunkhashes, decl, tensorData, modelFile, nullptr, *execCtx );

    ASSERT_TRUE( result.error.has_value() );
    // No crash reaching this point already proves SGF-02's fix; assert the
    // specific stage/message chosen in processing_processor_mnn_tensor.cpp's fix.
}
```

---

### `GNUS-NEO-SWARM/test/integration/test_sg_connectivity.cpp` (test, request-response)

**Analog:** `test/integration/test_sgprocessing_pipeline.cpp`'s `BuildSchemaJson_Fp4Ultra` — the correct reference assertion in the same repo.

**Stale test to fix** (`test_sg_connectivity.cpp` lines 65-73):
```cpp
TEST( SGConnectivity, BuildSchemaJsonFP4UltraFormatEmitsFP4Type )
{
    SGProcessingBridge bridge;
    auto result =
        bridge.BuildSchemaJson( kModelUri, kInputUri, sgns::InputFormat::FP4_ULTRA, { 1, 256, 256, 3 } );
    ASSERT_TRUE( result.has_value() );
    // FP4_ULTRA maps to the dedicated "fp4_ultra" type string in the schema.
    EXPECT_NE( result.value().find( "fp4_ultra" ), std::string::npos );   // WRONG: inverse of the correct assertion
}
```
**Correct reference pattern to copy from** (`test_sgprocessing_pipeline.cpp` lines 82-96):
```cpp
TEST( SGProcessingBridge, BuildSchemaJson_Fp4Ultra )
{
    SGProcessingBridge bridge;
    auto res = bridge.BuildSchemaJson( "file:///models/fp4-model.mnn", "file:///data/fp4_input.bin",
                                       sgns::InputFormat::FP4_ULTRA, { 1, 64 } );

    ASSERT_TRUE( res.has_value() );
    // FP4_ULTRA must dispatch to the "tensor" DataType (a valid from_json selector) --
    // "fp4_ultra" is not a recognized DataType and must never appear anywhere in the
    // generated schema. The encoding itself is carried only in the separate "format" field.
    EXPECT_NE( res.value().find( "\"type\":\"tensor\"" ), std::string::npos );
    EXPECT_NE( res.value().find( "\"format\":\"FP4_ULTRA\"" ), std::string::npos );
    EXPECT_EQ( res.value().find( "fp4_ultra" ), std::string::npos );
}
```
**Fix:** replace `test_sg_connectivity.cpp`'s single `EXPECT_NE(... "fp4_ultra" ...)` line with the same three-assertion block (adjusted for the `{ 1, 256, 256, 3 }` shape already in place there).

---

### SGF-03 deletion targets — no pattern extraction needed (removal only)

**Files to delete:**
- `src/core/fp4/fp4_codec.hpp` (self-flags itself as orphaned — header comment at lines 1-13 cites Phase 4 D-13, confirms `MNNInferenceEngine`'s reference already removed)
- `src/core/fp4/fp4_codec.cpp`
- `test/core/test_fp4_codec.cpp`

**CMake references to remove:**
```cmake
# src/core/CMakeLists.txt line 2 (inside add_library(neoswarm_core STATIC ...)):
    fp4/fp4_codec.cpp

# test/CMakeLists.txt line 59:
neoswarm_test(test_fp4_codec             core/test_fp4_codec.cpp                          "neoswarm_core")
```
Confirmed self-contained by RESEARCH.md Finding 7 (`git grep -c "fp4_codec\|FP4Codec"` shows only these 5 sites). No other analog needed — this is subtraction, not addition.

---

### New SGFP4 E2E test cases (SGF-01, D-04/D-05/D-07), in `test/integration/test_sgprocessing_pipeline.cpp`

**Analog 1 (dispatch/skip-gate shape):** same file, `Fp4UltraFormat_DispatchesToTensorProcessor` (lines 236-249):
```cpp
TEST( SGProcessingPipeline, Fp4UltraFormat_DispatchesToTensorProcessor )
{
    const std::string data_dir = TestDataPath();
    const std::string model_uri = "file://" + data_dir + "tensor_tiny.mnn";
    const std::string input_uri = "file://" + data_dir + "tensor_input.raw";

    if ( !FileExists( data_dir + "tensor_tiny.mnn" ) )
    {
        GTEST_SKIP() << "Test data not found at: " << data_dir;
    }

    SGProcessingBridge bridge;
    auto ioc = std::make_shared<boost::asio::io_context>();
    auto result = bridge.SubmitJob( model_uri, input_uri, sgns::InputFormat::FP4_ULTRA, { 1, 64 }, ioc );

    ASSERT_TRUE( result.has_value() ) << "SGProcessingBridge::SubmitJob (FP4_ULTRA) failed to dispatch";
    EXPECT_FALSE( result.value().empty() ) << "Process() returned empty bytes for FP4_ULTRA job";
}
```
**Adaptation for SGF-01:** replace `sgns::InputFormat::FP4_ULTRA` with the format the committed SGFP4 `.mnn` actually declares (per D-08, SGFP4 is a model-weight format discovered via the op graph, NOT an `InputFormat` — the schema's `format` field should stay whatever plain tensor format the test model's *input tensor* actually is, e.g. `FLOAT32`; SGFP4-ness lives entirely in the `.mnn` file's conv-weight ops, never in the schema). Add the `HasUsableVulkanDevice()` skip-gate (see Analog 3) only as a defensive "no device at all" gate (Finding 2 — deadlock is fixed, so this is not a permanent skip), and add D-07's op-walk assertion (see below) before or after dispatch.

**Helpers already available in this file** (lines 34-58, reuse directly):
```cpp
std::string TestDataPath()
{
    return std::string( SUPERGENIUS_TEST_DATA_DIR ) + "/processing_datatypes/";
}

bool FileExists( const std::string& path )
{
    std::ifstream f( path );
    return f.good();
}
```

**Analog 2 (explicit CPU classic-API session + D-07's op-walk assertion foundation):** `thirdparty/MNN/test/op/SGFP4ClassicAPITest.cpp` lines ~117-140 (per RESEARCH.md Code Examples; gated by `MNN_SUPPORT_TRANSFORMER_FUSE` in MNN's own suite — read as reference pattern only, not literally reused verbatim since the new test lives in NEO-SWARM's suite, not MNN's):
```cpp
std::shared_ptr<Interpreter> net(Interpreter::createFromFile(modelPath.c_str()), Interpreter::destroy);
ScheduleConfig cfg;
cfg.type = MNN_FORWARD_CPU;                     // explicit CPU -- the pattern D-05's CPU test needs
auto session = net->createSession(cfg);
auto inputTensor = net->getSessionInput(session, nullptr);
net->resizeSession(session);
::memcpy(inputTensor->host<float>(), inputVals.data(), kMatrixDim * sizeof(float));
net->runSession(session);
auto outputTensor = net->getSessionOutput(session, nullptr);
std::shared_ptr<Tensor> outUser(new Tensor(outputTensor, Tensor::CAFFE));
outputTensor->copyToHostTensor(outUser.get());
const float* got = outUser->host<float>();
```
D-05's Vulkan-session test mirrors this exact shape with `cfg.type = MNN_FORWARD_VULKAN` instead, both driven through the phase's new `SGProcessingBridge::SubmitJob()` → `ResolveMnnBackend(parameters)` path (not by calling MNN's classic API directly in the NEO-SWARM test) — this analog is for understanding the CPU/Vulkan session-creation contract MNN_Tensor::Process() implements internally, not for direct copy-paste into the integration test.

**D-07's op-walk assertion** (new, no existing exact analog in NEO-SWARM; nearest precedent is any code that inspects `MNN::Interpreter`'s loaded net — construct via the classic API's `Interpreter::createFromFile`/`createFromBuffer`, then walk `net->... ` op list for `OpType_SGFP4Dequant`; exact accessor to enumerate ops is MNN-internal API, confirm exact call at plan/execute time against `MNN/Interpreter.hpp`).

**Analog 3 (skip-gate mechanics, D-03):** referenced via `sgns::sgprocessing::HasUsableVulkanDevice()` (declared in `SGProcessingManager/include/processors/vulkan_gpu_probe.hpp`, already on NEO-SWARM's include path per Phase 4 plan 04-04). Usage shape (from 04-04-PLAN.md's documented pattern, reused verbatim):
```cpp
if ( sgns::sgprocessing::HasUsableVulkanDevice() )
{
    // NOTE (Finding 2): deadlock is now fixed (sgproc-render Phase 18, commit
    // 528a92a) -- this branch should be the DEFENSIVE "device exists, so proceed
    // to real assertions" path, not a permanent skip. Only genuinely skip when
    // HasUsableVulkanDevice() reports NO device present at all.
}
else
{
    GTEST_SKIP() << "No usable Vulkan device present -- skipping Vulkan session test";
}
```

---

### Committed `.mnn` test asset + recipe doc (D-06) — CMake wiring

**Analog:** `test/CMakeLists.txt`'s existing vendored-fixture pattern for `test_sgprocessing_pipeline` (lines 64-79):
```cmake
target_compile_definitions(test_sgprocessing_pipeline PRIVATE
    SUPERGENIUS_TEST_DATA_DIR="$<TARGET_FILE_DIR:test_sgprocessing_pipeline>"
)
add_custom_command(TARGET test_sgprocessing_pipeline POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E make_directory
    "$<TARGET_FILE_DIR:test_sgprocessing_pipeline>/processing_datatypes"
    COMMENT "Creating processing_datatypes directory"
)
add_custom_command(TARGET test_sgprocessing_pipeline POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
    "${CMAKE_CURRENT_SOURCE_DIR}/integration/processing_datatypes/float_model.mnn"
    "${CMAKE_CURRENT_SOURCE_DIR}/integration/processing_datatypes/float_input.bin"
    "${CMAKE_CURRENT_SOURCE_DIR}/integration/processing_datatypes/float_output_pt.raw"
    "${CMAKE_CURRENT_SOURCE_DIR}/integration/processing_datatypes/tensor_tiny.mnn"
    "${CMAKE_CURRENT_SOURCE_DIR}/integration/processing_datatypes/tensor_input.raw"
    "${CMAKE_CURRENT_SOURCE_DIR}/integration/processing_datatypes/bert-tiny.mnn"
    "${CMAKE_CURRENT_SOURCE_DIR}/integration/processing_datatypes/string_input.raw"
    "$<TARGET_FILE_DIR:test_sgprocessing_pipeline>/processing_datatypes/"
    COMMENT "Copying vendored SGProcessing test fixtures"
)
```
**Application to D-06:** add the new `.mnn` filename (e.g. `sgfp4_tiny.mnn`) to the existing `copy_if_different` file list — no new `add_custom_command` block needed, since the directory (`processing_datatypes/`) and target (`test_sgprocessing_pipeline`) are already set up and the new E2E test lives in the same file/binary. The `mnnconvert --sgfp4` recipe itself is documentation only (README/comment near the fixture, mirroring `RUN_AND_DEPLOY.md`'s `llmexport.py` documentation precedent) — not an automated CMake step.

## Shared Patterns

### Structured error propagation (`ProcessingResult` / `ProcessingError`)
**Source:** `SGProcessingManager/src/processors/processing_processor_mnn_tensor.cpp` (multiple sites, e.g. lines 202, 232, 244, 258, 279-282)
**Apply to:** SGF-02's null-check fix; SGF-02's negative regression test's assertions.
```cpp
return ProcessingResult{};                                             // bare-default early return
return ProcessingResult{ {}, nullptr, {}, ProcessingError{ ProcessingErrorStage::CANCELLED, "message" } };  // structured
```

### Schema-parameter resolution (`parameters` array, find-by-name)
**Source:** `SGProcessingManager/include/util/quantization.hpp` (`ResolveQuantScale`, `ResolveByteQuantMode`)
**Apply to:** the new backend-selection resolver (`ResolveMnnBackend`) required by Finding 3 to satisfy D-04/D-05.
```cpp
float ResolveQuantScale( const std::vector<sgns::Parameter> *parameters );  // fallback-safe, additive convention to mirror
```

### `GTEST_SKIP()` gating on real-hardware/environment availability
**Source:** `test/integration/test_sgprocessing_pipeline.cpp` (`FileExists(...)` gate) and the `HasUsableVulkanDevice()` convention documented in `04-04-PLAN.md`
**Apply to:** SGF-01's new E2E test cases — missing test asset (`FileExists`) and missing Vulkan device (`HasUsableVulkanDevice`) are the two legitimate skip conditions; the deadlock itself is no longer a skip reason (Finding 2).

### Vendored test-fixture CMake copy pattern
**Source:** `test/CMakeLists.txt` lines 64-79 (`test_sgprocessing_pipeline`'s `processing_datatypes/*` block)
**Apply to:** D-06's committed `.mnn` asset — append filename to the existing `copy_if_different` list, reuse `SUPERGENIUS_TEST_DATA_DIR`/`TestDataPath()` for the test-side lookup.

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| D-07's `OpType_SGFP4Dequant` op-list walk (new assertion helper) | test/unit assertion | transform | No existing NEO-SWARM or SGProcessingManager code enumerates MNN's loaded op graph for a specific `OpType`; nearest reference is MNN's own internal `Interpreter`/`Schedule` structures (read-only, MNN-side, out of scope to modify) — planner/implementer should consult `MNN/Interpreter.hpp`'s public accessors directly at implementation time rather than a codebase analog. |
| `ResolveMnnBackend(parameters)` (new function body — the string/enum parsing logic itself, not the calling convention) | utility (parameter resolution) | transform | `ResolveQuantScale`'s calling *convention* is an exact analog (documented above), but its body parses a `FLOAT` parameter with power-of-two validation — a "backend" parameter is a `STRING`/`INT` enum lookup (cpu/vulkan), structurally different validation logic with no direct prior-art in this file family. |

## Metadata

**Analog search scope:** `GNUS-NEO-SWARM/src/core/`, `GNUS-NEO-SWARM/test/{core,integration}/`, `GeniusNetwork/SuperGenius/SGProcessingManager/{src/processors,test/processors,include/util}`, `GeniusNetwork/thirdparty/MNN/test/op/`
**Files scanned:** 12 (read directly) + CMake config files (2)
**Pattern extraction date:** 2026-09-02
