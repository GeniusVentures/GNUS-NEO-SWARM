/**
 * @file       test_elm.cpp
 * @brief      Unit tests for Phase 7 ELM classes
 * @date       2026-07-16
 */

#include "elm/role_elm.hpp"
#include "elm/domain_elm.hpp"
#include "elm/specialist_adapter.hpp"
#include "elm/grounding_elm.hpp"
#include "elm/tool_support_elm.hpp"
#include "elm/elm_chain_builder.hpp"
#include "core/engine/inference_engine.hpp"
#include "specialists/i_specialist.hpp"
#include "knowledge/knowledge_retrieval.hpp"
#include "knowledge/context_injection.hpp"
#include "knowledge/fact_validation.hpp"
#include <gtest/gtest.h>
#include <functional>
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

    class MockSpecialist : public specialists::ISpecialist
    {
        public:
        std::string GetName() const override
        {
            return "MockSpecialist";
        }
        bool IsLoaded() const override
        {
            return m_loaded;
        }
        outcome::result<void> Load( const std::string& ) override
        {
            m_loaded = true;
            return outcome::success();
        }
        outcome::result<std::string> Process( const std::string& input ) override
        {
            m_lastConf = 0.9f;
            return outcome::success( input + " [specialized]" );
        }
        float GetConfidence() const override
        {
            return m_lastConf;
        }

        private:
        bool m_loaded = false;
        float m_lastConf = 0.0f;
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

TEST( RoleELM, Process_NotLoaded_ReturnsError )
{
    auto engine = std::make_shared<MockEngine>();
    elm::RoleELM elm( ELMRole::Verifier, engine );

    ELMContext ctx;
    auto result = elm.Process( "hello world", ctx );
    ASSERT_FALSE( result.has_value() );
    EXPECT_EQ( result.error(), Error::NotLoaded );
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

TEST( RoleELM, Process_NullEngine_ReturnsError )
{
    elm::RoleELM elm( ELMRole::PrimaryDraft, nullptr );

    ELMContext ctx;
    auto result = elm.Process( "hello", ctx );
    ASSERT_FALSE( result.has_value() );
    EXPECT_EQ( result.error(), Error::NotLoaded );
    EXPECT_FLOAT_EQ( elm.GetConfidence(), 0.0f );
}

// -----------------------------------------------------------------------
// DomainELM tests
// -----------------------------------------------------------------------

TEST( DomainELM, Process_SharedBackbone_ReturnsResponse )
{
    auto engine = std::make_shared<MockEngine>();
    elm::DomainELM elm( ELMRole::Code, engine );
    ASSERT_TRUE( elm.Load( "" ).has_value() );
    ASSERT_TRUE( elm.IsLoaded() );

    ELMContext ctx;
    ctx.m_originalTask = "write a function";
    auto result = elm.Process( "int main()", ctx );
    ASSERT_TRUE( result.has_value() );
    EXPECT_NE( result.value().find( "int main" ), std::string::npos );
    EXPECT_GT( elm.GetConfidence(), 0.0f );
}

TEST( DomainELM, Process_NoEngine_ReturnsError )
{
    elm::DomainELM elm( ELMRole::Code, nullptr );

    ELMContext ctx;
    auto result = elm.Process( "some code", ctx );
    ASSERT_FALSE( result.has_value() );
    EXPECT_EQ( result.error(), Error::NotLoaded );
    EXPECT_FLOAT_EQ( elm.GetConfidence(), 0.0f );
}

TEST( DomainELM, GetRole_ReturnsConfiguredRole )
{
    auto engine = std::make_shared<MockEngine>();
    elm::DomainELM elm( ELMRole::Math, engine );
    EXPECT_EQ( elm.GetRole(), ELMRole::Math );
}

TEST( DomainELM, IsLoaded_InitiallyFalse )
{
    elm::DomainELM elm( ELMRole::Science, nullptr );
    EXPECT_FALSE( elm.IsLoaded() );
}

TEST( DomainELM, GetName_ReturnsCorrectName )
{
    auto engine = std::make_shared<MockEngine>();
    elm::DomainELM codeElm( ELMRole::Code, engine );
    EXPECT_EQ( codeElm.GetName(), "Code" );

    elm::DomainELM mathElm( ELMRole::Math, engine );
    EXPECT_EQ( mathElm.GetName(), "Math" );
}

TEST( DomainELM, Load_EmptyPath_UsesSharedEngine )
{
    auto engine = std::make_shared<MockEngine>();
    elm::DomainELM elm( ELMRole::Science, engine );
    auto result = elm.Load( "" );
    ASSERT_TRUE( result.has_value() );
    EXPECT_TRUE( elm.IsLoaded() );
}

// -----------------------------------------------------------------------
// SpecialistAdapter tests
// -----------------------------------------------------------------------

TEST( SpecialistAdapter, Process_DelegatesToSpecialist )
{
    auto specialist = std::make_shared<MockSpecialist>();
    elm::SpecialistAdapter adapter( specialist, ELMRole::Refiner, "RefinerAdapter" );

    ELMContext ctx;
    auto result = adapter.Process( "input", ctx );
    ASSERT_TRUE( result.has_value() );
    EXPECT_EQ( result.value(), "input [specialized]" );
}

TEST( SpecialistAdapter, GetConfidence_ReflectsSpecialist )
{
    auto specialist = std::make_shared<MockSpecialist>();
    elm::SpecialistAdapter adapter( specialist, ELMRole::Refiner, "RefinerAdapter" );

    ELMContext ctx;
    auto result = adapter.Process( "x", ctx );
    ASSERT_TRUE( result.has_value() );
    EXPECT_FLOAT_EQ( adapter.GetConfidence(), 0.9f );
}

// -----------------------------------------------------------------------
// ELMChainBuilder tests
// -----------------------------------------------------------------------

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

TEST( ELMChainBuilder, Build_HighNumericDensity_ReturnsMathChain )
{
    elm::ELMChainBuilder builder;
    auto decision = MakeDecision();

    PromptFeatures features;
    features.numeric_density_ = 0.5f;

    auto chain = builder.Build( decision, features );
    EXPECT_EQ( chain.m_steps.size(), 2u );
    EXPECT_EQ( chain.m_steps[0].m_role, ELMRole::Math );
    EXPECT_FALSE( chain.m_reasoning.empty() );
}

TEST( ELMChainBuilder, Build_CodeSyntax_ReturnsPlannerCodeChain )
{
    elm::ELMChainBuilder builder;
    auto decision = MakeDecision();

    PromptFeatures features;
    features.has_code_syntax_ = true;

    auto chain = builder.Build( decision, features );
    EXPECT_EQ( chain.m_steps.size(), 2u );
    EXPECT_EQ( chain.m_steps[0].m_role, ELMRole::Planner );
    EXPECT_TRUE( chain.m_steps[1].m_domain.has_value() );
    EXPECT_EQ( chain.m_steps[1].m_domain.value(), "code" );
    EXPECT_FALSE( chain.m_reasoning.empty() );
}

TEST( ELMChainBuilder, Build_LowComplexity_ReturnsSingleStep )
{
    elm::ELMChainBuilder builder;
    auto decision = MakeDecision();

    PromptFeatures features;
    features.complexity_ = 1.0f;

    auto chain = builder.Build( decision, features );
    EXPECT_EQ( chain.m_steps.size(), 1u );
    EXPECT_EQ( chain.m_steps[0].m_role, ELMRole::PrimaryDraft );
    EXPECT_FALSE( chain.m_reasoning.empty() );
}

TEST( ELMChainBuilder, Build_HighComplexity_ReturnsFullChain )
{
    elm::ELMChainBuilder builder;
    auto decision = MakeDecision();

    PromptFeatures features;
    features.complexity_ = 6.0f;

    auto chain = builder.Build( decision, features );
    EXPECT_EQ( chain.m_steps.size(), 4u );
    EXPECT_EQ( chain.m_steps[3].m_role, ELMRole::Refiner );
    EXPECT_FALSE( chain.m_reasoning.empty() );
}

TEST( ELMChainBuilder, Build_Default_ReturnsPrimaryDraft )
{
    elm::ELMChainBuilder builder;
    auto decision = MakeDecision();

    PromptFeatures features;

    auto chain = builder.Build( decision, features );
    EXPECT_EQ( chain.m_steps.size(), 1u );
    EXPECT_EQ( chain.m_steps[0].m_role, ELMRole::PrimaryDraft );
    EXPECT_FALSE( chain.m_reasoning.empty() );
}

// -----------------------------------------------------------------------
// GroundingELM tests
// -----------------------------------------------------------------------

TEST( GroundingELM, Process_KnowledgeLoaded_ReturnsAugmentedOutput )
{
    auto knowledge = std::make_shared<knowledge::KnowledgeRetrieval>();
    ASSERT_TRUE( knowledge->Load().has_value() );
    ASSERT_TRUE( knowledge->IsLoaded() );

    auto engine = std::make_shared<MockEngine>();
    auto contextInj = std::make_unique<knowledge::ContextInjection>();
    auto factVal = std::make_unique<knowledge::FactValidation>( knowledge );

    elm::GroundingELM elm( engine, knowledge, std::move( contextInj ), std::move( factVal ) );
    ASSERT_TRUE( elm.Load( "" ).has_value() );
    ASSERT_TRUE( elm.IsLoaded() );

    ELMContext ctx;
    auto result = elm.Process( "speed of light", ctx );
    ASSERT_TRUE( result.has_value() );
    EXPECT_FALSE( result.value().empty() );
    EXPECT_GT( elm.GetConfidence(), 0.0f );
}

// -----------------------------------------------------------------------
// ToolSupportELM tests
// -----------------------------------------------------------------------

TEST( ToolSupportELM, Process_ReturnsInputUnchanged_ConfidenceZero )
{
    elm::ToolSupportELM elm;

    ELMContext ctx;
    auto result = elm.Process( "any", ctx );
    ASSERT_TRUE( result.has_value() );
    EXPECT_EQ( result.value(), "any" );
    EXPECT_FLOAT_EQ( elm.GetConfidence(), 0.0f );
}

TEST( ToolSupportELM, IsLoaded_AlwaysFalse )
{
    elm::ToolSupportELM elm;
    EXPECT_FALSE( elm.IsLoaded() );
}
