#include "knowledge/context_injection.hpp"
#include <gtest/gtest.h>
#include <string>
#include <vector>

using namespace sgns::neoswarm;

namespace
{
    KnowledgeFact MakeFact( const std::string& source, const std::string& content, float score = 1.0f )
    {
        KnowledgeFact fact;
        fact.m_source = source;
        fact.m_content = content;
        fact.m_relevanceScore = score;
        return fact;
    }
} // namespace

TEST(ContextInjection, Inject_WithValidFacts_PrependsFacts)
{
    knowledge::ContextInjection ci;
    std::vector<KnowledgeFact> facts = {MakeFact( "wiki", "Earth is round" ),
                                                    MakeFact( "wiki", "Water is wet" )};

    auto result = ci.Inject( "What is Earth?", facts );
    EXPECT_NE( result.find( "Earth is round" ), std::string::npos );
    EXPECT_NE( result.find( "Water is wet" ), std::string::npos );
    EXPECT_NE( result.find( "What is Earth?" ), std::string::npos );
}

TEST(ContextInjection, Inject_WithEmptyFacts_ReturnsOriginalPrompt)
{
    knowledge::ContextInjection ci;
    std::vector<KnowledgeFact> facts;

    auto result = ci.Inject( "Hello world", facts );
    EXPECT_EQ( result, "Hello world" );
}

TEST(ContextInjection, Fuzz_EmptyPrompt_DoesNotCrash)
{
    knowledge::ContextInjection ci;
    std::vector<KnowledgeFact> facts = {MakeFact( "src", "content" )};

    auto result = ci.Inject( "", facts );
    EXPECT_FALSE( result.empty() );
}

TEST(ContextInjection, Fuzz_EmptyFacts_DoesNotCrash)
{
    knowledge::ContextInjection ci;
    std::vector<KnowledgeFact> facts = {MakeFact( "", "" )};

    auto result = ci.Inject( "prompt", facts );
    EXPECT_FALSE( result.empty() );
}
