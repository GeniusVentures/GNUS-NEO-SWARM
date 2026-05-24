/**
 * @file       MNNInferenceEngine.cpp
 * @brief      MNN inference engine — cross-platform, config-driven
 * @date       2026-05-06
 * @author     Subaskar S (ssivakumar@gnus.ai)
 *
 * No platform-specific code. GPU = Vulkan only (MoltenVK on Apple).
 * Engine mode selected at runtime via Config::engine_mode_, not compile flags.
 */

#include "MNNInferenceEngine.hpp"
#include "common/Logging.hpp"

#include <algorithm>
#include <boost/asio/io_context.hpp>
#include <chrono>
#include <cmath>
#include <numeric>
#include <random>
#include <stdexcept>

#ifdef GENIUS_HAS_SGPROCESSING
#    include <InputFormat.hpp>
#else
namespace sgns
{
    enum class InputFormat : int
    {
        FLOAT16   = 0,
        FLOAT32   = 1,
        FP4_ULTRA = 2,
        INT16     = 3,
        INT32     = 4,
        INT8      = 5,
        RGB8      = 6,
        RGBA8     = 7
    };
}
#endif

#ifdef GENIUS_HAS_MNN
#    include <MNN/Interpreter.hpp>
#    include <MNN/MNNDefine.h>
#    include <MNN/Tensor.hpp>
#endif

namespace sgns::neoswarm::core
{
    namespace
    {
        auto EngineLogger()
        {
            return neoswarm::CreateLogger( "MNNInferenceEngine" );
        }
    }

    // -----------------------------------------------------------------------
    // Construction / destruction
    // -----------------------------------------------------------------------
    MNNInferenceEngine::MNNInferenceEngine() : cfg_( {} ) {}
    MNNInferenceEngine::MNNInferenceEngine( Config cfg ) : cfg_( std::move( cfg ) )
    {
        ( void )fp4_codec_;
    }

    MNNInferenceEngine::~MNNInferenceEngine()
    {
#ifdef GENIUS_HAS_MNN
        if ( interpreter_ && session_ )
        {
            interpreter_->releaseSession( session_ );
        }
#endif
    }

    // -----------------------------------------------------------------------
    // SelectBackend — Vulkan (cross-platform) or CPU
    // -----------------------------------------------------------------------
    int MNNInferenceEngine::SelectBackend() const
    {
#ifdef GENIUS_HAS_MNN
        // MNN_FORWARD_VULKAN = 7, MNN_FORWARD_CPU = 0
        return ( cfg_.backend_ == "vulkan" ) ? 7 : 0;
#else
        return 0;
#endif
    }

    std::string MNNInferenceEngine::BackendName() const
    {
        if ( cfg_.engine_mode_ == "sgprocessing" )
        {
            return cfg_.sg_network_mode_ ? "SGProcessing/Network" : "SGProcessing/Local";
        }
#ifdef GENIUS_HAS_MNN
        return ( cfg_.backend_ == "vulkan" ) ? "MNN/Vulkan" : "MNN/CPU";
#else
        return "Stub/NoMNN";
#endif
    }

    // -----------------------------------------------------------------------
    // LoadModel
    // -----------------------------------------------------------------------
    outcome::result<void> MNNInferenceEngine::LoadModel( const std::string &model_path )
    {
        EngineLogger()->info( "Loading model: {} (mode={}, backend={})",
                              model_path, cfg_.engine_mode_, BackendName() );

        // ---- SGProcessing path (primary) ----
        if ( cfg_.engine_mode_ == "sgprocessing" )
        {
            model_path_ = model_path;

            SGProcessingBridge::Config bridge_cfg;
            bridge_cfg.network_mode_ = cfg_.sg_network_mode_;
            bridge_ = std::make_unique<SGProcessingBridge>( bridge_cfg );

            tensor_interpreter_ = std::make_unique<TensorInterpreter>();
            if ( tokenizer_ )
            {
                tensor_interpreter_->SetTokenizer( tokenizer_ );
            }

            if ( !ioc_ )
            {
                ioc_ = std::make_shared<boost::asio::io_context>();
            }

            loaded_.store( true );
            EngineLogger()->info( "Model path stored for SGProcessing: {}", model_path );
            return outcome::success();
        }

        // ---- MNN Interpreter path (fallback) ----
#ifdef GENIUS_HAS_MNN
        if ( cfg_.engine_mode_ == "interpreter" )
        {
            interpreter_.reset( MNN::Interpreter::createFromFile( model_path.c_str() ) );
            if ( !interpreter_ )
            {
                return outcome::failure( Error::ModelLoadFailed );
            }
            MNN::ScheduleConfig sched_cfg;
            sched_cfg.type      = static_cast<MNNForwardType>( SelectBackend() );
            sched_cfg.numThread = cfg_.num_threads_;
            session_ = interpreter_->createSession( sched_cfg );
            if ( !session_ )
            {
                return outcome::failure( Error::ModelLoadFailed );
            }
            model_path_ = model_path;
            loaded_.store( true );
            EngineLogger()->info( "Model loaded (Interpreter, backend={})", BackendName() );
            return outcome::success();
        }
#endif

        // ---- Stub mode (no engine configured or MNN not compiled) ----
        EngineLogger()->warn( "Engine mode '{}' — running in stub mode", cfg_.engine_mode_ );
        model_path_ = model_path;
        loaded_.store( true );
        return outcome::success();
    }

