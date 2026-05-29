/**
 * @file       genius_slm_chat_c.cpp
 * @brief      C FFI entry points — wires OpenAI v1 chat API to GeniusAPIServer
 * @date       2026-05-08
 * @author     Subaskar S (ssivakumar@gnus.ai)
 */

#include "genius_slm_chat_c.h"
#include "api/GeniusAPIServer.hpp"
#include "common/Types.hpp"

#include <cstdlib>
#include <cstring>
#include <ctime>
#include <string>

using namespace sgns::neoswarm;

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------
namespace
{
    /**
     * @brief Copy a UTF-8 string into a heap buffer for FFI callers.
     */
    char *DuplicateString( const std::string &value ) noexcept
    {
        const size_t buf_size = value.size() + 1U;
        char *const  result   = static_cast<char *>( std::malloc( buf_size ) );
        if ( result == nullptr )
        {
            return nullptr;
        }
        std::memcpy( result, value.c_str(), buf_size );
        return result;
    }

    /**
     * @brief Extract the last user message content from an OpenAI v1 JSON request.
     *
     * Parses {"messages": [{"role": "user", "content": "..."}]} and returns
     * the content of the last user message. Falls back to the raw string if
     * parsing fails.
     */
    std::string ExtractPrompt( const char *request_json ) noexcept
    {
        if ( request_json == nullptr )
        {
            return "";
        }

        const std::string json( request_json );
        const std::string role_key    = "\"role\"";
        const std::string user_val    = "\"user\"";
        const std::string content_key = "\"content\"";

        size_t search_pos        = 0;
        size_t last_user_content = std::string::npos;

        while ( true )
        {
            size_t role_pos = json.find( role_key, search_pos );
            if ( role_pos == std::string::npos ) break;

            size_t colon_pos = json.find( ':', role_pos + role_key.size() );
            if ( colon_pos == std::string::npos ) break;

            size_t value_start = json.find_first_not_of( " \t\r\n", colon_pos + 1 );
            if ( value_start == std::string::npos ) break;

            if ( json.compare( value_start, user_val.size(), user_val ) == 0 )
            {
                size_t obj_start  = json.rfind( '{', role_pos );
                if ( obj_start == std::string::npos ) obj_start = 0;

                size_t content_pos = json.find( content_key, obj_start );
                if ( content_pos != std::string::npos
                     && content_pos < json.find( '}', role_pos ) )
                {
                    size_t c_colon = json.find( ':', content_pos + content_key.size() );
                    if ( c_colon != std::string::npos )
                    {
                        size_t c_start = json.find_first_not_of( " \t\r\n", c_colon + 1 );
                        if ( c_start != std::string::npos && json[c_start] == '"' )
                        {
                            last_user_content = c_start + 1;
                        }
                    }
                }
            }
            search_pos = role_pos + role_key.size();
        }

        if ( last_user_content != std::string::npos )
        {
            size_t c_end = json.find( '"', last_user_content );
            while ( c_end != std::string::npos && json[c_end - 1] == '\\' )
            {
                c_end = json.find( '"', c_end + 1 );
            }
            if ( c_end != std::string::npos )
            {
                std::string content = json.substr( last_user_content, c_end - last_user_content );
                std::string unescaped;
                unescaped.reserve( content.size() );
                for ( size_t i = 0; i < content.size(); ++i )
                {
                    if ( content[i] == '\\' && i + 1 < content.size() )
                    {
                        ++i;
                        switch ( content[i] )
                        {
                            case 'n':  unescaped += '\n'; break;
                            case 't':  unescaped += '\t'; break;
                            case 'r':  unescaped += '\r'; break;
                            case '"':  unescaped += '"';  break;
                            case '\\': unescaped += '\\'; break;
                            default:   unescaped += content[i]; break;
                        }
                    }
                    else
                    {
                        unescaped += content[i];
                    }
                }
                return unescaped;
            }
        }
        return json;
    }

