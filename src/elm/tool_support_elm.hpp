/**
 * @file       tool_support_elm.hpp
 * @brief      ToolSupportELM — interface-conforming stub (D-18), pass-through with confidence=0
 * @date       2026-07-17
 */

#ifndef NEOSWARM_ELM_TOOL_SUPPORT_ELM_HPP
#define NEOSWARM_ELM_TOOL_SUPPORT_ELM_HPP

#include "i_elm.hpp"
#include "common/types.hpp"

namespace sgns::neoswarm::elm
{
    /**
     * @brief Stub ELM for tool-call formatting (D-18).
     *
     * Per D-18: interface-conforming pass-through stub. Real tool-call
     * formatting requires Phase 10's Tool Intermediary boundary.
     *
     * All calls return input unchanged with confidence=0.0f and
     * IsLoaded()=false. This allows ELM chains that include a
     * ToolSupport step to execute without crashing — consumers
     * check confidence before treating output as augmented.
     */
    class ToolSupportELM : public IELM
    {
        public:
        ToolSupportELM() = default;

        std::string GetName() const override
        {
            return "ToolSupport";
        }

        ELMRole GetRole() const override
        {
            return ELMRole::ToolSupport;
        }

        bool IsLoaded() const override
        {
            return false;
        }

        float GetConfidence() const override
        {
            return m_lastConfidence;
        }

        outcome::result<void> Load( const std::string& model_path ) override;

        outcome::result<std::string> Process( const std::string& input, const ELMContext& context ) override;

        private:
        float m_lastConfidence = 0.0f;
    };

} // namespace sgns::neoswarm::elm

#endif // NEOSWARM_ELM_TOOL_SUPPORT_ELM_HPP
