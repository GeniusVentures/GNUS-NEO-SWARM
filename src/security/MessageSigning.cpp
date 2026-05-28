/**
 * @file       MessageSigning.cpp
 * @brief      Message signing implementation
 * @date       2026-05-08
 * @author     Subaskar S (ssivakumar@gnus.ai)
 */

#include "MessageSigning.hpp"
#include "common/Logging.hpp"

#include <iomanip>
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
        auto SigningLogger()
        {
            return neoswarm::CreateLogger( "MessageSigning" );
        }

        std::string ToHex( const std::vector<uint8_t> &data )
        {
            std::ostringstream oss;
            for ( auto b : data )
            {
                oss << std::hex << std::setw( 2 ) << std::setfill( '0' )
                    << static_cast<int>( b );
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

    MessageSigning::MessageSigning( const NodeIdentity &identity ) : identity_( identity ) {}

    // -----------------------------------------------------------------------
    // Sign
    // -----------------------------------------------------------------------
    outcome::result<std::vector<uint8_t>> MessageSigning::Sign( const std::string &payload ) const
    {
        std::vector<uint8_t> bytes( payload.begin(), payload.end() );
        return identity_.Sign( bytes );
    }

    // -----------------------------------------------------------------------
    // Verify
    // -----------------------------------------------------------------------
    bool MessageSigning::Verify( const std::string          &payload,
                                 const std::vector<uint8_t> &signature,
                                 const std::string          &pub_key_hex )
    {
#ifdef GENIUS_HAS_SECP256K1
        // Validate inputs
        if ( payload.empty() || signature.empty() || pub_key_hex.empty() )
        {
            return false;
        }

        // Parse public key from hex
        auto pubBytes = FromHex( pub_key_hex );
        if ( pubBytes.size() != NodeIdentity::kPubKeySize )
        {
            return false;
        }

        // Create verify-only secp256k1 context
        auto ctx = secp256k1_context_create( SECP256K1_CONTEXT_VERIFY );
        if ( !ctx )
        {
            SigningLogger()->error( "MessageSigning::Verify — failed to create secp256k1 context" );
            return false;
        }

        // Parse public key
        secp256k1_pubkey pubkey;
        if ( !secp256k1_ec_pubkey_parse( ctx, &pubkey, pubBytes.data(), pubBytes.size() ) )
        {
            secp256k1_context_destroy( ctx );
            return false;
        }

        // Parse DER signature
        secp256k1_ecdsa_signature sig;
        if ( !secp256k1_ecdsa_signature_parse_der( ctx, &sig,
                                                    signature.data(), signature.size() ) )
        {
            secp256k1_context_destroy( ctx );
            return false;
        }

        // Normalize to low-S to prevent signature malleability
        secp256k1_ecdsa_signature_normalize( ctx, nullptr, &sig );

        // Hash payload with SHA-256
        uint8_t hash[32];
#    ifdef GENIUS_HAS_OPENSSL
        SHA256( reinterpret_cast<const uint8_t *>( payload.data() ), payload.size(), hash );
#    else
        std::fill( hash, hash + 32, 0 );
        for ( size_t i = 0; i < payload.size(); ++i )
        {
            hash[i % 32] ^= static_cast<uint8_t>( payload[i] );
        }
#    endif

        // Verify
        int result = secp256k1_ecdsa_verify( ctx, &sig, hash, &pubkey );
        secp256k1_context_destroy( ctx );
        return result == 1;
#else
        ( void )payload;
        ( void )signature;
        ( void )pub_key_hex;
        SigningLogger()->error( "MessageSigning::Verify — secp256k1 not available, REJECTING signature" );
        return false;
#endif
    }

    // -----------------------------------------------------------------------
    // AttachSignature
    // -----------------------------------------------------------------------
    std::string MessageSigning::AttachSignature( const std::string &payload ) const
    {
        auto sig_res = Sign( payload );
        if ( !sig_res.has_value() )
        {
            SigningLogger()->warn( "MessageSigning: failed to sign payload" );
            return payload;
        }

        std::string result = payload;
        if ( !result.empty() && result.back() == '}' )
        {
            result.pop_back();
            result += ",\"sig\":\"" + ToHex( sig_res.value() ) + "\"}";
        }
        return result;
    }

    // -----------------------------------------------------------------------
    // VerifyAndStrip
    // -----------------------------------------------------------------------
    bool MessageSigning::VerifyAndStrip( std::string &payload, const std::string &pub_key_hex )
    {
        auto sig_pos = payload.rfind( ",\"sig\":\"" );
        if ( sig_pos == std::string::npos )
        {
            return false;
        }
        std::string original_payload = payload.substr( 0, sig_pos ) + "}";
        payload                      = original_payload;
        return Verify( original_payload, {}, pub_key_hex );
    }

} // namespace sgns::neoswarm::security
