/**
 * @file       SGMessageAuthenticator.cpp
 * @brief      Signs and verifies messages via hardened NodeIdentity + MessageSigning
 * @date       2026-05-28
 * @author     Subaskar S (ssivakumar@gnus.ai)
 */

#include "SGMessageAuthenticator.hpp"
#include "security/NodeIdentity.hpp"
#include "security/MessageSigning.hpp"
#include "common/Logging.hpp"

namespace sgns::neoswarm::network
{
    namespace
    {
        auto AuthLogger()
        {
            return CreateLogger( "NeoSwarm/SGAuth" );
        }
    }

    struct SGMessageAuthenticator::Impl
    {
        const security::NodeIdentity &identity_;
        std::unique_ptr<security::MessageSigning> signer_;

        explicit Impl( const security::NodeIdentity &identity )
            : identity_( identity )
            , signer_( std::make_unique<security::MessageSigning>( identity ) )
        {
        }
    };

    SGMessageAuthenticator::SGMessageAuthenticator(
        const security::NodeIdentity &identity )
        : impl_( std::make_unique<Impl>( identity ) )
    {
        AuthLogger()->debug( "SGMessageAuthenticator created" );
    }

    outcome::result<std::string> SGMessageAuthenticator::SignPayload(
        const std::string &payload ) const
    {
        if ( !impl_->identity_.IsLoaded() )
        {
            AuthLogger()->error( "Cannot sign — NodeIdentity not loaded" );
            return outcome::failure( Error::IdentityError );
        }

        std::string signedPayload = impl_->signer_->AttachSignature( payload );

        AuthLogger()->debug( "Payload signed ({} bytes → {} bytes)",
                             payload.size(), signedPayload.size() );
        return signedPayload;
    }

    outcome::result<bool> SGMessageAuthenticator::VerifyResult(
        std::string       &payload,
        const std::string &pubKeyHex ) const
    {
        bool valid = security::MessageSigning::VerifyAndStrip( payload, pubKeyHex );

        if ( !valid )
        {
            AuthLogger()->warn( "Result verification FAILED for key {}", pubKeyHex.substr( 0, 16 ) );
            return false;
        }

        AuthLogger()->debug( "Result verified successfully" );
        return true;
    }

} // namespace sgns::neoswarm::network
