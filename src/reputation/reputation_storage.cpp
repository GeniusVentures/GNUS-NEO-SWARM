/**
 * @file       reputation_storage.cpp
 * @brief      RocksDB-backed reputation persistence implementation
 * @date       2026-05-06
 * @author     Subaskar S (ssivakumar@gnus.ai)
 */

#include "reputation_storage.hpp"
#include "common/logging.hpp"

#include <nlohmann/json.hpp>
#include <sstream>
#include <stdexcept>
#include <unordered_map>

#ifdef GENIUS_HAS_ROCKSDB
#include <rocksdb/db.h>
#include <rocksdb/options.h>
#include <rocksdb/slice.h>
#endif

namespace sgns::neoswarm::reputation
{
    namespace
    {
        auto StorageLogger()
        {
            return neoswarm::CreateLogger( "ReputationStorage" );
        }
    } // namespace

    // -----------------------------------------------------------------------
    // Serialization — JSON (nlohmann/json)
    // -----------------------------------------------------------------------
    std::string ReputationStorage::Serialize( const NodeReputation& r )
    {
        nlohmann::json j;
        j["identity_key"] = r.identity_key_;
        j["global_score"] = r.global_score_;
        j["math_score"] = r.math_score_;
        j["grammar_score"] = r.grammar_score_;
        j["latency_score"] = r.latency_score_;
        j["consistency_score"] = r.consistency_score_;
        j["task_count"] = r.task_count_;
        j["last_updated_ms"] = r.last_updated_ms_;
        return j.dump();
    }

    NodeReputation ReputationStorage::Deserialize( const std::string& data )
    {
        NodeReputation r;
        try
        {
            nlohmann::json j = nlohmann::json::parse( data );
            r.identity_key_ = j.value( "identity_key", "" );
            r.global_score_ = j.value( "global_score", 0.0 );
            r.math_score_ = j.value( "math_score", 0.0 );
            r.grammar_score_ = j.value( "grammar_score", 0.0 );
            r.latency_score_ = j.value( "latency_score", 0.0 );
            r.consistency_score_ = j.value( "consistency_score", 0.0 );
            r.task_count_ = j.value( "task_count", 0ULL );
            r.last_updated_ms_ = j.value( "last_updated_ms", 0ULL );
        }
        catch ( const std::exception& e )
        {
            StorageLogger()->error( "Corrupt reputation record, skipping: {}", e.what() );
            r.identity_key_ = "";
        }
        return r;
    }

    // -----------------------------------------------------------------------
    // Impl
    // -----------------------------------------------------------------------
    struct ReputationStorage::Impl
    {
#ifdef GENIUS_HAS_ROCKSDB
        rocksdb::DB* db_ = nullptr;
        rocksdb::Options options_;
#else
        std::unordered_map<std::string, std::string> store_;
#endif
    };

    ReputationStorage::ReputationStorage( const std::string& db_path )
        : m_impl( std::make_unique<Impl>() )
        , db_path_( db_path )
    {
    }

    ReputationStorage::~ReputationStorage()
    {
        Close();
    }

    // -----------------------------------------------------------------------
    // Open
    // -----------------------------------------------------------------------
    outcome::result<void> ReputationStorage::Open()
    {
#ifdef GENIUS_HAS_ROCKSDB
        m_impl->options_.create_if_missing = true;
        rocksdb::Status status = rocksdb::DB::Open( m_impl->options_, db_path_, &m_impl->db_ );
        if ( !status.ok() )
        {
            return outcome::failure( Error::StorageError );
        }
        StorageLogger()->info( "ReputationStorage opened: {}", db_path_ );
#else
        StorageLogger()->warn( "RocksDB not compiled in — using in-memory reputation store" );
#endif
        open_ = true;
        return outcome::success();
    }

    // -----------------------------------------------------------------------
    // Close
    // -----------------------------------------------------------------------
    void ReputationStorage::Close()
    {
#ifdef GENIUS_HAS_ROCKSDB
        if ( m_impl && m_impl->db_ )
        {
            delete m_impl->db_;
            m_impl->db_ = nullptr;
        }
#endif
        open_ = false;
    }

    // -----------------------------------------------------------------------
    // Put
    // -----------------------------------------------------------------------
    outcome::result<void> ReputationStorage::Put( const NodeReputation& rep )
    {
        if ( !open_ )
        {
            return outcome::failure( Error::StorageError );
        }
        std::string val = Serialize( rep );
#ifdef GENIUS_HAS_ROCKSDB
        auto status = m_impl->db_->Put( rocksdb::WriteOptions(), rep.identity_key_, val );
        if ( !status.ok() )
        {
            return outcome::failure( Error::StorageError );
        }
#else
        m_impl->store_[rep.identity_key_] = val;
#endif
        return outcome::success();
    }

    // -----------------------------------------------------------------------
    // Get
    // -----------------------------------------------------------------------
    outcome::result<NodeReputation> ReputationStorage::Get( const std::string& identity_key ) const
    {
        if ( !open_ )
        {
            return outcome::failure( Error::StorageError );
        }
#ifdef GENIUS_HAS_ROCKSDB
        std::string val;
        rocksdb::Status status = m_impl->db_->Get( rocksdb::ReadOptions(), identity_key, &val );
        if ( status.IsNotFound() )
        {
            return outcome::failure( Error::ReputationNotFound );
        }
        if ( !status.ok() )
        {
            return outcome::failure( Error::StorageError );
        }
        return outcome::success( Deserialize( val ) );
#else
        auto it = m_impl->store_.find( identity_key );
        if ( it == m_impl->store_.end() )
        {
            return outcome::failure( Error::ReputationNotFound );
        }
        return outcome::success( Deserialize( it->second ) );
#endif
    }

    // -----------------------------------------------------------------------
    // Remove
    // -----------------------------------------------------------------------
    outcome::result<void> ReputationStorage::Remove( const std::string& identity_key )
    {
        if ( !open_ )
        {
            return outcome::failure( Error::StorageError );
        }
#ifdef GENIUS_HAS_ROCKSDB
        auto status = m_impl->db_->Delete( rocksdb::WriteOptions(), identity_key );
        if ( !status.ok() )
        {
            return outcome::failure( Error::StorageError );
        }
#else
        m_impl->store_.erase( identity_key );
#endif
        return outcome::success();
    }

    // -----------------------------------------------------------------------
    // GetAll
    // -----------------------------------------------------------------------
    outcome::result<std::vector<NodeReputation>> ReputationStorage::GetAll() const
    {
        if ( !open_ )
        {
            return outcome::failure( Error::StorageError );
        }
        std::vector<NodeReputation> result;
#ifdef GENIUS_HAS_ROCKSDB
        auto* it = m_impl->db_->NewIterator( rocksdb::ReadOptions() );
        for ( it->SeekToFirst(); it->Valid(); it->Next() )
        {
            result.push_back( Deserialize( it->value().ToString() ) );
        }
        delete it;
#else
        for ( const auto& [k, v] : m_impl->store_ )
        {
            result.push_back( Deserialize( v ) );
        }
#endif
        return outcome::success( std::move( result ) );
    }

} // namespace sgns::neoswarm::reputation
