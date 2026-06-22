/**
 * @file       p2p_node.cpp
 * @brief      libp2p swarm node implementation
 * @date       2026-05-06
 */

#include "p2p_node.hpp"
#include "common/logging.hpp"

#include <atomic>
#include <nlohmann/json.hpp>

#include <libp2p/host/basic_host/basic_host.hpp>
#include <libp2p/injector/host_injector.hpp>
#include <libp2p/multi/multiaddress.hpp>
#include <libp2p/protocol/gossip/gossip.hpp>

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
        std::string peer_m_id;
        std::vector<std::string> peers_;
        std::atomic<bool> m_running{ false };

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
    };

    P2PNode::P2PNode( std::shared_ptr<security::NodeIdentity> identity )
        : m_impl( std::make_unique<Impl>() )
        , m_identity( std::move( identity ) )
        , m_cfg( {} )
    {
    }

    P2PNode::P2PNode( std::shared_ptr<security::NodeIdentity> identity, Config cfg )
        : m_impl( std::make_unique<Impl>() )
        , m_identity( std::move( identity ) )
        , m_cfg( std::move( cfg ) )
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
        NetworkLogger()->info( "P2PNode starting (libp2p)..." );

        try
        {
            // 1. Create host with full libp2p stack via Boost.DI injector.
            //    makeNetworkInjector internally generates keys and creates all providers.
            auto injector = libp2p::injector::makeHostInjector();
            m_impl->host_ = injector.template create<std::shared_ptr<libp2p::Host>>();
            m_impl->id_mgr_ = injector.template create<std::shared_ptr<libp2p::peer::IdentityManager>>();

            // 2. Create GossipSub protocol using DI-provided components
            auto scheduler = injector.template create<std::shared_ptr<libp2p::basic::Scheduler>>();
            auto crypto_provider = injector.template create<std::shared_ptr<libp2p::crypto::CryptoProvider>>();
            auto key_marshaller =
                injector.template create<std::shared_ptr<libp2p::crypto::marshaller::KeyMarshaller>>();
            m_impl->gossip_ = libp2p::protocol::gossip::create( scheduler, m_impl->host_, m_impl->id_mgr_, crypto_provider,
                                                               key_marshaller, libp2p::protocol::gossip::Config{} );

            // 3. Subscribe to task and CRDT topics
            m_impl->subs_ = std::make_unique<Impl::GossipSubs>();
            m_impl->subs_->task_sub = m_impl->gossip_->subscribe(
                { kTaskTopic },
                [this]( libp2p::protocol::gossip::Gossip::SubscriptionData sub_data )
                {
                    if ( sub_data && m_taskHandler )
                    {
                        const auto& msg = sub_data.value();
                        auto json =
                            nlohmann::json::parse( std::string( msg.data.begin(), msg.data.end() ), nullptr, false );
                        if ( !json.is_discarded() )
                        {
                            Task t;
                            t.m_id = json.value( "id", "" );
                            t.m_prompt = json.value( "prompt", "" );
                            t.m_mode = static_cast<ExecutionMode>( json.value( "mode", 0 ) );
                            t.m_maxTokens = json.value( "max_tokens", 512U );
                            t.m_temperature = json.value( "temperature", 0.7f );
                            m_taskHandler( t, m_impl->peer_m_id );
                        }
                    }
                } );

            m_impl->subs_->crdt_sub =
                m_impl->gossip_->subscribe( { kCRDTTopic },
                                           [this]( libp2p::protocol::gossip::Gossip::SubscriptionData sub_data )
                                           {
                                               if ( sub_data && m_crdtHandler )
                                               {
                                                   const auto& msg = sub_data.value();
                                                   m_crdtHandler( std::string( msg.data.begin(), msg.data.end() ) );
                                               }
                                           } );

            // 4. Listen on configured address
            auto listen_ma = libp2p::multi::Multiaddress::create( m_cfg.listen_addr_.empty() ? "/ip4/0.0.0.0/tcp/0"
                                                                                            : m_cfg.listen_addr_ );
            if ( listen_ma )
            {
                (void)m_impl->host_->listen( listen_ma.value() );
            }

            // 5. Start the host and gossip
            m_impl->host_->start();
            m_impl->gossip_->start();

            m_impl->peer_m_id = m_impl->host_->getId().toBase58();
            m_impl->listen_addr_ = m_cfg.listen_addr_;
            m_impl->m_running.store( true );
            m_running = true;

            NetworkLogger()->info( "P2PNode started (libp2p): peerId={}", m_impl->peer_m_id );
        }
        catch ( const std::exception& e )
        {
            NetworkLogger()->error( "P2PNode start failed: {}", e.what() );
            return outcome::failure( Error::NetworkError );
        }

        return outcome::success();

    }

    // -----------------------------------------------------------------------
    // Stop
    // -----------------------------------------------------------------------
    void P2PNode::Stop()
    {
        if ( !m_running )
        {
            return;
        }
        if ( m_impl->gossip_ )
            m_impl->gossip_->stop();
        if ( m_impl->host_ )
            m_impl->host_->stop();
        m_impl->host_.reset();
        m_impl->gossip_.reset();
        m_impl->id_mgr_.reset();
        m_impl->m_running.store( false );
        m_running = false;
        NetworkLogger()->info( "P2PNode stopped" );
    }

    std::string P2PNode::ListenAddress() const
    {
        return m_impl->listen_addr_;
    }

    std::string P2PNode::PeerId() const
    {
        return m_impl->peer_m_id;
    }

    std::vector<std::string> P2PNode::ConnectedPeers() const
    {
        return m_impl->peers_;
    }

    // -----------------------------------------------------------------------
    // BroadcastTask
    // -----------------------------------------------------------------------
    outcome::result<void> P2PNode::BroadcastTask( const Task& task )
    {
        if ( !m_running )
        {
            return outcome::failure( Error::NetworkError );
        }

        nlohmann::json j;
        j["id"] = task.m_id;
        j["prompt"] = task.m_prompt;
        j["mode"] = static_cast<int>( task.m_mode );
        j["max_tokens"] = task.m_maxTokens;
        j["temperature"] = task.m_temperature;
        std::string payload = j.dump();

        NetworkLogger()->debug( "Broadcasting task {} to {} peers", task.m_id, m_impl->peers_.size() );

        // Publish via GossipSub to all peers
        if ( m_impl->gossip_ )
        {
            std::vector<uint8_t> data( payload.begin(), payload.end() );
            m_impl->gossip_->publish( kTaskTopic, std::move( data ) );
        }

        return outcome::success();
    }

    // -----------------------------------------------------------------------
    // BroadcastCRDT
    // -----------------------------------------------------------------------
    outcome::result<void> P2PNode::BroadcastCRDT( const std::string& crdt_data )
    {
        if ( !m_running )
        {
            return outcome::failure( Error::NetworkError );
        }
        NetworkLogger()->debug( "Broadcasting CRDT update ({} bytes)", crdt_data.size() );
        if ( m_impl->gossip_ )
        {
            std::vector<uint8_t> data( crdt_data.begin(), crdt_data.end() );
            m_impl->gossip_->publish( kCRDTTopic, std::move( data ) );
        }

        return outcome::success();
    }

} // namespace sgns::neoswarm::network
