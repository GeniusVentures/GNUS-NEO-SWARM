/**
 * @file       domain_elm.cpp
 * @brief      DomainELM stub implementation — TDD RED phase
 * @date       2026-07-16
 *
 * STUB — Process() returns input unchanged with confidence=0.
 * Replaced with full implementation in the GREEN phase.
 */

#include "domain_elm.hpp"
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
    // SelectEngine
    // -----------------------------------------------------------------------
    core::InferenceEngine* DomainELM::SelectEngine() const noexcept
    {
        // STUB: always returns nullptr (GREEN phase will implement dual-mode)
        return nullptr;
    }

    // -----------------------------------------------------------------------
    // Load — STUB (returns error)
    // -----------------------------------------------------------------------
    outcome::result<void> DomainELM::Load( const std::string& /*model_path*/ )
    {
        // STUB: will be replaced in GREEN phase
        DomainLogger()->warn( "DomainELM::Load — STUB (GREEN phase will implement)" );
        return outcome::failure( Error::ModelLoadFailed );
    }

    // -----------------------------------------------------------------------
    // BuildPrompt — STUB (returns empty)
    // -----------------------------------------------------------------------
    std::string DomainELM::BuildPrompt( const std::string& /*input*/, const ELMContext& /*context*/ ) const
    {
        // STUB: will be replaced with domain-specific templates in GREEN phase
        return "";
    }

    // -----------------------------------------------------------------------
    // Process — STUB (returns input unchanged, confidence=0)
    // -----------------------------------------------------------------------
    outcome::result<std::string> DomainELM::Process( const std::string& input, const ELMContext& /*context*/ )
    {
        // STUB: fail-close — return input unchanged with zero confidence
        DomainLogger()->warn( "DomainELM::Process — STUB (GREEN phase will implement)" );
        m_lastConfidence = 0.0f;
        return outcome::success( input );
    }

} // namespace sgns::neoswarm::elm
