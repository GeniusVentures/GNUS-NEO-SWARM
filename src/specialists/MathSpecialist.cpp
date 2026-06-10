/**
 * @file       MathSpecialist.cpp
 * @brief      Math specialist implementation
 * @date       2026-05-06
 * @author     Subaskar S (ssivakumar@gnus.ai)
 */

#include "MathSpecialist.hpp"
#include "common/Logging.hpp"

#include <functional>

namespace sgns::neoswarm::specialists
{
    namespace
    {
        auto MathLogger()
        {
            return neoswarm::CreateLogger( "MathSpecialist" );
        }
    } // namespace

    MathSpecialist::MathSpecialist( std::shared_ptr<core::InferenceEngine> engine )
        : engine_( std::move( engine ) )
    {
    }

    // -----------------------------------------------------------------------
    // Load
    // -----------------------------------------------------------------------
    outcome::result<void> MathSpecialist::Load( const std::string& model_path )
    {
        if ( !engine_ )
        {
            return outcome::failure( Error::MODEL_LOAD_FAILED );
        }
        BOOST_OUTCOME_TRY( engine_->LoadModel( model_path ) );
        loaded_ = true;
        MathLogger()->info( "MathSpecialist loaded: {}", model_path );
        return outcome::success();
    }

    // -----------------------------------------------------------------------
    // BuildPrompt
    // -----------------------------------------------------------------------
    std::string MathSpecialist::BuildPrompt( const std::string& input ) const
    {
        return "[INST] Solve the following math problem step by step. "
               "Show your work and provide the final numerical answer clearly.\n\n"
               "Problem: " +
               input + "\n\nSolution: [/INST]";
    }

    // -----------------------------------------------------------------------
    // TrySymbolicFallback
    // -----------------------------------------------------------------------
    std::optional<std::string> MathSpecialist::TrySymbolicFallback( const std::string& input ) const
    {
        auto result = SymbolicFallback::ExtractAndEvaluate( input );
        if ( result.has_value() )
        {
            return "= " + SymbolicFallback::FormatResult( result.value() );
        }
        return std::nullopt;
    }

    // -----------------------------------------------------------------------
    // Process
    // -----------------------------------------------------------------------
    outcome::result<std::string> MathSpecialist::Process( const std::string& input )
    {
        // Always try symbolic fallback first for pure arithmetic
        auto symbolic = TrySymbolicFallback( input );
        if ( symbolic.has_value() )
        {
            MathLogger()->debug( "MathSpecialist: symbolic fallback succeeded" );
            last_confidence_ = 1.0f;
            return outcome::success( symbolic.value() );
        }

        if ( !loaded_ || !engine_ )
        {
            MathLogger()->warn( "MathSpecialist not loaded — returning input unchanged" );
            last_confidence_ = 0.0f;
            return outcome::success( input );
        }

        Task task;
        task.id_ = "math-" + std::to_string( std::hash<std::string>{}( input ) );
        task.prompt_ = BuildPrompt( input );
        task.max_tokens_ = 512;
        task.temperature_ = 0.1f;

        auto res = engine_->Infer( task );
        if ( !res.has_value() )
        {
            MathLogger()->warn( "MathSpecialist inference failed" );
            last_confidence_ = 0.0f;
            return outcome::success( input );
        }

        last_confidence_ = 1.0f - std::min( res.value().perplexity_ / 10.0f, 1.0f );

        if ( last_confidence_ < SymbolicFallback::kConfidenceThreshold )
        {
            auto fallback = TrySymbolicFallback( res.value().output_ );
            if ( fallback.has_value() )
            {
                MathLogger()->debug( "MathSpecialist: low confidence ({:.2f}), using symbolic fallback",
                                     last_confidence_ );
                last_confidence_ = 1.0f;
                return outcome::success( fallback.value() );
            }
        }

        return outcome::success( res.value().output_ );
    }

} // namespace sgns::neoswarm::specialists
