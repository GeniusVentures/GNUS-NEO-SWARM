/**
 * @file       super_genius_client.hpp
 * @brief      Client for SuperGenius blockchain compute network dispatch via GeniusSDK
 * @date       2026-05-28
 *
 * GeniusSDK runs in-process via direct linking — every swarm node has the SDK
 * compiled in. No remote endpoint, no gRPC channel management. Initialize() starts
 * the SDK node; SubmitJob() dispatches through GeniusSDKProcess(); Disconnect()
 * calls GeniusSDKShutdown().
 *
 * SDK identity is managed internally — GeniusSDKInit() generates its own keypair.
 * NEO-SWARM does NOT derive SDK keys from NodeIdentity (they serve different purposes:
 * NodeIdentity = P2P swarm identity, SDK identity = blockchain node identity).
 */

#ifndef NEOSWARM_NETWORK_SG_CLIENT_SUPERGENIUSCLIENT_HPP
#define NEOSWARM_NETWORK_SG_CLIENT_SUPERGENIUSCLIENT_HPP

#include "common/error.hpp"
#include "account/TokenID.hpp"
#include <chrono>
#include <cstdint>
#include <memory>
#include <string>
#include <vector>

namespace sgns::neoswarm::network
{
    /**
     * @brief Runtime configuration values used to bootstrap a Genius node instance.
     *
     * Lightweight mirror of sgns::GeniusNodeConfig (SuperGenius GeniusNode.hpp)
     * so SGClient consumers don't pull in the full node header chain.
     */
    struct GeniusNodeConfig
    {
        std::string   Addr;             ///< Developer payout address.
        std::string   Cut;              ///< Developer or peer cut encoded as a string.
        std::string   TokenValueInGNUS; ///< Conversion rate used for child-token.
        // Default TokenID{} is intentionally all-zero = the GNUS token.
        // ToHex() emits 64 zeros, which GeniusSDK's ParseDevConfig accepts and
        // IsGNUS() reports as the GNUS token (IN-02).
        sgns::TokenID TokenID;          ///< Child token identifier (default = GNUS token).
        std::string   BaseWritePath;    ///< Base directory for node databases, logs, and account storage.
    };

    // Dev-config defaults — match GeniusSDK/example/dev_config.json (WR-01).
    // kDefaultDevAddr is a placeholder only; a production deployment MUST
    // override it with a real payout address ("0x" + 40 hex chars).
    inline constexpr const char* kDefaultDevAddr       = "0xcafe";
    inline constexpr const char* kDefaultDevCut        = "0.65";
    inline constexpr const char* kDefaultDevTokenValue = "1.0";
    inline constexpr unsigned int kDefaultResultTimeoutSeconds = 300; ///< 5 minutes (WR-02)

    class SGClient
    {
        public:
        struct Config
        {
            GeniusNodeConfig m_geniusNodeConfig{ kDefaultDevAddr, kDefaultDevCut, kDefaultDevTokenValue,
                                                 sgns::TokenID{}, "./sdk" };
            std::chrono::seconds m_resultTimeout{ kDefaultResultTimeoutSeconds };   ///< Inference result timeout
        };

        explicit SGClient( Config cfg );
        ~SGClient();

        SGClient( const SGClient& ) = delete;
        SGClient& operator=( const SGClient& ) = delete;
        SGClient( SGClient&& ) noexcept;
        SGClient& operator=( SGClient&& ) noexcept;

        /**
         * @brief Initialize the GeniusSDK node in-process.
         *
         * Calls GeniusSDKInit() — the SDK generates its own keypair internally
         * for blockchain identity. NEO-SWARM's NodeIdentity is separate (swarm P2P).
         * After this, SubmitJob() can dispatch via GeniusSDKProcess().
         *
         * @return outcome::success or error.
         */
        outcome::result<void> Initialize();

        /**
         * @brief Submit a GNUS schema JSON job and wait for the result.
         *
         * Passes the raw GNUS schema JSON directly to GeniusSDKProcess().
         * The SDK handles auth internally via its own identity.
         *
         * @param gnusSchemaJson  The GNUS_Schema JSON from BuildSchemaJson().
         * @return                Raw output bytes or error.
         */
        outcome::result<std::vector<uint8_t>> SubmitJob( const std::string& gnusSchemaJson );

        /**
         * @brief Shut down the GeniusSDK node and release resources.
         *
         * Calls GeniusSDKShutdown() to tear down the in-process node.
         */
        void Disconnect();

        /**
         * @brief Check whether the SDK node is ready.
         * @return true if GeniusSDKGetNodeState() == GENIUS_NODE_READY.
         */
        bool IsConnected() const noexcept;

        private:
        struct Impl;
        std::unique_ptr<Impl> m_impl;
    };

} // namespace sgns::neoswarm::network

#endif // NEOSWARM_NETWORK_SG_CLIENT_SUPERGENIUSCLIENT_HPP