/**
 * @file       MNNInferenceEngine.hpp
 * @brief      MNN-backed inference engine — cross-platform, config-driven
 * @date       2026-05-06
 * @author     Subaskar S (ssivakumar@gnus.ai)
 *
 * Design:
 *   - Backend selection (Vulkan/CPU) is runtime config, not compile-time.
 *   - SGProcessing is the primary inference path (Phase 1 local, Phase 2 network).
 *   - MNN Interpreter is a fallback for standard single-file .mnn models.
 *   - No platform-specific code (Metal, Apple frameworks, etc.).
 *   - All GPU acceleration goes through Vulkan (MoltenVK on macOS/iOS).
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
     * @brief MNN-backed inference engine with composable configuration.
     *
     * Inference paths (selected at runtime via Config::engine_mode_):
     *
     *   "sgprocessing" — Primary path. Routes through SGProcessingManager
     *                    which handles model loading, chunking, and execution.
     *                    Cross-platform. Network-ready (Phase 2).
     *
     *   "interpreter"  — Fallback. Uses MNN::Interpreter directly for
     *                    standard single-file .mnn models. Requires the
     *                    external SentencePieceTokenizer to be attached.
     *
     * GPU backend (selected at runtime via Config::backend_):
     *
     *   "vulkan" — Vulkan (cross-platform). MoltenVK translates to Metal on Apple.
     *   "cpu"    — CPU-only fallback.
     */
    class MNNInferenceEngine : public InferenceEngine
    {
    public:
        struct Config
        {
            /// Inference path: "sgprocessing" (primary) or "interpreter" (fallback)
            std::string engine_mode_       = "sgprocessing";

            /// GPU backend: "vulkan" (cross-platform) or "cpu"
            std::string backend_           = "vulkan";

            /// Use FP4 quantization for SGProcessing path
            bool  use_fp4_                 = true;

            /// CPU thread count (used when backend_ == "cpu")
            int   num_threads_             = 4;

            /// Generation parameters
            int   max_new_tokens_          = 512;
            float temperature_             = 0.7f;
            float top_p_                   = 0.9f;
            int   top_k_                   = 40;
            float repetition_penalty_      = 1.1f;

            /// SGProcessing network mode (Phase 2: dispatch via gRPC to SuperGenius)
            bool  sg_network_mode_         = false;
        };

        MNNInferenceEngine();
        explicit MNNInferenceEngine( Config cfg );
        ~MNNInferenceEngine() override;

        outcome::result<void>              LoadModel( const std::string &model_path ) override;
        outcome::result<InferenceResponse> Infer( const Task &task ) override;
        outcome::result<void>              StreamInfer(
            const Task                                       &task,
            std::function<void( const std::string &token )>  callback ) override;

        bool        IsLoaded()    const override { return loaded_.load(); }
        std::string BackendName() const override;

        /// Attach a tokenizer (required for "interpreter" mode).
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
        Config cfg_;

        // --- MNN Interpreter path ---
        std::shared_ptr<MNN::Interpreter> interpreter_;
        MNN::Session                     *session_   = nullptr;

        // --- SGProcessing path ---
        std::unique_ptr<SGProcessingBridge>      bridge_;
        std::unique_ptr<TensorInterpreter>       tensor_interpreter_;
        std::shared_ptr<boost::asio::io_context> ioc_;

        std::atomic<bool>          loaded_    = false;
        std::string                model_path_;
        std::shared_ptr<Tokenizer> tokenizer_;
        fp4::FP4Codec              fp4_codec_;

        // Interpreter-path helpers
        int  SelectBackend() const;
        outcome::result<std::vector<float>> RunForward( const std::vector<int> &input_ids );
        int  SampleToken( const std::vector<float> &logits,
                          float temperature, float top_p, int top_k ) const;
        void ApplyRepetitionPenalty( std::vector<float>     &logits,
                                     const std::vector<int> &generated,
                                     float                   penalty ) const;
    };

} // namespace sgns::neoswarm::core

#endif // NEOSWARM_CORE_ENGINE_MNNINFERENCEENGINE_HPP_
