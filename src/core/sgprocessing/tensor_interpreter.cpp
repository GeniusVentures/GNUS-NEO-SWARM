/**
 * @file       TensorInterpreter.cpp
 * @brief      Raw tensor byte to text conversion
 * @date       2026-05-06
 * @author     Subaskar S (ssivakumar@gnus.ai)
 */

#include "TensorInterpreter.hpp"
#include "common/Logging.hpp"

#include <algorithm>
#include <cstring>
#include <sstream>

#ifdef GENIUS_HAS_SGPROCESSING
#include <InputFormat.hpp>
#else
namespace sgns
{
    enum class InputFormat : int
    {
        FLOAT16 = 0,
        FLOAT32 = 1,
        FP4_ULTRA = 2,
        INT16 = 3,
        INT32 = 4,
        INT8 = 5,
        RGB8 = 6,
        RGBA8 = 7
    };
} // namespace sgns
#endif

namespace sgns::neoswarm::core
{
    namespace
    {
        auto InterpreterLogger()
        {
            return neoswarm::CreateLogger( "TensorInterpreter" );
        }
    } // namespace

    void TensorInterpreter::SetTokenizer( std::shared_ptr<Tokenizer> tok )
    {
        tokenizer_ = std::move( tok );
    }

    // -----------------------------------------------------------------------
    // Interpret
    // -----------------------------------------------------------------------
    outcome::result<std::string> TensorInterpreter::Interpret( const std::vector<uint8_t>& bytes,
                                                               sgns::InputFormat format ) const
    {
        InterpreterLogger()->debug( "Interpret: bytes={} format={}", bytes.size(), static_cast<int>( format ) );

        if ( bytes.empty() )
        {
            return outcome::failure( Error::InvalidArgument );
        }

        switch ( format )
        {
            case sgns::InputFormat::FLOAT32:
                return InterpretFloat32( bytes );
            case sgns::InputFormat::FLOAT16:
                return InterpretFloat16( bytes );
            case sgns::InputFormat::INT32:
                return InterpretInt32( bytes );
            case sgns::InputFormat::INT8:
                return InterpretInt8( bytes );
            case sgns::InputFormat::FP4_ULTRA:
                // FP4_ULTRA output from SGProcessingManager is already dequantized to FLOAT32
                return InterpretFloat32( bytes );
            default:
                return InterpretFloat32( bytes );
        }
    }

    // -----------------------------------------------------------------------
    // InterpretFloat32
    // -----------------------------------------------------------------------
    outcome::result<std::string> TensorInterpreter::InterpretFloat32( const std::vector<uint8_t>& bytes ) const
    {
        constexpr size_t kElemSize = sizeof( float );
        if ( bytes.size() % kElemSize != 0 )
        {
            return outcome::failure( Error::InferenceFailed );
        }

        const size_t count = bytes.size() / kElemSize;
        std::vector<float> values( count );
        std::memcpy( values.data(), bytes.data(), bytes.size() );

        if ( tokenizer_ && !values.empty() )
        {
            return DecodeLogits( values );
        }

        std::ostringstream oss;
        for ( size_t i = 0; i < values.size(); ++i )
        {
            if ( i > 0 )
                oss << ", ";
            oss << values[i];
        }
        return outcome::success( oss.str() );
    }

    // -----------------------------------------------------------------------
    // InterpretFloat16
    // -----------------------------------------------------------------------
    outcome::result<std::string> TensorInterpreter::InterpretFloat16( const std::vector<uint8_t>& bytes ) const
    {
        constexpr size_t kElemSize = 2U;
        if ( bytes.size() % kElemSize != 0 )
        {
            return outcome::failure( Error::InferenceFailed );
        }

        const size_t count = bytes.size() / kElemSize;
        std::vector<float> values;
        values.reserve( count );

        for ( size_t i = 0; i < count; ++i )
        {
            uint16_t h = 0;
            std::memcpy( &h, bytes.data() + i * kElemSize, kElemSize );

            const uint32_t sign = ( static_cast<uint32_t>( h ) >> 15U ) & 0x1U;
            const uint32_t exponent = ( static_cast<uint32_t>( h ) >> 10U ) & 0x1FU;
            const uint32_t mantissa = static_cast<uint32_t>( h ) & 0x3FFU;

            uint32_t f32 = 0;
            if ( exponent == 0U )
            {
                if ( mantissa == 0U )
                {
                    f32 = sign << 31U;
                }
                else
                {
                    uint32_t e = 0;
                    uint32_t m = mantissa;
                    while ( ( m & 0x400U ) == 0U )
                    {
                        m <<= 1U;
                        ++e;
                    }
                    m &= 0x3FFU;
                    f32 = ( sign << 31U ) | ( ( 127U - 14U - e ) << 23U ) | ( m << 13U );
                }
            }
            else if ( exponent == 0x1FU )
            {
                f32 = ( sign << 31U ) | ( 0xFFU << 23U ) | ( mantissa << 13U );
            }
            else
            {
                f32 = ( sign << 31U ) | ( ( exponent + 127U - 15U ) << 23U ) | ( mantissa << 13U );
            }

            float fval = 0.0f;
            std::memcpy( &fval, &f32, sizeof( float ) );
            values.push_back( fval );
        }

        std::vector<uint8_t> f32_bytes( values.size() * sizeof( float ) );
        std::memcpy( f32_bytes.data(), values.data(), f32_bytes.size() );
        return InterpretFloat32( f32_bytes );
    }

    // -----------------------------------------------------------------------
    // InterpretInt32
    // -----------------------------------------------------------------------
    outcome::result<std::string> TensorInterpreter::InterpretInt32( const std::vector<uint8_t>& bytes ) const
    {
        constexpr size_t kElemSize = sizeof( int32_t );
        if ( bytes.size() % kElemSize != 0 )
        {
            return outcome::failure( Error::InferenceFailed );
        }

        const size_t count = bytes.size() / kElemSize;
        std::ostringstream oss;
        for ( size_t i = 0; i < count; ++i )
        {
            int32_t v = 0;
            std::memcpy( &v, bytes.data() + i * kElemSize, kElemSize );
            if ( i > 0 )
                oss << ", ";
            oss << v;
        }
        return outcome::success( oss.str() );
    }

    // -----------------------------------------------------------------------
    // InterpretInt8
    // -----------------------------------------------------------------------
    outcome::result<std::string> TensorInterpreter::InterpretInt8( const std::vector<uint8_t>& bytes ) const
    {
        std::ostringstream oss;
        for ( size_t i = 0; i < bytes.size(); ++i )
        {
            if ( i > 0 )
                oss << ", ";
            oss << static_cast<int>( static_cast<int8_t>( bytes[i] ) );
        }
        return outcome::success( oss.str() );
    }

    // -----------------------------------------------------------------------
    // DecodeLogits
    // -----------------------------------------------------------------------
    outcome::result<std::string> TensorInterpreter::DecodeLogits( const std::vector<float>& logits ) const
    {
        if ( !tokenizer_ )
        {
            return outcome::failure( Error::InferenceFailed );
        }

        const auto max_it = std::max_element( logits.begin(), logits.end() );
        const int argmax = static_cast<int>( std::distance( logits.begin(), max_it ) );

        auto dec_res = tokenizer_->Decode( { argmax } );
        if ( !dec_res.has_value() )
        {
            return outcome::failure( dec_res.error() );
        }
        return outcome::success( dec_res.value() );
    }

} // namespace sgns::neoswarm::core
