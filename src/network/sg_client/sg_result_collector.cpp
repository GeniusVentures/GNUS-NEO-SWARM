/**
 * @file       sg_result_collector.cpp
 * @brief      Timeout-bounded result collection via GeniusSDK polling with exponential backoff
 * @date       2026-05-28
 */

#include "sg_result_collector.hpp"
#include "sg_message_authenticator.hpp"
#include "common/logging.hpp"
#include "GeniusSDK.h"
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
        SGMessageAuthenticator& m_authenticator;
        SGResultCollectorConfig m_cfg;

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
        CollectLogger()->info( "Polling GeniusSDK for result on task {} (timeout={}s)", taskId, timeout.count() );

        auto deadline = std::chrono::steady_clock::now() + timeout;
        std::chrono::milliseconds backoff{ 100 }; // Start at 100ms (per D-06)
        constexpr std::chrono::milliseconds kMaxBackoff{ 1000 }; // Cap at 1s
        GeniusProcessingStatus_t lastStatus = GENIUS_PR_STATUS_IDLE;
        bool wasProcessing = false;

        while ( std::chrono::steady_clock::now() < deadline )
        {
            GeniusProcessingStatusInfo info = GeniusSDKGetProcessingStatus();
            GeniusProcessingStatus_t status = info.status;

            // Per D-07: completion = transition from PROCESSING to IDLE
            if ( status == GENIUS_PR_STATUS_IDLE && wasProcessing )
            {
                CollectLogger()->info( "Task {} processing complete (percentage={:.1f}%)", taskId,
                                       static_cast<double>( info.percentage ) );
                // D-08: SDK has no result retrieval API — log and return empty
                CollectLogger()->warn( "Result retrieval not available — SDK team roadmap item" );
                return outcome::success( std::vector<uint8_t>{} );
            }

            if ( status == GENIUS_PR_STATUS_DISABLED )
            {
                CollectLogger()->error( "SDK processing disabled for task {}", taskId );
                return outcome::failure( Error::NetworkError );
            }

            wasProcessing = ( status == GENIUS_PR_STATUS_PROCESSING );

            if ( status != lastStatus )
            {
                CollectLogger()->debug( "Task {} SDK status: {} ({}%)", taskId,
                                        static_cast<int>( status ),
                                        static_cast<double>( info.percentage ) );
                lastStatus = status;
            }

            std::this_thread::sleep_for( backoff );
            backoff = std::min( backoff * 2, kMaxBackoff ); // Exponential growth capped at 1s
        }

        CollectLogger()->warn( "Result collection timed out for task {} after {}s", taskId, timeout.count() );
        return outcome::failure( Error::BroadcastTimeout );
    }

    outcome::result<std::vector<uint8_t>> SGResultCollector::WaitForResult( const std::string& taskId )
    {
        return WaitForResult( taskId, m_impl->m_cfg.result_m_timeout );
    }

    SGResultCollector::~SGResultCollector() = default;

} // namespace sgns::neoswarm::network
