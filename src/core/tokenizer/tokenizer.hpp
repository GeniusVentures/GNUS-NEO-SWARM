/**
 * @file       tokenizer.hpp
 * @brief      Abstract tokenizer interface and SentencePiece implementation
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

    /**
     * @brief SentencePiece tokenizer.
     *
     * Wraps the sentencepiece library when available.
     * Falls back to a simple whitespace tokenizer when not compiled in.
     */
    class SentencePieceTokenizer : public Tokenizer
    {
        public:
        explicit SentencePieceTokenizer( int eos_id = 2, int bos_id = 1 );
        ~SentencePieceTokenizer() override;

        /**
         * @brief Load a SentencePiece .model file.
         * @param model_path  Path to the .model file.
         * @return            outcome::success or TokenizerFailed.
         */
        outcome::result<void> Load( const std::string& model_path );

        outcome::result<std::vector<int>> Encode( const std::string& text ) const override;
        outcome::result<std::string> Decode( const std::vector<int>& ids ) const override;
        bool IsEOS( int token_id ) const override
        {
            return token_id == m_eosId;
        }
        int EosTokenId() const override
        {
            return m_eosId;
        }
        int BosTokenId() const override
        {
            return m_bosId;
        }
        size_t VocabSize() const override;

        private:
        struct Impl;
        std::unique_ptr<Impl> impl_;
        int m_eosId;
        int m_bosId;
    };

} // namespace sgns::neoswarm::core

#endif // NEOSWARM_CORE_TOKENIZER_TOKENIZER_HPP
