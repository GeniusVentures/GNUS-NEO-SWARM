/**
 * @file       NodeIdentity.cpp
 * @brief      secp256k1 keypair implementation
 * @date       2026-05-08
 * @author     Subaskar S (ssivakumar@gnus.ai)
 */

#include "NodeIdentity.hpp"
#include "common/Logging.hpp"

#include <fstream>
#include <iomanip>
#include <random>
#include <sstream>

#ifdef GENIUS_HAS_SECP256K1
namespace { constexpr int kPbkdf2Iterations = 600000; }
#include <secp256k1.h>
#endif

#ifdef GENIUS_HAS_OPENSSL
#include <openssl/evp.h>
#include <openssl/rand.h>
#include <openssl/sha.h>
#endif
#include <cstring>

namespace sgns::neoswarm::security
{
    namespace
    {
        auto IdentityLogger()
        {
            return neoswarm::CreateLogger( "NodeIdentity" );
        }

        std::string ToHex( const uint8_t* data, size_t len )
        {
            std::ostringstream oss;
            for ( size_t i = 0; i < len; ++i )
            {
                oss << std::hex << std::setw( 2 ) << std::setfill( '0' ) << static_cast<int>( data[i] );
            }
            return oss.str();
        }

        std::vector<uint8_t> FromHex( const std::string& hex )
        {
            std::vector<uint8_t> bytes;
            for ( size_t i = 0; i + 1 < hex.size(); i += 2 )
            {
                bytes.push_back( static_cast<uint8_t>( std::stoul( hex.substr( i, 2 ), nullptr, 16 ) ) );
            }
            return bytes;
        }
    } // namespace

    // -----------------------------------------------------------------------
    // Impl
    // -----------------------------------------------------------------------
    struct NodeIdentity::Impl
    {
        PrivKey priv_key_{};
#ifdef GENIUS_HAS_SECP256K1
        secp256k1_context* ctx_ = nullptr;
#endif
    };

    NodeIdentity::NodeIdentity()
        : impl_( std::make_unique<Impl>() )
    {
#ifdef GENIUS_HAS_SECP256K1
        impl_->ctx_ = secp256k1_context_create( SECP256K1_CONTEXT_SIGN | SECP256K1_CONTEXT_VERIFY );
#endif
    }

    NodeIdentity::~NodeIdentity()
    {
#ifdef GENIUS_HAS_SECP256K1
        if ( impl_ && impl_->ctx_ )
        {
            secp256k1_context_destroy( impl_->ctx_ );
        }
#endif
    }

    // -----------------------------------------------------------------------
    // Generate
    // -----------------------------------------------------------------------
    outcome::result<void> NodeIdentity::Generate()
    {
#ifdef GENIUS_HAS_SECP256K1
        std::random_device rd;
        std::mt19937_64 rng( rd() );
        std::uniform_int_distribution<uint8_t> dist( 0, 255 );

        for ( int attempt = 0; attempt < 100; ++attempt )
        {
            for ( auto& b : impl_->priv_key_ )
            {
                b = dist( rng );
            }
            if ( secp256k1_ec_seckey_verify( impl_->ctx_, impl_->priv_key_.data() ) )
            {
                secp256k1_pubkey pubkey;
                (void)secp256k1_ec_pubkey_create( impl_->ctx_, &pubkey, impl_->priv_key_.data() );
                size_t pub_len = kPubKeySize;
                secp256k1_ec_pubkey_serialize( impl_->ctx_, pub_key_.data(), &pub_len, &pubkey,
                                               SECP256K1_EC_COMPRESSED );
                loaded_ = true;
                IdentityLogger()->info( "NodeIdentity generated: peerId={}", PeerId() );
                return outcome::success();
            }
        }
        return outcome::failure( Error::IdentityError );
#else
        std::random_device rd;
        std::mt19937_64 rng( rd() );
        std::uniform_int_distribution<uint8_t> dist( 0, 255 );
        for ( auto& b : impl_->priv_key_ )
        {
            b = dist( rng );
        }
        for ( auto& b : pub_key_ )
        {
            b = dist( rng );
        }
        pub_key_[0] = 0x02; // compressed prefix
        loaded_ = true;
        IdentityLogger()->warn( "secp256k1 not compiled in — using stub identity" );
        return outcome::success();
#endif
    }

