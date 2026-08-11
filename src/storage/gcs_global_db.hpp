/**
 * @file       gcs_global_db.hpp
 * @brief      NEO-SWARM-owned sgns::crdt::GlobalDB component (Phase 3, D-01..D-04).
 *             Owns the GCS CRDT lifecycle: pulls the shared GossipPubSub from the in-process
 *             GeniusSDK (D-15/D-16a), constructs io_context/scheduler/graphsync network/request-id
 *             generator locally (D-17), wires the gcs-reputation topic (D-07), and exposes an
 *             init-style lifecycle (D-13).
 * @date       2026-08-10
 */

#ifndef NEOSWARM_STORAGE_GCS_GLOBAL_DB_HPP
#define NEOSWARM_STORAGE_GCS_GLOBAL_DB_HPP

#include <atomic>
#include <memory>
#include <string>
#include <thread>

#include <boost/asio/io_context.hpp>

#include "common/error.hpp"
#include "common/logging.hpp"

// ---------------------------------------------------------------------------
// Forward declarations — heavy SuperGenius/libp2p headers stay in the .cpp.
// ---------------------------------------------------------------------------
namespace sgns::crdt
{
    class GlobalDB;
}

namespace sgns::ipfs_pubsub
{
    class GossipPubSub;
}

namespace sgns::ipfs_lite::ipfs::graphsync
{
    class Network;
    class RequestIdGenerator;
}

namespace libp2p::basic
{
    class Scheduler;
}

namespace sgns::neoswarm::storage
{
    /**
     * @brief GCS GlobalDB component — single owner of the NEO-SWARM CRDT store.
     *
     * Lifecycle:
     *  - Constructor stores config only (no fallible work, no I/O) — D-13.
     *  - Initialize() runs the 7-step init chain (acquire pubsub via GeniusSDKGetNode,
     *    build local io/scheduler/network/generator, GlobalDB::New with nullptr datastore,
     *    Start, wire gcs-reputation listen+broadcast topic, spawn io thread).
     *  - Shutdown() is idempotent and joins the io thread.
     *
     * Error mapping (D-14):
     *  - GeniusSDKGetNode() == nullptr                -> Error::SdkNotInitialized
     *  - GlobalDB::New / AddBroadcastTopic failures    -> Error::GcsDbError
     *  - Double Initialize()                           -> Error::GcsDbError (programmer error)
     */
    class GcsGlobalDb
    {
    public:
        /**
         * @brief Component configuration.
         *
         * Aggregate-initializable; designed for designated initializers.
         */
        struct Config
        {
            /// Default database directory, relative to the process working directory (D-02).
            static constexpr const char *kDefaultDbPath = "./gcs.db";
            /// Dedicated CRDT topic for reputation convergence across the swarm (D-07).
            static constexpr const char *kReputationTopic = "gcs-reputation";

            std::string m_dbPath = kDefaultDbPath; ///< RocksDB path for the GCS CRDT store
        };

        /**
         * @brief Construct the component, storing the config only.
         *
         * Performs no I/O, no network activity, and no fallible work — D-13.
         *
         * @param[in] cfg Configuration; defaults to ./gcs.db.
         */
        explicit GcsGlobalDb( Config cfg ) noexcept;

        /**
         * @brief Destructor — calls Shutdown() if running; never throws.
         */
        ~GcsGlobalDb();

        GcsGlobalDb( const GcsGlobalDb & )            = delete;
        GcsGlobalDb &operator=( const GcsGlobalDb & ) = delete;
        GcsGlobalDb( GcsGlobalDb && )                 = delete;
        GcsGlobalDb &operator=( GcsGlobalDb && )      = delete;

        /**
         * @brief Production init — acquires the shared pubsub via GeniusSDKGetNode()
         *        and delegates to the injected-pubsub overload.
         *
         * @return outcome::success on a fully wired, started GlobalDB; otherwise:
         *         Error::SdkNotInitialized (GeniusSDK init chain has not run — D-20 ordering),
         *         Error::GcsDbError       (GlobalDB::New / AddBroadcastTopic / double-init).
         */
        outcome::result<void> Initialize();

        /**
         * @brief Injected-pubsub init — test seam (Tier 2 fixture pattern).
         *
         * Runs the full init chain (steps 3-7) against the supplied pubsub without
         * consulting GeniusSDK. Production callers should prefer the no-arg overload;
         * this overload exists so unit tests can stand up a real GossipPubSub on port 0
         * without bringing the entire GeniusNode online (per RESEARCH Q-01).
         *
         * @param[in] pubsub A started GossipPubSub whose lifetime outlives this component.
         * @return outcome::success or a specific Error code (see Initialize()).
         */
        outcome::result<void> Initialize( std::shared_ptr<sgns::ipfs_pubsub::GossipPubSub> pubsub );

        /**
         * @brief Idempotent shutdown — quiesces the GlobalDB, stops the io_context,
         *        and joins the io thread. Safe to call when not initialized.
         */
        void Shutdown() noexcept;

        /**
         * @brief Whether the component has a running GlobalDB + io thread.
         */
        bool IsRunning() const noexcept;

    private:
        Config m_cfg;                                                    ///< Component configuration
        std::shared_ptr<boost::asio::io_context> m_io;                   ///< Dedicated io_context (D-17)
        std::shared_ptr<libp2p::basic::Scheduler> m_scheduler;           ///< libp2p scheduler over m_io
        std::shared_ptr<sgns::ipfs_lite::ipfs::graphsync::Network> m_graphsyncNetwork; ///< graphsync network
        std::shared_ptr<sgns::ipfs_lite::ipfs::graphsync::RequestIdGenerator> m_generator; ///< request-id generator
        std::shared_ptr<sgns::crdt::GlobalDB> m_db;                      ///< Owned GlobalDB (nullptr until Initialize)
        std::thread m_ioThread;                                          ///< io->run() worker thread
        std::atomic<bool> m_running{ false };                            ///< Lifecycle flag
        Logger m_logger;                                                 ///< spdlog component logger
    };

} // namespace sgns::neoswarm::storage

#endif // NEOSWARM_STORAGE_GCS_GLOBAL_DB_HPP
