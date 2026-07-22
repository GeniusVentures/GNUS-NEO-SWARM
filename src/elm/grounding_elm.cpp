/**
 * @file       grounding_elm.cpp
 * @brief      GroundingELM implementation — 4-stage knowledge pipeline
 * @date       2026-07-17
 */

#include "grounding_elm.hpp"
#include "common/logging.hpp"

#include <functional>

namespace sgns::neoswarm::elm
{
    namespace
    {
        auto GroundingLogger()
        {
            return neoswarm::CreateLogger( "GroundingELM" );
        }
    } // namespace

    GroundingELM::GroundingELM( std::shared_ptr<core::InferenceEngine> engine,
                                std::shared_ptr<knowledge::KnowledgeRetrieval> knowledge,
                                std::unique_ptr<knowledge::ContextInjection> contextInj,
                                std::unique_ptr<knowledge::FactValidation> factVal )
        : m_engine( std::move( engine ) )
        , m_knowledge( std::move( knowledge ) )
        , m_contextInj( std::move( contextInj ) )
        , m_factVal( std::move( factVal ) )
    {
    }

    outcome::result<void> GroundingELM::Load( const std::string& /*model_path*/ )
    {
        if ( !m_knowledge || !m_knowledge->IsLoaded() )
        {
            GroundingLogger()->warn( "GroundingELM — knowledge retrieval not available" );
            return outcome::failure( Error::KnowledgeUnavailable );
        }
        m_loaded = true;
        GroundingLogger()->info( "GroundingELM loaded" );
        return outcome::success();
    }

    outcome::result<std::string> GroundingELM::Process( const std::string& input, const ELMContext& context )
    {
        // Fail-close: no knowledge pipeline
        if ( !m_loaded || !m_knowledge || !m_engine )
        {
            GroundingLogger()->warn( "GroundingELM not loaded" );
            m_lastConfidence = 0.0f;
            return outcome::failure( Error::ModelLoadFailed );
        }

        // Stage 1: Retrieve facts (copy AugmentPrompt pattern: api_server.cpp:308-312)
        auto factsRes = m_knowledge->Retrieve( input );
        if ( !factsRes.has_value() || factsRes.value().empty() )
        {
            GroundingLogger()->debug( "GroundingELM — no facts retrieved" );
            m_lastConfidence = 0.0f;
            return outcome::failure( Error::KnowledgeUnavailable );
        }
        std::vector<KnowledgeFact> facts = std::move( factsRes.value() );

        // Stage 2: Inject facts into prompt (copy AugmentPrompt: api_server.cpp:319)
        std::string augmentedPrompt;
        if ( m_contextInj )
        {
            augmentedPrompt = m_contextInj->Inject( input, facts );
        }
        else
        {
            augmentedPrompt = input;
        }

        // Stage 3: Infer (copy grammar_specialist.cpp:69-81 Process pattern)
        Task task;
        task.m_id = "grounding-" + std::to_string( std::hash<std::string>{}( input ) );
        task.m_prompt = augmentedPrompt;
        task.m_maxTokens = static_cast<uint32_t>( input.size() + 256 );
        task.m_temperature = 0.1f;

        auto res = m_engine->Infer( task );
        if ( !res.has_value() )
        {
            GroundingLogger()->warn( "GroundingELM inference failed" );
            m_lastConfidence = 0.0f;
            return outcome::failure( Error::InferenceFailed );
        }

        std::string output = res.value().m_output;

        // Stage 4: Validate output against facts
        float confidence = 1.0f - std::min( res.value().m_perplexity / 10.0f, 1.0f );
        if ( m_factVal && m_factVal->IsAvailable() )
        {
            auto valResult = m_factVal->Validate( output, facts );
            if ( !valResult.passed_ )
            {
                GroundingLogger()->warn( "GroundingELM — fact validation found {} contradictions",
                                         valResult.m_contradictions.size() );
                confidence *= ( 1.0f - std::min( valResult.m_contradictionScore, 0.9f ) );
            }
        }

        m_lastConfidence = confidence;
        return outcome::success( output );
    }

} // namespace sgns::neoswarm::elm
