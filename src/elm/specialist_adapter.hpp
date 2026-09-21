/**
 * @file       specialist_adapter.hpp
 * @brief      Composition-based adapter that wraps ISpecialist behind the IELM interface (D-06, D-07)
 * @date       2026-07-17
 */

#ifndef NEOSWARM_ELM_SPECIALIST_ADAPTER_HPP
#define NEOSWARM_ELM_SPECIALIST_ADAPTER_HPP

#include "i_elm.hpp"
#include "specialists/i_specialist.hpp"

#include <memory>
#include <string>

namespace sgns::neoswarm::elm
{
    /**
     * @brief Adapter that maps ISpecialist → IELM via composition.
     *
     * Per D-06 (legacy mapping) and D-07 (composition, not inheritance):
     * - GrammarSpecialist is wrapped as the Refiner/Formatter role ELM
     * - MathSpecialist is wrapped as the Math domain ELM
     *
     * The adapter drops ELMContext when forwarding to ISpecialist::Process(string)
     * since legacy specialists do not accept context.
     */
    class SpecialistAdapter : public IELM
    {
        public:
        /**
         * @brief Construct an adapter for a legacy ISpecialist.
         * @param specialist  The specialist instance to wrap (shared ownership).
         * @param role        The ELM role this adapter fulfills.
         * @param name        Human-readable name for this adapter.
         */
        SpecialistAdapter( std::shared_ptr<specialists::ISpecialist> specialist,
                           ELMRole role,
                           const std::string& name );

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
            return m_specialist && m_specialist->IsLoaded();
        }

        float GetConfidence() const override
        {
            return m_lastConfidence;
        }

        outcome::result<void> Load( const std::string& model_path ) override;

        outcome::result<std::string> Process( const std::string& input, const ELMContext& context ) override;

        private:
        std::shared_ptr<specialists::ISpecialist> m_specialist;
        ELMRole m_role;
        std::string m_name;
        float m_lastConfidence = 0.0f;
    };

} // namespace sgns::neoswarm::elm

#endif // NEOSWARM_ELM_SPECIALIST_ADAPTER_HPP
