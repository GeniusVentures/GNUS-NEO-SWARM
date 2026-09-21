/**
 * @file       test_gcs_global_db.cpp
 * @brief      Lifecycle unit tests for the GCS GlobalDB component (Phase 3, Task 3).
 *             Uses a real GossipPubSub on port 0 (Tier 2 fixture pattern from
 *             SuperGenius/test/src/crdt/globaldb_integration.cpp) and the NEO-SWARM
 *             wait-condition template (condition_variable polling — no
 *             std::this_thread sleeps).
 * @date       2026-08-10
 */

#include "storage/gcs_global_db.hpp"

#include <chrono>
#include <condition_variable>
#include <cstdlib>
#include <filesystem>
#include <functional>
#include <mutex>
#include <string>

#include <gtest/gtest.h>

#include "crdt/globaldb/keypair_file_storage.hpp"

#include "ipfs_pubsub/gossip_pubsub.hpp"

#include <libp2p/log/configurator.hpp>
#include <libp2p/log/logger.hpp>

#include <soralog/impl/configurator_from_yaml.hpp>
#include <soralog/logging_system.hpp>

namespace
{
    /// Upper bound for a single wait-condition call (mirrors the fixture's WAIT_TIMEOUT).
    constexpr std::chrono::milliseconds kWaitTimeout{ 25000 };
    /// Re-check interval for pure polling predicates inside WaitForCondition.
    constexpr std::chrono::milliseconds kPollInterval{ 10 };
    /// GossipPubSub bind address used by every test.
    constexpr const char *kListenIp = "0.0.0.0";

    /**
     * @brief Minimal soralog YAML — console sink only, error level, sufficient to satisfy
     *        libp2p::log::setLoggingSystem() before any SuperGenius logger is constructed.
     */
    constexpr const char *kLoggingYaml = R"(
     sinks:
       - name: console
         type: console
         color: false
     groups:
       - name: gcs_global_db_test
         sink: console
         level: error
         children:
           - name: libp2p
           - name: Gossip
    )";

    /**
     * @brief Wait-condition template (NEO-SWARM): poll `predicate` via
     *        condition_variable::wait_for until it returns true or `timeout` elapses.
     *
     * condition_variable only wakes on notify, so for pure polling predicates
     * (e.g. "file exists on disk") we use the sanctioned polling-with-cv idiom:
     * cv.wait_for(lock, kPollInterval, pred) inside a deadline loop.
     *
     * @param[in] predicate Nullary callable returning bool.
     * @param[in] timeout   Maximum time to wait.
     * @return true if the predicate became true before the deadline; false otherwise.
     */
    bool WaitForCondition( const std::function<bool()> &predicate, std::chrono::milliseconds timeout )
    {
        std::mutex              mtx;
        std::condition_variable cv;
        std::unique_lock<std::mutex> lock( mtx );
        const auto deadline = std::chrono::steady_clock::now() + timeout;
        while ( std::chrono::steady_clock::now() < deadline )
        {
            if ( predicate() )
            {
                return true;
            }
            const auto remaining = std::chrono::duration_cast<std::chrono::milliseconds>(
                deadline - std::chrono::steady_clock::now() );
            const auto slice     = std::min( kPollInterval, remaining );
            cv.wait_for( lock, slice );
        }
        return predicate();
    }
} // namespace

namespace sgns::neoswarm::storage::test
{
    /**
     * @brief Fixture that owns a per-test temp directory under
     *        std::filesystem::temp_directory_path() and removes it in TearDown.
     */
    class GcsGlobalDbTest : public ::testing::Test
    {
    protected:
        /**
         * @brief One-time logging-system init — SuperGenius's base::createLogger asserts
         *        a configured soralog LoggingSystem; without it GossipPubSub construction
         *        crashes with "Logging system is not ready". Mirrors the SuperGenius
         *        globaldb_integration.cpp SetUpTestSuite.
         */
        static void SetUpTestSuite()
        {
            auto loggerConfigurator = std::make_shared<libp2p::log::Configurator>();
            auto configFromYaml     = std::make_shared<soralog::ConfiguratorFromYAML>( loggerConfigurator,
                                                                                       std::string{ kLoggingYaml } );
            auto loggingSystem      = std::make_shared<soralog::LoggingSystem>( configFromYaml );
            const auto confResult   = loggingSystem->configure();
            ASSERT_FALSE( confResult.has_error ) << "Could not configure test logging system";
            libp2p::log::setLoggingSystem( loggingSystem );
        }

        void SetUp() override
        {
            const auto *info       = ::testing::UnitTest::GetInstance()->current_test_info();
            const auto  uniqueSalt = std::chrono::steady_clock::now().time_since_epoch().count();
            m_tempPath = ( std::filesystem::temp_directory_path()
                           / ( std::string{ "gcs_global_db_" } + info->name() + "_" +
                               std::to_string( uniqueSalt ) ) )
                             .string();
            std::filesystem::create_directories( m_tempPath );
        }

