/**
 * @file       test_sg_client.cpp
 * @brief      Unit tests for SGJobSubmitter and SGResultCollector
 * @date       2026-07-09
 */

#include "network/sg_client/sg_job_submitter.hpp"
#include "network/sg_client/sg_result_collector.hpp"
#include "common/error.hpp"
#include <gtest/gtest.h>
#include <chrono>
#include <future>

using namespace sgns::neoswarm::network;

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
    EXPECT_EQ( cfg.m_resultTimeout, std::chrono::seconds( 120 ) );
}

TEST( SGResultCollector, CustomTimeoutAccepted )
{
    SGResultCollectorConfig cfg;
    cfg.m_resultTimeout = std::chrono::seconds( 30 );
    SGResultCollector collector( cfg );
}

TEST( SGResultCollector, ShortTimeoutReturnsError )
{
    SGResultCollector collector;
    auto start = std::chrono::steady_clock::now();
    auto result = collector.PollForResult( std::chrono::seconds( 1 ) );
    auto elapsed = std::chrono::steady_clock::now() - start;

    ASSERT_FALSE( result.has_value() );
    // Should return within timeout window
    EXPECT_LE( elapsed, std::chrono::seconds( 3 ) );
}

TEST( SGResultCollector, AsyncPollCompletesGracefully )
{
    SGResultCollectorConfig cfg;
    cfg.m_resultTimeout = std::chrono::seconds( 1 );
    SGResultCollector collector( cfg );
    auto future = collector.PollForResultAsync();
    auto status = future.wait_for( std::chrono::seconds( 3 ) );
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
    auto r1 = collector1.PollForResult( std::chrono::seconds( 1 ) );
    auto r2 = collector2.PollForResult( std::chrono::seconds( 1 ) );
    ASSERT_FALSE( r1.has_value() );
    ASSERT_FALSE( r2.has_value() );
}
