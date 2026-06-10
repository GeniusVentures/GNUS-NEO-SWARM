/**
 * @file       test_reputation.cpp
 * @brief      Unit tests for reputation subsystem
 * @date       2026-05-08
 * @author     Subaskar S (ssivakumar@gnus.ai)
 */

#include "reputation/reputation_crdt.hpp"
#include "reputation/reputation_scoring.hpp"
#include "reputation/reputation_storage.hpp"
#include "reputation/weighted_consensus.hpp"
#include <chrono>
#include <gtest/gtest.h>

using namespace sgns::neoswarm;
using namespace sgns::neoswarm::reputation;

// ---------------------------------------------------------------------------
// ReputationScoring
// ---------------------------------------------------------------------------
TEST( ReputationScoring, AccuracyDeltaWithGroundTruth )
{
    ReputationScoring scoring;
    EXPECT_GT( scoring.DeltaAccuracy( true, 1.0 ), 0.0 );
    EXPECT_LT( scoring.DeltaAccuracy( true, 0.0 ), 0.0 );
}

TEST( ReputationScoring, LatencyPenalty )
{
    ReputationScoring scoring;
    double d1 = scoring.DeltaLatency( 1000.0, 500.0 ); // 2× median
    double d2 = scoring.DeltaLatency( 100.0, 500.0 );  // 0.2× median
    EXPECT_LT( d1, 0.0 );
    EXPECT_GT( d2, d1 );
}

TEST( ReputationScoring, ConsistencyBonus )
{
    ReputationScoring scoring;
    EXPECT_GT( scoring.DeltaConsistency( 1.0f ), scoring.DeltaConsistency( 50.0f ) );
}

TEST( ReputationScoring, ScoreClampedToRange )
{
    ReputationScoring scoring;
    NodeReputation rep;
    rep.m_identityKey = "test-node";
    rep.m_globalScore = 0.99;

    InferenceResponse resp;
    resp.m_output = "correct";
    resp.m_perplexity = 1.0f;
    resp.m_latencyMs = 100.0;
    resp.m_nodeId = "test-node";

    auto updated = scoring.Update( rep, resp, 100.0, std::string( "correct" ), "correct" );
    EXPECT_LE( updated.m_globalScore, 1.0 );
    EXPECT_GE( updated.m_globalScore, 0.0 );
}

TEST( ReputationScoring, TaskCountIncremented )
{
    ReputationScoring scoring;
    NodeReputation rep;
    rep.m_identityKey = "test-node";
    rep.m_taskCount = 5;

    InferenceResponse resp;
    resp.m_output = "answer";
    resp.m_perplexity = 2.0f;
    resp.m_latencyMs = 200.0;
    resp.m_nodeId = "test-node";

    auto updated = scoring.Update( rep, resp, 200.0, std::nullopt, "answer" );
    EXPECT_EQ( updated.m_taskCount, 6u );
}

// ---------------------------------------------------------------------------
// WeightedConsensus
// ---------------------------------------------------------------------------
TEST( WeightedConsensus, SelectsHighReputationNode )
{
    WeightedConsensus consensus;
    std::vector<NodeOutput> outputs = { { "node-A", "815961", 1.0f, 100.0, 0.9 },
                                        { "node-B", "815961", 1.2f, 120.0, 0.7 },
                                        { "node-C", "814000", 2.0f, 150.0, 0.2 } };
    auto winner = consensus.SelectWinner( outputs );
    EXPECT_EQ( winner.m_output, "815961" );
}

TEST( WeightedConsensus, SingleNode )
{
    WeightedConsensus consensus;
    std::vector<NodeOutput> outputs = { { "node-A", "answer", 1.0f, 100.0, 0.8 } };
    EXPECT_EQ( consensus.SelectWinner( outputs ).m_output, "answer" );
}

TEST( WeightedConsensus, EmptyInputReturnsDefault )
{
    WeightedConsensus consensus;
    std::vector<NodeOutput> outputs;
    EXPECT_TRUE( consensus.SelectWinner( outputs ).m_output.empty() );
}

TEST( WeightedConsensus, BestWeightedScoreStrategy )
{
    WeightedConsensus::Config cfg;
    cfg.strategy_ = WeightedConsensus::Strategy::BestWeightedScore;
    WeightedConsensus consensus( cfg );

    std::vector<NodeOutput> outputs = { { "node-A", "wrong", 5.0f, 100.0, 0.9 },
                                        { "node-B", "correct", 1.0f, 100.0, 0.8 } };
    EXPECT_EQ( consensus.SelectWinner( outputs ).m_output, "correct" );
}

