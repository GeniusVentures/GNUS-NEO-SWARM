/**
 * @file       test_chain_builder.cpp
 * @brief      Unit tests for ELMChainBuilder heuristic triggers (Phase 7, Plan 04)
 * @date       2026-07-17
 */

#include "elm/elm_chain_builder.hpp"
#include <gtest/gtest.h>

using namespace sgns::neoswarm;
using namespace sgns::neoswarm::elm;

namespace
{
    RouteDecision MakeDecision()
    {
        RouteDecision d;
        d.m_target = RouteTarget::CoreOnly;
        d.confidence_ = 0.9f;
        d.m_reasoning = "test";
        d.m_mode = ExecutionMode::ElmAssisted;
        return d;
    }
} // namespace

// -----------------------------------------------------------------------
// Trigger 1: Numeric density → Math + Verifier
// -----------------------------------------------------------------------
TEST( ELMChainBuilder, Build_HighNumericDensity_ReturnsMathVerifierChain )
{
    ELMChainBuilder builder;
    auto decision = MakeDecision();

    PromptFeatures features;
    features.numeric_density_ = 0.5f;

    auto chain = builder.Build( decision, features );
    

    EXPECT_EQ( chain.m_steps.size(), 2u );
    EXPECT_EQ( chain.m_steps[0].m_role, ELMRole::Math );
    EXPECT_EQ( chain.m_steps[1].m_role, ELMRole::Verifier );
    EXPECT_FALSE( chain.m_reasoning.empty() );
}

// -----------------------------------------------------------------------
// Trigger 2: Code syntax → Planner + Code
// -----------------------------------------------------------------------
TEST( ELMChainBuilder, Build_CodeSyntax_ReturnsPlannerCodeChain )
{
    ELMChainBuilder builder;
    auto decision = MakeDecision();

    PromptFeatures features;
    features.has_code_syntax_ = true;

    auto chain = builder.Build( decision, features );
    

    EXPECT_EQ( chain.m_steps.size(), 2u );
    EXPECT_EQ( chain.m_steps[0].m_role, ELMRole::Planner );
    EXPECT_EQ( chain.m_steps[1].m_role, ELMRole::Code );
    EXPECT_FALSE( chain.m_reasoning.empty() );
}

// -----------------------------------------------------------------------
// Trigger 3: Grounding request → Grounding + Draft + Verifier
// -----------------------------------------------------------------------
TEST( ELMChainBuilder, Build_GroundingRequest_ReturnsGroundingChain )
{
    ELMChainBuilder builder;
    auto decision = MakeDecision();

    PromptFeatures features;
    features.has_grounding_request_ = true;

    auto chain = builder.Build( decision, features );
    

    EXPECT_EQ( chain.m_steps.size(), 3u );
    EXPECT_EQ( chain.m_steps[0].m_role, ELMRole::Grounding );
    EXPECT_EQ( chain.m_steps[1].m_role, ELMRole::PrimaryDraft );
    EXPECT_EQ( chain.m_steps[2].m_role, ELMRole::Verifier );
    EXPECT_FALSE( chain.m_reasoning.empty() );
}

// -----------------------------------------------------------------------
// Trigger 4: Formatting request → Draft + Refiner
// -----------------------------------------------------------------------
TEST( ELMChainBuilder, Build_FormattingRequest_ReturnsDraftRefinerChain )
{
    ELMChainBuilder builder;
    auto decision = MakeDecision();

    PromptFeatures features;
    features.has_formatting_request_ = true;

    auto chain = builder.Build( decision, features );
    

    EXPECT_EQ( chain.m_steps.size(), 2u );
    EXPECT_EQ( chain.m_steps[0].m_role, ELMRole::PrimaryDraft );
    EXPECT_EQ( chain.m_steps[1].m_role, ELMRole::Refiner );
    EXPECT_FALSE( chain.m_reasoning.empty() );
}

