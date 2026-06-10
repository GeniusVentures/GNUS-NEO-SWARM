/**
 * @file       reputation_scoring.hpp
 * @brief      Reputation update formulas (PTDS §7.2)
 * @date       2026-05-06
 * @author     Subaskar S (ssivakumar@gnus.ai)
 */

#ifndef NEOSWARM_REPUTATION_REPUTATIONSCORING_HPP
#define NEOSWARM_REPUTATION_REPUTATIONSCORING_HPP

#include "common/types.hpp"
#include "node_reputation.hpp"
#include <optional>

namespace sgns::neoswarm::reputation
{
    /**
     * @brief Implements the PTDS §7.2 reputation update formulas.
     *
     * Δ accuracy  = α × (was_correct − 0.5)
     * Δ consensus = β × agreed_with_winning_answer
     * Δ latency   = −γ × (my_time / median_time)
     * Δ consistency = δ × (1 / perplexity)
     */
    class ReputationScoring
    {
        public:
        struct Config
        {
            double alpha_ = 0.10;   ///< accuracy weight
            double beta_ = 0.05;    ///< consensus agreement weight
            double gamma_ = 0.02;   ///< latency penalty
            double delta_ = 0.03;   ///< consistency bonus
            double epsilon_ = 1e-6; ///< perplexity smoothing
            double baseline_accuracy_ = 0.5;
        };

        ReputationScoring();
        explicit ReputationScoring( Config cfg );

        /**
         * @brief Compute an updated reputation after a completed task.
         * @param old               Current reputation record.
         * @param response          Inference response from this node.
         * @param median_latency_ms Median latency across all responding nodes (ms).
         * @param ground_truth      Correct answer if available.
         * @param m_consensusoutput  The winning consensus output string.
         * @return                  Updated NodeReputation.
         */
        NodeReputation Update( const NodeReputation& old,
                               const InferenceResponse& response,
                               double median_latency_ms,
                               std::optional<std::string> ground_truth,
                               const std::string& m_consensusoutput ) const;

        /**
         * @brief Compute the accuracy delta component.
         * @param has_ground_truth  Whether a ground truth answer is available.
         * @param accuracy          Accuracy score in [0, 1].
         * @return                  Accuracy delta.
         */
        double DeltaAccuracy( bool has_ground_truth, double accuracy ) const;

        /**
         * @brief Compute the latency delta component.
         * @param latency_ms         This node's latency in ms.
         * @param median_latency_ms  Median latency across all nodes.
         * @return                   Latency delta (negative = penalty).
         */
        double DeltaLatency( double latency_ms, double median_latency_ms ) const;

        /**
         * @brief Compute the consistency delta component from perplexity.
         * @param perplexity  Model perplexity (lower = more confident).
         * @return            Consistency delta.
         */
        double DeltaConsistency( float perplexity ) const;

        private:
        Config m_cfg;
    };

} // namespace sgns::neoswarm::reputation

#endif // NEOSWARM_REPUTATION_REPUTATIONSCORING_HPP
