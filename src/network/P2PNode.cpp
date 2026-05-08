/**
 * @file       P2PNode.cpp
 * @brief      libp2p swarm node implementation
 * @date       2026-05-06
 * @author     Subaskar S (ssivakumar@gnus.ai)
 */

#include "P2PNode.hpp"
#include "common/Logging.hpp"

#include <atomic>
#include <nlohmann/json.hpp>

#ifdef GENIUS_HAS_LIBP2P
#    include <libp2p/host/basic_host/basic_host.hpp>
#    include <libp2p/protocol/gossip/gossip.hpp>
#    include <libp2p/multi/multiaddress.hpp>
#endif

namespace sgns::neoswarm::network
{
    namespace
    {
        constexpr char kTaskTopic[] = "genius/tasks/1.0.0";
        constexpr char kCRDTTopic[] = "genius/crdt/1.0.0";

        auto NetworkLogger()
        {
            return neoswarm::CreateLogger( "P2PNode" );
        }
    }

    struct P2PNode::Impl
    {
        std::string              listen_addr_;
        std::string              peer_id_;
        std::vector<std::string> peers_;
        std::atomic<bool>        running_{ false };
    };

    P2PNode::P2PNode( std::shared_ptr<security::NodeIdentity> identity )
        : impl_( std::make_unique<Impl>() )
        , identity_( std::move( identity ) )
        , cfg_( {} )
    {
    }

    P2PNode::P2PNode( std::shared_ptr<security::NodeIdentity> identity, Config cfg )
        : impl_( std::make_unique<Impl>() )
        , identity_( std::move( identity ) )
        , cfg_( std::move( cfg ) )
    {
    }

    P2PNode::~P2PNode()
    {
        Stop();
    }

    // -----------------------------------------------------------------------
    // Start
    // -----------------------------------------------------------------------
    outcome::result<void> P2PNode::Start()
    {
#ifdef GENIUS_HAS_LIBP2P
        NetworkLogger()->info( "P2PNode starting (libp2p)..." );
        // Full libp2p initialisation:
        // 1. Create BasicHost with Noise + Yamux
        // 2. Subscribe to kTaskTopic and kCRDTTopic via GossipSub
        // 3. Start mDNS discovery if cfg_.enable_mdns_
        // 4. Connect to bootstrap peer if cfg_.bootstrap_peer_ is set
#else
        NetworkLogger()->warn( "libp2p not compiled in — P2PNode running in stub mode" );
#endif

        impl_->peer_id_    = identity_ ? identity_->PeerId() : "stub-peer";
        impl_->listen_addr_ = cfg_.listen_addr_;
        impl_->running_.store( true );
        running_ = true;

        NetworkLogger()->info( "P2PNode started: peerId={} addr={}",
                               impl_->peer_id_,
                               impl_->listen_addr_ );
        return outcome::success();
    }

    // -----------------------------------------------------------------------
    // Stop
    // -----------------------------------------------------------------------
    void P2PNode::Stop()
    {
        if ( !running_ )
        {
            return;
        }
        impl_->running_.store( false );
        running_ = false;
        NetworkLogger()->info( "P2PNode stopped" );
    }

    std::string P2PNode::ListenAddress() const
    {
        return impl_->listen_addr_;
    }

    std::string P2PNode::PeerId() const
    {
        return impl_->peer_id_;
    }

    std::vector<std::string> P2PNode::ConnectedPeers() const
    {
        return impl_->peers_;
    }

    // -----------------------------------------------------------------------
    // BroadcastTask
    // -----------------------------------------------------------------------
    outcome::result<void> P2PNode::BroadcastTask( const Task &task )
    {
        if ( !running_ )
        {
            return outcome::failure( Error::NetworkError );
        }

        nlohmann::json j;
        j["id"]          = task.id_;
        j["prompt"]      = task.prompt_;
        j["mode"]        = static_cast<int>( task.mode_ );
        j["max_tokens"]  = task.max_tokens_;
        j["temperature"] = task.temperature_;
        std::string payload = j.dump();

        NetworkLogger()->debug( "Broadcasting task {} to {} peers",
                                task.id_,
                                impl_->peers_.size() );

#ifdef GENIUS_HAS_LIBP2P
        // gossip_->publish(kTaskTopic, payload);
#else
        // Stub: call local handler directly for single-process testing
        if ( task_handler_ )
        {
            Task t = task;
            task_handler_( t, impl_->peer_id_ );
        }
#endif
        return outcome::success();
    }

    // -----------------------------------------------------------------------
    // BroadcastCRDT
    // -----------------------------------------------------------------------
    outcome::result<void> P2PNode::BroadcastCRDT( const std::string &crdt_data )
    {
        if ( !running_ )
        {
            return outcome::failure( Error::NetworkError );
        }
        NetworkLogger()->debug( "Broadcasting CRDT update ({} bytes)", crdt_data.size() );
#ifdef GENIUS_HAS_LIBP2P
        // gossip_->publish(kCRDTTopic, crdt_data);
#else
        if ( crdt_handler_ )
        {
            crdt_handler_( crdt_data );
        }
#endif
        return outcome::success();
    }

} // namespace sgns::neoswarm::network
