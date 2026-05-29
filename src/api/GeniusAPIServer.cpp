/**
 * @file       GeniusAPIServer.cpp
 * @brief      Inference pipeline orchestration implementation
 * @date       2026-05-08
 * @author     Subaskar S (ssivakumar@gnus.ai)
 */

#include "GeniusAPIServer.hpp"
#include "core/engine/MNNInferenceEngine.hpp"
#include "core/tokenizer/Tokenizer.hpp"
#include "network/sg_client/SuperGeniusClient.hpp"
#include "common/Logging.hpp"

#include <algorithm>
#include <chrono>
#include <fstream>
#include <numeric>
#include <thread>

namespace sgns::neoswarm::api
{
    namespace
    {
        auto ServerLogger()
        {
            return neoswarm::CreateLogger( "GeniusAPIServer" );
        }

        std::string GenerateId()
        {
            auto now = std::chrono::steady_clock::now().time_since_epoch().count();
            auto tid = std::hash<std::thread::id>{}( std::this_thread::get_id() );
            return "task-" + std::to_string( now ) + "-" + std::to_string( tid & 0xFFFF );
        }
    }

    GeniusAPIServer::GeniusAPIServer( Config cfg ) : cfg_( std::move( cfg ) ) {}
    GeniusAPIServer::~GeniusAPIServer()
    {
        Stop();
    }

    // -----------------------------------------------------------------------
    // Initialize
    // -----------------------------------------------------------------------
    outcome::result<void> GeniusAPIServer::Initialize()
    {
        ServerLogger()->info( "Initializing GeniusAPIServer..." );

        // 1. Node identity
        identity_ = std::make_shared<security::NodeIdentity>();
        {
            std::ifstream key_check( cfg_.node_key_file_ );
            if ( key_check.good() )
            {
                auto res = identity_->LoadFromFile( cfg_.node_key_file_ );
                if ( !res.has_value() )
                {
                    ServerLogger()->warn( "Key load failed, generating new key" );
                }
            }
            if ( !identity_->IsLoaded() )
            {
                BOOST_OUTCOME_TRY( identity_->Generate() );
                identity_->SaveToFile( cfg_.node_key_file_ );
            }
        }
        ServerLogger()->info( "Node identity: {}", identity_->PeerId() );

        // 2. Core inference engine
        core::MNNInferenceEngine::Config engine_cfg;
        engine_cfg.engine_mode_     = cfg_.enable_sg_processing_ ? "sgprocessing" : "interpreter";
        engine_cfg.backend_         = "vulkan";  // cross-platform; MoltenVK on Apple
        engine_cfg.sg_network_mode_ = cfg_.sg_processing_network_mode_;
        auto engine = std::make_shared<core::MNNInferenceEngine>( engine_cfg );

        auto tokenizer = std::make_shared<core::SentencePieceTokenizer>();
        std::string tok_path = cfg_.model_path_;
        auto dot_pos = tok_path.rfind( '.' );
        if ( dot_pos != std::string::npos ) tok_path = tok_path.substr( 0, dot_pos );
        tok_path += ".tokenizer.model";
        tokenizer->Load( tok_path );  // degrades gracefully if not found
        engine->SetTokenizer( tokenizer );

        if ( !cfg_.model_path_.empty() )
        {
            auto res = engine->LoadModel( cfg_.model_path_ );
            if ( !res.has_value() )
            {
                ServerLogger()->warn( "Core model load failed — continuing in stub mode" );
            }
        }
        else
        {
            engine->SetStubMode();
        }
        core_engine_ = engine;

        // 3. Specialists
        grammar_spec_ = std::make_shared<specialists::GrammarSpecialist>(
            cfg_.grammar_model_path_.empty() ? nullptr : core_engine_ );
        math_spec_ = std::make_shared<specialists::MathSpecialist>(
            cfg_.math_model_path_.empty() ? nullptr : core_engine_ );

        if ( !cfg_.grammar_model_path_.empty() )
        {
            grammar_spec_->Load( cfg_.grammar_model_path_ );
        }
        if ( !cfg_.math_model_path_.empty() )
        {
            math_spec_->Load( cfg_.math_model_path_ );
        }

        // 4. Router
        router_ = std::make_unique<router::RuleBasedRouter>();

        // 5. Reputation
        scoring_     = std::make_unique<reputation::ReputationScoring>();
        consensus_   = std::make_unique<reputation::WeightedConsensus>();
        rep_crdt_    = std::make_unique<reputation::ReputationCRDT>();
        rep_storage_ = std::make_unique<reputation::ReputationStorage>( cfg_.reputation_db_path_ );
        auto stor_res = rep_storage_->Open();
        if ( !stor_res.has_value() )
        {
            ServerLogger()->warn( "Reputation storage open failed" );
        }

        // 6. Network (optional)
        if ( cfg_.enable_network_ )
        {
            network::P2PNode::Config net_cfg;
            p2p_node_    = std::make_unique<network::P2PNode>( identity_, net_cfg );
            aggregation_ = std::make_unique<network::ResultAggregation>();
            auto net_res = p2p_node_->Start();
            if ( !net_res.has_value() )
            {
                ServerLogger()->warn( "P2P network start failed" );
            }
        }

        // 6b. SuperGenius connectivity (optional — Phase 2 network dispatch)
        if ( !cfg_.sg_endpoint_.empty() )
        {
            network::SuperGeniusClient::Config sgCfg;
            sgCfg.endpoint_     = cfg_.sg_endpoint_;
            sgCfg.tls_ca_path_  = cfg_.sg_tls_ca_;
            sgCfg.tls_cert_path_ = cfg_.sg_tls_cert_;

            sg_client_ = std::make_unique<network::SuperGeniusClient>( std::move( sgCfg ) );
            auto initRes = sg_client_->Initialize( *identity_ );
            if ( initRes.has_value() )
            {
                auto connRes = sg_client_->Connect();
                if ( connRes.has_value() )
                {
                    ServerLogger()->info( "Connected to SuperGenius at {}", cfg_.sg_endpoint_ );
                }
                else
                {
                    ServerLogger()->warn( "SuperGenius connection failed — will fall back to local mode" );
                }
            }
            else
            {
                ServerLogger()->warn( "SuperGeniusClient initialization failed" );
            }

            // Wire SuperGeniusClient into the engine's SGProcessingBridge
            if ( core_engine_ )
            {
                auto *mnnEngine = dynamic_cast<core::MNNInferenceEngine *>( core_engine_.get() );
                if ( mnnEngine )
                {
                    mnnEngine->SetSuperGeniusClient( sg_client_.get() );
                }
            }
        }

        // 7. Knowledge
        if ( cfg_.enable_knowledge_ )
        {
            knowledge::KnowledgeRetrieval::Config k_cfg;
            k_cfg.facts_path_ = cfg_.knowledge_facts_;
            knowledge_ = std::make_shared<knowledge::KnowledgeRetrieval>( k_cfg );
            knowledge_->Load();
            context_inj_ = std::make_unique<knowledge::ContextInjection>();
            fact_val_    = std::make_unique<knowledge::FactValidation>( knowledge_ );
        }

        ServerLogger()->info( "GeniusAPIServer initialized (node={})", identity_->PeerId() );
        return outcome::success();
    }

