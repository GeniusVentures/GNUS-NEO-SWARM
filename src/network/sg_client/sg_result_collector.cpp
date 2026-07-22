/**
 * @file       sg_result_collector.cpp
 * @brief      GeniusSDK processing status polling with exponential backoff
 * @date       2026-05-28
 */

#include "sg_result_collector.hpp"
#include "common/logging.hpp"
#include "GeniusSDK.h"
#include <future>
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
        SGResultCollectorConfig m_cfg;

        explicit Impl( SGResultCollectorConfig cfg )
            : m_cfg( std::move( cfg ) )
        {
        }
    };

    SGResultCollector::SGResultCollector( SGResultCollectorConfig cfg )
        : m_impl( std::make_unique<Impl>( std::move( cfg ) ) )
    {
    }

    outcome::result<std::vector<uint8_t>> SGResultCollector::PollForResult( std::chrono::seconds timeout )
    {
        CollectLogger()->info( "Polling GeniusSDK for result (timeout={}s)", timeout.count() );

        auto deadline = std::chrono::steady_clock::now() + timeout;
        std::chrono::milliseconds backoff{ 100 };
        constexpr std::chrono::milliseconds kMaxBackoff{ 1000 };
        GeniusProcessingStatus_t lastStatus = GENIUS_PR_STATUS_IDLE;
        bool wasProcessing = false;

        while ( std::chrono::steady_clock::now() < deadline )
        {
            // TODO: SDK team — GetProcessingStatus returns global node status,
            // not per-task. Need GeniusSDKGetProcessingStatus(task_id) API.
            GeniusProcessingStatusInfo info = GeniusSDKGetProcessingStatus();
            GeniusProcessingStatus_t status = info.status;

            if ( status == GENIUS_PR_STATUS_IDLE && wasProcessing )
            {
                CollectLogger()->info( "Processing complete (percentage={:.1f}%)",
                                       static_cast<double>( info.percentage ) );
                // TODO: SDK team — no result-retrieval API yet.
                // Results flow via transaction layer. Retrieve from GetInTransactions() when available.
                CollectLogger()->warn( "Result not retrieved — SDK result API pending" );
                return outcome::success( std::vector<uint8_t>{} );
            }

            if ( status == GENIUS_PR_STATUS_DISABLED )
            {
                CollectLogger()->error( "SDK processing disabled" );
                return outcome::failure( Error::NetworkError );
            }

            wasProcessing = ( status == GENIUS_PR_STATUS_PROCESSING );

            if ( status != lastStatus )
            {
                CollectLogger()->debug( "SDK status: {} ({}%)", static_cast<int>( status ),
                                        static_cast<double>( info.percentage ) );
                lastStatus = status;
            }

            std::this_thread::sleep_for( backoff );
            backoff = std::min( backoff * 2, kMaxBackoff );
        }

        CollectLogger()->warn( "Polling timed out after {}s", timeout.count() );
        return outcome::failure( Error::BroadcastTimeout );
    }

    outcome::result<std::vector<uint8_t>> SGResultCollector::PollForResult()
    {
        return PollForResult( m_impl->m_cfg.m_resultTimeout );
    }

    std::future<outcome::result<std::vector<uint8_t>>> SGResultCollector::PollForResultAsync(
        std::chrono::seconds timeout )
    {
        return std::async( std::launch::async, [ this, timeout ]() { return PollForResult( timeout ); } );
    }

    std::future<outcome::result<std::vector<uint8_t>>> SGResultCollector::PollForResultAsync()
    {
        return PollForResultAsync( m_impl->m_cfg.m_resultTimeout );
    }

    SGResultCollector::~SGResultCollector() = default;

} // namespace sgns::neoswarm::network