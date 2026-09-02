/**
 * @file       test_sgprocessing_pipeline.cpp
 * @brief      Integration tests: NeoSwarm → SGProcessingManager → TensorInterpreter
 * @date       2026-05-08
 *
 * Phase 1 flow (direct, no network):
 *   NeoSwarm (SGProcessingBridge) → input data + .mnn
 *       → SGProcessingManager::Create(json) + Process()
 *       → raw MNN::Tensor bytes
 *       → TensorInterpreter::Interpret()
 *       → human-readable output
 *
 * Test data is taken from SuperGenius/test/src/processing_datatypes/.
 * See GNUS-NEO-SWARM/AgentDocs/SGPROCESSING_INTEGRATION.md for full details.
 */

#include "common/error.hpp"
#include "core/sgprocessing/sg_processing_bridge.hpp"
#include "core/sgprocessing/tensor_interpreter.hpp"
#include <boost/asio/io_context.hpp>
#include <cstring>
#include <fstream>
#include <gtest/gtest.h>
#include <memory>
#include <sstream>

#include <InputFormat.hpp>
#include <processingbase/ProcessingManager.hpp>
#include <processors/vulkan_gpu_probe.hpp>

// Phase 13, Plan 13-02 (D-07): raw flatbuffer op-list walk over the committed
// SGFP4 fixture. MNN_generated.h is a header-only generated reader (GetNet is
// inline; no MNN library symbols are referenced).
#include <MNN_generated.h>

#include <nlohmann/json.hpp>

using namespace sgns::neoswarm;
using namespace sgns::neoswarm::core;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
namespace
{
    /// Path to the SuperGenius processing_datatypes test data directory.
    /// Adjust if running from a different working directory.
    std::string TestDataPath()
    {
        return std::string( SUPERGENIUS_TEST_DATA_DIR ) + "/processing_datatypes/";
    }

    bool FileExists( const std::string& path )
    {
        std::ifstream f( path );
        return f.good();
    }

    std::vector<float> ReadFloatFile( const std::string& path )
    {
        std::ifstream f( path, std::ios::binary );
        if ( !f )
            return {};
        f.seekg( 0, std::ios::end );
        const auto size = f.tellg();
        f.seekg( 0, std::ios::beg );
        std::vector<float> data( static_cast<size_t>( size ) / sizeof( float ) );
        f.read( reinterpret_cast<char*>( data.data() ), static_cast<std::streamsize>( size ) );
        return data;
    }

    // -----------------------------------------------------------------------
    // Phase 13, Plan 13-02 helpers (SGF-01 / D-05 / D-07)
    // -----------------------------------------------------------------------

    /// Loads the committed SGFP4 fixture's raw flatbuffer and asserts at least
    /// one op in Net::oplists() is OpType_SGFP4Dequant (D-07). Without this a
    /// silently all-FP32 model could pass the E2E tests vacuously (T-13-04).
    /// Uses only the header-only generated reader (MNN::GetNet) -- the same
    /// classic-API-adjacent pattern SGFP4ClassicAPITest.cpp documents.
    testing::AssertionResult AssertModelContainsSgfp4DequantOp( const std::string& modelPath )
    {
        std::ifstream f( modelPath, std::ios::binary );
        if ( !f )
            return testing::AssertionFailure() << "cannot open model at " << modelPath;
        std::vector<char> bytes( ( std::istreambuf_iterator<char>( f ) ), std::istreambuf_iterator<char>() );
        if ( bytes.size() < sizeof( uint32_t ) )
            return testing::AssertionFailure() << "model file too small: " << bytes.size() << " bytes";

        flatbuffers::Verifier verifier( reinterpret_cast<const uint8_t *>( bytes.data() ), bytes.size() );
        if ( !MNN::VerifyNetBuffer( verifier ) )
            return testing::AssertionFailure() << "model is not a valid MNN flatbuffer";

        const MNN::Net *net = MNN::GetNet( bytes.data() );
        const auto     *ops = net->oplists();
        if ( ops == nullptr )
            return testing::AssertionFailure() << "model has no oplists vector";

        size_t sgfp4Count = 0;
        for ( flatbuffers::uoffset_t i = 0; i < ops->size(); ++i )
        {
            if ( ops->Get( static_cast<flatbuffers::uoffset_t>( i ) )->type() == MNN::OpType_SGFP4Dequant )
            {
                ++sgfp4Count;
            }
        }
        if ( sgfp4Count == 0 )
        {
            return testing::AssertionFailure()
                << "fixture contains zero OpType_SGFP4Dequant ops (" << ops->size()
                << " ops total) -- an all-FP32 model cannot prove SGFP4 execution (D-07)";
        }
        return testing::AssertionSuccess() << sgfp4Count << " OpType_SGFP4Dequant op(s) present";
    }

