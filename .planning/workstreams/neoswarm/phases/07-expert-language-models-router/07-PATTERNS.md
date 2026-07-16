# Phase 07: Expert Language Models + Router - Pattern Map

**Mapped:** 2026-07-16
**Files analyzed:** 18 (11 new, 7 modified)
**Analogs found:** 18 / 18

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/elm/i_elm.hpp` | interface | request-response | `src/specialists/i_specialist.hpp` | exact (I-prefix abstract class, outcome::result signatures) |
| `src/elm/role_elm.hpp` | service | transform | `src/specialists/grammar_specialist.hpp` | exact (prompt-template + engine→Infer, same member layout) |
| `src/elm/role_elm.cpp` | service | transform | `src/specialists/grammar_specialist.cpp` | exact (BuildPrompt + Task construction + Infer + confidence) |
| `src/elm/domain_elm.hpp` | service | transform | `src/specialists/math_specialist.hpp` | exact (optional own engine, configurable model path, same structure) |
| `src/elm/domain_elm.cpp` | service | transform | `src/specialists/math_specialist.cpp` | exact (Load, BuildPrompt, Process, confidence computation) |
| `src/elm/grounding_elm.hpp` | service | pipeline-transform | `src/knowledge/knowledge_retrieval.hpp` + `src/api/api_server.hpp:AugmentPrompt` | role-match (composes knowledge/ pipeline + engine) |
| `src/elm/grounding_elm.cpp` | service | pipeline-transform | `src/api/api_server.cpp:204-217` (AugmentPrompt) + `grammar_specialist.cpp:56-81` (Process) | role-match (Retrieve→Inject→Infer→Validate ordering) |
| `src/elm/tool_support_elm.hpp` | service | request-response (stub) | `src/specialists/grammar_specialist.hpp` (simplified) | role-match (same interface, no engine, pass-through) |
| `src/elm/tool_support_elm.cpp` | service | request-response (stub) | `src/specialists/grammar_specialist.cpp:56-63` (not-loaded path) | partial (identical fail-close pattern: return input unchanged, confidence=0) |
| `src/elm/specialist_adapter.hpp` | adapter | request-response | `src/specialists/i_specialist.hpp` (composition target) + `src/api/api_server.hpp:116-117` (member pattern) | role-match (has-a ISpecialist, maps Process signatures) |
| `src/elm/specialist_adapter.cpp` | adapter | request-response | `src/specialists/grammar_specialist.cpp:22-25` (constructor DI pattern) | partial (simple delegation — composition of shared_ptr) |
| `src/elm/elm_chain_builder.hpp` | service | transform | `src/router/rule_based_router.hpp` | role-match (Config struct, constructor, single public method, private helpers) |
| `src/elm/elm_chain_builder.cpp` | service | transform | `src/router/rule_based_router.cpp` | role-match (feature-based decision tree, logging, outcome::result return) |
| `src/elm/CMakeLists.txt` | config | — | `src/specialists/CMakeLists.txt` | exact (STATIC library, PUBLIC include dirs, PUBLIC link libs) |
| `src/common/types.hpp` (modify) | model | — | `src/common/types.hpp` (existing structs) | exact (same naming conventions, member layout, doxygen style) |
| `src/router/prompt_analyzer.hpp` (modify) | service | transform | `src/router/prompt_analyzer.hpp` (existing methods) | exact (add to same class, same method signatures, same naming) |
| `src/router/prompt_analyzer.cpp` (modify) | service | transform | `src/router/prompt_analyzer.cpp` (existing HasGrammarRequest/HasMathKeywords patterns) | exact (copy keyword-detection pattern for grounding/formatting) |
| `src/api/api_server.hpp` (modify) | controller | request-response | `src/api/api_server.hpp:116-132` (existing member layout, private method signatures) | exact (same class, add RunELMChain + ELM registry members) |
| `src/api/api_server.cpp` (modify) | controller | request-response | `src/api/api_server.cpp:280-337` (RunSpecialist pattern) | exact (same class, sequential steps, outcome::result chain, logging) |
| `src/main.cpp` (modify) | config | file-I/O | `src/main.cpp:89-138` (LoadConfigFile JSON parsing pattern) | exact (nlohmann/json array iteration, args struct extension) |
| `test/elm/test_elm.cpp` | test | — | `test/specialists/test_grammar_specialist.cpp` | exact (MockEngine class, GTest fixture, happy/unhappy path tests) |
| `test/common/test_types.cpp` (modify) | test | — | `test/common/test_types.cpp` (existing enum/struct default-constructor tests) | exact (EXPECT_EQ on enum values, EXPECT_TRUE on defaults) |
| `test/integration/test_pipeline.cpp` (modify) | test | — | `test/integration/test_pipeline.cpp:13-56` (PipelineTest fixture, stub-mode Process tests) | exact (same fixture, add chain-mode test cases) |
| `test/CMakeLists.txt` (modify) | config | — | `test/CMakeLists.txt:42-53,69-70` (neoswarm_test macro, specialist test registration) | exact (copy macro invocation with neoswarm_elm library) |

## Pattern Assignments

---

### 1. `src/elm/i_elm.hpp` (interface, request-response)

**Analog:** `src/specialists/i_specialist.hpp` (lines 1-54)

**Why:** Both are `I`-prefix abstract interfaces with `outcome::result` signatures and identical semantics. ISpecialist has 5 virtuals (GetName, IsLoaded, Load, Process, GetConfidence); IELM adds `GetRole()` and changes `Process(input)` → `Process(input, ELMContext)`.

**Imports pattern** (lines 10-11):
```cpp
#include "common/error.hpp"
#include <string>
```

**Include guard pattern** (lines 7-8):
```cpp
#ifndef NEOSWARM_SPECIALISTS_ISPECIALIST_HPP
#define NEOSWARM_SPECIALISTS_ISPECIALIST_HPP
```
For IELM, use: `#ifndef NEOSWARM_ELM_IELM_HPP` / `#define NEOSWARM_ELM_IELM_HPP`

**Namespace pattern** (lines 13-14):
```cpp
namespace sgns::neoswarm::specialists
{
```
For IELM, use: `namespace sgns::neoswarm::elm`

**Interface class pattern** (lines 20-50):
```cpp
class ISpecialist
{
    public:
    virtual ~ISpecialist() = default;

    /// @return Human-readable name of this specialist.
    virtual std::string GetName() const = 0;

    /// @return True if the specialist model has been loaded.
    virtual bool IsLoaded() const = 0;

    /**
     * @brief Load the specialist model from disk.
     * @param model_path  Path to the model file.
     * @return            outcome::success or ModelLoadFailed.
     */
    virtual outcome::result<void> Load( const std::string& model_path ) = 0;

    /**
     * @brief Process input (typically Core LLM output) and return refined output.
     * @param input  Text to process.
     * @return       Refined text or InferenceFailed.
     */
    virtual outcome::result<std::string> Process( const std::string& input ) = 0;

    /**
     * @brief Confidence in the last Process() call.
     * @return  Confidence score in [0, 1].
     */
    virtual float GetConfidence() const = 0;
};
```

