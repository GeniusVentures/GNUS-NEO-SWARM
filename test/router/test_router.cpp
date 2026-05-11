/**
 * @file       test_router.cpp
 * @brief      Unit tests for PromptAnalyzer and RuleBasedRouter
 * @date       2026-05-08
 * @author     Subaskar S (ssivakumar@gnus.ai)
 */

#include <gtest/gtest.h>
#include "router/RuleBasedRouter.hpp"
#include "router/PromptAnalyzer.hpp"

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
    Task            task;
    task.prompt_ = "Calculate 847 × 963 + 12 / 4 - 100";
    task.mode_   = ExecutionMode::SingleNode;

    auto res = router.Route( task );
    ASSERT_TRUE( res.has_value() );
    EXPECT_EQ( res.value().target_, RouteTarget::CorePlusMath );
}

TEST( RuleBasedRouter, RouteMathByKeyword )
{
    RuleBasedRouter router;
    Task            task;
    task.prompt_ = "Solve the integral of x^2 from 0 to 1";
    task.mode_   = ExecutionMode::SingleNode;

    auto res = router.Route( task );
    ASSERT_TRUE( res.has_value() );
    EXPECT_EQ( res.value().target_, RouteTarget::CorePlusMath );
}

TEST( RuleBasedRouter, RouteGrammar )
{
    RuleBasedRouter router;
    Task            task;
    task.prompt_ = "Please fix my grammar: I goes to the store yesterday.";
    task.mode_   = ExecutionMode::SingleNode;

    auto res = router.Route( task );
    ASSERT_TRUE( res.has_value() );
    EXPECT_EQ( res.value().target_, RouteTarget::CorePlusGrammar );
}

TEST( RuleBasedRouter, RouteCoreOnly )
{
    RuleBasedRouter router;
    Task            task;
    task.prompt_ = "Tell me about the history of ancient Rome.";
    task.mode_   = ExecutionMode::SingleNode;

    auto res = router.Route( task );
    ASSERT_TRUE( res.has_value() );
    EXPECT_EQ( res.value().target_, RouteTarget::CoreOnly );
}

TEST( RuleBasedRouter, HonourExplicitSwarmMode )
{
    RuleBasedRouter router;
    Task            task;
    task.prompt_ = "Simple question";
    task.mode_   = ExecutionMode::Swarm;

    auto res = router.Route( task );
    ASSERT_TRUE( res.has_value() );
    EXPECT_EQ( res.value().mode_, ExecutionMode::Swarm );
}

TEST( RuleBasedRouter, ConfidenceInRange )
{
    RuleBasedRouter router;
    Task            task;
    task.prompt_ = "What is 2 + 2?";
    task.mode_   = ExecutionMode::SingleNode;

    auto res = router.Route( task );
    ASSERT_TRUE( res.has_value() );
    EXPECT_GE( res.value().confidence_, 0.0f );
    EXPECT_LE( res.value().confidence_, 1.0f );
}
