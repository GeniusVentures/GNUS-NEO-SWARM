/**
 * @file       super_genius_client.hpp
 * @brief      Client for SuperGenius blockchain compute network dispatch via GeniusSDK
 * @date       2026-05-28
 *
 * GeniusSDK runs in-process via direct linking — every swarm node has the SDK
 * compiled in. No remote endpoint, no gRPC channel management. Initialize() starts
 * the SDK node; SubmitJob() dispatches through GeniusSDKProcess(); Disconnect()
 * calls GeniusSDKShutdown().
 *
 * SDK identity is managed internally — GeniusSDKInit() generates its own keypair.
 * NEO-SWARM does NOT derive SDK keys from NodeIdentity (they serve different purposes:
 * NodeIdentity = P2P swarm identity, SDK identity = blockchain node identity).
 */

#ifndef NEOSWARM_NETWORK_SG_CLIENT_SUPERGENIUSCLIENT_HPP
#define NEOSWARM_NETWORK_SG_CLIENT_SUPERGENIUSCLIENT_HPP

#include "common/error.hpp"
#include <chrono>
#include <cstdint>
#include <memory>
#include <string>
#include <vector>

namespace sgns::neoswarm::network
{
    class SGClient
    {
        public:
        struct Config
        {
            std::string m_sdkBasePath = "./sdk";           ///< GeniusSDK data directory
            uint16_t m_basePort = 40001;                   ///< SDK network port
            bool m_autoDht = true;                         ///< Enable DHT
            bool m_enableProcessing = true;                ///< Enable job processing
            std::chrono::seconds m_resultTimeout{ 300 };   ///< Inference result timeout (5 min)
        };

        explicit SGClient( Config cfg );
        ~SGClient();

        SGClient( const SGClient& ) = delete;
        SGClient& operator=( const SGClient& ) = delete;
        SGClient( SGClient&& ) noexcept;
        SGClient& operator=( SGClient&& ) noexcept;

        /**
         * @brief Initialize the GeniusSDK node in-process.
         *
         * Calls GeniusSDKInit() — the SDK generates its own keypair internally
         * for blockchain identity. NEO-SWARM's NodeIdentity is separate (swarm P2P).
         * After this, SubmitJob() can dispatch via GeniusSDKProcess().
         *
         * @return outcome::success or error.
         */
        outcome::result<void> Initialize();

        /**
         * @brief Submit a GNUS schema JSON job and wait for the result.
         *
         * Passes the raw GNUS schema JSON directly to GeniusSDKProcess().
         * The SDK handles auth internally via its own identity.
         *
         * @param gnusSchemaJson  The GNUS_Schema JSON from BuildSchemaJson().
         * @return                Raw output bytes or error.
         */
        outcome::result<std::vector<uint8_t>> SubmitJob( const std::string& gnusSchemaJson );

        /**
         * @brief Shut down the GeniusSDK node and release resources.
         *
         * Calls GeniusSDKShutdown() to tear down the in-process node.
         */
        void Disconnect();

        /**
         * @brief Check whether the SDK node is ready.
         * @return true if GeniusSDKGetNodeState() == GENIUS_NODE_READY.
         */
        bool IsConnected() const noexcept;

        private:
        struct Impl;
        std::unique_ptr<Impl> m_impl;
    };

} // namespace sgns::neoswarm::network

#endif // NEOSWARM_NETWORK_SG_CLIENT_SUPERGENIUSCLIENT_HPP