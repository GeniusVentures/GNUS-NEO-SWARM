/**
 * @file       elm_chain_builder.cpp
 * @brief      ELMChainBuilder implementation — 6 heuristic triggers → ExecutionChain
 * @date       2026-07-17
 */

#include "elm_chain_builder.hpp"
#include "common/logging.hpp"

#include <optional>
#include <utility>

namespace sgns::neoswarm::elm
{
    namespace
    {
        auto BuilderLogger()
        {
            return neoswarm::CreateLogger( "ELMChainBuilder" );
        }
    } // namespace

    ELMChainBuilder::ELMChainBuilder()
        : m_cfg( {} )
    {
    }

    ELMChainBuilder::ELMChainBuilder( Config cfg )
        : m_cfg( std::move( cfg ) )
    {
    }

    // -----------------------------------------------------------------------
    // Build — 6-trigger decision tree (doc 03 §6.2)
    // -----------------------------------------------------------------------
    outcome::result<ExecutionChain> ELMChainBuilder::Build( const RouteDecision& decision,
                                                            const PromptFeatures& features )
    {
        ExecutionChain chain;

        // Trigger 1: Numeric density → Math + Verifier
        if ( features.numeric_density_ > m_cfg.numeric_density_threshold_ )
        {
            chain.m_steps.push_back( { ELMRole::Math, std::string{ "math" } } );
            chain.m_steps.push_back( { ELMRole::Verifier, std::nullopt } );
            chain.m_reasoning = "High numeric density — routing to Math + Verifier";
        }
        // Trigger 2: Code syntax → Planner + Code
        else if ( features.has_code_syntax_ )
        {
            chain.m_steps.push_back( { ELMRole::Planner, std::nullopt } );
            chain.m_steps.push_back( { ELMRole::Code, std::string{ "code" } } );
            chain.m_reasoning = "Code syntax detected — Planner → Code domain";
        }
        // Trigger 3: Grounding-sensitive → Grounding + Draft + Verify
        else if ( features.has_grounding_request_ )
        {
            chain.m_steps.push_back( { ELMRole::Grounding, std::nullopt } );
            chain.m_steps.push_back( { ELMRole::PrimaryDraft, std::nullopt } );
            chain.m_steps.push_back( { ELMRole::Verifier, std::nullopt } );
            chain.m_reasoning = "Grounding-sensitive — Grounding → Draft → Verify";
        }
        // Trigger 4: Formatting-sensitive → Draft + Refiner
        else if ( features.has_formatting_request_ )
        {
            chain.m_steps.push_back( { ELMRole::PrimaryDraft, std::nullopt } );
            chain.m_steps.push_back( { ELMRole::Refiner, std::nullopt } );
            chain.m_reasoning = "Formatting-sensitive — Draft → Refiner";
        }
        // Trigger 5: Low complexity → single-step draft
        else if ( features.complexity_ < m_cfg.complexity_low_threshold_ )
        {
            chain.m_steps.push_back( { ELMRole::PrimaryDraft, std::nullopt } );
            chain.m_reasoning = "Low complexity — single-step PrimaryDraft";
        }
        // Trigger 6: High complexity/uncertainty → full chain
        else if ( features.complexity_ >= m_cfg.complexity_high_threshold_ )
        {
            chain.m_steps.push_back( { ELMRole::Planner, std::nullopt } );
            chain.m_steps.push_back( { ELMRole::PrimaryDraft, std::nullopt } );
            chain.m_steps.push_back( { ELMRole::Verifier, std::nullopt } );
            chain.m_steps.push_back( { ELMRole::Refiner, std::nullopt } );
            chain.m_reasoning = "High complexity — Planner → Draft → Verify → Refine";
        }
        // Default: single-step draft
        else
        {
            chain.m_steps.push_back( { ELMRole::PrimaryDraft, std::nullopt } );
            chain.m_reasoning = "Default — single-step PrimaryDraft";
        }

        // Carry forward the router's confidence
        chain.m_chainConfidence = decision.confidence_;

        BuilderLogger()->debug( "Built chain: {} step(s), reason='{}', confidence={:.2f}",
                                chain.m_steps.size(), chain.m_reasoning, chain.m_chainConfidence );
        return outcome::success( std::move( chain ) );
    }

} // namespace sgns::neoswarm::elm
