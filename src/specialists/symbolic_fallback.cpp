/**
 * @file       symbolic_fallback.cpp
 * @brief      Recursive-descent expression evaluator
 * @date       2026-05-06
 * @author     Subaskar S (ssivakumar@gnus.ai)
 */

#include "symbolic_fallback.hpp"

#include <cctype>
#include <cmath>
#include <iomanip>
#include <regex>
#include <sstream>
#include <stdexcept>

namespace sgns::neoswarm::specialists
{
    // -----------------------------------------------------------------------
    // Parser helpers
    // -----------------------------------------------------------------------
    void SymbolicFallback::Parser::SkipWhitespace()
    {
        while ( pos_ < input_.size() && std::isspace( static_cast<unsigned char>( input_[pos_] ) ) )
        {
            ++pos_;
        }
    }

    char SymbolicFallback::Parser::Peek() const
    {
        if ( pos_ >= input_.size() )
        {
            return '\0';
        }
        return input_[pos_];
    }

    char SymbolicFallback::Parser::Consume()
    {
        return input_[pos_++];
    }

    // expr = term (('+' | '-') term)*
    double SymbolicFallback::Parser::ParseExpr()
    {
        double result = ParseTerm();
        SkipWhitespace();
        while ( Peek() == '+' || Peek() == '-' )
        {
            char op = Consume();
            double rhs = ParseTerm();
            result = ( op == '+' ) ? result + rhs : result - rhs;
            SkipWhitespace();
        }
        return result;
    }

    // term = factor (('*' | '/') factor)*
    double SymbolicFallback::Parser::ParseTerm()
    {
        double result = ParseFactor();
        SkipWhitespace();
        while ( Peek() == '*' || Peek() == '/' )
        {
            char op = Consume();
            double rhs = ParseFactor();
            if ( op == '/' && rhs == 0.0 )
            {
                throw std::runtime_error( "division by zero" );
            }
            result = ( op == '*' ) ? result * rhs : result / rhs;
            SkipWhitespace();
        }
        return result;
    }

    // factor = primary ('^' factor)?
    double SymbolicFallback::Parser::ParseFactor()
    {
        double base = ParsePrimary();
        SkipWhitespace();
        if ( Peek() == '^' )
        {
            Consume();
            double exp = ParseFactor();
            return std::pow( base, exp );
        }
        return base;
    }

    // primary = number | '(' expr ')' | '-' primary | function '(' expr ')'
    double SymbolicFallback::Parser::ParsePrimary()
    {
        SkipWhitespace();
        char c = Peek();

        if ( c == '-' )
        {
            Consume();
            return -ParsePrimary();
        }

        if ( c == '(' )
        {
            Consume();
            double val = ParseExpr();
            SkipWhitespace();
            if ( Peek() == ')' )
            {
                Consume();
            }
            return val;
        }

        if ( std::isalpha( static_cast<unsigned char>( c ) ) )
        {
            std::string name;
            while ( pos_ < input_.size() && std::isalpha( static_cast<unsigned char>( input_[pos_] ) ) )
            {
                name += Consume();
            }
            SkipWhitespace();
            if ( Peek() == '(' )
            {
                Consume();
                double arg = ParseExpr();
                SkipWhitespace();
                if ( Peek() == ')' )
                {
                    Consume();
                }
                if ( name == "sqrt" )
                    return std::sqrt( arg );
                if ( name == "abs" )
                    return std::abs( arg );
                if ( name == "sin" )
                    return std::sin( arg );
                if ( name == "cos" )
                    return std::cos( arg );
                if ( name == "tan" )
                    return std::tan( arg );
                if ( name == "log" )
                    return std::log( arg );
                if ( name == "exp" )
                    return std::exp( arg );
                throw std::runtime_error( "unknown function: " + name );
            }
            throw std::runtime_error( "unexpected identifier: " + name );
        }

        if ( std::isdigit( static_cast<unsigned char>( c ) ) || c == '.' )
        {
            std::string num_str;
            while ( pos_ < input_.size() &&
                    ( std::isdigit( static_cast<unsigned char>( input_[pos_] ) ) || input_[pos_] == '.' ) )
            {
                num_str += Consume();
            }
            return std::stod( num_str );
        }

        throw std::runtime_error( std::string( "unexpected character: " ) + c );
    }

    // -----------------------------------------------------------------------
    // Evaluate
    // -----------------------------------------------------------------------
    std::optional<double> SymbolicFallback::Evaluate( const std::string& expr )
    {
        try
        {
            Parser p{ expr, 0 };
            double result = p.ParseExpr();
            p.SkipWhitespace();
            if ( p.pos_ != expr.size() )
            {
                return std::nullopt; // trailing garbage
            }
            return result;
        }
        catch ( ... )
        {
            return std::nullopt;
        }
    }

    // -----------------------------------------------------------------------
    // ExtractAndEvaluate
    // -----------------------------------------------------------------------
    std::optional<double> SymbolicFallback::ExtractAndEvaluate( const std::string& text )
    {
        static const std::regex kExprPattern( R"([\d\.\+\-\*\/\^\(\)\s]{3,})" );
        std::sregex_iterator it( text.begin(), text.end(), kExprPattern );
        std::sregex_iterator end;
        for ( ; it != end; ++it )
        {
            auto candidate = it->str();
            auto result = Evaluate( candidate );
            if ( result.has_value() )
            {
                return result;
            }
        }
        return std::nullopt;
    }

    // -----------------------------------------------------------------------
    // FormatResult
    // -----------------------------------------------------------------------
    std::string SymbolicFallback::FormatResult( double value )
    {
        if ( value == std::floor( value ) && std::abs( value ) < 1e15 )
        {
            std::ostringstream oss;
            oss << static_cast<long long>( value );
            return oss.str();
        }
        std::ostringstream oss;
        oss << std::setprecision( 10 ) << value;
        return oss.str();
    }

} // namespace sgns::neoswarm::specialists
