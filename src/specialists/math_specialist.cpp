/**
 * @file       math_specialist.cpp
 * @brief      Math specialist implementation
 * @date       2026-05-06
 */

#include "math_specialist.hpp"
#include "common/logging.hpp"

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
        : m_engine( std::move( engine ) )
    {
    }

    // -----------------------------------------------------------------------
    // Load
    // -----------------------------------------------------------------------
    outcome::result<void> MathSpecialist::Load( const std::string& model_path )
    {
        if ( !m_engine )
        {
            return outcome::failure( Error::ModelLoadFailed );
        }
        BOOST_OUTCOME_TRY( m_engine->LoadModel( model_path ) );
        m_loaded = true;
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

        if ( !m_loaded || !m_engine )
        {
            MathLogger()->warn( "MathSpecialist not loaded — returning input unchanged" );
            last_confidence_ = 0.0f;
            return outcome::success( input );
        }

        Task task;
        task.m_id = "math-" + std::to_string( std::hash<std::string>{}( input ) );
        task.m_prompt = BuildPrompt( input );
        task.m_maxTokens = 512;
        task.m_temperature = 0.1f;

        auto res = m_engine->Infer( task );
        if ( !res.has_value() )
        {
            MathLogger()->warn( "MathSpecialist inference failed" );
            last_confidence_ = 0.0f;
            return outcome::success( input );
        }

        last_confidence_ = 1.0f - std::min( res.value().m_perplexity / 10.0f, 1.0f );

        if ( last_confidence_ < SymbolicFallback::kConfidenceThreshold )
        {
            auto fallback = TrySymbolicFallback( res.value().m_output );
            if ( fallback.has_value() )
            {
                MathLogger()->debug( "MathSpecialist: low confidence ({:.2f}), using symbolic fallback",
                                     last_confidence_ );
                last_confidence_ = 1.0f;
                return outcome::success( fallback.value() );
            }
        }

        return outcome::success( res.value().m_output );
    }

} // namespace sgns::neoswarm::specialists
