/**
 * @file       SGResultCollector.cpp
 * @brief      Timeout-bounded result collection from SuperGenius PubSub result channels
 * @date       2026-05-28
 * @author     Subaskar S (ssivakumar@gnus.ai)
 */

#include "SGResultCollector.hpp"
#include "SGMessageAuthenticator.hpp"
#include "common/Logging.hpp"
#include <condition_variable>
#include <mutex>

namespace sgns::neoswarm::network
{
    namespace
    {
        auto CollectLogger()
        {
            return CreateLogger( "NeoSwarm/SGCollect" );
        }
    }

    struct SGResultCollector::Impl
    {
        std::shared_ptr<grpc::Channel> channel_;
        SGMessageAuthenticator        &authenticator_;
        Config                         cfg_;

        // Timeout-bounded collection using condition_variable
        // (matches existing ResultAggregation pattern)
        std::mutex                     mutex_;
        std::condition_variable        cv_;
        bool                           resultReady_ = false;
        std::vector<uint8_t>           resultData_;

        Impl( std::shared_ptr<grpc::Channel>  channel,
              SGMessageAuthenticator         &authenticator,
              Config                          cfg )
            : channel_( std::move( channel ) )
            , authenticator_( authenticator )
            , cfg_( std::move( cfg ) )
        {
        }
    };

    SGResultCollector::SGResultCollector(
        std::shared_ptr<grpc::Channel>  channel,
        SGMessageAuthenticator         &authenticator,
        Config                          cfg )
        : impl_( std::make_unique<Impl>(
            std::move( channel ), authenticator, std::move( cfg ) ) )
    {
    }

    outcome::result<std::vector<uint8_t>> SGResultCollector::WaitForResult(
        const std::string          &taskId,
        std::chrono::seconds        timeout )
    {
        CollectLogger()->info( "Waiting for result on results/{} (timeout={}s)",
                               taskId, timeout.count() );

        // Subscribe to results/<taskId> channel
        // TODO(Phase 2): implement actual gRPC PubSub subscribe when service stubs linked

        // Block until result arrives or timeout expires
        // Pattern matches ResultAggregation::Collect() in src/network/ResultAggregation.cpp
        std::unique_lock<std::mutex> lock( impl_->mutex_ );

        bool gotResult = impl_->cv_.wait_for(
            lock,
            timeout,
            [this]{ return impl_->resultReady_; } );

        if ( !gotResult )
        {
            CollectLogger()->warn( "Result collection timed out for task {}", taskId );
            return outcome::failure( Error::BroadcastTimeout );
        }

        if ( impl_->resultData_.empty() )
        {
            CollectLogger()->warn( "Empty result received for task {}", taskId );
            return outcome::failure( Error::InferenceFailed );
        }

        CollectLogger()->info( "Result collected for task {} ({} bytes)",
                               taskId, impl_->resultData_.size() );

        std::vector<uint8_t> result = std::move( impl_->resultData_ );
        impl_->resultReady_ = false;

        return outcome::success( result );
    }

    outcome::result<std::vector<uint8_t>> SGResultCollector::WaitForResult(
        const std::string &taskId )
    {
        return WaitForResult( taskId, impl_->cfg_.result_timeout_ );
    }

} // namespace sgns::neoswarm::network
