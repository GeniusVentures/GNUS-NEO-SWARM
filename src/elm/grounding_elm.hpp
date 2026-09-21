/**
 * @file       grounding_elm.hpp
 * @brief      GroundingELM — wraps the 3-stage knowledge pipeline behind IELM (D-17)
 * @date       2026-07-17
 */

#ifndef NEOSWARM_ELM_GROUNDING_ELM_HPP
#define NEOSWARM_ELM_GROUNDING_ELM_HPP

#include "i_elm.hpp"
#include "core/engine/inference_engine.hpp"
#include "knowledge/knowledge_retrieval.hpp"
#include "knowledge/context_injection.hpp"
#include "knowledge/fact_validation.hpp"

#include <memory>
#include <string>

namespace sgns::neoswarm::elm
{
    /**
     * @brief ELM that grounds responses against the Grokipedia knowledge base.
     *
     * Implements a 4-stage pipeline per D-17:
     *   1. Retrieve — query knowledge base for relevant facts
     *   2. Inject   — augment the prompt with retrieved facts
     *   3. Infer    — run inference on the augmented prompt
     *   4. Validate — check output against grounding facts, adjust confidence
     *
     * If the knowledge pipeline is unavailable, the ELM returns input unchanged
     * with zero confidence (fail-close pattern).
     */
    class GroundingELM : public IELM
    {
        public:
        /**
         * @brief Construct a GroundingELM with the full knowledge pipeline.
         * @param engine      Shared inference engine for stage 3.
         * @param knowledge   Knowledge retrieval backend for stage 1.
         * @param contextInj  Context injection for stage 2.
         * @param factVal     Fact validation for stage 4.
         */
        GroundingELM( std::shared_ptr<core::InferenceEngine> engine,
                      std::shared_ptr<knowledge::KnowledgeRetrieval> knowledge,
                      std::unique_ptr<knowledge::ContextInjection> contextInj,
                      std::unique_ptr<knowledge::FactValidation> factVal );

        std::string GetName() const override
        {
            return "Grounding";
        }

        ELMRole GetRole() const override
        {
            return ELMRole::Grounding;
        }

        bool IsLoaded() const override
        {
            return m_loaded;
        }

        float GetConfidence() const override
        {
            return m_lastConfidence;
        }

        outcome::result<void> Load( const std::string& model_path ) override;

        outcome::result<std::string> Process( const std::string& input, const ELMContext& context ) override;

        private:
        std::shared_ptr<core::InferenceEngine> m_engine;
        std::shared_ptr<knowledge::KnowledgeRetrieval> m_knowledge;
        std::unique_ptr<knowledge::ContextInjection> m_contextInj;
        std::unique_ptr<knowledge::FactValidation> m_factVal;
        bool m_loaded = false;
        float m_lastConfidence = 0.0f;
    };

} // namespace sgns::neoswarm::elm

#endif // NEOSWARM_ELM_GROUNDING_ELM_HPP
