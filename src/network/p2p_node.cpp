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
#include <libp2p/host/basic_host/basic_host.hpp>
#include <libp2p/injector/host_injector.hpp>
#include <libp2p/multi/multiaddress.hpp>
#include <libp2p/protocol/gossip/gossip.hpp>
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
    } // namespace

    struct P2PNode::Impl
    {
        std::string listen_addr_;
        std::string peer_id_;
        std::vector<std::string> peers_;
        std::atomic<bool> running_{ false };

#ifdef GENIUS_HAS_LIBP2P
        std::shared_ptr<libp2p::Host> host_;
        std::shared_ptr<libp2p::protocol::gossip::Gossip> gossip_;
        std::shared_ptr<libp2p::peer::IdentityManager> id_mgr_;

        // Subscription ownership — heap-allocated to avoid needing the
        // Subscription constructor/destructor symbols at link time.
        struct GossipSubs
        {
            libp2p::protocol::Subscription task_sub;
            libp2p::protocol::Subscription crdt_sub;
        };
        std::unique_ptr<GossipSubs> subs_;
#endif
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

        try
        {
            // 1. Create host with full libp2p stack via Boost.DI injector.
            //    makeNetworkInjector internally generates keys and creates all providers.
            auto injector = libp2p::injector::makeHostInjector();
            impl_->host_ = injector.template create<std::shared_ptr<libp2p::Host>>();
            impl_->id_mgr_ = injector.template create<std::shared_ptr<libp2p::peer::IdentityManager>>();

            // 2. Create GossipSub protocol using DI-provided components
            auto scheduler = injector.template create<std::shared_ptr<libp2p::basic::Scheduler>>();
            auto crypto_provider = injector.template create<std::shared_ptr<libp2p::crypto::CryptoProvider>>();
            auto key_marshaller =
                injector.template create<std::shared_ptr<libp2p::crypto::marshaller::KeyMarshaller>>();
            impl_->gossip_ = libp2p::protocol::gossip::create( scheduler, impl_->host_, impl_->id_mgr_, crypto_provider,
                                                               key_marshaller, libp2p::protocol::gossip::Config{} );

            // 3. Subscribe to task and CRDT topics
            impl_->subs_ = std::make_unique<Impl::GossipSubs>();
            impl_->subs_->task_sub = impl_->gossip_->subscribe(
                { kTaskTopic },
                [this]( libp2p::protocol::gossip::Gossip::SubscriptionData sub_data )
                {
                    if ( sub_data && task_handler_ )
                    {
                        const auto& msg = sub_data.value();
                        auto json =
                            nlohmann::json::parse( std::string( msg.data.begin(), msg.data.end() ), nullptr, false );
                        if ( !json.is_discarded() )
                        {
                            Task t;
                            t.id_ = json.value( "id", "" );
                            t.prompt_ = json.value( "prompt", "" );
                            t.mode_ = static_cast<ExecutionMode>( json.value( "mode", 0 ) );
                            t.max_tokens_ = json.value( "max_tokens", 512U );
                            t.temperature_ = json.value( "temperature", 0.7f );
                            task_handler_( t, impl_->peer_id_ );
                        }
                    }
                } );

            impl_->subs_->crdt_sub =
                impl_->gossip_->subscribe( { kCRDTTopic },
                                           [this]( libp2p::protocol::gossip::Gossip::SubscriptionData sub_data )
                                           {
                                               if ( sub_data && crdt_handler_ )
                                               {
                                                   const auto& msg = sub_data.value();
                                                   crdt_handler_( std::string( msg.data.begin(), msg.data.end() ) );
                                               }
                                           } );

            // 4. Listen on configured address
            auto listen_ma = libp2p::multi::Multiaddress::create( cfg_.listen_addr_.empty() ? "/ip4/0.0.0.0/tcp/0"
                                                                                            : cfg_.listen_addr_ );
            if ( listen_ma )
            {
                (void)impl_->host_->listen( listen_ma.value() );
            }

            // 5. Start the host and gossip
            impl_->host_->start();
            impl_->gossip_->start();

            impl_->peer_id_ = impl_->host_->getId().toBase58();
            impl_->listen_addr_ = cfg_.listen_addr_;
            impl_->running_.store( true );
            running_ = true;

            NetworkLogger()->info( "P2PNode started (libp2p): peerId={}", impl_->peer_id_ );
        }
        catch ( const std::exception& e )
        {
            NetworkLogger()->error( "P2PNode start failed: {}", e.what() );
            return outcome::failure( Error::NetworkError );
        }

        return outcome::success();
#else
        NetworkLogger()->warn( "libp2p not compiled in — P2PNode running in stub mode" );

        impl_->peer_id_ = identity_ ? identity_->PeerId() : "stub-peer";
        impl_->listen_addr_ = cfg_.listen_addr_;
        impl_->running_.store( true );
        running_ = true;

        NetworkLogger()->info( "P2PNode started: peerId={} addr={}", impl_->peer_id_, impl_->listen_addr_ );
        return outcome::success();
#endif
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
#ifdef GENIUS_HAS_LIBP2P
        if ( impl_->gossip_ )
            impl_->gossip_->stop();
        if ( impl_->host_ )
            impl_->host_->stop();
        impl_->host_.reset();
        impl_->gossip_.reset();
        impl_->id_mgr_.reset();
#endif
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
    outcome::result<void> P2PNode::BroadcastTask( const Task& task )
    {
        if ( !running_ )
        {
            return outcome::failure( Error::NetworkError );
        }

        nlohmann::json j;
        j["id"] = task.id_;
        j["prompt"] = task.prompt_;
        j["mode"] = static_cast<int>( task.mode_ );
        j["max_tokens"] = task.max_tokens_;
        j["temperature"] = task.temperature_;
        std::string payload = j.dump();

        NetworkLogger()->debug( "Broadcasting task {} to {} peers", task.id_, impl_->peers_.size() );

#ifdef GENIUS_HAS_LIBP2P
        // Publish via GossipSub to all peers
        if ( impl_->gossip_ )
        {
            std::vector<uint8_t> data( payload.begin(), payload.end() );
            impl_->gossip_->publish( kTaskTopic, std::move( data ) );
        }
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
    outcome::result<void> P2PNode::BroadcastCRDT( const std::string& crdt_data )
    {
        if ( !running_ )
        {
            return outcome::failure( Error::NetworkError );
        }
        NetworkLogger()->debug( "Broadcasting CRDT update ({} bytes)", crdt_data.size() );
#ifdef GENIUS_HAS_LIBP2P
        if ( impl_->gossip_ )
        {
            std::vector<uint8_t> data( crdt_data.begin(), crdt_data.end() );
            impl_->gossip_->publish( kCRDTTopic, std::move( data ) );
        }
#else
        if ( crdt_handler_ )
        {
            crdt_handler_( crdt_data );
        }
#endif
        return outcome::success();
    }

} // namespace sgns::neoswarm::network
