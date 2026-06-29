/**
 * @file       tokenizer.hpp
 * @brief      Abstract tokenizer interface
 * @date       2026-05-06
 */

#ifndef NEOSWARM_CORE_TOKENIZER_TOKENIZER_HPP
#define NEOSWARM_CORE_TOKENIZER_TOKENIZER_HPP

#include "common/error.hpp"
#include <memory>
#include <string>
#include <vector>

namespace sgns::neoswarm::core
{
    /**
     * @brief Abstract tokenizer interface.
     */
    class Tokenizer
    {
        public:
        virtual ~Tokenizer() = default;

        /**
         * @brief Encode text to token IDs.
         * @param text  Input string.
         * @return      Token ID vector or TokenizerFailed.
         */
        virtual outcome::result<std::vector<int>> Encode( const std::string& text ) const = 0;

        /**
         * @brief Decode token IDs to text.
         * @param ids  Token ID vector.
         * @return     Decoded string or TokenizerFailed.
         */
        virtual outcome::result<std::string> Decode( const std::vector<int>& ids ) const = 0;

        /**
         * @brief Check whether a token ID is the end-of-sequence token.
         * @param token_id  Token ID to check.
         * @return          True if this is the EOS token.
         */
        virtual bool IsEOS( int token_id ) const = 0;

        /// @return The EOS token ID.
        virtual int EosTokenId() const = 0;

        /// @return The BOS token ID.
        virtual int BosTokenId() const = 0;

        /// @return The vocabulary size.
        virtual size_t VocabSize() const = 0;
    };

} // namespace sgns::neoswarm::core

} // namespace sgns::neoswarm::core

#endif // NEOSWARM_CORE_TOKENIZER_TOKENIZER_HPP
