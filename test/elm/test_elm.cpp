/**
 * @file       test_elm.cpp
 * @brief      Unit tests for Expert Language Model implementations
 * @date       2026-07-16
 */

#include "elm/role_elm.hpp"

// #include "elm/domain_elm.hpp" — added in Task 2 RED phase

#include <gtest/gtest.h>

#include <memory>
#include <string>

using namespace sgns::neoswarm;

// -----------------------------------------------------------------------
// Mock inference engine — returns prompt + "[response]" with perplexity=1.0
// (verbatim copy of mock pattern from test/specialists/test_grammar_specialist.cpp)
// -----------------------------------------------------------------------
namespace
{
    class MockEngine : public core::InferenceEngine
    {
        public:
        outcome::result<InferenceResponse> Infer( const Task& task ) override
        {
            InferenceResponse resp;
            resp.m_output = task.m_prompt + " [response]";
            resp.m_perplexity = 1.0f;
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

} // namespace

// -----------------------------------------------------------------------
// RoleELM tests
// -----------------------------------------------------------------------

TEST( RoleELM, Process_LoadedEngine_ReturnsResponse )
{
    auto engine = std::make_shared<MockEngine>();
    elm::RoleELM elm( ELMRole::Verifier, engine );
    ASSERT_TRUE( elm.Load( "dummy" ).has_value() );
    ASSERT_TRUE( elm.IsLoaded() );

    ELMContext ctx;
    ctx.m_originalTask = "test task";
    auto result = elm.Process( "input text", ctx );
    ASSERT_TRUE( result.has_value() );
    EXPECT_NE( result.value().find( "input" ), std::string::npos );
    EXPECT_GT( elm.GetConfidence(), 0.0f );
}

TEST( RoleELM, Process_NotLoaded_ReturnsInputUnchanged )
{
    auto engine = std::make_shared<MockEngine>();
    elm::RoleELM elm( ELMRole::Verifier, engine );

    ELMContext ctx;
    auto result = elm.Process( "hello world", ctx );
    ASSERT_TRUE( result.has_value() );
    EXPECT_EQ( result.value(), "hello world" );
    EXPECT_FLOAT_EQ( elm.GetConfidence(), 0.0f );
}

TEST( RoleELM, GetName_ReturnsCorrectName )
{
    auto engine = std::make_shared<MockEngine>();
    elm::RoleELM planner( ELMRole::Planner, engine );
    EXPECT_EQ( planner.GetName(), "Planner" );

    elm::RoleELM verifier( ELMRole::Verifier, engine );
    EXPECT_EQ( verifier.GetName(), "Verifier" );
}

TEST( RoleELM, GetRole_ReturnsConfiguredRole )
{
    auto engine = std::make_shared<MockEngine>();
    elm::RoleELM elm( ELMRole::Arbiter, engine );
    EXPECT_EQ( elm.GetRole(), ELMRole::Arbiter );
}

TEST( RoleELM, IsLoaded_InitiallyFalse )
{
    elm::RoleELM elm( ELMRole::Refiner, nullptr );
    EXPECT_FALSE( elm.IsLoaded() );
}

TEST( RoleELM, Process_NullEngine_ReturnsInputUnchanged )
{
    elm::RoleELM elm( ELMRole::PrimaryDraft, nullptr );

    ELMContext ctx;
    auto result = elm.Process( "hello", ctx );
    ASSERT_TRUE( result.has_value() );
    EXPECT_EQ( result.value(), "hello" );
    EXPECT_FLOAT_EQ( elm.GetConfidence(), 0.0f );
}
