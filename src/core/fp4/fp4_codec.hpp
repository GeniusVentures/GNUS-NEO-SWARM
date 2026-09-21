/**
 * @file       fp4_codec.hpp
 * @brief      FP4 v3 4-bit floating-point quantization codec (PTDS §4.1)
 * @date       2026-05-06
 *
 * @note Flagged per Phase 4 D-13: this NF4-style (non-uniform 16-value LUT)
 *       codec predates and does not match MNN_Ultra's E2M1 target format for
 *       InputFormat::FP4_ULTRA. MNNInferenceEngine's reference to this class
 *       was confirmed orphaned and removed (Phase 4 plan 04-04). This class
 *       is a candidate for removal or explicit re-justification in a future
 *       phase -- it is left in place here only because a full-file removal
 *       is a separate, bigger decision this phase does not make unilaterally.
 */

#ifndef NEOSWARM_CORE_FP4_FP4CODEC_HPP
#define NEOSWARM_CORE_FP4_FP4CODEC_HPP

#include "common/error.hpp"
#include <cstddef>
#include <cstdint>
#include <memory>
#include <vector>

namespace sgns::neoswarm::fp4
{
    static constexpr size_t kMacroblockRows = 64;
    static constexpr size_t kMacroblockCols = 64;
    static constexpr size_t kMacroblockSize = kMacroblockRows * kMacroblockCols;
    static constexpr int kScaleSearchSteps = 32;

    /// NF4-style symmetric lookup table: 16 representable values in [-1, 1]
    static constexpr float kFP4LUT[16] = { -1.0f,   -0.6962f, -0.5251f, -0.3949f, -0.2844f, -0.1848f, -0.0911f, 0.0f,
                                           0.0796f, 0.1609f,  0.2461f,  0.3379f,  0.4407f,  0.5626f,  0.7230f,  1.0f };

    /**
     * @brief Packed FP4 tensor: each byte holds two nibbles (high = even index).
     */
    struct FP4Tensor
    {
        std::vector<uint8_t> data_; ///< packed nibbles
        std::vector<float> scales_; ///< one scale per macroblock
        size_t rows_ = 0;
        size_t cols_ = 0;

        size_t NumMacroblocks() const
        {
            size_t mb_rows = ( rows_ + kMacroblockRows - 1 ) / kMacroblockRows;
            size_t mb_cols = ( cols_ + kMacroblockCols - 1 ) / kMacroblockCols;
            return mb_rows * mb_cols;
        }
    };

    /**
     * @brief Encodes and decodes FP32 weight matrices to/from FP4.
     */
    class FP4Codec
    {
        public:
        FP4Codec() = default;

        /**
         * @brief Quantize a row-major FP32 weight matrix to FP4.
         * @param weights          Pointer to rows×cols FP32 values.
         * @param rows             Number of rows.
         * @param cols             Number of columns.
         * @param activation_stats Optional per-column activation magnitudes (may be nullptr).
         * @return                 Encoded FP4Tensor or FP4DecodeFailed.
         */
        outcome::result<FP4Tensor> Encode( const float* weights,
                                           size_t rows,
                                           size_t cols,
                                           const float* activation_stats = nullptr ) const;

        /**
         * @brief Dequantize an FP4Tensor to a FP32 output buffer.
         * @param tensor  Encoded tensor.
         * @param output  Pre-allocated buffer of tensor.rows_ × tensor.cols_ floats.
         * @return        outcome::success or FP4DecodeFailed.
         */
        outcome::result<void> Decode( const FP4Tensor& tensor, float* output ) const;

        /**
         * @brief Compute mean squared error between original and round-tripped weights.
         * @param original  Original FP32 weights.
         * @param encoded   Encoded FP4Tensor.
         * @return          MSE value.
         */
        float ComputeError( const float* original, const FP4Tensor& encoded ) const;

        private:
        float FindBestScale( const float* block, size_t n, const float* act_stats = nullptr ) const;
        static uint8_t QuantizeValue( float v, float scale );
        static float DequantizeValue( uint8_t idx, float scale );
    };

} // namespace sgns::neoswarm::fp4

#endif // NEOSWARM_CORE_FP4_FP4CODEC_HPP
