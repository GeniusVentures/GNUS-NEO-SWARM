/**
 * @file       m_knowledgeretrieval.cpp
 * @brief      Grokipedia knowledge retrieval implementation
 * @date       2026-05-06
 * @author     Subaskar S (ssivakumar@gnus.ai)
 */

#include "knowledge_retrieval.hpp"
#include "common/logging.hpp"

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
        std::vector<FactEntry> m_facts;
    };

    KnowledgeRetrieval::KnowledgeRetrieval()
        : m_impl( std::make_unique<Impl>() )
    {
    }

    KnowledgeRetrieval::KnowledgeRetrieval( Config cfg )
        : m_impl( std::make_unique<Impl>() )
        , m_cfg( std::move( cfg ) )
    {
    }

    KnowledgeRetrieval::~KnowledgeRetrieval() = default;

    // -----------------------------------------------------------------------
    // Load
    // -----------------------------------------------------------------------
    outcome::result<void> KnowledgeRetrieval::Load()
    {
        if ( !m_cfg.enabled_ )
        {
            KnowledgeLogger()->info( "KnowledgeRetrieval disabled" );
            return outcome::success();
        }

        if ( m_cfg.m_factsPath.empty() )
        {
            KnowledgeLogger()->warn( "KnowledgeRetrieval: no facts path — using stub facts" );
            m_impl->m_facts.push_back(
                { { "Grokipedia", "The speed of light in vacuum is approximately 299,792,458 m/s.", 0.0f },
                  Embed( "speed of light vacuum" ) } );
            m_impl->m_facts.push_back( { { "Grokipedia", "Pi (π) is approximately 3.14159265358979.", 0.0f },
                                         Embed( "pi mathematical constant" ) } );
            m_impl->m_facts.push_back(
                { { "Grokipedia", "Water (H2O) has a molecular weight of approximately 18.015 g/mol.", 0.0f },
                  Embed( "water molecular weight chemistry" ) } );
            m_loaded = true;
            return outcome::success();
        }

        std::ifstream f( m_cfg.m_factsPath );
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
            fact.m_source = line.substr( 0, comma );
            fact.m_content = line.substr( comma + 1 );
            m_impl->m_facts.push_back( { fact, Embed( fact.m_content ) } );
        }

        KnowledgeLogger()->info( "KnowledgeRetrieval loaded {} facts", m_impl->m_facts.size() );
        m_loaded = true;
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
        if ( !m_loaded || m_impl->m_facts.empty() )
        {
            return outcome::failure( Error::KnowledgeUnavailable );
        }

        auto query_emb = Embed( query );

        std::vector<std::pair<float, size_t>> scored;
        scored.reserve( m_impl->m_facts.size() );
        for ( size_t i = 0; i < m_impl->m_facts.size(); ++i )
        {
            float score = CosineSimilarity( query_emb, m_impl->m_facts[i].embedding_ );
            if ( score >= m_cfg.min_score_ )
            {
                scored.push_back( { score, i } );
            }
        }

        std::sort( scored.begin(), scored.end(), []( const auto& a, const auto& b ) { return a.first > b.first; } );

        std::vector<KnowledgeFact> results;
        int k = std::min( m_cfg.top_k_, static_cast<int>( scored.size() ) );
        for ( int i = 0; i < k; ++i )
        {
            KnowledgeFact f = m_impl->m_facts[scored[i].second].fact_;
            f.m_relevanceScore = scored[i].first;
            results.push_back( std::move( f ) );
        }

        KnowledgeLogger()->debug( "Retrieved {} facts for query '{}'", results.size(), query.substr( 0, 50 ) );
        return outcome::success( std::move( results ) );
    }

} // namespace sgns::neoswarm::knowledge
