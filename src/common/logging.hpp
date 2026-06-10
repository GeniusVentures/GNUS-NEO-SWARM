/**
 * @file       Logging.hpp
 * @brief      Logging facade — wraps spdlog directly
 */

#ifndef NEOSWARM_COMMON_LOGGING_HPP_
#define NEOSWARM_COMMON_LOGGING_HPP_

#include <memory>
#include <spdlog/sinks/stdout_color_sinks.h>
#include <spdlog/spdlog.h>
#include <string>

namespace sgns::neoswarm
{
    /// Logger sgns::base::Logger convention
    using Logger = std::shared_ptr<spdlog::logger>;

    /**
     * @brief Create a named logger for a NEO SWARM component.
     *
     * @param tag  Component name shown in log output (e.g. "Router", "P2PNode").
     * @return     Logger instance.
     */
    inline Logger CreateLogger( const std::string& tag )
    {
        const std::string name = "NeoSwarm/" + tag;
        auto existing = spdlog::get( name );
        if ( existing )
        {
            return existing;
        }
        auto logger = spdlog::stdout_color_mt( name );
        logger->set_pattern( "[%Y-%m-%d %H:%M:%S.%e] [%^%l%$] [%n] %v" );
        return logger;
    }

} // namespace sgns::neoswarm

#endif // NEOSWARM_COMMON_LOGGING_HPP_
