/**
 * @file       reputation_crdt.hpp
 * @brief      Last-Write-Wins CRDT for reputation synchronisation (PTDS §4.2)
 * @date       2026-05-06
 * @author     Subaskar S (ssivakumar@gnus.ai)
 */

#ifndef NEOSWARM_REPUTATION_REPUTATIONCRDT_HPP
#define NEOSWARM_REPUTATION_REPUTATIONCRDT_HPP

#include "node_reputation.hpp"
#include <mutex>
#include <optional>
#include <string>
#include <unordered_map>
#include <vector>

namespace sgns::neoswarm::reputation
{
    /**
     * @brief Last-Write-Wins Register per node (PTDS §4.2).
     *
     * Merge rule: keep the entry with the highest m_lastUpdatedMs timestamp.
     * Designed to be replicated across nodes via libp2p GossipSub.
     */
    class ReputationCRDT
    {
        public:
        /**
         * @brief Apply a remote reputation update (merge).
         * @param remote  Reputation record received from a peer.
         */
        void Merge( const NodeReputation& remote );

        /**
         * @brief Get the current merged state for a node.
         * @param identity_key  Node identity key.
         * @return              NodeReputation if known, std::nullopt otherwise.
         */
        std::optional<NodeReputation> Get( const std::string& identity_key ) const;

        /**
         * @brief Get all merged reputation records.
         * @return  Vector of all known records.
         */
        std::vector<NodeReputation> GetAll() const;

        /**
         * @brief Serialise the full CRDT state for network transmission.
         * @return  CSV-encoded state string.
         */
        std::string Serialize() const;

        /**
         * @brief Deserialise and merge a received CRDT state.
         * @param data  CSV-encoded state string from a peer.
         */
        void DeserializeAndMerge( const std::string& data );

        private:
        mutable std::mutex m_mutex;
        std::unordered_map<std::string, NodeReputation> state_; ///< key = m_identityKey
    };

} // namespace sgns::neoswarm::reputation

#endif // NEOSWARM_REPUTATION_REPUTATIONCRDT_HPP
