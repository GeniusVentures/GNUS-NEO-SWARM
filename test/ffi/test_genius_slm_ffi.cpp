/**
 * @file       test_genius_slm_ffi.cpp
 * @brief      Unit tests for C FFI layer — chat completions, string free
 * @date       2026-06-09
 * @author     Subaskar S (ssivakumar@gnus.ai)
 */

#include "genius_elm_chat_c.h"
#include <gtest/gtest.h>

TEST( GeniusElmFFI, StringFreeNullptrDoesNotCrash )
{
    GeniusElmStringFree( nullptr );
    SUCCEED();
}

TEST( GeniusElmFFI, ChatCompletionsReturnsValidJson )
{
    const char *request = R"({"messages":[{"role":"user","content":"Hello"}]})";
    char      *response = GeniusElmChatCompletionsCreate( request );
    ASSERT_NE( response, nullptr );

    std::string respStr( response );
    EXPECT_TRUE( respStr.find( '{' ) != std::string::npos );
    EXPECT_TRUE( respStr.find( '}' ) != std::string::npos );

    GeniusElmStringFree( response );
}

TEST( GeniusElmFFI, ChatCompletionsWithNullDoesNotCrash )
{
    char *response = GeniusElmChatCompletionsCreate( nullptr );
    ASSERT_NE( response, nullptr );

    std::string respStr( response );
    EXPECT_TRUE( respStr.find( '{' ) != std::string::npos );

    GeniusElmStringFree( response );
}

TEST( GeniusElmFFI, ChatCompletionsStubContainsRequiredFields )
{
    const char *request = R"({"messages":[{"role":"user","content":"test"}]})";
    char      *response = GeniusElmChatCompletionsCreate( request );
    ASSERT_NE( response, nullptr );

    std::string respStr( response );
    EXPECT_NE( respStr.find( "chat.completion" ), std::string::npos );
    EXPECT_NE( respStr.find( "assistant" ), std::string::npos );

    GeniusElmStringFree( response );
}
