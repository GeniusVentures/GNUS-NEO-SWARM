/**
 * @file       error.cpp
 * @brief      Boost.Outcome error category registration for GNUS NEO SWARM
 */

#include "error.hpp"

OUTCOME_CPP_DEFINE_CATEGORY_3( sgns::neoswarm, Error, e )
{
    using E = sgns::neoswarm::Error;
    switch ( e )
    {
        case E::ModelLoadFailed:
            return "Model load failed";
        case E::InferenceFailed:
            return "Inference failed";
        case E::TokenizerFailed:
            return "Tokenizer failed";
        case E::FP4DecodeFailed:
            return "FP4 decode failed";
        case E::RoutingFailed:
            return "Routing failed";
        case E::NetworkError:
            return "Network error";
        case E::PeerNotFound:
            return "Peer not found";
        case E::BroadcastTimeout:
            return "Broadcast timeout";
        case E::StorageError:
            return "Storage error";
        case E::ReputationNotFound:
            return "Reputation not found";
        case E::KnowledgeUnavailable:
            return "Knowledge unavailable";
        case E::FactValidationFailed:
            return "Fact validation failed";
        case E::IdentityError:
            return "Identity error";
        case E::SignatureInvalid:
            return "Signature invalid";
        case E::InvalidArgument:
            return "Invalid argument";
        case E::NotImplemented:
            return "Not implemented";
        case E::InternalError:
            return "Internal error";
        case E::MemoryNotFound:
            return "Memory object not found";
        case E::MemoryUnavailable:
            return "Memory storage unavailable";
        case E::MemoryIngestionFailed:
            return "Memory ingestion failed";
        case E::NotLoaded:
            return "ELM not loaded";
        case E::GcsDbError:
            return "GCS GlobalDB operation failed";
        case E::SdkNotInitialized:
            return "GeniusSDK not initialized";
    }
    return "Unknown error";
}
