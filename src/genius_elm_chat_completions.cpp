/**
 * @file       genius_elm_chat_c.cpp
 * @brief      C FFI entry points for Genius ELM chat completions API
 * @date       2026-06-15
 *
 * Wires the FFI surface to the real ApiServer pipeline.
 * Thread-safe: all FFI calls are protected by a global mutex.
 * Degrades gracefully: returns stub responses when no model is loaded.
 */
#include "genius_elm_chat_completions.h"

#include "api/api_server.hpp"
#include "common/types.hpp"

#include <cstdlib>
#include <cstring>
#include <memory>
#include <mutex>
#include <string>
#include <string_view>
#include <nlohmann/json.hpp>

namespace
{
    std::mutex g_mutex;
    std::unique_ptr<sgns::neoswarm::api::ApiServer> g_server;

    char* AllocCopy( const std::string& src )
    {
        const auto len = src.size();
        auto* dst = static_cast<char*>( std::malloc( len + 1 ) );
        if ( dst != nullptr )
        {
            std::memcpy( dst, src.data(), len );
            dst[ len ] = '\0';
        }
        return dst;
    }

    constexpr std::string_view kStubChatJson = R"({
  "id": "chatcmpl-stub",
  "object": "chat.completion",
  "created": 0,
  "model": "neoswarm-elm-stub",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "NeoSwarm ELM is running in stub mode."
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "total_tokens": 0
  }
})";

    constexpr std::string_view kStatusJsonStub = R"({
  "model_loaded": false,
  "mode": "stub",
  "backend": "none",
  "node_id": "stub",
  "supergenius_connected": false,
  "fallback_active": true
})";

    std::string BuildChatResponseJson( const sgns::neoswarm::InferenceResponse& resp )
    {
        nlohmann::json j;
        j[ "id" ]       = "chatcmpl-" + resp.m_taskId;
        j[ "object" ]   = "chat.completion";
        j[ "created" ]  = 0;
        j[ "model" ]    = "genius-elm-v1";
        j[ "choices" ]  = nlohmann::json::array( { { { "index", 0 },
                                                    { "message",
                                                      { { "role", "assistant" },
                                                        { "content", resp.m_output } } },
                                                    { "finish_reason", resp.m_success ? "stop" : "error" } } } );
        j[ "usage" ] = { { "prompt_tokens", 0 }, { "completion_tokens", 0 }, { "total_tokens", 0 } };
        return j.dump();
    }

    std::string BuildStatusJson()
    {
        std::lock_guard<std::mutex> lock( g_mutex );
        if ( !g_server )
        {
            return kStatusJsonStub;
        }

        nlohmann::json j;
        j[ "model_loaded" ]         = false; // ApiServer doesn't expose this directly
        j[ "mode" ]                 = g_server->IsRunning() ? "active" : "idle";
        j[ "backend" ]              = "cpu";
        j[ "node_id" ]              = "local";
        j[ "supergenius_connected" ] = g_server->IsSuperGeniusConnected();
        j[ "fallback_active" ]      = false;
        return j.dump();
    }

    std::string ExtractPrompt( const std::string& requestJson )
    {
        if ( requestJson.empty() )
        {
            return "";
        }

        try
        {
            auto j = nlohmann::json::parse( requestJson );
            if ( j.contains( "messages" ) && j[ "messages" ].is_array() )
            {
                for ( auto it = j[ "messages" ].rbegin(); it != j[ "messages" ].rend(); ++it )
                {
                    if ( it->contains( "role" ) && ( *it )[ "role" ] == "user" && it->contains( "content" ) )
                    {
                        return ( *it )[ "content" ].get<std::string>();
                    }
                }
            }
            if ( j.contains( "prompt" ) )
            {
                return j[ "prompt" ].get<std::string>();
            }
        }
        catch ( const nlohmann::json::exception& )
        {
            // Fall through — return empty prompt
        }

        return "";
    }

} // anonymous namespace

extern "C"
{
    GENIUS_ELM_CHAT_C_API int GeniusElmInit( const char* modelPath,
                                              const char* knowledgePath ) GENIUS_ELM_CHAT_C_NOEXCEPT
    {
        std::lock_guard<std::mutex> lock( g_mutex );

        if ( g_server )
        {
            return 0; // already initialized
        }

        sgns::neoswarm::api::ApiServer::Config cfg;
        if ( modelPath != nullptr && modelPath[ 0 ] != '\0' )
        {
            cfg.m_modelPath = modelPath;
        }
        if ( knowledgePath != nullptr && knowledgePath[ 0 ] != '\0' )
        {
            cfg.m_knowledgeFacts = knowledgePath;
        }
        cfg.m_enableNetwork = false;

        auto server = std::make_unique<sgns::neoswarm::api::ApiServer>( std::move( cfg ) );
        auto result = server->Initialize();
        if ( !result.has_value() )
        {
            return -1;
        }

        g_server = std::move( server );
        return 0;
    }

    GENIUS_ELM_CHAT_C_API char*
        GeniusElmChatCompletionsCreate( const char* requestJson ) GENIUS_ELM_CHAT_C_NOEXCEPT
    {
        std::lock_guard<std::mutex> lock( g_mutex );

        if ( !g_server )
        {
            return AllocCopy( kStubChatJson );
        }

        std::string prompt;
        if ( requestJson != nullptr )
        {
            prompt = ExtractPrompt( requestJson );
        }

        if ( prompt.empty() )
        {
            return AllocCopy( kStubChatJson );
        }

        sgns::neoswarm::Task task;
        task.m_id     = "ffi-" + std::to_string( std::hash<std::string>{}( prompt ) );
        task.m_prompt = std::move( prompt );
        task.m_mode   = sgns::neoswarm::ExecutionMode::SingleNode;

        auto result = g_server->Process( task );
        if ( !result.has_value() )
        {
            return AllocCopy( kStubChatJson );
        }

        return AllocCopy( BuildChatResponseJson( result.value() ) );
    }

    GENIUS_ELM_CHAT_C_API void GeniusElmStringFree( char* value ) GENIUS_ELM_CHAT_C_NOEXCEPT
    {
        std::free( value );
    }

    GENIUS_ELM_CHAT_C_API char* GeniusElmGetStatus( void ) GENIUS_ELM_CHAT_C_NOEXCEPT
    {
        return AllocCopy( BuildStatusJson() );
    }
} // extern "C"
