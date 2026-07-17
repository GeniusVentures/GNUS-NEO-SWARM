#ifndef GNUS_NEO_SWARM_GENIUS_ELM_CHAT_C_H
#define GNUS_NEO_SWARM_GENIUS_ELM_CHAT_C_H

#include <stddef.h>

#if defined( _WIN32 )
#if defined( NEOSWARM_CHAT_C_EXPORTS )
#define NEOSWARM_ELM_CHAT_C_API __declspec( dllexport )
#else
#define NEOSWARM_ELM_CHAT_C_API __declspec( dllimport )
#endif
#else
#define NEOSWARM_ELM_CHAT_C_API
#endif

#if defined( __cplusplus )
#define NEOSWARM_ELM_CHAT_C_NOEXCEPT noexcept
extern "C"
{
#else
#define NEOSWARM_ELM_CHAT_C_NOEXCEPT
#endif

    /**
 * \brief Initialises the Genius ELM engine.
 *
 * Creates and initialises an ApiServer instance with the given model and
 * knowledge paths. Must be called before \c GeniusElmChatCompletionsCreate
 * for real inference; falls back to stub mode if not called.
 *
 * Thread-safe: may be called multiple times. Subsequent calls are no-ops.
 *
 * \param modelPath      Path to the MNN model file, or NULL for stub mode.
 * \param knowledgePath  Path to a Grokipedia facts CSV, or NULL to disable.
 * \return 0 on success, -1 if ApiServer initialization fails.
 */
    NEOSWARM_ELM_CHAT_C_API int GeniusElmInit( const char* modelPath,
                                             const char* knowledgePath ) NEOSWARM_ELM_CHAT_C_NOEXCEPT;

    /**
     * \brief Creates an OpenAI v1-style chat completion response.
     *
     * Parses the last user message from \p requestJson via nlohmann::json,
     * dispatches through the ApiServer pipeline (router → inference →
     * optional specialist), and returns a JSON chat completion.
     *
     * Falls back to a stub response if GeniusElmInit has not been called
     * or if the ApiServer fails to process the request.
     *
     * Thread-safe via global mutex.
     *
     * \param requestJson  UTF-8 JSON request in OpenAI v1 format, or NULL.
     * \return Heap-allocated UTF-8 JSON string. Caller must release with
     *         \c GeniusElmStringFree. Returns NULL only on allocation failure.
     */
    NEOSWARM_ELM_CHAT_C_API char* GeniusElmChatCompletionsCreate( const char* requestJson ) NEOSWARM_ELM_CHAT_C_NOEXCEPT;

    /**
     * \brief Releases a string buffer returned by the chat FFI API.
     *
     * \param value  Heap-allocated string returned by
     *               \c GeniusElmChatCompletionsCreate. NULL is allowed.
     */
    NEOSWARM_ELM_CHAT_C_API void GeniusElmStringFree( char* value ) NEOSWARM_ELM_CHAT_C_NOEXCEPT;

    /**
     * \brief Returns the current engine status as a JSON string.
     *
     * The returned JSON contains:
     *   - "model_loaded": bool
     *   - "mode": string — "active", "idle", or "stub"
     *   - "backend": string — "cpu", "vulkan", or "none"
     *   - "node_id": string — local node identifier
     *   - "supergenius_connected": bool
     *   - "fallback_active": bool
     *
     * Thread-safe via global mutex.
     *
     * \return Heap-allocated UTF-8 JSON string. Caller must release with
     *         \c GeniusElmStringFree. Returns NULL only on allocation failure.
     */
    NEOSWARM_ELM_CHAT_C_API char* GeniusElmGetStatus( void ) NEOSWARM_ELM_CHAT_C_NOEXCEPT;

    /**
     * \brief Shuts down the Genius ELM engine.
     *
     * Destroys the ApiServer instance and releases all associated resources.
     * Must be called before program exit to ensure clean teardown of the
     * inference engine, networking stack, and other subsystems before the
     * C runtime finalizes static destructors.
     *
     * Thread-safe via global mutex.
     *
     * \return 0 on success, -1 if shutdown fails.
     */
    NEOSWARM_ELM_CHAT_C_API int GeniusElmShutdown( void ) NEOSWARM_ELM_CHAT_C_NOEXCEPT;

#if defined( __cplusplus )
}
#endif

#endif // GNUS_NEO_SWARM_GENIUS_ELM_CHAT_C_H
