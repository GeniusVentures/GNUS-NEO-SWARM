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
        bool m_initialized = false;
    };

    SGClient::SGClient( Config cfg )
        : m_impl( std::make_unique<Impl>() )
    {
        m_impl->m_cfg = std::move( cfg );
    }

    SGClient::~SGClient()
    {
        Disconnect();
    }

    SGClient::SGClient( SGClient&& ) noexcept = default;
    SGClient& SGClient::operator=( SGClient&& ) noexcept = default;

    outcome::result<void> SGClient::Initialize( const security::NodeIdentity& identity )
    {
        m_impl->m_identity = &identity;

        m_impl->m_authenticator = std::make_unique<SGMessageAuthenticator>( identity );

        m_impl->jobSubmitter_ = std::make_unique<SGJobSubmitter>( *m_impl->m_authenticator );

        SGResultCollectorConfig rcCfg;
        rcCfg.result_m_timeout = m_impl->m_cfg.result_m_timeout;
        m_impl->resultCollector_ = std::make_unique<SGResultCollector>( *m_impl->m_authenticator, rcCfg );

        const char* initResult = GeniusSDKInitWithKey(
            m_impl->m_cfg.m_sdkBasePath.c_str(),
            m_impl->m_cfg.m_ethKey.c_str(),
            m_impl->m_cfg.m_autoDht,
            m_impl->m_cfg.m_enableProcessing,
            m_impl->m_cfg.m_basePort,
            false );

        if ( initResult == nullptr )
        {
            ClientLogger()->error( "GeniusSDKInitWithKey failed" );
            return outcome::failure( Error::NetworkError );
        }

        m_impl->m_initialized = true;
        ClientLogger()->info( "SGClient initialized — SDK node started at {}", initResult );
        return outcome::success();
    }

    outcome::result<std::vector<uint8_t>> SGClient::SubmitJob( const std::string& gnusSchemaJson )
    {
        if ( !m_impl->m_initialized )
        {
            ClientLogger()->error( "SubmitJob: SGClient not initialized" );
            return outcome::failure( Error::InternalError );
        }

        if ( !m_impl->jobSubmitter_ || !m_impl->resultCollector_ )
        {
            ClientLogger()->error( "SubmitJob: sub-components not initialized" );
            return outcome::failure( Error::InternalError );
        }

        auto taskIdResult = m_impl->jobSubmitter_->PublishJob( gnusSchemaJson );
        if ( !taskIdResult.has_value() )
        {
            ClientLogger()->error( "Failed to publish job: {}", taskIdResult.error().message() );
            return outcome::failure( taskIdResult.error() );
        }

        std::string taskId = taskIdResult.value();
        ClientLogger()->info( "Job published as task {}", taskId );

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
        m_impl->m_initialized = false;
        GeniusSDKShutdown();
        ClientLogger()->info( "SGClient shut down — SDK node stopped" );
    }

    bool SGClient::IsConnected() const noexcept
    {
        if ( !m_impl->m_initialized )
        {
            return false;
        }
        return GeniusSDKGetNodeState() == GENIUS_NODE_READY;
    }

} // namespace sgns::neoswarm::network
