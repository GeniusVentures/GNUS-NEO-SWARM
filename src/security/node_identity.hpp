/**
 * @file       node_identity.hpp
 * @brief      secp256k1 keypair and PeerId derivation (PTDS §4.3)
 * @date       2026-05-08
 * @author     Subaskar S (ssivakumar@gnus.ai)
 */

#ifndef NEOSWARM_SECURITY_NODEIDENTITY_HPP_
#define NEOSWARM_SECURITY_NODEIDENTITY_HPP_

#include "common/error.hpp"
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
        static constexpr size_t kPubKeySize = 33; ///< compressed
        static constexpr size_t kPeerIdSize = 32;

        using PrivKey = std::array<uint8_t, kPrivKeySize>;
        using PubKey = std::array<uint8_t, kPubKeySize>;

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
        outcome::result<void> LoadFromFile( const std::string& path );

        /**
         * @brief Save the current keypair to a hex file.
         * @param path  Destination file path.
         * @return      outcome::success or IdentityError.
         */
        outcome::result<void> SaveToFile( const std::string& path ) const;

        /**
         * @brief Save the current keypair encrypted with AES-256-GCM.
         *
         * Derives a 256-bit encryption key from @p passphrase using
         * PBKDF2-HMAC-SHA256 (600,000 iterations) with a random salt.
         * The key is encrypted and written in a self-describing binary
         * format: [4-byte salt length][salt][12-byte IV][ciphertext][16-byte GCM tag].
         *
         * @param path        Destination file path (typically "node.key").
         * @param passphrase  User-supplied encryption passphrase.
         * @return            outcome::success or IdentityError.
         */
        outcome::result<void> SaveEncrypted( const std::string& path, const std::string& passphrase ) const;

        /**
         * @brief Load an encrypted keypair and decrypt it.
         *
         * Reads the binary format written by SaveEncrypted, derives the
         * decryption key from @p passphrase, decrypts, and verifies the
         * GCM authentication tag. If the tag does not match (wrong
         * passphrase or tampered file), returns IdentityError.
         *
         * On success, the public key is derived and PeerId is available.
         *
         * @param path        Path to the encrypted key file.
         * @param passphrase  Decryption passphrase.
         * @return            outcome::success or IdentityError.
         */
        outcome::result<void> LoadEncrypted( const std::string& path, const std::string& passphrase );

        /**
         * @brief Derive the PeerId string from the public key.
         * @return  Hex-encoded SHA-256 of the compressed public key.
         */
        std::string PeerId() const;

        /// @return The compressed public key bytes.
        const PubKey& PublicKey() const
        {
            return m_pubKey;
        }

        /// @return True if a keypair has been loaded or generated.
        bool IsLoaded() const
        {
            return m_loaded;
        }

        /**
         * @brief Sign a message with the node's private key.
         * @param message  Raw bytes to sign.
         * @return         DER-encoded signature or IdentityError.
         */
        outcome::result<std::vector<uint8_t>> Sign( const std::vector<uint8_t>& message ) const;

        /**
         * @brief Verify a signature against this node's public key.
         * @param message    Original message bytes.
         * @param signature  DER-encoded signature to verify.
         * @return           True if the signature is valid.
         */
        bool Verify( const std::vector<uint8_t>& message, const std::vector<uint8_t>& signature ) const;

        private:
        struct Impl;
        std::unique_ptr<Impl> m_impl;
        PubKey m_pubKey{};
        bool m_loaded = false;
    };

} // namespace sgns::neoswarm::security

#endif // NEOSWARM_SECURITY_NODEIDENTITY_HPP_
