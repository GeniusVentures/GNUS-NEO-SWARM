#include "common/types.hpp"
#include <gtest/gtest.h>

using namespace sgns::neoswarm;

TEST(ExecutionMode, EnumValues_AreDistinct)
{
    EXPECT_NE( static_cast<int>( ExecutionMode::SingleNode ), static_cast<int>( ExecutionMode::Specialist ) );
    EXPECT_NE( static_cast<int>( ExecutionMode::SingleNode ), static_cast<int>( ExecutionMode::Swarm ) );
    EXPECT_NE( static_cast<int>( ExecutionMode::Specialist ), static_cast<int>( ExecutionMode::Swarm ) );
}

TEST(RouteTarget, EnumValues_AreDistinct)
{
    EXPECT_NE( static_cast<int>( RouteTarget::CoreOnly ), static_cast<int>( RouteTarget::CorePlusMath ) );
    EXPECT_NE( static_cast<int>( RouteTarget::CoreOnly ), static_cast<int>( RouteTarget::CorePlusGrammar ) );
    EXPECT_NE( static_cast<int>( RouteTarget::CorePlusMath ),
               static_cast<int>( RouteTarget::CorePlusGrammar ) );
}

TEST(Task, DefaultConstructor_HasReasonableDefaults)
{
    Task task;
    EXPECT_EQ( task.m_mode, ExecutionMode::SingleNode );
    EXPECT_EQ( task.m_maxTokens, 512 );
    EXPECT_FLOAT_EQ( task.m_temperature, 0.7f );
    EXPECT_TRUE( task.m_id.empty() );
    EXPECT_TRUE( task.m_prompt.empty() );
    EXPECT_TRUE( task.m_nodeId.empty() );
}

TEST(InferenceResponse, DefaultConstructor_HasReasonableDefaults)
{
    InferenceResponse resp;
    EXPECT_EQ( resp.m_modeUsed, ExecutionMode::SingleNode );
    EXPECT_EQ( resp.m_routeUsed, RouteTarget::CoreOnly );
    EXPECT_FLOAT_EQ( resp.m_perplexity, 1.0f );
    EXPECT_DOUBLE_EQ( resp.m_totalLatencyMs, 0.0 );
    EXPECT_TRUE( resp.m_success );
    EXPECT_TRUE( resp.m_output.empty() );
    EXPECT_TRUE( resp.m_taskId.empty() );
}

TEST(RouteDecision, DefaultConstructor_HasReasonableDefaults)
{
    RouteDecision decision;
    EXPECT_EQ( decision.m_target, RouteTarget::CoreOnly );
    EXPECT_FLOAT_EQ( decision.confidence_, 1.0f );
    EXPECT_EQ( decision.m_mode, ExecutionMode::SingleNode );
    EXPECT_TRUE( decision.m_reasoning.empty() );
}

TEST(NodeOutput, DefaultConstructor_ReasonableDefaults)
{
    NodeOutput output;
    EXPECT_FLOAT_EQ( output.m_perplexity, 1.0f );
    EXPECT_DOUBLE_EQ( output.m_latencyMs, 0.0 );
    EXPECT_DOUBLE_EQ( output.reputation_, 0.5 );
    EXPECT_TRUE( output.m_nodeId.empty() );
    EXPECT_TRUE( output.m_output.empty() );
}

TEST(NodeReputation, DefaultConstructor_ReasonableDefaults)
{
    NodeReputation rep;
    EXPECT_DOUBLE_EQ( rep.m_globalScore, 0.5 );
    EXPECT_DOUBLE_EQ( rep.m_mathScore, 0.5 );
    EXPECT_DOUBLE_EQ( rep.m_grammarScore, 0.5 );
    EXPECT_DOUBLE_EQ( rep.m_latencyScore, 0.5 );
    EXPECT_DOUBLE_EQ( rep.m_consistencyScore, 0.5 );
    EXPECT_EQ( rep.m_taskCount, 0 );
    EXPECT_EQ( rep.m_lastUpdatedMs, 0 );
    EXPECT_TRUE( rep.m_identityKey.empty() );
}

TEST(PromptFeatures, DefaultConstructor_AllFalse)
{
    PromptFeatures pf;
    EXPECT_FLOAT_EQ( pf.numeric_density_, 0.0f );
    EXPECT_FALSE( pf.has_code_syntax_ );
    EXPECT_FLOAT_EQ( pf.complexity_, 0.0f );
    EXPECT_EQ( pf.token_count_, 0 );
    EXPECT_FALSE( pf.has_math_keywords_ );
    EXPECT_FALSE( pf.has_grammar_request_ );
    EXPECT_FALSE( pf.has_grounding_request_ );
    EXPECT_FALSE( pf.has_formatting_request_ );
}

