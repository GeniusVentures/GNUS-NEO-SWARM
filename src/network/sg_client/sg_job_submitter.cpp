/**
 * @file       sg_job_submitter.cpp
 * @brief      Publishes signed Task messages via GeniusSDK dispatch
 * @date       2026-05-28
 */

#include "sg_job_submitter.hpp"
#include "sg_message_authenticator.hpp"
#include "common/logging.hpp"
#include <chrono>
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
        SGMessageAuthenticator& m_authenticator;

        Impl( SGMessageAuthenticator& authenticator )
            : m_authenticator( authenticator )
        {
        }
    };

    SGJobSubmitter::SGJobSubmitter( SGMessageAuthenticator& authenticator )
        : m_impl( std::make_unique<Impl>( authenticator ) )
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

        SubmitLogger()->info( "Publishing task {} ({} bytes, signed)", taskId, taskMessage.size() );

        // TODO(Phase 2 Wave 2): dispatch via GeniusSDKProcess(taskMessage)
        SubmitLogger()->warn( "GeniusSDK dispatch not yet wired — task {} prepared for submission", taskId );

        return taskId;

    }

    SGJobSubmitter::~SGJobSubmitter() = default;

} // namespace sgns::neoswarm::network
