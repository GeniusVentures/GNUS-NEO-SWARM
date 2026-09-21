/**
 * @file       test_sg_client.cpp
 * @brief      Unit tests for SGJobSubmitter, SGResultCollector, and SGClient
 * @date       2026-07-09
 */

#include "network/sg_client/sg_job_submitter.hpp"
#include "network/sg_client/sg_result_collector.hpp"
#include "network/sg_client/super_genius_client.hpp"
#include "common/error.hpp"
#include "GeniusSDK.h"
#include <gtest/gtest.h>
#include <chrono>
#include <filesystem>
#include <future>

using namespace sgns::neoswarm::network;
using namespace sgns::neoswarm;

namespace
{
    constexpr auto kShortPollTimeout = std::chrono::seconds( 1 );      ///< Short poll for timeout tests
    constexpr auto kPollCompletionSlack = std::chrono::seconds( 3 );   ///< Upper bound for poll completion
    constexpr auto kDefaultCollectorTimeout = std::chrono::seconds( 120 ); ///< SGResultCollector default
    constexpr auto kCustomTimeout = std::chrono::seconds( 30 );        ///< Custom (non-default) timeout
} // namespace

// =======================================================================
// SGJobSubmitter
// =======================================================================

TEST( SGJobSubmitter, DefaultConstructs )
{
    SGJobSubmitter submitter;
}

TEST( SGJobSubmitter, RejectsOversizedPayload )
{
    SGJobSubmitter submitter;
    std::string largePayload( sizeof( JsonData_t ), 'x' );
    auto result = submitter.PublishJob( largePayload );
    ASSERT_FALSE( result.has_value() );
    EXPECT_NE( result.error(), Error::BroadcastTimeout );
}

TEST( SGJobSubmitter, AcceptsMaxSizeMinusOne )
{
    SGJobSubmitter submitter;
    std::string maxPayload( sizeof( JsonData_t ) - 1, 'x' );
    auto result = submitter.PublishJob( maxPayload );
    // Size check passes. Without SDK, dispatch fails — but NOT from InvalidArgument.
    ASSERT_FALSE( result.has_value() );
    EXPECT_NE( result.error(), Error::InvalidArgument );
}

TEST( SGJobSubmitter, RejectsEmptyPayloadWithoutSDK )
{
    SGJobSubmitter submitter;
    auto result = submitter.PublishJob( "" );
    ASSERT_FALSE( result.has_value() );
    EXPECT_NE( result.error(), Error::InvalidArgument );
}

// =======================================================================
// SGResultCollector
// =======================================================================

TEST( SGResultCollector, DefaultConfigTimeoutIs120Seconds )
{
    SGResultCollectorConfig cfg;
    EXPECT_EQ( cfg.m_resultTimeout, kDefaultCollectorTimeout );
}

TEST( SGResultCollector, CustomTimeoutAccepted )
{
    SGResultCollectorConfig cfg;
    cfg.m_resultTimeout = kCustomTimeout;
    SGResultCollector collector( cfg );
}

TEST( SGResultCollector, ShortTimeoutReturnsError )
{
    SGResultCollector collector;
    auto start = std::chrono::steady_clock::now();
    auto result = collector.PollForResult( kShortPollTimeout );
    auto elapsed = std::chrono::steady_clock::now() - start;

    ASSERT_FALSE( result.has_value() );
    // Should return within timeout window
    EXPECT_LE( elapsed, kPollCompletionSlack );
}

TEST( SGResultCollector, AsyncPollCompletesGracefully )
{
    SGResultCollectorConfig cfg;
    cfg.m_resultTimeout = kShortPollTimeout;
    SGResultCollector collector( cfg );
    auto future = collector.PollForResultAsync();
    auto status = future.wait_for( kPollCompletionSlack );
    EXPECT_EQ( status, std::future_status::ready );
}

TEST( SGResultCollector, DefaultTimeoutResolves )
{
    SGResultCollector collector;
    auto result = collector.PollForResult();
    // Without SDK, polling returns error — verify not a crash
    ASSERT_FALSE( result.has_value() );
}

TEST( SGResultCollector, MultipleInstancesIndependent )
{
    SGResultCollector collector1;
    SGResultCollector collector2;
    auto r1 = collector1.PollForResult( kShortPollTimeout );
    auto r2 = collector2.PollForResult( kShortPollTimeout );
    ASSERT_FALSE( r1.has_value() );
    ASSERT_FALSE( r2.has_value() );
}

// =======================================================================
// SGClient (lifecycle — post-02-05 API: m_geniusNodeConfig + m_resultTimeout,
// Initialize() takes no identity, SDK generates its own keypair)
// =======================================================================

TEST( SGClient, DefaultConfigMatchesNamedConstants )
{
    SGClient::Config cfg;
    // SGClient result deadline is kDefaultResultTimeoutSeconds (WR-02);
    // SGResultCollector's own default (120s) is overridden at construction.
    EXPECT_EQ( cfg.m_resultTimeout, std::chrono::seconds( kDefaultResultTimeoutSeconds ) );
    // BaseWritePath default is "./sdk" via GeniusNodeConfig default.
    EXPECT_EQ( cfg.m_geniusNodeConfig.BaseWritePath, "./sdk" );
}

TEST( SGClient, IsConnectedBeforeInitReturnsFalse )
{
    SGClient::Config cfg;
    SGClient client( std::move( cfg ) );
    EXPECT_FALSE( client.IsConnected() );
}

TEST( SGClient, ConstructWithConfigDoesNotCrash )
{
    SGClient::Config cfg;
    cfg.m_geniusNodeConfig.BaseWritePath =
        ( std::filesystem::temp_directory_path() / "test-sgclient-sdk" ).string();
    SGClient client( std::move( cfg ) );
    EXPECT_FALSE( client.IsConnected() );
}

TEST( SGClient, MoveConstructorTransfersOwnership )
{
    SGClient::Config cfg;
    cfg.m_geniusNodeConfig.BaseWritePath =
        ( std::filesystem::temp_directory_path() / "test-sgclient-sdk-move" ).string();
    SGClient client1( std::move( cfg ) );
    SGClient client2( std::move( client1 ) );
    // client2 owns the state; neither is initialized.
    EXPECT_FALSE( client2.IsConnected() );
    // Moved-from client1 has null m_impl — IsConnected() must be safe (no segfault).
    EXPECT_FALSE( client1.IsConnected() );
}

TEST( SGClient, DisconnectBeforeInitDoesNotCrash )
{
    SGClient::Config cfg;
    SGClient client( std::move( cfg ) );
    // Disconnect() on a never-initialized client must be safe (no SDK node up).
    client.Disconnect();
    EXPECT_FALSE( client.IsConnected() );
}
