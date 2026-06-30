/**
 * @file       sg_job_submitter.hpp
 * @brief      Publishes signed Task messages via GeniusSDK dispatch
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
    class SGMessageAuthenticator;

    /**
     * @brief Signs and publishes Task messages via GeniusSDK.
     *
     * Converts GNUS schema JSON into signed Task messages, dispatches
     * through GeniusSDKProcess(), and returns a taskId for result collection.
     */
    class SGJobSubmitter
    {
        public:
        SGJobSubmitter( SGMessageAuthenticator& authenticator );
        ~SGJobSubmitter();

        /**
         * @brief Sign and publish a GNUS schema JSON job.
         * @param gnusSchemaJson  The GNUS_Schema JSON from BuildSchemaJson().
         * @return                The generated taskId for result collection.
         */
        outcome::result<std::string> PublishJob( const std::string& gnusSchemaJson );

        private:
        struct Impl;
        std::unique_ptr<Impl> m_impl;
    };

} // namespace sgns::neoswarm::network

#endif // NEOSWARM_NETWORK_SG_CLIENT_SGJOBSUBMITTER_HPP
