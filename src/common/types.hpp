/**
 * @file       types.hpp
 * @brief      Shared data types for the GNUS NEO SWARM engine
 */

#ifndef NEOSWARM_COMMON_TYPES_HPP
#define NEOSWARM_COMMON_TYPES_HPP

#include <chrono>
#include <nlohmann/json.hpp>
#include <optional>
#include <string>
#include <unordered_map>
#include <utility>
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
        Swarm = 2,      ///< Mode 3 — Multiple nodes, weighted consensus
        ElmAssisted = 3 ///< Mode 2 (doc 07 §9.2) — ELM-assisted sequential chain (Phase 7+)
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
    // ELM roles (doc 03 §5.2.1) — Phase 7
    // -----------------------------------------------------------------------
    enum class ELMRole : uint8_t
    {
        Planner = 0,      ///< Analyses task, determines execution plan
        PrimaryDraft = 1, ///< Core draft generation (shared backbone)
        Verifier = 2,     ///< Reviews outputs for correctness
        Arbiter = 3,      ///< Resolves conflicts between outputs
        Refiner = 4,      ///< Polishes formatting, style, grammar
        Grounding = 5,    ///< Fact-checks against knowledge base
        ToolSupport = 6,  ///< Tool-call formatting (stub in Phase 7)
        Math = 7,         ///< Domain ELM — math
        Code = 8,         ///< Domain ELM — code
        Science = 9       ///< Domain ELM — science (shared-backbone only)
    };

    // -----------------------------------------------------------------------
    // Memory object types (GAML v1 — Phase 8 — per D-02)
    // -----------------------------------------------------------------------
    enum class MemoryObjectType : uint8_t
    {
        bridge_block = 0,       ///< Memory bridge block
        fact = 1,               ///< Declarative fact
        policy = 2,             ///< Behavioral policy / rule
        event = 3,              ///< Temporal event record
        tenant_operational = 4  ///< Tenant operational data
    };

    /// Trust classification for memory objects (GAML v1 — per D-01, D-09)
    enum class TrustClass : uint8_t
    {
        unverified = 0,     ///< Default privacy stub (D-09)
        verified = 1,       ///< Fact-validated
        premium = 2,        ///< Premium tier
        replica = 3         ///< Replicated from remote
    };

    // -----------------------------------------------------------------------
    // A task coming in from a client
    // -----------------------------------------------------------------------
    struct Task
    {
        std::string m_id;
        std::string m_prompt;
        ExecutionMode m_mode = ExecutionMode::SingleNode;
        uint32_t m_maxTokens = 512;
        float m_temperature = 0.7f;
        std::string m_nodeId; ///< originating node
    };

    // -----------------------------------------------------------------------
    // What each node returns after inference
    // -----------------------------------------------------------------------
    struct InferenceResponse
    {
        std::string m_output;
        std::string m_taskId;
        ExecutionMode m_modeUsed = ExecutionMode::SingleNode;
        RouteTarget m_routeUsed = RouteTarget::CoreOnly;
        double m_totalLatencyMs = 0.0;
        float m_perplexity = 1.0f;
        double m_latencyMs = 0.0;
        std::string m_nodeId;
        bool m_success = true;
        std::string m_errorMessage;
    };

    // -----------------------------------------------------------------------
    // Routing decision produced by the router
    // -----------------------------------------------------------------------
    struct RouteDecision
    {
        RouteTarget m_target = RouteTarget::CoreOnly;
        float confidence_ = 1.0f;
        std::string m_reasoning;
        ExecutionMode m_mode = ExecutionMode::SingleNode;
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
        bool has_grounding_request_ = false;    ///< factual verification request detected (Phase 7)
        bool has_formatting_request_ = false;   ///< structure/style formatting request detected (Phase 7)
    };

    // -----------------------------------------------------------------------
    // Node output used in consensus
    // -----------------------------------------------------------------------
    struct NodeOutput
    {
        std::string m_nodeId;
        std::string m_output;
        float m_perplexity = 1.0f;
        double m_latencyMs = 0.0;
        double reputation_ = 0.5;
    };

    // -----------------------------------------------------------------------
    // Reputation data model (PTDS §7.1)
    // -----------------------------------------------------------------------
    struct NodeReputation
    {
        std::string m_identityKey;
        double m_globalScore = 0.5;
        double m_mathScore = 0.5;
        double m_grammarScore = 0.5;
        double m_latencyScore = 0.5;
        double m_consistencyScore = 0.5;
        uint64_t m_taskCount = 0;
        uint64_t m_lastUpdatedMs = 0; ///< Unix epoch ms

        /// Minimum tasks before high-trust (anti-gaming)
        static constexpr uint64_t kMinTasksForHighTrust = 10;
    };

    // -----------------------------------------------------------------------
    // Grokipedia fact entry
    // -----------------------------------------------------------------------
    struct KnowledgeFact
    {
        std::string m_source;
        std::string m_content;
        float m_relevanceScore = 0.0f;
    };

    // -----------------------------------------------------------------------
    // ELM execution context (Phase 7 — doc 03 §5.2.1)
    //
    // The previous chain step's output is carried exclusively by the `input`
    // parameter of IELM::Process(input, context) — no double-accounting
    // via a context field (per review WR-01).
    // -----------------------------------------------------------------------
    struct ELMContext
    {
        std::string m_originalTask;                                   ///< the user's original prompt
        std::vector<std::pair<ELMRole, float>> m_stepConfidences;     ///< (role, confidence) per completed step
        std::vector<KnowledgeFact> m_groundingFacts;                  ///< facts from GroundingELM, if any
    };

    // -----------------------------------------------------------------------
    // Chain step and execution chain (Phase 7 — doc 03 §6.2)
    // -----------------------------------------------------------------------
    struct ChainStep
    {
        ELMRole m_role = ELMRole::PrimaryDraft;
        std::optional<std::string> m_domain; ///< e.g. "math", "code" — for domain ELMs
    };

    struct ExecutionChain
    {
        std::vector<ChainStep> m_steps;
        std::string m_reasoning;          ///< why this chain was chosen
        float m_chainConfidence = 0.0f;   ///< builder's confidence in this chain
    };

    // -----------------------------------------------------------------------
    // Final API response
    // -----------------------------------------------------------------------
    

} // namespace sgns::neoswarm

#endif // NEOSWARM_COMMON_TYPES_HPP
