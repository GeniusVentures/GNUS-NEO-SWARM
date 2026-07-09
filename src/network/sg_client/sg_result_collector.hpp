/**
 * @file       sg_result_collector.hpp
 * @brief      Collects inference results via GeniusSDK processing status polling
 * @date       2026-05-28
 */

#ifndef NEOSWARM_NETWORK_SG_CLIENT_SGRESULTCOLLECTOR_HPP
#define NEOSWARM_NETWORK_SG_CLIENT_SGRESULTCOLLECTOR_HPP

#include "common/error.hpp"
#include <chrono>
#include <cstdint>
#include <future>
#include <memory>
#include <string>
#include <vector>

namespace sgns::neoswarm::network
{
    struct SGResultCollectorConfig
    {
        std::chrono::seconds m_resultTimeout{ 120 };
    };

    /**
     * @brief Collects inference results via GeniusSDK processing status polling.
     *
     * GeniusSDKGetProcessingStatus() reports global node status (not per-task),
     * so the completion signal is: was PROCESSING → now IDLE.
     *
     * TODO: Switch to per-task status API when SDK supports it.
     */
    class SGResultCollector
    {
        public:
        explicit SGResultCollector( SGResultCollectorConfig cfg = {} );
        ~SGResultCollector();

        /**
         * @brief Poll SDK synchronously until processing completes or timeout.
         *
         * Blocks the calling thread. For non-blocking use, call PollForResultAsync().
         *
         * @return Raw output bytes on completion, or BroadcastTimeout on expiry.
         */
        outcome::result<std::vector<uint8_t>> PollForResult( std::chrono::seconds timeout );

        /**
         * @brief Poll using configured default timeout.
         */
        outcome::result<std::vector<uint8_t>> PollForResult();

        /**
         * @brief Non-blocking poll — returns a future that callers can wait on.
         *
         * Launches PollForResult() on a detached thread via std::async(std::launch::async).
         * Does not block the calling thread.
         */
        std::future<outcome::result<std::vector<uint8_t>>> PollForResultAsync( std::chrono::seconds timeout );

        /**
         * @brief Non-blocking poll with default timeout.
         */
        std::future<outcome::result<std::vector<uint8_t>>> PollForResultAsync();

        private:
        struct Impl;
        std::unique_ptr<Impl> m_impl;
    };

} // namespace sgns::neoswarm::network

#endif // NEOSWARM_NETWORK_SG_CLIENT_SGRESULTCOLLECTOR_HPP