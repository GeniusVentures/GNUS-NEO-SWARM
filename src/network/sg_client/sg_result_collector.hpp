/**
 * @file       sg_result_collector.hpp
 * @brief      Collects inference results via GeniusSDK polling
 * @date       2026-05-28
 */

#ifndef NEOSWARM_NETWORK_SG_CLIENT_SGRESULTCOLLECTOR_HPP
#define NEOSWARM_NETWORK_SG_CLIENT_SGRESULTCOLLECTOR_HPP

#include "common/error.hpp"
#include <chrono>
#include <cstdint>
#include <memory>
#include <string>
#include <vector>

namespace sgns::neoswarm::network
{
    class SGMessageAuthenticator;

    struct SGResultCollectorConfig
    {
        std::chrono::seconds result_m_timeout{ 120 };
    };

    /**
     * @brief Collects inference results via GeniusSDK processing status polling.
     */
    class SGResultCollector
    {
        public:
        SGResultCollector( SGMessageAuthenticator& authenticator, SGResultCollectorConfig cfg = {} );
        ~SGResultCollector();

        /**
         * @brief Block until a result arrives or timeout expires.
         * @param taskId  The task ID to collect results for.
         * @param timeout Maximum time to wait.
         * @return        Raw output bytes or timeout/network error.
         */
        outcome::result<std::vector<uint8_t>> WaitForResult( const std::string& taskId, std::chrono::seconds timeout );

        /**
         * @brief Wait for result using the configured default timeout.
         * @param taskId  The task ID to collect results for.
         * @return        Raw output bytes or error.
         */
        outcome::result<std::vector<uint8_t>> WaitForResult( const std::string& taskId );

        private:
        struct Impl;
        std::unique_ptr<Impl> m_impl;
    };

} // namespace sgns::neoswarm::network

#endif // NEOSWARM_NETWORK_SG_CLIENT_SGRESULTCOLLECTOR_HPP