    /// Builds a base schema for the SGFP4 fixture via the public bridge API and
    /// patches it for backend-selected MNN_Tensor dispatch:
    ///   1. input `type` "float" -> "tensor" so the job dispatches to
    ///      MNN_Tensor — the processor whose 13-01 ResolveMnnBackend() call
    ///      consumes the backend parameter (MNN_Float would silently ignore
    ///      it; same JSON-patch pattern as LlmDataType_JobReachesRegisteredProcessor);
    ///   2. injects a top-level `parameters` entry selecting the MNN session
    ///      backend.
    /// The input `format` stays "FLOAT32": SGFP4 is a WEIGHT format inside the
    /// .mnn, never an input encoding (D-08). The whole 5,776-element input is
    /// declared as one block so MNN_Tensor feeds the model's full [1,1,76,76]
    /// input rather than a 64-element prefix.
    std::string BuildBackendParameterizedSchemaJson( const SGProcessingBridge &bridge,
                                                     const std::string        &modelUri,
                                                     const std::string        &inputUri,
                                                     const std::string        &backend )
    {
        auto schema_res
            = bridge.BuildSchemaJson( modelUri, inputUri, sgns::InputFormat::FLOAT32, { 1, 5776 } );
        if ( !schema_res.has_value() )
        {
            return {};
        }
        std::string json = schema_res.value();
        const std::string needle = "\"type\":\"float\"";
        const auto      pos = json.find( needle );
        if ( pos == std::string::npos )
        {
            return {};
        }
        json.replace( pos, needle.size(), "\"type\":\"tensor\"" );

        nlohmann::json doc = nlohmann::json::parse( json );
        doc["parameters"] = nlohmann::json::array( { { { "name", "backend" },
                                                       { "type", "string" },
                                                       { "default", backend } } } );
        return doc.dump();
    }
} // namespace

// ---------------------------------------------------------------------------
// SGProcessingBridge — schema JSON generation (no SGProcessingManager needed)
// ---------------------------------------------------------------------------
TEST( SGProcessingBridge, BuildSchemaJson_ValidInputs )
{
    SGProcessingBridge bridge;
    auto res = bridge.BuildSchemaJson( "file:///models/bert-tiny.mnn", "file:///data/input.raw",
                                       sgns::InputFormat::FLOAT32, { 1, 64 } );

    ASSERT_TRUE( res.has_value() );
    // Verify key fields are present
    EXPECT_NE( res.value().find( "\"FLOAT32\"" ), std::string::npos );
    EXPECT_NE( res.value().find( "\"inference\"" ), std::string::npos );
    EXPECT_NE( res.value().find( "\"MNN\"" ), std::string::npos );
    EXPECT_NE( res.value().find( "\"dimensions\"" ), std::string::npos );
    EXPECT_NE( res.value().find( "neo-swarm-inference" ), std::string::npos );
    // type should be "float" for FLOAT32 (matches SGProcessingManager DataType)
    EXPECT_NE( res.value().find( "\"float\"" ), std::string::npos );
}

