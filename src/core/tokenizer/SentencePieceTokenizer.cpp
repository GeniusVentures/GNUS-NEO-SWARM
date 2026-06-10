/**
 * @file       SentencePieceTokenizer.cpp
 * @brief      SentencePiece tokenizer implementation
 * @date       2026-05-06
 * @author     Subaskar S (ssivakumar@gnus.ai)
 */

#include "Tokenizer.hpp"
#include "common/Logging.hpp"

#include <algorithm>
#include <cctype>
#include <sstream>

#ifdef GENIUS_HAS_SENTENCEPIECE
#include <sentencepiece_processor.h>
#endif

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
#ifdef GENIUS_HAS_SENTENCEPIECE
        sentencepiece::SentencePieceProcessor processor_;
#endif
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
#ifdef GENIUS_HAS_SENTENCEPIECE
        auto status = impl_->processor_.Load( model_path );
        if ( !status.ok() )
        {
            return outcome::failure( Error::TOKENIZER_FAILED );
        }
        impl_->loaded_ = true;
        TokenizerLogger()->info( "Tokenizer loaded: {} (vocab={})", model_path, VocabSize() );
        return outcome::success();
#else
        (void) model_path;
        TokenizerLogger()->warn( "SentencePiece not compiled in — using whitespace tokenizer stub" );
        impl_->loaded_ = true;
        return outcome::success();
#endif
    }

    // -----------------------------------------------------------------------
    // Encode
    // -----------------------------------------------------------------------
    outcome::result<std::vector<int>> SentencePieceTokenizer::Encode( const std::string& text ) const
    {
#ifdef GENIUS_HAS_SENTENCEPIECE
        if ( !impl_->loaded_ )
        {
            return outcome::failure( Error::TOKENIZER_FAILED );
        }
        std::vector<int> ids;
        auto status = impl_->processor_.Encode( text, &ids );
        if ( !status.ok() )
        {
            return outcome::failure( Error::TOKENIZER_FAILED );
        }
        return outcome::success( std::move( ids ) );
#else
        std::vector<int> ids;
        ids.push_back( bos_id_ );
        std::istringstream iss( text );
        std::string word;
        while ( iss >> word )
        {
            int id = 3 + static_cast<int>( std::hash<std::string>{}( word ) % 31997 );
            ids.push_back( id );
        }
        return outcome::success( std::move( ids ) );
#endif
    }

    // -----------------------------------------------------------------------
    // Decode
    // -----------------------------------------------------------------------
    outcome::result<std::string> SentencePieceTokenizer::Decode( const std::vector<int>& ids ) const
    {
#ifdef GENIUS_HAS_SENTENCEPIECE
        if ( !impl_->loaded_ )
        {
            return outcome::failure( Error::TOKENIZER_FAILED );
        }
        std::string text;
        auto status = impl_->processor_.Decode( ids, &text );
        if ( !status.ok() )
        {
            return outcome::failure( Error::TOKENIZER_FAILED );
        }
        return outcome::success( std::move( text ) );
#else
        std::string out;
        for ( int id : ids )
        {
            if ( !out.empty() )
                out += ' ';
            out += std::to_string( id );
        }
        return outcome::success( out );
#endif
    }

    // -----------------------------------------------------------------------
    // VocabSize
    // -----------------------------------------------------------------------
    size_t SentencePieceTokenizer::VocabSize() const
    {
#ifdef GENIUS_HAS_SENTENCEPIECE
        if ( impl_->loaded_ )
        {
            return static_cast<size_t>( impl_->processor_.GetPieceSize() );
        }
#endif
        return 0; // unknown until model is loaded
    }

} // namespace sgns::neoswarm::core
