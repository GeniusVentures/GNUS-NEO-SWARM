/**
 * @file       ReputationCRDT.cpp
 * @brief      LWW CRDT reputation synchronisation implementation
 * @date       2026-05-06
 * @author     Subaskar S (ssivakumar@gnus.ai)
 */

#include "ReputationCRDT.hpp"
#include "common/Logging.hpp"

#include <sstream>
#include <stdexcept>

namespace sgns::neoswarm::reputation
{
    namespace
    {
        auto CRDTLogger()
        {
            return neoswarm::CreateLogger( "ReputationCRDT" );
        }
    } // namespace

    // -----------------------------------------------------------------------
    // Merge
    // -----------------------------------------------------------------------
    void ReputationCRDT::Merge( const NodeReputation& remote )
    {
        std::lock_guard<std::mutex> lock( mutex_ );
        auto it = state_.find( remote.identity_key_ );
        if ( it == state_.end() )
        {
            state_[remote.identity_key_] = remote;
            CRDTLogger()->debug( "CRDT: new entry for {}", remote.identity_key_ );
            return;
        }

        NodeReputation& local = it->second;
        if ( remote.last_updated_ms_ > local.last_updated_ms_ )
        {
            CRDTLogger()->debug( "CRDT: updated {} (remote ts={} > local ts={})", remote.identity_key_,
                                 remote.last_updated_ms_, local.last_updated_ms_ );
            local = remote;
        }
    }

    // -----------------------------------------------------------------------
    // Get
    // -----------------------------------------------------------------------
    std::optional<NodeReputation> ReputationCRDT::Get( const std::string& identity_key ) const
    {
        std::lock_guard<std::mutex> lock( mutex_ );
        auto it = state_.find( identity_key );
        if ( it == state_.end() )
        {
            return std::nullopt;
        }
        return it->second;
    }

    // -----------------------------------------------------------------------
    // GetAll
    // -----------------------------------------------------------------------
    std::vector<NodeReputation> ReputationCRDT::GetAll() const
    {
        std::lock_guard<std::mutex> lock( mutex_ );
        std::vector<NodeReputation> result;
        result.reserve( state_.size() );
        for ( const auto& [k, v] : state_ )
        {
            result.push_back( v );
        }
        return result;
    }

    // -----------------------------------------------------------------------
    // Serialize
    // -----------------------------------------------------------------------
    std::string ReputationCRDT::Serialize() const
    {
        std::lock_guard<std::mutex> lock( mutex_ );
        std::ostringstream oss;
        for ( const auto& [k, r] : state_ )
        {
            oss << r.identity_key_ << ',' << r.global_score_ << ',' << r.math_score_ << ',' << r.grammar_score_ << ','
                << r.latency_score_ << ',' << r.consistency_score_ << ',' << r.task_count_ << ',' << r.last_updated_ms_
                << '\n';
        }
        return oss.str();
    }

    // -----------------------------------------------------------------------
    // DeserializeAndMerge
    // -----------------------------------------------------------------------
    void ReputationCRDT::DeserializeAndMerge( const std::string& data )
    {
        std::istringstream iss( data );
        std::string line;
        while ( std::getline( iss, line ) )
        {
            if ( line.empty() )
            {
                continue;
            }
            std::istringstream ls( line );
            std::string token;
            auto next = [&]() -> std::string
            {
                std::getline( ls, token, ',' );
                return token;
            };
            try
            {
                NodeReputation r;
                r.identity_key_ = next();
                r.global_score_ = std::stod( next() );
                r.math_score_ = std::stod( next() );
                r.grammar_score_ = std::stod( next() );
                r.latency_score_ = std::stod( next() );
                r.consistency_score_ = std::stod( next() );
                r.task_count_ = std::stoull( next() );
                r.last_updated_ms_ = std::stoull( next() );
                Merge( r );
            }
            catch ( const std::exception& e )
            {
                CRDTLogger()->warn( "CRDT deserialize error: {}", e.what() );
            }
        }
    }

} // namespace sgns::neoswarm::reputation
