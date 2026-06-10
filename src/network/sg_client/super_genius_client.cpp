/**
 * @file       super_genius_client.cpp
 * @brief      Bridges GNUS NEO SWARM to SuperGenius via PubSub gRPC dispatch
 * @date       2026-05-28
 * @author     Subaskar S (ssivakumar@gnus.ai)
 */

#include "super_genius_client.hpp"
#include "sg_channel_manager.hpp"
#include "sg_job_submitter.hpp"
#include "sg_message_authenticator.hpp"
#include "sg_result_collector.hpp"
#include "common/logging.hpp"
#include "security/node_identity.hpp"

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
        Config m_cfg;
        const security::NodeIdentity* m_identity = nullptr;
        std::unique_ptr<SGMessageAuthenticator> m_authenticator;
        std::unique_ptr<SGChannelManager> channelMgr_;
        std::unique_ptr<SGJobSubmitter> jobSubmitter_;
        std::unique_ptr<SGResultCollector> resultCollector_;
        bool m_connected = false;
    };

    SuperGeniusClient::SuperGeniusClient( Config cfg )
        : m_impl( std::make_unique<Impl>() )
    {
        m_impl->m_cfg = std::move( cfg );
    }

    SuperGeniusClient::~SuperGeniusClient() = default;

    SuperGeniusClient::SuperGeniusClient( SuperGeniusClient&& ) noexcept = default;
    SuperGeniusClient& SuperGeniusClient::operator=( SuperGeniusClient&& ) noexcept = default;

    outcome::result<void> SuperGeniusClient::Initialize( const security::NodeIdentity& identity )
    {
        m_impl->m_identity = &identity;

        // Create authenticator using the hardened NodeIdentity from Phase 1
        m_impl->m_authenticator = std::make_unique<SGMessageAuthenticator>( identity );

        // Create channel manager with configured endpoint and TLS settings
        SGChannelManager::Config chCfg;
        chCfg.m_endpoint = m_impl->m_cfg.m_endpoint;
        chCfg.m_tlsCaPath = m_impl->m_cfg.m_tlsCaPath;
        chCfg.m_tlsCertPath = m_impl->m_cfg.m_tlsCertPath;
        chCfg.m_timeout = m_impl->m_cfg.channel_m_timeout;

        m_impl->channelMgr_ = std::make_unique<SGChannelManager>( std::move( chCfg ) );

        ClientLogger()->info( "SuperGeniusClient initialized — endpoint={}", m_impl->m_cfg.m_endpoint );
        return outcome::success();
    }

    outcome::result<void> SuperGeniusClient::Connect()
    {
        if ( !m_impl->channelMgr_ )
        {
            ClientLogger()->error( "Connect called before Initialize" );
            return outcome::failure( Error::InternalError );
        }

        auto result = m_impl->channelMgr_->CreateChannel();
        if ( !result.has_value() )
        {
            ClientLogger()->warn( "Failed to create channel to {} — SuperGenius unavailable", m_impl->m_cfg.m_endpoint );
            return result;
        }

        auto channel = m_impl->channelMgr_->GetChannel();
        if ( channel && m_impl->m_authenticator )
        {
            // Create sub-components that depend on the channel
            m_impl->jobSubmitter_ = std::make_unique<SGJobSubmitter>( channel, *m_impl->m_authenticator );

            SGResultCollectorConfig rcCfg;
            rcCfg.result_m_timeout = m_impl->m_cfg.result_m_timeout;
            m_impl->resultCollector_ = std::make_unique<SGResultCollector>( channel, *m_impl->m_authenticator, rcCfg );
        }

        // Verify connectivity
        auto health = m_impl->channelMgr_->HealthCheck();
        if ( health.has_value() && health.value() )
        {
            m_impl->m_connected = true;
            ClientLogger()->info( "Connected to SuperGenius at {}", m_impl->m_cfg.m_endpoint );
        }
        else
        {
            ClientLogger()->warn( "Channel created but health check failed — may be starting up" );
            m_impl->m_connected = true;
        }

        return outcome::success();
    }

    outcome::result<std::vector<uint8_t>> SuperGeniusClient::SubmitJob( const std::string& gnusSchemaJson )
    {
        // Verify we are connected — attempt reconnect if channel is dead
        if ( !m_impl->m_connected || !m_impl->channelMgr_->IsConnected() )
        {
            ClientLogger()->warn( "Channel not connected, attempting reconnect" );
            auto reconnectResult = m_impl->channelMgr_->Reconnect();
            if ( !reconnectResult.has_value() )
            {
                ClientLogger()->error( "Reconnect failed — cannot submit job" );
                return outcome::failure( Error::NetworkError );
            }
            m_impl->m_connected = true;
        }

        if ( !m_impl->jobSubmitter_ || !m_impl->resultCollector_ )
        {
            ClientLogger()->error( "SubmitJob: sub-components not initialized" );
            return outcome::failure( Error::InternalError );
        }

        // Step 1: Publish the signed job to the grid channel
        auto taskIdResult = m_impl->jobSubmitter_->PublishJob( gnusSchemaJson );
        if ( !taskIdResult.has_value() )
        {
            ClientLogger()->error( "Failed to publish job: {}", taskIdResult.error().message() );
            return outcome::failure( taskIdResult.error() );
        }

        std::string taskId = taskIdResult.value();
        ClientLogger()->info( "Job published as task {}", taskId );

        // Step 2: Wait for the result with timeout-bounded collection
        auto result = m_impl->resultCollector_->WaitForResult( taskId, m_impl->m_cfg.result_m_timeout );

        if ( !result.has_value() )
        {
            ClientLogger()->warn( "Job {} failed or timed out: {}", taskId, result.error().message() );
        }

        return result;
    }

    void SuperGeniusClient::Disconnect()
    {
        m_impl->jobSubmitter_.reset();
        m_impl->resultCollector_.reset();
        m_impl->channelMgr_.reset();
        m_impl->m_connected = false;
        ClientLogger()->info( "SuperGeniusClient disconnected" );
    }

    bool SuperGeniusClient::IsConnected() const noexcept
    {
        return m_impl->m_connected && m_impl->channelMgr_ && m_impl->channelMgr_->IsConnected();
    }

} // namespace sgns::neoswarm::network
