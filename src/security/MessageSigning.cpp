/**
 * @file       MessageSigning.cpp
 * @brief      Message signing implementation
 * @date       2026-05-08
 * @author     Subaskar S (ssivakumar@gnus.ai)
 */

#include "MessageSigning.hpp"
#include "common/Logging.hpp"

#include <chrono>
#include <iomanip>
#include <random>
#include <sstream>

#ifdef GENIUS_HAS_SECP256K1
#include <secp256k1.h>
#endif
#ifdef GENIUS_HAS_OPENSSL
#include <openssl/sha.h>
#endif

namespace sgns::neoswarm::security
{
    namespace
    {
        auto SigningLogger()
        {
            return neoswarm::CreateLogger( "MessageSigning" );
        }

        std::string ToHex( const std::vector<uint8_t>& data )
        {
            std::ostringstream oss;
            for ( auto b : data )
            {
                oss << std::hex << std::setw( 2 ) << std::setfill( '0' ) << static_cast<int>( b );
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

    MessageSigning::MessageSigning( const NodeIdentity& identity )
        : identity_( identity )
    {
    }

    // -----------------------------------------------------------------------
    // Sign
    // -----------------------------------------------------------------------
    outcome::result<std::vector<uint8_t>> MessageSigning::Sign( const std::string& payload ) const
    {
        std::vector<uint8_t> bytes( payload.begin(), payload.end() );
        return identity_.Sign( bytes );
    }

    // -----------------------------------------------------------------------
    // Verify
    // -----------------------------------------------------------------------
    bool MessageSigning::Verify( const std::string& payload,
                                 const std::vector<uint8_t>& signature,
                                 const std::string& pubKeyHex )
    {
#ifdef GENIUS_HAS_SECP256K1
        // Validate inputs
        if ( payload.empty() || signature.empty() || pubKeyHex.empty() )
        {
            return false;
        }

        // Parse public key from hex
        auto pubBytes = FromHex( pubKeyHex );
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
        if ( !secp256k1_ecdsa_signature_parse_der( ctx, &sig, signature.data(), signature.size() ) )
        {
            secp256k1_context_destroy( ctx );
            return false;
        }

        // Normalize to low-S to prevent signature malleability
        secp256k1_ecdsa_signature_normalize( ctx, nullptr, &sig );

        // Hash payload with SHA-256
        uint8_t hash[32];
#ifdef GENIUS_HAS_OPENSSL
        SHA256( reinterpret_cast<const uint8_t*>( payload.data() ), payload.size(), hash );
#else
        std::fill( hash, hash + 32, 0 );
        for ( size_t i = 0; i < payload.size(); ++i )
        {
            hash[i % 32] ^= static_cast<uint8_t>( payload[i] );
        }
#endif

        // Verify
        int result = secp256k1_ecdsa_verify( ctx, &sig, hash, &pubkey );
        secp256k1_context_destroy( ctx );
        return result == 1;
#else
        (void) payload;
        (void) signature;
        (void) pubKeyHex;
        SigningLogger()->error( "MessageSigning::Verify — secp256k1 not available, REJECTING signature" );
        return false;
#endif
    }

    // -----------------------------------------------------------------------
    // GenerateNonce / CurrentTimestampMs
    // -----------------------------------------------------------------------
    std::string MessageSigning::GenerateNonce()
    {
        std::random_device rd;
        std::mt19937_64 rng( rd() );
        std::uniform_int_distribution<uint8_t> dist( 0, 255 );
        std::vector<uint8_t> nonceBytes( 32 );
        for ( auto& b : nonceBytes )
        {
            b = dist( rng );
        }
        return ToHex( nonceBytes );
    }

    uint64_t MessageSigning::CurrentTimestampMs()
    {
        auto now = std::chrono::system_clock::now();
        return static_cast<uint64_t>(
            std::chrono::duration_cast<std::chrono::milliseconds>( now.time_since_epoch() ).count() );
    }

    // -----------------------------------------------------------------------
    // AttachSignature
    // -----------------------------------------------------------------------
    std::string MessageSigning::AttachSignature( const std::string& payload ) const
    {
        // Generate nonce and timestamp
        const std::string nonce = GenerateNonce();
        const uint64_t ts = CurrentTimestampMs();

        // Build signed payload: inject nonce + ts into JSON before signing
        std::string signedPayload = payload;
        if ( !signedPayload.empty() && signedPayload.back() == '}' )
        {
            signedPayload.pop_back();
            signedPayload += ",\"nonce\":\"" + nonce + "\"";
            signedPayload += ",\"ts\":" + std::to_string( ts );
            signedPayload += "}";
        }

        // Sign the payload WITH nonce+ts included
        auto sig_res = Sign( signedPayload );
        if ( !sig_res.has_value() )
        {
            SigningLogger()->warn( "MessageSigning: failed to sign payload" );
            return payload;
        }

        // Append signature field
        std::string result = signedPayload;
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
    bool MessageSigning::VerifyAndStrip( std::string& payload, const std::string& pubKeyHex )
    {
        // Step 1: Extract sig field (last field appended by AttachSignature)
        auto sigPos = payload.rfind( ",\"sig\":\"" );
        if ( sigPos == std::string::npos )
        {
            return false;
        }
        auto sigStart = sigPos + 8; // strlen(",\"sig\":\"")
        auto sigEnd = payload.find( "\"", sigStart );
        if ( sigEnd == std::string::npos )
        {
            return false;
        }
        auto sigBytes = FromHex( payload.substr( sigStart, sigEnd - sigStart ) );
        if ( sigBytes.empty() )
        {
            return false;
        }

        // Step 2: Build the verify payload (everything before ",sig" + "}")
        std::string verifyPayload = payload.substr( 0, sigPos ) + "}";

        // Step 3: Extract ts from verifyPayload
        auto tsPos = verifyPayload.rfind( ",\"ts\":" );
        if ( tsPos == std::string::npos )
        {
            SigningLogger()->warn( "MessageSigning: missing timestamp in signed payload" );
            return false;
        }
        auto tsStart = tsPos + 6; // strlen(",\"ts\":")
        auto tsEnd = verifyPayload.find_first_of( ",}", tsStart );
        uint64_t msgTs = 0;
        try
        {
            msgTs = std::stoull( verifyPayload.substr( tsStart, tsEnd - tsStart ) );
        }
        catch ( ... )
        {
            return false;
        }

        // Step 4: Validate replay window
        uint64_t nowMs = CurrentTimestampMs();
        int64_t ageMs = static_cast<int64_t>( nowMs - msgTs );
        if ( ageMs < 0 || ageMs > ( kReplayWindowSec * 1000 ) )
        {
            SigningLogger()->warn( "MessageSigning: replay detected — message age {}ms exceeds {}s window", ageMs,
                                   kReplayWindowSec );
            return false;
        }

        // Step 5: Verify signature on the full payload (includes nonce+ts)
        if ( !Verify( verifyPayload, sigBytes, pubKeyHex ) )
        {
            return false;
        }

        // Step 6: Strip injected fields to recover original payload
        // Remove ",sig":"<hex>" (keep trailing '}')
        payload.erase( sigPos, sigEnd - sigPos + 1 ); // +1 to include closing '"'

        // Remove ",ts":<num>
        tsPos = payload.rfind( ",\"ts\":" );
        if ( tsPos != std::string::npos )
        {
            auto tsEnd2 = payload.find_first_of( ",}", tsPos + 6 );
            payload.erase( tsPos, tsEnd2 - tsPos );
        }

        // Remove ",nonce":"<hex>"
        auto noncePos = payload.rfind( ",\"nonce\":\"" );
        if ( noncePos != std::string::npos )
        {
            auto nonceEnd = payload.find( "\"", noncePos + 10 );
            payload.erase( noncePos, nonceEnd - noncePos + 1 );
        }

        return true;
    }

} // namespace sgns::neoswarm::security
