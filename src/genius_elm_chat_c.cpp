#include "genius_elm_chat_c.h"

#include <cstdlib>
#include <cstring>
#include <string>

namespace
{
    /**
     * \brief Copies a UTF-8 string into a heap buffer for FFI callers.
     *
     * \param value Source string to copy.
     * \return Heap-allocated null-terminated buffer, or `nullptr` on failure.
     */
    char * DuplicateString(const std::string & value) noexcept
    {
        const size_t bufferSize = value.size() + 1U;
        char * const result = static_cast<char *>(std::malloc(bufferSize));

        if ( result == nullptr )
        {
            return nullptr;
        }

        std::memcpy(result, value.c_str(), bufferSize);
        return result;
    }
}

char * GeniusElmChatCompletionsCreate(const char * requestJson) noexcept
{
    static_cast<void>(requestJson);

    const std::string responseJson =
        R"JSON({"id":"chatcmpl-stub","object":"chat.completion","created":1742688000,"model":"GNUS-NEO-SWARM-stub","choices":[{"index":0,"message":{"role":"assistant","content":"Stub response from GNUS-NEO-SWARM. Local OpenAI v1 chat behavior will be implemented behind this ABI."},"finish_reason":"stop"}],"usage":{"prompt_tokens":0,"completion_tokens":0,"total_tokens":0}})JSON";

    return DuplicateString(responseJson);
}

void GeniusElmStringFree(char * value) noexcept
{
    std::free(value);
}
