/**
 * @file       PromptAnalyzer.cpp
 * @brief      Prompt feature extraction implementation
 * @date       2026-05-06
 * @author     Subaskar S (ssivakumar@gnus.ai)
 */

#include "PromptAnalyzer.hpp"

#include <algorithm>
#include <cctype>
#include <cmath>
#include <regex>
#include <sstream>
#include <unordered_set>

namespace sgns::neoswarm::router
{
    namespace
    {
        bool IsNumericChar( char c )
        {
            return std::isdigit( static_cast<unsigned char>( c ) ) || c == '.' || c == ',' || c == '-' || c == '+' ||
                   c == '/' || c == '*' || c == '%' || c == '^' || c == '=';
        }
    } // namespace

    // -----------------------------------------------------------------------
    // CountTokens
    // -----------------------------------------------------------------------
    size_t PromptAnalyzer::CountTokens( const std::string& text ) const
    {
        std::istringstream iss( text );
        size_t count = 0;
        std::string word;
        while ( iss >> word )
        {
            ++count;
        }
        return count;
    }

    // -----------------------------------------------------------------------
    // ComputeNumericDensity
    // -----------------------------------------------------------------------
    float PromptAnalyzer::ComputeNumericDensity( const std::string& prompt ) const
    {
        if ( prompt.empty() )
        {
            return 0.0f;
        }

        std::istringstream iss( prompt );
        std::string token;
        size_t total = 0;
        size_t numeric = 0;

        while ( iss >> token )
        {
            ++total;
            size_t numChars = 0;
            for ( char c : token )
            {
                if ( IsNumericChar( c ) )
                {
                    ++numChars;
                }
            }
            if ( numChars * 2 >= token.size() )
            {
                ++numeric;
            }
        }
        return total > 0 ? static_cast<float>( numeric ) / static_cast<float>( total ) : 0.0f;
    }

    // -----------------------------------------------------------------------
    // DetectCodeSyntax
    // -----------------------------------------------------------------------
    bool PromptAnalyzer::DetectCodeSyntax( const std::string& prompt ) const
    {
        static const std::regex kCodePatterns(
            R"(\b(def |class |function |import |#include|void |int |float |return |if\s*\(|for\s*\(|while\s*\(|\{|\}|=>|->|::|std::))",
            std::regex::icase );
        return std::regex_search( prompt, kCodePatterns );
    }

    // -----------------------------------------------------------------------
    // EstimateComplexity
    // -----------------------------------------------------------------------
    float PromptAnalyzer::EstimateComplexity( const std::string& prompt ) const
    {
        std::istringstream iss( prompt );
        std::string word;
        std::unordered_set<std::string> vocab;
        size_t total = 0;

        while ( iss >> word )
        {
            std::transform( word.begin(), word.end(), word.begin(),
                            []( unsigned char c ) { return std::tolower( c ); } );
            vocab.insert( word );
            ++total;
        }
        if ( total == 0 )
        {
            return 0.0f;
        }

        float diversity = static_cast<float>( vocab.size() ) / static_cast<float>( total );
        return std::log1p( static_cast<float>( total ) ) * diversity;
    }

    // -----------------------------------------------------------------------
    // HasMathKeywords
    // -----------------------------------------------------------------------
    bool PromptAnalyzer::HasMathKeywords( const std::string& prompt ) const
    {
        static const std::vector<std::string> kMathKeywords = {
            "solve",      "calculate", "compute",      "integral",   "derivative", "equation",
            "algebra",    "geometry",  "trigonometry", "matrix",     "vector",     "probability",
            "statistics", "factorial", "prime",        "sqrt",       "logarithm",  "exponent",
            "polynomial", "theorem",   "proof",        "formula",    "arithmetic", "multiply",
            "divide",     "sum",       "product",      "difference", "quotient",   "remainder" };

        std::string lower = prompt;
        std::transform( lower.begin(), lower.end(), lower.begin(),
                        []( unsigned char c ) { return std::tolower( c ); } );

        for ( const auto& kw : kMathKeywords )
        {
            if ( lower.find( kw ) != std::string::npos )
            {
                return true;
            }
        }
        return false;
    }

    // -----------------------------------------------------------------------
    // HasGrammarRequest
    // -----------------------------------------------------------------------
    bool PromptAnalyzer::HasGrammarRequest( const std::string& prompt ) const
    {
        static const std::vector<std::string> kGrammarKeywords = {
            "grammar", "spelling",           "punctuation", "proofread", "correct my",
            "fix my",  "improve my writing", "rewrite",     "rephrase",  "paraphrase",
            "fluency", "sentence structure", "typo",        "edit this", "revise" };

        std::string lower = prompt;
        std::transform( lower.begin(), lower.end(), lower.begin(),
                        []( unsigned char c ) { return std::tolower( c ); } );

        for ( const auto& kw : kGrammarKeywords )
        {
            if ( lower.find( kw ) != std::string::npos )
            {
                return true;
            }
        }
        return false;
    }

    // -----------------------------------------------------------------------
    // Analyze
    // -----------------------------------------------------------------------
    PromptFeatures PromptAnalyzer::Analyze( const std::string& prompt ) const
    {
        PromptFeatures f;
        f.numeric_density_ = ComputeNumericDensity( prompt );
        f.has_code_syntax_ = DetectCodeSyntax( prompt );
        f.complexity_ = EstimateComplexity( prompt );
        f.token_count_ = CountTokens( prompt );
        f.has_math_keywords_ = HasMathKeywords( prompt );
        f.has_grammar_request_ = HasGrammarRequest( prompt );
        return f;
    }

} // namespace sgns::neoswarm::router