TEST( SGProcessingBridge, BuildSchemaJson_Fp4Ultra )
{
    SGProcessingBridge bridge;
    auto res = bridge.BuildSchemaJson( "file:///models/fp4-model.mnn", "file:///data/fp4_input.bin",
                                       sgns::InputFormat::FP4_ULTRA, { 1, 64 } );

    ASSERT_TRUE( res.has_value() );
    // FP4_ULTRA must dispatch to the "tensor" DataType (a valid from_json selector) —
    // "fp4_ultra" is not a recognized DataType and must never appear anywhere in the
    // generated schema. The encoding itself is carried only in the separate "format" field.
    EXPECT_NE( res.value().find( "\"type\":\"tensor\"" ), std::string::npos );
    EXPECT_NE( res.value().find( "\"format\":\"FP4_ULTRA\"" ), std::string::npos );
    EXPECT_EQ( res.value().find( "fp4_ultra" ), std::string::npos );
}

TEST( SGProcessingBridge, BuildSchemaJson_EmptyModelUri_ReturnsError )
{
    SGProcessingBridge bridge;
    EXPECT_FALSE(
        bridge.BuildSchemaJson( "", "file:///data/input.raw", sgns::InputFormat::FLOAT32, { 64 } ).has_value() );
}

TEST( SGProcessingBridge, BuildSchemaJson_EmptyInputUri_ReturnsError )
{
    SGProcessingBridge bridge;
    EXPECT_FALSE(
        bridge.BuildSchemaJson( "file:///models/model.mnn", "", sgns::InputFormat::FLOAT32, { 64 } ).has_value() );
}

TEST( SGProcessingBridge, BuildSchemaJson_FlatWidthFromShape )
{
    SGProcessingBridge bridge;
    // shape [2, 64] → flatWidth = 128
    auto res = bridge.BuildSchemaJson( "file:///models/model.mnn", "file:///data/input.raw", sgns::InputFormat::FLOAT32,
                                       { 2, 64 } );
    ASSERT_TRUE( res.has_value() );
    EXPECT_NE( res.value().find( "128" ), std::string::npos );
}

TEST( SGProcessingBridge, NetworkMode_ReturnsNotImplemented )
{
    SGProcessingBridge::Config cfg;
    cfg.m_networkMode = true;
    SGProcessingBridge bridge( cfg );

    auto ioc = std::make_shared<boost::asio::io_context>();
    auto res = bridge.SubmitJob( "file:///models/model.mnn", "file:///data/input.raw", sgns::InputFormat::FLOAT32,
                                 { 1, 64 }, ioc );

    EXPECT_FALSE( res.has_value() );
}

// ---------------------------------------------------------------------------
// Phase 1 integration test: NeoSwarm → SGProcessingManager → TensorInterpreter
//
// Uses real test data from SuperGenius/test/src/processing_datatypes/.
// Skipped automatically if the test data directory is not present.
// ---------------------------------------------------------------------------

