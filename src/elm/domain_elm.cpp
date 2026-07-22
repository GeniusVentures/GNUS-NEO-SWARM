/**
 * @file       domain_elm.cpp
 * @brief      DomainELM implementation — optional dedicated model with shared-backbone fallback
 * @date       2026-07-16
 */

#include "domain_elm.hpp"
#include "core/engine/mnn_inference_engine.hpp"
#include "common/logging.hpp"

#include <string>
#include <unordered_map>

namespace sgns::neoswarm::elm
{
    namespace
    {
        auto DomainLogger()
        {
            return neoswarm::CreateLogger( "DomainELM" );
        }
    } // namespace

    // -----------------------------------------------------------------------
    // Constructor
    // -----------------------------------------------------------------------
    DomainELM::DomainELM( ELMRole role, std::shared_ptr<core::InferenceEngine> sharedEngine )
        : m_role( role )
        , m_sharedEngine( std::move( sharedEngine ) )
    {
        static const std::unordered_map<ELMRole, std::string> kRoleNames = {
            { ELMRole::Planner,      "Planner" },
            { ELMRole::PrimaryDraft, "PrimaryDraft" },
            { ELMRole::Verifier,     "Verifier" },
            { ELMRole::Arbiter,      "Arbiter" },
            { ELMRole::Refiner,      "Refiner/Formatter" },
            { ELMRole::Grounding,    "Grounding" },
            { ELMRole::ToolSupport,  "ToolSupport" },
            { ELMRole::Math,         "Math" },
            { ELMRole::Code,         "Code" },
            { ELMRole::Science,      "Science" },
        };
        auto it = kRoleNames.find( m_role );
        m_name = ( it != kRoleNames.end() ) ? it->second : "Unknown";
    }

    // -----------------------------------------------------------------------
    // SelectEngine — dual-mode: own engine if loaded, shared otherwise
    // -----------------------------------------------------------------------
    core::InferenceEngine* DomainELM::SelectEngine() const noexcept
    {
        if ( m_ownsEngine && m_ownEngine )
        {
            return m_ownEngine.get();
        }
        return m_sharedEngine.get();
    }

    // -----------------------------------------------------------------------
    // Load — dual-mode logic (D-02, D-04)
    // -----------------------------------------------------------------------
    outcome::result<void> DomainELM::Load( const std::string& model_path )
    {
        if ( !model_path.empty() )
        {
            // Per D-02: load dedicated model file into own engine
            m_ownEngine = std::make_unique<core::MNNInferenceEngine>();
            BOOST_OUTCOME_TRY( m_ownEngine->LoadModel( model_path ) );
            m_ownsEngine = true;
            m_loaded = true;
            DomainLogger()->info( "DomainELM loaded own model: {} ({})", m_name, model_path );
            return outcome::success();
        }

        // Per D-01: use shared backbone
        if ( !m_sharedEngine )
        {
            // Per D-04: no engine available — fail
            DomainLogger()->warn( "DomainELM::Load — no engine available for {}", m_name );
            return outcome::failure( Error::ModelLoadFailed );
        }

        // Shared engine is already loaded by ApiServer
        m_loaded = true;
        m_ownsEngine = false;
        DomainLogger()->info( "DomainELM using shared backbone: {}", m_name );
        return outcome::success();
    }

    // -----------------------------------------------------------------------
    // BuildPrompt — 3 domain-specific [INST] templates
    // -----------------------------------------------------------------------
    std::string DomainELM::BuildPrompt( const std::string& input, const ELMContext& /*context*/ ) const
    {
        switch ( m_role )
        {
        case ELMRole::Math:
            return "[INST] You are a Math specialist. Solve the following problem step by step. "
                   "Show your work. Provide the final answer clearly.\n\n"
                   "Problem: " +
                   input + "\n\nSolution: [/INST]";

        case ELMRole::Code:
            return "[INST] You are a Code specialist. Write clean, correct, well-commented code to solve "
                   "the following task. "
                   "Include error handling and edge cases.\n\n"
                   "Task: " +
                   input + "\n\nCode: [/INST]";

        case ELMRole::Science:
            return "[INST] You are a Science specialist. Explain the following scientific concept clearly "
                   "and accurately. "
                   "Include relevant principles, evidence, and consensus view where applicable.\n\n"
                   "Topic: " +
                   input + "\n\nExplanation: [/INST]";

        default:
            return "[INST] Respond to the following:\n\n" + input + "\n\nResponse: [/INST]";
        }
    }

    // -----------------------------------------------------------------------
    // Process — dual-engine selection + confidence
    // -----------------------------------------------------------------------
    outcome::result<std::string> DomainELM::Process( const std::string& input, const ELMContext& context )
    {
        if ( !m_loaded )
        {
            DomainLogger()->warn( "DomainELM not loaded — returning input unchanged" );
            m_lastConfidence = 0.0f;
            return outcome::failure( Error::ModelLoadFailed );
        }

        auto* engine = SelectEngine();
        if ( !engine )
        {
            DomainLogger()->warn( "DomainELM::Process — no engine available" );
            m_lastConfidence = 0.0f;
            return outcome::failure( Error::InternalError );
        }

        Task task;
        task.m_id = m_name + "-" + std::to_string( std::hash<std::string>{}( input ) );
        task.m_prompt = BuildPrompt( input, context );
        task.m_maxTokens = static_cast<uint32_t>( input.size() + 128 );
        task.m_temperature = 0.2f;

        auto res = engine->Infer( task );
        if ( !res.has_value() )
        {
            DomainLogger()->warn( "DomainELM inference failed — returning input unchanged" );
            m_lastConfidence = 0.0f;
            return outcome::failure( Error::InferenceFailed );
        }

        m_lastConfidence = 1.0f - std::min( res.value().m_perplexity / 10.0f, 1.0f );
        return outcome::success( res.value().m_output );
    }

} // namespace sgns::neoswarm::elm
