/**
 * @file       mnn_inference_engine.cpp
 * @brief      MNN inference engine — cross-platform, config-driven
 * @date       2026-05-06
 *
 * No platform-specific code. GPU = Vulkan only (MoltenVK on Apple).
 * Engine mode selected at runtime via Config::m_engineMode, not compile flags.
 */

#include "mnn_inference_engine.hpp"
#include "common/logging.hpp"

#include <boost/asio/io_context.hpp>
#include <chrono>
#include <numeric>
#include <stdexcept>

#include <InputFormat.hpp>

#include <MNN/MNNDefine.h>
#include <MNN/expr/Executor.hpp>
#include <MNN/llm/llm.hpp>

namespace sgns::neoswarm::core
{
    namespace
    {
        auto EngineLogger()
        {
            return neoswarm::CreateLogger( "MNNInferenceEngine" );
        }

        // Custom streambuf that forwards writes to a callback (used by StreamInfer)
        class CallbackStreambuf : public std::streambuf
        {
            public:
            explicit CallbackStreambuf( std::function<void( const std::string& )> cb )
                : m_cb( std::move( cb ) )
            {
            }

            protected:
            std::streamsize xsputn( const char* s, std::streamsize n ) override
            {
                if ( m_cb && n > 0 )
                {
                    m_cb( std::string( s, static_cast<size_t>( n ) ) );
                }
                return n;
            }
            int overflow( int c ) override
            {
                if ( c != EOF && m_cb )
                {
                    char ch = static_cast<char>( c );
                    m_cb( std::string( 1, ch ) );
                }
                return c;
            }

            private:
            std::function<void( const std::string& )> m_cb;
        };
    } // namespace

    // -----------------------------------------------------------------------
    // Construction / destruction
    // -----------------------------------------------------------------------
    MNNInferenceEngine::MNNInferenceEngine()
        : m_cfg( {} )
    {
    }
    MNNInferenceEngine::MNNInferenceEngine( Config cfg )
        : m_cfg( std::move( cfg ) )
    {
    }

    MNNInferenceEngine::~MNNInferenceEngine()
    {
        if ( mnn_llm_ )
        {
            MNN::Transformer::Llm::destroy( mnn_llm_ );
            mnn_llm_ = nullptr;
        }
    }

    std::string MNNInferenceEngine::BackendName() const
    {
        if ( m_cfg.m_engineMode == "sgprocessing" )
        {
            return m_cfg.m_sgNetworkMode ? "SGProcessing/Network" : "SGProcessing/Local";
        }
        return ( m_cfg.m_backend == "vulkan" ) ? "MNN/Vulkan" : "MNN/CPU";

    }

