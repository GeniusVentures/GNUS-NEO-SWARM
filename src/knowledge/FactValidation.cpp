/**
 * @file       FactValidation.cpp
 * @brief      Post-generation fact checking implementation
 * @date       2026-05-06
 * @author     Subaskar S (ssivakumar@gnus.ai)
 */

#include "FactValidation.hpp"
#include "common/Logging.hpp"

#include <algorithm>
#include <cmath>
#include <regex>
#include <sstream>

namespace sgns::neoswarm::knowledge
{
    namespace
    {
        auto ValidationLogger()
        {
            return neoswarm::CreateLogger( "FactValidation" );
        }
    }

    FactValidation::FactValidation( std::shared_ptr<KnowledgeRetrieval> retrieval )
        : retrieval_( std::move( retrieval ) )
    {
    }

    bool FactValidation::IsAvailable() const
    {
        return retrieval_ && retrieval_->IsLoaded();
    }

    // -----------------------------------------------------------------------
    // ExtractNumericClaims
    // -----------------------------------------------------------------------
    std::vector<std::pair<std::string, double>> FactValidation::ExtractNumericClaims(
        const std::string &text ) const
    {
        std::vector<std::pair<std::string, double>> claims;
        static const std::regex                     kNumPattern(
            R"((?:is|=|equals?|approximately|about|around)\s+([\d,]+(?:\.\d+)?))" );

        std::sregex_iterator it( text.begin(), text.end(), kNumPattern );
        std::sregex_iterator end;
        for ( ; it != end; ++it )
        {
            std::string num_str = ( *it )[1].str();
            num_str.erase( std::remove( num_str.begin(), num_str.end(), ',' ), num_str.end() );
            try
            {
                double val = std::stod( num_str );
                claims.push_back( { ( *it )[0].str(), val } );
            }
            catch ( ... )
            {
            }
        }
        return claims;
    }

    // -----------------------------------------------------------------------
    // Contradicts
    // -----------------------------------------------------------------------
    bool FactValidation::Contradicts( double claim, const std::string &fact_content ) const
    {
        static const std::regex kNumPattern( R"([\d,]+(?:\.\d+)?)" );
        std::sregex_iterator    it( fact_content.begin(), fact_content.end(), kNumPattern );
        std::sregex_iterator    end;
        for ( ; it != end; ++it )
        {
            std::string num_str = it->str();
            num_str.erase( std::remove( num_str.begin(), num_str.end(), ',' ), num_str.end() );
            try
            {
                double fact_val = std::stod( num_str );
                if ( fact_val == 0.0 )
                {
                    continue;
                }
                double rel_diff = std::abs( claim - fact_val ) / std::abs( fact_val );
                if ( rel_diff > 0.01 )
                {
                    return true;  // >1% difference = contradiction
                }
            }
            catch ( ... )
            {
            }
        }
        return false;
    }

    // -----------------------------------------------------------------------
    // Validate
    // -----------------------------------------------------------------------
    FactValidation::ValidationResult FactValidation::Validate(
        const std::string              &output,
        const std::vector<KnowledgeFact> &grounding_facts ) const
    {
        ValidationResult result;

        if ( !IsAvailable() || grounding_facts.empty() )
        {
            ValidationLogger()->debug( "FactValidation: skipping (unavailable or no grounding facts)" );
            return result;
        }

        auto claims = ExtractNumericClaims( output );
        if ( claims.empty() )
        {
            return result;
        }

        int contradiction_count = 0;
        for ( const auto &[claim_text, claim_val] : claims )
        {
            for ( const auto &fact : grounding_facts )
            {
                if ( Contradicts( claim_val, fact.content_ ) )
                {
                    result.contradictions_.push_back(
                        "Claim '" + claim_text + "' may contradict: " + fact.content_ );
                    ++contradiction_count;
                }
            }
        }

        if ( contradiction_count > 0 )
        {
            result.passed_              = false;
            result.contradiction_score_ = std::min(
                static_cast<float>( contradiction_count ) / static_cast<float>( claims.size() ),
                1.0f );
            result.suggestion_ = "Output contains "
                                 + std::to_string( contradiction_count )
                                 + " potential contradiction(s) with Grokipedia facts.";
            ValidationLogger()->warn( "FactValidation: {} contradiction(s) detected",
                                      contradiction_count );
        }

        return result;
    }

} // namespace sgns::neoswarm::knowledge