TEST( SGProcessingPipeline, FloatModel_EndToEnd )
{
    const std::string data_dir = TestDataPath();
    const std::string model_uri = "file://" + data_dir + "float_model.mnn";
    const std::string input_uri = "file://" + data_dir + "float_input.bin";
    const std::string ref_path = data_dir + "float_output_pt.raw";

    if ( !FileExists( data_dir + "float_model.mnn" ) )
    {
        GTEST_SKIP() << "Test data not found at: " << data_dir;
    }

    // Phase 1: NeoSwarm → SGProcessingManager
    // total_width=512/chunk_stride=32 match float-processing-definition.json (the schema
    // float_output_pt.raw was generated against) -- the fixture is 512 elements processed
    // as overlapping 64-wide windows, not a single 64-element block.
    SGProcessingBridge bridge;
    auto ioc = std::make_shared<boost::asio::io_context>();
    auto result = bridge.SubmitJob( model_uri, input_uri, sgns::InputFormat::FLOAT32, { 1, 64 }, ioc, 512, 32 );

    ASSERT_TRUE( result.has_value() ) << "SGProcessingBridge::SubmitJob failed";
    ASSERT_FALSE( result.value().empty() ) << "Process() returned empty bytes";

    // Phase 2: NeoSwarm interprets raw bytes → human-readable
    TensorInterpreter interp;
    auto text_res = interp.Interpret( result.value(), sgns::InputFormat::FLOAT32 );
    ASSERT_TRUE( text_res.has_value() );
    EXPECT_FALSE( text_res.value().empty() );

    std::cout << "Float model output (first 80 chars): " << text_res.value().substr( 0, 80 ) << "...\n";

    // Phase 3: Compare against PyTorch reference output
    if ( FileExists( ref_path ) )
    {
        const size_t n_bytes = result.value().size();
        std::vector<float> output( n_bytes / sizeof( float ) );
        std::memcpy( output.data(), result.value().data(), n_bytes );

        auto reference = ReadFloatFile( ref_path );
        ASSERT_EQ( output.size(), reference.size() ) << "Output size mismatch vs reference";

        double mean_abs_diff = 0.0;
        double max_abs_diff = 0.0;
        for ( size_t i = 0; i < output.size(); ++i )
        {
            double diff = std::abs( static_cast<double>( output[i] ) - static_cast<double>( reference[i] ) );
            mean_abs_diff += diff;
            if ( diff > max_abs_diff )
                max_abs_diff = diff;
        }
        mean_abs_diff /= static_cast<double>( output.size() );

        std::cout << "Float model diff: mean=" << mean_abs_diff << " max=" << max_abs_diff << "\n";

        EXPECT_LT( mean_abs_diff, 1e-3 ) << "Mean absolute diff too large";
        EXPECT_LT( max_abs_diff, 1e-2 ) << "Max absolute diff too large";
    }
    else
    {
        std::cout << "Reference file not found — skipping numerical comparison\n";
    }
}

TEST( SGProcessingPipeline, TensorModel_EndToEnd )
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
    auto result = bridge.SubmitJob( model_uri, input_uri, sgns::InputFormat::FLOAT32, { 1, 64 }, ioc );

    ASSERT_TRUE( result.has_value() );
    ASSERT_FALSE( result.value().empty() );

    TensorInterpreter interp;
    auto text_res = interp.Interpret( result.value(), sgns::InputFormat::FLOAT32 );
    ASSERT_TRUE( text_res.has_value() );
    EXPECT_FALSE( text_res.value().empty() );

    std::cout << "Tensor model output (first 80 chars): " << text_res.value().substr( 0, 80 ) << "...\n";
}

// ---------------------------------------------------------------------------
// FP4_ULTRA / LLM integration test cases (Phase 4 plan 04-04, PROC-01/PROC-02)
// ---------------------------------------------------------------------------

TEST( SGProcessingPipeline, Fp4UltraFormat_DispatchesToTensorProcessor )
{
    const std::string data_dir = TestDataPath();
    const std::string model_uri = "file://" + data_dir + "tensor_tiny.mnn";
    const std::string input_uri = "file://" + data_dir + "tensor_input.raw";

    if ( !FileExists( data_dir + "tensor_tiny.mnn" ) )
    {
        GTEST_SKIP() << "Test data not found at: " << data_dir;
    }

    // FP4_ULTRA is a TENSOR-typed InputFormat (D-10/D-13) -- SubmitJob() must dispatch
    // this job to the TENSOR processor's validated path rather than being rejected as
    // an unrecognized DataType/format combination.
    SGProcessingBridge bridge;
    auto ioc = std::make_shared<boost::asio::io_context>();
    auto result = bridge.SubmitJob( model_uri, input_uri, sgns::InputFormat::FP4_ULTRA, { 1, 64 }, ioc );

    ASSERT_TRUE( result.has_value() ) << "SGProcessingBridge::SubmitJob (FP4_ULTRA) failed to dispatch";
    EXPECT_FALSE( result.value().empty() ) << "Process() returned empty bytes for FP4_ULTRA job";
}

