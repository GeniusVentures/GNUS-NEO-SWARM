/**
 * @file       gcs_global_db.cpp
 * @brief      GCS GlobalDB component implementation — init-style lifecycle (D-13),
 *             PubSub acquired from GeniusSDK (D-15/D-16a), GlobalDB::Error mapped to
 *             NEO-SWARM codes at the boundary (D-14).
 * @date       2026-08-10
 */

#include "storage/gcs_global_db.hpp"

#include <chrono>
#include <utility>

#include <libp2p/basic/scheduler.hpp>
#include <libp2p/basic/scheduler/scheduler_impl.hpp>

#include "GeniusSDK.hpp"

#include "crdt/crdt_options.hpp"
#include "crdt/globaldb/globaldb.hpp"

#include "ipfs_lite/ipfs/graphsync/impl/network/network.hpp"
#include "ipfs_lite/ipfs/graphsync/impl/local_requests.hpp"

#include "ipfs_pubsub/gossip_pubsub.hpp"

namespace sgns::neoswarm::storage
{
    namespace
    {
        /// Scheduler tick used by the local AsioSchedulerBackend (matches globaldb_integration.cpp).
        constexpr uint32_t kSchedulerTickMs = 100;

        /**
         * @brief Map a SuperGenius GlobalDB::Error onto the NEO-SWARM error domain (D-14).
         *
         * One NEO-SWARM code is used here — the specific GlobalDB value is preserved in the
         * spdlog error line at the call site (T-03-03 accepted disposition).
         *
         * @param[in] globalDbErr The SuperGenius GlobalDB error to translate.
         * @return Error::GcsDbError for every GlobalDB::Error value.
         */
        Error MapGlobalDbError( crdt::GlobalDB::Error globalDbErr ) noexcept
        {
            switch ( globalDbErr )
            {
                case crdt::GlobalDB::Error::ROCKSDB_IO:
                case crdt::GlobalDB::Error::IPFS_DB_NOT_CREATED:
                case crdt::GlobalDB::Error::DAG_SYNCHER_NOT_LISTENING:
                case crdt::GlobalDB::Error::CRDT_DATASTORE_NOT_CREATED:
                case crdt::GlobalDB::Error::PUBSUB_BROADCASTER_NOT_CREATED:
                case crdt::GlobalDB::Error::INVALID_PARAMETERS:
                case crdt::GlobalDB::Error::GLOBALDB_NOT_STARTED:
                    return Error::GcsDbError;
            }
            return Error::GcsDbError;
        }

        /**
         * @brief Translate an outcome error_code produced by GlobalDB::New into the
         *        underlying GlobalDB::Error enum value (Boost.Outcome stores enum-based
         *        errors as std::error_code whose .value() is the enum's underlying value).
         */
        crdt::GlobalDB::Error ExtractGlobalDbError( const std::error_code &ec ) noexcept
        {
            return static_cast<crdt::GlobalDB::Error>( ec.value() );
        }
    } // namespace

    GcsGlobalDb::GcsGlobalDb( Config cfg ) noexcept
        : m_cfg( std::move( cfg ) ), m_logger( neoswarm::CreateLogger( "GcsGlobalDb" ) )
    {
        // Constructor stores config only — no fallible work (D-13).
    }

    GcsGlobalDb::~GcsGlobalDb()
    {
        Shutdown();
    }

    outcome::result<void> GcsGlobalDb::Initialize()
    {
        // Step 2: PubSub acquisition (D-15, D-16, D-16a) — pull from the in-process GeniusSDK.
        auto node = GeniusSDKGetNode();
        if ( !node )
        {
            m_logger->error( "GcsGlobalDb::Initialize — GeniusSDKGetNode() returned nullptr; "
                             "GeniusSDK init chain has not run (D-20 ordering: SDK before GlobalDB)" );
            return outcome::failure( Error::SdkNotInitialized );
        }

        auto pubsub = node->GetPubSub();
        if ( !pubsub )
        {
            m_logger->error( "GcsGlobalDb::Initialize — GeniusNode::GetPubSub() returned nullptr; "
                             "SDK is up but pubsub is not started" );
            return outcome::failure( Error::SdkNotInitialized );
        }

        return Initialize( std::move( pubsub ) );
    }

