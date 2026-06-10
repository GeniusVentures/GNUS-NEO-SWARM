/**
 * @file       error.hpp
 * @brief      Error codes and outcome::result alias for GNUS NEO SWARM
 */

#ifndef NEOSWARM_COMMON_ERROR_HPP_
#define NEOSWARM_COMMON_ERROR_HPP_

#include <libp2p/outcome/outcome.hpp>

namespace sgns::neoswarm
{
    namespace outcome = libp2p::outcome;

    // -----------------------------------------------------------------------
    // Error codes
    // -----------------------------------------------------------------------
    enum class Error : uint8_t
    {
        // Core engine
        ModelLoadFailed = 1,
        InferenceFailed = 2,
        TokenizerFailed = 3,
        FP4DecodeFailed = 4,
        // Router
        RoutingFailed = 5,
        // Network
        NetworkError = 6,
        PeerNotFound = 7,
        BroadcastTimeout = 8,
        // Reputation
        StorageError = 9,
        ReputationNotFound = 10,
        // Knowledge
        KnowledgeUnavailable = 11,
        FactValidationFailed = 12,
        // Security
        IdentityError = 13,
        SignatureInvalid = 14,
        // General
        InvalidArgument = 15,
        NotImplemented = 16,
        InternalError = 17,
    };

} // namespace sgns::neoswarm

// Register the error enum with Boost.Outcome so it can be used in outcome::result<>
OUTCOME_HPP_DECLARE_ERROR_2( sgns::neoswarm, Error )

#endif // NEOSWARM_COMMON_ERROR_HPP_
