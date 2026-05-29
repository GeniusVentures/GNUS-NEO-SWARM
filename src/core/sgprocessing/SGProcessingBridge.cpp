/**
 * @file       SGProcessingBridge.cpp
 * @brief      SGProcessingManager bridge — Phase 1 direct inference
 * @date       2026-05-06
 * @author     Subaskar S (ssivakumar@gnus.ai)
 *
 * JSON schema matches SuperGenius/test/src/processing_datatypes/ examples exactly.
 */

#include "SGProcessingBridge.hpp"
#include "network/sg_client/SuperGeniusClient.hpp"
#include "common/Logging.hpp"

#include <boost/asio/io_context.hpp>
#include <nlohmann/json.hpp>

#ifdef __unix__
#    include <unistd.h>  // getcwd
#elif defined(_WIN32)
#    include <direct.h>
#    define getcwd _getcwd
#endif

#ifdef GENIUS_HAS_SGPROCESSING
#    include <processingbase/ProcessingManager.hpp>
#    include <SGNSProcMain.hpp>
#    include <Generators.hpp>
#    include <InputFormat.hpp>
#else
namespace sgns
{
    enum class InputFormat : int
    {
        FLOAT16   = 0,
        FLOAT32   = 1,
        FP4_ULTRA = 2,
        INT16     = 3,
        INT32     = 4,
        INT8      = 5,
        RGB8      = 6,
        RGBA8     = 7
    };
}
#endif

namespace sgns::neoswarm::core
{
    namespace
    {
        auto BridgeLogger()
        {
            return neoswarm::CreateLogger( "SGProcessingBridge" );
        }

        // -----------------------------------------------------------------------
        // InputFormat → JSON type string
        // Maps to the "type" field in the inputs array of the GNUS schema.
        // These match the DataType enum values used by SGProcessingManager.
        // -----------------------------------------------------------------------
        std::string InputFormatToTypeString( sgns::InputFormat fmt )
        {
            switch ( fmt )
            {
                case sgns::InputFormat::FLOAT32:   return "float";
                case sgns::InputFormat::FLOAT16:   return "float";
                case sgns::InputFormat::INT32:     return "int";
                case sgns::InputFormat::INT8:      return "int";
                case sgns::InputFormat::INT16:     return "int";
                case sgns::InputFormat::RGB8:      return "texture2d";
                case sgns::InputFormat::RGBA8:     return "texture2d";
                case sgns::InputFormat::FP4_ULTRA: return "fp4_ultra";  // FP4_ULTRA → dedicated processor
                default:                           return "tensor";
            }
        }

        // -----------------------------------------------------------------------
        // InputFormat → JSON format string
        // Maps to the "format" field in the inputs array.
        // -----------------------------------------------------------------------
        std::string InputFormatToFormatString( sgns::InputFormat fmt )
        {
            switch ( fmt )
            {
                case sgns::InputFormat::FLOAT16:   return "FLOAT16";
                case sgns::InputFormat::FLOAT32:   return "FLOAT32";
                case sgns::InputFormat::INT16:     return "INT16";
                case sgns::InputFormat::INT32:     return "INT32";
                case sgns::InputFormat::INT8:      return "INT8";
                case sgns::InputFormat::RGB8:      return "RGB8";
                case sgns::InputFormat::RGBA8:     return "RGBA8";
                case sgns::InputFormat::FP4_ULTRA: return "FP4_ULTRA";
                default:                           return "FLOAT32";
            }
        }

        // -----------------------------------------------------------------------
        // Ensure a URI is absolute (file:///absolute/path).
        // SGProcessingManager requires absolute file:// URIs.
        // Relative paths like "file://data/input.bin" are patched to absolute.
        // -----------------------------------------------------------------------
        std::string EnsureAbsoluteUri( const std::string &uri )
        {
            // Already absolute: file:///path or file://C:/path
            if ( uri.find( "file:///" ) == 0 || uri.find( "ipfs://" ) == 0 )
            {
                return uri;
            }
            // Relative file:// URI — prepend cwd
            if ( uri.find( "file://" ) == 0 )
            {
                const std::string rel = uri.substr( 7 );  // strip "file://"
                // Use the path as-is if it looks absolute already
                if ( !rel.empty() && ( rel[0] == '/' || ( rel.size() > 1 && rel[1] == ':' ) ) )
                {
                    return uri;
                }
                // Prepend current working directory
                char cwd[4096] = {};
                if ( getcwd( cwd, sizeof( cwd ) ) != nullptr )
                {
                    return std::string( "file://" ) + cwd + "/" + rel;
                }
            }
            return uri;
        }
    }

    SGProcessingBridge::SGProcessingBridge() : cfg_( {} ) {}
    SGProcessingBridge::SGProcessingBridge( Config cfg ) : cfg_( std::move( cfg ) ) {}

