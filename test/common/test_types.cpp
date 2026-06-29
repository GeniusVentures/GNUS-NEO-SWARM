#include "common/types.hpp"
#include <gtest/gtest.h>

using namespace sgns::neoswarm;

TEST(ExecutionMode, EnumValues_AreDistinct)
{
    EXPECT_NE( static_cast<int>( ExecutionMode::SingleNode ), static_cast<int>( ExecutionMode::Specialist ) );
    EXPECT_NE( static_cast<int>( ExecutionMode::SingleNode ), static_cast<int>( ExecutionMode::Swarm ) );
    EXPECT_NE( static_cast<int>( ExecutionMode::Specialist ), static_cast<int>( ExecutionMode::Swarm ) );
}

TEST(RouteTarget, EnumValues_AreDistinct)
{
    EXPECT_NE( static_cast<int>( RouteTarget::CoreOnly ), static_cast<int>( RouteTarget::CorePlusMath ) );
    EXPECT_NE( static_cast<int>( RouteTarget::CoreOnly ), static_cast<int>( RouteTarget::CorePlusGrammar ) );
    EXPECT_NE( static_cast<int>( RouteTarget::CorePlusMath ),
               static_cast<int>( RouteTarget::CorePlusGrammar ) );
}

TEST(Task, DefaultConstructor_HasReasonableDefaults)
{
    Task task;
    EXPECT_EQ( task.m_mode, ExecutionMode::SingleNode );
    EXPECT_EQ( task.m_maxTokens, 512 );
    EXPECT_FLOAT_EQ( task.m_temperature, 0.7f );
    EXPECT_TRUE( task.m_id.empty() );
    EXPECT_TRUE( task.m_prompt.empty() );
    EXPECT_TRUE( task.m_nodeId.empty() );
}

TEST(InferenceResponse, DefaultConstructor_HasReasonableDefaults)
{
    InferenceResponse resp;
    EXPECT_EQ( resp.m_modeUsed, ExecutionMode::SingleNode );
    EXPECT_EQ( resp.m_routeUsed, RouteTarget::CoreOnly );
    EXPECT_FLOAT_EQ( resp.m_perplexity, 1.0f );
    EXPECT_DOUBLE_EQ( resp.m_totalLatencyMs, 0.0 );
    EXPECT_TRUE( resp.m_success );
    EXPECT_TRUE( resp.m_output.empty() );
    EXPECT_TRUE( resp.m_taskId.empty() );
}

TEST(RouteDecision, DefaultConstructor_HasReasonableDefaults)
{
    RouteDecision decision;
    EXPECT_EQ( decision.m_target, RouteTarget::CoreOnly );
    EXPECT_FLOAT_EQ( decision.confidence_, 1.0f );
    EXPECT_EQ( decision.m_mode, ExecutionMode::SingleNode );
    EXPECT_TRUE( decision.m_reasoning.empty() );
}

TEST(NodeOutput, DefaultConstructor_ReasonableDefaults)
{
    NodeOutput output;
    EXPECT_FLOAT_EQ( output.m_perplexity, 1.0f );
    EXPECT_DOUBLE_EQ( output.m_latencyMs, 0.0 );
    EXPECT_DOUBLE_EQ( output.reputation_, 0.5 );
    EXPECT_TRUE( output.m_nodeId.empty() );
    EXPECT_TRUE( output.m_output.empty() );
}

TEST(NodeReputation, DefaultConstructor_ReasonableDefaults)
{
    NodeReputation rep;
    EXPECT_DOUBLE_EQ( rep.m_globalScore, 0.5 );
    EXPECT_DOUBLE_EQ( rep.m_mathScore, 0.5 );
    EXPECT_DOUBLE_EQ( rep.m_grammarScore, 0.5 );
    EXPECT_DOUBLE_EQ( rep.m_latencyScore, 0.5 );
    EXPECT_DOUBLE_EQ( rep.m_consistencyScore, 0.5 );
    EXPECT_EQ( rep.m_taskCount, 0 );
    EXPECT_EQ( rep.m_lastUpdatedMs, 0 );
    EXPECT_TRUE( rep.m_identityKey.empty() );
}

TEST(PromptFeatures, DefaultConstructor_AllFalse)
{
    PromptFeatures pf;
    EXPECT_FLOAT_EQ( pf.numeric_density_, 0.0f );
    EXPECT_FALSE( pf.has_code_syntax_ );
    EXPECT_FLOAT_EQ( pf.complexity_, 0.0f );
    EXPECT_EQ( pf.token_count_, 0 );
    EXPECT_FALSE( pf.has_math_keywords_ );
    EXPECT_FALSE( pf.has_grammar_request_ );
}

TEST(KnowledgeFact, DefaultConstructor_ReasonableDefaults)
{
    KnowledgeFact fact;
    EXPECT_FLOAT_EQ( fact.m_relevanceScore, 0.0f );
    EXPECT_TRUE( fact.m_source.empty() );
    EXPECT_TRUE( fact.m_content.empty() );
}
