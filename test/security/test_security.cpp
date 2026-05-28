/**
 * @file       test_security.cpp
 * @brief      Unit tests for NodeIdentity and MessageSigning (TDD for plan 01-02)
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

// =======================================================================
// Task 1: RFC6979 Deterministic Nonces
// =======================================================================

TEST( NodeIdentity, DeterministicSignature )
{
    // Signing the same message twice with the same key MUST produce
    // identical DER-encoded signatures (deterministic nonces).
    NodeIdentity ident;
    ASSERT_TRUE( ident.Generate().has_value() );
    ASSERT_TRUE( ident.IsLoaded() );

    std::vector<uint8_t> msg1 = {0x01, 0x02, 0x03, 0x04};
    std::vector<uint8_t> msg2 = {0x01, 0x02, 0x03, 0x04};  // same message

    auto sig1 = ident.Sign( msg1 );
    auto sig2 = ident.Sign( msg2 );
    ASSERT_TRUE( sig1.has_value() );
    ASSERT_TRUE( sig2.has_value() );

    EXPECT_EQ( sig1.value().size(), sig2.value().size() );
    EXPECT_EQ( sig1.value(), sig2.value() );
}

TEST( NodeIdentity, DifferentMessagesDifferentSignatures )
{
    // Signing different messages MUST produce different signatures.
    NodeIdentity ident;
    ASSERT_TRUE( ident.Generate().has_value() );

    std::vector<uint8_t> msgA = {0xAA};
    std::vector<uint8_t> msgB = {0xBB};

    auto sigA = ident.Sign( msgA );
    auto sigB = ident.Sign( msgB );
    ASSERT_TRUE( sigA.has_value() );
    ASSERT_TRUE( sigB.has_value() );

    EXPECT_NE( sigA.value(), sigB.value() );
}

TEST( NodeIdentity, SignAndVerifyRoundtrip )
{
    // The produced signature MUST verify against the node's public key.
    NodeIdentity ident;
    ASSERT_TRUE( ident.Generate().has_value() );

    std::vector<uint8_t> msg = {0x01, 0x02, 0x03, 0x04, 0x05};
    auto sig = ident.Sign( msg );
    ASSERT_TRUE( sig.has_value() );

    EXPECT_TRUE( ident.Verify( msg, sig.value() ) );
}

// =======================================================================
// Task 2: Real MessageSigning::Verify
// =======================================================================

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

TEST( MessageSigning, VerifyValidSignature )
{
    // Sign a message with NodeIdentity, verify with MessageSigning::Verify
    // using the correct pub_key_hex — MUST return true.
    NodeIdentity ident;
    ASSERT_TRUE( ident.Generate().has_value() );

    const std::string pubKeyHex = PubKeyToHex( ident.PublicKey() );
    MessageSigning   signer( ident );

    const std::string payload = R"({"msg":"hello"})";
    auto              sig     = signer.Sign( payload );
    ASSERT_TRUE( sig.has_value() );
    ASSERT_FALSE( sig.value().empty() );

    EXPECT_TRUE( MessageSigning::Verify( payload, sig.value(), pubKeyHex ) );
}

TEST( MessageSigning, VerifyTamperedPayload )
{
    // Tamper with the payload after signing, verify — MUST return false.
    NodeIdentity ident;
    ASSERT_TRUE( ident.Generate().has_value() );

    const std::string pubKeyHex = PubKeyToHex( ident.PublicKey() );
    MessageSigning   signer( ident );

    const std::string payload = R"({"msg":"hello"})";
    auto              sig     = signer.Sign( payload );
    ASSERT_TRUE( sig.has_value() );

    // Tamper: change the payload
    const std::string tampered = R"({"msg":"world"})";
    EXPECT_FALSE( MessageSigning::Verify( tampered, sig.value(), pubKeyHex ) );
}

TEST( MessageSigning, VerifyWrongKey )
{
    // Use a different node's public key to verify — MUST return false.
    NodeIdentity identA;
    NodeIdentity identB;
    ASSERT_TRUE( identA.Generate().has_value() );
    ASSERT_TRUE( identB.Generate().has_value() );

    const std::string pubKeyB = PubKeyToHex( identB.PublicKey() );
    MessageSigning   signerA( identA );

    const std::string payload = R"({"msg":"hello"})";
    auto              sig     = signerA.Sign( payload );
    ASSERT_TRUE( sig.has_value() );

    // Verify identA's signature with identB's key — should fail
    EXPECT_FALSE( MessageSigning::Verify( payload, sig.value(), pubKeyB ) );
}

TEST( MessageSigning, VerifyEmptySignature )
{
    // Provide an empty signature — MUST return false.
    NodeIdentity ident;
    ASSERT_TRUE( ident.Generate().has_value() );

    const std::string pubKeyHex = PubKeyToHex( ident.PublicKey() );

    EXPECT_FALSE( MessageSigning::Verify( "payload", {}, pubKeyHex ) );
}

TEST( MessageSigning, VerifyTruncatedSignature )
{
    // Provide a truncated/corrupted DER signature — MUST return false.
    NodeIdentity ident;
    ASSERT_TRUE( ident.Generate().has_value() );

    const std::string pubKeyHex = PubKeyToHex( ident.PublicKey() );

    // Truncated DER: just 8 bytes
    std::vector<uint8_t> truncated = {0x30, 0x06, 0x02, 0x01, 0x01, 0x02, 0x01, 0x01};
    EXPECT_FALSE( MessageSigning::Verify( "payload", truncated, pubKeyHex ) );
}
