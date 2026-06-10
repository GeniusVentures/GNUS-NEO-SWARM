/**
 * @file       prompt_analyzer.hpp
 * @brief      Extracts routing features from a raw prompt string (PTDS §6.1)
 * @date       2026-05-06
 * @author     Subaskar S (ssivakumar@gnus.ai)
 */

#ifndef NEOSWARM_ROUTER_PROMPTANALYZER_HPP_
#define NEOSWARM_ROUTER_PROMPTANALYZER_HPP_

#include "common/types.hpp"
#include <string>

namespace sgns::neoswarm::router
{
    /**
     * @brief Analyses a prompt string and returns a feature vector used by the router.
     */
    class PromptAnalyzer
    {
        public:
        /**
         * @brief Analyse a prompt and return its feature vector.
         * @param prompt  Raw user prompt string.
         * @return        PromptFeatures struct populated with extracted features.
         */
        PromptFeatures Analyze( const std::string& prompt ) const;

        private:
        /**
         * @brief Compute the ratio of tokens that are numeric.
         * @param prompt  Input string.
         * @return        Numeric density in [0, 1].
         */
        float ComputeNumericDensity( const std::string& prompt ) const;

        /**
         * @brief Detect code-like syntax (braces, keywords, operators).
         * @param prompt  Input string.
         * @return        True if code syntax is detected.
         */
        bool DetectCodeSyntax( const std::string& prompt ) const;

        /**
         * @brief Estimate prompt complexity as log(token_count) × vocab_diversity.
         * @param prompt  Input string.
         * @return        Complexity score ≥ 0.
         */
        float EstimateComplexity( const std::string& prompt ) const;

        /**
         * @brief Check for explicit math-domain keywords.
         * @param prompt  Input string.
         * @return        True if math keywords are present.
         */
        bool HasMathKeywords( const std::string& prompt ) const;

        /**
         * @brief Check for explicit grammar/writing correction requests.
         * @param prompt  Input string.
         * @return        True if grammar request keywords are present.
         */
        bool HasGrammarRequest( const std::string& prompt ) const;

        /**
         * @brief Count whitespace-delimited tokens.
         * @param text  Input string.
         * @return      Token count.
         */
        size_t CountTokens( const std::string& text ) const;
    };

} // namespace sgns::neoswarm::router

#endif // NEOSWARM_ROUTER_PROMPTANALYZER_HPP_
