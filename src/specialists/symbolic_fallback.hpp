/**
 * @file       symbolic_fallback.hpp
 * @brief      Expression parser and evaluator for math validation (PTDS §5.2)
 * @date       2026-05-06
 * @author     Subaskar S (ssivakumar@gnus.ai)
 */

#ifndef NEOSWARM_SPECIALISTS_SYMBOLICFALLBACK_HPP
#define NEOSWARM_SPECIALISTS_SYMBOLICFALLBACK_HPP

#include "common/error.hpp"
#include <optional>
#include <string>

namespace sgns::neoswarm::specialists
{
    /**
     * @brief Evaluates mathematical expressions symbolically.
     *
     * Triggered when MathSpecialist model confidence < kConfidenceThreshold.
     * Supports: +, -, *, /, ^, parentheses, sqrt, abs, sin, cos, tan, log, exp.
     */
    class SymbolicFallback
    {
        public:
        static constexpr float kConfidenceThreshold = 0.6f;

        /**
         * @brief Evaluate a mathematical expression string.
         * @param expr  Expression string (e.g. "847 * 963").
         * @return      Result value or std::nullopt if parsing fails.
         */
        static std::optional<double> Evaluate( const std::string& expr );

        /**
         * @brief Extract the first numeric expression from text and evaluate it.
         * @param text  Free-form text containing a math expression.
         * @return      Result value or std::nullopt if no expression found.
         */
        static std::optional<double> ExtractAndEvaluate( const std::string& text );

        /**
         * @brief Format a double result as a clean string.
         * @param value  Numeric result.
         * @return       Integer string if value is whole, decimal string otherwise.
         */
        static std::string FormatResult( double value );

        private:
        struct Parser
        {
            const std::string& input_;
            size_t pos_ = 0;

            double ParseExpr();
            double ParseTerm();
            double ParseFactor();
            double ParsePrimary();
            void SkipWhitespace();
            char Peek() const;
            char Consume();
        };
    };

} // namespace sgns::neoswarm::specialists

#endif // NEOSWARM_SPECIALISTS_SYMBOLICFALLBACK_HPP
