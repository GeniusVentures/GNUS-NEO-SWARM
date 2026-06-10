/**
 * @file       super_genius_client.hpp
 * @brief      Client for SuperGenius blockchain compute network dispatch via PubSub gRPC
 * @date       2026-05-28
 * @author     Subaskar S (ssivakumar@gnus.ai)
 *
 * Encapsulates all communication with the SuperGenius processing network.
 * Manages a persistent gRPC channel, publishes signed Task messages to the
 * grid channel via PubSub, and collects results from per-job result channels.
 */

#ifndef NEOSWARM_NETWORK_SG_CLIENT_SUPERGENIUSCLIENT_HPP
#define NEOSWARM_NETWORK_SG_CLIENT_SUPERGENIUSCLIENT_HPP

#include "common/error.hpp"
#include <chrono>
#include <cstdint>
#include <memory>
#include <string>
#include <vector>

namespace sgns::neoswarm::security
{
    class NodeIdentity;
}

namespace sgns::neoswarm::network
{
    /**
     * @brief Client that bridges GNUS NEO SWARM to the SuperGenius blockchain
     *        compute network via PubSub-based gRPC dispatch.
     *
     * Methodology:
     *   - Open a persistent gRPC channel with keepalive
     *   - Sign every Task with the node's secp256k1 identity
     *   - Publish to the grid channel, subscribe to per-job result channels
     *   - Timeout-bounded result collection via condition_variable
     *
     * Designed as a separate component under src/network/sg_client/ with
     * four internal sub-components: channel manager, job submitter, result
     * collector, and message authenticator.
     */
    class SuperGeniusClient
    {
        public:
        /**
         * @brief Configuration for SuperGenius network connectivity.
         */
        struct Config
        {
            std::string m_endpoint = "localhost:50051";   ///< SuperGenius node address
            std::string m_tlsCaPath;                    ///< TLS CA certificate bundle
            std::string m_tlsCertPath;                  ///< TLS client certificate
            std::chrono::seconds channel_m_timeout{ 30 }; ///< Channel creation timeout
            std::chrono::seconds result_m_timeout{ 300 }; ///< Inference result timeout (5 min)
        };

        /**
         * @brief Construct with configuration.
         * @param cfg Network and timeout settings.
         */
        explicit SuperGeniusClient( Config cfg );

        ~SuperGeniusClient();

        // Non-copyable, movable
        SuperGeniusClient( const SuperGeniusClient& ) = delete;
        SuperGeniusClient& operator=( const SuperGeniusClient& ) = delete;
        SuperGeniusClient( SuperGeniusClient&& ) noexcept;
        SuperGeniusClient& operator=( SuperGeniusClient&& ) noexcept;

        /**
         * @brief Initialize with the node's cryptographic identity.
         *
         * Must be called before Connect(). The NodeIdentity is used for
         * signing all Task messages dispatched to SuperGenius.
         *
         * @param identity The node's secp256k1 identity.
         * @return        outcome::success or IdentityError.
         */
        outcome::result<void> Initialize( const security::NodeIdentity& identity );

        /**
         * @brief Establish connection to the SuperGenius node.
         *
         * Creates a persistent gRPC channel with TLS, keepalive, and
         * health checking. For localhost endpoints without TLS certs,
         * an insecure channel is used with a WARN log.
         *
         * @return outcome::success or NetworkError.
         */
        outcome::result<void> Connect();

        /**
         * @brief Submit a GNUS schema JSON job and wait for the result.
         *
         * Signs the payload, publishes to the grid channel, subscribes to
         * the per-job result channel, and blocks until the result arrives
         * or the timeout expires.
         *
         * Blocking synchronous call — uses condition_variable internally
         * for timeout-bounded collection.
         *
         * @param gnusSchemaJson  The GNUS_Schema JSON from BuildSchemaJson().
         * @return                Raw output bytes or error.
         */
        outcome::result<std::vector<uint8_t>> SubmitJob( const std::string& gnusSchemaJson );

        /**
         * @brief Disconnect from the SuperGenius node.
         *
         * Closes the gRPC channel and resets internal state. Safe to
         * call Connect() again after Disconnect().
         */
        void Disconnect();

        /**
         * @brief Check whether the client is currently connected.
         * @return true if the gRPC channel is alive.
         */
        bool IsConnected() const noexcept;

        private:
        struct Impl;
        std::unique_ptr<Impl> m_impl;
    };

} // namespace sgns::neoswarm::network

#endif // NEOSWARM_NETWORK_SG_CLIENT_SUPERGENIUSCLIENT_HPP