    // -----------------------------------------------------------------------
    // LoadModel
    // -----------------------------------------------------------------------
    outcome::result<void> MNNInferenceEngine::LoadModel( const std::string& model_path )
    {
        EngineLogger()->info( "Loading model: {} (mode={}, backend={})", model_path, m_cfg.m_engineMode, BackendName() );

        // ---- SGProcessing path (primary) ----
        if ( m_cfg.m_engineMode == "sgprocessing" )
        {
            m_modelPath = model_path;

            SGProcessingBridge::Config bridge_cfg;
            bridge_cfg.m_networkMode = m_cfg.m_sgNetworkMode;
            m_bridge = std::make_unique<SGProcessingBridge>( bridge_cfg );

            m_tensorInterpreter = std::make_unique<TensorInterpreter>();
            if ( m_tokenizer )
            {
                m_tensorInterpreter->SetTokenizer( m_tokenizer );
            }

            if ( !m_ioc )
            {
                m_ioc = std::make_shared<boost::asio::io_context>();
            }

            m_loaded.store( true );
            EngineLogger()->info( "Model path stored for SGProcessing: {}", model_path );
            return outcome::success();
        }

        // ---- MNN Interpreter path (fallback) ----
        if ( m_cfg.m_engineMode == "interpreter" )
        {
            // Check if this is an MNN LLM model directory (has llm_config.json or llm.mnn.json)
            std::string config_path;
            {
                // If model_path points to a .mnn file, check for llm_config.json in same dir
                std::string dir = model_path;
                auto slash_pos = dir.rfind( '/' );
                if ( slash_pos != std::string::npos )
                    dir = dir.substr( 0, slash_pos );
                else
                    dir = ".";

                std::string llm_config = dir + "/llm_config.json";
                std::ifstream check( llm_config );
                if ( check.good() )
                {
                    config_path = dir;
                }
            }

            if ( !config_path.empty() )
            {
                // Configure Vulkan backend for MNN LLM before creation
                if ( m_cfg.m_backend == "vulkan" )
                {
                    auto executor = MNN::Express::Executor::getGlobalExecutor();
                    MNN::BackendConfig backendConfig;
                    executor->setGlobalExecutorConfig( MNN_FORWARD_VULKAN, backendConfig, m_cfg.m_numThreads );
                    EngineLogger()->info( "MNN Vulkan backend configured for LLM" );
                }

                // Use MNN's native LLM API for autoregressive generation
                // createLLM expects a directory path ending with '/'
                std::string llm_dir = config_path;
                if ( !llm_dir.empty() && llm_dir.back() != '/' )
                {
                    llm_dir += '/';
                }
                EngineLogger()->info( "Detected MNN LLM model directory: {}", llm_dir );
                mnn_llm_ = MNN::Transformer::Llm::createLLM( llm_dir );
                if ( !mnn_llm_ )
                {
                    EngineLogger()->error( "Llm::createLLM failed for {}", llm_dir );
                    return outcome::failure( Error::ModelLoadFailed );
                }
                if ( !mnn_llm_->load() )
                {
                    EngineLogger()->error( "Llm::load() failed" );
                    MNN::Transformer::Llm::destroy( mnn_llm_ );
                    mnn_llm_ = nullptr;
                    return outcome::failure( Error::ModelLoadFailed );
                }
                m_modelPath = model_path;
                m_loaded.store( true );
                EngineLogger()->info( "MNN LLM model loaded successfully (native API)" );
                return outcome::success();
            }

            // No LLM-directory model detected — "interpreter" mode only supports
            // mnn_llm_-backed native generation (D-06). The hand-rolled raw-MNN
            // single-file-.mnn sampling loop has been removed; fail closed instead
            // of falling through to a silently-equivalent hidden path.
            EngineLogger()->error( "No MNN LLM model directory found at '{}' — 'interpreter' mode requires an "
                                    "MNN LLM model (llm_config.json)",
                                    model_path );
            return outcome::failure( Error::ModelLoadFailed );
        }

        // ---- Stub mode (no engine configured or MNN not compiled) ----
        EngineLogger()->warn( "Engine mode '{}' — running in stub mode", m_cfg.m_engineMode );
        m_modelPath = model_path;
        m_loaded.store( true );
        return outcome::success();
    }

    // -----------------------------------------------------------------------
    // Infer
    // -----------------------------------------------------------------------
    outcome::result<InferenceResponse> MNNInferenceEngine::Infer( const Task& task )
    {
        if ( !m_loaded.load() )
        {
            return outcome::failure( Error::InferenceFailed );
        }

        // Stub mode (no model loaded)
        if ( m_modelPath.empty() )
        {
            InferenceResponse resp;
            resp.m_output = "[stub response — no model loaded]";
            resp.m_latencyMs = 1.0;
            resp.m_nodeId = task.m_nodeId;
            resp.m_success = true;
            return outcome::success( std::move( resp ) );
        }

        // SGProcessing path (primary)
        if ( m_cfg.m_engineMode == "sgprocessing" )
        {
            return InferViaSGProcessing( task );
        }

        // MNN Interpreter path (fallback) — mnn_llm_-backed native generation only
        // (D-06: the hand-rolled raw-MNN sampling loop has been removed; fail
        // closed rather than silently falling through to an equivalent hidden path)
        if ( m_cfg.m_engineMode == "interpreter" )
        {
            if ( mnn_llm_ )
            {
                return InferViaMnnLlm( task );
            }
            return outcome::failure( Error::InferenceFailed );
        }

        // Unconfigured — stub response
        InferenceResponse resp;
        resp.m_output = "[stub response — engine not configured]";
        resp.m_latencyMs = 1.0;
        resp.m_nodeId = task.m_nodeId;
        resp.m_success = true;
        return outcome::success( std::move( resp ) );
    }

