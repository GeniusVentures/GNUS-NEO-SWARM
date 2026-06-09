/**
 * @file       genius_chat.cpp
 * @brief      CLI entry point for GNUS NEO SWARM
 * @date       2026-05-08
 * @author     Subaskar S (ssivakumar@gnus.ai)
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

#include "api/GeniusAPIServer.hpp"
#include "common/Logging.hpp"

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
    std::string model_path_;
    std::string grammar_model_path_;
    std::string math_model_path_;
    std::string mode_ = "auto";
    std::string prompt_;
    int port_ = 50051;
    std::string db_path_ = "./reputation.db";
    std::string key_file_ = "./node.key";
    std::string knowledge_path_;
    int max_tokens_ = 512;
    float temperature_ = 0.7f;
    std::string sg_endpoint_ = "localhost:50051";
    std::string sg_tls_ca_;
    std::string sg_tls_cert_;
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
    if ( j.contains( "model" ) && args.model_path_.empty() )
        args.model_path_ = j["model"].get<std::string>();
    if ( j.contains( "grammar_model" ) && args.grammar_model_path_.empty() )
        args.grammar_model_path_ = j["grammar_model"].get<std::string>();
    if ( j.contains( "math_model" ) && args.math_model_path_.empty() )
        args.math_model_path_ = j["math_model"].get<std::string>();
    if ( j.contains( "mode" ) && args.mode_ == "auto" )
        args.mode_ = j["mode"].get<std::string>();
    if ( j.contains( "port" ) && args.port_ == 50051 )
        args.port_ = j["port"].get<int>();
    if ( j.contains( "db" ) && args.db_path_ == "./reputation.db" )
        args.db_path_ = j["db"].get<std::string>();
    if ( j.contains( "key" ) && args.key_file_ == "./node.key" )
        args.key_file_ = j["key"].get<std::string>();
    if ( j.contains( "knowledge" ) && args.knowledge_path_.empty() )
        args.knowledge_path_ = j["knowledge"].get<std::string>();
    if ( j.contains( "max_tokens" ) && args.max_tokens_ == 512 )
        args.max_tokens_ = j["max_tokens"].get<int>();
    if ( j.contains( "temperature" ) && args.temperature_ == 0.7f )
        args.temperature_ = j["temperature"].get<float>();
    if ( j.contains( "sg_endpoint" ) && args.sg_endpoint_ == "localhost:50051" )
        args.sg_endpoint_ = j["sg_endpoint"].get<std::string>();
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
            args.model_path_ = next();
        else if ( a == "--grammar-model" )
            args.grammar_model_path_ = next();
        else if ( a == "--math-model" )
            args.math_model_path_ = next();
        else if ( a == "--mode" )
            args.mode_ = next();
        else if ( a == "--prompt" )
            args.prompt_ = next();
        else if ( a == "--port" )
            args.port_ = std::stoi( next() );
        else if ( a == "--db" )
            args.db_path_ = next();
        else if ( a == "--key" )
            args.key_file_ = next();
        else if ( a == "--knowledge" )
            args.knowledge_path_ = next();
        else if ( a == "--max-tokens" )
            args.max_tokens_ = std::stoi( next() );
        else if ( a == "--temperature" )
            args.temperature_ = std::stof( next() );
        else if ( a == "--config" )
            args.config_path_ = next();
        else if ( a == "--sg-endpoint" )
            args.sg_endpoint_ = next();
        else if ( a == "--sg-tls-ca" )
            args.sg_tls_ca_ = next();
        else if ( a == "--sg-tls-cert" )
            args.sg_tls_cert_ = next();
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
static void RunInteractive( api::GeniusAPIServer& server, ExecutionMode mode, int max_tokens, float temperature )
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
        task.prompt_ = line;
        task.mode_ = mode;
        task.max_tokens_ = static_cast<uint32_t>( max_tokens );
        task.temperature_ = temperature;

        auto res = server.Process( task );
        if ( !res.has_value() )
        {
            std::cerr << "[ERROR] inference failed\n";
        }
        else
        {
            std::cout << "\n" << res.value().output_ << "\n\n";
            std::cout << "[mode=" << static_cast<int>( res.value().mode_used_ )
                      << " latency=" << res.value().total_latency_ms_ << "ms]\n\n";
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
    api::GeniusAPIServer::Config cfg;
    cfg.model_path_ = args.model_path_;
    cfg.grammar_model_path_ = args.grammar_model_path_;
    cfg.math_model_path_ = args.math_model_path_;
    cfg.reputation_db_path_ = args.db_path_;
    cfg.knowledge_facts_ = args.knowledge_path_;
    cfg.enable_network_ = args.network_;
    cfg.enable_knowledge_ = true;
    (void) args.port_;
    cfg.node_key_file_ = args.key_file_;
    cfg.sg_endpoint_ = args.sg_endpoint_;
    cfg.sg_tls_ca_ = args.sg_tls_ca_;
    cfg.sg_tls_cert_ = args.sg_tls_cert_;

    api::GeniusAPIServer server( cfg );

    auto init_res = server.Initialize();
    if ( !init_res.has_value() )
    {
        std::cerr << "[FATAL] Initialization failed\n";
        return 1;
    }

    ExecutionMode mode = ( args.mode_ == "auto" ) ? ExecutionMode::SingleNode : ParseMode( args.mode_ );

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

    if ( !args.prompt_.empty() )
    {
        Task task;
        task.prompt_ = args.prompt_;
        task.mode_ = mode;
        task.max_tokens_ = static_cast<uint32_t>( args.max_tokens_ );
        task.temperature_ = args.temperature_;

        auto res = server.Process( task );
        if ( !res.has_value() )
        {
            std::cerr << "[ERROR] inference failed\n";
            return 1;
        }
        std::cout << res.value().output_ << "\n";
        return 0;
    }

    RunInteractive( server, mode, args.max_tokens_, args.temperature_ );
    return 0;
}
