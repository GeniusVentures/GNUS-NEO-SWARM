/**
 * @file       api_server.hpp
 * @brief      Orchestrates the full inference pipeline (PTDS §9)
 * @date       2026-05-08
 * @author     Subaskar S (ssivakumar@gnus.ai)
 */

#ifndef NEOSWARM_API_GENIUSAPISERVER_HPP_
#define NEOSWARM_API_GENIUSAPISERVER_HPP_

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
    class GeniusAPIServer
    {
        public:
        struct Config
        {
            std::string model_path_;
            std::string grammar_model_path_;
            std::string math_model_path_;
            std::string reputation_db_path_ = "./reputation.db";
            std::string knowledge_facts_ = "";
            bool enable_network_ = false;
            bool enable_knowledge_ = true;
            int grpc_port_ = 50051;
            std::string node_key_file_ = "./node.key";
            bool enable_sg_processing_ = false;
            bool sg_processing_network_mode_ = false;
            std::string sg_endpoint_ = "localhost:50051";
            std::string sg_tls_ca_;
            std::string sg_tls_cert_;
        };

        explicit GeniusAPIServer( Config cfg );
        ~GeniusAPIServer();

        /**
         * @brief Initialise all subsystems.
         * @return outcome::success or the first error encountered.
         */
        outcome::result<void> Initialize();

        /**
         * @brief Process a single inference request (all modes).
         * @param task  Incoming task.
         * @return      GeniusResponse or InferenceFailed.
         */
        outcome::result<GeniusResponse> Process( const Task& task );

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
        std::shared_ptr<core::InferenceEngine> core_engine_;
        std::shared_ptr<specialists::GrammarSpecialist> grammar_spec_;
        std::shared_ptr<specialists::MathSpecialist> math_spec_;
        std::unique_ptr<router::RuleBasedRouter> router_;
        std::unique_ptr<reputation::WeightedConsensus> consensus_;
        std::unique_ptr<reputation::ReputationScoring> scoring_;
        std::unique_ptr<reputation::ReputationStorage> rep_storage_;
        std::unique_ptr<reputation::ReputationCRDT> rep_crdt_;
        std::unique_ptr<network::P2PNode> p2p_node_;
        std::unique_ptr<network::ResultAggregation> aggregation_;
        std::shared_ptr<knowledge::KnowledgeRetrieval> knowledge_;
        std::unique_ptr<knowledge::ContextInjection> context_inj_;
        std::unique_ptr<knowledge::FactValidation> fact_val_;
        std::unique_ptr<network::SuperGeniusClient> sg_client_;

        outcome::result<GeniusResponse> RunSingleNode( const Task& task, const RouteDecision& route );
        outcome::result<GeniusResponse> RunSpecialist( const Task& task, const RouteDecision& route );
        outcome::result<GeniusResponse> RunSwarm( const Task& task, const RouteDecision& route );

        std::string AugmentPrompt( const std::string& prompt, std::vector<KnowledgeFact>& out_facts ) const;

        void UpdateReputation( const InferenceResponse& resp,
                               double median_latency_ms,
                               const std::string& consensus_output );
    };

} // namespace sgns::neoswarm::api

#endif // NEOSWARM_API_GENIUSAPISERVER_HPP_
