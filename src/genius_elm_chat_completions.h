#ifndef GNUS_NEO_SWARM_GENIUS_ELM_CHAT_C_H
#define GNUS_NEO_SWARM_GENIUS_ELM_CHAT_C_H

#include <stddef.h>

#if defined( _WIN32 )
#if defined( NEOSWARM_CHAT_C_EXPORTS )
#define GENIUS_ELM_CHAT_C_API __declspec( dllexport )
#else
#define GENIUS_ELM_CHAT_C_API __declspec( dllimport )
#endif
#else
#define GENIUS_ELM_CHAT_C_API
#endif

#if defined( __cplusplus )
#define GENIUS_ELM_CHAT_C_NOEXCEPT noexcept
extern "C"
{
#else
#define GENIUS_ELM_CHAT_C_NOEXCEPT
#endif

    /**
     * \brief Initialises the Genius ELM engine.
     *
     * Must be called before \c GeniusElmChatCompletionsCreate if a real model is
     * available. If not called, the engine starts in stub mode (returns canned
     * responses) which is useful for UI development and testing.
     *
     * \param modelPath      Path to the MNN model file, or NULL for stub mode.
     * \param knowledgePath  Path to a Grokipedia facts CSV, or NULL to disable.
     * \return 0 on success, -1 on failure.
     */
    GENIUS_ELM_CHAT_C_API int GeniusElmInit( const char* modelPath,
                                             const char* knowledgePath ) GENIUS_ELM_CHAT_C_NOEXCEPT;

    /**
     * \brief Creates an OpenAI v1-style chat completion response.
     *
     * Parses the last user message from \p requestJson, routes it through the
     * GeniusAPIServer pipeline (router → inference → optional specialist), and
     * returns a JSON string matching the /v1/chat/completions response schema.
     *
     * If \c GeniusElmInit has not been called, the engine initialises in stub
     * mode on the first call.
     *
     * \param requestJson  UTF-8 JSON request in OpenAI v1 format, or NULL.
     * \return Heap-allocated UTF-8 JSON string. The caller must release it with
     *         \c GeniusElmStringFree. Returns NULL only on allocation failure.
     */
    GENIUS_ELM_CHAT_C_API char* GeniusElmChatCompletionsCreate( const char* requestJson ) GENIUS_ELM_CHAT_C_NOEXCEPT;

    /**
     * \brief Releases a string buffer returned by the chat FFI API.
     *
     * \param value  Heap-allocated string returned by
     *               \c GeniusElmChatCompletionsCreate. NULL is allowed.
     */
    GENIUS_ELM_CHAT_C_API void GeniusElmStringFree( char* value ) GENIUS_ELM_CHAT_C_NOEXCEPT;

    /**
     * \brief Returns the current engine status as a JSON string.
     *
     * The returned JSON contains:
     *   - "model_loaded": bool — whether a real model is loaded
     *   - "mode": string — "sgprocessing", "interpreter", or "stub"
     *   - "backend": string — "vulkan", "cpu", or "none"
     *   - "node_id": string — the node's peer identity
     *
     * \return Heap-allocated UTF-8 JSON string. The caller must release it with
     *         \c GeniusElmStringFree. Returns NULL only on allocation failure.
     */
    GENIUS_ELM_CHAT_C_API char* GeniusElmGetStatus( void ) GENIUS_ELM_CHAT_C_NOEXCEPT;

#if defined( __cplusplus )
}
#endif

#endif // GNUS_NEO_SWARM_GENIUS_ELM_CHAT_C_H
