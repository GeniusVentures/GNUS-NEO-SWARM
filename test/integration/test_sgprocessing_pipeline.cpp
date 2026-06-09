/**
 * @file       test_sgprocessing_pipeline.cpp
 * @brief      Integration tests: NeoSwarm → SGProcessingManager → TensorInterpreter
 * @date       2026-05-08
 * @author     Subaskar S (ssivakumar@gnus.ai)
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

#include "common/Error.hpp"
#include "core/sgprocessing/SGProcessingBridge.hpp"
#include "core/sgprocessing/TensorInterpreter.hpp"
#include <boost/asio/io_context.hpp>
#include <cstring>
#include <fstream>
#include <gtest/gtest.h>
#include <memory>

#ifdef GENIUS_HAS_SGPROCESSING
#include <InputFormat.hpp>
#else
namespace sgns
{
    enum class InputFormat : int
    {
        FLOAT16 = 0,
        FLOAT32 = 1,
        FP4_ULTRA = 2,
        INT16 = 3,
        INT32 = 4,
        INT8 = 5,
        RGB8 = 6,
        RGBA8 = 7
    };
} // namespace sgns
#endif

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

TEST( SGProcessingBridge, SubmitJob_StubMode_ReturnsOk )
{
    SGProcessingBridge bridge;
    auto ioc = std::make_shared<boost::asio::io_context>();
    auto res = bridge.SubmitJob( "file:///models/model.mnn", "file:///data/input.raw", sgns::InputFormat::FLOAT32,
                                 { 1, 64 }, ioc );

#ifdef GENIUS_HAS_SGPROCESSING
    (void) res; // result depends on whether model file exists
#else
    ASSERT_TRUE( res.has_value() );
    EXPECT_TRUE( res.value().empty() ); // stub returns empty bytes
#endif
}

TEST( SGProcessingBridge, NetworkMode_ReturnsNotImplemented )
{
    SGProcessingBridge::Config cfg;
    cfg.network_mode_ = true;
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
#ifdef GENIUS_HAS_SGPROCESSING

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
    SGProcessingBridge bridge;
    auto ioc = std::make_shared<boost::asio::io_context>();
    auto result = bridge.SubmitJob( model_uri, input_uri, sgns::InputFormat::FLOAT32, { 1, 64 }, ioc );

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

#endif // GENIUS_HAS_SGPROCESSING

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