**Closing pattern** (lines 52-53):
```cpp
} // namespace sgns::neoswarm::specialists
#endif // NEOSWARM_SPECIALISTS_ISPECIALIST_HPP
```

**IELM adaptation:** Copy this exact structure but:
- Add `virtual ELMRole GetRole() const = 0;` between `GetName()` and `IsLoaded()`
- Change `Process(const std::string& input)` to `Process(const std::string& input, const ELMContext& context)`
- Forward-declare or include ELMRole and ELMContext from `common/types.hpp`

---

### 2. `src/elm/role_elm.hpp` (service, transform)

**Analog:** `src/specialists/grammar_specialist.hpp` (lines 1-53)

**Why:** RoleELM is a concrete IELM that holds a shared_ptr<InferenceEngine>, has m_loaded + last_confidence_ members, BuildPrompt private method, and a Configurable role template. Exactly the same structural pattern as GrammarSpecialist.

**Imports pattern** (lines 10-12):
```cpp
#include "i_elm.hpp"
#include "core/engine/inference_engine.hpp"
#include <memory>
```

**Class declaration pattern** (lines 22-49):
```cpp
class GrammarSpecialist : public ISpecialist
{
    public:
    explicit GrammarSpecialist( std::shared_ptr<core::InferenceEngine> engine = nullptr );

    std::string GetName() const override { return "GrammarSpecialist"; }
    bool IsLoaded() const override { return m_loaded; }

    outcome::result<void> Load( const std::string& model_path ) override;
    outcome::result<std::string> Process( const std::string& input ) override;
    float GetConfidence() const override { return last_confidence_; }

    private:
    std::shared_ptr<core::InferenceEngine> m_engine;
    bool m_loaded = false;
    float last_confidence_ = 0.0f;

    std::string BuildPrompt( const std::string& input ) const;
};
```

**RoleELM adaptation:** 
- Inherit from `IELM` not `ISpecialist`
- Add `ELMRole m_role;` member
- Add `std::string m_name;` member (constructed from role name)
- Add constructor `RoleELM(ELMRole role, std::shared_ptr<core::InferenceEngine> engine = nullptr)`
- `GetName()` returns `m_name`
- `GetRole()` returns `m_role`
- `Process()` signature: `outcome::result<std::string> Process( const std::string& input, const ELMContext& context ) override;`
- `BuildPrompt(const std::string& input, const ELMContext& context) const` (takes context to inject prior outputs)

---

### 3. `src/elm/role_elm.cpp` (service, transform)

**Analog:** `src/specialists/grammar_specialist.cpp` (lines 1-83)

**Why:** The Process() method follows the exact pattern needed: check loaded/engine → BuildPrompt → create Task → Infer → compute confidence → return output or fail-close. Every RoleELM (Planner, PrimaryDraft, Verifier, Arbiter, Refiner) is just this with a different prompt template.

**Logger pattern** (lines 14-19):
```cpp
namespace
{
    auto GrammarLogger()
    {
        return neoswarm::CreateLogger( "GrammarSpecialist" );
    }
} // namespace
```
For RoleELM: use `neoswarm::CreateLogger("RoleELM/" + roleName)` or similar tagged logger.

**Constructor pattern** (lines 22-25):
```cpp
GrammarSpecialist::GrammarSpecialist( std::shared_ptr<core::InferenceEngine> engine )
    : m_engine( std::move( engine ) )
{
}
```

**Load pattern** (lines 30-40):
```cpp
outcome::result<void> GrammarSpecialist::Load( const std::string& model_path )
{
    if ( !m_engine )
    {
        return outcome::failure( Error::ModelLoadFailed );
    }
    BOOST_OUTCOME_TRY( m_engine->LoadModel( model_path ) );
    m_loaded = true;
    GrammarLogger()->info( "GrammarSpecialist loaded: {}", model_path );
    return outcome::success();
}
```

**BuildPrompt pattern** (lines 45-51):
```cpp
std::string GrammarSpecialist::BuildPrompt( const std::string& input ) const
{
    return "[INST] Correct the grammar, spelling, and fluency of the following text. "
           "Return only the corrected text without explanation.\n\n"
           "Text: " + input + "\n\nCorrected: [/INST]";
}
```
For RoleELM: Use `[INST] You are a {role_name}. {role instructions}... [/INST]` template format.

**Process pattern** (lines 56-81) — **this is the core pattern to replicate**:
```cpp
outcome::result<std::string> GrammarSpecialist::Process( const std::string& input )
{
    if ( !m_loaded || !m_engine )
    {
        GrammarLogger()->warn( "GrammarSpecialist not loaded — returning input unchanged" );
        last_confidence_ = 0.0f;
        return outcome::success( input );
    }

    Task task;
    task.m_id = "grammar-" + std::to_string( std::hash<std::string>{}( input ) );
    task.m_prompt = BuildPrompt( input );
    task.m_maxTokens = static_cast<uint32_t>( input.size() + 64 );
    task.m_temperature = 0.1f;

    auto res = m_engine->Infer( task );
    if ( !res.has_value() )
    {
        GrammarLogger()->warn( "GrammarSpecialist inference failed — returning input unchanged" );
        last_confidence_ = 0.0f;
        return outcome::success( input );
    }

    last_confidence_ = 1.0f - std::min( res.value().m_perplexity / 10.0f, 1.0f );
    return outcome::success( res.value().m_output );
}
```

**RoleELM adaptation:**
- Task ID prefix changes per role: `"planner-"`, `"verifier-"`, etc.
- `BuildPrompt(input, context)` — uses `context.m_lastOutput` and `context.m_originalTask` in template
- Same fail-close: return `input` unchanged on not-loaded or inference failure

---

### 4. `src/elm/domain_elm.hpp` + `src/elm/domain_elm.cpp` (service, transform)

**Analog:** `src/specialists/math_specialist.hpp` (lines 1-56) + `math_specialist.cpp` (lines 1-118)

**Why:** Domain ELMs may own a dedicated MNNInferenceEngine instance (separate `.mnn` file) instead of sharing the backbone. MathSpecialist has the same pattern of optional-engine + own model loading + BuildPrompt + Process flow.

**Key structural difference from RoleELM:** DomainELM has TWO engine references:
- `m_sharedEngine` (shared_ptr) — used when no dedicated model path
- `m_ownEngine` (unique_ptr) — created when config provides a model path

**Constructor pattern** (math_specialist.cpp:22-25):
```cpp
MathSpecialist::MathSpecialist( std::shared_ptr<core::InferenceEngine> engine )
    : m_engine( std::move( engine ) )
{
}
```