    // -----------------------------------------------------------------------
    // AugmentPrompt
    // -----------------------------------------------------------------------
    std::string GeniusAPIServer::AugmentPrompt( const std::string          &prompt,
                                                std::vector<KnowledgeFact> &out_facts ) const
    {
        if ( !knowledge_ || !knowledge_->IsLoaded() || !context_inj_ )
        {
            return prompt;
        }
        auto facts_res = knowledge_->Retrieve( prompt );
        if ( !facts_res.has_value() || facts_res.value().empty() )
        {
            return prompt;
        }
        out_facts = facts_res.value();
        return context_inj_->Inject( prompt, out_facts );
    }

    // -----------------------------------------------------------------------
    // UpdateReputation
    // -----------------------------------------------------------------------
    void GeniusAPIServer::UpdateReputation( const InferenceResponse &resp,
                                            double                   median_latency_ms,
                                            const std::string       &consensus_output )
    {
        if ( !rep_storage_ || !rep_storage_->IsOpen() )
        {
            return;
        }

        auto get_res = rep_storage_->Get( resp.node_id_ );
        NodeReputation rep;
        if ( get_res.has_value() )
        {
            rep = get_res.value();
        }
        else
        {
            rep.identity_key_ = resp.node_id_;
        }

        auto updated = scoring_->Update( rep, resp, median_latency_ms,
                                         std::nullopt, consensus_output );
        rep_storage_->Put( updated );
        rep_crdt_->Merge( updated );

        if ( p2p_node_ && p2p_node_->IsRunning() )
        {
            p2p_node_->BroadcastCRDT( rep_crdt_->Serialize() );
        }
    }