// ---------------------------------------------------------------------------
// SGFP4 direct-path end-to-end tests (Phase 13, Plan 13-02, SGF-01 / D-05)
//
// Real SGFP4-quantized .mnn through the FULL direct-call chain:
//   schema JSON (backend parameter) -> SubmitDirect() ->
//   ProcessingManager::Create() -> Process() -> MNN_Tensor (13-01 resolver
//   selects the session backend) -> output bytes.
// The VulkanInitMutex re-entrancy deadlock is CLOSED (research Finding 2:
// sgproc-render Phase 18, commit 528a92a is an ancestor of the linked
// SGProcessingManager), so these tests run REAL execution assertions -- the
// Vulkan test skips only for a genuinely absent Vulkan device (D-03).
// ---------------------------------------------------------------------------

TEST( SGProcessingPipeline, Sgfp4DirectCpu_EndToEnd )
{
    const std::string data_dir = TestDataPath();
    const std::string model_path = data_dir + "sgfp4_tiny.mnn";
    const std::string model_uri = "file://" + model_path;
    const std::string input_uri = "file://" + data_dir + "sgfp4_tiny_input.raw";

    if ( !FileExists( model_path ) )
    {
        GTEST_SKIP() << "Test data not found at: " << data_dir;
    }

    // D-07: prove the fixture really is SGFP4-quantized before dispatching.
    EXPECT_TRUE( AssertModelContainsSgfp4DequantOp( model_path ) );

    SGProcessingBridge bridge;
    const std::string json = BuildBackendParameterizedSchemaJson( bridge, model_uri, input_uri, "cpu" );
    ASSERT_FALSE( json.empty() ) << "schema build failed";

    auto ioc = std::make_shared<boost::asio::io_context>();
    auto result = bridge.SubmitDirect( json, ioc );

    ASSERT_TRUE( result.has_value() ) << "SubmitDirect (backend=cpu) failed";
    ASSERT_FALSE( result.value().empty() ) << "SubmitDirect (backend=cpu) returned empty bytes";
}

TEST( SGProcessingPipeline, Sgfp4DirectVulkan_EndToEnd )
{
    const std::string data_dir = TestDataPath();
    const std::string model_path = data_dir + "sgfp4_tiny.mnn";
    const std::string model_uri = "file://" + model_path;
    const std::string input_uri = "file://" + data_dir + "sgfp4_tiny_input.raw";

    if ( !FileExists( model_path ) )
    {
        GTEST_SKIP() << "Test data not found at: " << data_dir;
    }

    // D-03: skip ONLY when this host has no usable Vulkan device (a valid,
    // expected environment). The old VulkanInitMutex deadlock workaround is
    // NOT cited here -- it is fixed on the linked SGProcessingManager.
    if ( !sgns::sgprocessing::HasUsableVulkanDevice() )
    {
        GTEST_SKIP() << "No usable Vulkan device present";
    }

    // D-07: prove the fixture really is SGFP4-quantized before dispatching.
    EXPECT_TRUE( AssertModelContainsSgfp4DequantOp( model_path ) );

    SGProcessingBridge bridge;
    const std::string json = BuildBackendParameterizedSchemaJson( bridge, model_uri, input_uri, "vulkan" );
    ASSERT_FALSE( json.empty() ) << "schema build failed";

    auto ioc = std::make_shared<boost::asio::io_context>();
    auto result = bridge.SubmitDirect( json, ioc );

    ASSERT_TRUE( result.has_value() ) << "SubmitDirect (backend=vulkan) failed";
    ASSERT_FALSE( result.value().empty() ) << "SubmitDirect (backend=vulkan) returned empty bytes";
}

