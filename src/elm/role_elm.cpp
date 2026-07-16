/**
 * @file       role_elm.cpp
 * @brief      RoleELM implementation — shared-backbone ELM with 7 role-specific prompt templates
 * @date       2026-07-16
 */

#include "role_elm.hpp"
#include "common/logging.hpp"

#include <functional>
#include <string>
#include <unordered_map>

namespace sgns::neoswarm::elm
{
    namespace
    {
        auto RoleLogger()
        {
            return neoswarm::CreateLogger( "RoleELM" );
        }
    } // namespace

    // -----------------------------------------------------------------------
    // Constructor
    // -----------------------------------------------------------------------
    RoleELM::RoleELM( ELMRole role, std::shared_ptr<core::InferenceEngine> engine )
        : m_role( role )
        , m_engine( std::move( engine ) )
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
    // Load
    // -----------------------------------------------------------------------
    outcome::result<void> RoleELM::Load( const std::string& model_path )
    {
        if ( !m_engine )
        {
            RoleLogger()->warn( "RoleELM::Load — no engine available for role {}", m_name );
            return outcome::failure( Error::ModelLoadFailed );
        }
        BOOST_OUTCOME_TRY( m_engine->LoadModel( model_path ) );
        m_loaded = true;
        RoleLogger()->info( "RoleELM loaded: {} (model={})", m_name, model_path );
        return outcome::success();
    }

    // -----------------------------------------------------------------------
    // BuildPrompt — 7 role-specific [INST] templates
    // -----------------------------------------------------------------------
    std::string RoleELM::BuildPrompt( const std::string& input, const ELMContext& context ) const
    {
        switch ( m_role )
        {
        case ELMRole::Planner:
            return "[INST] You are a Planner. Analyze the following task and determine:\n"
                   "1. The primary domain (Math/Code/Science/General)\n"
                   "2. Estimated complexity (Low/Medium/High)\n"
                   "3. Recommended execution steps\n\n"
                   "Task: " +
                   input + "\n\nAnalysis: [/INST]";

        case ELMRole::PrimaryDraft:
            return "[INST] You are a Primary Draft generator. Respond to the following task directly and "
                   "completely. "
                   "Provide a well-structured answer with clear reasoning.\n\n"
                   "Task: " +
                   input + "\n\nResponse: [/INST]";

        case ELMRole::Verifier:
            return "[INST] You are a Verifier. Review the following output for factual accuracy, logical "
                   "consistency, "
                   "and completeness. "
                   "List any errors or omissions found. If the output is correct, state 'Verified: no issues "
                   "found.'\n\n"
                   "Original task: " +
                   context.m_originalTask + "\n"
                   "Output to verify:\n" +
                   input + "\n\nVerification result: [/INST]";

        case ELMRole::Arbiter:
            return "[INST] You are an Arbiter. Review conflicting outputs and determine the most correct "
                   "resolution. "
                   "Synthesize the best answer from the available information. Explain your reasoning.\n\n"
                   "Task: " +
                   input + "\n\nArbitration: [/INST]";

        case ELMRole::Refiner:
            return "[INST] You are a Refiner/Formatter. Polish the following text for grammar, spelling, "
                   "clarity, and professional formatting. "
                   "Return only the refined text without explanation.\n\n"
                   "Text to refine:\n" +
                   input + "\n\nRefined: [/INST]";

        case ELMRole::Grounding:
            return "[INST] You are a Grounding specialist. Verify the following claims against known facts. "
                   "For each claim, state whether it is supported, contradicted, or unverifiable. "
                   "Cite specific facts where possible.\n\n"
                   "Claims to verify:\n" +
                   input + "\n\nVerification: [/INST]";

        case ELMRole::ToolSupport:
            return "[INST] You are a Tool-Support specialist. Identify any tool calls needed to answer the "
                   "following task. "
                   "List tool name, parameters, and expected output format.\n\n"
                   "Task: " +
                   input + "\n\nTool calls: [/INST]";

        default:
            return "[INST] Respond to the following:\n\n" + input + "\n\nResponse: [/INST]";
        }
    }

    // -----------------------------------------------------------------------
    // Process
    // -----------------------------------------------------------------------
    outcome::result<std::string> RoleELM::Process( const std::string& input, const ELMContext& context )
    {
        if ( !m_loaded || !m_engine )
        {
            RoleLogger()->warn( "RoleELM not loaded — returning input unchanged" );
            m_lastConfidence = 0.0f;
            return outcome::success( input );
        }

        Task task;
        task.m_id = m_name + "-" + std::to_string( std::hash<std::string>{}( input ) );
        task.m_prompt = BuildPrompt( input, context );
        task.m_maxTokens = static_cast<uint32_t>( input.size() + 128 );
        task.m_temperature = 0.2f;

        auto res = m_engine->Infer( task );
        if ( !res.has_value() )
        {
            RoleLogger()->warn( "RoleELM inference failed — returning input unchanged" );
            m_lastConfidence = 0.0f;
            return outcome::success( input );
        }

        m_lastConfidence = 1.0f - std::min( res.value().m_perplexity / 10.0f, 1.0f );
        return outcome::success( res.value().m_output );
    }

} // namespace sgns::neoswarm::elm
