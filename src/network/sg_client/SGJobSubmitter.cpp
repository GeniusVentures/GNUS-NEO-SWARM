/**
 * @file       SGJobSubmitter.cpp
 * @brief      Publishes signed Task messages to the SuperGenius grid channel via PubSub
 * @date       2026-05-28
 * @author     Subaskar S (ssivakumar@gnus.ai)
 */

#include "SGJobSubmitter.hpp"
#include "SGMessageAuthenticator.hpp"
#include "common/Logging.hpp"
#include <chrono>
#include <random>
#include <sstream>
#include <iomanip>

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
            // Simple unique task ID: timestamp + random hex
            auto now = std::chrono::steady_clock::now();
            auto ms  = std::chrono::duration_cast<std::chrono::milliseconds>(
                now.time_since_epoch() ).count();

            std::random_device rd;
            std::mt19937       gen( rd() );
            std::uniform_int_distribution<uint32_t> dist;

            std::ostringstream oss;
            oss << "task-" << std::hex << ms << "-" << dist( gen );
            return oss.str();
        }
    }

    struct SGJobSubmitter::Impl
    {
        std::shared_ptr<grpc::Channel> channel_;
        SGMessageAuthenticator        &authenticator_;
        std::string                    gridChannel_ = "gnus.processing.grid";

        Impl( std::shared_ptr<grpc::Channel>  channel,
              SGMessageAuthenticator         &authenticator )
            : channel_( std::move( channel ) )
            , authenticator_( authenticator )
        {
        }
    };

    SGJobSubmitter::SGJobSubmitter(
        std::shared_ptr<grpc::Channel>  channel,
        SGMessageAuthenticator         &authenticator )
        : impl_( std::make_unique<Impl>( std::move( channel ), authenticator ) )
    {
    }

    outcome::result<std::string> SGJobSubmitter::PublishJob(
        const std::string &gnusSchemaJson )
    {
        std::string taskId = GenerateTaskId();

#ifdef GENIUS_HAS_GRPC
        // Sign the payload with nonce + timestamp + secp256k1 signature
        auto signedPayload = impl_->authenticator_.SignPayload( gnusSchemaJson );
        if ( !signedPayload.has_value() )
        {
            SubmitLogger()->error( "Failed to sign payload: {}", signedPayload.error().message() );
            return outcome::failure( signedPayload.error() );
        }

        // Build the Task message with results channel
        // Format: { "task_id": "...", "results_channel": "results/...",
        //           "json_data": <signed_payload> }
        std::ostringstream taskJson;
        taskJson << "{"
                 << "\"task_id\":\"" << taskId << "\","
                 << "\"results_channel\":\"results/" << taskId << "\","
                 << "\"json_data\":" << signedPayload.value()
                 << "}";

        std::string taskMessage = taskJson.str();

        // Publish to grid channel via PubSub
        // Actual gRPC PubSub publish implementation depends on the
        // SuperGenius gRPC service definitions
        SubmitLogger()->info( "Publishing task {} to grid channel ({} bytes, signed)",
                              taskId, taskMessage.size() );
        SubmitLogger()->debug( "Task payload preview: {}...", taskMessage.substr( 0, 120 ) );

        // TODO(Phase 2): implement actual gRPC PubSub publish via
        // SuperGenius processing API once service stubs are linked
        SubmitLogger()->warn( "gRPC PubSub publish not yet wired — task {} prepared for dispatch",
                              taskId );

        return taskId;
#else
        SubmitLogger()->warn( "SGJobSubmitter: gRPC not compiled in — returning taskId as stub" );
        return taskId;
#endif
    }

    SGJobSubmitter::~SGJobSubmitter() = default;

} // namespace sgns::neoswarm::network
