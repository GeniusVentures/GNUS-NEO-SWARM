#include "knowledge/knowledge_retrieval.hpp"
#include <gtest/gtest.h>

using namespace sgns::neoswarm;

TEST(KnowledgeRetrieval, DefaultConstructed_IsNotLoaded)
{
    knowledge::KnowledgeRetrieval kr;
    EXPECT_FALSE( kr.IsLoaded() );
}

TEST(KnowledgeRetrieval, Retrieve_WithoutLoad_ReturnsError)
{
    knowledge::KnowledgeRetrieval kr;
    auto result = kr.Retrieve( "test query" );
    EXPECT_FALSE( result.has_value() );
}

TEST(KnowledgeRetrieval, Retrieve_WhenDisabled_ReturnsError)
{
    knowledge::KnowledgeRetrieval::Config cfg;
    cfg.enabled_ = false;
    knowledge::KnowledgeRetrieval kr( cfg );
    auto result = kr.Retrieve( "test query" );
    EXPECT_FALSE( result.has_value() );
}
