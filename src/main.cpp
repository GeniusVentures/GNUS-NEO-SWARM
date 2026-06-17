/**
 * @file       genius_chat.cpp
 * @brief      CLI entry point for GNUS NEO SWARM
 * @date       2026-05-08
 *
 * Usage:
 *   neo-swarm --model <path> [options]
 *
 * Options:
 *   --model <path>          Path to core MNN model file (required)
 *   --grammar-model <path>  Path to grammar specialist model
 *   --math-model <path>     Path to math specialist model
 *   --mode single|specialist|swarm   Execution mode (default: auto)
 *   --prompt <text>         Prompt to process (interactive if omitted)
 *   --port <n>              gRPC port (default: 50051)
 *   --db <path>             Reputation DB path (default: ./reputation.db)
 *   --key <path>            Node key file (default: ./node.key)
 *   --network               Enable P2P networking
 *   --knowledge <path>      Path to Grokipedia facts CSV
 *   --max-tokens <n>        Max tokens to generate (default: 512)
 *   --temperature <f>       Sampling temperature (default: 0.7)
 *   --serve                 Start gRPC server (blocking)
 *   --verbose               Enable debug logging
 *   --help                  Show this help
 */

#include "api/api_server.hpp"
#include "common/logging.hpp"

#include <fstream>
#include <iostream>
#include <nlohmann/json.hpp>
#include <stdexcept>
#include <string>

using namespace sgns::neoswarm;

// ---------------------------------------------------------------------------
// Argument parser
// ---------------------------------------------------------------------------
struct Args
{
    std::string m_modelPath;
    std::string grammar_m_modelPath;
    std::string math_m_modelPath;
    std::string m_mode = "auto";
    std::string m_prompt;
    int port_ = 50051;
    std::string db_path_ = "./reputation.db";
    std::string key_file_ = "./node.key";
    std::string m_knowledgepath_;
    int m_maxTokens = 512;
    float m_temperature = 0.7f;
    std::string sg_m_endpoint = "localhost:50051";
    std::string m_sgTlsCa;
    std::string m_sgTlsCert;
    std::string config_path_;
    bool network_ = false;
    bool serve_ = false;
    bool verbose_ = false;
    bool help_ = false;
};

static void PrintHelp( const char* prog )
{
    std::cout << "Usage: " << prog << " --model <path> [options]\n\n"
              << "Options:\n"
              << "  --model <path>           Core MNN model file (required)\n"
              << "  --grammar-model <path>   Grammar specialist model\n"
              << "  --math-model <path>      Math specialist model\n"
              << "  --mode single|specialist|swarm  Execution mode (default: auto)\n"
              << "  --prompt <text>          Prompt to process\n"
              << "  --port <n>               gRPC port (default: 50051)\n"
              << "  --db <path>              Reputation DB (default: ./reputation.db)\n"
              << "  --key <path>             Node key file (default: ./node.key)\n"
              << "  --config <path>         JSON config file (CLI flags override file values)\n"
              << "  --sg-endpoint <host:port> SuperGenius node address (default: localhost:50051)\n"
              << "  --sg-tls-ca <path>       TLS CA certificate bundle for SuperGenius\n"
              << "  --sg-tls-cert <path>     TLS client certificate for SuperGenius\n"
              << "  --network                Enable P2P networking\n"
              << "  --knowledge <path>       Grokipedia facts CSV\n"
              << "  --max-tokens <n>         Max tokens (default: 512)\n"
              << "  --temperature <f>        Temperature (default: 0.7)\n"
              << "  --serve                  Start gRPC server\n"
              << "  --verbose                Debug logging\n"
              << "  --help                   Show this help\n";
}

