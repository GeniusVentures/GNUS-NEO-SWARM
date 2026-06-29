/**
 * @file       test_node_identity.cpp
 * @brief      Unit tests for NodeIdentity — key generation, sign/verify, encrypted save/load
 * @date       2026-05-28
 * @author     GSD Executor
 */

#include "security/node_identity.hpp"
#include <gtest/gtest.h>

#include <cstdio>
#include <fstream>
#include <vector>

using namespace sgns::neoswarm;
using namespace sgns::neoswarm::security;

namespace
{
    const std::string kTestKeyPath = "/tmp/gnus_test_node.key";
    const std::string kTestPass = "test123";
    const std::string kWrongPass = "wrong456";

    void RemoveTestFile()
    {
        std::remove( kTestKeyPath.c_str() );
    }
} // namespace

// =======================================================================
// Key Generation & Identity
// =======================================================================

TEST( NodeIdentity, DeterministicSignature )
{
    NodeIdentity ident;
    ASSERT_TRUE( ident.Generate().has_value() );
    ASSERT_TRUE( ident.IsLoaded() );

    std::vector<uint8_t> msg1 = { 0x01, 0x02, 0x03, 0x04 };
    std::vector<uint8_t> msg2 = { 0x01, 0x02, 0x03, 0x04 };

    auto sig1 = ident.Sign( msg1 );
    auto sig2 = ident.Sign( msg2 );
    ASSERT_TRUE( sig1.has_value() );
    ASSERT_TRUE( sig2.has_value() );

    EXPECT_EQ( sig1.value().size(), sig2.value().size() );
    EXPECT_EQ( sig1.value(), sig2.value() );
}

TEST( NodeIdentity, DifferentMessagesDifferentSignatures )
{
    NodeIdentity ident;
    ASSERT_TRUE( ident.Generate().has_value() );

    std::vector<uint8_t> msgA = { 0xAA };
    std::vector<uint8_t> msgB = { 0xBB };

    auto sigA = ident.Sign( msgA );
    auto sigB = ident.Sign( msgB );
    ASSERT_TRUE( sigA.has_value() );
    ASSERT_TRUE( sigB.has_value() );

    EXPECT_NE( sigA.value(), sigB.value() );
}

TEST( NodeIdentity, SignAndVerifyRoundtrip )
{
    NodeIdentity ident;
    ASSERT_TRUE( ident.Generate().has_value() );

    std::vector<uint8_t> msg = { 0x01, 0x02, 0x03, 0x04, 0x05 };
    auto sig = ident.Sign( msg );
    ASSERT_TRUE( sig.has_value() );

    EXPECT_TRUE( ident.Verify( msg, sig.value() ) );
}

// =======================================================================
// AES-256-GCM Encrypted Key Storage
// =======================================================================

TEST( NodeIdentity, SaveEncryptedLoadEncryptedRoundtrip )
{
    RemoveTestFile();

    NodeIdentity ident1;
    ASSERT_TRUE( ident1.Generate().has_value() );
    ASSERT_TRUE( ident1.IsLoaded() );

    auto saveResult = ident1.SaveEncrypted( kTestKeyPath, kTestPass );
    ASSERT_TRUE( saveResult.has_value() );

    NodeIdentity ident2;
    auto loadResult = ident2.LoadEncrypted( kTestKeyPath, kTestPass );
    ASSERT_TRUE( loadResult.has_value() );
    ASSERT_TRUE( ident2.IsLoaded() );

    EXPECT_EQ( ident1.GetPeerId(), ident2.GetPeerId() );

    RemoveTestFile();
}

TEST( NodeIdentity, LoadEncryptedWrongPassphrase )
{
    RemoveTestFile();

    NodeIdentity ident1;
    ASSERT_TRUE( ident1.Generate().has_value() );
    ASSERT_TRUE( ident1.SaveEncrypted( kTestKeyPath, kTestPass ).has_value() );

    NodeIdentity ident2;
    auto result = ident2.LoadEncrypted( kTestKeyPath, kWrongPass );

    EXPECT_FALSE( result.has_value() );
    EXPECT_EQ( result.error(), Error::IdentityError );

    RemoveTestFile();
}