// -----------------------------------------------------------------------
// Trigger 5: Low complexity → single-step PrimaryDraft
// -----------------------------------------------------------------------
TEST( ELMChainBuilder, Build_LowComplexity_ReturnsSingleStepDraft )
{
    ELMChainBuilder builder;
    auto decision = MakeDecision();

    PromptFeatures features;
    features.complexity_ = 1.0f;

    auto chain = builder.Build( decision, features );
    

    EXPECT_EQ( chain.m_steps.size(), 1u );
    EXPECT_EQ( chain.m_steps[0].m_role, ELMRole::PrimaryDraft );
    EXPECT_FALSE( chain.m_reasoning.empty() );
}

// -----------------------------------------------------------------------
// Trigger 6: High complexity → Planner + Draft + Verify + Refine
// -----------------------------------------------------------------------
TEST( ELMChainBuilder, Build_HighComplexity_ReturnsFullChain )
{
    ELMChainBuilder builder;
    auto decision = MakeDecision();

    PromptFeatures features;
    features.complexity_ = 6.0f;

    auto chain = builder.Build( decision, features );
    

    EXPECT_EQ( chain.m_steps.size(), 4u );
    EXPECT_EQ( chain.m_steps[0].m_role, ELMRole::Planner );
    EXPECT_EQ( chain.m_steps[1].m_role, ELMRole::PrimaryDraft );
    EXPECT_EQ( chain.m_steps[2].m_role, ELMRole::Verifier );
    EXPECT_EQ( chain.m_steps[3].m_role, ELMRole::Refiner );
    EXPECT_FALSE( chain.m_reasoning.empty() );
}

// -----------------------------------------------------------------------
// Default: no triggers → single-step PrimaryDraft
// -----------------------------------------------------------------------
TEST( ELMChainBuilder, Build_NoTriggers_ReturnsDefaultSingleStep )
{
    ELMChainBuilder builder;
    auto decision = MakeDecision();

    PromptFeatures features;
    features.complexity_ = 3.0f; // between low (2.0) and high (5.0) thresholds

    auto chain = builder.Build( decision, features );
    

    EXPECT_EQ( chain.m_steps.size(), 1u );
    EXPECT_EQ( chain.m_steps[0].m_role, ELMRole::PrimaryDraft );
    EXPECT_FALSE( chain.m_reasoning.empty() );
}

// -----------------------------------------------------------------------
// Reasoning is always set
// -----------------------------------------------------------------------
TEST( ELMChainBuilder, Build_EveryTrigger_SetsReasoning )
{
    ELMChainBuilder builder;
    auto decision = MakeDecision();

    // Numeric density
    {
        PromptFeatures f;
        f.numeric_density_ = 0.5f;
        auto r = builder.Build( decision, f );
        EXPECT_FALSE( r.m_reasoning.empty() );
    }
    // Code syntax
    {
        PromptFeatures f;
        f.has_code_syntax_ = true;
        auto r = builder.Build( decision, f );
        EXPECT_FALSE( r.m_reasoning.empty() );
    }
    // Grounding
    {
        PromptFeatures f;
        f.has_grounding_request_ = true;
        auto r = builder.Build( decision, f );
        EXPECT_FALSE( r.m_reasoning.empty() );
    }
    // Formatting
    {
        PromptFeatures f;
        f.has_formatting_request_ = true;
        auto r = builder.Build( decision, f );
        EXPECT_FALSE( r.m_reasoning.empty() );
    }
    // Low complexity
    {
        PromptFeatures f;
        f.complexity_ = 1.0f;
        auto r = builder.Build( decision, f );
        EXPECT_FALSE( r.m_reasoning.empty() );
    }
    // High complexity
    {
        PromptFeatures f;
        f.complexity_ = 6.0f;
        auto r = builder.Build( decision, f );
        EXPECT_FALSE( r.m_reasoning.empty() );
    }
    // Default
    {
        PromptFeatures f;
        f.complexity_ = 3.0f;
        auto r = builder.Build( decision, f );
        EXPECT_FALSE( r.m_reasoning.empty() );
    }
}
