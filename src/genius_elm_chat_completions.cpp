/**
 * @file       genius_elm_chat_c.cpp
 * @brief      FFI stub for Genius ELM chat completions API (C ABI)
 */
#include "genius_elm_chat_completions.h"

#include <cstdlib>
#include <cstring>
#include <string>

namespace
{
    constexpr const char* kStubResponseJson = R"({
  "id": "chatcmpl-stub",
  "object": "chat.completion",
  "created": 0,
  "model": "genius-elm-stub",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Genius ELM is running in stub mode."
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

    constexpr const char* kStatusJson = R"({
  "model_loaded": false,
  "mode": "stub",
  "backend": "cpu",
  "node_id": "stub-node"
})";

    char* AllocCopy( const std::string& src )
    {
        const auto len = src.size();
        auto*      dst = static_cast<char*>( std::malloc( len + 1 ) );
        if ( dst != nullptr )
        {
            std::memcpy( dst, src.data(), len );
            dst[ len ] = '\0';
        }
        return dst;
    }
} // anonymous namespace

extern "C"
{
    GENIUS_ELM_CHAT_C_API int GeniusElmInit( const char* /*modelPath*/,
                                             const char* /*knowledgePath*/ ) GENIUS_ELM_CHAT_C_NOEXCEPT
    {
        return 0;
    }

    GENIUS_ELM_CHAT_C_API char*
        GeniusElmChatCompletionsCreate( const char* /*requestJson*/ ) GENIUS_ELM_CHAT_C_NOEXCEPT
    {
        return AllocCopy( kStubResponseJson );
    }

    GENIUS_ELM_CHAT_C_API void GeniusElmStringFree( char* value ) GENIUS_ELM_CHAT_C_NOEXCEPT
    {
        std::free( value );
    }

    GENIUS_ELM_CHAT_C_API char* GeniusElmGetStatus( void ) GENIUS_ELM_CHAT_C_NOEXCEPT
    {
        return AllocCopy( kStatusJson );
    }
} // extern "C"
