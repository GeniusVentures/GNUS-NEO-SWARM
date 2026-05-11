/**
 * @file       NodeIdentity.hpp
 * @brief      secp256k1 keypair and PeerId derivation (PTDS §4.3)
 * @date       2026-05-08
 * @author     Subaskar S (ssivakumar@gnus.ai)
 */

#ifndef NEOSWARM_SECURITY_NODEIDENTITY_HPP_
#define NEOSWARM_SECURITY_NODEIDENTITY_HPP_

#include "common/Error.hpp"
#include <array>
#include <memory>
#include <string>
#include <vector>

namespace sgns::neoswarm::security
{
    /**
     * @brief Manages a secp256k1 keypair and derives the node's PeerId.
     *
     * PeerId = hex( SHA-256( compressed_public_key ) )
     */
    class NodeIdentity
    {
    public:
        static constexpr size_t kPrivKeySize = 32;
        static constexpr size_t kPubKeySize  = 33;  ///< compressed
        static constexpr size_t kPeerIdSize  = 32;

        using PrivKey = std::array<uint8_t, kPrivKeySize>;
        using PubKey  = std::array<uint8_t, kPubKeySize>;

        NodeIdentity();
        ~NodeIdentity();

        /**
         * @brief Generate a new random secp256k1 keypair.
         * @return outcome::success or IdentityError.
         */
        outcome::result<void> Generate();

        /**
         * @brief Load a keypair from a hex file.
         * @param path  Path to the key file.
         * @return      outcome::success or IdentityError.
         */
        outcome::result<void> LoadFromFile( const std::string &path );

        /**
         * @brief Save the current keypair to a hex file.
         * @param path  Destination file path.
         * @return      outcome::success or IdentityError.
         */
        outcome::result<void> SaveToFile( const std::string &path ) const;

        /**
         * @brief Derive the PeerId string from the public key.
         * @return  Hex-encoded SHA-256 of the compressed public key.
         */
        std::string PeerId() const;

        /// @return The compressed public key bytes.
        const PubKey &PublicKey() const
        {
            return pub_key_;
        }

        /// @return True if a keypair has been loaded or generated.
        bool IsLoaded() const
        {
            return loaded_;
        }

        /**
         * @brief Sign a message with the node's private key.
         * @param message  Raw bytes to sign.
         * @return         DER-encoded signature or IdentityError.
         */
        outcome::result<std::vector<uint8_t>> Sign( const std::vector<uint8_t> &message ) const;

        /**
         * @brief Verify a signature against this node's public key.
         * @param message    Original message bytes.
         * @param signature  DER-encoded signature to verify.
         * @return           True if the signature is valid.
         */
        bool Verify( const std::vector<uint8_t> &message,
                     const std::vector<uint8_t> &signature ) const;

    private:
        struct Impl;
        std::unique_ptr<Impl> impl_;
        PubKey                pub_key_{};
        bool                  loaded_ = false;
    };

} // namespace sgns::neoswarm::security

#endif // NEOSWARM_SECURITY_NODEIDENTITY_HPP_
