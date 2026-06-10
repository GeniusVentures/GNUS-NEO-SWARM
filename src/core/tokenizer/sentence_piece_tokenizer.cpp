/**
 * @file       sentence_piece_tokenizer.cpp
 * @brief      SentencePiece tokenizer implementation
 * @date       2026-05-06
 * @author     Subaskar S (ssivakumar@gnus.ai)
 */

#include "tokenizer.hpp"
#include "common/logging.hpp"

#include <algorithm>
#include <cctype>
#include <sstream>

#include <sentencepiece_processor.h>

namespace sgns::neoswarm::core
{
    namespace
    {
        auto TokenizerLogger()
        {
            return neoswarm::CreateLogger( "Tokenizer" );
        }
    } // namespace

    struct SentencePieceTokenizer::Impl
    {
        sentencepiece::SentencePieceProcessor processor_;
        bool loaded_ = false;
    };

    SentencePieceTokenizer::SentencePieceTokenizer( int eos_id, int bos_id )
        : impl_( std::make_unique<Impl>() )
        , eos_id_( eos_id )
        , bos_id_( bos_id )
    {
    }

    SentencePieceTokenizer::~SentencePieceTokenizer() = default;

    // -----------------------------------------------------------------------
    // Load
    // -----------------------------------------------------------------------
    outcome::result<void> SentencePieceTokenizer::Load( const std::string& model_path )
    {
        auto status = impl_->processor_.Load( model_path );
        if ( !status.ok() )
        {
            return outcome::failure( Error::TokenizerFailed );
        }
        impl_->loaded_ = true;
        TokenizerLogger()->info( "Tokenizer loaded: {} (vocab={})", model_path, VocabSize() );
        return outcome::success();

    }

    // -----------------------------------------------------------------------
    // Encode
    // -----------------------------------------------------------------------
    outcome::result<std::vector<int>> SentencePieceTokenizer::Encode( const std::string& text ) const
    {
        if ( !impl_->loaded_ )
        {
            return outcome::failure( Error::TokenizerFailed );
        }
        std::vector<int> ids;
        auto status = impl_->processor_.Encode( text, &ids );
        if ( !status.ok() )
        {
            return outcome::failure( Error::TokenizerFailed );
        }
        return outcome::success( std::move( ids ) );

    }

    // -----------------------------------------------------------------------
    // Decode
    // -----------------------------------------------------------------------
    outcome::result<std::string> SentencePieceTokenizer::Decode( const std::vector<int>& ids ) const
    {
        if ( !impl_->loaded_ )
        {
            return outcome::failure( Error::TokenizerFailed );
        }
        std::string text;
        auto status = impl_->processor_.Decode( ids, &text );
        if ( !status.ok() )
        {
            return outcome::failure( Error::TokenizerFailed );
        }
        return outcome::success( std::move( text ) );

    }

    // -----------------------------------------------------------------------
    // VocabSize
    // -----------------------------------------------------------------------
    size_t SentencePieceTokenizer::VocabSize() const
    {
        if ( impl_->loaded_ )
        {
            return static_cast<size_t>( impl_->processor_.GetPieceSize() );
        }
        return 0; // unknown until model is loaded
    }

} // namespace sgns::neoswarm::core