**Load pattern for DomainELM** (Conceptual — extends grammar Load with own-engine creation):
```cpp
outcome::result<void> DomainELM::Load( const std::string& model_path )
{
    if ( !model_path.empty() )
    {
        // Create own engine (unique_ptr) for this domain
        m_ownEngine = std::make_unique<core::MNNInferenceEngine>(...);
        BOOST_OUTCOME_TRY( m_ownEngine->LoadModel( model_path ) );
        m_loaded = true;
        return outcome::success();
    }
    // Fall back to shared backbone
    if ( !m_sharedEngine )
    {
        return outcome::failure( Error::ModelLoadFailed );
    }
    m_loaded = true; // Shared engine is already loaded by ApiServer
    return outcome::success();
}
```

**Process pattern for DomainELM** (same as role_elm but uses ownEngine if available):
```cpp
auto& engine = m_ownEngine ? m_ownEngine : m_sharedEngine;
auto res = engine->Infer( task );
```

---

### 5. `src/elm/grounding_elm.hpp` + `src/elm/grounding_elm.cpp` (service, pipeline-transform)

**Analog:** `src/api/api_server.cpp:204-217` (AugmentPrompt) + `src/specialists/grammar_specialist.cpp:56-81` (Process flow)

**Why:** GroundingELM wraps the existing 3-stage knowledge pipeline (Retrieve → Inject → Infer → Validate) behind the IELM interface. The AugmentPrompt method in ApiServer already does stages 1-2; GrammarSpecialist::Process covers stages 3-4 with confidence.

**Pipeline composition pattern** (api_server.cpp:204-217):
```cpp
std::string ApiServer::AugmentPrompt( const std::string& prompt, std::vector<KnowledgeFact>& out_facts ) const
{
    if ( !m_knowledge || !m_knowledge->IsLoaded() || !m_contextInj )
    {
        return prompt;
    }
    auto facts_res = m_knowledge->Retrieve( prompt );
    if ( !facts_res.has_value() || facts_res.value().empty() )
    {
        return prompt;
    }
    out_facts = facts_res.value();
    return m_contextInj->Inject( prompt, out_facts );
}
```

**GroundingELM::Process() flow** (replicates stages 1-4 in sequence):
```
1. m_knowledge->Retrieve(input) → facts
2. m_contextInj->Inject(input, facts) → augmented prompt
3. m_engine->Infer(augmentedPrompt) → output
4. m_factVal->Validate(output, facts) → validation result
5. If contradiction: log warning, set low confidence
6. Return output + confidence
```

**Members needed:**
```cpp
std::shared_ptr<core::InferenceEngine> m_engine;
std::shared_ptr<knowledge::KnowledgeRetrieval> m_knowledge;
std::unique_ptr<knowledge::ContextInjection> m_contextInj;
std::unique_ptr<knowledge::FactValidation> m_factVal;
```

**Confidence pattern** (grammar_specialist.cpp:79):
```cpp
last_confidence_ = 1.0f - std::min( res.value().m_perplexity / 10.0f, 1.0f );
```
For GroundingELM: If validation finds contradictions, multiply confidence by (1.0 - contradictionScore).

---

### 6. `src/elm/tool_support_elm.hpp` + `src/elm/tool_support_elm.cpp` (service, request-response stub)

**Analog:** `src/specialists/grammar_specialist.cpp:56-63` (not-loaded fail-close path)

**Why:** ToolSupportELM is a pure stub — every call returns the input unchanged with confidence=0 and logs "not implemented". This is exactly what GrammarSpecialist does when `!m_loaded || !m_engine`.

**Fail-close pattern** (grammar_specialist.cpp:56-63):
```cpp
if ( !m_loaded || !m_engine )
{
    GrammarLogger()->warn( "GrammarSpecialist not loaded — returning input unchanged" );
    last_confidence_ = 0.0f;
    return outcome::success( input );
}
```

**ToolSupportELM::Process()** — the entire implementation:
```cpp
outcome::result<std::string> ToolSupportELM::Process( const std::string& input, const ELMContext& /*ctx*/ )
{
    ToolLogger()->warn( "ToolSupportELM not implemented — returning input unchanged" );
    m_lastConfidence = 0.0f;
    return outcome::success( input );
}
```

**IsLoaded()** returns `false` always. **Load()** returns `outcome::success()` (no-op).

---

### 7. `src/elm/specialist_adapter.hpp` + `src/elm/specialist_adapter.cpp` (adapter, request-response)

**Analog:** `src/specialists/i_specialist.hpp` (target interface signatures, lines 38-43) + `src/api/api_server.hpp:116-117` (shared_ptr member composition pattern)

**Why:** The adapter maps `IELM::Process(input, ELMContext)` → `ISpecialist::Process(input)`. It drops the ELMContext parameter and delegates directly. Composition via shared_ptr<ISpecialist> member.

**ISpecialist::Process signature** (i_specialist.hpp:43):
```cpp
virtual outcome::result<std::string> Process( const std::string& input ) = 0;
```

**Adapter delegation** — the core mapping:
```cpp
outcome::result<std::string> SpecialistAdapter::Process( const std::string& input, const ELMContext& /*ctx*/ )
{
    return m_specialist->Process( input );
}
```

**Construction with dependency injection** (copy grammar_specialist.cpp:22-25 DI pattern):
```cpp
SpecialistAdapter::SpecialistAdapter( std::shared_ptr<ISpecialist> specialist, ELMRole role, const std::string& name )
    : m_specialist( std::move( specialist ) )
    , m_role( role )
    , m_name( name )
{
}
```

**Member layout** (copy api_server.hpp:116-117 shared_ptr member pattern):
```cpp
private:
    std::shared_ptr<specialists::ISpecialist> m_specialist;
    ELMRole m_role;
    std::string m_name;
    float m_lastConfidence = 0.0f;
```

**Delegated methods** (simply forward):
```cpp
std::string GetName() const override { return m_name; }
ELMRole GetRole() const override { return m_role; }
bool IsLoaded() const override { return m_specialist && m_specialist->IsLoaded(); }
float GetConfidence() const override { return m_lastConfidence; }
outcome::result<void> Load( const std::string& model_path ) override {
    return m_specialist->Load( model_path );
}
```

---

### 8. `src/elm/elm_chain_builder.hpp` + `src/elm/elm_chain_builder.cpp` (service, transform)

**Analog:** `src/router/rule_based_router.hpp` (lines 1-59) + `src/router/rule_based_router.cpp` (lines 1-102)

**Why:** Both are stateless decision-tree classes that take input features and produce structured output. RuleBasedRouter has a Config struct, constructor overloads, a single public method, and private helper methods. ELMChainBuilder follows the exact same pattern, just mapping RouteDecision + PromptFeatures → ExecutionChain instead of Task → RouteDecision.

