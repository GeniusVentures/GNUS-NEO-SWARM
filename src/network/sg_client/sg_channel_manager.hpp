/**
 * @file       sg_channel_manager.hpp
 * @brief      Manages gRPC channel lifecycle — create, keepalive, reconnect, health check
 * @date       2026-05-28
 * @author     Subaskar S (ssivakumar@gnus.ai)
 */

#ifndef NEOSWARM_NETWORK_SG_CLIENT_SGCHANNELMANAGER_HPP
#define NEOSWARM_NETWORK_SG_CLIENT_SGCHANNELMANAGER_HPP

#include "common/error.hpp"
#include <chrono>
#include <memory>
#include <string>

namespace grpc
{
    class Channel;
}

namespace sgns::neoswarm::network
{
    /**
     * @brief Manages a persistent gRPC channel to a SuperGenius node.
     *
     * Handles channel creation with optional TLS, keepalive configuration,
     * health checking, and exponential backoff reconnection.
     */
    class SGChannelManager
    {
        public:
        struct Config
        {
            std::string m_endpoint = "localhost:50051";
            std::string m_tlsCaPath;
            std::string m_tlsCertPath;
            std::chrono::seconds m_timeout{ 30 };
        };

        explicit SGChannelManager( Config cfg );
        ~SGChannelManager() = default;

        outcome::result<void> CreateChannel();
        outcome::result<bool> HealthCheck() const;
        outcome::result<void> Reconnect();
        std::shared_ptr<grpc::Channel> GetChannel() const;

        bool IsConnected() const noexcept;

        private:
        Config m_cfg;
        std::shared_ptr<grpc::Channel> m_channel;
    };

} // namespace sgns::neoswarm::network

#endif // NEOSWARM_NETWORK_SG_CLIENT_SGCHANNELMANAGER_HPP
