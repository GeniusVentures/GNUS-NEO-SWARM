/**
 * @file       ResultAggregation.cpp
 * @brief      Swarm response aggregation implementation
 * @date       2026-05-06
 * @author     Subaskar S (ssivakumar@gnus.ai)
 */

#include "ResultAggregation.hpp"
#include "common/Logging.hpp"

namespace sgns::neoswarm::network
{
    namespace
    {
        auto AggregationLogger()
        {
            return neoswarm::CreateLogger( "ResultAggregation" );
        }
    } // namespace

    ResultAggregation::ResultAggregation()
        : cfg_( {} )
    {
    }
    ResultAggregation::ResultAggregation( Config cfg )
        : cfg_( std::move( cfg ) )
    {
    }

    // -----------------------------------------------------------------------
    // Submit
    // -----------------------------------------------------------------------
    void ResultAggregation::Submit( const NodeOutput& output )
    {
        std::lock_guard<std::mutex> lock( mutex_ );
        if ( results_.size() >= cfg_.max_responses_ )
        {
            return;
        }
        results_.push_back( output );
        AggregationLogger()->debug( "Received from {} ({}/{})", output.node_id_, results_.size(), cfg_.max_responses_ );
        if ( results_.size() >= cfg_.min_responses_ )
        {
            done_ = true;
            cv_.notify_all();
        }
    }

    // -----------------------------------------------------------------------
    // Collect
    // -----------------------------------------------------------------------
    outcome::result<std::vector<NodeOutput>> ResultAggregation::Collect()
    {
        std::unique_lock<std::mutex> lock( mutex_ );
        bool timed_out =
            !cv_.wait_for( lock, cfg_.timeout_, [this] { return done_ || results_.size() >= cfg_.max_responses_; } );

        if ( timed_out && results_.empty() )
        {
            return outcome::failure( Error::BROADCAST_TIMEOUT );
        }

        AggregationLogger()->info( "Collected {} responses (timeout={})", results_.size(), timed_out ? "yes" : "no" );
        return outcome::success( results_ );
    }

    // -----------------------------------------------------------------------
    // Reset
    // -----------------------------------------------------------------------
    void ResultAggregation::Reset()
    {
        std::lock_guard<std::mutex> lock( mutex_ );
        results_.clear();
        done_ = false;
    }

    // -----------------------------------------------------------------------
    // ResponseCount
    // -----------------------------------------------------------------------
    size_t ResultAggregation::ResponseCount() const
    {
        std::lock_guard<std::mutex> lock( mutex_ );
        return results_.size();
    }

} // namespace sgns::neoswarm::network
