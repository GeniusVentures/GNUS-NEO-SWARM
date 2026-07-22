/**
 * @file       domain_elm.hpp
 * @brief      Domain ELM — optional dedicated model with shared-backbone fallback
 * @date       2026-07-16
 */

#ifndef NEOSWARM_ELM_DOMAIN_ELM_HPP
#define NEOSWARM_ELM_DOMAIN_ELM_HPP

#include "i_elm.hpp"
#include "core/engine/inference_engine.hpp"

#include <memory>
#include <string>

namespace sgns::neoswarm::elm
{
    /**
     * @brief Domain-specific ELM (Math, Code, Science) with optional dedicated
     *        .mnn model file.
     *
     * Per D-01/D-02: by default uses the shared MNN backbone; if Load() is called
     * with a non-empty model_path, creates a dedicated MNNInferenceEngine instance
     * and uses that instead.  Fail-close per D-04.
     */
    class DomainELM : public IELM
    {
        public:
        /**
         * @brief Construct a DomainELM for the given domain role.
         * @param role          ELMRole::Math, Code, or Science.
         * @param sharedEngine  Shared inference engine (MNN backbone).  May be
         *                      nullptr for stub/testing; Process will fail-close.
         */
        explicit DomainELM( ELMRole role, std::shared_ptr<core::InferenceEngine> sharedEngine = nullptr );

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

        // GetConfidence() inherited from IELM — m_lastConfidence is set in Process()

        private:
        ELMRole m_role;
        std::string m_name;
        std::shared_ptr<core::InferenceEngine> m_sharedEngine;
        std::unique_ptr<core::InferenceEngine> m_ownEngine;
        bool m_loaded = false;
        bool m_ownsEngine = false;

        /**
         * @brief Build the domain-specific [INST] prompt template around the input.
         * @param input    Text from the prior chain step (or original user prompt).
         * @param context  ELM execution context.
         * @return         Complete prompt string ready for inference.
         */
        std::string BuildPrompt( const std::string& input, const ELMContext& context ) const;

        /**
         * @brief Select the active engine: own if loaded, shared otherwise.
         * @return Pointer to the active engine, or nullptr if neither available.
         */
        core::InferenceEngine* SelectEngine() const noexcept;
    };

} // namespace sgns::neoswarm::elm

#endif // NEOSWARM_ELM_DOMAIN_ELM_HPP
