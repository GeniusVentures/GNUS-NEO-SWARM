/**
 * @file       rule_based_router.cpp
 * @brief      Rule-based router implementation
 * @date       2026-05-06
 */

#include "rule_based_router.hpp"
#include "common/logging.hpp"

namespace sgns::neoswarm::router
{
    namespace
    {
        auto RouterLogger()
        {
            return neoswarm::CreateLogger( "Router" );
        }
    } // namespace

    RuleBasedRouter::RuleBasedRouter()
        : m_cfg( {} )
    {
    }
    RuleBasedRouter::RuleBasedRouter( Config cfg )
        : m_cfg( std::move( cfg ) )
    {
    }

    // -----------------------------------------------------------------------
    // SelectMode
    // -----------------------------------------------------------------------
    ExecutionMode RuleBasedRouter::SelectMode( const PromptFeatures& features, ExecutionMode requested ) const
    {
        // Honour explicit Swarm or Specialist request
        if ( requested == ExecutionMode::Swarm )
        {
            return ExecutionMode::Swarm;
        }
        if ( requested == ExecutionMode::Specialist )
        {
            return ExecutionMode::Specialist;
        }

        // Auto-upgrade to Swarm for complex prompts
        if ( m_cfg.enable_swarm_m_mode && features.complexity_ > m_cfg.complexity_swarm_threshold_ )
        {
            return ExecutionMode::Swarm;
        }

        // Specialist mode when a specialist is needed
        if ( features.numeric_density_ > m_cfg.numeric_density_threshold_ || features.has_math_keywords_ ||
             features.has_grammar_request_ )
        {
            return ExecutionMode::Specialist;
        }

        return ExecutionMode::SingleNode;
    }

    // -----------------------------------------------------------------------
    // Route
    // -----------------------------------------------------------------------
    outcome::result<RouteDecision> RuleBasedRouter::Route( const Task& task )
    {
        PromptFeatures features = m_analyzer.Analyze( task.m_prompt );

        RouteDecision decision;
        decision.m_mode = SelectMode( features, task.m_mode );

        if ( features.numeric_density_ > m_cfg.numeric_density_threshold_ || features.has_math_keywords_ )
        {
            decision.m_target = RouteTarget::CorePlusMath;
            decision.confidence_ = 0.85f + features.numeric_density_ * 0.15f;
            decision.m_reasoning = "High numeric density or math keywords detected";
        }
        else if ( features.has_grammar_request_ )
        {
            decision.m_target = RouteTarget::CorePlusGrammar;
            decision.confidence_ = 0.90f;
            decision.m_reasoning = "Grammar/writing correction request detected";
        }
        else if ( features.has_code_syntax_ )
        {
            decision.m_target = RouteTarget::CoreOnly;
            decision.confidence_ = 0.75f;
            decision.m_reasoning = "Code syntax detected — routing to Core (Code specialist: future)";
        }
        else
        {
            decision.m_target = RouteTarget::CoreOnly;
            decision.confidence_ = 1.0f;
            decision.m_reasoning = "General prompt — Core LLM only";
        }

        RouterLogger()->debug( "Route: target={} mode={} confidence={:.2f} reason='{}'",
                               static_cast<int>( decision.m_target ), static_cast<int>( decision.m_mode ),
                               decision.confidence_, decision.m_reasoning );

        return outcome::success( std::move( decision ) );
    }

} // namespace sgns::neoswarm::router
