/**
 * @file       P2PNode.hpp
 * @brief      libp2p swarm node (PTDS §4.2)
 * @date       2026-05-06
 * @author     Subaskar S (ssivakumar@gnus.ai)
 */

#ifndef NEOSWARM_NETWORK_P2PNODE_HPP_
#define NEOSWARM_NETWORK_P2PNODE_HPP_

#include "common/Types.hpp"
#include "common/Error.hpp"
#include "security/NodeIdentity.hpp"
#include <functional>
#include <memory>
#include <string>
#include <vector>

namespace sgns::neoswarm::network
{
    /**
     * @brief Manages a libp2p host for swarm task broadcasting and CRDT sync.
     *
     * Uses Noise protocol for encryption and Yamux for stream multiplexing.
     * Falls back to a local stub when libp2p is not compiled in.
     */
    class P2PNode
    {
    public:
        struct Config
        {
            std::string listen_addr_     = "/ip4/0.0.0.0/tcp/0";
            std::string bootstrap_peer_  = "";    ///< optional bootstrap peer multiaddr
            bool        enable_mdns_     = true;  ///< local peer discovery
            bool        enable_kademlia_ = true;
            int         max_peers_       = 50;
        };

        using TaskHandler = std::function<void( const Task &task, const std::string &from_peer )>;
        using CRDTHandler = std::function<void( const std::string &crdt_data )>;

        P2PNode( std::shared_ptr<security::NodeIdentity> identity, Config cfg );
        explicit P2PNode( std::shared_ptr<security::NodeIdentity> identity );
        ~P2PNode();

        /**
         * @brief Start the libp2p host and begin listening.
         * @return outcome::success or NetworkError.
         */
        outcome::result<void> Start();

        /// Stop the host and disconnect all peers.
        void Stop();

        /// @return True if the node is currently running.
        bool IsRunning() const
        {
            return running_;
        }

        /// @return Our listen multiaddress (available after Start()).
        std::string ListenAddress() const;

        /// @return Our peer ID string.
        std::string PeerId() const;

        /**
         * @brief Register a handler for incoming task broadcasts.
         * @param handler  Callback invoked when a task is received from a peer.
         */
        void OnTask( TaskHandler handler )
        {
            task_handler_ = std::move( handler );
        }

        /**
         * @brief Register a handler for incoming CRDT sync messages.
         * @param handler  Callback invoked when a CRDT update is received.
         */
        void OnCRDT( CRDTHandler handler )
        {
            crdt_handler_ = std::move( handler );
        }

        /**
         * @brief Broadcast a task to all connected peers via GossipSub.
         * @param task  Task to broadcast.
         * @return      outcome::success or NetworkError.
         */
        outcome::result<void> BroadcastTask( const Task &task );

        /**
         * @brief Broadcast a CRDT state update to all peers.
         * @param crdt_data  Serialised CRDT state.
         * @return           outcome::success or NetworkError.
         */
        outcome::result<void> BroadcastCRDT( const std::string &crdt_data );

        /**
         * @brief Get the list of currently connected peer IDs.
         * @return  Vector of peer ID strings.
         */
        std::vector<std::string> ConnectedPeers() const;

    private:
        struct Impl;
        std::unique_ptr<Impl>                   impl_;
        std::shared_ptr<security::NodeIdentity> identity_;
        Config                                  cfg_;
        bool                                    running_      = false;
        TaskHandler                             task_handler_;
        CRDTHandler                             crdt_handler_;
    };

} // namespace sgns::neoswarm::network

#endif // NEOSWARM_NETWORK_P2PNODE_HPP_
