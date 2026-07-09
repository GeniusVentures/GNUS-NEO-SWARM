/**
 * @file       sg_job_submitter.hpp
 * @brief      Dispatches GNUS schema JSON directly to GeniusSDKProcess
 * @date       2026-05-28
 */

#ifndef NEOSWARM_NETWORK_SG_CLIENT_SGJOBSUBMITTER_HPP
#define NEOSWARM_NETWORK_SG_CLIENT_SGJOBSUBMITTER_HPP

#include "common/error.hpp"
#include <memory>
#include <string>
#include <vector>

namespace sgns::neoswarm::network
{
    /**
     * @brief Dispatches GNUS schema JSON to GeniusSDK in-process.
     *
     * Passes the raw GNUS schema JSON directly to GeniusSDKProcess() —
     * the SDK handles auth internally via the eth key from InitWithKey().
     * No custom wrapper, no external signing layer.
     */
    class SGJobSubmitter
    {
        public:
        SGJobSubmitter() = default;
        ~SGJobSubmitter();

        /**
         * @brief Dispatch a GNUS schema JSON job via GeniusSDKProcess.
         * @param gnusSchemaJson  The GNUS_Schema JSON from BuildSchemaJson().
         * @return                The generated taskId for result tracking.
         */
        outcome::result<std::string> PublishJob( const std::string& gnusSchemaJson );

        private:
    };

} // namespace sgns::neoswarm::network

#endif // NEOSWARM_NETWORK_SG_CLIENT_SGJOBSUBMITTER_HPP
