/**
 * @file       SuperGeniusClient.cpp
 * @brief      Bridges GNUS NEO SWARM to SuperGenius via PubSub gRPC dispatch
 * @date       2026-05-28
 * @author     Subaskar S (ssivakumar@gnus.ai)
 */

#include "SuperGeniusClient.hpp"
#include "SGChannelManager.hpp"
#include "SGJobSubmitter.hpp"
#include "SGMessageAuthenticator.hpp"
#include "SGResultCollector.hpp"
#include "common/Logging.hpp"
#include "security/NodeIdentity.hpp"

namespace sgns::neoswarm::network
{
    namespace
    {
        auto ClientLogger()
        {
            return CreateLogger( "NeoSwarm/SGClient" );
        }
    } // namespace

    struct SuperGeniusClient::Impl
    {
        Config cfg_;
        const security::NodeIdentity* identity_ = nullptr;
        std::unique_ptr<SGMessageAuthenticator> authenticator_;
        std::unique_ptr<SGChannelManager> channelMgr_;
        std::unique_ptr<SGJobSubmitter> jobSubmitter_;
        std::unique_ptr<SGResultCollector> resultCollector_;
        bool connected_ = false;
    };

    SuperGeniusClient::SuperGeniusClient( Config cfg )
        : impl_( std::make_unique<Impl>() )
    {
        impl_->cfg_ = std::move( cfg );
    }

    SuperGeniusClient::~SuperGeniusClient() = default;

    SuperGeniusClient::SuperGeniusClient( SuperGeniusClient&& ) noexcept = default;
    SuperGeniusClient& SuperGeniusClient::operator=( SuperGeniusClient&& ) noexcept = default;

    outcome::result<void> SuperGeniusClient::Initialize( const security::NodeIdentity& identity )
    {
        impl_->identity_ = &identity;

        // Create authenticator using the hardened NodeIdentity from Phase 1
        impl_->authenticator_ = std::make_unique<SGMessageAuthenticator>( identity );

        // Create channel manager with configured endpoint and TLS settings
        SGChannelManager::Config chCfg;
        chCfg.endpoint_ = impl_->cfg_.endpoint_;
        chCfg.tls_ca_path_ = impl_->cfg_.tls_ca_path_;
        chCfg.tls_cert_path_ = impl_->cfg_.tls_cert_path_;
        chCfg.timeout_ = impl_->cfg_.channel_timeout_;

        impl_->channelMgr_ = std::make_unique<SGChannelManager>( std::move( chCfg ) );

        ClientLogger()->info( "SuperGeniusClient initialized — endpoint={}", impl_->cfg_.endpoint_ );
        return outcome::success();
    }

    outcome::result<void> SuperGeniusClient::Connect()
    {
        if ( !impl_->channelMgr_ )
        {
            ClientLogger()->error( "Connect called before Initialize" );
            return outcome::failure( Error::InternalError );
        }

        auto result = impl_->channelMgr_->CreateChannel();
        if ( !result.has_value() )
        {
            ClientLogger()->warn( "Failed to create channel to {} — SuperGenius unavailable", impl_->cfg_.endpoint_ );
            return result;
        }

        auto channel = impl_->channelMgr_->GetChannel();
        if ( channel && impl_->authenticator_ )
        {
            // Create sub-components that depend on the channel
            impl_->jobSubmitter_ = std::make_unique<SGJobSubmitter>( channel, *impl_->authenticator_ );

            SGResultCollectorConfig rcCfg;
            rcCfg.result_timeout_ = impl_->cfg_.result_timeout_;
            impl_->resultCollector_ = std::make_unique<SGResultCollector>( channel, *impl_->authenticator_, rcCfg );
        }

        // Verify connectivity
        auto health = impl_->channelMgr_->HealthCheck();
        if ( health.has_value() && health.value() )
        {
            impl_->connected_ = true;
            ClientLogger()->info( "Connected to SuperGenius at {}", impl_->cfg_.endpoint_ );
        }
        else
        {
            ClientLogger()->warn( "Channel created but health check failed — may be starting up" );
            impl_->connected_ = true;
        }

        return outcome::success();
    }

    outcome::result<std::vector<uint8_t>> SuperGeniusClient::SubmitJob( const std::string& gnusSchemaJson )
    {
        // Verify we are connected — attempt reconnect if channel is dead
        if ( !impl_->connected_ || !impl_->channelMgr_->IsConnected() )
        {
            ClientLogger()->warn( "Channel not connected, attempting reconnect" );
            auto reconnectResult = impl_->channelMgr_->Reconnect();
            if ( !reconnectResult.has_value() )
            {
                ClientLogger()->error( "Reconnect failed — cannot submit job" );
                return outcome::failure( Error::NetworkError );
            }
            impl_->connected_ = true;
        }

        if ( !impl_->jobSubmitter_ || !impl_->resultCollector_ )
        {
            ClientLogger()->error( "SubmitJob: sub-components not initialized" );
            return outcome::failure( Error::InternalError );
        }

        // Step 1: Publish the signed job to the grid channel
        auto taskIdResult = impl_->jobSubmitter_->PublishJob( gnusSchemaJson );
        if ( !taskIdResult.has_value() )
        {
            ClientLogger()->error( "Failed to publish job: {}", taskIdResult.error().message() );
            return outcome::failure( taskIdResult.error() );
        }

        std::string taskId = taskIdResult.value();
        ClientLogger()->info( "Job published as task {}", taskId );

        // Step 2: Wait for the result with timeout-bounded collection
        auto result = impl_->resultCollector_->WaitForResult( taskId, impl_->cfg_.result_timeout_ );

        if ( !result.has_value() )
        {
            ClientLogger()->warn( "Job {} failed or timed out: {}", taskId, result.error().message() );
        }

        return result;
    }

    void SuperGeniusClient::Disconnect()
    {
        impl_->jobSubmitter_.reset();
        impl_->resultCollector_.reset();
        impl_->channelMgr_.reset();
        impl_->connected_ = false;
        ClientLogger()->info( "SuperGeniusClient disconnected" );
    }

    bool SuperGeniusClient::IsConnected() const noexcept
    {
        return impl_->connected_ && impl_->channelMgr_ && impl_->channelMgr_->IsConnected();
    }

} // namespace sgns::neoswarm::network
