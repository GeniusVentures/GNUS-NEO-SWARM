/**
 * @file       sg_message_authenticator.hpp
 * @brief      Signs and verifies messages using the node's secp256k1 identity
 * @date       2026-05-28
 * @author     Subaskar S (ssivakumar@gnus.ai)
 */

#ifndef NEOSWARM_NETWORK_SG_CLIENT_SGMESSAGEAUTHENTICATOR_HPP_
#define NEOSWARM_NETWORK_SG_CLIENT_SGMESSAGEAUTHENTICATOR_HPP_

#include "common/error.hpp"
#include <memory>
#include <string>
#include <vector>

namespace sgns::neoswarm::security
{
    class NodeIdentity;
}

namespace sgns::neoswarm::network
{
    /**
     * @brief Wraps NodeIdentity and MessageSigning for SuperGenius dispatch.
     *
     * Signs every outgoing Task payload with the node's secp256k1 identity
     * (including nonce + timestamp for replay protection) and verifies
     * incoming result signatures before accepting them.
     */
    class SGMessageAuthenticator
    {
        public:
        /**
         * @brief Construct with the node's cryptographic identity.
         * @param identity The node's secp256k1 identity (from Phase 1).
         */
        explicit SGMessageAuthenticator( const security::NodeIdentity& identity );

        ~SGMessageAuthenticator();

        /**
         * @brief Sign a JSON payload with nonce + timestamp replays protection.
         * @param payload  The raw JSON payload to sign.
         * @return         The signed payload (JSON with attached signature fields).
         */
        outcome::result<std::string> SignPayload( const std::string& payload ) const;

        /**
         * @brief Verify a signed result and strip authentication fields.
         * @param payload      The signed payload (modified in-place).
         * @param pubKeyHex    The expected signer's public key as hex.
         * @return             true if signature is valid and replay-check passes.
         */
        outcome::result<bool> VerifyResult( std::string& payload, const std::string& pubKeyHex ) const;

        private:
        struct Impl;
        std::unique_ptr<Impl> m_impl;
    };

} // namespace sgns::neoswarm::network

#endif // NEOSWARM_NETWORK_SG_CLIENT_SGMESSAGEAUTHENTICATOR_HPP_
