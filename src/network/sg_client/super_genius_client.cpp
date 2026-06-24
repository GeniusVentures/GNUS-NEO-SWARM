/**
 * @file       super_genius_client.cpp
 * @brief      Bridges GNUS NEO SWARM to SuperGenius via GeniusSDK dispatch
 * @date       2026-05-28
 */

#include "super_genius_client.hpp"
#include "sg_job_submitter.hpp"
#include "sg_message_authenticator.hpp"
#include "sg_result_collector.hpp"
#include "common/logging.hpp"
#include "security/node_identity.hpp"
#include "GeniusSDK.h"

namespace sgns::neoswarm::network
{
    namespace
    {
        auto ClientLogger()
        {
            return CreateLogger( "NeoSwarm/SGClient" );
        }
    } // namespace

    struct SGClient::Impl
    {
        Config m_cfg;
        const security::NodeIdentity* m_identity = nullptr;
        std::unique_ptr<SGMessageAuthenticator> m_authenticator;
        std::unique_ptr<SGJobSubmitter> jobSubmitter_;
        std::unique_ptr<SGResultCollector> resultCollector_;
        bool m_connected = false;
    };

    SGClient::SGClient( Config cfg )
        : m_impl( std::make_unique<Impl>() )
    {
        m_impl->m_cfg = std::move( cfg );
    }

    SGClient::~SGClient() = default;

    SGClient::SGClient( SGClient&& ) noexcept = default;
    SGClient& SGClient::operator=( SGClient&& ) noexcept = default;

    outcome::result<void> SGClient::Initialize( const security::NodeIdentity& identity )
    {
        m_impl->m_identity = &identity;

        m_impl->m_authenticator = std::make_unique<SGMessageAuthenticator>( identity );

        ClientLogger()->info( "SGClient initialized — endpoint={}", m_impl->m_cfg.m_endpoint );
        return outcome::success();
    }

    outcome::result<void> SGClient::Connect()
    {
        if ( m_impl->m_authenticator )
        {
            m_impl->jobSubmitter_ = std::make_unique<SGJobSubmitter>( m_impl->m_cfg.m_endpoint, *m_impl->m_authenticator );

            SGResultCollectorConfig rcCfg;
            rcCfg.result_m_timeout = m_impl->m_cfg.result_m_timeout;
            m_impl->resultCollector_ = std::make_unique<SGResultCollector>( m_impl->m_cfg.m_endpoint, *m_impl->m_authenticator, rcCfg );
        }

        m_impl->m_connected = true;
        ClientLogger()->info( "SGClient connected — GeniusSDK transport active, endpoint={}", m_impl->m_cfg.m_endpoint );
        return outcome::success();
    }

    outcome::result<std::vector<uint8_t>> SGClient::SubmitJob( const std::string& gnusSchemaJson )
    {
        if ( !m_impl->m_connected )
        {
            ClientLogger()->warn( "Not connected, attempting reconnect" );
            auto reconnectResult = Connect();
            if ( !reconnectResult.has_value() )
            {
                ClientLogger()->error( "Reconnect failed — cannot submit job" );
                return outcome::failure( Error::NetworkError );
            }
        }

        if ( !m_impl->jobSubmitter_ || !m_impl->resultCollector_ )
        {
            ClientLogger()->error( "SubmitJob: sub-components not initialized" );
            return outcome::failure( Error::InternalError );
        }

        // Step 1: Publish the signed job via GeniusSDK
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

    void SGClient::Disconnect()
    {
        m_impl->jobSubmitter_.reset();
        m_impl->resultCollector_.reset();
        m_impl->m_connected = false;
        ClientLogger()->info( "SGClient disconnected" );
    }

    bool SGClient::IsConnected() const noexcept
    {
        return m_impl->m_connected;
    }

} // namespace sgns::neoswarm::network