**Header pattern** (rule_based_router.hpp:24-55):
```cpp
class RuleBasedRouter : public IRouter
{
    public:
    struct Config
    {
        float numeric_density_threshold_ = 0.30f;
        float complexity_swarm_threshold_ = 5.0f;
        bool enable_swarm_m_mode = true;
    };

    RuleBasedRouter();
    explicit RuleBasedRouter( Config cfg );

    outcome::result<RouteDecision> Route( const Task& task ) override;

    private:
    Config m_cfg;
    PromptAnalyzer m_analyzer;

    ExecutionMode SelectMode( const PromptFeatures& features, ExecutionMode requested ) const;
};
```

**ELMChainBuilder adaptation:**
```cpp
class ELMChainBuilder
{
    public:
    struct Config
    {
        float numeric_density_threshold_ = 0.30f;
        float complexity_high_threshold_ = 5.0f;
        float complexity_low_threshold_ = 2.0f;
        float confidence_threshold_ = 0.6f;
    };

    ELMChainBuilder();
    explicit ELMChainBuilder( Config cfg );

    outcome::result<ExecutionChain> Build( const RouteDecision& decision, const PromptFeatures& features );

    private:
    Config m_cfg;
};
```

**Implementation pattern** (rule_based_router.cpp:1-102):
- Anonymous namespace logger: `CreateLogger("ELMChainBuilder")`
- Two constructors (default + Config)
- `Route()` → `Build()` — decision-tree logic with if/else chains
- Logging at end: `Logger()->debug(...)` with format args

**Decision tree for Build()** (replicates rule_based_router.cpp:63-99 heuristic pattern):
```cpp
outcome::result<ExecutionChain> ELMChainBuilder::Build( const RouteDecision& decision, const PromptFeatures& features )
{
    ExecutionChain chain;

    if ( features.numeric_density_ > m_cfg.numeric_density_threshold_ )
    {
        chain.m_steps.push_back( { ELMRole::Math, "math" } );
        chain.m_steps.push_back( { ELMRole::Verifier } );
        chain.m_reasoning = "High numeric density — routing to Math + Verifier";
    }
    else if ( features.has_code_syntax_ )
    {
        chain.m_steps.push_back( { ELMRole::Planner } );
        chain.m_steps.push_back( { ELMRole::Code, "code" } );
        chain.m_reasoning = "Code syntax detected — Planner → Code domain";
    }
    else if ( features.has_grounding_request_ )
    {
        chain.m_steps.push_back( { ELMRole::Grounding } );
        chain.m_steps.push_back( { ELMRole::PrimaryDraft } );
        chain.m_steps.push_back( { ELMRole::Verifier } );
        chain.m_reasoning = "Grounding-sensitive — Grounding → Draft → Verify";
    }
    else if ( features.has_formatting_request_ )
    {
        chain.m_steps.push_back( { ELMRole::PrimaryDraft } );
        chain.m_steps.push_back( { ELMRole::Refiner } );
        chain.m_reasoning = "Formatting-sensitive — Draft → Refiner";
    }
    else if ( features.complexity_ < m_cfg.complexity_low_threshold_ )
    {
        chain.m_steps.push_back( { ELMRole::PrimaryDraft } );
        chain.m_reasoning = "Low complexity — single-step draft";
    }
    else if ( features.complexity_ >= m_cfg.complexity_high_threshold_ )
    {
        chain.m_steps.push_back( { ELMRole::Planner } );
        // domain determined from other features, default to PrimaryDraft for general
        chain.m_steps.push_back( { ELMRole::PrimaryDraft } );
        chain.m_steps.push_back( { ELMRole::Verifier } );
        chain.m_steps.push_back( { ELMRole::Refiner } );
        chain.m_reasoning = "High complexity — Planner → Draft → Verify → Refine";
    }
    else
    {
        chain.m_steps.push_back( { ELMRole::PrimaryDraft } );
        chain.m_reasoning = "Default — single-step draft";
    }

    chain.m_chainConfidence = decision.confidence_;
    BuilderLogger()->debug( "Chain: {} steps, reason='{}'", chain.m_steps.size(), chain.m_reasoning );
    return outcome::success( std::move( chain ) );
}
```

---

### 9. `src/elm/CMakeLists.txt` (config)

**Analog:** `src/specialists/CMakeLists.txt` (lines 1-12)

**Why:** Exact same pattern — STATIC library, PUBLIC include dirs, PUBLIC link deps. ELM library depends on neoswarm_common, neoswarm_core, neoswarm_knowledge.

**Template to copy:**
```cmake
add_library(neoswarm_elm STATIC
    role_elm.cpp
    domain_elm.cpp
    grounding_elm.cpp
    tool_support_elm.cpp
    specialist_adapter.cpp
    elm_chain_builder.cpp
)

target_include_directories(neoswarm_elm PUBLIC
    $<BUILD_INTERFACE:${PROJECT_ROOT}/src>
    $<INSTALL_INTERFACE:include>
)

target_link_libraries(neoswarm_elm PUBLIC neoswarm_common neoswarm_core neoswarm_knowledge neoswarm_specialists)
```

**src/CMakeLists.txt addition** (copy line 9 pattern):
```cmake
add_subdirectory(${CMAKE_CURRENT_LIST_DIR}/elm ${CMAKE_CURRENT_BINARY_DIR}/elm)
```

---

### 10. `src/common/types.hpp` (MODIFY — add ELMRole, ELMContext, ExecutionChain)

**Analog:** `src/common/types.hpp` itself (lines 20-25 for enum, 41-49 for Task struct, 82-90 for PromptFeatures struct)

**Why:** The file already contains Enums (ExecutionMode, RouteTarget) and structs (Task, InferenceResponse, RouteDecision, PromptFeatures) with the exact conventions to follow.

**Enum pattern** (lines 20-25):
```cpp
enum class ExecutionMode : uint8_t
{
    SingleNode = 0, ///< Mode 1 — Core LLM only, fast
    Specialist = 1, ///< Mode 2 — Core + Grammar/Math, sequential
    Swarm = 2       ///< Mode 3 — Multiple nodes, weighted consensus
};
```

**New ELMRole enum** (add after RouteTarget enum, before Task struct):
```cpp
// -----------------------------------------------------------------------
// ELM roles (doc 03 §5.2.1)
// -----------------------------------------------------------------------
enum class ELMRole : uint8_t
{
    Planner = 0,      ///< Analyses task, determines execution plan
    PrimaryDraft = 1, ///< Core draft generation (shared backbone)
    Verifier = 2,     ///< Reviews outputs for correctness
    Arbiter = 3,      ///< Resolves conflicts between outputs
    Refiner = 4,      ///< Polishes formatting, style, grammar
    Grounding = 5,    ///< Fact-checks against knowledge base
    ToolSupport = 6,  ///< Tool-call formatting (stub in Phase 7)
    Math = 7,         ///< Domain ELM — math
    Code = 8,         ///< Domain ELM — code
    Science = 9       ///< Domain ELM — science (shared-backbone only in Phase 7)
};
```

