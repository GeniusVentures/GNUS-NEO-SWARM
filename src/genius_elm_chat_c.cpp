/**
 * @file       genius_elm_chat_c.cpp
 * @brief      C FFI entry point — stub for GeniusElmChatCompletionsCreate / GeniusElmStringFree
 * @date       2026-06-09
 * @author     Subaskar S (ssivakumar@gnus.ai)
 *
 * This stub returns a fixed JSON response until the real GeniusAPIServer
 * pipeline is wired. The shared library is consumed by the Flutter bridge.
 */

#include "genius_elm_chat_c.h"

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
} // namespace

GENIUS_ELM_CHAT_C_API char* GeniusElmChatCompletionsCreate( const char* /* requestJson */ ) GENIUS_ELM_CHAT_C_NOEXCEPT
{
    static const char kStubJson[] = "{\"id\":\"chatcmpl-stub\",\"object\":\"chat.completion\","
                                    "\"created\":0,\"model\":\"elm-v1\","
                                    "\"choices\":[{\"index\":0,\"message\":{"
                                    "\"role\":\"assistant\",\"content\":\"[ELM stub — engine not wired]\"},"
                                    "\"finish_reason\":\"stop\"}],"
                                    "\"usage\":{\"prompt_tokens\":0,\"completion_tokens\":0,\"total_tokens\":0}}";

    return DuplicateString( kStubJson );
}

GENIUS_ELM_CHAT_C_API void GeniusElmStringFree( char* value ) GENIUS_ELM_CHAT_C_NOEXCEPT
{
    std::free( value );
}