    // -----------------------------------------------------------------------
    // RunSingleNode
    // -----------------------------------------------------------------------
    outcome::result<GeniusResponse> GeniusAPIServer::RunSingleNode(
        const Task &task, const RouteDecision &route )
    {
        std::vector<KnowledgeFact> facts;
        Task                       aug_task = task;
        aug_task.prompt_ = AugmentPrompt( task.prompt_, facts );

        auto res = core_engine_->Infer( aug_task );
        if ( !res.has_value() )
        {
            return outcome::failure( res.error() );
        }

        GeniusResponse resp;
        resp.output_          = res.value().output_;
        resp.task_id_         = task.id_;
        resp.mode_used_       = ExecutionMode::SingleNode;
        resp.route_used_      = route.target_;
        resp.grounding_facts_ = facts;
        resp.total_latency_ms_ = res.value().latency_ms_;
        resp.success_         = true;

        UpdateReputation( res.value(), res.value().latency_ms_, res.value().output_ );
        return outcome::success( std::move( resp ) );
    }

    // -----------------------------------------------------------------------
    // RunSpecialist
    // -----------------------------------------------------------------------
    outcome::result<GeniusResponse> GeniusAPIServer::RunSpecialist(
        const Task &task, const RouteDecision &route )
    {
        auto t0 = std::chrono::steady_clock::now();

        std::vector<KnowledgeFact> facts;
        Task                       aug_task = task;
        aug_task.prompt_ = AugmentPrompt( task.prompt_, facts );

        auto core_res = core_engine_->Infer( aug_task );
        if ( !core_res.has_value() )
        {
            return outcome::failure( core_res.error() );
        }

        std::string output = core_res.value().output_;

        if ( route.target_ == RouteTarget::CorePlusMath && math_spec_ )
        {
            auto spec_res = math_spec_->Process( output );
            if ( spec_res.has_value() ) output = spec_res.value();
        }
        else if ( route.target_ == RouteTarget::CorePlusGrammar && grammar_spec_ )
        {
            auto spec_res = grammar_spec_->Process( output );
            if ( spec_res.has_value() ) output = spec_res.value();
        }

        auto   t1         = std::chrono::steady_clock::now();
        double total_ms   = std::chrono::duration<double, std::milli>( t1 - t0 ).count();

        if ( fact_val_ && fact_val_->IsAvailable() )
        {
            auto val_result = fact_val_->Validate( output, facts );
            if ( !val_result.passed_ )
            {
                ServerLogger()->warn( "Fact validation failed: {}", val_result.suggestion_ );
                InferenceResponse penalty_resp = core_res.value();
                penalty_resp.perplexity_ = std::min(
                    penalty_resp.perplexity_ * ( 1.0f + val_result.contradiction_score_ ),
                    100.0f );
                UpdateReputation( penalty_resp, total_ms, output );
            }
        }

        GeniusResponse resp;
        resp.output_           = output;
        resp.task_id_          = task.id_;
        resp.mode_used_        = ExecutionMode::Specialist;
        resp.route_used_       = route.target_;
        resp.grounding_facts_  = facts;
        resp.total_latency_ms_ = total_ms;
        resp.success_          = true;

        UpdateReputation( core_res.value(), total_ms, output );
        return outcome::success( std::move( resp ) );
    }

