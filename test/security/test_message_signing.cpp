/**
 * @file       test_message_signing.cpp
 * @brief      Unit tests for MessageSigning — verify, tamper rejection, replay protection
 * @date       2026-05-28
 * @author     GSD Executor
 */

#include <gtest/gtest.h>
#include "security/NodeIdentity.hpp"
#include "security/MessageSigning.hpp"

#include <iomanip>
#include <sstream>
#include <string>
#include <vector>

using namespace sgns::neoswarm;
using namespace sgns::neoswarm::security;

namespace
{
    std::string PubKeyToHex( const NodeIdentity::PubKey &key )
    {
        std::ostringstream oss;
        for ( auto b : key )
        {
            oss << std::hex << std::setw( 2 ) << std::setfill( '0' )
                << static_cast<int>( b );
        }
        return oss.str();
    }
}

// =======================================================================
// Signature Verification
// =======================================================================

TEST( MessageSigning, VerifyValidSignature )
{
    NodeIdentity ident;
    ASSERT_TRUE( ident.Generate().has_value() );

    const std::string pubKeyHex = PubKeyToHex( ident.PublicKey() );
    MessageSigning signer( ident );

    const std::string payload = R"({"msg":"hello"})";
    auto sig = signer.Sign( payload );
    ASSERT_TRUE( sig.has_value() );
    ASSERT_FALSE( sig.value().empty() );

    EXPECT_TRUE( MessageSigning::Verify( payload, sig.value(), pubKeyHex ) );
}

TEST( MessageSigning, VerifyTamperedPayload )
{
    NodeIdentity ident;
    ASSERT_TRUE( ident.Generate().has_value() );

    const std::string pubKeyHex = PubKeyToHex( ident.PublicKey() );
    MessageSigning signer( ident );

    const std::string payload = R"({"msg":"hello"})";
    auto sig = signer.Sign( payload );
    ASSERT_TRUE( sig.has_value() );

    const std::string tampered = R"({"msg":"world"})";
    EXPECT_FALSE( MessageSigning::Verify( tampered, sig.value(), pubKeyHex ) );
}

TEST( MessageSigning, VerifyWrongKey )
{
    NodeIdentity identA;
    NodeIdentity identB;
    ASSERT_TRUE( identA.Generate().has_value() );
    ASSERT_TRUE( identB.Generate().has_value() );

    const std::string pubKeyB = PubKeyToHex( identB.PublicKey() );
    MessageSigning signerA( identA );

    const std::string payload = R"({"msg":"hello"})";
    auto sig = signerA.Sign( payload );
    ASSERT_TRUE( sig.has_value() );

    EXPECT_FALSE( MessageSigning::Verify( payload, sig.value(), pubKeyB ) );
}

TEST( MessageSigning, VerifyEmptySignature )
{
    NodeIdentity ident;
    ASSERT_TRUE( ident.Generate().has_value() );

    const std::string pubKeyHex = PubKeyToHex( ident.PublicKey() );

    EXPECT_FALSE( MessageSigning::Verify( "payload", {}, pubKeyHex ) );
}

TEST( MessageSigning, VerifyTruncatedSignature )
{
    NodeIdentity ident;
    ASSERT_TRUE( ident.Generate().has_value() );

    const std::string pubKeyHex = PubKeyToHex( ident.PublicKey() );

    std::vector<uint8_t> truncated = {0x30, 0x06, 0x02, 0x01, 0x01, 0x02, 0x01, 0x01};
    EXPECT_FALSE( MessageSigning::Verify( "payload", truncated, pubKeyHex ) );
}

// =======================================================================
// Nonce + Timestamp Replay Protection
// =======================================================================

TEST( MessageSigning, VerifyAndStripValid )
{
    NodeIdentity ident;
    ASSERT_TRUE( ident.Generate().has_value() );

    const std::string pubKeyHex = PubKeyToHex( ident.PublicKey() );
    MessageSigning signer( ident );

    const std::string original = R"({"msg":"hello"})";
    std::string payload = signer.AttachSignature( original );

    EXPECT_NE( payload, original );
    EXPECT_TRUE( MessageSigning::VerifyAndStrip( payload, pubKeyHex ) );
    EXPECT_EQ( payload, original );
}

TEST( MessageSigning, VerifyAndStripExpiredTimestamp )
{
    NodeIdentity ident;
    ASSERT_TRUE( ident.Generate().has_value() );

    const std::string pubKeyHex = PubKeyToHex( ident.PublicKey() );
    MessageSigning signer( ident );

    std::string payload = signer.AttachSignature( R"({"msg":"test"})" );

    auto tsPos = payload.rfind( ",\"ts\":" );
    ASSERT_NE( tsPos, std::string::npos );

    uint64_t oldTs = MessageSigning::CurrentTimestampMs() - 61000;
    auto tsVal = payload.find_first_of( "0123456789", tsPos + 6 );
    auto tsEnd = payload.find_first_of( ",}", tsVal );
    ASSERT_NE( tsVal, std::string::npos );
    ASSERT_NE( tsEnd, std::string::npos );

    payload.replace( tsVal, tsEnd - tsVal, std::to_string( oldTs ) );

    EXPECT_FALSE( MessageSigning::VerifyAndStrip( payload, pubKeyHex ) );
}
