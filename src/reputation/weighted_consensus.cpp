/**
 * @file       weighted_consensus.cpp
 * @brief      Weighted consensus implementation
 * @date       2026-05-06
 * @author     Subaskar S (ssivakumar@gnus.ai)
 */

#include "weighted_consensus.hpp"
#include "common/logging.hpp"

#include <algorithm>
#include <unordered_map>

namespace sgns::neoswarm::reputation
{
    namespace
    {
        auto ConsensusLogger()
        {
            return neoswarm::CreateLogger( "WeightedConsensus" );
        }
    } // namespace

    WeightedConsensus::WeightedConsensus()
        : m_cfg( {} )
    {
    }
    WeightedConsensus::WeightedConsensus( Config cfg )
        : m_cfg( std::move( cfg ) )
    {
    }

    // -----------------------------------------------------------------------
    // ComputeWeights
    // -----------------------------------------------------------------------
    std::vector<double> WeightedConsensus::ComputeWeights( const std::vector<NodeOutput>& outputs ) const
    {
        std::vector<double> weights;
        weights.reserve( outputs.size() );
        for ( const auto& o : outputs )
        {
            double w = o.reputation_ / ( static_cast<double>( o.perplexity_ ) + m_cfg.epsilon_ );
            weights.push_back( std::max( w, 0.0 ) );
        }
        return weights;
    }

    // -----------------------------------------------------------------------
    // WeightedVoting
    // -----------------------------------------------------------------------
    NodeOutput WeightedConsensus::WeightedVoting( const std::vector<NodeOutput>& outputs,
                                                  const std::vector<double>& weights ) const
    {
        std::unordered_map<std::string, double> vote_map;
        for ( size_t i = 0; i < outputs.size(); ++i )
        {
            if ( weights[i] >= m_cfg.min_weight_ )
            {
                vote_map[outputs[i].output_] += weights[i];
            }
        }

        if ( vote_map.empty() )
        {
            return outputs.front();
        }

        auto winner = std::max_element( vote_map.begin(), vote_map.end(),
                                        []( const auto& a, const auto& b ) { return a.second < b.second; } );

        for ( size_t i = 0; i < outputs.size(); ++i )
        {
            if ( outputs[i].output_ == winner->first )
            {
                ConsensusLogger()->debug( "Consensus winner: node={} weight={:.3f}", outputs[i].node_id_,
                                          winner->second );
                return outputs[i];
            }
        }
        return outputs.front();
    }

    // -----------------------------------------------------------------------
    // BestWeightedScore
    // -----------------------------------------------------------------------
    NodeOutput WeightedConsensus::BestWeightedScore( const std::vector<NodeOutput>& outputs,
                                                     const std::vector<double>& weights ) const
    {
        size_t best_idx = 0;
        double best_w = -1.0;
        for ( size_t i = 0; i < outputs.size(); ++i )
        {
            if ( weights[i] > best_w )
            {
                best_w = weights[i];
                best_idx = i;
            }
        }
        ConsensusLogger()->debug( "Best-score winner: node={} weight={:.3f}", outputs[best_idx].node_id_, best_w );
        return outputs[best_idx];
    }

    // -----------------------------------------------------------------------
    // SelectWinner
    // -----------------------------------------------------------------------
    NodeOutput WeightedConsensus::SelectWinner( const std::vector<NodeOutput>& outputs ) const
    {
        if ( outputs.empty() )
        {
            return {};
        }
        if ( outputs.size() == 1 )
        {
            return outputs.front();
        }

        auto weights = ComputeWeights( outputs );

        switch ( m_cfg.strategy_ )
        {
            case Strategy::WeightedVoting:
                return WeightedVoting( outputs, weights );
            case Strategy::BestWeightedScore:
                return BestWeightedScore( outputs, weights );
        }
        return outputs.front();
    }

} // namespace sgns::neoswarm::reputation
