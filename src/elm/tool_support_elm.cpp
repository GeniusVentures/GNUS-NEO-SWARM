/**
 * @file       tool_support_elm.cpp
 * @brief      ToolSupportELM implementation — pass-through stub with logged not-implemented
 * @date       2026-07-17
 */

#include "tool_support_elm.hpp"
#include "common/logging.hpp"

namespace sgns::neoswarm::elm
{
    namespace
    {
        auto ToolLogger()
        {
            return neoswarm::CreateLogger( "ToolSupportELM" );
        }
    } // namespace

    outcome::result<void> ToolSupportELM::Load( const std::string& /*model_path*/ )
    {
        ToolLogger()->info( "ToolSupportELM — stub, no model to load" );
        return outcome::success();
    }

    outcome::result<std::string> ToolSupportELM::Process( const std::string& input, const ELMContext& /*ctx*/ )
    {
        ToolLogger()->warn( "ToolSupportELM not implemented — returning input unchanged" );
        m_lastConfidence = 0.0f;
        return outcome::success( input );
    }

} // namespace sgns::neoswarm::elm
