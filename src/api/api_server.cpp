/**
 * @file       api_server.cpp
 * @brief      Inference pipeline orchestration implementation
 * @date       2026-05-08
 */

#include "api_server.hpp"
#include "common/logging.hpp"
#include "core/engine/mnn_inference_engine.hpp"
#include "core/tokenizer/tokenizer.hpp"
#include "network/sg_client/super_genius_client.hpp"

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
            return neoswarm::CreateLogger( "ApiServer" );
        }

        std::string GenerateId()
        {
            auto now = std::chrono::steady_clock::now().time_since_epoch().count();
            auto tid = std::hash<std::thread::id>{}( std::this_thread::get_id() );
            return "task-" + std::to_string( now ) + "-" + std::to_string( tid & 0xFFFF );
        }
    } // namespace

    ApiServer::ApiServer( Config cfg )
        : m_cfg( std::move( cfg ) )
    {
    }
    ApiServer::~ApiServer()
    {
        Stop();
    }

    // -----------------------------------------------------------------------
    // Initialize
    // -----------------------------------------------------------------------
    outcome::result<void> ApiServer::Initialize()
    {
        ServerLogger()->info( "Initializing ApiServer..." );

        // 1. Node identity
        m_identity = std::make_shared<security::NodeIdentity>();
        {
            std::ifstream key_check( m_cfg.m_nodeKeyFile );
            if ( key_check.good() )
            {
                auto res = m_identity->LoadFromFile( m_cfg.m_nodeKeyFile );
                if ( !res.has_value() )
                {
                    ServerLogger()->warn( "Key load failed, generating new key" );
                }
            }
            if ( !m_identity->IsLoaded() )
            {
                BOOST_OUTCOME_TRY( m_identity->Generate() );
                (void)m_identity->SaveToFile( m_cfg.m_nodeKeyFile );
            }
        }
        ServerLogger()->info( "Node identity: {}", m_identity->PeerId() );

        // 2. Core inference engine
        core::MNNInferenceEngine::Config engine_cfg;
        engine_cfg.engine_m_mode = m_cfg.m_enableSgProcessing ? "sgprocessing" : "interpreter";
        engine_cfg.backend_ = "vulkan"; // cross-platform; MoltenVK on Apple
        engine_cfg.sg_m_networkMode = m_cfg.sg_processing_m_networkMode;
        auto engine = std::make_shared<core::MNNInferenceEngine>( engine_cfg );

        auto tokenizer = std::make_shared<core::SentencePieceTokenizer>();
        std::string tok_path = m_cfg.m_modelPath;
        auto dot_pos = tok_path.rfind( '.' );
        if ( dot_pos != std::string::npos )
            tok_path = tok_path.substr( 0, dot_pos );
        tok_path += ".tokenizer.model";
        (void)tokenizer->Load( tok_path ); // degrades gracefully if not found
        engine->SetTokenizer( tokenizer );

        if ( !m_cfg.m_modelPath.empty() )
        {
            auto res = engine->LoadModel( m_cfg.m_modelPath );
            if ( !res.has_value() )
            {
                ServerLogger()->warn( "Core model load failed — continuing in stub mode" );
            }
        }
        else
        {
            engine->SetStubMode();
        }
        m_coreEngine = engine;

        // 3. Specialists
        m_grammarSpec = std::make_shared<specialists::GrammarSpecialist>(
            m_cfg.grammar_m_modelPath.empty() ? nullptr : m_coreEngine );
        m_mathSpec =
            std::make_shared<specialists::MathSpecialist>( m_cfg.math_m_modelPath.empty() ? nullptr : m_coreEngine );

        if ( !m_cfg.grammar_m_modelPath.empty() )
        {
            (void)m_grammarSpec->Load( m_cfg.grammar_m_modelPath );
        }
        if ( !m_cfg.math_m_modelPath.empty() )
        {
            (void)m_mathSpec->Load( m_cfg.math_m_modelPath );
        }

        // 4. Router
        m_router = std::make_unique<router::RuleBasedRouter>();

        // 5. Reputation
        m_scoring = std::make_unique<reputation::ReputationScoring>();
        m_consensus = std::make_unique<reputation::WeightedConsensus>();
        m_repCrdt = std::make_unique<reputation::ReputationCRDT>();
        m_repStorage = std::make_unique<reputation::ReputationStorage>( m_cfg.m_reputationDbPath );
        auto stor_res = m_repStorage->Open();
        if ( !stor_res.has_value() )
        {
            ServerLogger()->warn( "Reputation storage open failed" );
        }

        // 6. Network (optional)
        if ( m_cfg.m_enableNetwork )
        {
            network::P2PNode::Config net_cfg;
            m_p2pNode = std::make_unique<network::P2PNode>( m_identity, net_cfg );
            m_aggregation = std::make_unique<network::ResultAggregation>();
            auto net_res = m_p2pNode->Start();
            if ( !net_res.has_value() )
            {
                ServerLogger()->warn( "P2P network start failed" );
            }
        }

        // 6b. SuperGenius connectivity (optional — Phase 2 network dispatch)
        if ( !m_cfg.sg_m_endpoint.empty() )
        {
            network::SuperGeniusClient::Config sgCfg;
            sgCfg.m_endpoint = m_cfg.sg_m_endpoint;
            sgCfg.m_tlsCaPath = m_cfg.m_sgTlsCa;
            sgCfg.m_tlsCertPath = m_cfg.m_sgTlsCert;

            m_sgClient = std::make_unique<network::SuperGeniusClient>( std::move( sgCfg ) );
            auto initRes = m_sgClient->Initialize( *m_identity );
            if ( initRes.has_value() )
            {
                auto connRes = m_sgClient->Connect();
                if ( connRes.has_value() )
                {
                    ServerLogger()->info( "Connected to SuperGenius at {}", m_cfg.sg_m_endpoint );
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
            if ( m_coreEngine )
            {
                auto* mnnEngine = dynamic_cast<core::MNNInferenceEngine*>( m_coreEngine.get() );
                if ( mnnEngine )
                {
                    mnnEngine->SetSuperGeniusClient( m_sgClient.get() );
                }
            }
        }

        // 7. Knowledge
        if ( m_cfg.m_enableKnowledge )
        {
            knowledge::KnowledgeRetrieval::Config k_cfg;
            k_cfg.m_factsPath = m_cfg.m_knowledgefacts_;
            m_knowledge = std::make_shared<knowledge::KnowledgeRetrieval>( k_cfg );
            (void)m_knowledge->Load();
            m_contextInj = std::make_unique<knowledge::ContextInjection>();
            m_factVal = std::make_unique<knowledge::FactValidation>( m_knowledge );
        }

        ServerLogger()->info( "ApiServer initialized (node={})", m_identity->PeerId() );
        return outcome::success();
    }

    // -----------------------------------------------------------------------
    // AugmentPrompt
    // -----------------------------------------------------------------------
    std::string ApiServer::AugmentPrompt( const std::string& prompt, std::vector<KnowledgeFact>& out_facts ) const
    {
        if ( !m_knowledge || !m_knowledge->IsLoaded() || !m_contextInj )
        {
            return prompt;
        }
        auto facts_res = m_knowledge->Retrieve( prompt );
        if ( !facts_res.has_value() || facts_res.value().empty() )
        {
            return prompt;
        }
        out_facts = facts_res.value();
        return m_contextInj->Inject( prompt, out_facts );
    }

    // -----------------------------------------------------------------------
    // UpdateReputation
    // -----------------------------------------------------------------------
    void ApiServer::UpdateReputation( const InferenceResponse& resp,
                                            double median_latency_ms,
                                            const std::string& m_consensusoutput )
    {
        if ( !m_repStorage || !m_repStorage->IsOpen() )
        {
            return;
        }

        auto get_res = m_repStorage->Get( resp.m_nodeId );
        NodeReputation rep;
        if ( get_res.has_value() )
        {
            rep = get_res.value();
        }
        else
        {
            rep.m_identityKey = resp.m_nodeId;
        }

        auto updated = m_scoring->Update( rep, resp, median_latency_ms, std::nullopt, m_consensusoutput );
        (void)m_repStorage->Put( updated );
        m_repCrdt->Merge( updated );

        if ( m_p2pNode && m_p2pNode->IsRunning() )
        {
            (void)m_p2pNode->BroadcastCRDT( m_repCrdt->Serialize() );
        }
    }

    // -----------------------------------------------------------------------
    // RunSingleNode
    // -----------------------------------------------------------------------
    outcome::result<InferenceResponse> ApiServer::RunSingleNode( const Task& task, const RouteDecision& route )
    {
        std::vector<KnowledgeFact> facts;
        Task aug_task = task;
        aug_task.m_prompt = AugmentPrompt( task.m_prompt, facts );

        auto res = m_coreEngine->Infer( aug_task );
        if ( !res.has_value() )
        {
            return outcome::failure( res.error() );
        }

        InferenceResponse resp;
        resp.m_output = res.value().m_output;
        resp.m_taskId = task.m_id;
        resp.m_modeUsed = ExecutionMode::SingleNode;
        resp.m_routeUsed = route.m_target;
        resp.m_totalLatencyMs = res.value().m_latencyMs;
        resp.m_success = true;

        UpdateReputation( res.value(), res.value().m_latencyMs, res.value().m_output );
        return outcome::success( std::move( resp ) );
    }

    // -----------------------------------------------------------------------
    // RunSpecialist
    // -----------------------------------------------------------------------
    outcome::result<InferenceResponse> ApiServer::RunSpecialist( const Task& task, const RouteDecision& route )
    {
        auto t0 = std::chrono::steady_clock::now();

        std::vector<KnowledgeFact> facts;
        Task aug_task = task;
        aug_task.m_prompt = AugmentPrompt( task.m_prompt, facts );

        auto core_res = m_coreEngine->Infer( aug_task );
        if ( !core_res.has_value() )
        {
            return outcome::failure( core_res.error() );
        }

        std::string output = core_res.value().m_output;

        if ( route.m_target == RouteTarget::CorePlusMath && m_mathSpec )
        {
            auto spec_res = m_mathSpec->Process( output );
            if ( spec_res.has_value() )
                output = spec_res.value();
        }
        else if ( route.m_target == RouteTarget::CorePlusGrammar && m_grammarSpec )
        {
            auto spec_res = m_grammarSpec->Process( output );
            if ( spec_res.has_value() )
                output = spec_res.value();
        }

        auto t1 = std::chrono::steady_clock::now();
        double total_ms = std::chrono::duration<double, std::milli>( t1 - t0 ).count();

        if ( m_factVal && m_factVal->IsAvailable() )
        {
            auto val_result = m_factVal->Validate( output, facts );
            if ( !val_result.passed_ )
            {
                ServerLogger()->warn( "Fact validation failed: {}", val_result.suggestion_ );
                InferenceResponse penalty_resp = core_res.value();
                penalty_resp.m_perplexity =
                    std::min( penalty_resp.m_perplexity * ( 1.0f + val_result.m_contradictionScore ), 100.0f );
                UpdateReputation( penalty_resp, total_ms, output );
            }
        }

        InferenceResponse resp;
        resp.m_output = output;
        resp.m_taskId = task.m_id;
        resp.m_modeUsed = ExecutionMode::Specialist;
        resp.m_routeUsed = route.m_target;
        resp.m_totalLatencyMs = total_ms;
        resp.m_success = true;

        UpdateReputation( core_res.value(), total_ms, output );
        return outcome::success( std::move( resp ) );
    }

    // -----------------------------------------------------------------------
    // RunSwarm
    // -----------------------------------------------------------------------
    outcome::result<InferenceResponse> ApiServer::RunSwarm( const Task& task, const RouteDecision& route )
    {
        auto t0 = std::chrono::steady_clock::now();

        std::vector<KnowledgeFact> facts;
        Task aug_task = task;
        aug_task.m_prompt = AugmentPrompt( task.m_prompt, facts );

        if ( m_p2pNode && m_p2pNode->IsRunning() && m_aggregation )
        {
            m_aggregation->Reset();

            m_p2pNode->OnTask(
                [this, aug_task]( const Task& t, const std::string& from_peer )
                {
                    auto res = m_coreEngine->Infer( t );
                    if ( res.has_value() )
                    {
                        NodeOutput out;
                        out.m_nodeId = from_peer;
                        out.m_output = res.value().m_output;
                        out.m_perplexity = res.value().m_perplexity;
                        out.m_latencyMs = res.value().m_latencyMs;
                        if ( m_repStorage && m_repStorage->IsOpen() )
                        {
                            auto rep_res = m_repStorage->Get( from_peer );
                            if ( rep_res.has_value() )
                            {
                                out.reputation_ = rep_res.value().m_globalScore;
                            }
                        }
                        m_aggregation->Submit( out );
                    }
                } );

            (void)m_p2pNode->BroadcastTask( aug_task );
            auto collect_res = m_aggregation->Collect();
            if ( !collect_res.has_value() )
            {
                ServerLogger()->warn( "Swarm collection failed — falling back to single node" );
                return RunSingleNode( task, route );
            }

            auto winner = m_consensus->SelectWinner( collect_res.value() );

            double median_latency = 0.0;
            auto& outputs = collect_res.value();
            if ( !outputs.empty() )
            {
                std::vector<double> latencies;
                for ( const auto& o : outputs )
                    latencies.push_back( o.m_latencyMs );
                std::sort( latencies.begin(), latencies.end() );
                median_latency = latencies[latencies.size() / 2];
            }
            for ( const auto& o : outputs )
            {
                InferenceResponse r;
                r.m_output = o.m_output;
                r.m_perplexity = o.m_perplexity;
                r.m_latencyMs = o.m_latencyMs;
                r.m_nodeId = o.m_nodeId;
                UpdateReputation( r, median_latency, winner.m_output );
            }

            auto t1 = std::chrono::steady_clock::now();
            InferenceResponse resp;
            resp.m_output = winner.m_output;
            resp.m_taskId = task.m_id;
            resp.m_modeUsed = ExecutionMode::Swarm;
            resp.m_routeUsed = route.m_target;
            resp.m_totalLatencyMs = std::chrono::duration<double, std::milli>( t1 - t0 ).count();
            resp.m_success = true;
            return outcome::success( std::move( resp ) );
        }

        ServerLogger()->warn( "Swarm mode requested but network unavailable — running locally" );
        return RunSingleNode( task, route );
    }

    // -----------------------------------------------------------------------
    // Process
    // -----------------------------------------------------------------------
    outcome::result<InferenceResponse> ApiServer::Process( const Task& task )
    {
        if ( !m_coreEngine )
        {
            return outcome::failure( Error::InternalError );
        }

        Task t = task;
        if ( t.m_id.empty() )
            t.m_id = GenerateId();
        if ( t.m_nodeId.empty() )
            t.m_nodeId = m_identity ? m_identity->PeerId() : "local";

        auto route_res = m_router->Route( t );
        if ( !route_res.has_value() )
        {
            return outcome::failure( route_res.error() );
        }
        const RouteDecision& route = route_res.value();

        ServerLogger()->info( "Processing task {}: mode={} route={}", t.m_id, static_cast<int>( route.m_mode ),
                              static_cast<int>( route.m_target ) );

        switch ( route.m_mode )
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
    outcome::result<void> ApiServer::Serve()
    {
        m_running.store( true );
        ServerLogger()->info( "ApiServer serving on port {}", m_cfg.m_grpcPort );

        while ( m_running.load() )
        {
            std::this_thread::sleep_for( std::chrono::milliseconds( 100 ) );
        }
        return outcome::success();
    }

    void ApiServer::Stop()
    {
        m_running.store( false );
        if ( m_p2pNode )
            m_p2pNode->Stop();
        if ( m_sgClient )
            m_sgClient->Disconnect();
        if ( m_repStorage )
            m_repStorage->Close();
        ServerLogger()->info( "ApiServer stopped" );
    }

    bool ApiServer::IsSuperGeniusConnected() const noexcept
    {
        return m_sgClient != nullptr && m_sgClient->IsConnected();
    }

} // namespace sgns::neoswarm::api
