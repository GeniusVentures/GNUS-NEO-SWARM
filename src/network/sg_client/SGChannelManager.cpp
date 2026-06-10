/**
 * @file       SGChannelManager.cpp
 * @brief      gRPC channel lifecycle implementation — TLS, keepalive, reconnect
 * @date       2026-05-28
 * @author     Subaskar S (ssivakumar@gnus.ai)
 */

#include "SGChannelManager.hpp"
#include "common/Logging.hpp"
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
        : cfg_( std::move( cfg ) )
    {
    }

    outcome::result<void> SGChannelManager::CreateChannel()
    {
        if ( channel_ )
        {
            ChannelLogger()->debug( "Channel already exists, reusing" );
            return outcome::success();
        }

#ifdef GENIUS_HAS_GRPC
        bool isLocalhost = cfg_.endpoint_.find( "localhost" ) != std::string::npos ||
                           cfg_.endpoint_.find( "127.0.0.1" ) != std::string::npos;

        std::shared_ptr<grpc::ChannelCredentials> creds;

        if ( !cfg_.tls_ca_path_.empty() || !isLocalhost )
        {
            // TLS required — load CA bundle
            grpc::SslCredentialsOptions sslOpts;
            if ( !cfg_.tls_ca_path_.empty() )
            {
                sslOpts.pem_root_certs = cfg_.tls_ca_path_;
            }
            creds = grpc::SslCredentials( sslOpts );
            ChannelLogger()->info( "Creating TLS-secured channel to {}", cfg_.endpoint_ );
        }
        else
        {
            // Localhost without TLS certs — insecure with warning
            creds = grpc::InsecureChannelCredentials();
            ChannelLogger()->warn( "Creating INSECURE channel to {} — TLS not configured", cfg_.endpoint_ );
        }

        grpc::ChannelArguments args;
        args.SetInt( GRPC_ARG_KEEPALIVE_TIME_MS, 30000 );
        args.SetInt( GRPC_ARG_KEEPALIVE_TIMEOUT_MS, 10000 );
        args.SetInt( GRPC_ARG_KEEPALIVE_PERMIT_WITHOUT_CALLS, 1 );

        channel_ = grpc::CreateCustomChannel( cfg_.endpoint_, creds, args );

        if ( !channel_ )
        {
            ChannelLogger()->error( "Failed to create channel to {}", cfg_.endpoint_ );
            return outcome::failure( Error::NETWORK_ERROR );
        }

        ChannelLogger()->info( "Channel created to {}", cfg_.endpoint_ );
        return outcome::success();
#else
        ChannelLogger()->warn( "SGChannelManager: gRPC not compiled in — stub mode" );
        return outcome::failure( Error::NOT_IMPLEMENTED );
#endif
    }

    outcome::result<bool> SGChannelManager::HealthCheck() const
    {
        if ( !channel_ )
        {
            return false;
        }

#ifdef GENIUS_HAS_GRPC
        auto state = channel_->GetState( false );
        if ( state == GRPC_CHANNEL_READY )
        {
            return true;
        }
        ChannelLogger()->debug( "Channel health check: state={}", static_cast<int>( state ) );
        return false;
#else
        return false;
#endif
    }

    outcome::result<void> SGChannelManager::Reconnect()
    {
        channel_.reset();

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
        return outcome::failure( Error::NETWORK_ERROR );
    }

    std::shared_ptr<grpc::Channel> SGChannelManager::GetChannel() const
    {
        return channel_;
    }

    bool SGChannelManager::IsConnected() const noexcept
    {
        auto health = HealthCheck();
        return health.has_value() && health.value();
    }

} // namespace sgns::neoswarm::network
