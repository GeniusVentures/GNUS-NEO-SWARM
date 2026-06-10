/**
 * @file       test_router.cpp
 * @brief      Unit tests for PromptAnalyzer and RuleBasedRouter
 * @date       2026-05-08
 * @author     Subaskar S (ssivakumar@gnus.ai)
 */

#include "router/prompt_analyzer.hpp"
#include "router/rule_based_router.hpp"
#include <gtest/gtest.h>

using namespace sgns::neoswarm;
using namespace sgns::neoswarm::router;

TEST( PromptAnalyzer, NumericDensityHigh )
{
    PromptAnalyzer analyzer;
    auto f = analyzer.Analyze( "What is 847 × 963 + 12.5 / 3?" );
    EXPECT_GT( f.numeric_density_, 0.2f );
}

TEST( PromptAnalyzer, NumericDensityLow )
{
    PromptAnalyzer analyzer;
    auto f = analyzer.Analyze( "Tell me a story about a brave knight." );
    EXPECT_LT( f.numeric_density_, 0.1f );
}

TEST( PromptAnalyzer, MathKeywords )
{
    PromptAnalyzer analyzer;
    auto f = analyzer.Analyze( "Solve the quadratic equation x^2 + 5x + 6 = 0" );
    EXPECT_TRUE( f.has_math_keywords_ );
}

TEST( PromptAnalyzer, GrammarRequest )
{
    PromptAnalyzer analyzer;
    auto f = analyzer.Analyze( "Please proofread and fix my grammar in this paragraph." );
    EXPECT_TRUE( f.has_grammar_request_ );
}

TEST( PromptAnalyzer, CodeSyntax )
{
    PromptAnalyzer analyzer;
    auto f = analyzer.Analyze( "def fibonacci(n):\n    if n <= 1: return n" );
    EXPECT_TRUE( f.has_code_syntax_ );
}

TEST( RuleBasedRouter, RouteMathByDensity )
{
    RuleBasedRouter router;
    Task task;
    task.m_prompt = "Calculate 847 × 963 + 12 / 4 - 100";
    task.m_mode = ExecutionMode::SingleNode;

    auto res = router.Route( task );
    ASSERT_TRUE( res.has_value() );
    EXPECT_EQ( res.value().m_target, RouteTarget::CorePlusMath );
}

TEST( RuleBasedRouter, RouteMathByKeyword )
{
    RuleBasedRouter router;
    Task task;
    task.m_prompt = "Solve the integral of x^2 from 0 to 1";
    task.m_mode = ExecutionMode::SingleNode;

    auto res = router.Route( task );
    ASSERT_TRUE( res.has_value() );
    EXPECT_EQ( res.value().m_target, RouteTarget::CorePlusMath );
}

TEST( RuleBasedRouter, RouteGrammar )
{
    RuleBasedRouter router;
    Task task;
    task.m_prompt = "Please fix my grammar: I goes to the store yesterday.";
    task.m_mode = ExecutionMode::SingleNode;

    auto res = router.Route( task );
    ASSERT_TRUE( res.has_value() );
    EXPECT_EQ( res.value().m_target, RouteTarget::CorePlusGrammar );
}

TEST( RuleBasedRouter, RouteCoreOnly )
{
    RuleBasedRouter router;
    Task task;
    task.m_prompt = "Tell me about the history of ancient Rome.";
    task.m_mode = ExecutionMode::SingleNode;

    auto res = router.Route( task );
    ASSERT_TRUE( res.has_value() );
    EXPECT_EQ( res.value().m_target, RouteTarget::CoreOnly );
}

TEST( RuleBasedRouter, HonourExplicitSwarmMode )
{
    RuleBasedRouter router;
    Task task;
    task.m_prompt = "Simple question";
    task.m_mode = ExecutionMode::Swarm;

    auto res = router.Route( task );
    ASSERT_TRUE( res.has_value() );
    EXPECT_EQ( res.value().m_mode, ExecutionMode::Swarm );
}

TEST( RuleBasedRouter, ConfidenceInRange )
{
    RuleBasedRouter router;
    Task task;
    task.m_prompt = "What is 2 + 2?";
    task.m_mode = ExecutionMode::SingleNode;

    auto res = router.Route( task );
    ASSERT_TRUE( res.has_value() );
    EXPECT_GE( res.value().confidence_, 0.0f );
    EXPECT_LE( res.value().confidence_, 1.0f );
}
