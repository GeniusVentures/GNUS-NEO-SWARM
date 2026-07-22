/**
 * @file       rule_based_router.hpp
 * @brief      Rule-based prompt router (PTDS §6.1)
 * @date       2026-05-06
 */

#ifndef NEOSWARM_ROUTER_RULEBASEDROUTER_HPP
#define NEOSWARM_ROUTER_RULEBASEDROUTER_HPP

#include "i_router.hpp"
#include "prompt_analyzer.hpp"

namespace sgns::neoswarm::router
{
    /**
     * @brief MVP rule-based routing (PTDS §6.1).
     *
     * Decision tree:
     *   numeric_density > threshold  OR  has_math_keywords  → CorePlusMath
     *   has_grammar_request                                  → CorePlusGrammar
     *   has_code_syntax                                      → CoreOnly (future: CorePlusCode)
     *   else                                                 → CoreOnly
     */
    class RuleBasedRouter : public IRouter
    {
        public:
        struct Config
        {
            float numeric_density_threshold_ = 0.30f;
            float complexity_swarm_threshold_ = 5.0f;
            bool enable_swarm_m_mode = true;
        };

        RuleBasedRouter();
        explicit RuleBasedRouter( Config cfg );

        /**
         * @brief Route a task to the appropriate execution mode and specialist.
         * @param task  Incoming task.
         * @return      RouteDecision on success, Error on failure.
         */
        outcome::result<RouteDecision> Route( const Task& task ) override;

        private:
        Config m_cfg;
        PromptAnalyzer m_analyzer;

        /**
         * @brief Select execution mode based on prompt features and explicit request.
         * @param features   Extracted prompt features.
         * @param requested  Mode explicitly requested by the caller.
         * @return           Selected ExecutionMode.
         */
        ExecutionMode SelectMode( const PromptFeatures& features, ExecutionMode requested ) const;
    };

} // namespace sgns::neoswarm::router

#endif // NEOSWARM_ROUTER_RULEBASEDROUTER_HPP