// ---------------------------------------------------------------------------
// ReputationCRDT
// ---------------------------------------------------------------------------
TEST( ReputationCRDT, MergeNewEntry )
{
    ReputationCRDT crdt;
    NodeReputation r;
    r.m_identityKey = "node-1";
    r.m_globalScore = 0.8;
    r.m_lastUpdatedMs = 1000;
    crdt.Merge( r );

    auto got = crdt.Get( "node-1" );
    ASSERT_TRUE( got.has_value() );
    EXPECT_DOUBLE_EQ( got->m_globalScore, 0.8 );
}

TEST( ReputationCRDT, LWWKeepsLatest )
{
    ReputationCRDT crdt;
    NodeReputation old_r;
    old_r.m_identityKey = "node-1";
    old_r.m_globalScore = 0.5;
    old_r.m_lastUpdatedMs = 1000;
    crdt.Merge( old_r );

    NodeReputation newer;
    newer.m_identityKey = "node-1";
    newer.m_globalScore = 0.9;
    newer.m_lastUpdatedMs = 2000;
    crdt.Merge( newer );

    EXPECT_DOUBLE_EQ( crdt.Get( "node-1" )->m_globalScore, 0.9 );
}

TEST( ReputationCRDT, LWWIgnoresOlder )
{
    ReputationCRDT crdt;
    NodeReputation newer;
    newer.m_identityKey = "node-1";
    newer.m_globalScore = 0.9;
    newer.m_lastUpdatedMs = 2000;
    crdt.Merge( newer );

    NodeReputation old_r;
    old_r.m_identityKey = "node-1";
    old_r.m_globalScore = 0.3;
    old_r.m_lastUpdatedMs = 500;
    crdt.Merge( old_r );

    EXPECT_DOUBLE_EQ( crdt.Get( "node-1" )->m_globalScore, 0.9 );
}

TEST( ReputationCRDT, SerializeDeserializeRoundtrip )
{
    ReputationCRDT crdt1;
    NodeReputation r;
    r.m_identityKey = "node-X";
    r.m_globalScore = 0.75;
    r.m_taskCount = 42;
    r.m_lastUpdatedMs = 99999;
    crdt1.Merge( r );

    ReputationCRDT crdt2;
    crdt2.DeserializeAndMerge( crdt1.Serialize() );

    auto got = crdt2.Get( "node-X" );
    ASSERT_TRUE( got.has_value() );
    EXPECT_DOUBLE_EQ( got->m_globalScore, 0.75 );
    EXPECT_EQ( got->m_taskCount, 42u );
}

// ---------------------------------------------------------------------------
// ReputationStorage
// ---------------------------------------------------------------------------
static std::string UniqueDbPath( const std::string& tag )
{
    return "/tmp/genius_test_" + tag + "_" +
           std::to_string( std::chrono::steady_clock::now().time_since_epoch().count() );
}

TEST( ReputationStorage, PutAndGet )
{
    ReputationStorage storage( UniqueDbPath( "putget" ) );
    ASSERT_TRUE( storage.Open().has_value() );

    NodeReputation r;
    r.m_identityKey = "test-node";
    r.m_globalScore = 0.65;
    r.m_taskCount = 10;
    ASSERT_TRUE( storage.Put( r ).has_value() );

    auto got = storage.Get( "test-node" );
    ASSERT_TRUE( got.has_value() );
    EXPECT_DOUBLE_EQ( got.value().m_globalScore, 0.65 );
    EXPECT_EQ( got.value().m_taskCount, 10u );
}

TEST( ReputationStorage, GetNotFound )
{
    ReputationStorage storage( UniqueDbPath( "notfound" ) );
    ASSERT_TRUE( storage.Open().has_value() );
    EXPECT_FALSE( storage.Get( "nonexistent" ).has_value() );
}

TEST( ReputationStorage, GetAll )
{
    ReputationStorage storage( UniqueDbPath( "getall" ) );
    ASSERT_TRUE( storage.Open().has_value() );

    for ( int i = 0; i < 5; ++i )
    {
        NodeReputation r;
        r.m_identityKey = "node-" + std::to_string( i );
        r.m_globalScore = 0.5 + i * 0.1;
        ASSERT_TRUE( storage.Put( r ).has_value() );
    }

    auto all = storage.GetAll();
    ASSERT_TRUE( all.has_value() );
    EXPECT_EQ( all.value().size(), 5u );
}
