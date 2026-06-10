/**
 * @file       types.hpp
 * @brief      Shared data types for the GNUS NEO SWARM engine
 */

#ifndef NEOSWARM_COMMON_TYPES_HPP
#define NEOSWARM_COMMON_TYPES_HPP

#include <chrono>
#include <optional>
#include <string>
#include <unordered_map>
#include <vector>

namespace sgns::neoswarm
{
    // -----------------------------------------------------------------------
    // Execution modes (PTDS §9)
    // -----------------------------------------------------------------------
    enum class ExecutionMode : uint8_t
    {
        SingleNode = 0, ///< Mode 1 — Core LLM only, fast
        Specialist = 1, ///< Mode 2 — Core + Grammar/Math, sequential
        Swarm = 2       ///< Mode 3 — Multiple nodes, weighted consensus
    };

    // -----------------------------------------------------------------------
    // Routing targets (PTDS §6)
    // -----------------------------------------------------------------------
    enum class RouteTarget : uint8_t
    {
        CoreOnly = 0,
        CorePlusMath = 1,
        CorePlusGrammar = 2,
        CorePlusCode = 3 ///< Future
    };

    // -----------------------------------------------------------------------
    // A task coming in from a client
    // -----------------------------------------------------------------------
    struct Task
    {
        std::string id_;
        std::string prompt_;
        ExecutionMode mode_ = ExecutionMode::SingleNode;
        uint32_t max_tokens_ = 512;
        float temperature_ = 0.7f;
        std::string node_id_; ///< originating node
    };

    // -----------------------------------------------------------------------
    // What each node returns after inference
    // -----------------------------------------------------------------------
    struct InferenceResponse
    {
        std::string output_;
        std::string task_id_;
        ExecutionMode mode_used_ = ExecutionMode::SingleNode;
        RouteTarget route_used_ = RouteTarget::CoreOnly;
        double total_latency_ms_ = 0.0;
        float perplexity_ = 1.0f; ///< model confidence (lower = better)
        double latency_ms_ = 0.0;
        std::string node_id_;
        bool success_ = true;
        std::string error_message_;
    };

    // -----------------------------------------------------------------------
    // Routing decision produced by the router
    // -----------------------------------------------------------------------
    struct RouteDecision
    {
        RouteTarget target_ = RouteTarget::CoreOnly;
        float confidence_ = 1.0f;
        std::string reasoning_;
        ExecutionMode mode_ = ExecutionMode::SingleNode;
    };

    // -----------------------------------------------------------------------
    // Prompt analysis features (PTDS §6.1)
    // -----------------------------------------------------------------------
    struct PromptFeatures
    {
        float numeric_density_ = 0.0f; ///< ratio of numeric tokens
        bool has_code_syntax_ = false;
        float complexity_ = 0.0f; ///< token count / vocab diversity
        size_t token_count_ = 0;
        bool has_math_keywords_ = false;
        bool has_grammar_request_ = false;
    };

    // -----------------------------------------------------------------------
    // Node output used in consensus
    // -----------------------------------------------------------------------
    struct NodeOutput
    {
        std::string node_id_;
        std::string output_;
        float perplexity_ = 1.0f;
        double latency_ms_ = 0.0;
        double reputation_ = 0.5;
    };

    // -----------------------------------------------------------------------
    // Reputation data model (PTDS §7.1)
    // -----------------------------------------------------------------------
    struct NodeReputation
    {
        std::string identity_key_;
        double global_score_ = 0.5;
        double math_score_ = 0.5;
        double grammar_score_ = 0.5;
        double latency_score_ = 0.5;
        double consistency_score_ = 0.5;
        uint64_t task_count_ = 0;
        uint64_t last_updated_ms_ = 0; ///< Unix epoch ms

        /// Minimum tasks before high-trust (anti-gaming)
        static constexpr uint64_t kMinTasksForHighTrust = 10;
    };

    // -----------------------------------------------------------------------
    // Grokipedia fact entry
    // -----------------------------------------------------------------------
    struct KnowledgeFact
    {
        std::string source_;
        std::string content_;
        float relevance_score_ = 0.0f;
    };

    // -----------------------------------------------------------------------
    // Final API response
    // -----------------------------------------------------------------------
    

} // namespace sgns::neoswarm

#endif // NEOSWARM_COMMON_TYPES_HPP