    // -----------------------------------------------------------------------
    // Infer
    // -----------------------------------------------------------------------
    outcome::result<InferenceResponse> MNNInferenceEngine::Infer( const Task &task )
    {
        if ( !loaded_.load() )
        {
            return outcome::failure( Error::InferenceFailed );
        }

        // ---- Stub mode (no model loaded) ----
        if ( model_path_.empty() )
        {
            InferenceResponse resp;
            resp.output_     = "[stub response — no model loaded]";
            resp.latency_ms_ = 1.0;
            resp.node_id_    = task.node_id_;
            resp.success_    = true;
            return outcome::success( std::move( resp ) );
        }

        // ---- SGProcessing path (primary) ----
        if ( cfg_.engine_mode_ == "sgprocessing" )
        {
            if ( !bridge_ || !tensor_interpreter_ )
            {
                return outcome::failure( Error::InferenceFailed );
            }

            auto t0 = std::chrono::steady_clock::now();

            const sgns::InputFormat input_fmt = cfg_.use_fp4_
                ? sgns::InputFormat::FP4_ULTRA
                : sgns::InputFormat::FLOAT32;
            const std::vector<int64_t> shape = { 1, static_cast<int64_t>( task.prompt_.size() ) };

            auto bytes_res = bridge_->SubmitJob( model_path_, task.prompt_, input_fmt, shape, ioc_ );
            if ( !bytes_res.has_value() )
            {
                return outcome::failure( bytes_res.error() );
            }
            auto text_res = tensor_interpreter_->Interpret( bytes_res.value(),
                                                            sgns::InputFormat::FLOAT32 );
            if ( !text_res.has_value() )
            {
                return outcome::failure( text_res.error() );
            }

            auto t1 = std::chrono::steady_clock::now();
            InferenceResponse resp;
            resp.output_     = text_res.value();
            resp.latency_ms_ = std::chrono::duration<double, std::milli>( t1 - t0 ).count();
            resp.node_id_    = task.node_id_;
            resp.success_    = true;
            return outcome::success( std::move( resp ) );
        }

        // ---- MNN Interpreter path (fallback) ----
#ifdef GENIUS_HAS_MNN
        if ( cfg_.engine_mode_ == "interpreter" )
        {
            if ( !tokenizer_ )
            {
                return outcome::failure( Error::InferenceFailed );
            }

            auto t0 = std::chrono::steady_clock::now();

            auto enc_res = tokenizer_->Encode( task.prompt_ );
            if ( !enc_res.has_value() )
            {
                return outcome::failure( enc_res.error() );
            }
            std::vector<int> input_ids = enc_res.value();
            std::vector<int> generated;
            generated.reserve( task.max_tokens_ );

            std::string output_text;
            float       total_log_prob = 0.0f;
            int         token_count    = 0;

            for ( uint32_t step = 0; step < task.max_tokens_; ++step )
            {
                std::vector<int> context_ids = input_ids;
                context_ids.insert( context_ids.end(), generated.begin(), generated.end() );

                auto logits_res = RunForward( context_ids );
                if ( !logits_res.has_value() )
                {
                    return outcome::failure( logits_res.error() );
                }

                auto &logits = logits_res.value();
                ApplyRepetitionPenalty( logits, generated, cfg_.repetition_penalty_ );
                int next_token = SampleToken( logits, task.temperature_, cfg_.top_p_, cfg_.top_k_ );

                float max_l   = *std::max_element( logits.begin(), logits.end() );
                float sum_exp = 0.0f;
                for ( auto v : logits ) sum_exp += std::exp( v - max_l );
                total_log_prob += logits[next_token] - max_l - std::log( sum_exp );
                ++token_count;

                if ( tokenizer_->IsEOS( next_token ) ) break;
                generated.push_back( next_token );

                auto dec_res = tokenizer_->Decode( { next_token } );
                if ( dec_res.has_value() ) output_text += dec_res.value();
            }

            auto   t1         = std::chrono::steady_clock::now();
            double latency_ms = std::chrono::duration<double, std::milli>( t1 - t0 ).count();
            float  perplexity = token_count > 0
                ? std::exp( -total_log_prob / static_cast<float>( token_count ) )
                : 1.0f;

            InferenceResponse resp;
            resp.output_     = output_text;
            resp.perplexity_ = perplexity;
            resp.latency_ms_ = latency_ms;
            resp.node_id_    = task.node_id_;
            resp.success_    = true;

            EngineLogger()->debug( "Inference done: {} tokens, {:.1f} ms, perplexity={:.2f}",
                                   generated.size(), latency_ms, perplexity );
            return outcome::success( std::move( resp ) );
        }
#endif

        // ---- Stub path ----
        InferenceResponse resp;
        resp.output_     = "[stub response — engine not configured]";
        resp.latency_ms_ = 1.0;
        resp.node_id_    = task.node_id_;
        resp.success_    = true;
        return outcome::success( std::move( resp ) );
    }