**Add Chain to ExecutionMode** (line 23, after `Swarm = 2`):
```cpp
    Swarm = 2,  ///< Mode 3 — Multiple nodes, weighted consensus
    Chain = 3   ///< Mode 4 — Multi-step ELM chain (Phase 7+)
```

**Struct pattern** (lines 41-49 for Task):
```cpp
struct Task
{
    std::string m_id;
    std::string m_prompt;
    ExecutionMode m_mode = ExecutionMode::SingleNode;
    uint32_t m_maxTokens = 512;
    float m_temperature = 0.7f;
    std::string m_nodeId; ///< originating node
};
```

**New ELMContext struct** (add after PromptFeatures struct):
```cpp
// -----------------------------------------------------------------------
// ELM execution context (doc 03 §5.2.1)
// -----------------------------------------------------------------------
struct ELMContext
{
    std::string m_originalTask;                                   ///< the user's original prompt
    std::string m_lastOutput;                                     ///< output of the immediately prior step
    std::vector<std::pair<ELMRole, float>> m_stepConfidences;     ///< (role, confidence) per completed step
    std::vector<KnowledgeFact> m_groundingFacts;                  ///< facts from GroundingELM, if any
};
```

**New ChainStep + ExecutionChain structs** (add after ELMContext):
```cpp
// -----------------------------------------------------------------------
// Chain step and execution chain (doc 03 §6.2)
// -----------------------------------------------------------------------
struct ChainStep
{
    ELMRole m_role = ELMRole::PrimaryDraft;
    std::optional<std::string> m_domain; ///< e.g. "math", "code" — for domain ELMs
};

struct ExecutionChain
{
    std::vector<ChainStep> m_steps;
    std::string m_reasoning;          ///< why this chain was chosen
    float m_chainConfidence = 0.0f;   ///< builder's confidence in this chain
};
```

**New features** (add to PromptFeatures struct, lines 89-90):
```cpp
    bool has_grounding_request_ = false;    ///< factual verification request detected
    bool has_formatting_request_ = false;   ///< structure/style formatting request detected
```

**Include needed:** Add `#include <optional>` — already present at line 10.

---

### 11. `src/router/prompt_analyzer.hpp` + `prompt_analyzer.cpp` (MODIFY)

**Analog:** `src/router/prompt_analyzer.hpp:57-62` (HasGrammarRequest private method) — copy this pattern for new detectors

**Why:** Two new feature detectors needed (`HasGroundingRequest`, `HasFormattingRequest`). The existing `HasGrammarRequest` method (lines 57-62) shows the exact keyword-detection pattern.

**Header additions** (copy HasGrammarRequest pattern at lines 57-62):
```cpp
/**
 * @brief Check for grounding/factuality verification requests.
 * @param prompt  Input string.
 * @return        True if grounding keywords are present.
 */
bool HasGroundingRequest( const std::string& prompt ) const;

/**
 * @brief Check for formatting/structure/style requests.
 * @param prompt  Input string.
 * @return        True if formatting keywords are present.
 */
bool HasFormattingRequest( const std::string& prompt ) const;
```

**Implementation pattern** — replicate HasGrammarRequest keyword-detection logic from `prompt_analyzer.cpp`:

For `HasGroundingRequest`: Look for keywords: "is it true", "verify", "according to", "fact check", "factual", "evidence", "source", "citation", "is this correct"

For `HasFormattingRequest`: Look for keywords: "format as", "make this look", "structure this", "organize", "write as", "rewrite in", "convert to", "summarize", "bullet", "outline", "markdown", "json format"

**Analyze() update** — add the two new feature extractions after existing features (lines in prompt_analyzer.cpp):
```cpp
features.has_grounding_request_ = HasGroundingRequest( prompt );
features.has_formatting_request_ = HasFormattingRequest( prompt );
```

---

### 12. `src/api/api_server.hpp` (MODIFY — add RunELMChain + ELM registry)

**Analog:** `src/api/api_server.hpp:116-132` (existing member and method layout)

**Why:** The ApiServer already has private methods RunSingleNode/RunSpecialist/RunSwarm (lines 130-132) and member variables for specialists (lines 116-117). Add RunELMChain alongside them, following the same conventions.

**New members** — add after m_sgClient (line 128):
```cpp
// ELM registry (Phase 7+)
std::unordered_map<ELMRole, std::shared_ptr<elm::IELM>> m_elmRegistry;
std::unique_ptr<elm::ELMChainBuilder> m_chainBuilder;
```

**New private method** — add after RunSwarm (line 133):
```cpp
outcome::result<InferenceResponse> RunELMChain( const Task& task, const RouteDecision& route );
```

**New include** — add after router include (line 22):
```cpp
#include "elm/i_elm.hpp"
#include "elm/elm_chain_builder.hpp"
```

**Config struct extension** (add to Config struct, lines 50-66):
```cpp
struct ElmEntry
{
    std::string role;     ///< e.g. "planner", "verifier", "math"
    std::string model;    ///< optional dedicated model path
    bool eager = false;   ///< load at Initialize() vs lazy
};
std::vector<ElmEntry> m_elmConfigs;
```

---

### 13. `src/api/api_server.cpp` (MODIFY — RunELMChain, Initialize ELMs, Process switch)

**Analog:** `src/api/api_server.cpp:280-337` (RunSpecialist pattern) — **the primary pattern to replicate**

**Why:** RunELMChain is the sequential chain version of RunSpecialist. Same structure: timing, AugmentPrompt, step-by-step execution, error handling, fact validation, response construction.

**RunELMChain pattern** (conceptual, based on RunSpecialist + sequential loop):
```cpp
outcome::result<InferenceResponse> ApiServer::RunELMChain( const Task& task, const RouteDecision& route )
{
    auto t0 = std::chrono::steady_clock::now();

    std::vector<KnowledgeFact> facts;
    Task aug_task = task;
    aug_task.m_prompt = AugmentPrompt( task.m_prompt, facts );

    ELMContext context;
    context.m_originalTask = task.m_prompt;
    context.m_stepConfidences.reserve( 8 );

    std::string currentOutput = aug_task.m_prompt;
    float aggregateConfidence = 1.0f;

    auto chainResult = m_chainBuilder->Build( route, /* features */ );
    if ( !chainResult.has_value() )
    {
        return outcome::failure( chainResult.error() );
    }

    for ( const auto& step : chainResult.value().m_steps )
    {
        context.m_lastOutput = currentOutput;
        context.m_groundingFacts = facts;

        auto it = m_elmRegistry.find( step.m_role );
        if ( it == m_elmRegistry.end() || !it->second )
        {
            ServerLogger()->warn( "ELM not found for role {}", static_cast<int>( step.m_role ) );
            continue;
        }

        auto elm = it->second;
        if ( !elm->IsLoaded() )
        {
            ServerLogger()->warn( "ELM {} not loaded — skipping step", elm->GetName() );
            continue;
        }

        auto stepRes = elm->Process( currentOutput, context );
        if ( !stepRes.has_value() )
        {
            ServerLogger()->warn( "ELM {} failed — stopping chain", elm->GetName() );
            break;
        }

        currentOutput = stepRes.value();
        float stepConf = elm->GetConfidence();
        context.m_stepConfidences.push_back( { step.m_role, stepConf } );
        aggregateConfidence = std::min( aggregateConfidence, stepConf );

        ServerLogger()->debug( "Chain step {} completed (confidence={:.2f})", elm->GetName(), stepConf );
    }

    auto t1 = std::chrono::steady_clock::now();
    double total_ms = std::chrono::duration<double, std::milli>( t1 - t0 ).count();

    // Fact validation (copy from RunSpecialist.cpp:314-325)
    if ( m_factVal && m_factVal->IsAvailable() )
    {
        // ... same validation pattern as RunSpecialist
    }

    InferenceResponse resp;
    resp.m_output = currentOutput;
    resp.m_taskId = task.m_id;
    resp.m_modeUsed = ExecutionMode::Chain;
    resp.m_routeUsed = route.m_target;
    resp.m_totalLatencyMs = total_ms;
    resp.m_success = true;
    resp.m_perplexity = 1.0f - aggregateConfidence; // invert: low conf = high perplexity

    return outcome::success( std::move( resp ) );
}
```

