/**
 * @file       GrammarSpecialist.cpp
 * @brief      Grammar specialist implementation
 * @date       2026-05-06
 * @author     Subaskar S (ssivakumar@gnus.ai)
 */

#include "GrammarSpecialist.hpp"
#include "common/Logging.hpp"

#include <functional>

namespace sgns::neoswarm::specialists
{
    namespace
    {
        auto GrammarLogger()
        {
            return neoswarm::CreateLogger( "GrammarSpecialist" );
        }
    }

    GrammarSpecialist::GrammarSpecialist( std::shared_ptr<core::InferenceEngine> engine )
        : engine_( std::move( engine ) )
    {
    }

    // -----------------------------------------------------------------------
    // Load
    // -----------------------------------------------------------------------
    outcome::result<void> GrammarSpecialist::Load( const std::string &model_path )
    {
        if ( !engine_ )
        {
            return outcome::failure( Error::ModelLoadFailed );
        }
        BOOST_OUTCOME_TRY( engine_->LoadModel( model_path ) );
        loaded_ = true;
        GrammarLogger()->info( "GrammarSpecialist loaded: {}", model_path );
        return outcome::success();
    }

    // -----------------------------------------------------------------------
    // BuildPrompt
    // -----------------------------------------------------------------------
    std::string GrammarSpecialist::BuildPrompt( const std::string &input ) const
    {
        return "[INST] Correct the grammar, spelling, and fluency of the following text. "
               "Return only the corrected text without explanation.\n\n"
               "Text: "
               + input
               + "\n\nCorrected: [/INST]";
    }

    // -----------------------------------------------------------------------
    // Process
    // -----------------------------------------------------------------------
    outcome::result<std::string> GrammarSpecialist::Process( const std::string &input )
    {
        if ( !loaded_ || !engine_ )
        {
            GrammarLogger()->warn( "GrammarSpecialist not loaded — returning input unchanged" );
            last_confidence_ = 0.0f;
            return outcome::success( input );
        }

        Task task;
        task.id_          = "grammar-" + std::to_string( std::hash<std::string>{}( input ) );
        task.prompt_      = BuildPrompt( input );
        task.max_tokens_  = static_cast<uint32_t>( input.size() + 64 );
        task.temperature_ = 0.1f;

        auto res = engine_->Infer( task );
        if ( !res.has_value() )
        {
            GrammarLogger()->warn( "GrammarSpecialist inference failed — returning input unchanged" );
            last_confidence_ = 0.0f;
            return outcome::success( input );
        }

        last_confidence_ = 1.0f - std::min( res.value().perplexity_ / 10.0f, 1.0f );
        return outcome::success( res.value().output_ );
    }

} // namespace sgns::neoswarm::specialists
