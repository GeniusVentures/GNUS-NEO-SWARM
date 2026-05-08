/**
 * @file       ISpecialist.hpp
 * @brief      Abstract interface for all specialist modules (PTDS §5.2)
 * @date       2026-05-06
 * @author     Subaskar S (ssivakumar@gnus.ai)
 */

#ifndef NEOSWARM_SPECIALISTS_ISPECIALIST_HPP_
#define NEOSWARM_SPECIALISTS_ISPECIALIST_HPP_

#include "common/Error.hpp"
#include <string>

namespace sgns::neoswarm::specialists
{
    /**
     * @brief Abstract interface for specialist post-processing modules.
     *
     * Each specialist takes Core LLM output and refines it for a specific domain.
     */
    class ISpecialist
    {
    public:
        virtual ~ISpecialist() = default;

        /// @return Human-readable name of this specialist.
        virtual std::string GetName() const = 0;

        /// @return True if the specialist model has been loaded.
        virtual bool IsLoaded() const = 0;

        /**
         * @brief Load the specialist model from disk.
         * @param model_path  Path to the model file.
         * @return            outcome::success or ModelLoadFailed.
         */
        virtual outcome::result<void> Load( const std::string &model_path ) = 0;

        /**
         * @brief Process input (typically Core LLM output) and return refined output.
         * @param input  Text to process.
         * @return       Refined text or InferenceFailed.
         */
        virtual outcome::result<std::string> Process( const std::string &input ) = 0;

        /**
         * @brief Confidence in the last Process() call.
         * @return  Confidence score in [0, 1].
         */
        virtual float GetConfidence() const = 0;
    };

} // namespace sgns::neoswarm::specialists

#endif // NEOSWARM_SPECIALISTS_ISPECIALIST_HPP_
