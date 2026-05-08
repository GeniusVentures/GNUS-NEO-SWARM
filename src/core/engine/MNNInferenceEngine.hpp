/**
 * @file       MNNInferenceEngine.hpp
 * @brief      MNN-backed inference engine with FP4 and SGProcessing support
 * @date       2026-05-06
 * @author     Subaskar S (ssivakumar@gnus.ai)
 */

#ifndef NEOSWARM_CORE_ENGINE_MNNINFERENCEENGINE_HPP_
#define NEOSWARM_CORE_ENGINE_MNNINFERENCEENGINE_HPP_

#include "InferenceEngine.hpp"
#include "core/fp4/FP4Codec.hpp"
#include "core/tokenizer/Tokenizer.hpp"
#include "core/sgprocessing/SGProcessingBridge.hpp"
#include "core/sgprocessing/TensorInterpreter.hpp"
#include <atomic>
#include <memory>
#include <string>

namespace MNN
{
class Interpreter;
class Session;
} // namespace MNN

namespace boost::asio
{
class io_context;
} // namespace boost::asio

namespace sgns
{
enum class InputFormat : int;
} // namespace sgns

namespace sgns::neoswarm::core
{
    /**
     * @brief MNN-backed inference engine.
     *
     * Wraps MNN::Interpreter + MNN::Session.
     * Integrates FP4Codec for weight decompression at load time.
     * Uses Vulkan/MoltenVK backend when available, falls back to CPU.
     * Optionally delegates to SGProcessingManager for GNUS network dispatch.
     */
    class MNNInferenceEngine : public InferenceEngine
    {
    public:
        struct Config
        {
            bool  use_gpu_           = true;   ///< prefer Vulkan/MoltenVK
            bool  use_fp4_           = true;   ///< decompress FP4 weights at load
            bool  use_sg_processing_ = false;  ///< delegate to SGProcessingManager
            int   num_threads_       = 4;      ///< CPU thread count (fallback)
            int   max_new_tokens_    = 512;
            float temperature_       = 0.7f;
            float top_p_             = 0.9f;
            int   top_k_             = 40;
            float repetition_penalty_ = 1.1f;
        };

        MNNInferenceEngine();
        explicit MNNInferenceEngine( Config cfg );
        ~MNNInferenceEngine() override;

        outcome::result<void>              LoadModel( const std::string &model_path ) override;
        outcome::result<InferenceResponse> Infer( const Task &task ) override;
        outcome::result<void>              StreamInfer(
            const Task                                    &task,
            std::function<void( const std::string &token )> callback ) override;

        bool        IsLoaded()    const override { return loaded_.load(); }
        std::string BackendName() const override;

        /**
         * @brief Attach a tokenizer (must be set before inference).
         * @param tok  Tokenizer instance.
         */
        void SetTokenizer( std::shared_ptr<Tokenizer> tok )
        {
            tokenizer_ = std::move( tok );
        }

        /// Mark engine as loaded in stub/test mode (no real model file needed).
        void SetStubMode()
        {
            loaded_.store( true );
        }

    private:
        Config                            cfg_;
        std::shared_ptr<MNN::Interpreter> interpreter_;
        MNN::Session                     *session_    = nullptr;
        std::atomic<bool>                 loaded_     = false;
        std::string                       model_path_;
        std::shared_ptr<Tokenizer>        tokenizer_;
        fp4::FP4Codec                     fp4_codec_;

        std::unique_ptr<SGProcessingBridge>              bridge_;
        std::unique_ptr<TensorInterpreter>               tensor_interpreter_;
        std::shared_ptr<boost::asio::io_context>         ioc_;

        int    SelectBackend() const;
        outcome::result<std::vector<float>> RunForward( const std::vector<int> &input_ids );
        int    SampleToken( const std::vector<float> &logits,
                            float temperature, float top_p, int top_k ) const;
        void   ApplyRepetitionPenalty( std::vector<float>       &logits,
                                       const std::vector<int>   &generated,
                                       float                     penalty ) const;
    };

} // namespace sgns::neoswarm::core

#endif // NEOSWARM_CORE_ENGINE_MNNINFERENCEENGINE_HPP_