TEST(KnowledgeFact, DefaultConstructor_ReasonableDefaults)
{
    KnowledgeFact fact;
    EXPECT_FLOAT_EQ( fact.m_relevanceScore, 0.0f );
    EXPECT_TRUE( fact.m_source.empty() );
    EXPECT_TRUE( fact.m_content.empty() );
}

// ---------------------------------------------------------------------------
// Phase 8 — GAML v1 Memory Types (GAML-01, GAML-02)
// ---------------------------------------------------------------------------

TEST(MemoryObjectType, EnumValues_AreDistinct)
{
    // Verify 5 distinct values for 5 subtypes (D-02)
    EXPECT_EQ(static_cast<int>(MemoryObjectType::bridge_block), 0);
    EXPECT_EQ(static_cast<int>(MemoryObjectType::fact), 1);
    EXPECT_EQ(static_cast<int>(MemoryObjectType::policy), 2);
    EXPECT_EQ(static_cast<int>(MemoryObjectType::event), 3);
    EXPECT_EQ(static_cast<int>(MemoryObjectType::tenant_operational), 4);
}

TEST(TrustClass, EnumValues_AreDistinct)
{
    // Verify 4 distinct values (D-01, D-09)
    EXPECT_EQ(static_cast<int>(TrustClass::UNVERIFIED), 0);
    EXPECT_EQ(static_cast<int>(TrustClass::VERIFIED), 1);
    EXPECT_EQ(static_cast<int>(TrustClass::PREMIUM), 2);
    EXPECT_EQ(static_cast<int>(TrustClass::REPLICA), 3);
}

TEST(MemoryObjectType, IsScopedEnum)
{
    // Verify scoped enum — unqualified names should not compile
    // (This test simply verifies the values exist in scoped form)
    MemoryObjectType t = MemoryObjectType::fact;
    EXPECT_EQ(static_cast<int>(t), 1);
}

TEST(TrustClass, IsScopedEnum)
{
    TrustClass t = TrustClass::UNVERIFIED;
    EXPECT_EQ(static_cast<int>(t), 0);
}

TEST(MemoryObjectType, UnderlyingTypeIsUint8)
{
    // sizeof(uint8_t) == 1, scoped enums with : uint8_t should also be 1 byte
    EXPECT_EQ(sizeof(MemoryObjectType), 1);
}

TEST(TrustClass, UnderlyingTypeIsUint8)
{
    EXPECT_EQ(sizeof(TrustClass), 1);
}

// ---------------------------------------------------------------------------
// Phase 8 — CognitiveAsset default construction (GAML-01)
// ---------------------------------------------------------------------------

TEST(CognitiveAsset, DefaultConstruction)
{
    CognitiveAsset a;
    EXPECT_TRUE(a.m_id.empty());
    EXPECT_TRUE(a.m_entity.empty());
    EXPECT_EQ(a.m_type, MemoryObjectType::fact);
    EXPECT_EQ(a.m_timestamp, 0);
    EXPECT_FLOAT_EQ(a.m_confidence, 0.0f);
    EXPECT_FLOAT_EQ(a.m_provenance, 0.0f);
    EXPECT_EQ(a.m_trustClass, TrustClass::UNVERIFIED);
    EXPECT_TRUE(a.m_sourceNode.empty());
}

TEST(CognitiveAsset, DesignatedInitialization)
{
    CognitiveAsset a{
        .m_id = "test-001",
        .m_entity = "physics",
        .m_type = MemoryObjectType::fact,
        .m_timestamp = 1000,
        .m_sourceNode = "node-1",
        .m_confidence = 0.85f,
        .m_provenance = 0.6f,
        .m_trustClass = TrustClass::VERIFIED,
    };
    EXPECT_EQ(a.m_id, "test-001");
    EXPECT_EQ(a.m_entity, "physics");
    EXPECT_EQ(a.m_type, MemoryObjectType::fact);
    EXPECT_EQ(a.m_timestamp, 1000);
    EXPECT_FLOAT_EQ(a.m_confidence, 0.85f);
    EXPECT_EQ(a.m_sourceNode, "node-1");
}

TEST(ExecutionChain, NeedsRetrievalDefaultsToFalse)
{
    ExecutionChain chain;
    EXPECT_FALSE(chain.m_needsRetrieval);
}

TEST(ELMContext, MemoryFieldsDefaultEmpty)
{
    ELMContext ctx;
    EXPECT_TRUE(ctx.m_memoryFacts.empty());
    EXPECT_TRUE(ctx.m_memoryPolicies.empty());
}

TEST(MemoryContext, EmptyByDefault)
{
    MemoryContext mctx;
    EXPECT_TRUE(mctx.m_facts.empty());
    EXPECT_TRUE(mctx.m_policies.empty());
}

// ---------------------------------------------------------------------------
// Phase 8 — JSON serialization roundtrip (GAML-01)
// ---------------------------------------------------------------------------

