/**
 * @file       bench_mnn_llm.cpp
 * @brief      Benchmark MNN LLM inference — measures prefill + decode performance
 *
 * Measures:
 *   - Prefill latency (time to process the prompt)
 *   - Decode throughput (tokens/second during generation)
 *   - Peak memory usage
 *   - Total latency for full generation
 *
 * Usage:
 *   ./bench_mnn_llm [model_dir] [prompt] [max_tokens]
 *
 * Example:
 *   ./bench_mnn_llm /path/to/mistral-7b-mnn/ "What is 2+2?" 64
 *
 * This benchmark helps decide whether custom TurboQuant-K/V is needed
 * on top of MNN's built-in quantized inference.
 */

#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

#include "os_memory.hpp"

#include <llm/llm.hpp>

namespace
{
    struct BenchResult
    {
        double prefill_ms       = 0.0;
        double decode_ms        = 0.0;
        double total_ms         = 0.0;
        int    prompt_tokens    = 0;
        int    generated_tokens = 0;
        double tokens_per_sec   = 0.0;
        double prefill_tok_sec  = 0.0;
        size_t peak_memory_mb   = 0;
    };

    // GetCurrentMemoryMB() defined in os_memory.hpp (platform abstraction)

    BenchResult RunBenchmark( const std::string &model_dir,
                              const std::string &prompt,
                              int                max_tokens )
    {
        BenchResult result;

        std::printf( "=== MNN LLM Benchmark ===\n" );
        std::printf( "Model:      %s\n", model_dir.c_str() );
        std::printf( "Prompt:     \"%s\"\n", prompt.c_str() );
        std::printf( "Max tokens: %d\n\n", max_tokens );

        // --- Load model ---
        std::printf( "[1/4] Loading model...\n" );
        auto t_load_start = std::chrono::steady_clock::now();

        auto *llm = MNN::Transformer::Llm::createLLM( model_dir );
        if ( !llm )
        {
            std::fprintf( stderr, "ERROR: Llm::createLLM failed\n" );
            return result;
        }
        if ( !llm->load() )
        {
            std::fprintf( stderr, "ERROR: Llm::load() failed\n" );
            MNN::Transformer::Llm::destroy( llm );
            return result;
        }

        auto   t_load_end = std::chrono::steady_clock::now();
        double load_ms    = std::chrono::duration<double, std::milli>( t_load_end - t_load_start ).count();
        size_t mem_after_load = GetCurrentMemoryMB();
        std::printf( "      Load time: %.1f ms\n", load_ms );
        std::printf( "      Memory after load: %zu MB\n\n", mem_after_load );

        // --- Generate (prefill + decode) ---
        std::printf( "[2/4] Running inference...\n" );

        std::ostringstream oss;
        int                token_count = 0;

        // Use a counting stream to track tokens
        class CountingStreambuf : public std::streambuf
        {
        public:
            int          count = 0;
            std::string  output;
            std::chrono::steady_clock::time_point first_token_time;
            bool         got_first = false;

        protected:
            std::streamsize xsputn( const char *s, std::streamsize n ) override
            {
                if ( n > 0 )
                {
                    if ( !got_first )
                    {
                        first_token_time = std::chrono::steady_clock::now();
                        got_first = true;
                    }
                    ++count;
                    output.append( s, static_cast<size_t>( n ) );
                }
                return n;
            }
            int overflow( int c ) override
            {
                if ( c != EOF )
                {
                    if ( !got_first )
                    {
                        first_token_time = std::chrono::steady_clock::now();
                        got_first = true;
                    }
                    ++count;
                    output += static_cast<char>( c );
                }
                return c;
            }
        };

        CountingStreambuf counting_buf;
        std::ostream     counting_os( &counting_buf );

        auto t_gen_start = std::chrono::steady_clock::now();
        llm->response( prompt, &counting_os, nullptr, max_tokens );
        auto t_gen_end = std::chrono::steady_clock::now();

        size_t mem_after_gen = GetCurrentMemoryMB();

        // --- Extract timing from MNN context ---
        const auto *ctx = llm->getContext();
        if ( ctx )
        {
            result.prefill_ms       = static_cast<double>( ctx->prefill_us ) / 1000.0;
            result.decode_ms        = static_cast<double>( ctx->decode_us ) / 1000.0;
            result.prompt_tokens    = ctx->prompt_len;
            result.generated_tokens = static_cast<int>( ctx->output_tokens.size() );
        }
        else
        {
            result.total_ms = std::chrono::duration<double, std::milli>( t_gen_end - t_gen_start ).count();
            result.generated_tokens = counting_buf.count;
        }

        result.total_ms = std::chrono::duration<double, std::milli>( t_gen_end - t_gen_start ).count();
        result.peak_memory_mb = mem_after_gen;

        if ( result.decode_ms > 0 && result.generated_tokens > 0 )
        {
            result.tokens_per_sec = static_cast<double>( result.generated_tokens ) * 1000.0 / result.decode_ms;
        }
        if ( result.prefill_ms > 0 && result.prompt_tokens > 0 )
        {
            result.prefill_tok_sec = static_cast<double>( result.prompt_tokens ) * 1000.0 / result.prefill_ms;
        }

        // --- Print results ---
        std::printf( "\n[3/4] Results:\n" );
        std::printf( "      ┌─────────────────────────────────────────────┐\n" );
        std::printf( "      │ Prefill                                     │\n" );
        std::printf( "      │   Tokens:     %4d                          │\n", result.prompt_tokens );
        std::printf( "      │   Latency:    %8.1f ms                   │\n", result.prefill_ms );
        std::printf( "      │   Throughput: %8.1f tokens/sec           │\n", result.prefill_tok_sec );
        std::printf( "      ├─────────────────────────────────────────────┤\n" );
        std::printf( "      │ Decode                                      │\n" );
        std::printf( "      │   Tokens:     %4d                          │\n", result.generated_tokens );
        std::printf( "      │   Latency:    %8.1f ms                   │\n", result.decode_ms );
        std::printf( "      │   Throughput: %8.2f tokens/sec           │\n", result.tokens_per_sec );
        std::printf( "      ├─────────────────────────────────────────────┤\n" );
        std::printf( "      │ Total                                       │\n" );
        std::printf( "      │   Latency:    %8.1f ms                   │\n", result.total_ms );
        std::printf( "      │   Memory:     %4zu MB (resident)            │\n", result.peak_memory_mb );
        std::printf( "      └─────────────────────────────────────────────┘\n" );

        // --- Print generated text ---
        std::printf( "\n[4/4] Generated text:\n" );
        std::printf( "      \"%s\"\n", counting_buf.output.c_str() );

        // --- Decision guidance ---
        std::printf( "\n=== TurboQuant Decision Guidance ===\n" );
        if ( result.tokens_per_sec >= 15.0 )
        {
            std::printf( "  ✓ Decode speed %.1f tok/s is GOOD (>15 tok/s).\n", result.tokens_per_sec );
            std::printf( "    TurboQuant-K is likely NOT needed for this device.\n" );
        }
        else if ( result.tokens_per_sec >= 5.0 )
        {
            std::printf( "  ~ Decode speed %.1f tok/s is ACCEPTABLE (5-15 tok/s).\n", result.tokens_per_sec );
            std::printf( "    TurboQuant-K could help but is not critical.\n" );
        }
        else
        {
            std::printf( "  ✗ Decode speed %.1f tok/s is SLOW (<5 tok/s).\n", result.tokens_per_sec );
            std::printf( "    TurboQuant-K would significantly help on this device.\n" );
        }

        if ( result.peak_memory_mb > 4096 )
        {
            std::printf( "  ✗ Memory %zu MB is HIGH (>4GB). KV cache compression needed for mobile.\n",
                         result.peak_memory_mb );
        }
        else if ( result.peak_memory_mb > 2048 )
        {
            std::printf( "  ~ Memory %zu MB is MODERATE (2-4GB). May be tight on phones.\n",
                         result.peak_memory_mb );
        }
        else
        {
            std::printf( "  ✓ Memory %zu MB is OK (<2GB).\n", result.peak_memory_mb );
        }

        MNN::Transformer::Llm::destroy( llm );
        return result;
    }
}

int main( int argc, char *argv[] )
{
    std::string model_dir  = "/Volumes/Work/Gnus_ai/genius-llm-v1/models/mistral-7b-mnn/";
    std::string prompt     = "Explain what a blockchain is in simple terms.";
    int         max_tokens = 64;

    if ( argc >= 2 ) model_dir  = argv[1];
    if ( argc >= 3 ) prompt     = argv[2];
    if ( argc >= 4 ) max_tokens = std::atoi( argv[3] );

    // Ensure trailing slash
    if ( !model_dir.empty() && model_dir.back() != '/' )
        model_dir += '/';

    RunBenchmark( model_dir, prompt, max_tokens );
    return 0;
}