    // -----------------------------------------------------------------------
    // StreamInfer
    // -----------------------------------------------------------------------
    outcome::result<void> MNNInferenceEngine::StreamInfer(
        const Task                                       &task,
        std::function<void( const std::string &token )>  callback )
    {
        if ( !loaded_.load() )
        {
            return outcome::failure( Error::InferenceFailed );
        }

        // SGProcessing does not support streaming yet — fall through to batch.
        // Interpreter path supports token-by-token streaming.

#ifdef GENIUS_HAS_MNN
        if ( cfg_.engine_mode_ == "interpreter" )
        {
            if ( !tokenizer_ )
            {
                return outcome::failure( Error::InferenceFailed );
            }

            auto enc_res = tokenizer_->Encode( task.prompt_ );
            if ( !enc_res.has_value() )
            {
                return outcome::failure( enc_res.error() );
            }
            std::vector<int> input_ids = enc_res.value();
            std::vector<int> generated;

            for ( uint32_t step = 0; step < task.max_tokens_; ++step )
            {
                std::vector<int> context_ids = input_ids;
                context_ids.insert( context_ids.end(), generated.begin(), generated.end() );

                auto logits_res = RunForward( context_ids );
                if ( !logits_res.has_value() )
                {
                    return outcome::failure( logits_res.error() );
                }

                auto &logits = logits_res.value();
                ApplyRepetitionPenalty( logits, generated, cfg_.repetition_penalty_ );
                int next_token = SampleToken( logits, task.temperature_, cfg_.top_p_, cfg_.top_k_ );

                if ( tokenizer_->IsEOS( next_token ) ) break;
                generated.push_back( next_token );

                auto dec_res = tokenizer_->Decode( { next_token } );
                if ( dec_res.has_value() && callback )
                {
                    callback( dec_res.value() );
                }
            }
            return outcome::success();
        }
#endif

        // Fallback: run batch inference and emit the full result as one token.
        auto result = Infer( task );
        if ( !result.has_value() )
        {
            return outcome::failure( result.error() );
        }
        if ( callback )
        {
            callback( result.value().output_ );
        }
        return outcome::success();
    }

