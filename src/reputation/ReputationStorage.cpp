/**
 * @file       ReputationStorage.cpp
 * @brief      RocksDB-backed reputation persistence implementation
 * @date       2026-05-06
 * @author     Subaskar S (ssivakumar@gnus.ai)
 */

#include "ReputationStorage.hpp"
#include "common/Logging.hpp"

#include <sstream>
#include <stdexcept>
#include <unordered_map>

#ifdef GENIUS_HAS_ROCKSDB
#    include <rocksdb/db.h>
#    include <rocksdb/options.h>
#    include <rocksdb/slice.h>
#endif

namespace sgns::neoswarm::reputation
{
    namespace
    {
        auto StorageLogger()
        {
            return neoswarm::CreateLogger( "ReputationStorage" );
        }
    }

    // -----------------------------------------------------------------------
    // Serialization — simple CSV; replace with protobuf in production
    // -----------------------------------------------------------------------
    std::string ReputationStorage::Serialize( const NodeReputation &r )
    {
        std::ostringstream oss;
        oss << r.identity_key_     << ','
            << r.global_score_     << ','
            << r.math_score_       << ','
            << r.grammar_score_    << ','
            << r.latency_score_    << ','
            << r.consistency_score_ << ','
            << r.task_count_       << ','
            << r.last_updated_ms_;
        return oss.str();
    }

    NodeReputation ReputationStorage::Deserialize( const std::string &data )
    {
        NodeReputation     r;
        std::istringstream iss( data );
        std::string        token;
        auto               next = [&]() -> std::string
        {
            std::getline( iss, token, ',' );
            return token;
        };
        r.identity_key_      = next();
        r.global_score_      = std::stod( next() );
        r.math_score_        = std::stod( next() );
        r.grammar_score_     = std::stod( next() );
        r.latency_score_     = std::stod( next() );
        r.consistency_score_ = std::stod( next() );
        r.task_count_        = std::stoull( next() );
        r.last_updated_ms_   = std::stoull( next() );
        return r;
    }

    // -----------------------------------------------------------------------
    // Impl
    // -----------------------------------------------------------------------
    struct ReputationStorage::Impl
    {
#ifdef GENIUS_HAS_ROCKSDB
        rocksdb::DB     *db_      = nullptr;
        rocksdb::Options options_;
#else
        std::unordered_map<std::string, std::string> store_;
#endif
    };

    ReputationStorage::ReputationStorage( const std::string &db_path )
        : impl_( std::make_unique<Impl>() )
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
        impl_->options_.create_if_missing = true;
        rocksdb::Status status = rocksdb::DB::Open( impl_->options_, db_path_, &impl_->db_ );
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
        if ( impl_ && impl_->db_ )
        {
            delete impl_->db_;
            impl_->db_ = nullptr;
        }
#endif
        open_ = false;
    }

    // -----------------------------------------------------------------------
    // Put
    // -----------------------------------------------------------------------
    outcome::result<void> ReputationStorage::Put( const NodeReputation &rep )
    {
        if ( !open_ )
        {
            return outcome::failure( Error::StorageError );
        }
        std::string val = Serialize( rep );
#ifdef GENIUS_HAS_ROCKSDB
        auto status = impl_->db_->Put( rocksdb::WriteOptions(), rep.identity_key_, val );
        if ( !status.ok() )
        {
            return outcome::failure( Error::StorageError );
        }
#else
        impl_->store_[rep.identity_key_] = val;
#endif
        return outcome::success();
    }

    // -----------------------------------------------------------------------
    // Get
    // -----------------------------------------------------------------------
    outcome::result<NodeReputation> ReputationStorage::Get( const std::string &identity_key ) const
    {
        if ( !open_ )
        {
            return outcome::failure( Error::StorageError );
        }
#ifdef GENIUS_HAS_ROCKSDB
        std::string     val;
        rocksdb::Status status = impl_->db_->Get( rocksdb::ReadOptions(), identity_key, &val );
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
        auto it = impl_->store_.find( identity_key );
        if ( it == impl_->store_.end() )
        {
            return outcome::failure( Error::ReputationNotFound );
        }
        return outcome::success( Deserialize( it->second ) );
#endif
    }

    // -----------------------------------------------------------------------
    // Remove
    // -----------------------------------------------------------------------
    outcome::result<void> ReputationStorage::Remove( const std::string &identity_key )
    {
        if ( !open_ )
        {
            return outcome::failure( Error::StorageError );
        }
#ifdef GENIUS_HAS_ROCKSDB
        auto status = impl_->db_->Delete( rocksdb::WriteOptions(), identity_key );
        if ( !status.ok() )
        {
            return outcome::failure( Error::StorageError );
        }
#else
        impl_->store_.erase( identity_key );
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
        auto *it = impl_->db_->NewIterator( rocksdb::ReadOptions() );
        for ( it->SeekToFirst(); it->Valid(); it->Next() )
        {
            result.push_back( Deserialize( it->value().ToString() ) );
        }
        delete it;
#else
        for ( const auto &[k, v] : impl_->store_ )
        {
            result.push_back( Deserialize( v ) );
        }
#endif
        return outcome::success( std::move( result ) );
    }

} // namespace sgns::neoswarm::reputation
