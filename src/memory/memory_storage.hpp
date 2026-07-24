/**
 * @file       memory_storage.hpp
 * @brief      RocksDB-backed memory object persistence (GAML v1 — Phase 8)
 */

#ifndef NEOSWARM_MEMORY_MEMORYSTORAGE_HPP
#define NEOSWARM_MEMORY_MEMORYSTORAGE_HPP

#include "common/error.hpp"
#include "common/types.hpp"
#include <memory>
#include <string>
#include <vector>

namespace sgns::neoswarm::memory
{
    /**
     * @brief Persists CognitiveAsset memory objects to RocksDB.
     *
     * Uses the Pimpl idiom — header has ZERO RocksDB includes (D-15).
     * Key format: {entity}/{type}/{timestamp_ns}/{id} (D-14).
     */
    class MemoryStorage
    {
        public:
        struct Config
        {
            std::string m_dbPath = "./memory.db";
        };

        explicit MemoryStorage( const Config& cfg );
        ~MemoryStorage();

        outcome::result<void> Open();
        void Close();
        bool IsOpen() const
        {
            return m_open;
        }

        /// Persist a single CognitiveAsset (D-13)
        outcome::result<void> Put( const CognitiveAsset& obj );

        /// Atomically persist multiple CognitiveAssets
        outcome::result<void> PutBatch( const std::vector<CognitiveAsset>& objects );

        /// Prefix range scan — returns up to maxResults objects matching prefix
        outcome::result<std::vector<CognitiveAsset>> GetByPrefix(
            const std::string& prefix, int maxResults = 10 ) const;

        /// Retrieve by exact key
        outcome::result<CognitiveAsset> Get( const std::string& key ) const;

        private:
        struct Impl;
        std::unique_ptr<Impl> m_impl;
        Config m_cfg;
        bool m_open = false;

        static std::string BuildKey( const CognitiveAsset& obj );
        static std::string Serialize( const CognitiveAsset& obj );
        static outcome::result<CognitiveAsset> Deserialize( const std::string& data );
    };

} // namespace sgns::neoswarm::memory

#endif // NEOSWARM_MEMORY_MEMORYSTORAGE_HPP
