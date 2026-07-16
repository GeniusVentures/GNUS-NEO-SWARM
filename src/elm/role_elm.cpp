/**
 * @file       role_elm.cpp
 * @brief      RoleELM stub implementation — TDD RED phase
 * @date       2026-07-16
 *
 * STUB — Process() returns input unchanged with confidence=0.
 * Replaced with full implementation in the GREEN phase.
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
    // Load — STUB (returns error)
    // -----------------------------------------------------------------------
    outcome::result<void> RoleELM::Load( const std::string& /*model_path*/ )
    {
        // STUB: will be replaced in GREEN phase
        RoleLogger()->warn( "RoleELM::Load — STUB (GREEN phase will implement)" );
        return outcome::failure( Error::ModelLoadFailed );
    }

    // -----------------------------------------------------------------------
    // BuildPrompt — STUB (returns empty)
    // -----------------------------------------------------------------------
    std::string RoleELM::BuildPrompt( const std::string& input, const ELMContext& /*context*/ ) const
    {
        // STUB: will be replaced with role-specific templates in GREEN phase
        return "";
    }

    // -----------------------------------------------------------------------
    // Process — STUB (returns input unchanged, confidence=0)
    // -----------------------------------------------------------------------
    outcome::result<std::string> RoleELM::Process( const std::string& input, const ELMContext& /*context*/ )
    {
        // STUB: fail-close — return input unchanged with zero confidence
        RoleLogger()->warn( "RoleELM::Process — STUB (GREEN phase will implement)" );
        m_lastConfidence = 0.0f;
        return outcome::success( input );
    }

} // namespace sgns::neoswarm::elm