    // -----------------------------------------------------------------------
    // BuildSchemaJson
    //
    // Produces JSON matching the exact schema used by SGProcessingManager,
    // as documented in SuperGenius/test/src/processing_datatypes/*.json.
    // -----------------------------------------------------------------------
    outcome::result<std::string> SGProcessingBridge::BuildSchemaJson(
        const std::string          &model_uri,
        const std::string          &input_uri,
        sgns::InputFormat           input_format,
        const std::vector<int64_t> &shape ) const
    {
        if ( model_uri.empty() || input_uri.empty() )
        {
            return outcome::failure( Error::InvalidArgument );
        }

        const std::string type_str   = InputFormatToTypeString( input_format );
        const std::string format_str = InputFormatToFormatString( input_format );

        // Compute flat width from shape (product of all dims)
        int64_t flat_width = 1;
        for ( const auto &dim : shape )
        {
            if ( dim > 0 ) flat_width *= dim;
        }

        // Build shape array for input_nodes and output_nodes
        nlohmann::json shape_json = nlohmann::json::array();
        for ( const auto &dim : shape ) shape_json.push_back( dim );

        // Chunking parameters — block_len is the chunk size for processing,
        // chunk_stride is the step between chunks.
        // For LLM inference: block_len = sequence length, chunk_stride = block_len (no overlap)
        const int64_t block_len    = shape.empty() ? flat_width : shape.back();
        const int64_t chunk_stride = block_len;

        // Ensure URIs are absolute
        const std::string abs_model_uri = EnsureAbsoluteUri( model_uri );
        const std::string abs_input_uri = EnsureAbsoluteUri( input_uri );

        // Derive output URI from input URI (replace extension with _output.raw)
        std::string output_uri = abs_input_uri;
        auto        dot_pos    = output_uri.rfind( '.' );
        if ( dot_pos != std::string::npos )
        {
            output_uri = output_uri.substr( 0, dot_pos ) + "_output.raw";
        }
        else
        {
            output_uri += "_output.raw";
        }

        // -----------------------------------------------------------------------
        // Build JSON matching the GNUS schema exactly
        // -----------------------------------------------------------------------
        nlohmann::json doc;
        doc["name"]              = "neo-swarm-inference";
        doc["version"]           = "1.0.0";
        doc["gnus_spec_version"] = 1.0;
        doc["description"]       = "GeniusNeoSwarm inference job";

        // inputs
        nlohmann::json input_decl;
        input_decl["name"]             = "modelInput";
        input_decl["source_uri_param"] = abs_input_uri;
        input_decl["type"]             = type_str;
        input_decl["format"]           = format_str;
        input_decl["dimensions"]       = {
            { "width",        flat_width  },
            { "block_len",    block_len   },
            { "chunk_stride", chunk_stride }
        };
        doc["inputs"] = nlohmann::json::array( { input_decl } );

        // outputs
        nlohmann::json output_decl;
        output_decl["name"]             = "inferenceOutput";
        output_decl["source_uri_param"] = output_uri;
        output_decl["type"]             = "tensor";
        doc["outputs"] = nlohmann::json::array( { output_decl } );

        // passes
        nlohmann::json input_node;
        input_node["name"]   = "input";
        input_node["type"]   = "tensor";
        input_node["source"] = "input:modelInput";
        input_node["shape"]  = shape_json;

        nlohmann::json output_node;
        output_node["name"]   = "output";
        output_node["type"]   = "tensor";
        output_node["target"] = "output:inferenceOutput";
        output_node["shape"]  = shape_json;

        nlohmann::json model_config;
        model_config["source_uri_param"] = abs_model_uri;
        model_config["format"]           = "MNN";
        model_config["batch_size"]       = 1;
        model_config["input_nodes"]      = nlohmann::json::array( { input_node } );
        model_config["output_nodes"]     = nlohmann::json::array( { output_node } );

        nlohmann::json pass;
        pass["name"]        = "inference";
        pass["type"]        = "inference";
        pass["description"] = "MNN inference pass";
        pass["model"]       = model_config;

        doc["passes"] = nlohmann::json::array( { pass } );

        return outcome::success( doc.dump() );
    }

