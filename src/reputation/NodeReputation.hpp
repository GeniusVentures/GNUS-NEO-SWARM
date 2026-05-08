/**
 * @file       NodeReputation.hpp
 * @brief      Reputation helpers for GNUS NEO SWARM nodes
 * @date       2026-05-06
 * @author     Subaskar S (ssivakumar@gnus.ai)
 */

#ifndef NEOSWARM_REPUTATION_NODEREPUTATION_HPP_
#define NEOSWARM_REPUTATION_NODEREPUTATION_HPP_

#include "common/Types.hpp"
#include <algorithm>

namespace sgns::neoswarm::reputation
{
    using neoswarm::NodeReputation;

    /**
     * @brief Clamp a reputation score to [0.0, 1.0].
     * @param score  Raw score value.
     * @return       Clamped score.
     */
    inline double ClampScore( double score )
    {
        return std::max( 0.0, std::min( 1.0, score ) );
    }

    /**
     * @brief Check whether a node has enough history to be considered high-trust.
     * @param rep  Node reputation record.
     * @return     True if the node meets the high-trust threshold.
     */
    inline bool IsHighTrust( const NodeReputation &rep )
    {
        return rep.task_count_ >= NodeReputation::kMinTasksForHighTrust
               && rep.global_score_ >= 0.7;
    }

} // namespace sgns::neoswarm::reputation

#endif // NEOSWARM_REPUTATION_NODEREPUTATION_HPP_
