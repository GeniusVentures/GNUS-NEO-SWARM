/**
 * @file       Error.hpp
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
        MODEL_LOAD_FAILED = 1,
        INFERENCE_FAILED = 2,
        TOKENIZER_FAILED = 3,
        FP4_DECODE_FAILED = 4,
        ROUTING_FAILED = 5,
        NETWORK_ERROR = 6,
        PEER_NOT_FOUND = 7,
        BROADCAST_TIMEOUT = 8,
        STORAGE_ERROR = 9,
        REPUTATION_NOT_FOUND = 10,
        KNOWLEDGE_UNAVAILABLE = 11,
        FACT_VALIDATION_FAILED = 12,
        IDENTITY_ERROR = 13,
        SIGNATURE_INVALID = 14,
        INVALID_ARGUMENT = 15,
        NOT_IMPLEMENTED = 16,
        INTERNAL_ERROR = 17,
    };

} // namespace sgns::neoswarm

// Register the error enum with Boost.Outcome so it can be used in outcome::result<>
OUTCOME_HPP_DECLARE_ERROR_2( sgns::neoswarm, Error )

#endif // NEOSWARM_COMMON_ERROR_HPP_
