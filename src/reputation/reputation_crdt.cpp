/**
 * @file       reputation_crdt.cpp
 * @brief      LWW CRDT reputation synchronisation implementation
 * @date       2026-05-06
 */

#include "reputation_crdt.hpp"
#include "common/logging.hpp"

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
        std::lock_guard<std::mutex> lock( m_mutex );
        auto it = state_.find( remote.m_identityKey );
        if ( it == state_.end() )
        {
            state_[remote.m_identityKey] = remote;
            CRDTLogger()->debug( "CRDT: new entry for {}", remote.m_identityKey );
            return;
        }

        NodeReputation& local = it->second;
        if ( remote.m_lastUpdatedMs > local.m_lastUpdatedMs )
        {
            CRDTLogger()->debug( "CRDT: updated {} (remote ts={} > local ts={})", remote.m_identityKey,
                                 remote.m_lastUpdatedMs, local.m_lastUpdatedMs );
            local = remote;
        }
    }

    // -----------------------------------------------------------------------
    // Get
    // -----------------------------------------------------------------------
    std::optional<NodeReputation> ReputationCRDT::Get( const std::string& identity_key ) const
    {
        std::lock_guard<std::mutex> lock( m_mutex );
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
        std::lock_guard<std::mutex> lock( m_mutex );
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
        std::lock_guard<std::mutex> lock( m_mutex );
        std::ostringstream oss;
        for ( const auto& [k, r] : state_ )
        {
            oss << r.m_identityKey << ',' << r.m_globalScore << ',' << r.m_mathScore << ',' << r.m_grammarScore << ','
                << r.m_latencyScore << ',' << r.m_consistencyScore << ',' << r.m_taskCount << ',' << r.m_lastUpdatedMs
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
                r.m_identityKey = next();
                r.m_globalScore = std::stod( next() );
                r.m_mathScore = std::stod( next() );
                r.m_grammarScore = std::stod( next() );
                r.m_latencyScore = std::stod( next() );
                r.m_consistencyScore = std::stod( next() );
                r.m_taskCount = std::stoull( next() );
                r.m_lastUpdatedMs = std::stoull( next() );
                Merge( r );
            }
            catch ( const std::exception& e )
            {
                CRDTLogger()->warn( "CRDT deserialize error: {}", e.what() );
            }
        }
    }

} // namespace sgns::neoswarm::reputation