    // -----------------------------------------------------------------------
    // InferViaSGProcessing — Phase 1: direct SGProcessingManager pipeline
    // -----------------------------------------------------------------------
    outcome::result<InferenceResponse> MNNInferenceEngine::InferViaSGProcessing( const Task& task )
    {
        if ( !m_bridge || !m_tensorInterpreter )
        {
            return outcome::failure( Error::InferenceFailed );
        }

        auto t0 = std::chrono::steady_clock::now();

        const sgns::InputFormat input_fmt =
            m_cfg.m_useFp4 ? sgns::InputFormat::FP4_ULTRA : sgns::InputFormat::FLOAT32;
        const std::vector<int64_t> shape = { 1, static_cast<int64_t>( task.m_prompt.size() ) };

        auto bytes_res = m_bridge->SubmitJob( m_modelPath, task.m_prompt, input_fmt, shape, m_ioc );
        if ( !bytes_res.has_value() )
        {
            return outcome::failure( bytes_res.error() );
        }
        auto text_res = m_tensorInterpreter->Interpret( bytes_res.value(), sgns::InputFormat::FLOAT32 );
        if ( !text_res.has_value() )
        {
            return outcome::failure( text_res.error() );
        }

        auto t1 = std::chrono::steady_clock::now();
        InferenceResponse resp;
        resp.m_output = text_res.value();
        resp.m_latencyMs = std::chrono::duration<double, std::milli>( t1 - t0 ).count();
        resp.m_nodeId = task.m_nodeId;
        resp.m_success = true;
        return outcome::success( std::move( resp ) );
    }

    // -----------------------------------------------------------------------
    // InferViaMnnLlm — MNN native LLM autoregressive path
    // -----------------------------------------------------------------------
    outcome::result<InferenceResponse> MNNInferenceEngine::InferViaMnnLlm( const Task& task )
    {
        auto t0 = std::chrono::steady_clock::now();

        std::ostringstream oss;
        mnn_llm_->response( task.m_prompt, &oss, nullptr, static_cast<int>( task.m_maxTokens ) );

        auto t1 = std::chrono::steady_clock::now();
        double latency_ms = std::chrono::duration<double, std::milli>( t1 - t0 ).count();

        const auto* ctx = mnn_llm_->getContext();
        int gen_tokens = ctx ? static_cast<int>( ctx->output_tokens.size() ) : 0;

        InferenceResponse resp;
        resp.m_output = oss.str();
        resp.m_perplexity = 1.0f;
        resp.m_latencyMs = latency_ms;
        resp.m_nodeId = task.m_nodeId;
        resp.m_success = true;

        EngineLogger()->info( "MNN LLM inference: {} tokens, {:.1f} ms", gen_tokens, latency_ms );
        return outcome::success( std::move( resp ) );
    }

    // -----------------------------------------------------------------------
    // StreamInfer
    // -----------------------------------------------------------------------
    outcome::result<void> MNNInferenceEngine::StreamInfer( const Task& task,
                                                           std::function<void( const std::string& token )> callback )
    {
        if ( !m_loaded.load() )
        {
            return outcome::failure( Error::InferenceFailed );
        }

        // SGProcessing does not support streaming yet — fall through to batch.
        // Interpreter path supports token-by-token streaming.

        if ( m_cfg.m_engineMode == "interpreter" )
        {
            // --- MNN native LLM streaming ---
            if ( mnn_llm_ )
            {
                CallbackStreambuf buf( callback );
                std::ostream os( &buf );
                mnn_llm_->response( task.m_prompt, &os, nullptr, static_cast<int>( task.m_maxTokens ) );
                return outcome::success();
            }

            // No LLM-directory model loaded — "interpreter" mode only supports
            // mnn_llm_-backed native generation (D-06). The hand-rolled raw-MNN
            // token-generation-loop fallback has been removed; fail closed
            // rather than silently falling through to an equivalent hidden path.
            return outcome::failure( Error::InferenceFailed );
        }

        // Fallback: run batch inference and emit the full result as one token.
        auto result = Infer( task );
        if ( !result.has_value() )
        {
            return outcome::failure( result.error() );
        }
        if ( callback )
        {
            callback( result.value().m_output );
        }
        return outcome::success();
    }

    // -----------------------------------------------------------------------
    // SetSGClient
    // -----------------------------------------------------------------------
    void MNNInferenceEngine::SetSGClient( network::SGClient* client ) noexcept
    {
        if ( m_bridge )
        {
            m_bridge->SetClient( client );
        }
    }

} // namespace sgns::neoswarm::core