    // -----------------------------------------------------------------------
    // PeerId
    // -----------------------------------------------------------------------
    std::string NodeIdentity::PeerId() const
    {
        if ( !loaded_ )
        {
            return "";
        }
#ifdef GENIUS_HAS_OPENSSL
        uint8_t hash[SHA256_DIGEST_LENGTH];
        SHA256( pub_key_.data(), pub_key_.size(), hash );
        return ToHex( hash, SHA256_DIGEST_LENGTH );
#else
        uint8_t hash[32] = {};
        for ( size_t i = 0; i < pub_key_.size(); ++i )
        {
            hash[i % 32] ^= pub_key_[i];
        }
        return ToHex( hash, 32 );
#endif
    }

    // -----------------------------------------------------------------------
    // LoadFromFile
    // -----------------------------------------------------------------------
    outcome::result<void> NodeIdentity::LoadFromFile( const std::string& path )
    {
        std::ifstream f( path );
        if ( !f )
        {
            return outcome::failure( Error::IdentityError );
        }
        std::string hex_priv;
        f >> hex_priv;
        auto bytes = FromHex( hex_priv );
        if ( bytes.size() != kPrivKeySize )
        {
            return outcome::failure( Error::IdentityError );
        }
        std::copy( bytes.begin(), bytes.end(), impl_->priv_key_.begin() );
#ifdef GENIUS_HAS_SECP256K1
        secp256k1_pubkey pubkey;
        (void)secp256k1_ec_pubkey_create( impl_->ctx_, &pubkey, impl_->priv_key_.data() );
        size_t pub_len = kPubKeySize;
        secp256k1_ec_pubkey_serialize( impl_->ctx_, pub_key_.data(), &pub_len, &pubkey, SECP256K1_EC_COMPRESSED );
#endif
        loaded_ = true;
        return outcome::success();
    }

    // -----------------------------------------------------------------------
    // SaveToFile
    // -----------------------------------------------------------------------
    outcome::result<void> NodeIdentity::SaveToFile( const std::string& path ) const
    {
        if ( !loaded_ )
        {
            return outcome::failure( Error::IdentityError );
        }
        std::ofstream f( path );
        if ( !f )
        {
            return outcome::failure( Error::IdentityError );
        }
        f << ToHex( impl_->priv_key_.data(), kPrivKeySize ) << '\n';
        return outcome::success();
    }

