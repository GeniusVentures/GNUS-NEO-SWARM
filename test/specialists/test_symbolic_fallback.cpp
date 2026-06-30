/**
 * @file       test_symbolic_fallback.cpp
 * @brief      Unit tests for SymbolicFallback expression parser — happy, unhappy, fuzz
 * @date       2026-06-16
 */

#include "specialists/symbolic_fallback.hpp"
#include <gtest/gtest.h>
#include <random>
#include <string>

using sgns::neoswarm::specialists::SymbolicFallback;

// =======================================================================
// Happy path — basic arithmetic
// =======================================================================

TEST( SymbolicFallback, Evaluate_Addition )
{
    auto r = SymbolicFallback::Evaluate( "2 + 3" );
    ASSERT_TRUE( r.has_value() );
    EXPECT_DOUBLE_EQ( r.value(), 5.0 );
}

TEST( SymbolicFallback, Evaluate_Subtraction )
{
    auto r = SymbolicFallback::Evaluate( "10 - 7" );
    ASSERT_TRUE( r.has_value() );
    EXPECT_DOUBLE_EQ( r.value(), 3.0 );
}

TEST( SymbolicFallback, Evaluate_Multiplication )
{
    auto r = SymbolicFallback::Evaluate( "6 * 7" );
    ASSERT_TRUE( r.has_value() );
    EXPECT_DOUBLE_EQ( r.value(), 42.0 );
}

TEST( SymbolicFallback, Evaluate_Division )
{
    auto r = SymbolicFallback::Evaluate( "100 / 4" );
    ASSERT_TRUE( r.has_value() );
    EXPECT_DOUBLE_EQ( r.value(), 25.0 );
}

TEST( SymbolicFallback, Evaluate_OperatorPrecedence )
{
    auto r = SymbolicFallback::Evaluate( "2 + 3 * 4" );
    ASSERT_TRUE( r.has_value() );
    EXPECT_DOUBLE_EQ( r.value(), 14.0 );
}

TEST( SymbolicFallback, Evaluate_NestedParentheses )
{
    auto r = SymbolicFallback::Evaluate( "(1 + 2) * (3 + 4)" );
    ASSERT_TRUE( r.has_value() );
    EXPECT_DOUBLE_EQ( r.value(), 21.0 );
}

TEST( SymbolicFallback, Evaluate_FloatingPoint )
{
    auto r = SymbolicFallback::Evaluate( "3.5 + 2.5" );
    ASSERT_TRUE( r.has_value() );
    EXPECT_DOUBLE_EQ( r.value(), 6.0 );
}

TEST( SymbolicFallback, Evaluate_NegativeNumber )
{
    auto r = SymbolicFallback::Evaluate( "-5 + 3" );
    ASSERT_TRUE( r.has_value() );
    EXPECT_DOUBLE_EQ( r.value(), -2.0 );
}

TEST( SymbolicFallback, Evaluate_IntegerResult )
{
    auto r = SymbolicFallback::Evaluate( "847 * 963" );
    ASSERT_TRUE( r.has_value() );
    EXPECT_DOUBLE_EQ( r.value(), 815661.0 );
}

// =======================================================================
// Unhappy path — error recovery
// =======================================================================

TEST( SymbolicFallback, Evaluate_DivisionByZero )
{
    auto r = SymbolicFallback::Evaluate( "1 / 0" );
    EXPECT_FALSE( r.has_value() );
}

TEST( SymbolicFallback, Evaluate_EmptyString )
{
    EXPECT_FALSE( SymbolicFallback::Evaluate( "" ).has_value() );
}

TEST( SymbolicFallback, Evaluate_WhitespaceOnly )
{
    EXPECT_FALSE( SymbolicFallback::Evaluate( "   " ).has_value() );
    EXPECT_FALSE( SymbolicFallback::Evaluate( "\t\n" ).has_value() );
}

TEST( SymbolicFallback, Evaluate_TrailingGarbage )
{
    EXPECT_FALSE( SymbolicFallback::Evaluate( "1 + 2 x" ).has_value() );
}

