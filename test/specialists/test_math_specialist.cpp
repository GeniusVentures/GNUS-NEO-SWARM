/**
 * @file       test_math_specialist.cpp
 * @brief      Unit tests for MathSpecialist — happy, unhappy paths
 * @date       2026-06-16
 */

#include "specialists/math_specialist.hpp"
#include "core/engine/inference_engine.hpp"
#include <functional>
#include <gtest/gtest.h>
#include <memory>

using namespace sgns::neoswarm;

namespace
{
    class MockEngine : public core::InferenceEngine
    {
    public:
        outcome::result<InferenceResponse> Infer( const Task& task ) override
        {
            InferenceResponse resp;
            resp.m_output = "42";
            resp.m_perplexity = 0.5f;
            resp.m_success = true;
            resp.m_taskId = task.m_id;
            return outcome::success( resp );
        }
        outcome::result<void> StreamInfer( const Task&,
                                            std::function<void( const std::string& )> ) override
        {
            return outcome::success();
        }
        outcome::result<void> LoadModel( const std::string& ) override
        {
            return outcome::success();
        }
        bool IsLoaded() const override
        {
            return true;
        }
        std::string BackendName() const override
        {
            return "mock";
        }
    };

    class FailingMockEngine : public core::InferenceEngine
    {
    public:
        outcome::result<InferenceResponse> Infer( const Task& ) override
        {
            return outcome::failure( Error::InferenceFailed );
        }
        outcome::result<void> StreamInfer( const Task&,
                                            std::function<void( const std::string& )> ) override
        {
            return outcome::failure( Error::InferenceFailed );
        }
        outcome::result<void> LoadModel( const std::string& ) override
        {
            return outcome::failure( Error::ModelLoadFailed );
        }
        bool IsLoaded() const override
        {
            return false;
        }
        std::string BackendName() const override
        {
            return "mock";
        }
    };
} // namespace

// =======================================================================
// Happy path
// =======================================================================

TEST( MathSpecialist, Process_LoadedEngine_ReturnsResult )
{
    auto engine = std::make_shared<MockEngine>();
    specialists::MathSpecialist specialist( engine );
    ASSERT_TRUE( specialist.Load( "dummy" ).has_value() );
    ASSERT_TRUE( specialist.IsLoaded() );

    auto result = specialist.Process( "what is 2 + 3" );
    ASSERT_TRUE( result.has_value() );
    EXPECT_FALSE( result.value().empty() );
}

TEST( MathSpecialist, GetName_ReturnsCorrectName )
{
    specialists::MathSpecialist specialist;
    EXPECT_EQ( specialist.GetName(), "MathSpecialist" );
}

TEST( MathSpecialist, IsLoaded_InitiallyFalse )
{
    specialists::MathSpecialist specialist;
    EXPECT_FALSE( specialist.IsLoaded() );
}

TEST( MathSpecialist, GetConfidence_InitiallyZero )
{
    specialists::MathSpecialist specialist;
    EXPECT_FLOAT_EQ( specialist.GetConfidence(), 0.0f );
}

// =======================================================================
// Unhappy path — fail-close
// =======================================================================

TEST( MathSpecialist, Process_NotLoaded_SymbolicFallbackWins )
{
    auto engine = std::make_shared<MockEngine>();
    specialists::MathSpecialist specialist( engine );
    // NOT calling Load()

    // Symbolic fallback runs first — succeeds for pure arithmetic
    auto result = specialist.Process( "2 + 3" );
    ASSERT_TRUE( result.has_value() );
    EXPECT_EQ( result.value(), "= 5" );
    EXPECT_FLOAT_EQ( specialist.GetConfidence(), 1.0f );
}

TEST( MathSpecialist, Process_NotLoaded_NonMath_ReturnsInputUnchanged )
{
    auto engine = std::make_shared<MockEngine>();
    specialists::MathSpecialist specialist( engine );

    // Non-math input: symbolic fails, not-loaded check → returns input unchanged
    auto result = specialist.Process( "hello world" );
    ASSERT_TRUE( result.has_value() );
    EXPECT_EQ( result.value(), "hello world" );
    EXPECT_FLOAT_EQ( specialist.GetConfidence(), 0.0f );
}

TEST( MathSpecialist, Process_InferenceFails_ReturnsInputUnchanged )
{
    // No engine at all — Process will try symbolic first, fail, then return input unchanged
    specialists::MathSpecialist specialist;
    auto result = specialist.Process( "hello world" );
    ASSERT_TRUE( result.has_value() );
    EXPECT_EQ( result.value(), "hello world" );
    EXPECT_FLOAT_EQ( specialist.GetConfidence(), 0.0f );
}

TEST( MathSpecialist, Load_NoEngine_ReturnsError )
{
    specialists::MathSpecialist specialist;
    auto result = specialist.Load( "dummy" );
    EXPECT_FALSE( result.has_value() );
}
