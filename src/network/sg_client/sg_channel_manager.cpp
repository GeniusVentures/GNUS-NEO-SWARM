/**
 * @file       sg_channel_manager.cpp
 * @brief      gRPC channel lifecycle implementation — TLS, keepalive, reconnect
 * @date       2026-05-28
 * @author     Subaskar S (ssivakumar@gnus.ai)
 */

#include "sg_channel_manager.hpp"
#include "common/logging.hpp"
#include <chrono>
#include <thread>

namespace sgns::neoswarm::network
{
    namespace
    {
        auto ChannelLogger()
        {
            return CreateLogger( "NeoSwarm/SGChannel" );
        }

        constexpr int kMaxReconnectAttempts = 5;
        constexpr std::chrono::seconds kMaxBackoff{ 30 };
    } // namespace

    SGChannelManager::SGChannelManager( Config cfg )
        : m_cfg( std::move( cfg ) )
    {
    }

    outcome::result<void> SGChannelManager::CreateChannel()
    {
        if ( m_channel )
        {
            ChannelLogger()->debug( "Channel already exists, reusing" );
            return outcome::success();
        }

        bool isLocalhost = m_cfg.m_endpoint.find( "localhost" ) != std::string::npos ||
                           m_cfg.m_endpoint.find( "127.0.0.1" ) != std::string::npos;
#ifdef GENIUS_HAS_GRPC

        std::shared_ptr<grpc::ChannelCredentials> creds;

        if ( !m_cfg.m_tlsCaPath.empty() || !isLocalhost )
        {
            // TLS required — load CA bundle
            grpc::SslCredentialsOptions sslOpts;
            if ( !m_cfg.m_tlsCaPath.empty() )
            {
                sslOpts.pem_root_certs = m_cfg.m_tlsCaPath;
            }
            creds = grpc::SslCredentials( sslOpts );
            ChannelLogger()->info( "Creating TLS-secured channel to {}", m_cfg.m_endpoint );
        }
        else
        {
            // Localhost without TLS certs — insecure with warning
            creds = grpc::InsecureChannelCredentials();
            ChannelLogger()->warn( "Creating INSECURE channel to {} — TLS not configured", m_cfg.m_endpoint );
        }

        grpc::ChannelArguments args;
        args.SetInt( GRPC_ARG_KEEPALIVE_TIME_MS, 30000 );
        args.SetInt( GRPC_ARG_KEEPALIVE_TIMEOUT_MS, 10000 );
        args.SetInt( GRPC_ARG_KEEPALIVE_PERMIT_WITHOUT_CALLS, 1 );

        m_channel = grpc::CreateCustomChannel( m_cfg.m_endpoint, creds, args );

        if ( !m_channel )
        {
            ChannelLogger()->error( "Failed to create channel to {}", m_cfg.m_endpoint );
            return outcome::failure( Error::NetworkError );
        }
#endif  // GENIUS_HAS_GRPC

        ChannelLogger()->info( "Channel created to {}", m_cfg.m_endpoint );
        return outcome::success();

    }

    outcome::result<bool> SGChannelManager::HealthCheck() const
    {
        if ( !m_channel )
        {
            return false;
        }

        auto state = m_channel->GetState( false );
        if ( state == GRPC_CHANNEL_READY )
        {
            return true;
        }
        ChannelLogger()->debug( "Channel health check: state={}", static_cast<int>( state ) );
        return false;

    }

    outcome::result<void> SGChannelManager::Reconnect()
    {
        m_channel.reset();

        std::chrono::seconds backoff{ 1 };

        for ( int attempt = 0; attempt < kMaxReconnectAttempts; ++attempt )
        {
            ChannelLogger()->info( "Reconnect attempt {}/{} (backoff={}s)", attempt + 1, kMaxReconnectAttempts,
                                   backoff.count() );

            std::this_thread::sleep_for( backoff );

            auto result = CreateChannel();
            if ( result.has_value() )
            {
                // Verify with health check
                auto health = HealthCheck();
                if ( health.has_value() && health.value() )
                {
                    ChannelLogger()->info( "Reconnected successfully on attempt {}", attempt + 1 );
                    return outcome::success();
                }
            }

            // Exponential backoff: 1s → 2s → 4s → 8s → 16s → 30s
            backoff = std::min( backoff * 2, kMaxBackoff );
        }

        ChannelLogger()->error( "Reconnect failed after {} attempts", kMaxReconnectAttempts );
        return outcome::failure( Error::NetworkError );
    }

    std::shared_ptr<grpc::Channel> SGChannelManager::GetChannel() const
    {
        return m_channel;
    }

    bool SGChannelManager::IsConnected() const noexcept
    {
        auto health = HealthCheck();
        return health.has_value() && health.value();
    }

} // namespace sgns::neoswarm::network
