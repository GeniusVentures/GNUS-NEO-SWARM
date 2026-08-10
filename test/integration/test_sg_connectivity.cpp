/**
 * @file       test_sg_connectivity.cpp
 * @brief      Integration tests: SGProcessingBridge BuildSchemaJson + SubmitNetwork fallback
 * @date       2026-08-09
 *
 * Plan 02-08 task 3. Verifies the SuperGenius dispatch bridge against the
 * post-02-05 API (no SGMessageAuthenticator, PollForResult, m_geniusNodeConfig).
 *
 * These tests run WITHOUT a live GeniusSDK node — network dispatch fails and
 * the auto-fallback path (SubmitDirect) is exercised. SubmitDirect itself fails
 * in this environment because SGProcessingManager has no valid model, which is
 * expected: the assertions target error propagation and crash-safety, not success.
 */

#include "common/error.hpp"
#include "core/sgprocessing/sg_processing_bridge.hpp"
#include <boost/asio/io_context.hpp>
#include <gtest/gtest.h>
#include <memory>
#include <string>

#include <InputFormat.hpp>

using namespace sgns::neoswarm;
using namespace sgns::neoswarm::core;

namespace
{
    constexpr const char* kModelUri = "file:///tmp/model.mnn";
    constexpr const char* kInputUri = "file:///tmp/input.bin";
} // namespace

// =======================================================================
// BuildSchemaJson
// =======================================================================

TEST( SGConnectivity, BuildSchemaJsonValidParamsReturnsJson )
{
    SGProcessingBridge bridge;
    auto result = bridge.BuildSchemaJson( kModelUri, kInputUri, sgns::InputFormat::FLOAT32, { 1, 512 } );
    ASSERT_TRUE( result.has_value() );
    EXPECT_FALSE( result.value().empty() );
    // GNUS schema marker emitted by BuildSchemaJson (doc["gnus_spec_version"]).
    EXPECT_NE( result.value().find( "gnus_spec_version" ), std::string::npos );
}

TEST( SGConnectivity, BuildSchemaJsonEmptyModelUriReturnsInvalidArgument )
{
    SGProcessingBridge bridge;
    auto result = bridge.BuildSchemaJson( "", kInputUri, sgns::InputFormat::FLOAT32, { 1, 512 } );
    ASSERT_FALSE( result.has_value() );
    EXPECT_EQ( result.error(), Error::InvalidArgument );
}

TEST( SGConnectivity, BuildSchemaJsonEmptyInputUriReturnsInvalidArgument )
{
    SGProcessingBridge bridge;
    auto result = bridge.BuildSchemaJson( kModelUri, "", sgns::InputFormat::FLOAT32, { 1, 512 } );
    ASSERT_FALSE( result.has_value() );
    EXPECT_EQ( result.error(), Error::InvalidArgument );
}

TEST( SGConnectivity, BuildSchemaJsonFP4UltraFormatEmitsFP4Type )
{
    SGProcessingBridge bridge;
    auto result =
        bridge.BuildSchemaJson( kModelUri, kInputUri, sgns::InputFormat::FP4_ULTRA, { 1, 256, 256, 3 } );
    ASSERT_TRUE( result.has_value() );
    // FP4_ULTRA maps to the dedicated "fp4_ultra" type string in the schema.
    EXPECT_NE( result.value().find( "fp4_ultra" ), std::string::npos );
}

// =======================================================================
// SubmitNetwork fallback / SetClient
// =======================================================================

TEST( SGConnectivity, SubmitJobNetworkModeNoClientFallsBackAndFails )
{
    SGProcessingBridge::Config cfg;
    cfg.m_networkMode = true;
    SGProcessingBridge bridge( cfg );
    auto ioc = std::make_shared<boost::asio::io_context>();

    // No client set → SubmitNetwork returns NetworkError → bridge falls back to
    // SubmitDirect, which also fails (no SGProcessingManager / no valid model).
    // The key assertion: the chain resolves to a failure result, not a crash.
    auto result = bridge.SubmitJob( kModelUri, kInputUri, sgns::InputFormat::FLOAT32, { 1, 512 }, ioc );
    ASSERT_FALSE( result.has_value() );
}

TEST( SGConnectivity, SubmitJobDirectModeDoesNotRequireClient )
{
    SGProcessingBridge::Config cfg;
    cfg.m_networkMode = false; // direct mode — never touches SubmitNetwork
    SGProcessingBridge bridge( cfg );
    auto ioc = std::make_shared<boost::asio::io_context>();

    // Direct mode may fail (SGProcessingManager unavailable) but must not crash.
    auto result = bridge.SubmitJob( kModelUri, kInputUri, sgns::InputFormat::FLOAT32, { 1, 512 }, ioc );
    ASSERT_FALSE( result.has_value() );
}

TEST( SGConnectivity, SetClientNullptrDoesNotCrash )
{
    SGProcessingBridge bridge;
    bridge.SetClient( nullptr );
    SUCCEED();
}

TEST( SGConnectivity, SubmitJobInvalidSchemaDoesNotAttemptDispatch )
{
    // Empty model URI fails BuildSchemaJson before any network/direct dispatch.
    SGProcessingBridge::Config cfg;
    cfg.m_networkMode = true;
    SGProcessingBridge bridge( cfg );
    auto ioc = std::make_shared<boost::asio::io_context>();

    auto result = bridge.SubmitJob( "", kInputUri, sgns::InputFormat::FLOAT32, { 1, 512 }, ioc );
    ASSERT_FALSE( result.has_value() );
    EXPECT_EQ( result.error(), Error::InvalidArgument );
}
