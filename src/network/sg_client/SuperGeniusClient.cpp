/**
 * @file       SuperGeniusClient.cpp
 * @brief      Stub implementation — real gRPC dispatch in plan 02-02/02-03
 * @date       2026-05-28
 * @author     Subaskar S (ssivakumar@gnus.ai)
 */

#include "SuperGeniusClient.hpp"
#include "common/Logging.hpp"
#include "security/NodeIdentity.hpp"

namespace sgns::neoswarm::network
{
    namespace
    {
        auto ClientLogger()
        {
            return CreateLogger( "NeoSwarm/SGClient" );
        }
    }

    struct SuperGeniusClient::Impl
    {
        Config cfg_;
        const security::NodeIdentity *identity_ = nullptr;
        bool connected_ = false;
    };

    SuperGeniusClient::SuperGeniusClient( Config cfg )
        : impl_( std::make_unique<Impl>() )
    {
        impl_->cfg_ = std::move( cfg );
    }

    SuperGeniusClient::~SuperGeniusClient() = default;

    SuperGeniusClient::SuperGeniusClient( SuperGeniusClient && ) noexcept = default;
    SuperGeniusClient &SuperGeniusClient::operator=( SuperGeniusClient && ) noexcept = default;

    outcome::result<void> SuperGeniusClient::Initialize(
        const security::NodeIdentity &identity )
    {
        impl_->identity_ = &identity;
        ClientLogger()->info( "SuperGeniusClient initialized with NodeIdentity" );
        return outcome::success();
    }

    outcome::result<void> SuperGeniusClient::Connect()
    {
        ClientLogger()->warn( "SuperGeniusClient::Connect — not yet implemented (Phase 2, plan 02-02)" );
        return outcome::failure( Error::NetworkError );
    }

    outcome::result<std::vector<uint8_t>> SuperGeniusClient::SubmitJob(
        const std::string &gnusSchemaJson )
    {
        ( void )gnusSchemaJson;
        ClientLogger()->warn( "SuperGeniusClient::SubmitJob — not yet implemented (Phase 2, plan 02-03)" );
        return outcome::failure( Error::NotImplemented );
    }

    void SuperGeniusClient::Disconnect()
    {
        impl_->connected_ = false;
        ClientLogger()->info( "SuperGeniusClient disconnected" );
    }

    bool SuperGeniusClient::IsConnected() const noexcept
    {
        return impl_->connected_;
    }

} // namespace sgns::neoswarm::network