TEST( SymbolicFallback, Evaluate_IncompleteExpression )
{
    EXPECT_FALSE( SymbolicFallback::Evaluate( "1 +" ).has_value() );
    EXPECT_FALSE( SymbolicFallback::Evaluate( "* 5" ).has_value() );
}

TEST( SymbolicFallback, Evaluate_DoubleOperator )
{
    EXPECT_FALSE( SymbolicFallback::Evaluate( "1 + * 2" ).has_value() );
}

// =======================================================================
// ExtractAndEvaluate
// =======================================================================

TEST( SymbolicFallback, ExtractAndEvaluate_PlainExpression )
{
    auto r = SymbolicFallback::ExtractAndEvaluate( "2 + 2 = ?" );
    ASSERT_TRUE( r.has_value() );
    EXPECT_DOUBLE_EQ( r.value(), 4.0 );
}

TEST( SymbolicFallback, ExtractAndEvaluate_NoExpression )
{
    auto r = SymbolicFallback::ExtractAndEvaluate( "hello world" );
    EXPECT_FALSE( r.has_value() );
}

TEST( SymbolicFallback, ExtractAndEvaluate_EmptyText )
{
    auto r = SymbolicFallback::ExtractAndEvaluate( "" );
    EXPECT_FALSE( r.has_value() );
}

// =======================================================================
// FormatResult
// =======================================================================

TEST( SymbolicFallback, FormatResult_Integer )
{
    EXPECT_EQ( SymbolicFallback::FormatResult( 42.0 ), "42" );
    EXPECT_EQ( SymbolicFallback::FormatResult( -7.0 ), "-7" );
}

TEST( SymbolicFallback, FormatResult_Decimal )
{
    EXPECT_EQ( SymbolicFallback::FormatResult( 3.14 ), "3.14" );
    EXPECT_EQ( SymbolicFallback::FormatResult( -2.5 ), "-2.5" );
}

TEST( SymbolicFallback, FormatResult_LargeNumber )
{
    auto result = SymbolicFallback::FormatResult( 1e15 + 0.1 );
    EXPECT_NE( result.find( "1e" ), std::string::npos );
}

// =======================================================================
// Fuzz — random expressions, must not crash
// =======================================================================

TEST( SymbolicFallback, Fuzz_RandomExpressions_NoCrash )
{
    std::mt19937 rng( 42 );
    const char kChars[] = "0123456789+-*/(). ";

    for ( int round = 0; round < 5000; ++round )
    {
        std::string expr;
        size_t len = std::uniform_int_distribution<size_t>( 0, 256 )( rng );
        for ( size_t i = 0; i < len; ++i )
        {
            expr.push_back( kChars[ std::uniform_int_distribution<size_t>( 0, sizeof( kChars ) - 2 )( rng ) ] );
        }
        auto result = SymbolicFallback::Evaluate( expr );
        (void)result;
    }
    SUCCEED();
}

TEST( SymbolicFallback, Fuzz_BinaryGarbage_NoCrash )
{
    std::mt19937 rng( 42 );

    for ( int round = 0; round < 1000; ++round )
    {
        std::string expr;
        size_t len = std::uniform_int_distribution<size_t>( 0, 256 )( rng );
        for ( size_t i = 0; i < len; ++i )
        {
            expr.push_back( static_cast<char>( std::uniform_int_distribution<int>( 0, 255 )( rng ) ) );
        }
        auto result = SymbolicFallback::Evaluate( expr );
        (void)result;
    }
    SUCCEED();
}

TEST( SymbolicFallback, Fuzz_DeeplyNested_NoStackOverflow )
{
    // 200 levels of nesting — must not stack overflow
    std::string expr;
    for ( int i = 0; i < 200; ++i )
    {
        expr += "(";
    }
    expr += "1";
    for ( int i = 0; i < 200; ++i )
    {
        expr += ")";
    }

    auto result = SymbolicFallback::Evaluate( expr );
    // It may fail to parse, but must not crash
    (void)result;
    SUCCEED();
}