    // -----------------------------------------------------------------------
    // RunSwarm
    // -----------------------------------------------------------------------
    outcome::result<GeniusResponse> GeniusAPIServer::RunSwarm(
        const Task &task, const RouteDecision &route )
    {
        auto t0 = std::chrono::steady_clock::now();

        std::vector<KnowledgeFact> facts;
        Task                       aug_task = task;
        aug_task.prompt_ = AugmentPrompt( task.prompt_, facts );

        if ( p2p_node_ && p2p_node_->IsRunning() && aggregation_ )
        {
            aggregation_->Reset();

            p2p_node_->OnTask( [this, aug_task]( const Task &t, const std::string &from_peer )
            {
                auto res = core_engine_->Infer( t );
                if ( res.has_value() )
                {
                    NodeOutput out;
                    out.node_id_    = from_peer;
                    out.output_     = res.value().output_;
                    out.perplexity_ = res.value().perplexity_;
                    out.latency_ms_ = res.value().latency_ms_;
                    if ( rep_storage_ && rep_storage_->IsOpen() )
                    {
                        auto rep_res = rep_storage_->Get( from_peer );
                        if ( rep_res.has_value() )
                        {
                            out.reputation_ = rep_res.value().global_score_;
                        }
                    }
                    aggregation_->Submit( out );
                }
            } );

            p2p_node_->BroadcastTask( aug_task );
            auto collect_res = aggregation_->Collect();
            if ( !collect_res.has_value() )
            {
                ServerLogger()->warn( "Swarm collection failed — falling back to single node" );
                return RunSingleNode( task, route );
            }

            auto winner = consensus_->SelectWinner( collect_res.value() );

            double median_latency = 0.0;
            auto  &outputs        = collect_res.value();
            if ( !outputs.empty() )
            {
                std::vector<double> latencies;
                for ( const auto &o : outputs ) latencies.push_back( o.latency_ms_ );
                std::sort( latencies.begin(), latencies.end() );
                median_latency = latencies[latencies.size() / 2];
            }
            for ( const auto &o : outputs )
            {
                InferenceResponse r;
                r.output_     = o.output_;
                r.perplexity_ = o.perplexity_;
                r.latency_ms_ = o.latency_ms_;
                r.node_id_    = o.node_id_;
                UpdateReputation( r, median_latency, winner.output_ );
            }

            auto t1 = std::chrono::steady_clock::now();
            GeniusResponse resp;
            resp.output_           = winner.output_;
            resp.task_id_          = task.id_;
            resp.mode_used_        = ExecutionMode::Swarm;
            resp.route_used_       = route.target_;
            resp.grounding_facts_  = facts;
            resp.total_latency_ms_ = std::chrono::duration<double, std::milli>( t1 - t0 ).count();
            resp.success_          = true;
            return outcome::success( std::move( resp ) );
        }

        ServerLogger()->warn( "Swarm mode requested but network unavailable — running locally" );
        return RunSingleNode( task, route );
    }

    // -----------------------------------------------------------------------
    // Process
    // -----------------------------------------------------------------------
    outcome::result<GeniusResponse> GeniusAPIServer::Process( const Task &task )
    {
        if ( !core_engine_ )
        {
            return outcome::failure( Error::InternalError );
        }

        Task t = task;
        if ( t.id_.empty() )   t.id_      = GenerateId();
        if ( t.node_id_.empty() ) t.node_id_ = identity_ ? identity_->PeerId() : "local";

        auto route_res = router_->Route( t );
        if ( !route_res.has_value() )
        {
            return outcome::failure( route_res.error() );
        }
        const RouteDecision &route = route_res.value();

        ServerLogger()->info( "Processing task {}: mode={} route={}",
                              t.id_,
                              static_cast<int>( route.mode_ ),
                              static_cast<int>( route.target_ ) );

        switch ( route.mode_ )
        {
            case ExecutionMode::SingleNode:
                return RunSingleNode( t, route );
            case ExecutionMode::Specialist:
                return RunSpecialist( t, route );
            case ExecutionMode::Swarm:
                return RunSwarm( t, route );
        }
        return outcome::failure( Error::InternalError );
    }

    // -----------------------------------------------------------------------
    // Serve / Stop
    // -----------------------------------------------------------------------
    outcome::result<void> GeniusAPIServer::Serve()
    {
        running_.store( true );
        ServerLogger()->info( "GeniusAPIServer serving on port {}", cfg_.grpc_port_ );

        while ( running_.load() )
        {
            std::this_thread::sleep_for( std::chrono::milliseconds( 100 ) );
        }
        return outcome::success();
    }

    void GeniusAPIServer::Stop()
    {
        running_.store( false );
        if ( p2p_node_ ) p2p_node_->Stop();
        if ( sg_client_ ) sg_client_->Disconnect();
        if ( rep_storage_ ) rep_storage_->Close();
        ServerLogger()->info( "GeniusAPIServer stopped" );
    }

    bool GeniusAPIServer::IsSuperGeniusConnected() const noexcept
    {
        return sg_client_ != nullptr && sg_client_->IsConnected();
    }

} // namespace sgns::neoswarm::api
