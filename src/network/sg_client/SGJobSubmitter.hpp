/**
 * @file       SGJobSubmitter.hpp
 * @brief      Publishes signed Task messages to the SuperGenius grid channel via PubSub
 * @date       2026-05-28
 * @author     Subaskar S (ssivakumar@gnus.ai)
 */

#ifndef NEOSWARM_NETWORK_SG_CLIENT_SGJOBSUBMITTER_HPP_
#define NEOSWARM_NETWORK_SG_CLIENT_SGJOBSUBMITTER_HPP_

#include "common/Error.hpp"
#include <memory>
#include <string>
#include <vector>

namespace grpc
{
    class Channel;
}

namespace sgns::neoswarm::network
{
    class SGMessageAuthenticator;

    /**
     * @brief Signs and publishes Task messages to the SuperGenius grid channel.
     *
     * Converts GNUS schema JSON into signed PubSub Task messages, publishes them
     * to the processing grid channel, and returns a taskId for result collection.
     */
    class SGJobSubmitter
    {
        public:
        SGJobSubmitter( std::shared_ptr<grpc::Channel> channel, SGMessageAuthenticator& authenticator );
        ~SGJobSubmitter();

        /**
         * @brief Sign and publish a GNUS schema JSON job to the grid channel.
         * @param gnusSchemaJson  The GNUS_Schema JSON from BuildSchemaJson().
         * @return                The generated taskId for result collection.
         */
        outcome::result<std::string> PublishJob( const std::string& gnusSchemaJson );

        private:
        struct Impl;
        std::unique_ptr<Impl> impl_;
    };

} // namespace sgns::neoswarm::network

#endif // NEOSWARM_NETWORK_SG_CLIENT_SGJOBSUBMITTER_HPP_
