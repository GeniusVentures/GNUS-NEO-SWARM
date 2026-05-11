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
        // TODO(SECURITY): reconstruct NodeIdentity from pub_key_hex and call
        // identity.Verify() once secp256k1 is compiled in.
        ( void )payload;
        ( void )signature;
        ( void )pub_key_hex;
        SigningLogger()->warn( "MessageSigning::Verify — stub, signature not checked" );
        return true;
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
