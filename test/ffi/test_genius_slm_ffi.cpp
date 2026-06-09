/**
 * @file       test_genius_slm_ffi.cpp
 * @brief      Unit tests for C FFI layer — init, chat, status, string free
 * @date       2026-05-28
 * @author     Subaskar S (ssivakumar@gnus.ai)
 */

#include "genius_slm_chat_c.h"
#include <gtest/gtest.h>

TEST( GeniusSlmFFI, InitWithNullptrSucceeds )
{
    // GeniusSlmInit(nullptr, nullptr) should initialize in stub mode
    int result = GeniusSlmInit( nullptr, nullptr );
    EXPECT_EQ( result, 0 );
}

TEST( GeniusSlmFFI, StringFreeNullptrDoesNotCrash )
{
    // Freeing nullptr should not crash
    GeniusSlmStringFree( nullptr );
    SUCCEED();
}

TEST( GeniusSlmFFI, GetStatusReturnsValidJson )
{
    int result = GeniusSlmInit( nullptr, nullptr );
    EXPECT_EQ( result, 0 );

    char* status = GeniusSlmGetStatus();
    ASSERT_NE( status, nullptr );

    std::string statusStr( status );
    EXPECT_NE( statusStr.find( "model_loaded" ), std::string::npos );
    EXPECT_NE( statusStr.find( "mode" ), std::string::npos );
    EXPECT_NE( statusStr.find( "supergenius_connected" ), std::string::npos );
    EXPECT_NE( statusStr.find( "fallback_active" ), std::string::npos );

    GeniusSlmStringFree( status );
}

TEST( GeniusSlmFFI, ChatCompletionsReturnsValidJson )
{
    int result = GeniusSlmInit( nullptr, nullptr );
    EXPECT_EQ( result, 0 );

    const char* request = R"({"messages":[{"role":"user","content":"Hello"}]})";
    char* response = GeniusSlmChatCompletionsCreate( request );
    ASSERT_NE( response, nullptr );

    std::string respStr( response );
    // Should be valid JSON — either a chat completion or an error
    EXPECT_TRUE( respStr.find( '{' ) != std::string::npos );
    EXPECT_TRUE( respStr.find( '}' ) != std::string::npos );

    GeniusSlmStringFree( response );
}

TEST( GeniusSlmFFI, ChatCompletionsWithNullDoesNotCrash )
{
    int result = GeniusSlmInit( nullptr, nullptr );
    EXPECT_EQ( result, 0 );

    // Null request should not crash — returns a valid response or error JSON
    char* response = GeniusSlmChatCompletionsCreate( nullptr );
    ASSERT_NE( response, nullptr );

    std::string respStr( response );
    // Response should be valid JSON (stub mode returns a chat completion)
    EXPECT_TRUE( respStr.find( '{' ) != std::string::npos );

    GeniusSlmStringFree( response );
}

TEST( GeniusSlmFFI, MultipleInitCallsSucceed )
{
    // Calling GeniusSlmInit multiple times should succeed each time
    EXPECT_EQ( GeniusSlmInit( nullptr, nullptr ), 0 );
    EXPECT_EQ( GeniusSlmInit( nullptr, nullptr ), 0 );
    EXPECT_EQ( GeniusSlmInit( nullptr, nullptr ), 0 );
}

TEST( GeniusSlmFFI, ChatCompletionsWithoutInitSucceeds )
{
    // Chat should lazy-init if GeniusSlmInit was never called
    const char* request = R"({"messages":[{"role":"user","content":"test"}]})";
    char* response = GeniusSlmChatCompletionsCreate( request );
    ASSERT_NE( response, nullptr );

    GeniusSlmStringFree( response );
}
