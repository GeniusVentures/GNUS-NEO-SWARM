/**
 * @file       genius_elm_chat_c.cpp
 * @brief      C FFI entry point stub for GeniusElmInit / GeniusElmChatCompletionsCreate /
 *             GeniusElmStringFree / GeniusElmGetStatus
 * @date       2026-06-10
 * @author     Subaskar S (ssivakumar@gnus.ai)
 *
 * Returns canned responses until the real GeniusAPIServer pipeline is wired.
 * The shared library is consumed by the Flutter bridge.
 */

#include "genius_elm_chat_completions.h"

#include <cstdlib>
#include <cstring>
#include <string>

namespace
{
    char* DuplicateString( const std::string& value ) noexcept
    {
        const size_t size = value.size() + 1U;
        char*        buf  = static_cast<char*>( std::malloc( size ) );

        if ( buf == nullptr )
        {
            return nullptr;
        }

        std::memcpy( buf, value.data(), size );
        return buf;
    }

    static const char kStubChatJson[] =
        "{\"id\":\"chatcmpl-stub\",\"object\":\"chat.completion\","
        "\"created\":0,\"model\":\"elm-v1\","
        "\"choices\":[{\"index\":0,\"message\":{"
        "\"role\":\"assistant\",\"content\":\"[ELM stub - engine not wired]\"},"
        "\"finish_reason\":\"stop\"}],"
        "\"usage\":{\"prompt_tokens\":0,\"completion_tokens\":0,\"total_tokens\":0}}";

    static const char kStubStatusJson[] =
        "{\"model_loaded\":false,\"mode\":\"stub\",\"backend\":\"none\",\"node_id\":\"stub\"}";

    static bool g_initialized = false;
} // namespace

GENIUS_ELM_CHAT_C_API int GeniusElmInit( const char* /* modelPath */, const char* /* knowledgePath */ )
    GENIUS_ELM_CHAT_C_NOEXCEPT
{
    g_initialized = true;
    return 0;
}

GENIUS_ELM_CHAT_C_API char* GeniusElmChatCompletionsCreate( const char* /* requestJson */ )
    GENIUS_ELM_CHAT_C_NOEXCEPT
{
    return DuplicateString( kStubChatJson );
}

GENIUS_ELM_CHAT_C_API void GeniusElmStringFree( char* value ) GENIUS_ELM_CHAT_C_NOEXCEPT
{
    std::free( value );
}

GENIUS_ELM_CHAT_C_API char* GeniusElmGetStatus( void ) GENIUS_ELM_CHAT_C_NOEXCEPT
{
    return DuplicateString( kStubStatusJson );
}
