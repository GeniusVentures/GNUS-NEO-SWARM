#ifndef GENIUS_MOS_SLM_GENIUS_SLM_CHAT_C_H
#define GENIUS_MOS_SLM_GENIUS_SLM_CHAT_C_H

#include <stddef.h>

#if defined(_WIN32)
#if defined(GENIUS_SLM_CHAT_C_EXPORTS)
#define GENIUS_SLM_CHAT_C_API __declspec(dllexport)
#else
#define GENIUS_SLM_CHAT_C_API __declspec(dllimport)
#endif
#else
#define GENIUS_SLM_CHAT_C_API
#endif

#if defined(__cplusplus)
#define GENIUS_SLM_CHAT_C_NOEXCEPT noexcept
extern "C"
{
#else
#define GENIUS_SLM_CHAT_C_NOEXCEPT
#endif

/**
 * \brief Creates a stub OpenAI v1-style chat completion response.
 *
 * The current implementation returns a fixed UTF-8 JSON payload that matches
 * the general shape of a `/v1/chat/completions` response.
 *
 * \param requestJson Optional UTF-8 JSON request payload. The stub currently
 * ignores the payload contents.
 * \return Heap-allocated UTF-8 JSON string, or `NULL` on allocation failure.
 * The caller must release the returned buffer with `GeniusSlmStringFree`.
 */
GENIUS_SLM_CHAT_C_API char * GeniusSlmChatCompletionsCreate(const char * requestJson) GENIUS_SLM_CHAT_C_NOEXCEPT;

/**
 * \brief Releases a string buffer returned by the chat FFI API.
 *
 * \param value Heap-allocated string returned by
 * `GeniusSlmChatCompletionsCreate`. `NULL` is allowed.
 */
GENIUS_SLM_CHAT_C_API void GeniusSlmStringFree(char * value) GENIUS_SLM_CHAT_C_NOEXCEPT;

#if defined(__cplusplus)
}
#endif

#endif // GENIUS_MOS_SLM_GENIUS_SLM_CHAT_C_H