    // -----------------------------------------------------------------------
    // RunForward — Interpreter path only
    // -----------------------------------------------------------------------
    outcome::result<std::vector<float>> MNNInferenceEngine::RunForward(
        const std::vector<int> &input_ids )
    {
#ifdef GENIUS_HAS_MNN
        if ( !session_ )
        {
            // Stub: return random logits
            std::vector<float>              logits( 32000, 0.0f );
            static std::mt19937             rng( 42 );
            std::normal_distribution<float> dist( 0.0f, 1.0f );
            for ( auto &v : logits ) v = dist( rng );
            return outcome::success( std::move( logits ) );
        }

        auto *input_tensor = interpreter_->getSessionInput( session_, "input_ids" );
        if ( !input_tensor )
        {
            return outcome::failure( Error::InferenceFailed );
        }
        interpreter_->resizeTensor( input_tensor, { 1, static_cast<int>( input_ids.size() ) } );
        interpreter_->resizeSession( session_ );

        auto *host_tensor = new MNN::Tensor( input_tensor, MNN::Tensor::CAFFE );
        for ( size_t i = 0; i < input_ids.size(); ++i )
        {
            host_tensor->host<int>()[i] = input_ids[i];
        }
        input_tensor->copyFromHostTensor( host_tensor );
        delete host_tensor;

        interpreter_->runSession( session_ );

        auto *logits_tensor = interpreter_->getSessionOutput( session_, "logits" );
        if ( !logits_tensor )
        {
            return outcome::failure( Error::InferenceFailed );
        }
        auto *host_logits = new MNN::Tensor( logits_tensor, MNN::Tensor::CAFFE );
        logits_tensor->copyToHostTensor( host_logits );
        int                vocab_size = host_logits->elementSize();
        std::vector<float> logits( host_logits->host<float>(),
                                   host_logits->host<float>() + vocab_size );
        delete host_logits;
        return outcome::success( std::move( logits ) );
#else
        ( void )input_ids;
        std::vector<float>              logits( 32000, 0.0f );
        static std::mt19937             rng( 42 );
        std::normal_distribution<float> dist( 0.0f, 1.0f );
        for ( auto &v : logits ) v = dist( rng );
        return outcome::success( std::move( logits ) );
#endif
    }

    // -----------------------------------------------------------------------
    // ApplyRepetitionPenalty
    // -----------------------------------------------------------------------
    void MNNInferenceEngine::ApplyRepetitionPenalty( std::vector<float>     &logits,
                                                     const std::vector<int> &generated,
                                                     float                   penalty ) const
    {
        for ( int id : generated )
        {
            if ( id >= 0 && static_cast<size_t>( id ) < logits.size() )
            {
                logits[id] = logits[id] > 0 ? logits[id] / penalty : logits[id] * penalty;
            }
        }
    }

    // -----------------------------------------------------------------------
    // SampleToken
    // -----------------------------------------------------------------------
    int MNNInferenceEngine::SampleToken( const std::vector<float> &logits,
                                         float                     temperature,
                                         float                     top_p,
                                         int                       top_k ) const
    {
        if ( logits.empty() ) return 0;

        std::vector<float> scaled( logits.size() );
        float              t = std::max( temperature, 1e-6f );
        for ( size_t i = 0; i < logits.size(); ++i ) scaled[i] = logits[i] / t;

        float max_val = *std::max_element( scaled.begin(), scaled.end() );
        float sum     = 0.0f;
        for ( auto &v : scaled )
        {
            v = std::exp( v - max_val );
            sum += v;
        }
        for ( auto &v : scaled ) v /= sum;

        std::vector<std::pair<float, int>> probs;
        probs.reserve( scaled.size() );
        for ( size_t i = 0; i < scaled.size(); ++i )
        {
            probs.push_back( { scaled[i], static_cast<int>( i ) } );
        }
        std::partial_sort( probs.begin(),
                           probs.begin() + std::min( top_k, static_cast<int>( probs.size() ) ),
                           probs.end(),
                           []( const auto &a, const auto &b ) { return a.first > b.first; } );
        probs.resize( std::min( top_k, static_cast<int>( probs.size() ) ) );

        float  cum_sum = 0.0f;
        size_t cutoff  = probs.size();
        for ( size_t i = 0; i < probs.size(); ++i )
        {
            cum_sum += probs[i].first;
            if ( cum_sum >= top_p )
            {
                cutoff = i + 1;
                break;
            }
        }
        probs.resize( cutoff );

        float p_sum = 0.0f;
        for ( auto &p : probs ) p_sum += p.first;
        for ( auto &p : probs ) p.first /= p_sum;

        static thread_local std::mt19937      rng( std::random_device{}() );
        std::uniform_real_distribution<float> dist( 0.0f, 1.0f );
        float                                 r   = dist( rng );
        float                                 acc = 0.0f;
        for ( auto &p : probs )
        {
            acc += p.first;
            if ( r <= acc ) return p.second;
        }
        return probs.back().second;
    }

} // namespace sgns::neoswarm::core
