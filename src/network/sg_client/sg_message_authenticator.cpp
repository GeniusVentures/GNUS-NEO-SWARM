/**
 * @file       sg_message_authenticator.cpp
 * @brief      Signs and verifies messages via hardened NodeIdentity + MessageSigning
 * @date       2026-05-28
 */

#include "sg_message_authenticator.hpp"
#include "common/logging.hpp"
#include "security/message_signing.hpp"
#include "security/node_identity.hpp"

namespace sgns::neoswarm::network
{
    namespace
    {
        auto AuthLogger()
        {
            return CreateLogger( "NeoSwarm/SGAuth" );
        }
    } // namespace

    struct SGMessageAuthenticator::Impl
    {
        const security::NodeIdentity& m_identity;
        std::unique_ptr<security::MessageSigning> signer_;

        explicit Impl( const security::NodeIdentity& identity )
            : m_identity( identity )
            , signer_( std::make_unique<security::MessageSigning>( identity ) )
        {
        }
    };

    SGMessageAuthenticator::SGMessageAuthenticator( const security::NodeIdentity& identity )
        : m_impl( std::make_unique<Impl>( identity ) )
    {
        AuthLogger()->debug( "SGMessageAuthenticator created" );
    }

    outcome::result<std::string> SGMessageAuthenticator::SignPayload( const std::string& payload ) const
    {
        if ( !m_impl->m_identity.IsLoaded() )
        {
            AuthLogger()->error( "Cannot sign — NodeIdentity not loaded" );
            return outcome::failure( Error::IdentityError );
        }

        std::string signedPayload = m_impl->signer_->AttachSignature( payload );

        AuthLogger()->debug( "Payload signed ({} bytes → {} bytes)", payload.size(), signedPayload.size() );
        return signedPayload;
    }

    outcome::result<bool> SGMessageAuthenticator::VerifyResult( std::string& payload,
                                                                const std::string& pubKeyHex ) const
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

    SGMessageAuthenticator::~SGMessageAuthenticator() = default;

} // namespace sgns::neoswarm::network