        void TearDown() override
        {
            std::error_code ec;
            std::filesystem::remove_all( m_tempPath, ec );
        }

        /**
         * @brief Stand up a real GossipPubSub bound to port 0 (random free port).
         *        Mirrors globaldb_integration.cpp:93-99.
         */
        std::shared_ptr<sgns::ipfs_pubsub::GossipPubSub> MakeStartedPubSub( const std::string &keyDir )
        {
            sgns::crdt::KeyPairFileStorage keyStore( keyDir );
            auto                           keyPairResult = keyStore.GetKeyPair();
            EXPECT_FALSE( keyPairResult.has_error() );
            if ( keyPairResult.has_error() )
            {
                return nullptr;
            }
            auto pubsub = std::make_shared<sgns::ipfs_pubsub::GossipPubSub>( keyPairResult.value() );
            auto startFuture = pubsub->Start( 0, {}, kListenIp, {} );
            auto startError  = startFuture.get();
            EXPECT_FALSE( startError ) << "Could not start GossipPubSub: " << startError.message();
            if ( startError )
            {
                return nullptr;
            }
            return pubsub;
        }

        std::string m_tempPath; ///< Per-test temp directory (created in SetUp, removed in TearDown)
    };

    /**
     * @brief Default-constructed component: inert, IsRunning() false, Shutdown() a safe no-op.
     */
    TEST_F( GcsGlobalDbTest, DefaultConstructedIsNotRunning )
    {
        GcsGlobalDb::Config cfg{};
        cfg.m_dbPath = m_tempPath + "/db";
        GcsGlobalDb db( cfg );

        EXPECT_FALSE( db.IsRunning() );
        db.Shutdown(); // must not crash, must not throw
        EXPECT_FALSE( db.IsRunning() );
    }

    /**
     * @brief Initialize() without GeniusSDK initialized must fail with the specific
     *        Error::SdkNotInitialized code. This binary never calls GeniusSDKInit, so
     *        GeniusSDKGetNode() returns nullptr throughout the test.
     */
    TEST_F( GcsGlobalDbTest, InitializeWithoutSdkFails )
    {
        GcsGlobalDb::Config cfg{};
        cfg.m_dbPath = m_tempPath + "/db";
        GcsGlobalDb db( cfg );

        auto res = db.Initialize();
        ASSERT_FALSE( res.has_value() );
        EXPECT_EQ( res.error(), Error::SdkNotInitialized );
        EXPECT_FALSE( db.IsRunning() );
    }

    /**
     * @brief Full lifecycle with an injected pubsub: GlobalDB::New succeeds, Start is
     *        called, IsRunning() becomes true, the db directory appears on disk, and
     *        Shutdown() returns the component to a stopped state with the io thread
     *        joined.
     */
    TEST_F( GcsGlobalDbTest, LifecycleWithInjectedPubSub )
    {
        auto pubsub = MakeStartedPubSub( m_tempPath + "/key" );
        ASSERT_NE( pubsub, nullptr );

        GcsGlobalDb::Config cfg{};
        cfg.m_dbPath = m_tempPath + "/db";
        GcsGlobalDb db( cfg );

        auto res = db.Initialize( pubsub );
        ASSERT_TRUE( res.has_value() );
        EXPECT_TRUE( db.IsRunning() );

        // The db directory may be created lazily — wait for it via the wait-condition template.
        const auto dbPath = cfg.m_dbPath;
        EXPECT_TRUE( WaitForCondition( [&dbPath]() { return std::filesystem::exists( dbPath ); },
                                       kWaitTimeout ) );

        db.Shutdown();
        EXPECT_FALSE( db.IsRunning() );

        pubsub->Stop();
    }

    /**
     * @brief Double Initialize() must fail the second call with Error::GcsDbError
     *        (programmer error — surfaced, not silently swallowed).
     */
    TEST_F( GcsGlobalDbTest, DoubleInitializeFails )
    {
        auto pubsub = MakeStartedPubSub( m_tempPath + "/key" );
        ASSERT_NE( pubsub, nullptr );

        GcsGlobalDb::Config cfg{};
        cfg.m_dbPath = m_tempPath + "/db";
        GcsGlobalDb db( cfg );

        auto first = db.Initialize( pubsub );
        ASSERT_TRUE( first.has_value() );
        EXPECT_TRUE( db.IsRunning() );

        auto second = db.Initialize( pubsub );
        ASSERT_FALSE( second.has_value() );
        EXPECT_EQ( second.error(), Error::GcsDbError );

        db.Shutdown();
        pubsub->Stop();
    }

} // namespace sgns::neoswarm::storage::test