**Process() switch addition** (api_server.cpp:448-456, add case for Chain):
```cpp
    case ExecutionMode::Chain:
        return RunELMChain( t, route );
```

**Initialize() ELM setup** (add after specialist init, around lines 80-95):
```cpp
// ELM registry (Phase 7+)
m_chainBuilder = std::make_unique<elm::ELMChainBuilder>();

// Register role ELMs with shared backbone
m_elmRegistry[ELMRole::Planner] = std::make_shared<elm::RoleELM>( ELMRole::Planner, m_coreEngine );
m_elmRegistry[ELMRole::PrimaryDraft] = std::make_shared<elm::RoleELM>( ELMRole::PrimaryDraft, m_coreEngine );
m_elmRegistry[ELMRole::Verifier] = std::make_shared<elm::RoleELM>( ELMRole::Verifier, m_coreEngine );
m_elmRegistry[ELMRole::Arbiter] = std::make_shared<elm::RoleELM>( ELMRole::Arbiter, m_coreEngine );
m_elmRegistry[ELMRole::Refiner] = std::make_shared<elm::SpecialistAdapter>(
    m_grammarSpec, ELMRole::Refiner, "Refiner/Formatter" );
m_elmRegistry[ELMRole::Math] = std::make_shared<elm::SpecialistAdapter>(
    m_mathSpec, ELMRole::Math, "Math" );

// Domain ELMs
m_elmRegistry[ELMRole::Code] = std::make_shared<elm::DomainELM>( ELMRole::Code, m_coreEngine );
m_elmRegistry[ELMRole::Science] = std::make_shared<elm::RoleELM>( ELMRole::Science, m_coreEngine );

// Grounding ELM
if ( m_enableKnowledge )
{
    m_elmRegistry[ELMRole::Grounding] = std::make_shared<elm::GroundingELM>(
        m_coreEngine, m_knowledge, std::make_unique<knowledge::ContextInjection>(),
        std::make_unique<knowledge::FactValidation>( m_knowledge ) );
}

// Tool-Support stub
m_elmRegistry[ELMRole::ToolSupport] = std::make_shared<elm::ToolSupportELM>();

// Load eager ELMs from config
for ( const auto& cfg : m_cfg.m_elmConfigs )
{
    if ( cfg.eager && !cfg.model.empty() )
    {
        auto role = ParseRole( cfg.role );
        auto it = m_elmRegistry.find( role );
        if ( it != m_elmRegistry.end() )
        {
            (void)it->second->Load( cfg.model );
        }
    }
}
```

**new includes needed in api_server.cpp:**
```cpp
#include "elm/role_elm.hpp"
#include "elm/domain_elm.hpp"
#include "elm/grounding_elm.hpp"
#include "elm/tool_support_elm.hpp"
#include "elm/specialist_adapter.hpp"
```

---

### 14. `src/main.cpp` (MODIFY — parse `elms` JSON config section)

**Analog:** `src/main.cpp:89-138` (LoadConfigFile pattern — nlohmann/json key existence checks, args struct defaults)

**Why:** Extend the existing `LoadConfigFile()` function to parse an `elms` JSON array. Uses the same `j.contains("key")` pattern, same `args.*` fallback pattern.

**Config struct extension** (copy existing args member pattern from lines 41-60):
Add to `Args` struct:
```cpp
struct ElmConfigEntry
{
    std::string role;
    std::string model;
    bool eager = false;
};
std::vector<ElmConfigEntry> m_elmConfigs;
```

**JSON parsing addition** (add after line 135, before the `std::cout << "Loaded config..."` line 137):
```cpp
// Parse ELM config section (Phase 7+)
if ( j.contains( "elms" ) && j["elms"].is_array() )
{
    for ( const auto& e : j["elms"] )
    {
        ElmConfigEntry entry;
        if ( e.contains( "role" ) )
        {
            entry.role = e["role"].get<std::string>();
        }
        if ( e.contains( "model" ) )
        {
            entry.model = e["model"].get<std::string>();
        }
        if ( e.contains( "eager" ) )
        {
            entry.eager = e["eager"].get<bool>();
        }
        if ( !entry.role.empty() )
        {
            args.m_elmConfigs.push_back( std::move( entry ) );
        }
    }
}
```

**ApiServer::Config population** — map from Args → Config (in ApiServer construction, around line 260-290 of main.cpp):
```cpp
for ( const auto& entry : args.m_elmConfigs )
{
    api::ApiServer::ElmEntry cfgEntry;
    cfgEntry.role = entry.role;
    cfgEntry.model = entry.model;
    cfgEntry.eager = entry.eager;
    serverCfg.m_elmConfigs.push_back( std::move( cfgEntry ) );
}
```

---

### 15. `test/elm/test_elm.cpp` (NEW — ELM unit tests)

**Analog:** `test/specialists/test_grammar_specialist.cpp` (lines 1-139)

**Why:** Exact same test pattern — MockEngine for happy path, FailingMockEngine for unhappy path, GTest TEST macros, ASSERT_TRUE/EXPECT_EQ/EXPECT_FLOAT_EQ assertions.

**MockEngine pattern** (lines 17-46) — **reuse verbatim in test_elm.cpp**:
```cpp
class MockEngine : public core::InferenceEngine
{
public:
    outcome::result<InferenceResponse> Infer( const Task& task ) override
    {
        InferenceResponse resp;
        resp.m_output = task.m_prompt + " [response]";
        resp.m_perplexity = 1.0f;
        resp.m_success = true;
        resp.m_taskId = task.m_id;
        return outcome::success( resp );
    }
    outcome::result<void> StreamInfer( const Task&,
                                        std::function<void( const std::string& )> ) override
    {
        return outcome::success();
    }
    outcome::result<void> LoadModel( const std::string& ) override
    {
        return outcome::success();
    }
    bool IsLoaded() const override { return true; }
    std::string BackendName() const override { return "mock"; }
};
```