// ---------------------------------------------------------------------------
// Config file loader
// ---------------------------------------------------------------------------
static void LoadConfigFile( const std::string& path, Args& args )
{
    std::ifstream f( path );
    if ( !f.is_open() )
    {
        std::cerr << "Warning: cannot open config file '" << path << "'\n";
        return;
    }

    nlohmann::json j;
    try
    {
        f >> j;
    }
    catch ( const std::exception& e )
    {
        std::cerr << "Warning: invalid JSON in config file '" << path << "': " << e.what() << "\n";
        return;
    }

    // Only set defaults — CLI args will override
    if ( j.contains( "model" ) && args.m_modelPath.empty() )
        args.m_modelPath = j["model"].get<std::string>();
    if ( j.contains( "grammar_model" ) && args.grammar_m_modelPath.empty() )
        args.grammar_m_modelPath = j["grammar_model"].get<std::string>();
    if ( j.contains( "math_model" ) && args.math_m_modelPath.empty() )
        args.math_m_modelPath = j["math_model"].get<std::string>();
    if ( j.contains( "mode" ) && args.m_mode == "auto" )
        args.m_mode = j["mode"].get<std::string>();
    if ( j.contains( "port" ) && args.port_ == 50051 )
        args.port_ = j["port"].get<int>();
    if ( j.contains( "db" ) && args.db_path_ == "./reputation.db" )
        args.db_path_ = j["db"].get<std::string>();
    if ( j.contains( "key" ) && args.key_file_ == "./node.key" )
        args.key_file_ = j["key"].get<std::string>();
    if ( j.contains( "knowledge" ) && args.m_knowledgepath_.empty() )
        args.m_knowledgepath_ = j["knowledge"].get<std::string>();
    if ( j.contains( "max_tokens" ) && args.m_maxTokens == 512 )
        args.m_maxTokens = j["max_tokens"].get<int>();
    if ( j.contains( "temperature" ) && args.m_temperature == 0.7f )
        args.m_temperature = j["temperature"].get<float>();
    if ( j.contains( "sg_endpoint" ) && args.sg_m_endpoint == "localhost:50051" )
        args.sg_m_endpoint = j["sg_endpoint"].get<std::string>();
    if ( j.contains( "network" ) && !args.network_ )
        args.network_ = j["network"].get<bool>();
    if ( j.contains( "verbose" ) && !args.verbose_ )
        args.verbose_ = j["verbose"].get<bool>();

    std::cout << "Loaded config: " << path << "\n";
}

static Args ParseArgs( int argc, char** argv )
{
    Args args;
    for ( int i = 1; i < argc; ++i )
    {
        std::string a = argv[i];
        auto next = [&]() -> std::string
        {
            if ( i + 1 >= argc )
                throw std::runtime_error( "missing value for " + a );
            return argv[++i];
        };
        if ( a == "--model" )
            args.m_modelPath = next();
        else if ( a == "--grammar-model" )
            args.grammar_m_modelPath = next();
        else if ( a == "--math-model" )
            args.math_m_modelPath = next();
        else if ( a == "--mode" )
            args.m_mode = next();
        else if ( a == "--prompt" )
            args.m_prompt = next();
        else if ( a == "--port" )
            args.port_ = std::stoi( next() );
        else if ( a == "--db" )
            args.db_path_ = next();
        else if ( a == "--key" )
            args.key_file_ = next();
        else if ( a == "--knowledge" )
            args.m_knowledgepath_ = next();
        else if ( a == "--max-tokens" )
            args.m_maxTokens = std::stoi( next() );
        else if ( a == "--temperature" )
            args.m_temperature = std::stof( next() );
        else if ( a == "--config" )
            args.config_path_ = next();
        else if ( a == "--sg-endpoint" )
            args.sg_m_endpoint = next();
        else if ( a == "--sg-tls-ca" )
            args.m_sgTlsCa = next();
        else if ( a == "--sg-tls-cert" )
            args.m_sgTlsCert = next();
        else if ( a == "--network" )
            args.network_ = true;
        else if ( a == "--serve" )
            args.serve_ = true;
        else if ( a == "--verbose" )
            args.verbose_ = true;
        else if ( a == "--help" )
            args.help_ = true;
        else
            std::cerr << "Unknown option: " << a << "\n";
    }
    return args;
}