    /**
     * @brief Format a GeniusResponse as an OpenAI v1 chat.completion JSON string.
     */
    std::string FormatAsOpenAIResponse( const GeniusResponse &resp ) noexcept
    {
        const long long created = static_cast<long long>( std::time( nullptr ) );

        std::string escaped;
        escaped.reserve( resp.output_.size() );
        for ( char c : resp.output_ )
        {
            switch ( c )
            {
                case '"':  escaped += "\\\""; break;
                case '\\': escaped += "\\\\"; break;
                case '\n': escaped += "\\n";  break;
                case '\r': escaped += "\\r";  break;
                case '\t': escaped += "\\t";  break;
                default:   escaped += c;      break;
            }
        }

        const std::string model = resp.success_ ? "genius-neo-swarm" : "genius-neo-swarm-error";

        return std::string( R"({"id":"chatcmpl-)" )
             + resp.task_id_
             + R"(","object":"chat.completion","created":)"
             + std::to_string( created )
             + R"(,"model":")"
             + model
             + R"(","choices":[{"index":0,"message":{"role":"assistant","content":")"
             + escaped
             + R"("},"finish_reason":"stop"}],"usage":{"prompt_tokens":0,"completion_tokens":0,"total_tokens":0}})";
    }

    // -----------------------------------------------------------------------
    // Singleton GeniusAPIServer
    // -----------------------------------------------------------------------
    std::unique_ptr<api::GeniusAPIServer> g_server;
    std::string                            g_model_path;
    std::string                            g_knowledge_path;

    void InitServer() noexcept
    {
        api::GeniusAPIServer::Config cfg;
        cfg.model_path_       = g_model_path;
        cfg.knowledge_facts_  = g_knowledge_path;
        cfg.enable_network_   = false;
        cfg.enable_knowledge_ = !g_knowledge_path.empty();

        g_server = std::make_unique<api::GeniusAPIServer>( cfg );
        auto res = g_server->Initialize();
        if ( !res.has_value() )
        {
            std::fprintf( stderr, "[genius-slm] GeniusAPIServer::Initialize failed\n" );
        }
    }

} // anonymous namespace

// ---------------------------------------------------------------------------
// Public C API
// ---------------------------------------------------------------------------

int GeniusSlmInit( const char *model_path, const char *knowledge_path ) noexcept
{
    if ( model_path != nullptr )     g_model_path     = model_path;
    if ( knowledge_path != nullptr ) g_knowledge_path = knowledge_path;

    // Reset and re-initialise with new paths
    g_server.reset();
    InitServer();

    return ( g_server != nullptr ) ? 0 : -1;
}

char *GeniusSlmChatCompletionsCreate( const char *request_json ) noexcept
{
    // Lazy init on first call if GeniusSlmInit was never called
    if ( g_server == nullptr )
    {
        InitServer();
    }

    if ( g_server == nullptr )
    {
        const std::string err_json =
            R"({"error":{"message":"GeniusAPIServer not initialized","type":"server_error"}})";
        return DuplicateString( err_json );
    }

    const std::string prompt = ExtractPrompt( request_json );

    Task task;
    task.prompt_     = prompt;
    task.mode_       = ExecutionMode::SingleNode;
    task.max_tokens_ = 512;

    auto result = g_server->Process( task );

    if ( !result.has_value() )
    {
        const std::string err_json =
            R"({"error":{"message":"inference error","type":"inference_error"}})";
        return DuplicateString( err_json );
    }

    return DuplicateString( FormatAsOpenAIResponse( result.value() ) );
}

void GeniusSlmStringFree( char *value ) noexcept
{
    std::free( value );
}

char *GeniusSlmGetStatus( void ) noexcept
{
    if ( g_server == nullptr )
    {
        return DuplicateString(
            R"({"model_loaded":false,"mode":"uninitialized","backend":"none","node_id":""})" );
    }

    const bool   model_loaded = !g_model_path.empty();
    const char  *mode         = "stub";
    const char  *backend      = "vulkan";

    // Check SG connectivity if network mode is configured
    bool sgConnected = false;
    bool fallbackActive = false;
    if ( g_server )
    {
        sgConnected   = g_server->IsSuperGeniusConnected();
        // fallback is active if we expected SG but aren't connected
        // This is a simplified check — the bridge knows more precisely
        fallbackActive = !sgConnected;
    }

    std::string json = R"({"model_loaded":)";
    json += model_loaded ? "true" : "false";
    json += R"(,"mode":")";
    json += mode;
    json += R"(","backend":")";
    json += backend;
    json += R"(","model_path":")";
    json += g_model_path;
    json += R"(","supergenius_connected":)";
    json += sgConnected ? "true" : "false";
    json += R"(,"fallback_active":)";
    json += fallbackActive ? "true" : "false";
    json += R"("})";

    return DuplicateString( json );
}
