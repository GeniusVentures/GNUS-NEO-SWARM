/**
 * @file       MNNinference_engine.hpp
 * @brief      MNN-backed inference engine — cross-platform, config-driven
 * @date       2026-05-06
 *
 * Design:
 *   - Backend selection (Vulkan/CPU) is runtime config, not compile-time.
 *   - SGProcessing is the primary inference path (Phase 1 local, Phase 2 network).
 *   - MNN Interpreter is a fallback for standard single-file .mnn models.
 *   - No platform-specific code (Metal, Apple frameworks, etc.).
 *   - All GPU acceleration goes through Vulkan (MoltenVK on macOS/iOS).
 */

#ifndef NEOSWARM_CORE_ENGINE_MNNINFERENCEENGINE_HPP
#define NEOSWARM_CORE_ENGINE_MNNINFERENCEENGINE_HPP

#include "inference_engine.hpp"
#include "core/fp4/fp4_codec.hpp"
#include "core/sgprocessing/sg_processing_bridge.hpp"
#include "core/sgprocessing/tensor_interpreter.hpp"
#include "core/tokenizer/tokenizer.hpp"
#include <atomic>
#include <memory>
#include <string>

namespace MNN
{
    class Interpreter;
    class Session;
    namespace Transformer
    {
        class Llm;
    } // namespace Transformer
} // namespace MNN

namespace boost::asio
{
    class io_context;
} // namespace boost::asio

namespace sgns
{
    enum class InputFormat : int;
} // namespace sgns

namespace sgns::neoswarm::network
{
    class SuperGeniusClient;
}

namespace sgns::neoswarm::core
{
    /**
     * @brief MNN-backed inference engine with composable configuration.
     *
     * Inference paths (selected at runtime via Config::engine_m_mode):
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
            std::string engine_m_mode = "sgprocessing";

            /// GPU backend: "vulkan" (cross-platform) or "cpu"
            std::string backend_ = "vulkan";

            /// Use FP4 quantization for SGProcessing path
            bool use_fp4_ = true;

            /// CPU thread count (used when backend_ == "cpu")
            int num_threads_ = 4;

            /// Generation parameters
            static constexpr int   kDefaultMaxTokens         = 512;
            int   max_new_tokens_     = kDefaultMaxTokens;
            static constexpr float kDefaultTemperature       = 0.7f;
            float m_temperature        = kDefaultTemperature;
            static constexpr float kDefaultTopP              = 0.9f;
            float top_p_              = kDefaultTopP;
            static constexpr int   kDefaultTopK              = 40;
            int   top_k_              = kDefaultTopK;
            static constexpr float kDefaultRepetitionPenalty = 1.1f;
            float repetition_penalty_ = kDefaultRepetitionPenalty;

            /// SGProcessing network mode (Phase 2: dispatch via gRPC to SuperGenius)
            bool m_sgNetworkMode = false;
        };

        MNNInferenceEngine();
        explicit MNNInferenceEngine( Config cfg );
        ~MNNInferenceEngine() override;

        outcome::result<void> LoadModel( const std::string& model_path ) override;
        outcome::result<InferenceResponse> Infer( const Task& task ) override;
        outcome::result<void> StreamInfer( const Task& task,
                                           std::function<void( const std::string& token )> callback ) override;

        bool IsLoaded() const override
        {
            return m_loaded.load();
        }
        std::string BackendName() const override;

        /// Attach a tokenizer (required for "interpreter" mode).
        void SetTokenizer( std::shared_ptr<Tokenizer> tok )
        {
            m_tokenizer = std::move( tok );
        }

        /// Mark engine as loaded in stub/test mode (no real model file needed).
        void SetStubMode()
        {
            m_loaded.store( true );
        }

        /**
         * @brief Set the SuperGeniusClient for Phase 2 network dispatch.
         *
         * Call once during initialization after both the engine and the
         * SuperGeniusClient are created. The client pointer is passed through
         * to the internal SGProcessingBridge.
         *
         * @param client  The SuperGeniusClient instance (owned by ApiServer).
         */
        void SetSuperGeniusClient( network::SuperGeniusClient* client ) noexcept;

        private:
        Config m_cfg;

        // --- MNN Interpreter path ---
        std::shared_ptr<MNN::Interpreter> m_interpreter;
        MNN::Session* m_session = nullptr;

        // --- MNN LLM path (native autoregressive) ---
        MNN::Transformer::Llm* mnn_llm_ = nullptr;

        // --- SGProcessing path ---
        std::unique_ptr<SGProcessingBridge> m_bridge;
        std::unique_ptr<TensorInterpreter> m_tensorInterpreter;
        std::shared_ptr<boost::asio::io_context> m_ioc;

        std::atomic<bool> m_loaded = false;
        std::string m_modelPath;
        std::shared_ptr<Tokenizer> m_tokenizer;
        fp4::FP4Codec m_fp4Codec;

        // Interpreter-path helpers
        int SelectBackend() const;
        outcome::result<std::vector<float>> RunForward( const std::vector<int>& input_ids );
        int SampleToken( const std::vector<float>& logits, float temperature, float top_p, int top_k ) const;
        void ApplyRepetitionPenalty( std::vector<float>& logits,
                                     const std::vector<int>& generated,
                                     float penalty ) const;
    };

} // namespace sgns::neoswarm::core

#endif // NEOSWARM_CORE_ENGINE_MNNINFERENCEENGINE_HPP
