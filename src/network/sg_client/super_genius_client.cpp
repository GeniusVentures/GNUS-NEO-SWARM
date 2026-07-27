/**
 * @file       super_genius_client.cpp
 * @brief      Bridges GNUS NEO SWARM to SuperGenius via GeniusSDK dispatch
 * @date       2026-05-28
 */

#include "super_genius_client.hpp"
#include "sg_job_submitter.hpp"
#include "sg_result_collector.hpp"
#include "common/logging.hpp"
#include "GeniusSDK.h"

#include <nlohmann/json.hpp>

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
        std::unique_ptr<SGJobSubmitter> m_jobSubmitter;
        std::unique_ptr<SGResultCollector> m_resultCollector;
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

    outcome::result<void> SGClient::Initialize()
    {
        m_impl->m_jobSubmitter = std::make_unique<SGJobSubmitter>();

        SGResultCollectorConfig rcCfg;
        rcCfg.m_resultTimeout = m_impl->m_cfg.m_resultTimeout;
        m_impl->m_resultCollector = std::make_unique<SGResultCollector>( rcCfg );

        // SDK generates its own keypair internally for blockchain identity.
        // NEO-SWARM's NodeIdentity is separate (P2P swarm identity).
        // GeniusSDKInit takes the dev config as a JSON string (Address/Cut/TokenValue/TokenID).
        // Serialize via nlohmann::json so user-supplied strings are properly escaped (CR-02).
        const auto& nodeCfg = m_impl->m_cfg.m_geniusNodeConfig;
        const nlohmann::json devConfig = {
            { "Address",    nodeCfg.Addr },
            { "Cut",        nodeCfg.Cut },
            { "TokenValue", nodeCfg.TokenValueInGNUS },
            { "TokenID",    nodeCfg.TokenID.ToHex() },
        };
        const std::string devConfigJson = devConfig.dump();
        const char* initResult = GeniusSDKInit(
            nodeCfg.BaseWritePath.c_str(),
            devConfigJson.c_str() );

        if ( initResult == nullptr )
        {
            ClientLogger()->error( "GeniusSDKInit failed" );
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

        if ( !m_impl->m_jobSubmitter || !m_impl->m_resultCollector )
        {
            ClientLogger()->error( "SubmitJob: sub-components not initialized" );
            return outcome::failure( Error::InternalError );
        }

        auto taskIdResult = m_impl->m_jobSubmitter->PublishJob( gnusSchemaJson );
        if ( !taskIdResult.has_value() )
        {
            ClientLogger()->error( "Failed to publish job: {}", taskIdResult.error().message() );
            return outcome::failure( taskIdResult.error() );
        }

        std::string taskId = taskIdResult.value();
        ClientLogger()->info( "Job published as task {}", taskId );

        auto result = m_impl->m_resultCollector->PollForResult( m_impl->m_cfg.m_resultTimeout );

        if ( !result.has_value() )
        {
            ClientLogger()->warn( "Job {} failed or timed out: {}", taskId, result.error().message() );
        }

        return result;
    }

    void SGClient::Disconnect()
    {
        m_impl->m_jobSubmitter.reset();
        m_impl->m_resultCollector.reset();
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