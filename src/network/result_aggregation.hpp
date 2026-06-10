/**
 * @file       result_aggregation.hpp
 * @brief      Timeout-bounded collection of swarm node responses (PTDS §4.2)
 * @date       2026-05-06
 * @author     Subaskar S (ssivakumar@gnus.ai)
 */

#ifndef NEOSWARM_NETWORK_RESULTAGGREGATION_HPP
#define NEOSWARM_NETWORK_RESULTAGGREGATION_HPP

#include "common/error.hpp"
#include "common/types.hpp"
#include <chrono>
#include <condition_variable>
#include <mutex>
#include <vector>

namespace sgns::neoswarm::network
{
    /**
     * @brief Collects NodeOutput responses from swarm peers with a timeout.
     *
     * Returns as soon as min_responses_ are received or the timeout expires.
     */
    class ResultAggregation
    {
        public:
        struct Config
        {
            std::chrono::milliseconds timeout_{ 5000 }; ///< max wait for responses
            size_t min_responses_ = 1;                  ///< minimum before returning
            size_t max_responses_ = 10;                 ///< stop collecting after this many
        };

        ResultAggregation();
        explicit ResultAggregation( Config cfg );

        /**
         * @brief Submit a response from a node (thread-safe).
         * @param output  Node output to add to the collection.
         */
        void Submit( const NodeOutput& output );

        /**
         * @brief Wait for responses and return collected results.
         *
         * Blocks until min_responses_ received or timeout expires.
         * @return  Vector of collected NodeOutputs or BroadcastTimeout.
         */
        outcome::result<std::vector<NodeOutput>> Collect();

        /// Reset for a new collection round.
        void Reset();

        /// @return Number of responses received so far.
        size_t ResponseCount() const;

        private:
        Config cfg_;
        std::vector<NodeOutput> results_;
        mutable std::mutex mutex_;
        std::condition_variable cv_;
        bool done_ = false;
    };

} // namespace sgns::neoswarm::network

#endif // NEOSWARM_NETWORK_RESULTAGGREGATION_HPP
