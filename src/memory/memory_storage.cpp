/**
 * @file       memory_storage.cpp
 * @brief      RocksDB-backed memory object persistence implementation (GAML v1)
 */

#include "memory_storage.hpp"
#include "common/logging.hpp"

#include <rocksdb/db.h>
#include <rocksdb/options.h>
#include <rocksdb/slice.h>
#include <rocksdb/write_batch.h>

#include <nlohmann/json.hpp>

namespace sgns::neoswarm::memory
{
    namespace
    {
        auto StorageLogger()
        {
            return neoswarm::CreateLogger( "MemoryStorage" );
        }
    } // namespace

    // -----------------------------------------------------------------------
    // BuildKey — key format: {entity}/{type}/{timestamp_ns}/{id} (D-14)
    // Entity is sanitized: '/' replaced with '_' (T-08-04 mitigation)
    // -----------------------------------------------------------------------
    std::string MemoryStorage::BuildKey( const CognitiveAsset& obj )
    {
        // Sanitize entity — replace '/' with '_' (per RESEARCH.md Pitfall 2)
        std::string safeEntity = obj.m_entity;
        for ( auto& c : safeEntity )
        {
            if ( c == '/' )
            {
                c = '_';
            }
        }
        return safeEntity + "/" +
               std::to_string( static_cast<int>( obj.m_type ) ) + "/" +
               std::to_string( obj.m_timestamp ) + "/" +
               obj.m_id;
    }

    // -----------------------------------------------------------------------
    // Serialize — JSON serialization of all 9 CognitiveAsset fields
    // -----------------------------------------------------------------------
    std::string MemoryStorage::Serialize( const CognitiveAsset& obj )
    {
        nlohmann::json j;
        j["id"] = obj.m_id;
        j["entity"] = obj.m_entity;
        j["type"] = static_cast<int>( obj.m_type );
        j["payload"] = obj.m_payload;
        j["timestamp"] = obj.m_timestamp;
        j["source_node"] = obj.m_sourceNode;
        j["confidence"] = obj.m_confidence;
        j["provenance"] = obj.m_provenance;
        j["trust_class"] = static_cast<int>( obj.m_trustClass );
        return j.dump();
    }

    // -----------------------------------------------------------------------
    // Deserialize — JSON deserialization with exception safety (T-08-05)
    // -----------------------------------------------------------------------
    outcome::result<CognitiveAsset> MemoryStorage::Deserialize( const std::string& data )
    {
        try
        {
            auto j = nlohmann::json::parse( data );
            CognitiveAsset obj;
            obj.m_id = j.value( "id", "" );
            obj.m_entity = j.value( "entity", "" );
            obj.m_type = static_cast<MemoryObjectType>( j.value( "type", 0 ) );
            obj.m_payload = j.value( "payload", nlohmann::json::object() );
            obj.m_timestamp = j.value( "timestamp", int64_t( 0 ) );
            obj.m_sourceNode = j.value( "source_node", "" );
            obj.m_confidence = j.value( "confidence", 0.0f );
            obj.m_provenance = j.value( "provenance", 0.0f );
            obj.m_trustClass = static_cast<TrustClass>( j.value( "trust_class", 0 ) );
            return outcome::success( std::move( obj ) );
        }
        catch ( const nlohmann::json::exception& e )
        {
            StorageLogger()->error( "JSON deserialization failed: {}", e.what() );
            return outcome::failure( Error::StorageError );
        }
    }

    // -----------------------------------------------------------------------
    // Impl — RocksDB internals hidden behind Pimpl
    // -----------------------------------------------------------------------
    struct MemoryStorage::Impl
    {
        rocksdb::DB* m_db = nullptr;
        rocksdb::Options m_options;
    };

    // -----------------------------------------------------------------------
    // Constructor / Destructor
    // -----------------------------------------------------------------------
    MemoryStorage::MemoryStorage( const Config& cfg )
        : m_impl( std::make_unique<Impl>() )
        , m_cfg( cfg )
    {
    }