    outcome::result<void> GcsGlobalDb::Initialize( std::shared_ptr<sgns::ipfs_pubsub::GossipPubSub> pubsub )
    {
        // Step 1: Guard — double Initialize() is a programmer error.
        if ( m_running.load() )
        {
            m_logger->error( "GcsGlobalDb::Initialize called twice — already running" );
            return outcome::failure( Error::GcsDbError );
        }

        if ( !pubsub )
        {
            m_logger->error( "GcsGlobalDb::Initialize — null pubsub injected" );
            return outcome::failure( Error::GcsDbError );
        }

        // Step 3: Local construction (D-17, D-04) — mirror globaldb_integration.cpp:100-107.
        m_io = std::make_shared<boost::asio::io_context>();
        m_scheduler = std::make_shared<libp2p::basic::SchedulerImpl>(
            std::make_shared<libp2p::basic::AsioSchedulerBackend>( m_io ),
            libp2p::basic::Scheduler::Config{ std::chrono::milliseconds{ kSchedulerTickMs } } );
        m_graphsyncNetwork = std::make_shared<sgns::ipfs_lite::ipfs::graphsync::Network>( pubsub->GetHost(),
                                                                                          m_scheduler );
        m_generator = std::make_shared<sgns::ipfs_lite::ipfs::graphsync::RequestIdGenerator>();

        // Step 4: GlobalDB::New (D-03, D-04) — nullptr datastore, default BackupOptions{} (GCS
        // backups are disabled; the blockchain GlobalDB's backup policy is independent per D-01).
        auto dbResult = crdt::GlobalDB::New( m_io,
                                             m_cfg.m_dbPath,
                                             std::move( pubsub ),
                                             crdt::CrdtOptions::DefaultOptions(),
                                             m_graphsyncNetwork,
                                             m_scheduler,
                                             m_generator,
                                             nullptr,
                                             crdt::GlobalDB::BackupOptions{} );
        if ( dbResult.has_error() )
        {
            const auto &dbError = dbResult.error();
            m_logger->error( "GcsGlobalDb::Initialize — GlobalDB::New failed: {} (value {})",
                             dbError.message(),
                             dbError.value() );
            m_db.reset();
            m_generator.reset();
            m_graphsyncNetwork.reset();
            m_scheduler.reset();
            m_io.reset();
            return outcome::failure( MapGlobalDbError( ExtractGlobalDbError( dbError ) ) );
        }
        m_db = std::move( dbResult.value() );

        // Step 5: Start the GlobalDB.
        m_db->Start();

        // Step 6: Topic wiring (D-07) — listen first, then broadcast.
        m_db->AddListenTopic( Config::kReputationTopic );
        auto broadcastResult = m_db->AddBroadcastTopic( Config::kReputationTopic );
        if ( broadcastResult.has_error() )
        {
            m_logger->error( "GcsGlobalDb::Initialize — AddBroadcastTopic('{}') failed",
                             Config::kReputationTopic );
            m_db->ShutdownNow();
            m_db.reset();
            m_generator.reset();
            m_graphsyncNetwork.reset();
            m_scheduler.reset();
            m_io.reset();
            return outcome::failure( Error::GcsDbError );
        }

        // Step 7: Spawn the io thread (mirrors globaldb_integration.cpp:122).
        auto io = m_io;
        m_ioThread = std::thread( [io]() { io->run(); } );
        m_running.store( true );
        m_logger->info( "GcsGlobalDb initialized at '{}' — topic '{}' wired", m_cfg.m_dbPath, Config::kReputationTopic );
        return outcome::success();
    }

    void GcsGlobalDb::Shutdown() noexcept
    {
        if ( !m_running.load() )
        {
            return;
        }

        if ( m_db )
        {
            m_db->ShutdownNow(); // idempotent per GlobalDB contract
        }
        if ( m_io )
        {
            m_io->stop();
        }
        if ( m_ioThread.joinable() )
        {
            m_ioThread.join();
        }
        m_db.reset();
        m_generator.reset();
        m_graphsyncNetwork.reset();
        m_scheduler.reset();
        m_io.reset();
        m_running.store( false );
        m_logger->info( "GcsGlobalDb shut down" );
    }

    bool GcsGlobalDb::IsRunning() const noexcept
    {
        return m_running.load();
    }

} // namespace sgns::neoswarm::storage