static std::string SerializeCognitiveAsset(const CognitiveAsset& obj)
{
    nlohmann::json j;
    j["id"] = obj.m_id;
    j["entity"] = obj.m_entity;
    j["type"] = static_cast<int>(obj.m_type);
    j["payload"] = obj.m_payload;
    j["timestamp"] = obj.m_timestamp;
    j["source_node"] = obj.m_sourceNode;
    j["confidence"] = obj.m_confidence;
    j["provenance"] = obj.m_provenance;
    j["trust_class"] = static_cast<int>(obj.m_trustClass);
    return j.dump();
}

static CognitiveAsset DeserializeCognitiveAsset(const std::string& data)
{
    auto j = nlohmann::json::parse(data);
    CognitiveAsset obj;
    obj.m_id = j.value("id", "");
    obj.m_entity = j.value("entity", "");
    obj.m_type = static_cast<MemoryObjectType>(j.value("type", 0));
    obj.m_payload = j.value("payload", nlohmann::json::object());
    obj.m_timestamp = j.value("timestamp", int64_t(0));
    obj.m_sourceNode = j.value("source_node", "");
    obj.m_confidence = j.value("confidence", 0.0f);
    obj.m_provenance = j.value("provenance", 0.0f);
    obj.m_trustClass = static_cast<TrustClass>(j.value("trust_class", 0));
    return obj;
}

TEST(CognitiveAsset, JsonSerializationRoundtrip)
{
    CognitiveAsset original;
    original.m_id = "roundtrip-1";
    original.m_entity = "chemistry";
    original.m_type = MemoryObjectType::fact;
    original.m_payload = nlohmann::json::object({{"content", "H2O is water"}});
    original.m_timestamp = 1234567890;
    original.m_sourceNode = "node-XYZ";
    original.m_confidence = 0.75f;
    original.m_provenance = 0.5f;
    original.m_trustClass = TrustClass::VERIFIED;

    std::string serialized = SerializeCognitiveAsset(original);
    auto restored = DeserializeCognitiveAsset(serialized);

    EXPECT_EQ(restored.m_id, "roundtrip-1");
    EXPECT_EQ(restored.m_entity, "chemistry");
    EXPECT_EQ(restored.m_type, MemoryObjectType::fact);
    EXPECT_EQ(restored.m_timestamp, 1234567890);
    EXPECT_EQ(restored.m_sourceNode, "node-XYZ");
    EXPECT_FLOAT_EQ(restored.m_confidence, 0.75f);
    EXPECT_FLOAT_EQ(restored.m_provenance, 0.5f);
    EXPECT_EQ(restored.m_trustClass, TrustClass::VERIFIED);
    EXPECT_EQ(restored.m_payload["content"], "H2O is water");
}

TEST(ELMRole, EnumValues_AreDistinct)
{
    EXPECT_NE( static_cast<int>( ELMRole::Planner ), static_cast<int>( ELMRole::PrimaryDraft ) );
    EXPECT_NE( static_cast<int>( ELMRole::Verifier ), static_cast<int>( ELMRole::Arbiter ) );
    EXPECT_NE( static_cast<int>( ELMRole::Refiner ), static_cast<int>( ELMRole::Grounding ) );
    EXPECT_NE( static_cast<int>( ELMRole::ToolSupport ), static_cast<int>( ELMRole::Math ) );
    EXPECT_NE( static_cast<int>( ELMRole::Code ), static_cast<int>( ELMRole::Science ) );
}

TEST(ExecutionMode, ElmAssistedValue_IsDistinct)
{
    EXPECT_NE( static_cast<int>( ExecutionMode::ElmAssisted ), static_cast<int>( ExecutionMode::SingleNode ) );
    EXPECT_NE( static_cast<int>( ExecutionMode::ElmAssisted ), static_cast<int>( ExecutionMode::Specialist ) );
    EXPECT_NE( static_cast<int>( ExecutionMode::ElmAssisted ), static_cast<int>( ExecutionMode::Swarm ) );
}

TEST(ELMContext, DefaultConstructor_HasReasonableDefaults)
{
    ELMContext ctx;
    EXPECT_TRUE( ctx.m_originalTask.empty() );
    EXPECT_TRUE( ctx.m_stepConfidences.empty() );
    EXPECT_TRUE( ctx.m_groundingFacts.empty() );
}

TEST(ChainStep, DefaultConstructor_HasReasonableDefaults)
{
    ChainStep step;
    EXPECT_EQ( step.m_role, ELMRole::PrimaryDraft );
    EXPECT_FALSE( step.m_domain.has_value() );
}

TEST(ExecutionChain, DefaultConstructor_HasReasonableDefaults)
{
    ExecutionChain chain;
    EXPECT_TRUE( chain.m_steps.empty() );
    EXPECT_TRUE( chain.m_reasoning.empty() );
    EXPECT_FLOAT_EQ( chain.m_chainConfidence, 0.0f );
}
