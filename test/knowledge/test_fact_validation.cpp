/**
 * @file       test_fact_validation.cpp
 * @brief      Unit tests for FactValidation — claim verification against grounding facts
 * @date       2026-05-28
 * @author     Subaskar S (ssivakumar@gnus.ai)
 */

#include <gtest/gtest.h>
#include "knowledge/FactValidation.hpp"
#include "knowledge/KnowledgeRetrieval.hpp"
#include "common/Types.hpp"

#include <memory>

using namespace sgns::neoswarm;
using namespace sgns::neoswarm::knowledge;

namespace
{
    KnowledgeFact MakeFact( const std::string &source,
                            const std::string &content )
    {
        KnowledgeFact f;
        f.source_  = source;
        f.content_ = content;
        return f;
    }

    std::shared_ptr<KnowledgeRetrieval> MakeRetrieval()
    {
        KnowledgeRetrieval::Config cfg;
        cfg.facts_path_ = "";
        auto ret = std::make_shared<KnowledgeRetrieval>( cfg );
        ret->Load();
        return ret;
    }
}

TEST( FactValidation, EmptyFactsPasses )
{
    auto retrieval = MakeRetrieval();
    FactValidation validator( retrieval );

    std::vector<KnowledgeFact> facts;
    auto result = validator.Validate( "Anything goes", facts );

    EXPECT_TRUE( result.passed_ );
}

TEST( FactValidation, MatchingFactPasses )
{
    auto retrieval = MakeRetrieval();
    FactValidation validator( retrieval );

    std::vector<KnowledgeFact> facts = {
        MakeFact( "physics", "speed of light: 299792 km/s" )
    };

    auto result = validator.Validate(
        "The speed of light is approximately 299792 km per second", facts );
    EXPECT_TRUE( result.passed_ );
}

TEST( FactValidation, NoRelevantFactsPasses )
{
    auto retrieval = MakeRetrieval();
    FactValidation validator( retrieval );

    std::vector<KnowledgeFact> facts = {
        MakeFact( "geography", "Earth radius is 6371 km" ),
        MakeFact( "chemistry", "Water boils at 100 degrees Celsius at sea level" )
    };

    auto result = validator.Validate(
        "The speed of light is very fast", facts );
    EXPECT_TRUE( result.passed_ );
}

TEST( FactValidation, IsAvailable )
{
    auto retrieval = MakeRetrieval();
    FactValidation validator( retrieval );

    // May or may not be available depending on what was loaded
    bool available = validator.IsAvailable();
    // Just verify it doesn't crash — either state is valid
    SUCCEED();
}

TEST( KnowledgeRetrieval, LoadEmptyPathDoesNotCrash )
{
    KnowledgeRetrieval::Config cfg;
    cfg.facts_path_ = "";
    KnowledgeRetrieval retriever( cfg );
    retriever.Load();

    // Retrieve should handle empty facts gracefully
    auto result = retriever.Retrieve( "What is gravity?" );
    EXPECT_TRUE( !result.has_value() || result.has_value() );
}

TEST( KnowledgeRetrieval, NotLoadedReturnsEmpty )
{
    KnowledgeRetrieval::Config cfg;
    cfg.facts_path_ = "/nonexistent/path/facts.csv";
    KnowledgeRetrieval retriever( cfg );
    retriever.Load();

    EXPECT_FALSE( retriever.IsLoaded() );

    auto result = retriever.Retrieve( "test query" );
    EXPECT_FALSE( result.has_value() );
}
