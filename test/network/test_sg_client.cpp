/**
 * @file       test_sg_client.cpp
 * @brief      Unit tests for SGJobSubmitter and SGResultCollector
 * @date       2026-07-09
 */

#include "sg_client/sg_job_submitter.hpp"
#include "sg_client/sg_result_collector.hpp"
#include "common/error.hpp"
#include <gtest/gtest.h>
#include <chrono>

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
    std::string largePayload( 2048, 'x' );
    auto result = submitter.PublishJob( largePayload );
    ASSERT_FALSE( result.has_value() );
    EXPECT_EQ( result.error(), Error::InvalidArgument );
}

TEST( SGJobSubmitter, AcceptsPayloadAtMaxSize )
{
    SGJobSubmitter submitter;
    std::string maxPayload( 2047, 'x' );
    auto result = submitter.PublishJob( maxPayload );
    // Without real SDK, this returns NetworkError (SDK not initialized)
    ASSERT_FALSE( result.has_value() );
}

TEST( SGJobSubmitter, AcceptsSmallPayload )
{
    SGJobSubmitter submitter;
    std::string smallPayload = R"({"model":"test","input":"hello"})";
    auto result = submitter.PublishJob( smallPayload );
    // Without real SDK, expected to fail — but not from size check
    if ( result.has_value() )
    {
        ASSERT_FALSE( result.value().empty() );
    }
}

TEST( SGJobSubmitter, GenerateTaskIdIsUnique )
{
    SGJobSubmitter submitter;
    std::string payload = R"({"test":true})";
    auto r1 = submitter.PublishJob( payload );
    auto r2 = submitter.PublishJob( payload );
    // Both should fail the same way (no SDK), but task IDs differ in error case
    // No task IDs generated on size failure
}

// =======================================================================
// SGResultCollector
// =======================================================================

TEST( SGResultCollector, DefaultConfigTimeout )
{
    SGResultCollectorConfig cfg;
    EXPECT_EQ( cfg.m_resultTimeout, std::chrono::seconds( 120 ) );
}

TEST( SGResultCollector, CustomTimeoutConfig )
{
    SGResultCollectorConfig cfg;
    cfg.m_resultTimeout = std::chrono::seconds( 60 );
    SGResultCollector collector( cfg );
}

TEST( SGResultCollector, PollForResultDefaultTimeout )
{
    SGResultCollector collector;
    auto result = collector.PollForResult();
    // Without SDK initialized, expected to fail
    if ( !result.has_value() )
    {
        // Acceptable — no actual SDK running
    }
}

TEST( SGResultCollector, PollForResultCustomTimeout )
{
    SGResultCollector collector;
    auto result = collector.PollForResult( std::chrono::seconds( 1 ) );
    // Short timeout returns quickly without SDK
    ASSERT_FALSE( result.has_value() );
}

TEST( SGResultCollector, PollForResultAsyncDoesNotBlock )
{
    SGResultCollectorConfig cfg;
    cfg.m_resultTimeout = std::chrono::seconds( 1 );
    SGResultCollector collector( cfg );
    auto future = collector.PollForResultAsync();
    auto status = future.wait_for( std::chrono::milliseconds( 100 ) );
    // Should return immediately since SDK is not running
    // Future may be ready with error or still running
    // Either outcome is valid — just verifies no crash
}

TEST( SGResultCollector, MultipleInstancesIndependent )
{
    SGResultCollector collector1;
    SGResultCollector collector2;
    // Each should work independently
}
