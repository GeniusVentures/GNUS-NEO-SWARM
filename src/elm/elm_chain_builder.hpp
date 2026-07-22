/**
 * @file       elm_chain_builder.hpp
 * @brief      Maps RouteDecision + PromptFeatures to ExecutionChain (doc 03 §6.2)
 * @date       2026-07-17
 */

#ifndef NEOSWARM_ELM_ELM_CHAIN_BUILDER_HPP
#define NEOSWARM_ELM_ELM_CHAIN_BUILDER_HPP

#include "common/error.hpp"
#include "common/types.hpp"

namespace sgns::neoswarm::elm
{
    /**
     * @brief Stateless chain builder that maps routing decisions and prompt features
     *        to an ordered ExecutionChain using 6 heuristic triggers (doc 03 §6.2).
     *
     * Per D-11, this is a separate class from RuleBasedRouter. The router continues
     * producing RouteDecision; the chain builder translates that into an ExecutionChain.
     */
    class ELMChainBuilder
    {
        public:
        struct Config
        {
            float numeric_density_threshold_ = 0.30f;
            float complexity_high_threshold_ = 5.0f;
            float complexity_low_threshold_ = 2.0f;
            float confidence_threshold_ = 0.6f;
        };

        ELMChainBuilder();
        explicit ELMChainBuilder( Config cfg );

        /**
         * @brief Build an ExecutionChain from a route decision and prompt features.
         * @param decision   The route decision produced by the router.
         * @param features   Prompt features extracted by PromptAnalyzer.
         * @return           ExecutionChain on success, or error.
         */
        ExecutionChain Build( const RouteDecision& decision, const PromptFeatures& features );

        private:
        Config m_cfg;
    };

} // namespace sgns::neoswarm::elm

#endif // NEOSWARM_ELM_ELM_CHAIN_BUILDER_HPP
