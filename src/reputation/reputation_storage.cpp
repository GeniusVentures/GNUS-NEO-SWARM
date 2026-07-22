/**
 * @file       reputation_storage.cpp
 * @brief      RocksDB-backed reputation persistence implementation
 * @date       2026-05-06
 */

#include "reputation_storage.hpp"
#include "common/logging.hpp"

#include <rocksdb/db.h>
#include <rocksdb/options.h>
#include <rocksdb/slice.h>
#include <rocksdb/write_batch.h>

#include "proto/genius_reputation.pb.h"

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
    // Serialization — protobuf binary (genius_reputation.proto)
    // -----------------------------------------------------------------------
    std::string ReputationStorage::Serialize( const NodeReputation& r )
    {
        genius::reputation::NodeReputationProto proto;
        proto.set_identity_key( r.m_identityKey );
        proto.set_global_score( r.m_globalScore );
        proto.set_math_score( r.m_mathScore );
        proto.set_grammar_score( r.m_grammarScore );
        proto.set_latency_score( r.m_latencyScore );
        proto.set_consistency_score( r.m_consistencyScore );
        proto.set_task_count( r.m_taskCount );
        proto.set_last_updated_ms( r.m_lastUpdatedMs );
        return proto.SerializeAsString();
    }

    outcome::result<NodeReputation> ReputationStorage::Deserialize( const std::string& data )
    {
        NodeReputation r;
        genius::reputation::NodeReputationProto proto;
        if ( !proto.ParseFromString( data ) )
        {
            StorageLogger()->error( "Corrupt protobuf record — deserialization failed" );
            return outcome::failure( Error::StorageError );
        }
        r.m_identityKey = proto.identity_key();
        r.m_globalScore = proto.global_score();
        r.m_mathScore = proto.math_score();
        r.m_grammarScore = proto.grammar_score();
        r.m_latencyScore = proto.latency_score();
        r.m_consistencyScore = proto.consistency_score();
        r.m_taskCount = proto.task_count();
        r.m_lastUpdatedMs = proto.last_updated_ms();
        return outcome::success( r );
    }

    // -----------------------------------------------------------------------
    // Impl
    // -----------------------------------------------------------------------
    struct ReputationStorage::Impl
    {
        rocksdb::DB* m_db = nullptr;
        rocksdb::Options options_;

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
        m_impl->options_.create_if_missing = true;
        rocksdb::Status status = rocksdb::DB::Open( m_impl->options_, db_path_, &m_impl->m_db );
        if ( !status.ok() )
        {
            return outcome::failure( Error::StorageError );
        }
        StorageLogger()->info( "ReputationStorage opened: {}", db_path_ );

        open_ = true;
        return outcome::success();
    }

    // -----------------------------------------------------------------------
    // Close
    // -----------------------------------------------------------------------
    void ReputationStorage::Close()
    {
        if ( m_impl && m_impl->m_db )
        {
            delete m_impl->m_db;
            m_impl->m_db = nullptr;
        }
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
        rocksdb::WriteOptions opts;
        opts.sync = true;
        auto status = m_impl->m_db->Put( opts, rep.m_identityKey, val );
        if ( !status.ok() )
        {
            return outcome::failure( Error::StorageError );
        }

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
        std::string val;
        rocksdb::Status status = m_impl->m_db->Get( rocksdb::ReadOptions(), identity_key, &val );
        if ( status.IsNotFound() )
        {
            return outcome::failure( Error::ReputationNotFound );
        }
        if ( !status.ok() )
        {
            return outcome::failure( Error::StorageError );
        }
        return Deserialize( val );

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
        auto status = m_impl->m_db->Delete( rocksdb::WriteOptions(), identity_key );
        if ( !status.ok() )
        {
            return outcome::failure( Error::StorageError );
        }

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
        auto* it = m_impl->m_db->NewIterator( rocksdb::ReadOptions() );
        for ( it->SeekToFirst(); it->Valid(); it->Next() )
        {
            auto res = Deserialize( it->value().ToString() );
            if ( res.has_value() )
            {
                result.push_back( res.value() );
            }
        }
        delete it;

        return outcome::success( std::move( result ) );
    }

    // -----------------------------------------------------------------------
    // PutBatch — atomic multi-record write
    // -----------------------------------------------------------------------
    outcome::result<void> ReputationStorage::PutBatch( const std::vector<NodeReputation>& records )
    {
        if ( !open_ )
        {
            return outcome::failure( Error::StorageError );
        }
        rocksdb::WriteBatch batch;
        for ( const auto& rep : records )
        {
            batch.Put( rep.m_identityKey, Serialize( rep ) );
        }
        rocksdb::WriteOptions opts;
        opts.sync = true;
        auto status = m_impl->m_db->Write( opts, &batch );
        if ( !status.ok() )
        {
            return outcome::failure( Error::StorageError );
        }
        return outcome::success();
    }

} // namespace sgns::neoswarm::reputation
