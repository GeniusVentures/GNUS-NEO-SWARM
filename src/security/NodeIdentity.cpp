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
#    include <secp256k1.h>
#endif

#ifdef GENIUS_HAS_OPENSSL
#    include <openssl/sha.h>
#endif

namespace sgns::neoswarm::security
{
    namespace
    {
        auto IdentityLogger()
        {
            return neoswarm::CreateLogger( "NodeIdentity" );
        }

        std::string ToHex( const uint8_t *data, size_t len )
        {
            std::ostringstream oss;
            for ( size_t i = 0; i < len; ++i )
            {
                oss << std::hex << std::setw( 2 ) << std::setfill( '0' )
                    << static_cast<int>( data[i] );
            }
            return oss.str();
        }

        std::vector<uint8_t> FromHex( const std::string &hex )
        {
            std::vector<uint8_t> bytes;
            for ( size_t i = 0; i + 1 < hex.size(); i += 2 )
            {
                bytes.push_back(
                    static_cast<uint8_t>( std::stoul( hex.substr( i, 2 ), nullptr, 16 ) ) );
            }
            return bytes;
        }
    }

    // -----------------------------------------------------------------------
    // Impl
    // -----------------------------------------------------------------------
    struct NodeIdentity::Impl
    {
        PrivKey priv_key_{};
#ifdef GENIUS_HAS_SECP256K1
        secp256k1_context *ctx_ = nullptr;
#endif
    };

    NodeIdentity::NodeIdentity() : impl_( std::make_unique<Impl>() )
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
        std::random_device                    rd;
        std::mt19937_64                       rng( rd() );
        std::uniform_int_distribution<uint8_t> dist( 0, 255 );

        for ( int attempt = 0; attempt < 100; ++attempt )
        {
            for ( auto &b : impl_->priv_key_ )
            {
                b = dist( rng );
            }
            if ( secp256k1_ec_seckey_verify( impl_->ctx_, impl_->priv_key_.data() ) )
            {
                secp256k1_pubkey pubkey;
                secp256k1_ec_pubkey_create( impl_->ctx_, &pubkey, impl_->priv_key_.data() );
                size_t pub_len = kPubKeySize;
                secp256k1_ec_pubkey_serialize( impl_->ctx_, pub_key_.data(), &pub_len,
                                               &pubkey, SECP256K1_EC_COMPRESSED );
                loaded_ = true;
                IdentityLogger()->info( "NodeIdentity generated: peerId={}", PeerId() );
                return outcome::success();
            }
        }
        return outcome::failure( Error::IdentityError );
#else
        std::random_device                    rd;
        std::mt19937_64                       rng( rd() );
        std::uniform_int_distribution<uint8_t> dist( 0, 255 );
        for ( auto &b : impl_->priv_key_ )
        {
            b = dist( rng );
        }
        for ( auto &b : pub_key_ )
        {
            b = dist( rng );
        }
        pub_key_[0] = 0x02;  // compressed prefix
        loaded_     = true;
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
    outcome::result<void> NodeIdentity::LoadFromFile( const std::string &path )
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
        secp256k1_ec_pubkey_create( impl_->ctx_, &pubkey, impl_->priv_key_.data() );
        size_t pub_len = kPubKeySize;
        secp256k1_ec_pubkey_serialize( impl_->ctx_, pub_key_.data(), &pub_len,
                                       &pubkey, SECP256K1_EC_COMPRESSED );
#endif
        loaded_ = true;
        return outcome::success();
    }

    // -----------------------------------------------------------------------
    // SaveToFile
    // -----------------------------------------------------------------------
    outcome::result<void> NodeIdentity::SaveToFile( const std::string &path ) const
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
    // Sign
    // -----------------------------------------------------------------------
    outcome::result<std::vector<uint8_t>> NodeIdentity::Sign(
        const std::vector<uint8_t> &message ) const
    {
        if ( !loaded_ )
        {
            return outcome::failure( Error::IdentityError );
        }
#ifdef GENIUS_HAS_SECP256K1
        uint8_t hash[32];
#    ifdef GENIUS_HAS_OPENSSL
        SHA256( message.data(), message.size(), hash );
#    else
        std::fill( hash, hash + 32, 0 );
        for ( size_t i = 0; i < message.size(); ++i )
        {
            hash[i % 32] ^= message[i];
        }
#    endif
        secp256k1_ecdsa_signature sig;
        if ( !secp256k1_ecdsa_sign( impl_->ctx_, &sig, hash,
                                    impl_->priv_key_.data(), nullptr, nullptr ) )
        {
            return outcome::failure( Error::IdentityError );
        }
        std::vector<uint8_t> der( 72 );
        size_t               der_len = 72;
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
    bool NodeIdentity::Verify( const std::vector<uint8_t> &message,
                               const std::vector<uint8_t> &signature ) const
    {
        if ( !loaded_ )
        {
            return false;
        }
#ifdef GENIUS_HAS_SECP256K1
        uint8_t hash[32];
#    ifdef GENIUS_HAS_OPENSSL
        SHA256( message.data(), message.size(), hash );
#    else
        std::fill( hash, hash + 32, 0 );
        for ( size_t i = 0; i < message.size(); ++i )
        {
            hash[i % 32] ^= message[i];
        }
#    endif
        secp256k1_ecdsa_signature sig;
        if ( !secp256k1_ecdsa_signature_parse_der( impl_->ctx_, &sig,
                                                   signature.data(), signature.size() ) )
        {
            return false;
        }
        secp256k1_pubkey pubkey;
        if ( !secp256k1_ec_pubkey_parse( impl_->ctx_, &pubkey,
                                         pub_key_.data(), kPubKeySize ) )
        {
            return false;
        }
        return secp256k1_ecdsa_verify( impl_->ctx_, &sig, hash, &pubkey ) == 1;
#else
        ( void )message;
        ( void )signature;
        IdentityLogger()->warn( "NodeIdentity::Verify — stub, signature not checked" );
        return true;
#endif
    }

} // namespace sgns::neoswarm::security