TEST( SGProcessingPipeline, LlmDataType_JobReachesRegisteredProcessor )
{
    const std::string data_dir = TestDataPath();
    const std::string model_uri = "file://" + data_dir + "bert-tiny.mnn";
    const std::string input_uri = "file://" + data_dir + "string_input.raw";

    if ( !FileExists( data_dir + "bert-tiny.mnn" ) )
    {
        GTEST_SKIP() << "Test data not found at: " << data_dir;
    }

    // DataType::LLM (added by Phase 4 plan 04-03, guarded by SGPROC_HAS_MNN_LLM) has no
    // dedicated InputFormat/type-string mapping in SGProcessingBridge -- build a schema
    // via the normal FLOAT32 path, then patch the modelInput's "type" field to "llm" so
    // this test exercises the same JSON-parse/registration-lookup path a real LLM job's
    // schema would use, without requiring SGProcessingBridge itself to grow LLM-specific
    // schema-building support (out of scope for this plan).
    SGProcessingBridge bridge;
    auto schema_res = bridge.BuildSchemaJson( model_uri, input_uri, sgns::InputFormat::FLOAT32, { 1, 128 } );
    ASSERT_TRUE( schema_res.has_value() );

    std::string json = schema_res.value();
    const std::string needle = "\"type\":\"float\"";
    const auto pos = json.find( needle );
    ASSERT_NE( pos, std::string::npos ) << "Expected a \"type\":\"float\" input field to patch to \"llm\"";
    json.replace( pos, needle.size(), "\"type\":\"llm\"" );

    // At minimum, a schema with a valid "llm" type string must reach
    // ProcessingManager::Create() without an INVALID_JSON error -- whether DataType::LLM
    // has a registered processor factory in this build (it does not in this environment;
    // see 04-03-SUMMARY.md's SGPROC_HAS_MNN_LLM guard) is a separate, later-stage concern
    // (NO_PROCESSOR), not a JSON-parse failure.
    auto pm_result = sgns::sgprocessing::ProcessingManager::Create( json );
    ASSERT_TRUE( pm_result.has_value() ) << "Schema with type=\"llm\" failed at ProcessingManager::Create() "
                                             "(expected to reach Create() without an INVALID_JSON error): "
                                          << pm_result.error().message();
}

// ---------------------------------------------------------------------------
// TensorInterpreter unit tests (no SGProcessingManager needed)
// ---------------------------------------------------------------------------
TEST( TensorInterpreter, InterpretFloat32_Values )
{
    TensorInterpreter interp;
    std::vector<float> vals = { 1.0f, 2.5f, -0.5f };
    std::vector<uint8_t> bytes( vals.size() * sizeof( float ) );
    std::memcpy( bytes.data(), vals.data(), bytes.size() );

    auto res = interp.Interpret( bytes, sgns::InputFormat::FLOAT32 );
    ASSERT_TRUE( res.has_value() );
    EXPECT_NE( res.value().find( "1" ), std::string::npos );
    EXPECT_NE( res.value().find( "2.5" ), std::string::npos );
}

TEST( TensorInterpreter, InterpretInt32_Values )
{
    TensorInterpreter interp;
    std::vector<int32_t> vals = { 42, -7, 0 };
    std::vector<uint8_t> bytes( vals.size() * sizeof( int32_t ) );
    std::memcpy( bytes.data(), vals.data(), bytes.size() );

    auto res = interp.Interpret( bytes, sgns::InputFormat::INT32 );
    ASSERT_TRUE( res.has_value() );
    EXPECT_NE( res.value().find( "42" ), std::string::npos );
    EXPECT_NE( res.value().find( "-7" ), std::string::npos );
}

TEST( TensorInterpreter, InterpretInt8_Values )
{
    TensorInterpreter interp;
    std::vector<int8_t> vals = { 10, -20, 127 };
    std::vector<uint8_t> bytes( vals.begin(), vals.end() );

    auto res = interp.Interpret( bytes, sgns::InputFormat::INT8 );
    ASSERT_TRUE( res.has_value() );
    EXPECT_NE( res.value().find( "10" ), std::string::npos );
    EXPECT_NE( res.value().find( "-20" ), std::string::npos );
}

TEST( TensorInterpreter, InterpretEmptyBytes_ReturnsError )
{
    TensorInterpreter interp;
    EXPECT_FALSE( interp.Interpret( {}, sgns::InputFormat::FLOAT32 ).has_value() );
}

TEST( TensorInterpreter, InterpretFloat32_MisalignedBytes_ReturnsError )
{
    TensorInterpreter interp;
    std::vector<uint8_t> bytes( 5, 0 );
    EXPECT_FALSE( interp.Interpret( bytes, sgns::InputFormat::FLOAT32 ).has_value() );
}
