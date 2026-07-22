/**
 * @file       i_elm.hpp
 * @brief      Abstract interface for Expert Language Models (doc 03 §5.2)
 * @date       2026-07-16
 */

#ifndef NEOSWARM_ELM_IELM_HPP
#define NEOSWARM_ELM_IELM_HPP

#include "common/error.hpp"
#include "common/types.hpp"

#include <string>

namespace sgns::neoswarm::elm
{
    /**
     * @brief Abstract interface for Expert Language Models.
     *
     * Each ELM provides a specific cognitive role in a multi-step chain.
     * Implementations are swappable per doc 03 §5.2.1.
     */
    class IELM
    {
        public:
        virtual ~IELM() = default;

        /// @return Human-readable name of this ELM.
        virtual std::string GetName() const = 0;

        /// @return The ELM role this instance fulfills.
        virtual ELMRole GetRole() const = 0;

        /// @return True if the ELM model has been loaded.
        virtual bool IsLoaded() const = 0;

        /**
         * @brief Load the ELM model from disk (if a dedicated model path is configured).
         * @param model_path  Path to the model file (.mnn or similar).
         * @return            outcome::success or ModelLoadFailed.
         */
        virtual outcome::result<void> Load( const std::string& model_path ) = 0;

        /**
         * @brief Process input through this ELM and return refined output.
         * @param input    Text to process (typically output of previous chain step).
         * @param context  ELM execution context (original task, prior outputs, confidences).
         * @return         Refined text or InferenceFailed.
         */
        virtual outcome::result<std::string> Process( const std::string& input, const ELMContext& context ) = 0;

        /**
         * @brief Confidence in the last Process() call.
         * @return  Confidence score in [0, 1].
         *
         * Default implementation returns a protected m_lastConfidence field.
         * RoleELM and DomainELM set this in Process() and inherit the getter.
         * Specialists that use the adapter pattern override for legacy ISpecialist.
         */
        virtual float GetConfidence() const
        {
            return m_lastConfidence;
        }

        protected:
        float m_lastConfidence = 0.0f;
    };

} // namespace sgns::neoswarm::elm

#endif // NEOSWARM_ELM_IELM_HPP
