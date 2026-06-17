/**
 * @file       api_server.hpp
 * @brief      Orchestrates the full inference pipeline (PTDS §9)
 * @date       2026-05-08
 * @author     Subaskar S (ssivakumar@gnus.ai)
 */

#ifndef NEOSWARM_API_GENIUSAPISERVER_HPP
#define NEOSWARM_API_GENIUSAPISERVER_HPP

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
#include <atomic>
#include <memory>
#include <string>

namespace sgns::neoswarm::network
{
    class SuperGeniusClient;
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
            std::string grammar_m_modelPath;
            std::string math_m_modelPath;
            std::string m_reputationDbPath = "./reputation.db";
            std::string m_knowledgefacts_ = "";
            bool m_enableNetwork = false;
            bool m_enableKnowledge = true;
            int m_grpcPort = 50051;
            std::string m_nodeKeyFile = "./node.key";
            std::string m_nodeKeyPassphrase = "gnus-neo-swarm-default";
            bool m_enableSgProcessing = false;
            bool sg_processing_m_networkMode = false;
            std::string sg_m_endpoint = "localhost:50051";
            std::string m_sgTlsCa;
            std::string m_sgTlsCert;
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

        private:
        Config m_cfg;
        std::atomic<bool> m_running{ false };

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
#ifdef GENIUS_HAS_GRPC
        std::unique_ptr<network::SuperGeniusClient> m_sgClient;
#endif

        outcome::result<InferenceResponse> RunSingleNode( const Task& task, const RouteDecision& route );
        outcome::result<InferenceResponse> RunSpecialist( const Task& task, const RouteDecision& route );
        outcome::result<InferenceResponse> RunSwarm( const Task& task, const RouteDecision& route );

        std::string AugmentPrompt( const std::string& prompt, std::vector<KnowledgeFact>& out_facts ) const;

        void UpdateReputation( const InferenceResponse& resp,
                               double median_latency_ms,
                               const std::string& m_consensusoutput );
    };

} // namespace sgns::neoswarm::api

#endif // NEOSWARM_API_GENIUSAPISERVER_HPP
