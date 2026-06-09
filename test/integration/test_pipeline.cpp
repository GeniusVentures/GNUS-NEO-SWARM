/**
 * @file       test_pipeline.cpp
 * @brief      Integration tests — full pipeline in stub mode
 * @date       2026-05-08
 * @author     Subaskar S (ssivakumar@gnus.ai)
 */

#include "api/GeniusAPIServer.hpp"
#include <gtest/gtest.h>

using namespace sgns::neoswarm;
using namespace sgns::neoswarm::api;

class PipelineTest : public ::testing::Test
{
    protected:
    void SetUp() override
    {
        GeniusAPIServer::Config cfg;
        cfg.model_path_ = ""; // stub mode
        cfg.enable_network_ = false;
        cfg.enable_knowledge_ = true;
        cfg.reputation_db_path_ = ":memory:";
        cfg.node_key_file_ = "/tmp/test_genius_node.key";

        server_ = std::make_unique<GeniusAPIServer>( cfg );
        ASSERT_TRUE( server_->Initialize().has_value() );
    }

    std::unique_ptr<GeniusAPIServer> server_;
};

TEST_F( PipelineTest, SingleNodeMode )
{
    Task task;
    task.prompt_ = "Tell me about the history of Rome.";
    task.mode_ = ExecutionMode::SingleNode;
    task.max_tokens_ = 32;
    task.temperature_ = 0.7f;

    auto res = server_->Process( task );
    ASSERT_TRUE( res.has_value() );
    EXPECT_EQ( res.value().mode_used_, ExecutionMode::SingleNode );
    EXPECT_FALSE( res.value().task_id_.empty() );
}

TEST_F( PipelineTest, MathRoutingAutoDetect )
{
    Task task;
    task.prompt_ = "Calculate 847 × 963";
    task.mode_ = ExecutionMode::SingleNode;
    task.max_tokens_ = 32;

    auto res = server_->Process( task );
    ASSERT_TRUE( res.has_value() );
    EXPECT_NE( res.value().route_used_, RouteTarget::CoreOnly );
}

TEST_F( PipelineTest, GrammarRoutingAutoDetect )
{
    Task task;
    task.prompt_ = "Please fix my grammar: I goes to store yesterday.";
    task.mode_ = ExecutionMode::SingleNode;
    task.max_tokens_ = 64;

    auto res = server_->Process( task );
    ASSERT_TRUE( res.has_value() );
    EXPECT_EQ( res.value().route_used_, RouteTarget::CorePlusGrammar );
}

TEST_F( PipelineTest, ExplicitSpecialistMode )
{
    Task task;
    task.prompt_ = "What is the square root of 144?";
    task.mode_ = ExecutionMode::Specialist;
    task.max_tokens_ = 32;

    auto res = server_->Process( task );
    ASSERT_TRUE( res.has_value() );
    EXPECT_EQ( res.value().mode_used_, ExecutionMode::Specialist );
}

TEST_F( PipelineTest, SwarmFallsBackToSingleWithoutNetwork )
{
    Task task;
    task.prompt_ = "Complex question requiring swarm";
    task.mode_ = ExecutionMode::Swarm;
    task.max_tokens_ = 32;

    auto res = server_->Process( task );
    ASSERT_TRUE( res.has_value() );
    EXPECT_TRUE( res.value().success_ );
}

TEST_F( PipelineTest, ResponseHasTaskId )
{
    Task task;
    task.prompt_ = "Hello";
    task.max_tokens_ = 16;

    auto res = server_->Process( task );
    ASSERT_TRUE( res.has_value() );
    EXPECT_FALSE( res.value().task_id_.empty() );
}

TEST_F( PipelineTest, LatencyIsPositive )
{
    Task task;
    task.prompt_ = "What is 2 + 2?";
    task.max_tokens_ = 16;

    auto res = server_->Process( task );
    ASSERT_TRUE( res.has_value() );
    EXPECT_GT( res.value().total_latency_ms_, 0.0 );
}
