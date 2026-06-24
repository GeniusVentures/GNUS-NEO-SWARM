/**
 * @file       sg_result_collector.cpp
 * @brief      Timeout-bounded result collection via GeniusSDK polling
 * @date       2026-05-28
 */

#include "sg_result_collector.hpp"
#include "sg_message_authenticator.hpp"
#include "common/logging.hpp"
#include "GeniusSDK.h"
#include <chrono>
#include <condition_variable>
#include <mutex>
#include <thread>

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
        std::string m_endpoint;
        SGMessageAuthenticator& m_authenticator;
        SGResultCollectorConfig m_cfg;

        std::mutex m_mutex;
        std::condition_variable cv_;
        bool resultReady_ = false;
        std::vector<uint8_t> resultData_;

        Impl( const std::string& endpoint,
              SGMessageAuthenticator& authenticator,
              SGResultCollectorConfig cfg )
            : m_endpoint( endpoint )
            , m_authenticator( authenticator )
            , m_cfg( std::move( cfg ) )
        {
        }
    };

    SGResultCollector::SGResultCollector( const std::string& endpoint,
                                          SGMessageAuthenticator& authenticator,
                                          SGResultCollectorConfig cfg )
        : m_impl( std::make_unique<Impl>( endpoint, authenticator, std::move( cfg ) ) )
    {
    }

    outcome::result<std::vector<uint8_t>> SGResultCollector::WaitForResult( const std::string& taskId,
                                                                             std::chrono::seconds timeout )
    {
        CollectLogger()->info( "Waiting for result on task {} (timeout={}s)", taskId, timeout.count() );

        constexpr std::chrono::milliseconds kPollInterval{ 500 };
        auto deadline = std::chrono::steady_clock::now() + timeout;
        int pollCount = 0;

        while ( std::chrono::steady_clock::now() < deadline )
        {
            ++pollCount;

            auto status = GeniusSDKGetProcessingStatus();

            if ( status.status == GENIUS_PR_STATUS_DISABLED )
            {
                CollectLogger()->error( "GeniusSDK processing disabled — cannot collect result" );
                return outcome::failure( Error::NetworkError );
            }

            if ( status.status == GENIUS_PR_STATUS_IDLE )
            {
                CollectLogger()->info( "GeniusSDK processing complete ({} polls, {}%)", pollCount, status.percentage );
                break;
            }

            std::this_thread::sleep_for( kPollInterval );
        }

        if ( std::chrono::steady_clock::now() >= deadline )
        {
            CollectLogger()->warn( "Result collection timed out for task {} after {} polls", taskId, pollCount );
            return outcome::failure( Error::BroadcastTimeout );
        }

        if ( m_impl->resultData_.empty() )
        {
            CollectLogger()->warn( "Empty result for task {} — processing completed but no data", taskId );
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