**FailingMockEngine pattern** (lines 48-72 in test_grammar_specialist.cpp) — reuse verbatim.

**Test case patterns** (copy structure from lines 78-139):

Happy path test (lines 79-90):
```cpp
TEST( RoleELM, Process_LoadedEngine_ReturnsResponse )
{
    auto engine = std::make_shared<MockEngine>();
    elm::RoleELM elm( ELMRole::Verifier, engine );
    ASSERT_TRUE( elm.Load( "dummy" ).has_value() );
    ASSERT_TRUE( elm.IsLoaded() );

    ELMContext ctx;
    ctx.m_originalTask = "test task";
    auto result = elm.Process( "input text", ctx );
    ASSERT_TRUE( result.has_value() );
    EXPECT_NE( result.value().find( "input" ), std::string::npos );
    EXPECT_GT( elm.GetConfidence(), 0.0f );
}
```

Unhappy path — fail-close (lines 114-123):
```cpp
TEST( RoleELM, Process_NotLoaded_ReturnsInputUnchanged )
{
    auto engine = std::make_shared<MockEngine>();
    elm::RoleELM elm( ELMRole::Verifier, engine );

    ELMContext ctx;
    auto result = elm.Process( "hello world", ctx );
    ASSERT_TRUE( result.has_value() );
    EXPECT_EQ( result.value(), "hello world" );
    EXPECT_FLOAT_EQ( elm.GetConfidence(), 0.0f );
}
```

**Test targets to create in test_elm.cpp:**
1. `RoleELM_Process_LoadedEngine_ReturnsResponse` (happy)
2. `RoleELM_Process_NotLoaded_ReturnsInputUnchanged` (fail-close)
3. `RoleELM_GetName_ReturnsCorrectName`
4. `RoleELM_GetRole_ReturnsConfiguredRole`
5. `RoleELM_IsLoaded_InitiallyFalse`
6. `DomainELM_Process_SharedBackbone_ReturnsResponse` (happy)
7. `DomainELM_Process_NoEngine_ReturnsInputUnchanged` (fail-close)
8. `SpecialistAdapter_Process_DelegatesToSpecialist` (happy)
9. `SpecialistAdapter_GetConfidence_ReflectsSpecialist`
10. `ELMChainBuilder_Build_HighNumericDensity_ReturnsMathChain`
11. `ELMChainBuilder_Build_CodeSyntax_ReturnsPlannerCodeChain`
12. `ELMChainBuilder_Build_LowComplexity_ReturnsSingleStep`
13. `ELMChainBuilder_Build_HighComplexity_ReturnsFullChain`
14. `GroundingELM_Process_KnowledgeLoaded_ReturnsAugmentedOutput`
15. `GroundingELM_Process_NoKnowledge_ReturnsInputUnchanged`
16. `ToolSupportELM_Process_ReturnsInputUnchanged_ConfidenceZero`
17. `ToolSupportELM_IsLoaded_AlwaysFalse`

---

### 16. `test/common/test_types.cpp` (MODIFY — extend with ELMRole/ELMContext)

**Analog:** `test/common/test_types.cpp:6-11` (ExecutionMode enum test pattern) + lines 76-85 (PromptFeatures default test pattern)

**Why:** Add tests for new ELMRole enum values and ELMContext/ExecutionChain default initialization. Follows the exact same test structures.

**ELMRole enum test** (copy ExecutionMode pattern, lines 6-11):
```cpp
TEST(ELMRole, EnumValues_AreDistinct)
{
    EXPECT_NE( static_cast<int>( ELMRole::Planner ), static_cast<int>( ELMRole::PrimaryDraft ) );
    EXPECT_NE( static_cast<int>( ELMRole::Verifier ), static_cast<int>( ELMRole::Arbiter ) );
    EXPECT_NE( static_cast<int>( ELMRole::Refiner ), static_cast<int>( ELMRole::Grounding ) );
    EXPECT_NE( static_cast<int>( ELMRole::Math ), static_cast<int>( ELMRole::Code ) );
    EXPECT_NE( static_cast<int>( ELMRole::Science ), static_cast<int>( ELMRole::ToolSupport ) );
}
```

**ELMContext default test** (copy PromptFeatures pattern, lines 76-85):
```cpp
TEST(ELMContext, DefaultConstructor_HasReasonableDefaults)
{
    ELMContext ctx;
    EXPECT_TRUE( ctx.m_originalTask.empty() );
    EXPECT_TRUE( ctx.m_lastOutput.empty() );
    EXPECT_TRUE( ctx.m_stepConfidences.empty() );
    EXPECT_TRUE( ctx.m_groundingFacts.empty() );
}
```

**ExecutionChain default test:**
```cpp
TEST(ExecutionChain, DefaultConstructor_HasReasonableDefaults)
{
    ExecutionChain chain;
    EXPECT_TRUE( chain.m_steps.empty() );
    EXPECT_TRUE( chain.m_reasoning.empty() );
    EXPECT_FLOAT_EQ( chain.m_chainConfidence, 0.0f );
}
```

**ChainStep default test:**
```cpp
TEST(ChainStep, DefaultConstructor_HasReasonableDefaults)
{
    ChainStep step;
    EXPECT_EQ( step.m_role, ELMRole::PrimaryDraft );
    EXPECT_FALSE( step.m_domain.has_value() );
}
```

**ExecutionMode Chain value test** — extend existing test (lines 6-11):
```cpp
TEST(ExecutionMode, ChainValue_IsDistinct)
{
    EXPECT_NE( static_cast<int>( ExecutionMode::Chain ), static_cast<int>( ExecutionMode::SingleNode ) );
    EXPECT_NE( static_cast<int>( ExecutionMode::Chain ), static_cast<int>( ExecutionMode::Specialist ) );
    EXPECT_NE( static_cast<int>( ExecutionMode::Chain ), static_cast<int>( ExecutionMode::Swarm ) );
}
```

---

### 17. `test/integration/test_pipeline.cpp` (MODIFY — chain execution integration tests)

**Analog:** `test/integration/test_pipeline.cpp:13-56` (PipelineTest fixture + SingleNode/Math/Grammar tests)

**Why:** Add chain-mode integration tests using the same PipelineTest fixture, same stub-mode config, same Process() call pattern.

