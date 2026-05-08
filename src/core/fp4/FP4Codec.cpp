/**
 * @file       FP4Codec.cpp
 * @brief      FP4 v3 quantization codec implementation
 * @date       2026-05-06
 * @author     Subaskar S (ssivakumar@gnus.ai)
 */

#include "FP4Codec.hpp"
#include "common/Logging.hpp"

#include <algorithm>
#include <cassert>
#include <cmath>
#include <limits>
#include <numeric>

namespace sgns::neoswarm::fp4
{
    namespace
    {
        auto FP4Logger()
        {
            return neoswarm::CreateLogger( "FP4Codec" );
        }
    }

    // -----------------------------------------------------------------------
    // QuantizeValue
    // -----------------------------------------------------------------------
    uint8_t FP4Codec::QuantizeValue( float v, float scale )
    {
        if ( scale == 0.0f ) return 7;  // map to 0.0 in LUT
        float normalized = v / scale;
        normalized = std::max( -1.0f, std::min( 1.0f, normalized ) );

        uint8_t best      = 0;
        float   best_dist = std::abs( normalized - kFP4LUT[0] );
        for ( uint8_t i = 1; i < 16; ++i )
        {
            float dist = std::abs( normalized - kFP4LUT[i] );
            if ( dist < best_dist )
            {
                best_dist = dist;
                best      = i;
            }
        }
        return best;
    }

    // -----------------------------------------------------------------------
    // DequantizeValue
    // -----------------------------------------------------------------------
    float FP4Codec::DequantizeValue( uint8_t idx, float scale )
    {
        return kFP4LUT[idx & 0x0F] * scale;
    }

    // -----------------------------------------------------------------------
    // FindBestScale
    // -----------------------------------------------------------------------
    float FP4Codec::FindBestScale( const float *block, size_t n,
                                   const float *act_stats ) const
    {
        float abs_max = 0.0f;
        for ( size_t i = 0; i < n; ++i )
        {
            float w = block[i];
            if ( act_stats ) w *= act_stats[i];
            abs_max = std::max( abs_max, std::abs( w ) );
        }
        if ( abs_max == 0.0f ) return 1.0f;

        float best_scale = abs_max;
        float best_mse   = std::numeric_limits<float>::max();

        for ( int step = 0; step < kScaleSearchSteps; ++step )
        {
            float candidate = abs_max * ( 1.0f - static_cast<float>( step ) / kScaleSearchSteps );
            if ( candidate == 0.0f ) continue;

            float mse = 0.0f;
            for ( size_t i = 0; i < n; ++i )
            {
                uint8_t idx          = QuantizeValue( block[i], candidate );
                float   reconstructed = DequantizeValue( idx, candidate );
                float   diff          = block[i] - reconstructed;
                mse += diff * diff;
            }
            mse /= static_cast<float>( n );

            if ( mse < best_mse )
            {
                best_mse   = mse;
                best_scale = candidate;
            }
        }
        return best_scale;
    }

