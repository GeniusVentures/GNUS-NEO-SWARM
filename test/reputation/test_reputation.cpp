/**
 * @file       test_reputation.cpp
 * @brief      Unit tests for reputation subsystem
 * @date       2026-05-08
 * @author     Subaskar S (ssivakumar@gnus.ai)
 */

#include "reputation/ReputationCRDT.hpp"
#include "reputation/ReputationScoring.hpp"
#include "reputation/ReputationStorage.hpp"
#include "reputation/WeightedConsensus.hpp"
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
    rep.identity_key_ = "test-node";
    rep.global_score_ = 0.99;

    InferenceResponse resp;
    resp.output_ = "correct";
    resp.perplexity_ = 1.0f;
    resp.latency_ms_ = 100.0;
    resp.node_id_ = "test-node";

    auto updated = scoring.Update( rep, resp, 100.0, std::string( "correct" ), "correct" );
    EXPECT_LE( updated.global_score_, 1.0 );
    EXPECT_GE( updated.global_score_, 0.0 );
}

TEST( ReputationScoring, TaskCountIncremented )
{
    ReputationScoring scoring;
    NodeReputation rep;
    rep.identity_key_ = "test-node";
    rep.task_count_ = 5;

    InferenceResponse resp;
    resp.output_ = "answer";
    resp.perplexity_ = 2.0f;
    resp.latency_ms_ = 200.0;
    resp.node_id_ = "test-node";

    auto updated = scoring.Update( rep, resp, 200.0, std::nullopt, "answer" );
    EXPECT_EQ( updated.task_count_, 6u );
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
    EXPECT_EQ( winner.output_, "815961" );
}

TEST( WeightedConsensus, SingleNode )
{
    WeightedConsensus consensus;
    std::vector<NodeOutput> outputs = { { "node-A", "answer", 1.0f, 100.0, 0.8 } };
    EXPECT_EQ( consensus.SelectWinner( outputs ).output_, "answer" );
}

TEST( WeightedConsensus, EmptyInputReturnsDefault )
{
    WeightedConsensus consensus;
    std::vector<NodeOutput> outputs;
    EXPECT_TRUE( consensus.SelectWinner( outputs ).output_.empty() );
}

TEST( WeightedConsensus, BestWeightedScoreStrategy )
{
    WeightedConsensus::Config cfg;
    cfg.strategy_ = WeightedConsensus::Strategy::BestWeightedScore;
    WeightedConsensus consensus( cfg );

    std::vector<NodeOutput> outputs = { { "node-A", "wrong", 5.0f, 100.0, 0.9 },
                                        { "node-B", "correct", 1.0f, 100.0, 0.8 } };
    EXPECT_EQ( consensus.SelectWinner( outputs ).output_, "correct" );
}

// ---------------------------------------------------------------------------
// ReputationCRDT
// ---------------------------------------------------------------------------
TEST( ReputationCRDT, MergeNewEntry )
{
    ReputationCRDT crdt;
    NodeReputation r;
    r.identity_key_ = "node-1";
    r.global_score_ = 0.8;
    r.last_updated_ms_ = 1000;
    crdt.Merge( r );

    auto got = crdt.Get( "node-1" );
    ASSERT_TRUE( got.has_value() );
    EXPECT_DOUBLE_EQ( got->global_score_, 0.8 );
}

TEST( ReputationCRDT, LWWKeepsLatest )
{
    ReputationCRDT crdt;
    NodeReputation old_r;
    old_r.identity_key_ = "node-1";
    old_r.global_score_ = 0.5;
    old_r.last_updated_ms_ = 1000;
    crdt.Merge( old_r );

    NodeReputation newer;
    newer.identity_key_ = "node-1";
    newer.global_score_ = 0.9;
    newer.last_updated_ms_ = 2000;
    crdt.Merge( newer );

    EXPECT_DOUBLE_EQ( crdt.Get( "node-1" )->global_score_, 0.9 );
}

TEST( ReputationCRDT, LWWIgnoresOlder )
{
    ReputationCRDT crdt;
    NodeReputation newer;
    newer.identity_key_ = "node-1";
    newer.global_score_ = 0.9;
    newer.last_updated_ms_ = 2000;
    crdt.Merge( newer );

    NodeReputation old_r;
    old_r.identity_key_ = "node-1";
    old_r.global_score_ = 0.3;
    old_r.last_updated_ms_ = 500;
    crdt.Merge( old_r );

    EXPECT_DOUBLE_EQ( crdt.Get( "node-1" )->global_score_, 0.9 );
}

TEST( ReputationCRDT, SerializeDeserializeRoundtrip )
{
    ReputationCRDT crdt1;
    NodeReputation r;
    r.identity_key_ = "node-X";
    r.global_score_ = 0.75;
    r.task_count_ = 42;
    r.last_updated_ms_ = 99999;
    crdt1.Merge( r );

    ReputationCRDT crdt2;
    crdt2.DeserializeAndMerge( crdt1.Serialize() );

    auto got = crdt2.Get( "node-X" );
    ASSERT_TRUE( got.has_value() );
    EXPECT_DOUBLE_EQ( got->global_score_, 0.75 );
    EXPECT_EQ( got->task_count_, 42u );
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
    r.identity_key_ = "test-node";
    r.global_score_ = 0.65;
    r.task_count_ = 10;
    ASSERT_TRUE( storage.Put( r ).has_value() );

    auto got = storage.Get( "test-node" );
    ASSERT_TRUE( got.has_value() );
    EXPECT_DOUBLE_EQ( got.value().global_score_, 0.65 );
    EXPECT_EQ( got.value().task_count_, 10u );
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
        r.identity_key_ = "node-" + std::to_string( i );
        r.global_score_ = 0.5 + i * 0.1;
        ASSERT_TRUE( storage.Put( r ).has_value() );
    }

    auto all = storage.GetAll();
    ASSERT_TRUE( all.has_value() );
    EXPECT_EQ( all.value().size(), 5u );
}
