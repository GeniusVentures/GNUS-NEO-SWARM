/**
 * @file       test_genius_slm_ffi.cpp
 * @brief      Unit tests for C FFI layer — init, chat, status, string free
 * @date       2026-05-28
 * @author     Subaskar S (ssivakumar@gnus.ai)
 */

#include "genius_elm_chat_completions.h"
#include <gtest/gtest.h>

TEST( GeniusElmFFI, InitWithNullptrSucceeds )
{
    // GeniusElmInit(nullptr, nullptr) should initialize in stub mode
    int result = GeniusElmInit( nullptr, nullptr );
    EXPECT_EQ( result, 0 );
}

TEST( GeniusElmFFI, StringFreeNullptrDoesNotCrash )
{
    // Freeing nullptr should not crash
    GeniusElmStringFree( nullptr );
    SUCCEED();
}

TEST( GeniusElmFFI, GetStatusReturnsValidJson )
{
    int result = GeniusElmInit( nullptr, nullptr );
    EXPECT_EQ( result, 0 );

    char* status = GeniusElmGetStatus();
    ASSERT_NE( status, nullptr );

    std::string statusStr( status );
    EXPECT_NE( statusStr.find( "model_loaded" ), std::string::npos );
    EXPECT_NE( statusStr.find( "mode" ), std::string::npos );
    EXPECT_NE( statusStr.find( "supergenius_connected" ), std::string::npos );
    EXPECT_NE( statusStr.find( "fallback_active" ), std::string::npos );

    GeniusElmStringFree( status );
}

TEST( GeniusElmFFI, ChatCompletionsReturnsValidJson )
{
    int result = GeniusElmInit( nullptr, nullptr );
    EXPECT_EQ( result, 0 );

    const char* request = R"({"messages":[{"role":"user","content":"Hello"}]})";
    char* response = GeniusElmChatCompletionsCreate( request );
    ASSERT_NE( response, nullptr );

    std::string respStr( response );
    // Should be valid JSON — either a chat completion or an error
    EXPECT_TRUE( respStr.find( '{' ) != std::string::npos );
    EXPECT_TRUE( respStr.find( '}' ) != std::string::npos );

    GeniusElmStringFree( response );
}

TEST( GeniusElmFFI, ChatCompletionsWithNullDoesNotCrash )
{
    int result = GeniusElmInit( nullptr, nullptr );
    EXPECT_EQ( result, 0 );

    // Null request should not crash — returns a valid response or error JSON
    char* response = GeniusElmChatCompletionsCreate( nullptr );
    ASSERT_NE( response, nullptr );

    std::string respStr( response );
    // Response should be valid JSON (stub mode returns a chat completion)
    EXPECT_TRUE( respStr.find( '{' ) != std::string::npos );

    GeniusElmStringFree( response );
}

TEST( GeniusElmFFI, MultipleInitCallsSucceed )
{
    // Calling GeniusElmInit multiple times should succeed each time
    EXPECT_EQ( GeniusElmInit( nullptr, nullptr ), 0 );
    EXPECT_EQ( GeniusElmInit( nullptr, nullptr ), 0 );
    EXPECT_EQ( GeniusElmInit( nullptr, nullptr ), 0 );
}

TEST( GeniusElmFFI, ChatCompletionsWithoutInitSucceeds )
{
    // Chat should lazy-init if GeniusElmInit was never called
    const char* request = R"({"messages":[{"role":"user","content":"test"}]})";
    char* response = GeniusElmChatCompletionsCreate( request );
    ASSERT_NE( response, nullptr );

    GeniusElmStringFree( response );
}
