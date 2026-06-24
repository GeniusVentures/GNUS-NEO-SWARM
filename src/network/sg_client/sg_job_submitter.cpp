/**
 * @file       sg_job_submitter.cpp
 * @brief      Publishes signed Task messages via GeniusSDK dispatch
 * @date       2026-05-28
 */

#include "sg_job_submitter.hpp"
#include "sg_message_authenticator.hpp"
#include "common/logging.hpp"
#include "GeniusSDK.h"
#include <chrono>
#include <cstring>
#include <iomanip>
#include <random>
#include <sstream>

namespace sgns::neoswarm::network
{
    namespace
    {
        auto SubmitLogger()
        {
            return CreateLogger( "NeoSwarm/SGSubmit" );
        }

        std::string GenerateTaskId()
        {
            auto now = std::chrono::steady_clock::now();
            auto ms = std::chrono::duration_cast<std::chrono::milliseconds>( now.time_since_epoch() ).count();

            std::random_device rd;
            std::mt19937 gen( rd() );
            std::uniform_int_distribution<uint32_t> dist;

            std::ostringstream oss;
            oss << "task-" << std::hex << ms << "-" << dist( gen );
            return oss.str();
        }
    } // namespace

    struct SGJobSubmitter::Impl
    {
        std::string m_endpoint;
        SGMessageAuthenticator& m_authenticator;

        Impl( const std::string& endpoint, SGMessageAuthenticator& authenticator )
            : m_endpoint( endpoint )
            , m_authenticator( authenticator )
        {
        }
    };

    SGJobSubmitter::SGJobSubmitter( const std::string& endpoint, SGMessageAuthenticator& authenticator )
        : m_impl( std::make_unique<Impl>( endpoint, authenticator ) )
    {
    }

    outcome::result<std::string> SGJobSubmitter::PublishJob( const std::string& gnusSchemaJson )
    {
        std::string taskId = GenerateTaskId();

        auto signedPayload = m_impl->m_authenticator.SignPayload( gnusSchemaJson );
        if ( !signedPayload.has_value() )
        {
            SubmitLogger()->error( "Failed to sign payload: {}", signedPayload.error().message() );
            return outcome::failure( signedPayload.error() );
        }

        std::ostringstream taskJson;
        taskJson << "{"
                 << "\"task_id\":\"" << taskId << "\","
                 << "\"results_channel\":\"results/" << taskId << "\","
                 << "\"json_data\":" << signedPayload.value() << "}";

        std::string taskMessage = taskJson.str();

        SubmitLogger()->info( "Publishing task {} to {} ({} bytes, signed)", taskId, m_impl->m_endpoint, taskMessage.size() );

        if ( taskMessage.size() >= 2048 )
        {
            SubmitLogger()->error( "Task payload too large for GeniusSDK ({} bytes, max 2047)", taskMessage.size() );
            return outcome::failure( Error::InvalidArgument );
        }

        JsonData_t sdkPayload;
        std::strncpy( sdkPayload, taskMessage.c_str(), sizeof( sdkPayload ) - 1 );
        sdkPayload[ sizeof( sdkPayload ) - 1 ] = '\0';

        auto sdkResult = GeniusSDKProcess( sdkPayload );
        if ( sdkResult != GENIUS_NODE_RET_OK )
        {
            SubmitLogger()->error( "GeniusSDKProcess failed: error code {}", static_cast<int>( sdkResult ) );
            return outcome::failure( Error::NetworkError );
        }

        SubmitLogger()->info( "Task {} dispatched via GeniusSDK", taskId );
        return taskId;

    }

    SGJobSubmitter::~SGJobSubmitter() = default;

} // namespace sgns::neoswarm::network