    // -----------------------------------------------------------------------
    // SubmitJob
    // -----------------------------------------------------------------------
    outcome::result<std::vector<uint8_t>> SGProcessingBridge::SubmitJob(
        const std::string                       &model_uri,
        const std::string                       &input_uri,
        sgns::InputFormat                        input_format,
        const std::vector<int64_t>              &shape,
        std::shared_ptr<boost::asio::io_context> ioc )
    {
        BridgeLogger()->debug( "SubmitJob model={} format={} networkMode={}",
                               model_uri,
                               InputFormatToFormatString( input_format ),
                               static_cast<int>( cfg_.network_mode_ ) );

        auto json_res = BuildSchemaJson( model_uri, input_uri, input_format, shape );
        if ( !json_res.has_value() )
        {
            return outcome::failure( json_res.error() );
        }

        if ( cfg_.network_mode_ )
        {
            auto result = SubmitNetwork( json_res.value() );
            if ( !result.has_value() )
            {
                // Auto-fallback to local MNN on network failure
                // Auth failures (SignatureInvalid) are NOT silently swallowed
                if ( result.error() == Error::SignatureInvalid ||
                     result.error() == Error::IdentityError )
                {
                    BridgeLogger()->error( "Network dispatch auth failed — NOT falling back to local mode" );
                    return result;
                }
                BridgeLogger()->warn( "Network dispatch failed ({}), falling back to local mode",
                                      result.error().message() );
                return SubmitDirect( json_res.value(), ioc );
            }
            return result;
        }
        return SubmitDirect( json_res.value(), ioc );
    }

    // -----------------------------------------------------------------------
    // SubmitDirect — Phase 1: call ProcessingManager locally
    //
    // Follows the exact pattern from processing_datatypes_test.cpp:
    //   1. ProcessingManager::Create(json)
    //   2. GetProcessingData() → get_passes()[0].get_model() → get_input_nodes()[0]
    //   3. Process(ioc, chunkhashes, model_node)
    // -----------------------------------------------------------------------
    outcome::result<std::vector<uint8_t>> SGProcessingBridge::SubmitDirect(
        const std::string                       &jsondata,
        std::shared_ptr<boost::asio::io_context> ioc ) const
    {
#ifdef GENIUS_HAS_SGPROCESSING
        // Step 1: Create ProcessingManager from JSON
        auto pm_result = sgns::sgprocessing::ProcessingManager::Create( jsondata );
        if ( !pm_result )
        {
            BridgeLogger()->error( "ProcessingManager::Create failed (error={})",
                                   pm_result.error().message() );
            return outcome::failure( Error::InferenceFailed );
        }

        auto pm = pm_result.value();

        // Step 2: Extract ModelNode from the first pass's first input node
        // This is the exact pattern from processing_datatypes_test.cpp
        auto processing = pm->GetProcessingData();
        const auto &passes = processing.get_passes();
        if ( passes.empty() )
        {
            return outcome::failure( Error::InferenceFailed );
        }
        if ( !passes[0].get_model().has_value() )
        {
            return outcome::failure( Error::InferenceFailed );
        }
        const auto model_config = passes[0].get_model().value();
        const auto input_nodes  = model_config.get_input_nodes();
        if ( input_nodes.empty() )
        {
            return outcome::failure( Error::InferenceFailed );
        }
        sgns::ModelNode model_node = input_nodes[0];

        // Step 3: Run inference
        std::vector<std::vector<uint8_t>> chunkhashes;
        auto process_result = pm->Process( ioc, chunkhashes, model_node );
        if ( !process_result )
        {
            BridgeLogger()->error( "ProcessingManager::Process failed (error={})",
                                   process_result.error().message() );
            return outcome::failure( Error::InferenceFailed );
        }

        BridgeLogger()->debug( "Process() succeeded: {} bytes, {} chunk hashes",
                               process_result.value().size(),
                               chunkhashes.size() );
        return outcome::success( process_result.value() );
#else
        ( void )jsondata;
        ( void )ioc;
        BridgeLogger()->warn( "SGProcessingBridge: SGProcessingManager not compiled in — stub mode" );
        return outcome::success( std::vector<uint8_t>{} );
#endif
    }

    // -----------------------------------------------------------------------
    // SetClient
    // -----------------------------------------------------------------------
    void SGProcessingBridge::SetClient( network::SuperGeniusClient *client ) noexcept
    {
        client_ = client;
        BridgeLogger()->info( "SuperGeniusClient set (network_mode_={})",
                              client ? "true" : "false" );
    }

    // -----------------------------------------------------------------------
    // SubmitNetwork — Phase 2: dispatch via SuperGeniusClient
    // -----------------------------------------------------------------------
    outcome::result<std::vector<uint8_t>> SGProcessingBridge::SubmitNetwork(
        const std::string &jsondata ) const
    {
        if ( !client_ )
        {
            BridgeLogger()->error( "SubmitNetwork: SuperGeniusClient not configured" );
            return outcome::failure( Error::NetworkError );
        }

        BridgeLogger()->debug( "Submitting job via SuperGeniusClient ({} bytes)", jsondata.size() );
        return client_->SubmitJob( jsondata );
    }

} // namespace sgns::neoswarm::core
