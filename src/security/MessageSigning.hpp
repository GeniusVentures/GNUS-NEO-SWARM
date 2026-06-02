/**
 * @file       MessageSigning.hpp
 * @brief      secp256k1 sign/verify for inter-node messages (PTDS §4.3)
 * @date       2026-05-08
 * @author     Subaskar S (ssivakumar@gnus.ai)
 */

#ifndef NEOSWARM_SECURITY_MESSAGESIGNING_HPP_
#define NEOSWARM_SECURITY_MESSAGESIGNING_HPP_

#include "NodeIdentity.hpp"
#include "common/Error.hpp"
#include <cstdint>
#include <string>
#include <vector>

namespace sgns::neoswarm::security
{
    /**
     * @brief Signs and verifies inter-node message payloads.
     */
    class MessageSigning
    {
    public:
        /**
         * @brief Construct with a reference to the local node identity.
         * @param identity  Node identity used for signing.
         */
        explicit MessageSigning( const NodeIdentity &identity );

        /**
         * @brief Sign a serialised message payload.
         * @param payload  UTF-8 payload string.
         * @return         DER-encoded signature bytes or IdentityError.
         */
        outcome::result<std::vector<uint8_t>> Sign( const std::string &payload ) const;

        /**
         * @brief Verify a signature against a known public key.
         * @param payload     Original payload string.
         * @param signature   DER-encoded signature bytes.
         * @param pub_key_hex Hex-encoded compressed public key of the signer.
         * @return            True if the signature is valid.
         */
        static bool Verify( const std::string          &payload,
                            const std::vector<uint8_t> &signature,
                            const std::string          &pub_key_hex );

        /// Replay protection window in seconds.
        static constexpr int64_t kReplayWindowSec = 30;

        /**
         * @brief Generate a cryptographically random nonce.
         * @return Hex-encoded 32-byte nonce.
         */
        static std::string GenerateNonce();

        /**
         * @brief Get current Unix timestamp in milliseconds.
         * @return Milliseconds since epoch.
         */
        static uint64_t CurrentTimestampMs();

        /**
         * @brief Attach a signature field to a JSON payload string.
         * @param payload  JSON object string (must end with '}').
         * @return         Payload with appended "sig" field.
         */
        std::string AttachSignature( const std::string &payload ) const;

        /**
         * @brief Verify and strip the signature field from a signed JSON payload.
         * @param[in,out] payload     On entry: signed JSON. On exit: payload without sig.
         * @param         pub_key_hex Hex-encoded public key of the expected signer.
         * @return                    True if the signature is valid.
         */
        static bool VerifyAndStrip( std::string &payload, const std::string &pub_key_hex );

    private:
        const NodeIdentity &identity_;
    };

} // namespace sgns::neoswarm::security

#endif // NEOSWARM_SECURITY_MESSAGESIGNING_HPP_
