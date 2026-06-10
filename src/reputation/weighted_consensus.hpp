/**
 * @file       weighted_consensus.hpp
 * @brief      Weighted consensus selection (PTDS §7.3)
 * @date       2026-05-06
 * @author     Subaskar S (ssivakumar@gnus.ai)
 */

#ifndef NEOSWARM_REPUTATION_WEIGHTEDCONSENSUS_HPP
#define NEOSWARM_REPUTATION_WEIGHTEDCONSENSUS_HPP

#include "common/types.hpp"
#include <vector>

namespace sgns::neoswarm::reputation
{
    /**
     * @brief Selects the winning output from a set of node responses.
     *
     * weight_i = reputation_i / (perplexity_i + ε)
     *
     * Strategy A (WeightedVoting):    select O_k maximising Σ weight_i × (O_i == O_k)
     * Strategy B (BestWeightedScore): select O_i maximising weight_i
     */
    class WeightedConsensus
    {
        public:
        enum class Strategy : uint8_t
        {
            WeightedVoting = 0,
            BestWeightedScore = 1
        };

        struct Config
        {
            Strategy strategy_ = Strategy::WeightedVoting;
            double epsilon_ = 1e-6;
            double min_weight_ = 0.0; ///< ignore nodes below this weight
        };

        WeightedConsensus();
        explicit WeightedConsensus( Config cfg );

        /**
         * @brief Select the winning output from a set of node outputs.
         * @param outputs  Responses from all participating nodes.
         * @return         The winning NodeOutput (or the first if empty).
         */
        NodeOutput SelectWinner( const std::vector<NodeOutput>& outputs ) const;

        private:
        Config m_cfg;

        /**
         * @brief Compute per-node weights from reputation and perplexity.
         * @param outputs  Node output records.
         * @return         Weight vector aligned with outputs.
         */
        std::vector<double> ComputeWeights( const std::vector<NodeOutput>& outputs ) const;

        /**
         * @brief Select winner by aggregating weights per unique output string.
         */
        NodeOutput WeightedVoting( const std::vector<NodeOutput>& outputs, const std::vector<double>& weights ) const;

        /**
         * @brief Select the single node with the highest individual weight.
         */
        NodeOutput BestWeightedScore( const std::vector<NodeOutput>& outputs,
                                      const std::vector<double>& weights ) const;
    };

} // namespace sgns::neoswarm::reputation

#endif // NEOSWARM_REPUTATION_WEIGHTEDCONSENSUS_HPP
