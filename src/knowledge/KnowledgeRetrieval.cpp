/**
 * @file       KnowledgeRetrieval.cpp
 * @brief      Grokipedia knowledge retrieval implementation
 * @date       2026-05-06
 * @author     Subaskar S (ssivakumar@gnus.ai)
 */

#include "KnowledgeRetrieval.hpp"
#include "common/Logging.hpp"

#include <algorithm>
#include <cmath>
#include <fstream>
#include <sstream>
#include <unordered_map>

namespace sgns::neoswarm::knowledge
{
    namespace
    {
        auto KnowledgeLogger()
        {
            return neoswarm::CreateLogger( "KnowledgeRetrieval" );
        }
    } // namespace

    struct KnowledgeRetrieval::Impl
    {
        struct FactEntry
        {
            KnowledgeFact fact_;
            std::vector<float> embedding_;
        };
        std::vector<FactEntry> facts_;
    };

    KnowledgeRetrieval::KnowledgeRetrieval()
        : impl_( std::make_unique<Impl>() )
    {
    }

    KnowledgeRetrieval::KnowledgeRetrieval( Config cfg )
        : impl_( std::make_unique<Impl>() )
        , cfg_( std::move( cfg ) )
    {
    }

    KnowledgeRetrieval::~KnowledgeRetrieval() = default;

    // -----------------------------------------------------------------------
    // Load
    // -----------------------------------------------------------------------
    outcome::result<void> KnowledgeRetrieval::Load()
    {
        if ( !cfg_.enabled_ )
        {
            KnowledgeLogger()->info( "KnowledgeRetrieval disabled" );
            return outcome::success();
        }

        if ( cfg_.facts_path_.empty() )
        {
            KnowledgeLogger()->warn( "KnowledgeRetrieval: no facts path — using stub facts" );
            impl_->facts_.push_back(
                { { "Grokipedia", "The speed of light in vacuum is approximately 299,792,458 m/s.", 0.0f },
                  Embed( "speed of light vacuum" ) } );
            impl_->facts_.push_back( { { "Grokipedia", "Pi (π) is approximately 3.14159265358979.", 0.0f },
                                       Embed( "pi mathematical constant" ) } );
            impl_->facts_.push_back(
                { { "Grokipedia", "Water (H2O) has a molecular weight of approximately 18.015 g/mol.", 0.0f },
                  Embed( "water molecular weight chemistry" ) } );
            loaded_ = true;
            return outcome::success();
        }

        std::ifstream f( cfg_.facts_path_ );
        if ( !f )
        {
            return outcome::failure( Error::KnowledgeUnavailable );
        }

        std::string line;
        while ( std::getline( f, line ) )
        {
            if ( line.empty() )
            {
                continue;
            }
            auto comma = line.find( ',' );
            if ( comma == std::string::npos )
            {
                continue;
            }
            KnowledgeFact fact;
            fact.source_ = line.substr( 0, comma );
            fact.content_ = line.substr( comma + 1 );
            impl_->facts_.push_back( { fact, Embed( fact.content_ ) } );
        }

        KnowledgeLogger()->info( "KnowledgeRetrieval loaded {} facts", impl_->facts_.size() );
        loaded_ = true;
        return outcome::success();
    }

    // -----------------------------------------------------------------------
    // Embed — bag-of-words TF-IDF stub
    // -----------------------------------------------------------------------
    std::vector<float> KnowledgeRetrieval::Embed( const std::string& text ) const
    {
        static constexpr size_t kDim = 128;
        std::vector<float> vec( kDim, 0.0f );

        std::istringstream iss( text );
        std::string word;
        while ( iss >> word )
        {
            std::transform( word.begin(), word.end(), word.begin(),
                            []( unsigned char c ) { return std::tolower( c ); } );
            size_t idx = std::hash<std::string>{}( word ) % kDim;
            vec[idx] += 1.0f;
        }

        float norm = 0.0f;
        for ( float v : vec )
        {
            norm += v * v;
        }
        norm = std::sqrt( norm );
        if ( norm > 0.0f )
        {
            for ( auto& v : vec )
            {
                v /= norm;
            }
        }
        return vec;
    }

    // -----------------------------------------------------------------------
    // CosineSimilarity
    // -----------------------------------------------------------------------
    float KnowledgeRetrieval::CosineSimilarity( const std::vector<float>& a, const std::vector<float>& b )
    {
        if ( a.size() != b.size() )
        {
            return 0.0f;
        }
        float dot = 0.0f;
        for ( size_t i = 0; i < a.size(); ++i )
        {
            dot += a[i] * b[i];
        }
        return dot; // vectors are already L2-normalised
    }

    // -----------------------------------------------------------------------
    // Retrieve
    // -----------------------------------------------------------------------
    outcome::result<std::vector<KnowledgeFact>> KnowledgeRetrieval::Retrieve( const std::string& query ) const
    {
        if ( !loaded_ || impl_->facts_.empty() )
        {
            return outcome::failure( Error::KnowledgeUnavailable );
        }

        auto query_emb = Embed( query );

        std::vector<std::pair<float, size_t>> scored;
        scored.reserve( impl_->facts_.size() );
        for ( size_t i = 0; i < impl_->facts_.size(); ++i )
        {
            float score = CosineSimilarity( query_emb, impl_->facts_[i].embedding_ );
            if ( score >= cfg_.min_score_ )
            {
                scored.push_back( { score, i } );
            }
        }

        std::sort( scored.begin(), scored.end(), []( const auto& a, const auto& b ) { return a.first > b.first; } );

        std::vector<KnowledgeFact> results;
        int k = std::min( cfg_.top_k_, static_cast<int>( scored.size() ) );
        for ( int i = 0; i < k; ++i )
        {
            KnowledgeFact f = impl_->facts_[scored[i].second].fact_;
            f.relevance_score_ = scored[i].first;
            results.push_back( std::move( f ) );
        }

        KnowledgeLogger()->debug( "Retrieved {} facts for query '{}'", results.size(), query.substr( 0, 50 ) );
        return outcome::success( std::move( results ) );
    }

} // namespace sgns::neoswarm::knowledge
