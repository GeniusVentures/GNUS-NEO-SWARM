/**
 * @file       reputation_storage.hpp
 * @brief      RocksDB-backed reputation persistence (PTDS §4.2)
 * @date       2026-05-06
 */

#ifndef NEOSWARM_REPUTATION_REPUTATIONSTORAGE_HPP
#define NEOSWARM_REPUTATION_REPUTATIONSTORAGE_HPP

#include "node_reputation.hpp"
#include "common/error.hpp"
#include <memory>
#include <optional>
#include <string>
#include <vector>

namespace sgns::neoswarm::reputation
{
    /**
     * @brief Persists NodeReputation records to RocksDB.
     *        Falls back to an in-memory store when RocksDB is not compiled in.
     */
    class ReputationStorage
    {
        public:
        /**
         * @brief Construct storage pointing at the given database path.
         * @param db_path  Filesystem path for the RocksDB database directory.
         */
        explicit ReputationStorage( const std::string& db_path );
        ~ReputationStorage();

        /**
         * @brief Open (or create) the database.
         * @return outcome::success or StorageError.
         */
        outcome::result<void> Open();

        /// Close the database.
        void Close();

        /**
         * @brief Persist a reputation record.
         * @param rep  Record to store.
         * @return     outcome::success or StorageError.
         */
        outcome::result<void> Put( const NodeReputation& rep );

        /**
         * @brief Atomically persist multiple reputation records.
         * @param records  Records to store atomically.
         * @return         outcome::success or StorageError.
         */
        outcome::result<void> PutBatch( const std::vector<NodeReputation>& records );

        /**
         * @brief Retrieve a reputation record by identity key.
         * @param identity_key  Node identity key.
         * @return              NodeReputation or ReputationNotFound / StorageError.
         */
        outcome::result<NodeReputation> Get( const std::string& identity_key ) const;

        /**
         * @brief Delete a reputation record.
         * @param identity_key  Node identity key.
         * @return              outcome::success or StorageError.
         */
        outcome::result<void> Remove( const std::string& identity_key );

        /**
         * @brief Retrieve all stored reputation records.
         * @return  Vector of all records or StorageError.
         */
        outcome::result<std::vector<NodeReputation>> GetAll() const;

        /// @return True if the database is currently open.
        bool IsOpen() const
        {
            return open_;
        }

        private:
        struct Impl;
        std::unique_ptr<Impl> m_impl;
        std::string db_path_;
        bool open_ = false;

        static std::string Serialize( const NodeReputation& rep );
        static NodeReputation Deserialize( const std::string& data );
    };

} // namespace sgns::neoswarm::reputation

#endif // NEOSWARM_REPUTATION_REPUTATIONSTORAGE_HPP
