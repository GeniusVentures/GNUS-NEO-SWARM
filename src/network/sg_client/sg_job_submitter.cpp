/**
 * @file       sg_job_submitter.cpp
 * @brief      Dispatches GNUS schema JSON directly to GeniusSDKProcess
 * @date       2026-05-28
 */

#include "sg_job_submitter.hpp"
#include "common/logging.hpp"
#include "GeniusSDK.h"
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

    outcome::result<std::string> SGJobSubmitter::PublishJob( const std::string& gnusSchemaJson )
    {
        std::string taskId = GenerateTaskId();

        if ( gnusSchemaJson.size() >= sizeof( JsonData_t ) )
        {
            SubmitLogger()->error( "Task payload too large for GeniusSDK ({} bytes, max {})",
                                   gnusSchemaJson.size(), sizeof( JsonData_t ) - 1 );
            return outcome::failure( Error::InvalidArgument );
        }

        SubmitLogger()->info( "Publishing task {} ({} bytes)", taskId, gnusSchemaJson.size() );

        auto sdkResult = GeniusSDKProcess( gnusSchemaJson.c_str() );
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
