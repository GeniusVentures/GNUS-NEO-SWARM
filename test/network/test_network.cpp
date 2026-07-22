/**
 * @file       test_network.cpp
 * @brief      Unit tests for P2PNode and ResultAggregation
 * @date       2026-05-28
 */

#include "common/types.hpp"
#include "network/p2p_node.hpp"
#include "network/result_aggregation.hpp"
#include "security/node_identity.hpp"
#include <gtest/gtest.h>

using namespace sgns::neoswarm;
using namespace sgns::neoswarm::network;
using namespace sgns::neoswarm::security;

TEST( P2PNode, ConstructWithConfig )
{
    auto identity = std::make_shared<NodeIdentity>();
    ASSERT_TRUE( identity->Generate().has_value() );

    P2PNode::Config cfg;
    P2PNode node( identity, cfg );

    SUCCEED();
}

TEST( P2PNode, ConstructWithoutConfig )
{
    auto identity = std::make_shared<NodeIdentity>();
    ASSERT_TRUE( identity->Generate().has_value() );

    P2PNode node( identity );

    SUCCEED();
}

TEST( P2PNode, StopBeforeStartDoesNotCrash )
{
    auto identity = std::make_shared<NodeIdentity>();
    ASSERT_TRUE( identity->Generate().has_value() );

    P2PNode node( identity );
    node.Stop();
    SUCCEED();
}

TEST( ResultAggregation, CollectEmptyWithTimeout )
{
    ResultAggregation::Config cfg;
    cfg.m_timeout = std::chrono::milliseconds( 50 );
    cfg.min_responses_ = 1;

    ResultAggregation agg( cfg );

    auto result = agg.Collect();
    // No results submitted — timeout returns BroadcastTimeout error
    EXPECT_FALSE( result.has_value() );
    EXPECT_EQ( agg.ResponseCount(), 0U );
}

TEST( ResultAggregation, SubmitAndCollectSingle )
{
    ResultAggregation::Config cfg;
    cfg.m_timeout = std::chrono::milliseconds( 200 );
    cfg.min_responses_ = 1;

    ResultAggregation agg( cfg );

    NodeOutput output;
    output.m_nodeId = "test-node-1";
    output.m_output = "test output";
    output.m_latencyMs = 100.0;

    agg.Submit( output );

    auto result = agg.Collect();
    EXPECT_TRUE( result.has_value() );
    EXPECT_FALSE( result.value().empty() );
    EXPECT_EQ( result.value()[0].m_nodeId, "test-node-1" );
    EXPECT_EQ( agg.ResponseCount(), 1U );
}

TEST( ResultAggregation, ResetClearsState )
{
    ResultAggregation::Config cfg;
    cfg.m_timeout = std::chrono::milliseconds( 50 );
    cfg.min_responses_ = 1;

    ResultAggregation agg( cfg );

    NodeOutput output;
    output.m_nodeId = "test-node";
    agg.Submit( output );

    agg.Reset();

    EXPECT_EQ( agg.ResponseCount(), 0U );
}