    // -----------------------------------------------------------------------
    // SaveEncrypted
    // -----------------------------------------------------------------------
    outcome::result<void> NodeIdentity::SaveEncrypted( const std::string& path, const std::string& passphrase ) const
    {
        if ( !loaded_ )
        {
            return outcome::failure( Error::IdentityError );
        }

#ifdef GENIUS_HAS_OPENSSL
        // 1. Generate 32-byte random salt
        uint8_t salt[32];
        if ( !RAND_bytes( salt, sizeof( salt ) ) )
        {
            return outcome::failure( Error::IdentityError );
        }

        // 2. Derive 256-bit encryption key via PBKDF2
        uint8_t key[32]; // AES-256
        if ( !PKCS5_PBKDF2_HMAC( passphrase.c_str(), static_cast<int>( passphrase.size() ), salt, sizeof( salt ),
                                  kPbkdf2Iterations, // iterations
                                 EVP_sha256(), sizeof( key ), key ) )
        {
            return outcome::failure( Error::IdentityError );
        }

        // 3. Generate 12-byte random IV for GCM
        uint8_t iv[12];
        if ( !RAND_bytes( iv, sizeof( iv ) ) )
        {
            return outcome::failure( Error::IdentityError );
        }

        // 4. Encrypt with AES-256-GCM
        EVP_CIPHER_CTX* ctx = EVP_CIPHER_CTX_new();
        if ( !ctx )
        {
            return outcome::failure( Error::IdentityError );
        }

        if ( !EVP_EncryptInit_ex( ctx, EVP_aes_256_gcm(), nullptr, nullptr, nullptr ) )
        {
            EVP_CIPHER_CTX_free( ctx );
            return outcome::failure( Error::IdentityError );
        }

        if ( !EVP_CIPHER_CTX_ctrl( ctx, EVP_CTRL_GCM_SET_IVLEN, sizeof( iv ), nullptr ) )
        {
            EVP_CIPHER_CTX_free( ctx );
            return outcome::failure( Error::IdentityError );
        }

        if ( !EVP_EncryptInit_ex( ctx, nullptr, nullptr, key, iv ) )
        {
            EVP_CIPHER_CTX_free( ctx );
            return outcome::failure( Error::IdentityError );
        }

        // Encrypt the private key
        std::vector<uint8_t> ciphertext( kPrivKeySize + 16 ); // room for block padding
        int outLen = 0;
        if ( !EVP_EncryptUpdate( ctx, ciphertext.data(), &outLen, impl_->priv_key_.data(),
                                 static_cast<int>( kPrivKeySize ) ) )
        {
            EVP_CIPHER_CTX_free( ctx );
            return outcome::failure( Error::IdentityError );
        }
        int totalLen = outLen;

        if ( !EVP_EncryptFinal_ex( ctx, ciphertext.data() + totalLen, &outLen ) )
        {
            EVP_CIPHER_CTX_free( ctx );
            return outcome::failure( Error::IdentityError );
        }
        totalLen += outLen;
        ciphertext.resize( totalLen );

        // 5. Get GCM tag
        uint8_t tag[16];
        if ( !EVP_CIPHER_CTX_ctrl( ctx, EVP_CTRL_GCM_GET_TAG, sizeof( tag ), tag ) )
        {
            EVP_CIPHER_CTX_free( ctx );
            return outcome::failure( Error::IdentityError );
        }

        EVP_CIPHER_CTX_free( ctx );

        // 6. Write binary file: [4B salt_len][32B salt][12B IV][ciphertext][16B tag]
        std::ofstream f( path, std::ios::binary );
        if ( !f )
        {
            return outcome::failure( Error::IdentityError );
        }

        uint32_t saltLen = static_cast<uint32_t>( sizeof( salt ) );
        f.write( reinterpret_cast<const char*>( &saltLen ), sizeof( saltLen ) );
        f.write( reinterpret_cast<const char*>( salt ), sizeof( salt ) );
        f.write( reinterpret_cast<const char*>( iv ), sizeof( iv ) );
        f.write( reinterpret_cast<const char*>( ciphertext.data() ),
                 static_cast<std::streamsize>( ciphertext.size() ) );
        f.write( reinterpret_cast<const char*>( tag ), sizeof( tag ) );

        if ( !f.good() )
        {
            return outcome::failure( Error::IdentityError );
        }

        IdentityLogger()->info( "NodeIdentity saved encrypted to {}", path );
        return outcome::success();
#else
        IdentityLogger()->error( "SaveEncrypted: OpenSSL not available" );
        return outcome::failure( Error::IdentityError );
#endif
    }

