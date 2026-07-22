/**
 * @file       api_server.hpp
 * @brief      Orchestrates the full inference pipeline (PTDS §9)
 * @date       2026-05-08
 */

#ifndef NEOSWARM_API_SERVER_HPP
#define NEOSWARM_API_SERVER_HPP

#include "common/error.hpp"
#include "common/types.hpp"
#include "core/engine/inference_engine.hpp"
#include "knowledge/context_injection.hpp"
#include "knowledge/fact_validation.hpp"
#include "knowledge/knowledge_retrieval.hpp"
#include "network/p2p_node.hpp"
#include "network/result_aggregation.hpp"
#include "reputation/reputation_crdt.hpp"
#include "reputation/reputation_scoring.hpp"
#include "reputation/reputation_storage.hpp"
#include "reputation/weighted_consensus.hpp"
#include "router/rule_based_router.hpp"
#include "security/node_identity.hpp"
#include "specialists/grammar_specialist.hpp"
#include "specialists/math_specialist.hpp"
#include "elm/i_elm.hpp"
#include "elm/elm_chain_builder.hpp"
#include "router/prompt_analyzer.hpp"
#include <atomic>
#include <condition_variable>
#include <memory>
#include <mutex>
#include <string>
#include <unordered_map>
#include <vector>

namespace sgns::neoswarm::network
{
    class SGClient;
}

namespace sgns::neoswarm::api
{
    /**
     * @brief Orchestrates the full inference pipeline.
     *
     * Mode 1 (SingleNode): API → Router → Core LLM → Response
     * Mode 2 (Specialist): API → Router → Core → Specialist → Response
     * Mode 3 (Swarm):      API → Router → Broadcast → [Nodes] → Consensus
     *                           → Grokipedia Validation → Response
     */
    class ApiServer
    {
        public:
        struct Config
        {
            std::string m_modelPath;
            std::string m_grammarModelPath;
            std::string m_mathModelPath;
            std::string m_reputationDbPath = "./reputation.db";
            std::string m_knowledgeFacts = "";
            bool m_enableNetwork = false;
            bool m_enableKnowledge = true;
            int m_grpcPort = 50051;
            std::string m_nodeKeyFile = "./node.key";
            std::string m_nodeKeyPassphrase = "gnus-neo-swarm-default";
            bool m_enableSgProcessing = false;
            bool m_sgProcessingNetworkMode = false;
            std::string m_sgSdkBasePath = "./sdk";
            uint16_t m_sgBasePort = 40001;

            // ELM configuration (Phase 7+)
            struct ElmEntry
            {
                std::string role;     ///< e.g. "planner", "verifier", "math"
                std::string model;    ///< optional dedicated model path
                bool eager = false;   ///< load at Initialize() vs lazy
            };
            std::vector<ElmEntry> m_elmConfigs;
        };

        explicit ApiServer( Config cfg );
        ~ApiServer();

        /**
         * @brief Initialise all subsystems.
         * @return outcome::success or the first error encountered.
         */
        outcome::result<void> Initialize();

        /**
         * @brief Process a single inference request (all modes).
         * @param task  Incoming task.
         * @return      InferenceResponse or InferenceFailed.
         */
        outcome::result<InferenceResponse> Process( const Task& task );

        /**
         * @brief Start the gRPC server (blocks until Stop() is called).
         * @return outcome::success or NetworkError.
         */
        outcome::result<void> Serve();

        /// Stop the server and release all resources.
        void Stop();

        /// @return True if the server is currently running.
        bool IsRunning() const
        {
            return m_running.load();
        }

        /// @return True if connected to SuperGenius network.
        bool IsSuperGeniusConnected() const noexcept;

        /// @return True if SuperGenius network mode was enabled in config.
        bool IsSuperGeniusNetworkEnabled() const noexcept
        {
            return m_cfg.m_sgProcessingNetworkMode;
        }

        private:
        Config m_cfg;
        std::atomic<bool> m_running{ false };
        std::condition_variable m_stopCondition;
        std::mutex m_stopMutex;

        std::shared_ptr<security::NodeIdentity> m_identity;
        std::shared_ptr<core::InferenceEngine> m_coreEngine;
        std::shared_ptr<specialists::GrammarSpecialist> m_grammarSpec;
        std::shared_ptr<specialists::MathSpecialist> m_mathSpec;
        std::unique_ptr<router::RuleBasedRouter> m_router;
        std::unique_ptr<reputation::WeightedConsensus> m_consensus;
        std::unique_ptr<reputation::ReputationScoring> m_scoring;
        std::unique_ptr<reputation::ReputationStorage> m_repStorage;
        std::unique_ptr<reputation::ReputationCRDT> m_repCrdt;
        std::unique_ptr<network::P2PNode> m_p2pNode;
        std::unique_ptr<network::ResultAggregation> m_aggregation;
        std::shared_ptr<knowledge::KnowledgeRetrieval> m_knowledge;
        std::unique_ptr<knowledge::ContextInjection> m_contextInj;
        std::unique_ptr<knowledge::FactValidation> m_factVal;
        std::unique_ptr<network::SGClient> m_sgClient;

        // ELM subsystem (Phase 7+)
        std::unordered_map<ELMRole, std::shared_ptr<elm::IELM>> m_elmRegistry;
        std::unique_ptr<elm::ELMChainBuilder> m_chainBuilder;
        std::unique_ptr<router::PromptAnalyzer> m_promptAnalyzer;

        outcome::result<InferenceResponse> RunSingleNode( const Task& task, const RouteDecision& route );
        outcome::result<InferenceResponse> RunSpecialist( const Task& task, const RouteDecision& route );
        outcome::result<InferenceResponse> RunSwarm( const Task& task, const RouteDecision& route );
        outcome::result<InferenceResponse> RunELMChain( const Task& task, const RouteDecision& route );

        void InitializeEngine();
        void InitializeNetwork();

        std::string AugmentPrompt( const std::string& prompt, std::vector<KnowledgeFact>& out_facts ) const;

        void UpdateReputation( const InferenceResponse& resp,
                               double median_latency_ms,
                               const std::string& m_consensusoutput );
    };

} // namespace sgns::neoswarm::api

#endif // NEOSWARM_API_SERVER_HPP
