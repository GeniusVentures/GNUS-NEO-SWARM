/**
 * @file       api_server.cpp
 * @brief      Inference pipeline orchestration implementation
 * @date       2026-05-08
 */

#include "api_server.hpp"
#include "common/logging.hpp"
#include "core/engine/mnn_inference_engine.hpp"
#include "elm/role_elm.hpp"
#include "elm/domain_elm.hpp"
#include "elm/grounding_elm.hpp"
#include "elm/tool_support_elm.hpp"
#include "elm/specialist_adapter.hpp"
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

        static ELMRole ParseELMRole( const std::string& roleStr )
        {
            static const std::unordered_map<std::string, ELMRole> kRoleMap = {
                { "planner",       ELMRole::Planner },
                { "primarydraft",  ELMRole::PrimaryDraft },
                { "verifier",      ELMRole::Verifier },
                { "arbiter",       ELMRole::Arbiter },
                { "refiner",       ELMRole::Refiner },
                { "grounding",     ELMRole::Grounding },
                { "toolsupport",   ELMRole::ToolSupport },
                { "math",          ELMRole::Math },
                { "code",          ELMRole::Code },
                { "science",       ELMRole::Science },
            };
            auto it = kRoleMap.find( roleStr );
            return ( it != kRoleMap.end() ) ? it->second : ELMRole::PrimaryDraft;
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

        // 1. Node identity — encrypted at rest (AES-256-GCM + PBKDF2)
        m_identity = std::make_shared<security::NodeIdentity>();
        {
            std::ifstream key_check( m_cfg.m_nodeKeyFile );
            if ( key_check.good() )
            {
                // Try encrypted load first, fall back to plaintext for backward compat
                auto res = m_identity->LoadEncrypted( m_cfg.m_nodeKeyFile, m_cfg.m_nodeKeyPassphrase );
                if ( !res.has_value() )
                {
                    res = m_identity->LoadFromFile( m_cfg.m_nodeKeyFile );
                }
                if ( !res.has_value() )
                {
                    ServerLogger()->warn( "Key load failed, generating new key" );
                }
            }
            if ( !m_identity->IsLoaded() )
            {
                BOOST_OUTCOME_TRY( m_identity->Generate() );
                (void)m_identity->SaveEncrypted( m_cfg.m_nodeKeyFile, m_cfg.m_nodeKeyPassphrase );
            }
        }
        ServerLogger()->info( "Node identity: {}", m_identity->GetPeerId() );

        // 2. Core inference engine
        InitializeEngine();

        // 3. Specialists
        m_grammarSpec = std::make_shared<specialists::GrammarSpecialist>(
            m_cfg.m_grammarModelPath.empty() ? nullptr : m_coreEngine );
        m_mathSpec =
            std::make_shared<specialists::MathSpecialist>( m_cfg.m_mathModelPath.empty() ? nullptr : m_coreEngine );

        if ( !m_cfg.m_grammarModelPath.empty() )
        {
            (void)m_grammarSpec->Load( m_cfg.m_grammarModelPath );
        }
        if ( !m_cfg.m_mathModelPath.empty() )
        {
            (void)m_mathSpec->Load( m_cfg.m_mathModelPath );
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

        // 6. Network (optional) + SuperGenius connectivity
        InitializeNetwork();

        // 7. Knowledge
        if ( m_cfg.m_enableKnowledge )
        {
            knowledge::KnowledgeRetrieval::Config k_cfg;
            k_cfg.m_factsPath = m_cfg.m_knowledgeFacts;
            m_knowledge = std::make_shared<knowledge::KnowledgeRetrieval>( k_cfg );
            (void)m_knowledge->Load();
            m_contextInj = std::make_unique<knowledge::ContextInjection>();
            m_factVal = std::make_unique<knowledge::FactValidation>( m_knowledge );
        }

        // 8. ELM subsystem (Phase 7+)
        m_chainBuilder = std::make_unique<elm::ELMChainBuilder>();
        m_promptAnalyzer = std::make_unique<router::PromptAnalyzer>();

        // Register role-based ELMs (shared backbone — D-01)
        m_elmRegistry[ELMRole::Planner] = std::make_shared<elm::RoleELM>( ELMRole::Planner, m_coreEngine );
        m_elmRegistry[ELMRole::PrimaryDraft] = std::make_shared<elm::RoleELM>( ELMRole::PrimaryDraft, m_coreEngine );
        m_elmRegistry[ELMRole::Verifier] = std::make_shared<elm::RoleELM>( ELMRole::Verifier, m_coreEngine );
        m_elmRegistry[ELMRole::Arbiter] = std::make_shared<elm::RoleELM>( ELMRole::Arbiter, m_coreEngine );

        // Refiner wraps GrammarSpecialist via adapter (D-06)
        if ( m_grammarSpec )
        {
            m_elmRegistry[ELMRole::Refiner] = std::make_shared<elm::SpecialistAdapter>(
                m_grammarSpec, ELMRole::Refiner, "Refiner/Formatter" );
        }
        else
        {
            // Fallback: shared-backbone Refiner if no grammar specialist
            m_elmRegistry[ELMRole::Refiner] = std::make_shared<elm::RoleELM>( ELMRole::Refiner, m_coreEngine );
        }

        // Domain ELMs (Math via adapter, Code/Science as DomainELM)
        if ( m_mathSpec )
        {
            m_elmRegistry[ELMRole::Math] = std::make_shared<elm::SpecialistAdapter>(
                m_mathSpec, ELMRole::Math, "Math" );
        }
        else
        {
            m_elmRegistry[ELMRole::Math] = std::make_shared<elm::DomainELM>( ELMRole::Math, m_coreEngine );
        }
        m_elmRegistry[ELMRole::Code] = std::make_shared<elm::DomainELM>( ELMRole::Code, m_coreEngine );
        m_elmRegistry[ELMRole::Science] = std::make_shared<elm::DomainELM>( ELMRole::Science, m_coreEngine );

        // GroundingELM — wraps knowledge pipeline (D-17)
        if ( m_cfg.m_enableKnowledge && m_knowledge )
        {
            m_elmRegistry[ELMRole::Grounding] = std::make_shared<elm::GroundingELM>(
                m_coreEngine, m_knowledge,
                std::make_unique<knowledge::ContextInjection>(),
                std::make_unique<knowledge::FactValidation>( m_knowledge ) );
            auto groundLoad = m_elmRegistry[ELMRole::Grounding]->Load( "" );
            if ( !groundLoad.has_value() )
            {
                ServerLogger()->error( "GroundingELM failed to load" );
                return groundLoad.as_failure();
            }
        }
        else
        {
            // Fallback: shared-backbone Grounding if knowledge unavailable
            m_elmRegistry[ELMRole::Grounding] = std::make_shared<elm::RoleELM>( ELMRole::Grounding, m_coreEngine );
        }

        // ToolSupportELM — stub (D-18)
        m_elmRegistry[ELMRole::ToolSupport] = std::make_shared<elm::ToolSupportELM>();

        // Load eager ELMs from config (D-16)
        for ( const auto& elmCfg : m_cfg.m_elmConfigs )
        {
            if ( elmCfg.eager && !elmCfg.model.empty() )
            {
                // Parse role string to ELMRole enum
                auto role = ParseELMRole( elmCfg.role );
                auto it = m_elmRegistry.find( role );
                if ( it != m_elmRegistry.end() && it->second )
                {
                    auto loadRes = it->second->Load( elmCfg.model );
                    if ( !loadRes.has_value() )
                    {
                        ServerLogger()->error( "Failed to eagerly load ELM '{}': model={}",
                                               elmCfg.role, elmCfg.model );
                        return outcome::failure( Error::ModelLoadFailed );
                    }
                }
            }
        }

        ServerLogger()->info( "ApiServer initialized (node={})", m_identity->GetPeerId() );
        return outcome::success();
    }

    // -----------------------------------------------------------------------
    // InitializeEngine — extracted from Initialize for size/complexity
    // -----------------------------------------------------------------------
    void ApiServer::InitializeEngine()
    {
        core::MNNInferenceEngine::Config engine_cfg;
        engine_cfg.m_engineMode = m_cfg.m_enableSgProcessing ? "sgprocessing" : "interpreter";
        engine_cfg.m_backend = "vulkan"; // cross-platform; MoltenVK on Apple
        engine_cfg.m_sgNetworkMode = m_cfg.m_sgProcessingNetworkMode;
        auto engine = std::make_shared<core::MNNInferenceEngine>( engine_cfg );


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
    }

    // -----------------------------------------------------------------------
    // InitializeNetwork — P2P + SuperGenius connectivity
    // -----------------------------------------------------------------------
    void ApiServer::InitializeNetwork()
    {
        // P2P network (optional)
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

        // SuperGenius connectivity (optional — Phase 2 network dispatch)
        if ( m_cfg.m_sgProcessingNetworkMode )
        {
            network::SGClient::Config sgCfg;
            sgCfg.m_sdkBasePath = m_cfg.m_sgSdkBasePath;
            sgCfg.m_basePort = m_cfg.m_sgBasePort;

            m_sgClient = std::make_unique<network::SGClient>( std::move( sgCfg ) );
            auto initRes = m_sgClient->Initialize();
            if ( initRes.has_value() )
            {
                ServerLogger()->info( "SGClient initialized — SDK node started" );
            }
            else
            {
                ServerLogger()->warn( "SGClient initialization failed — will fall back to local mode" );
            }

            // Wire SGClient into the engine's SGProcessingBridge
            if ( m_coreEngine )
            {
                auto* mnnEngine = dynamic_cast<core::MNNInferenceEngine*>( m_coreEngine.get() );
                if ( mnnEngine )
                {
                    mnnEngine->SetSGClient( m_sgClient.get() );
                }
            }
        }
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
    // RunELMChain
    // -----------------------------------------------------------------------
    outcome::result<InferenceResponse> ApiServer::RunELMChain( const Task& task, const RouteDecision& route )
    {
        auto t0 = std::chrono::steady_clock::now();

        std::vector<KnowledgeFact> facts;
        Task augTask = task;
        augTask.m_prompt = AugmentPrompt( task.m_prompt, facts );

        // Extract prompt features for chain builder
        PromptFeatures features;
        if ( m_promptAnalyzer )
        {
            features = m_promptAnalyzer->Analyze( augTask.m_prompt );
        }

        // Build execution chain
        ExecutionChain chain = m_chainBuilder->Build( route, features );
        if ( chain.m_steps.empty() )
        {
            ServerLogger()->warn( "Chain builder produced empty chain — falling back to single node" );
            return RunSingleNode( task, route );
        }

        // Initialise ELM context
        ELMContext context;
        context.m_originalTask = task.m_prompt;
        context.m_groundingFacts = facts;
        context.m_stepConfidences.reserve( chain.m_steps.size() );

        std::string currentOutput = augTask.m_prompt;
        float aggregateConfidence = 1.0f;

        // Execute chain steps sequentially (D-09, D-13)
        for ( const auto& step : chain.m_steps )
        {
            // Look up ELM by role
            auto it = m_elmRegistry.find( step.m_role );
            if ( it == m_elmRegistry.end() || !it->second )
            {
                ServerLogger()->warn( "ELM not found for role {} — skipping step",
                                      static_cast<int>( step.m_role ) );
                continue;
            }

            auto elm = it->second;

            // Lazy-load if not loaded (D-16)
            if ( !elm->IsLoaded() )
            {
                // Check config for a model path for this role
                std::string modelPath;
                for ( const auto& cfg : m_cfg.m_elmConfigs )
                {
                    if ( ParseELMRole( cfg.role ) == step.m_role && !cfg.model.empty() )
                    {
                        modelPath = cfg.model;
                        break;
                    }
                }
                if ( !modelPath.empty() )
                {
                    auto lazyLoad = elm->Load( modelPath );
                    if ( !lazyLoad.has_value() )
                    {
                        ServerLogger()->error( "ELM {} lazy-load failed: {}", elm->GetName(), modelPath );
                        return lazyLoad.as_failure();
                    }
                }
            }

            if ( !elm->IsLoaded() )
            {
                ServerLogger()->warn( "ELM {} not loaded — skipping step", elm->GetName() );
                continue;
            }

            // Execute this step
            auto stepRes = elm->Process( currentOutput, context );
            if ( !stepRes.has_value() )
            {
                ServerLogger()->error( "ELM {} failed — returning error", elm->GetName() );
                return stepRes.as_failure();
            }

            currentOutput = stepRes.value();
            float stepConf = elm->GetConfidence();
            context.m_stepConfidences.push_back( { step.m_role, stepConf } );
            aggregateConfidence = std::min( aggregateConfidence, stepConf );

            ServerLogger()->debug( "Chain step {}: role={} conf={:.2f}",
                                   elm->GetName(), static_cast<int>( step.m_role ), stepConf );
        }

        auto t1 = std::chrono::steady_clock::now();
        double totalMs = std::chrono::duration<double, std::milli>( t1 - t0 ).count();

        // Fact validation
        if ( m_factVal && m_factVal->IsAvailable() && !facts.empty() )
        {
            auto valResult = m_factVal->Validate( currentOutput, facts );
            if ( !valResult.passed_ )
            {
                ServerLogger()->error( "Chain fact validation failed: {}", valResult.suggestion_ );
                return outcome::failure( Error::FactValidationFailed );
            }
        }

        InferenceResponse resp;
        resp.m_output = currentOutput;
        resp.m_taskId = task.m_id;
        resp.m_modeUsed = ExecutionMode::ElmAssisted;
        resp.m_routeUsed = route.m_target;
        resp.m_totalLatencyMs = totalMs;
        resp.m_success = true;
        resp.m_perplexity = 1.0f - aggregateConfidence;

        ServerLogger()->info( "Chain complete: {} steps, {}ms, agg_conf={:.2f}",
                              chain.m_steps.size(), totalMs, aggregateConfidence );
        return outcome::success( std::move( resp ) );
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
            t.m_nodeId = m_identity ? m_identity->GetPeerId() : "local";

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
            case ExecutionMode::ElmAssisted:
                return RunELMChain( t, route );
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

        std::unique_lock<std::mutex> lock( m_stopMutex );
        m_stopCondition.wait( lock, [this] { return !m_running.load(); } );
        return outcome::success();
    }

    void ApiServer::Stop()
    {
        m_running.store( false );
        m_stopCondition.notify_all();
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
