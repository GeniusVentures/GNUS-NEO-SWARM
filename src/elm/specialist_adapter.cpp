/**
 * @file       specialist_adapter.cpp
 * @brief      SpecialistAdapter implementation — delegates to ISpecialist via composition
 * @date       2026-07-17
 */

#include "specialist_adapter.hpp"
#include "common/logging.hpp"

namespace sgns::neoswarm::elm
{
    namespace
    {
        auto SpecialistLogger()
        {
            return neoswarm::CreateLogger( "SpecialistAdapter" );
        }
    } // namespace

    SpecialistAdapter::SpecialistAdapter( std::shared_ptr<specialists::ISpecialist> specialist,
                                          ELMRole role,
                                          const std::string& name )
        : m_specialist( std::move( specialist ) )
        , m_role( role )
        , m_name( name )
    {
    }

    outcome::result<void> SpecialistAdapter::Load( const std::string& model_path )
    {
        if ( !m_specialist )
        {
            return outcome::failure( Error::ModelLoadFailed );
        }
        return m_specialist->Load( model_path );
    }

    outcome::result<std::string> SpecialistAdapter::Process( const std::string& input, const ELMContext& /*ctx*/ )
    {
        if ( !m_specialist )
        {
            m_lastConfidence = 0.0f;
            return input;  // fail-close per CONTEXT D-04: return input unchanged on error
        }
        auto result = m_specialist->Process( input );
        if ( result.has_value() )
        {
            m_lastConfidence = m_specialist->GetConfidence();
        }
        else
        {
            m_lastConfidence = 0.0f;
            return input;  // fail-close per CONTEXT D-04: return input unchanged on error
        }
        return result;
    }

} // namespace sgns::neoswarm::elm
