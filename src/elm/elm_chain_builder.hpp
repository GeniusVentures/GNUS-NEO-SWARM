/**
 * @file       elm_chain_builder.hpp
 * @brief      ELMChainBuilder stub — will be implemented in GREEN phase
 * @date       2026-07-17
 */

#ifndef NEOSWARM_ELM_ELM_CHAIN_BUILDER_HPP
#define NEOSWARM_ELM_ELM_CHAIN_BUILDER_HPP

#include "common/error.hpp"
#include "common/types.hpp"

namespace sgns::neoswarm::elm
{
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

        outcome::result<ExecutionChain> Build( const RouteDecision& decision, const PromptFeatures& features );

        private:
        Config m_cfg;
    };

} // namespace sgns::neoswarm::elm

#endif // NEOSWARM_ELM_ELM_CHAIN_BUILDER_HPP
