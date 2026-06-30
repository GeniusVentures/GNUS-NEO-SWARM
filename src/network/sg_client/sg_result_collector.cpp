/**
 * @file       sg_result_collector.cpp
 * @brief      Timeout-bounded result collection via GeniusSDK polling
 * @date       2026-05-28
 */

#include "sg_result_collector.hpp"
#include "sg_message_authenticator.hpp"
#include "common/logging.hpp"
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
    } // namespace

    struct SGResultCollector::Impl
    {
        SGMessageAuthenticator& m_authenticator;
        SGResultCollectorConfig m_cfg;

        std::mutex m_mutex;
        std::condition_variable cv_;
        bool resultReady_ = false;
        std::vector<uint8_t> resultData_;

        Impl( SGMessageAuthenticator& authenticator, SGResultCollectorConfig cfg )
            : m_authenticator( authenticator )
            , m_cfg( std::move( cfg ) )
        {
        }
    };

    SGResultCollector::SGResultCollector( SGMessageAuthenticator& authenticator, SGResultCollectorConfig cfg )
        : m_impl( std::make_unique<Impl>( authenticator, std::move( cfg ) ) )
    {
    }

    outcome::result<std::vector<uint8_t>> SGResultCollector::WaitForResult( const std::string& taskId,
                                                                             std::chrono::seconds timeout )
    {
        CollectLogger()->info( "Waiting for result on results/{} (timeout={}s)", taskId, timeout.count() );

        // TODO(Phase 2 Wave 3): poll GeniusSDKGetProcessingStatus() in a loop
        std::unique_lock<std::mutex> lock( m_impl->m_mutex );

        bool gotResult = m_impl->cv_.wait_for( lock, timeout, [this] { return m_impl->resultReady_; } );

        if ( !gotResult )
        {
            CollectLogger()->warn( "Result collection timed out for task {}", taskId );
            return outcome::failure( Error::BroadcastTimeout );
        }

        if ( m_impl->resultData_.empty() )
        {
            CollectLogger()->warn( "Empty result received for task {}", taskId );
            return outcome::failure( Error::InferenceFailed );
        }

        CollectLogger()->info( "Result collected for task {} ({} bytes)", taskId, m_impl->resultData_.size() );

        std::vector<uint8_t> result = std::move( m_impl->resultData_ );
        m_impl->resultReady_ = false;

        return outcome::success( result );
    }

    outcome::result<std::vector<uint8_t>> SGResultCollector::WaitForResult( const std::string& taskId )
    {
        return WaitForResult( taskId, m_impl->m_cfg.result_m_timeout );
    }

    SGResultCollector::~SGResultCollector() = default;

} // namespace sgns::neoswarm::network