    MemoryStorage::~MemoryStorage()
    {
        Close();
    }

    // -----------------------------------------------------------------------
    // Open — create_if_missing, return StorageError on failure (D-20)
    // -----------------------------------------------------------------------
    outcome::result<void> MemoryStorage::Open()
    {
        m_impl->m_options.create_if_missing = true;
        rocksdb::Status status = rocksdb::DB::Open( m_impl->m_options, m_cfg.m_dbPath, &m_impl->m_db );
        if ( !status.ok() )
        {
            StorageLogger()->error( "MemoryStorage open failed: {}", status.ToString() );
            return outcome::failure( Error::StorageError );
        }
        StorageLogger()->info( "MemoryStorage opened: {}", m_cfg.m_dbPath );
        m_open = true;
        return outcome::success();
    }

    // -----------------------------------------------------------------------
    // Close — safe teardown with null guards
    // -----------------------------------------------------------------------
    void MemoryStorage::Close()
    {
        if ( m_impl && m_impl->m_db )
        {
            delete m_impl->m_db;
            m_impl->m_db = nullptr;
        }
        m_open = false;
    }

    // -----------------------------------------------------------------------
    // Put — single record write with sync for crash safety (T-08-06)
    // -----------------------------------------------------------------------
    outcome::result<void> MemoryStorage::Put( const CognitiveAsset& obj )
    {
        if ( !m_open )
        {
            return outcome::failure( Error::StorageError );
        }
        std::string key = BuildKey( obj );
        std::string val = Serialize( obj );
        rocksdb::WriteOptions opts;
        opts.sync = true;
        auto status = m_impl->m_db->Put( opts, key, val );
        if ( !status.ok() )
        {
            return outcome::failure( Error::StorageError );
        }
        return outcome::success();
    }

    // -----------------------------------------------------------------------
    // Get — exact key lookup with IsNotFound → MemoryNotFound (D-20)
    // -----------------------------------------------------------------------
    outcome::result<CognitiveAsset> MemoryStorage::Get( const std::string& key ) const
    {
        if ( !m_open )
        {
            return outcome::failure( Error::StorageError );
        }
        std::string val;
        rocksdb::Status status = m_impl->m_db->Get( rocksdb::ReadOptions(), key, &val );
        if ( status.IsNotFound() )
        {
            return outcome::failure( Error::MemoryNotFound );
        }
        if ( !status.ok() )
        {
            return outcome::failure( Error::StorageError );
        }
        return Deserialize( val );
    }

    // -----------------------------------------------------------------------
    // PutBatch — atomic multi-record write via WriteBatch (sync=true)
    // -----------------------------------------------------------------------
    outcome::result<void> MemoryStorage::PutBatch( const std::vector<CognitiveAsset>& objects )
    {
        if ( !m_open )
        {
            return outcome::failure( Error::StorageError );
        }
        rocksdb::WriteBatch batch;
        for ( const auto& obj : objects )
        {
            batch.Put( BuildKey( obj ), Serialize( obj ) );
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

    // -----------------------------------------------------------------------
    // GetByPrefix — prefix range scan using C++17 compare() (not starts_with)
    // -----------------------------------------------------------------------
    outcome::result<std::vector<CognitiveAsset>> MemoryStorage::GetByPrefix(
        const std::string& prefix, int maxResults ) const
    {
        if ( !m_open )
        {
            return outcome::failure( Error::StorageError );
        }
        std::vector<CognitiveAsset> results;
        auto* it = m_impl->m_db->NewIterator( rocksdb::ReadOptions() );

        for ( it->Seek( prefix );
              it->Valid() &&
              it->key().ToString().compare( 0, prefix.size(), prefix ) == 0 &&
              static_cast<int>( results.size() ) < maxResults;
              it->Next() )
        {
            auto obj = Deserialize( it->value().ToString() );
            if ( obj.has_value() )
            {
                results.push_back( std::move( obj.value() ) );
            }
        }
        delete it;
        return outcome::success( std::move( results ) );
    }

} // namespace sgns::neoswarm::memory
