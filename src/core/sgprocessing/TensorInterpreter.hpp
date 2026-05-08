/**
 * @file       TensorInterpreter.hpp
 * @brief      Converts raw SGProcessingManager output bytes to text
 * @date       2026-05-06
 * @author     Subaskar S (ssivakumar@gnus.ai)
 */

#ifndef NEOSWARM_CORE_SGPROCESSING_TENSORINTERPRETER_HPP_
#define NEOSWARM_CORE_SGPROCESSING_TENSORINTERPRETER_HPP_

#include "common/Error.hpp"
#include "core/tokenizer/Tokenizer.hpp"
#include <cstdint>
#include <memory>
#include <string>
#include <vector>

namespace sgns
{
enum class InputFormat : int;
} // namespace sgns

namespace sgns::neoswarm::core
{
    /**
     * @brief Converts raw MNN tensor output bytes to a human-readable string.
     *
     * Supported formats: FLOAT32, FLOAT16, INT32, INT8.
     * When a Tokenizer is attached and the format is FLOAT32, the bytes are
     * treated as a logit vector and the highest-probability token is decoded.
     */
    class TensorInterpreter
    {
    public:
        TensorInterpreter()  = default;
        ~TensorInterpreter() = default;

        /**
         * @brief Attach a tokenizer for token-decoding mode (optional).
         * @param tok  Tokenizer instance.
         */
        void SetTokenizer( std::shared_ptr<Tokenizer> tok );

        /**
         * @brief Convert raw tensor bytes to a human-readable string.
         * @param bytes   Raw output bytes from SGProcessingManager.
         * @param format  Tensor element format.
         * @return        Decoded string or InferenceFailed / InvalidArgument.
         */
        outcome::result<std::string> Interpret( const std::vector<uint8_t> &bytes,
                                                sgns::InputFormat            format ) const;

    private:
        std::shared_ptr<Tokenizer> tokenizer_;

        outcome::result<std::string> InterpretFloat32( const std::vector<uint8_t> &bytes ) const;
        outcome::result<std::string> InterpretFloat16( const std::vector<uint8_t> &bytes ) const;
        outcome::result<std::string> InterpretInt32( const std::vector<uint8_t> &bytes ) const;
        outcome::result<std::string> InterpretInt8( const std::vector<uint8_t> &bytes ) const;
        outcome::result<std::string> DecodeLogits( const std::vector<float> &logits ) const;
    };

} // namespace sgns::neoswarm::core

#endif // NEOSWARM_CORE_SGPROCESSING_TENSORINTERPRETER_HPP_