static ExecutionMode ParseMode( const std::string& mode )
{
    if ( mode == "single" )
        return ExecutionMode::SingleNode;
    if ( mode == "specialist" )
        return ExecutionMode::Specialist;
    if ( mode == "swarm" )
        return ExecutionMode::Swarm;
    return ExecutionMode::SingleNode; // "auto" — router decides
}

// ---------------------------------------------------------------------------
// Interactive REPL
// ---------------------------------------------------------------------------
static void RunInteractive( api::ApiServer& server, ExecutionMode mode, int max_tokens, float temperature )
{
    std::cout << "\nNEO SWARM v1 — Interactive Mode\n"
              << "Type your prompt and press Enter. Type 'quit' to exit.\n\n";

    std::string line;
    while ( true )
    {
        std::cout << "> ";
        if ( !std::getline( std::cin, line ) )
            break;
        if ( line == "quit" || line == "exit" )
            break;
        if ( line.empty() )
            continue;

        Task task;
        task.m_prompt = line;
        task.m_mode = mode;
        task.m_maxTokens = static_cast<uint32_t>( max_tokens );
        task.m_temperature = temperature;

        auto res = server.Process( task );
        if ( !res.has_value() )
        {
            std::cerr << "[ERROR] inference failed\n";
        }
        else
        {
            std::cout << "\n" << res.value().m_output << "\n\n";
            std::cout << "[mode=" << static_cast<int>( res.value().m_modeUsed )
                      << " latency=" << res.value().m_totalLatencyMs << "ms]\n\n";
        }
    }
}

// ---------------------------------------------------------------------------
// main
// ---------------------------------------------------------------------------
int main( int argc, char** argv )
{
    Args args;
    try
    {
        args = ParseArgs( argc, argv );
    }
    catch ( const std::exception& e )
    {
        std::cerr << "Argument error: " << e.what() << "\n";
        return 1;
    }

    if ( args.help_ )
    {
        PrintHelp( argv[0] );
        return 0;
    }

    // Load config file if specified (CLI flags already parsed, override file values)
    if ( !args.config_path_.empty() )
    {
        LoadConfigFile( args.config_path_, args );
    }

    if ( args.verbose_ )
    {
        spdlog::set_level( spdlog::level::debug );
    }

    // Build server config
    api::ApiServer::Config cfg;
    cfg.m_modelPath = args.m_modelPath;
    cfg.grammar_m_modelPath = args.grammar_m_modelPath;
    cfg.math_m_modelPath = args.math_m_modelPath;
    cfg.m_reputationDbPath = args.db_path_;
    cfg.m_knowledgefacts_ = args.m_knowledgepath_;
    cfg.m_enableNetwork = args.network_;
    cfg.m_enableKnowledge = true;
    (void) args.port_;
    cfg.m_nodeKeyFile = args.key_file_;
    cfg.sg_m_endpoint = args.sg_m_endpoint;
    cfg.m_sgTlsCa = args.m_sgTlsCa;
    cfg.m_sgTlsCert = args.m_sgTlsCert;

    api::ApiServer server( cfg );

    auto init_res = server.Initialize();
    if ( !init_res.has_value() )
    {
        std::cerr << "[FATAL] Initialization failed\n";
        return 1;
    }

    ExecutionMode mode = ( args.m_mode == "auto" ) ? ExecutionMode::SingleNode : ParseMode( args.m_mode );

    if ( args.serve_ )
    {
        auto serve_res = server.Serve();
        if ( !serve_res.has_value() )
        {
            std::cerr << "[FATAL] Serve failed\n";
            return 1;
        }
        return 0;
    }

    if ( !args.m_prompt.empty() )
    {
        Task task;
        task.m_prompt = args.m_prompt;
        task.m_mode = mode;
        task.m_maxTokens = static_cast<uint32_t>( args.m_maxTokens );
        task.m_temperature = args.m_temperature;

        auto res = server.Process( task );
        if ( !res.has_value() )
        {
            std::cerr << "[ERROR] inference failed\n";
            return 1;
        }
        std::cout << res.value().m_output << "\n";
        return 0;
    }

    RunInteractive( server, mode, args.m_maxTokens, args.m_temperature );
    return 0;
}
