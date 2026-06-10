/**
 * @file       reputation_scoring.cpp
 * @brief      Reputation update formula implementation
 * @date       2026-05-06
 * @author     Subaskar S (ssivakumar@gnus.ai)
 */

#include "reputation_scoring.hpp"
#include "common/logging.hpp"

#include <chrono>
#include <cmath>

namespace sgns::neoswarm::reputation
{
    namespace
    {
        auto ScoringLogger()
        {
            return neoswarm::CreateLogger( "ReputationScoring" );
        }
    } // namespace

    ReputationScoring::ReputationScoring()
        : m_cfg( {} )
    {
    }
    ReputationScoring::ReputationScoring( Config cfg )
        : m_cfg( std::move( cfg ) )
    {
    }

    // -----------------------------------------------------------------------
    // DeltaAccuracy
    // -----------------------------------------------------------------------
    double ReputationScoring::DeltaAccuracy( bool has_ground_truth, double accuracy ) const
    {
        if ( has_ground_truth )
        {
            return m_cfg.alpha_ * ( accuracy - m_cfg.baseline_accuracy_ );
        }
        // Agreement with weighted consensus
        return m_cfg.beta_ * accuracy;
    }

    // -----------------------------------------------------------------------
    // DeltaLatency
    // -----------------------------------------------------------------------
    double ReputationScoring::DeltaLatency( double latency_ms, double median_latency_ms ) const
    {
        if ( median_latency_ms <= 0.0 )
        {
            return 0.0;
        }
        return -m_cfg.gamma_ * ( latency_ms / median_latency_ms );
    }

    // -----------------------------------------------------------------------
    // DeltaConsistency
    // -----------------------------------------------------------------------
    double ReputationScoring::DeltaConsistency( float perplexity ) const
    {
        double inv = 1.0 / ( static_cast<double>( perplexity ) + m_cfg.epsilon_ );
        double normalized = std::min( inv, 1.0 );
        return m_cfg.delta_ * normalized;
    }

    // -----------------------------------------------------------------------
    // Update
    // -----------------------------------------------------------------------
    NodeReputation ReputationScoring::Update( const NodeReputation& old,
                                              const InferenceResponse& response,
                                              double median_latency_ms,
                                              std::optional<std::string> ground_truth,
                                              const std::string& m_consensusoutput ) const
    {
        NodeReputation updated = old;

        bool has_gt = ground_truth.has_value();
        double accuracy = 0.0;
        if ( has_gt )
        {
            accuracy = ( response.output_ == ground_truth.value() ) ? 1.0 : 0.0;
        }
        else
        {
            accuracy = ( response.output_ == m_consensusoutput ) ? 1.0 : 0.0;
        }

        double d_acc = DeltaAccuracy( has_gt, accuracy );
        double d_lat = DeltaLatency( response.latency_ms_, median_latency_ms );
        double d_cons = DeltaConsistency( response.perplexity_ );
        double delta = d_acc + d_lat + d_cons;

        updated.m_globalScore = ClampScore( old.m_globalScore + delta );
        updated.m_latencyScore = ClampScore( old.m_latencyScore + d_lat );
        updated.m_consistencyScore = ClampScore( old.m_consistencyScore + d_cons );
        updated.m_taskCount = old.m_taskCount + 1;
        updated.m_lastUpdatedMs = static_cast<uint64_t>(
            std::chrono::duration_cast<std::chrono::milliseconds>( std::chrono::system_clock::now().time_since_epoch() )
                .count() );

        ScoringLogger()->debug( "Reputation update for {}: {:.3f} → {:.3f} (Δ={:.4f})", old.m_identityKey,
                                old.m_globalScore, updated.m_globalScore, delta );

        return updated;
    }

} // namespace sgns::neoswarm::reputation
