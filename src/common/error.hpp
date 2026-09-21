/**
 * @file       error.hpp
 * @brief      Error codes and outcome::result alias for GNUS NEO SWARM
 */

#ifndef NEOSWARM_COMMON_ERROR_HPP
#define NEOSWARM_COMMON_ERROR_HPP

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
        // Memory (Phase 8 — GAML v1 — per D-20)
        MemoryNotFound = 18,          ///< D-20: requested memory object not found
        MemoryUnavailable = 19,       ///< storage offline but not fatal
        MemoryIngestionFailed = 20,   ///< failed write evaluation
        // ELM (Phase 7 — fail-close when Process() called before Load())
        NotLoaded = 21,               ///< ELM/ engine not loaded — cannot process
        // GCS GlobalDB (Phase 3)
        GcsDbError = 22,              ///< GCS GlobalDB operation failed (init, start, topic wiring)
        SdkNotInitialized = 23,       ///< GeniusSDKGetNode() returned nullptr — SDK init chain has not run
    };

} // namespace sgns::neoswarm

// Register the error enum with Boost.Outcome so it can be used in outcome::result<>
OUTCOME_HPP_DECLARE_ERROR_2( sgns::neoswarm, Error )

#endif // NEOSWARM_COMMON_ERROR_HPP
