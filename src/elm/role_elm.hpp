/**
 * @file       role_elm.hpp
 * @brief      Shared-backbone Role ELM — implements IELM with role-specific prompt templates
 * @date       2026-07-16
 */

#ifndef NEOSWARM_ELM_ROLE_ELM_HPP
#define NEOSWARM_ELM_ROLE_ELM_HPP

#include "i_elm.hpp"
#include "core/engine/inference_engine.hpp"

#include <memory>
#include <string>

namespace sgns::neoswarm::elm
{
    /**
     * @brief Role-based ELM using the shared MNN backbone with a role-specific
     *        prompt template.
     *
     * Implements the 7 role-based ELMs (Planner, PrimaryDraft, Verifier, Arbiter,
     * Refiner, Grounding, ToolSupport) behind the IELM interface.  Each instance
     * selects its prompt template at construction time (D-03 — templates are
     * named constants, not user-editable config).
     */
    class RoleELM : public IELM
    {
        public:
        /**
         * @brief Construct a RoleELM for the given role.
         * @param role    The ELM role this instance fulfills.
         * @param engine  Shared inference engine (MNN backbone).  May be nullptr
         *                for stub/testing; Process will fail-close.
         */
        explicit RoleELM( ELMRole role, std::shared_ptr<core::InferenceEngine> engine = nullptr );

        std::string GetName() const override
        {
            return m_name;
        }
        ELMRole GetRole() const override
        {
            return m_role;
        }
        bool IsLoaded() const override
        {
            return m_loaded;
        }

        outcome::result<void> Load( const std::string& model_path ) override;
        outcome::result<std::string> Process( const std::string& input, const ELMContext& context ) override;
        float GetConfidence() const override
        {
            return m_lastConfidence;
        }

        private:
        ELMRole m_role;
        std::string m_name;
        std::shared_ptr<core::InferenceEngine> m_engine;
        bool m_loaded = false;
        float m_lastConfidence = 0.0f;

        /**
         * @brief Build the role-specific [INST] prompt template around the input.
         * @param input    Text from the prior chain step (or original user prompt).
         * @param context  ELM execution context (original task, step confidences).
         * @return         Complete prompt string ready for inference.
         */
        std::string BuildPrompt( const std::string& input, const ELMContext& context ) const;
    };

} // namespace sgns::neoswarm::elm

#endif // NEOSWARM_ELM_ROLE_ELM_HPP
