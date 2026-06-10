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
#ifdef GENIUS_HAS_SENTENCEPIECE
#ifdef GENIUS_HAS_SENTENCEPIECE

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
        sentencepiece::SentencePieceProcessor m_processor;
        bool m_loaded = false;
    };

    SentencePieceTokenizer::SentencePieceTokenizer( int eos_id, int bos_id )
        : impl_( std::make_unique<Impl>() )
        , m_eosId( eos_id )
        , m_bosId( bos_id )
    {
    }

    SentencePieceTokenizer::~SentencePieceTokenizer() = default;

    // -----------------------------------------------------------------------
    // Load
    // -----------------------------------------------------------------------
    outcome::result<void> SentencePieceTokenizer::Load( const std::string& model_path )
    {
        auto status = impl_->m_processor.Load( model_path );
        if ( !status.ok() )
        {
            return outcome::failure( Error::TokenizerFailed );
        }
        impl_->m_loaded = true;
        TokenizerLogger()->info( "Tokenizer loaded: {} (vocab={})", model_path, VocabSize() );
        return outcome::success();

    }

    // -----------------------------------------------------------------------
    // Encode
    // -----------------------------------------------------------------------
    outcome::result<std::vector<int>> SentencePieceTokenizer::Encode( const std::string& text ) const
    {
        if ( !impl_->m_loaded )
        {
            return outcome::failure( Error::TokenizerFailed );
        }
        std::vector<int> ids;
        auto status = impl_->m_processor.Encode( text, &ids );
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
        if ( !impl_->m_loaded )
        {
            return outcome::failure( Error::TokenizerFailed );
        }
        std::string text;
        auto status = impl_->m_processor.Decode( ids, &text );
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
        if ( impl_->m_loaded )
        {
            return static_cast<size_t>( impl_->m_processor.GetPieceSize() );
        }
        return 0; // unknown until model is loaded
    }

} // namespace sgns::neoswarm::core

#endif // GENIUS_HAS_SENTENCEPIECE
#endif // GENIUS_HAS_SENTENCEPIECE