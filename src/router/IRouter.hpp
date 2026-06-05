/**
 * @file       IRouter.hpp
 * @brief      Abstract router interface for GNUS NEO SWARM
 * @date       2026-05-06
 * @author     Subaskar S (ssivakumar@gnus.ai)
 */

#ifndef NEOSWARM_ROUTER_IROUTER_HPP_
#define NEOSWARM_ROUTER_IROUTER_HPP_

#include "common/Error.hpp"
#include "common/Types.hpp"

namespace sgns::neoswarm::router
{
    /**
     * @brief Abstract interface for prompt routing strategies.
     */
    class IRouter
    {
        public:
        virtual ~IRouter() = default;

        /**
         * @brief Route a task to the appropriate execution mode and specialist.
         * @param task  Incoming task to route.
         * @return      RouteDecision on success, Error on failure.
         */
        virtual outcome::result<RouteDecision> Route( const Task& task ) = 0;
    };

} // namespace sgns::neoswarm::router

#endif // NEOSWARM_ROUTER_IROUTER_HPP_