    // -----------------------------------------------------------------------
    // Encode
    // -----------------------------------------------------------------------
    outcome::result<FP4Tensor> FP4Codec::Encode( const float *weights,
                                                  size_t       rows,
                                                  size_t       cols,
                                                  const float *activation_stats ) const
    {
        if ( !weights || rows == 0 || cols == 0 )
        {
            return outcome::failure( Error::InvalidArgument );
        }

        FP4Tensor tensor;
        tensor.rows_ = rows;
        tensor.cols_ = cols;

        const size_t total_elements = rows * cols;
        tensor.data_.resize( ( total_elements + 1 ) / 2, 0 );

        const size_t mb_rows = ( rows + kMacroblockRows - 1 ) / kMacroblockRows;
        const size_t mb_cols = ( cols + kMacroblockCols - 1 ) / kMacroblockCols;
        tensor.scales_.resize( mb_rows * mb_cols, 1.0f );

        std::vector<float> block_buf( kMacroblockSize );

        for ( size_t mbr = 0; mbr < mb_rows; ++mbr )
        {
            for ( size_t mbc = 0; mbc < mb_cols; ++mbc )
            {
                const size_t mb_idx = mbr * mb_cols + mbc;

                size_t block_n = 0;
                for ( size_t r = mbr * kMacroblockRows;
                      r < std::min( rows, ( mbr + 1 ) * kMacroblockRows ); ++r )
                {
                    for ( size_t c = mbc * kMacroblockCols;
                          c < std::min( cols, ( mbc + 1 ) * kMacroblockCols ); ++c )
                    {
                        block_buf[block_n++] = weights[r * cols + c];
                    }
                }

                const float *act_ptr = activation_stats
                    ? activation_stats + mbr * kMacroblockRows * cols + mbc * kMacroblockCols
                    : nullptr;
                float scale              = FindBestScale( block_buf.data(), block_n, act_ptr );
                tensor.scales_[mb_idx]   = scale;

                for ( size_t r = mbr * kMacroblockRows;
                      r < std::min( rows, ( mbr + 1 ) * kMacroblockRows ); ++r )
                {
                    for ( size_t c = mbc * kMacroblockCols;
                          c < std::min( cols, ( mbc + 1 ) * kMacroblockCols ); ++c )
                    {
                        const size_t linear_idx = r * cols + c;
                        const uint8_t nibble    = QuantizeValue( weights[linear_idx], scale );
                        const size_t  byte_idx  = linear_idx / 2;
                        if ( linear_idx % 2 == 0 )
                        {
                            tensor.data_[byte_idx] =
                                static_cast<uint8_t>( ( tensor.data_[byte_idx] & 0x0F ) | ( nibble << 4 ) );
                        }
                        else
                        {
                            tensor.data_[byte_idx] =
                                static_cast<uint8_t>( ( tensor.data_[byte_idx] & 0xF0 ) | ( nibble & 0x0F ) );
                        }
                    }
                }
            }
        }

        FP4Logger()->debug( "FP4 encode: {}x{} → {} bytes, {} macroblocks",
                            rows, cols, tensor.data_.size(), tensor.scales_.size() );
        return outcome::success( std::move( tensor ) );
    }

    // -----------------------------------------------------------------------
    // Decode
    // -----------------------------------------------------------------------
    outcome::result<void> FP4Codec::Decode( const FP4Tensor &tensor, float *output ) const
    {
        if ( !output )
        {
            return outcome::failure( Error::InvalidArgument );
        }

        const size_t rows    = tensor.rows_;
        const size_t cols    = tensor.cols_;
        const size_t mb_rows = ( rows + kMacroblockRows - 1 ) / kMacroblockRows;
        const size_t mb_cols = ( cols + kMacroblockCols - 1 ) / kMacroblockCols;

        for ( size_t mbr = 0; mbr < mb_rows; ++mbr )
        {
            for ( size_t mbc = 0; mbc < mb_cols; ++mbc )
            {
                const size_t mb_idx = mbr * mb_cols + mbc;
                const float  scale  = tensor.scales_[mb_idx];

                for ( size_t r = mbr * kMacroblockRows;
                      r < std::min( rows, ( mbr + 1 ) * kMacroblockRows ); ++r )
                {
                    for ( size_t c = mbc * kMacroblockCols;
                          c < std::min( cols, ( mbc + 1 ) * kMacroblockCols ); ++c )
                    {
                        const size_t  linear_idx = r * cols + c;
                        const size_t  byte_idx   = linear_idx / 2;
                        uint8_t       nibble;
                        if ( linear_idx % 2 == 0 )
                        {
                            nibble = ( tensor.data_[byte_idx] >> 4 ) & 0x0F;
                        }
                        else
                        {
                            nibble = tensor.data_[byte_idx] & 0x0F;
                        }
                        output[linear_idx] = DequantizeValue( nibble, scale );
                    }
                }
            }
        }
        return outcome::success();
    }

    // -----------------------------------------------------------------------
    // ComputeError
    // -----------------------------------------------------------------------
    float FP4Codec::ComputeError( const float *original, const FP4Tensor &encoded ) const
    {
        const size_t       n = encoded.rows_ * encoded.cols_;
        std::vector<float> decoded( n );
        auto               res = Decode( encoded, decoded.data() );
        if ( !res.has_value() )
        {
            return std::numeric_limits<float>::max();
        }

        double mse = 0.0;
        for ( size_t i = 0; i < n; ++i )
        {
            double diff = original[i] - decoded[i];
            mse += diff * diff;
        }
        return static_cast<float>( mse / static_cast<double>( n ) );
    }

} // namespace sgns::neoswarm::fp4
