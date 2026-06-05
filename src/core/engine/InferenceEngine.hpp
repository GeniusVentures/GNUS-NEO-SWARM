/**
 * @file       InferenceEngine.hpp
 * @brief      Abstract inference engine interface
 * @date       2026-05-06
 * @author     Subaskar S (ssivakumar@gnus.ai)
 */

#ifndef NEOSWARM_CORE_ENGINE_INFERENCEENGINE_HPP_
#define NEOSWARM_CORE_ENGINE_INFERENCEENGINE_HPP_

#include "common/Error.hpp"
#include "common/Types.hpp"
#include <functional>
#include <string>

namespace sgns::neoswarm::core
{
    /**
     * @brief Abstract interface for all inference backends.
     */
    class InferenceEngine
    {
        public:
        virtual ~InferenceEngine() = default;

        /**
         * @brief Load a model from disk (MNN .mnn file or similar).
         * @param model_path  Path to the model file.
         * @return            outcome::success or ModelLoadFailed.
         */
        virtual outcome::result<void> LoadModel( const std::string& model_path ) = 0;

        /**
         * @brief Synchronous inference — returns the full generated output.
         * @param task  Inference task with prompt and generation parameters.
         * @return      InferenceResponse or InferenceFailed.
         */
        virtual outcome::result<InferenceResponse> Infer( const Task& task ) = 0;

        /**
         * @brief Streaming inference — calls callback for each generated token.
         * @param task      Inference task.
         * @param callback  Called with each token string as it is generated.
         * @return          outcome::success or InferenceFailed.
         */
        virtual outcome::result<void> StreamInfer( const Task& task,
                                                   std::function<void( const std::string& token )> callback ) = 0;

        /// @return True if a model has been loaded.
        virtual bool IsLoaded() const = 0;

        /// @return Human-readable backend name (e.g. "MNN/Vulkan", "MNN/CPU").
        virtual std::string BackendName() const = 0;
    };

} // namespace sgns::neoswarm::core

#endif // NEOSWARM_CORE_ENGINE_INFERENCEENGINE_HPP_