**New test cases** (copy PipelineTest fixture from lines 13-30, reuse):
```cpp
TEST_F( PipelineTest, ChainMode_BasicExecution )
{
    Task task;
    task.m_prompt = "Solve this complex problem: what is 847 * 963 + 42?";
    task.m_mode = ExecutionMode::Chain;
    task.m_maxTokens = 64;

    auto res = server_->Process( task );
    ASSERT_TRUE( res.has_value() );
    EXPECT_EQ( res.value().m_modeUsed, ExecutionMode::Chain );
    EXPECT_FALSE( res.value().m_taskId.empty() );
}

TEST_F( PipelineTest, ChainMode_GeneralPrompt_SingleStep )
{
    Task task;
    task.m_prompt = "Tell me a short story.";
    task.m_mode = ExecutionMode::Chain;
    task.m_maxTokens = 32;

    auto res = server_->Process( task );
    ASSERT_TRUE( res.has_value() );
    EXPECT_EQ( res.value().m_modeUsed, ExecutionMode::Chain );
}
```

---

### 18. `test/CMakeLists.txt` (MODIFY — add ELM test targets)

**Analog:** `test/CMakeLists.txt:69-70` (specialist test registration pattern)

**Why:** Copy the exact `neoswarm_test` macro invocation, linking against `neoswarm_elm`.

**New test registrations:**
```cmake
# Phase 7 — ELM tests
neoswarm_test(test_elm             elm/test_elm.cpp              "neoswarm_elm;neoswarm_core;neoswarm_common")
```

**Add `test/elm/` directory** — test_elm.cpp lives there.

---

## Shared Patterns

### Authentication
**Source:** N/A — not applicable for Phase 7 (local-only, no auth gating on ELM calls)

### Error Handling (used by ALL new files)
**Source:** `src/common/error.hpp` (lines 1-51)

**Error propagation:**
```cpp
namespace sgns::neoswarm
{
    namespace outcome = libp2p::outcome;
}
```

**All ELM interfaces use:**
```cpp
outcome::result<T>     // return type (T = void for Load, string for Process)
outcome::success(val)  // return success with value
outcome::failure(Error::SomeError) // return failure with error code
BOOST_OUTCOME_TRY(var) // propagate error from called function
```

**Fail-close pattern** — all ELM Process() methods MUST return input unchanged on failure:
```cpp
if ( !m_loaded || !m_engine )
{
    Logger()->warn( "Not loaded — returning input unchanged" );
    m_lastConfidence = 0.0f;
    return outcome::success( input );
}
```

**No exceptions** — the codebase uses `outcome::result` exclusively. No `try/catch` in hot paths. Only `try/catch` for JSON parsing in main.cpp (nlohmann/json throws on bad input).

### Logging (used by ALL new .cpp files)
**Source:** `src/common/logging.hpp` (lines 1-40) + grammar_specialist.cpp:14-19 (logger creation pattern)

**Logger creation pattern:**
```cpp
namespace
{
    auto ElmLogger()
    {
        return neoswarm::CreateLogger( "ELM/TagName" );
    }
} // namespace
```

**Logging calls:**
```cpp
ElmLogger()->info( "Loaded: {}", model_path );
ElmLogger()->warn( "Inference failed" );
ElmLogger()->debug( "Confidence: {:.2f}", confidence );
```

### Validation (used by GroundingELM, Chain execution)
**Source:** `src/knowledge/fact_validation.hpp:27-33` (ValidationResult struct) + api_server.cpp:314-325 (validation pattern)

**Validation pattern:**
```cpp
if ( m_factVal && m_factVal->IsAvailable() )
{
    auto val_result = m_factVal->Validate( output, facts );
    if ( !val_result.passed_ )
    {
        Logger()->warn( "Fact validation failed: {}", val_result.suggestion_ );
        // Adjust confidence/perplexity based on contradiction score
    }
}
```

### CMake Registration (used by src/elm/CMakeLists.txt, test/CMakeLists.txt, src/CMakeLists.txt)
**Source:** `src/specialists/CMakeLists.txt` (lines 1-12) + `test/CMakeLists.txt:42-53,69-70`

**Library pattern:**
```cmake
add_library(neoswarm_<module> STATIC
    file1.cpp
    file2.cpp
)
target_include_directories(neoswarm_<module> PUBLIC
    $<BUILD_INTERFACE:${PROJECT_ROOT}/src>
    $<INSTALL_INTERFACE:include>
)
target_link_libraries(neoswarm_<module> PUBLIC neoswarm_common neoswarm_core ...)
```

**Test target pattern:**
```cmake
neoswarm_test(test_<name> <dir>/test_<name>.cpp "<libs>")
```

**Subdirectory pattern:**
```cmake
add_subdirectory(${CMAKE_CURRENT_LIST_DIR}/<module> ${CMAKE_CURRENT_BINARY_DIR}/<module>)
```

### Doxygen Headers (used by ALL new .hpp files)
**Source:** `src/specialists/i_specialist.hpp:1-5`

**File header pattern:**
```cpp
/**
 * @file       i_elm.hpp
 * @brief      Abstract interface for Expert Language Models (doc 03 §5.2)
 * @date       2026-07-16
 */
```

**Method documentation pattern:**
```cpp
/**
 * @brief Process input through this ELM and return refined output.
 * @param input    Text to process (typically output of previous chain step).
 * @param context  ELM execution context (original task, prior outputs, confidences).
 * @return         Refined text or InferenceFailed.
 */
virtual outcome::result<std::string> Process( const std::string& input, const ELMContext& context ) = 0;
```

### Naming Conventions (ALL files)
**Source:** CLAUDE.md SuperGenius Naming Convention Overrides section

| Element | Convention | Example |
|---------|-----------|---------|
| Member variables | `m_` prefix + camelCase | `m_engine`, `m_loaded`, `m_lastConfidence` |
| Function arguments | camelCase (no prefix) | `model_path`, `input`, `context` |
| File names | snake_case | `role_elm.cpp`, `i_elm.hpp` |
| Directory names | snake_case lowercase | `src/elm/`, `test/elm/` |
| Accessors | `Get` prefix, `Set` prefix, `Is` for bool | `GetName()`, `IsLoaded()`, `GetRole()` |
| Constants (compile-time) | `k` prefix + PascalCase | `kConfidenceThreshold` |
| Library names (CMake) | `neoswarm_` prefix + snake_case | `neoswarm_elm` |
| Interfaces | `I` prefix + PascalCase | `IELM` |

### Namespace Convention (ALL files)
**Source:** `src/specialists/i_specialist.hpp:13,52`

**New ELM namespace:**
```cpp
namespace sgns::neoswarm::elm
{
    // class declarations
} // namespace sgns::neoswarm::elm
```

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| *(none)* | — | — | All 18 files have close analogs in the existing codebase |

---

## Metadata

**Analog search scope:** `src/specialists/`, `src/router/`, `src/api/`, `src/common/`, `src/knowledge/`, `src/core/engine/`, `test/`, `src/main.cpp`
**Files scanned:** 22 (source files + test files + CMake files)
**Pattern extraction date:** 2026-07-16
**Research reference:** `.planning/workstreams/neoswarm/phases/07-expert-language-models-router/07-RESEARCH.md`