    // -----------------------------------------------------------------------
    // LoadEncrypted
    // -----------------------------------------------------------------------
    outcome::result<void> NodeIdentity::LoadEncrypted( const std::string& path, const std::string& passphrase )
    {
#ifdef GENIUS_HAS_OPENSSL
        std::ifstream f( path, std::ios::binary );
        if ( !f )
        {
            return outcome::failure( Error::IdentityError );
        }

        // 1. Read salt length
        uint32_t saltLen = 0;
        f.read( reinterpret_cast<char*>( &saltLen ), sizeof( saltLen ) );
        if ( !f.good() || saltLen == 0 || saltLen > 1024 )
        {
            return outcome::failure( Error::IdentityError );
        }

        // 2. Read salt
        std::vector<uint8_t> salt( saltLen );
        f.read( reinterpret_cast<char*>( salt.data() ), static_cast<std::streamsize>( saltLen ) );
        if ( !f.good() )
        {
            return outcome::failure( Error::IdentityError );
        }

        // 3. Read IV
        uint8_t iv[12];
        f.read( reinterpret_cast<char*>( iv ), sizeof( iv ) );
        if ( !f.good() )
        {
            return outcome::failure( Error::IdentityError );
        }

        // 4. Read ciphertext (remaining bytes minus 16-byte tag)
        f.seekg( 0, std::ios::end );
        auto fileSize = f.tellg();
        f.seekg( static_cast<std::streamoff>( sizeof( saltLen ) + saltLen + sizeof( iv ) ), std::ios::beg );
        auto ciphertextSize = static_cast<size_t>( fileSize - f.tellg() ) - 16; // minus tag
        if ( ciphertextSize > 1024 || ciphertextSize < kPrivKeySize )
        {
            return outcome::failure( Error::IdentityError );
        }
        std::vector<uint8_t> ciphertext( ciphertextSize );
        f.read( reinterpret_cast<char*>( ciphertext.data() ), static_cast<std::streamsize>( ciphertextSize ) );
        if ( !f.good() )
        {
            return outcome::failure( Error::IdentityError );
        }

        // 5. Read GCM tag
        uint8_t tag[16];
        f.read( reinterpret_cast<char*>( tag ), sizeof( tag ) );
        if ( !f.good() )
        {
            return outcome::failure( Error::IdentityError );
        }

        // 6. Derive key via PBKDF2
        uint8_t key[32];
        if ( !PKCS5_PBKDF2_HMAC( passphrase.c_str(), static_cast<int>( passphrase.size() ), salt.data(),
                                 static_cast<int>( salt.size() ),  kPbkdf2Iterations, EVP_sha256(), sizeof( key ), key ) )
        {
            return outcome::failure( Error::IdentityError );
        }

        // 7. Decrypt with AES-256-GCM
        EVP_CIPHER_CTX* ctx = EVP_CIPHER_CTX_new();
        if ( !ctx )
        {
            return outcome::failure( Error::IdentityError );
        }

        if ( !EVP_DecryptInit_ex( ctx, EVP_aes_256_gcm(), nullptr, nullptr, nullptr ) )
        {
            EVP_CIPHER_CTX_free( ctx );
            return outcome::failure( Error::IdentityError );
        }

        if ( !EVP_CIPHER_CTX_ctrl( ctx, EVP_CTRL_GCM_SET_IVLEN, sizeof( iv ), nullptr ) )
        {
            EVP_CIPHER_CTX_free( ctx );
            return outcome::failure( Error::IdentityError );
        }

        if ( !EVP_DecryptInit_ex( ctx, nullptr, nullptr, key, iv ) )
        {
            EVP_CIPHER_CTX_free( ctx );
            return outcome::failure( Error::IdentityError );
        }

        std::vector<uint8_t> plaintext( ciphertextSize );
        int outLen = 0;
        if ( !EVP_DecryptUpdate( ctx, plaintext.data(), &outLen, ciphertext.data(),
                                 static_cast<int>( ciphertextSize ) ) )
        {
            EVP_CIPHER_CTX_free( ctx );
            return outcome::failure( Error::IdentityError );
        }
        int totalLen = outLen;

        // 8. Set expected GCM tag BEFORE Final
        if ( !EVP_CIPHER_CTX_ctrl( ctx, EVP_CTRL_GCM_SET_TAG, sizeof( tag ), const_cast<uint8_t*>( tag ) ) )
        {
            EVP_CIPHER_CTX_free( ctx );
            return outcome::failure( Error::IdentityError );
        }

        // 9. Finalize — this validates the GCM tag
        int ret = EVP_DecryptFinal_ex( ctx, plaintext.data() + totalLen, &outLen );
        EVP_CIPHER_CTX_free( ctx );

        if ( ret <= 0 )
        {
            // Tag verification failed — wrong passphrase or tampered file
            IdentityLogger()->error( "LoadEncrypted: decryption failed — wrong passphrase or corrupt file" );
            return outcome::failure( Error::IdentityError );
        }
        totalLen += outLen;
        plaintext.resize( totalLen );

        // 10. Copy decrypted key
        if ( plaintext.size() != kPrivKeySize )
        {
            return outcome::failure( Error::IdentityError );
        }
        std::memcpy( impl_->priv_key_.data(), plaintext.data(), kPrivKeySize );

        // 11. Derive public key from private key
#ifdef GENIUS_HAS_SECP256K1
        secp256k1_pubkey pubkey;
        (void)secp256k1_ec_pubkey_create( impl_->ctx_, &pubkey, impl_->priv_key_.data() );
        size_t pubLen = kPubKeySize;
        secp256k1_ec_pubkey_serialize( impl_->ctx_, pub_key_.data(), &pubLen, &pubkey, SECP256K1_EC_COMPRESSED );
#endif

        loaded_ = true;
        IdentityLogger()->info( "NodeIdentity loaded encrypted from {}", path );
        return outcome::success();
#else
        IdentityLogger()->error( "LoadEncrypted: OpenSSL not available" );
        return outcome::failure( Error::IdentityError );
#endif
    }