TEST( NodeIdentity, LoadEncryptedTamperedFile )
{
    RemoveTestFile();

    NodeIdentity ident1;
    ASSERT_TRUE( ident1.Generate().has_value() );
    ASSERT_TRUE( ident1.SaveEncrypted( kTestKeyPath, kTestPass ).has_value() );

    {
        std::fstream f( kTestKeyPath, std::ios::binary | std::ios::in | std::ios::out );
        ASSERT_TRUE( f.is_open() );
        f.seekp( 48, std::ios::beg );
        char c = 0;
        f.get( c );
        f.seekp( 48, std::ios::beg );
        f.put( static_cast<char>( c ^ 0xFF ) );
        f.close();
    }

    NodeIdentity ident2;
    auto result = ident2.LoadEncrypted( kTestKeyPath, kTestPass );

    EXPECT_FALSE( result.has_value() );
    EXPECT_EQ( result.error(), Error::IdentityError );

    RemoveTestFile();
}

TEST( NodeIdentity, SaveEncryptedWithoutKey )
{
    RemoveTestFile();

    NodeIdentity ident;
    ASSERT_FALSE( ident.IsLoaded() );

    auto result = ident.SaveEncrypted( kTestKeyPath, kTestPass );

    EXPECT_FALSE( result.has_value() );
    EXPECT_EQ( result.error(), Error::IdentityError );

    RemoveTestFile();
}

TEST( NodeIdentity, LoadEncryptedNonexistentFile )
{
    RemoveTestFile();

    NodeIdentity ident;
    auto result = ident.LoadEncrypted( kTestKeyPath, kTestPass );

    EXPECT_FALSE( result.has_value() );
    EXPECT_EQ( result.error(), Error::IdentityError );
}

TEST( NodeIdentity, SaveEncryptedOverwrite )
{
    RemoveTestFile();

    NodeIdentity ident1;
    ASSERT_TRUE( ident1.Generate().has_value() );
    ASSERT_TRUE( ident1.SaveEncrypted( kTestKeyPath, kTestPass ).has_value() );
    ASSERT_TRUE( ident1.SaveEncrypted( kTestKeyPath, kTestPass ).has_value() );

    NodeIdentity ident2;
    ASSERT_TRUE( ident2.LoadEncrypted( kTestKeyPath, kTestPass ).has_value() );
    EXPECT_EQ( ident1.GetPeerId(), ident2.GetPeerId() );

    RemoveTestFile();
}

TEST( NodeIdentity, PeerId_ConsistentForSameKey )
{
    RemoveTestFile();

    NodeIdentity ident1;
    ASSERT_TRUE( ident1.Generate().has_value() );
    ASSERT_TRUE( ident1.SaveToFile( kTestKeyPath ).has_value() );
    std::string peerId1 = ident1.PeerId();

    NodeIdentity ident2;
    ASSERT_TRUE( ident2.LoadFromFile( kTestKeyPath ).has_value() );
    std::string peerId2 = ident2.PeerId();

    EXPECT_EQ( peerId1, peerId2 );
    EXPECT_FALSE( peerId1.empty() );
    RemoveTestFile();
}

TEST( NodeIdentity, LoadEncrypted_TruncatedFile_ReturnsError )
{
    RemoveTestFile();

    NodeIdentity ident;
    ASSERT_TRUE( ident.Generate().has_value() );
    ASSERT_TRUE( ident.SaveEncrypted( kTestKeyPath, kTestPass ).has_value() );

    {
        std::ofstream f( kTestKeyPath, std::ios::trunc | std::ios::binary );
        ASSERT_TRUE( f.is_open() );
        f.write( "short", 5 );
        f.close();
    }

    NodeIdentity ident2;
    auto result = ident2.LoadEncrypted( kTestKeyPath, kTestPass );
    EXPECT_FALSE( result.has_value() );

    RemoveTestFile();
}

TEST( NodeIdentity, PeerId_WithoutKey_ReturnsEmpty )
{
    NodeIdentity ident;
    EXPECT_TRUE( ident.PeerId().empty() );
}

TEST( NodeIdentity, LoadFromFile_EmptyPath_ReturnsError )
{
    NodeIdentity ident;
    auto result = ident.LoadFromFile( "" );
    EXPECT_FALSE( result.has_value() );
}

TEST( NodeIdentity, SaveToFile_WithoutKey_ReturnsError )
{
    NodeIdentity ident;
    auto result = ident.SaveToFile( kTestKeyPath );
    EXPECT_FALSE( result.has_value() );
}
