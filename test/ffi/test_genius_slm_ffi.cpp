/**
 * @file       test_elm_ffi.cpp
 * @brief      Unit tests for C FFI layer — init, chat completions, status, string free
 * @date       2026-06-10
 * @author     Subaskar S (ssivakumar@gnus.ai)
 */

#include "genius_elm_chat_completions.h"
#include <gtest/gtest.h>

TEST( GeniusElmFFI, InitSucceeds )
{
    int result = GeniusElmInit( nullptr, nullptr );
    EXPECT_EQ( result, 0 );
}

TEST( GeniusElmFFI, StringFreeNullptrDoesNotCrash )
{
    GeniusElmStringFree( nullptr );
    SUCCEED();
}

TEST( GeniusElmFFI, GetStatusReturnsValidJson )
{
    char* status = GeniusElmGetStatus();
    ASSERT_NE( status, nullptr );

    std::string statusStr( status );
    EXPECT_NE( statusStr.find( "model_loaded" ), std::string::npos );
    EXPECT_NE( statusStr.find( "mode" ), std::string::npos );
    EXPECT_NE( statusStr.find( "backend" ), std::string::npos );
    EXPECT_NE( statusStr.find( "node_id" ), std::string::npos );

    GeniusElmStringFree( status );
}

TEST( GeniusElmFFI, ChatCompletionsReturnsValidJson )
{
    const char* request = R"({"messages":[{"role":"user","content":"Hello"}]})";
    char*       response = GeniusElmChatCompletionsCreate( request );
    ASSERT_NE( response, nullptr );

    std::string respStr( response );
    EXPECT_TRUE( respStr.find( '{' ) != std::string::npos );
    EXPECT_TRUE( respStr.find( '}' ) != std::string::npos );

    GeniusElmStringFree( response );
}

TEST( GeniusElmFFI, ChatCompletionsWithNullDoesNotCrash )
{
    char* response = GeniusElmChatCompletionsCreate( nullptr );
    ASSERT_NE( response, nullptr );

    std::string respStr( response );
    EXPECT_TRUE( respStr.find( '{' ) != std::string::npos );

    GeniusElmStringFree( response );
}

TEST( GeniusElmFFI, MultipleInitCallsSucceed )
{
    EXPECT_EQ( GeniusElmInit( nullptr, nullptr ), 0 );
    EXPECT_EQ( GeniusElmInit( nullptr, nullptr ), 0 );
    EXPECT_EQ( GeniusElmInit( nullptr, nullptr ), 0 );
}