    // -----------------------------------------------------------------------
    // Sign
    // -----------------------------------------------------------------------
    outcome::result<std::vector<uint8_t>> NodeIdentity::Sign( const std::vector<uint8_t>& message ) const
    {
        if ( !loaded_ )
        {
            return outcome::failure( Error::IdentityError );
        }
#ifdef GENIUS_HAS_SECP256K1
        uint8_t hash[32];
#ifdef GENIUS_HAS_OPENSSL
        SHA256( message.data(), message.size(), hash );
#else
        std::fill( hash, hash + 32, 0 );
        for ( size_t i = 0; i < message.size(); ++i )
        {
            hash[i % 32] ^= message[i];
        }
#endif
        secp256k1_ecdsa_signature sig;
        if ( !secp256k1_ecdsa_sign( impl_->ctx_, &sig, hash, impl_->priv_key_.data(), secp256k1_nonce_function_rfc6979,
                                    nullptr ) )
        {
            return outcome::failure( Error::IdentityError );
        }
        std::vector<uint8_t> der( 72 );
        size_t der_len = 72;
        secp256k1_ecdsa_signature_serialize_der( impl_->ctx_, der.data(), &der_len, &sig );
        der.resize( der_len );
        return outcome::success( std::move( der ) );
#else
        std::vector<uint8_t> sig( 64, 0 );
        for ( size_t i = 0; i < message.size(); ++i )
        {
            sig[i % 64] ^= message[i];
        }
        return outcome::success( std::move( sig ) );
#endif
    }

    // -----------------------------------------------------------------------
    // Verify
    // -----------------------------------------------------------------------
    bool NodeIdentity::Verify( const std::vector<uint8_t>& message, const std::vector<uint8_t>& signature ) const
    {
        if ( !loaded_ )
        {
            return false;
        }
#ifdef GENIUS_HAS_SECP256K1
        uint8_t hash[32];
#ifdef GENIUS_HAS_OPENSSL
        SHA256( message.data(), message.size(), hash );
#else
        std::fill( hash, hash + 32, 0 );
        for ( size_t i = 0; i < message.size(); ++i )
        {
            hash[i % 32] ^= message[i];
        }
#endif
        secp256k1_ecdsa_signature sig;
        if ( !secp256k1_ecdsa_signature_parse_der( impl_->ctx_, &sig, signature.data(), signature.size() ) )
        {
            return false;
        }
        secp256k1_pubkey pubkey;
        if ( !secp256k1_ec_pubkey_parse( impl_->ctx_, &pubkey, pub_key_.data(), kPubKeySize ) )
        {
            return false;
        }
        return secp256k1_ecdsa_verify( impl_->ctx_, &sig, hash, &pubkey ) == 1;
#else
        (void) message;
        (void) signature;
        IdentityLogger()->error( "NodeIdentity::Verify — secp256k1 not compiled in, REJECTING signature" );
        return false;
#endif
    }

} // namespace sgns::neoswarm::security
