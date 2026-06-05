/**
 * @file       RuleBasedRouter.cpp
 * @brief      Rule-based router implementation
 * @date       2026-05-06
 * @author     Subaskar S (ssivakumar@gnus.ai)
 */

#include "RuleBasedRouter.hpp"
#include "common/Logging.hpp"

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
        : cfg_( {} )
    {
    }
    RuleBasedRouter::RuleBasedRouter( Config cfg )
        : cfg_( std::move( cfg ) )
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
        if ( cfg_.enable_swarm_mode_ && features.complexity_ > cfg_.complexity_swarm_threshold_ )
        {
            return ExecutionMode::Swarm;
        }

        // Specialist mode when a specialist is needed
        if ( features.numeric_density_ > cfg_.numeric_density_threshold_ || features.has_math_keywords_ ||
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
        PromptFeatures features = analyzer_.Analyze( task.prompt_ );

        RouteDecision decision;
        decision.mode_ = SelectMode( features, task.mode_ );

        if ( features.numeric_density_ > cfg_.numeric_density_threshold_ || features.has_math_keywords_ )
        {
            decision.target_ = RouteTarget::CorePlusMath;
            decision.confidence_ = 0.85f + features.numeric_density_ * 0.15f;
            decision.reasoning_ = "High numeric density or math keywords detected";
        }
        else if ( features.has_grammar_request_ )
        {
            decision.target_ = RouteTarget::CorePlusGrammar;
            decision.confidence_ = 0.90f;
            decision.reasoning_ = "Grammar/writing correction request detected";
        }
        else if ( features.has_code_syntax_ )
        {
            decision.target_ = RouteTarget::CoreOnly;
            decision.confidence_ = 0.75f;
            decision.reasoning_ = "Code syntax detected — routing to Core (Code specialist: future)";
        }
        else
        {
            decision.target_ = RouteTarget::CoreOnly;
            decision.confidence_ = 1.0f;
            decision.reasoning_ = "General prompt — Core LLM only";
        }

        RouterLogger()->debug( "Route: target={} mode={} confidence={:.2f} reason='{}'",
                               static_cast<int>( decision.target_ ), static_cast<int>( decision.mode_ ),
                               decision.confidence_, decision.reasoning_ );

        return outcome::success( std::move( decision ) );
    }

} // namespace sgns::neoswarm::router
