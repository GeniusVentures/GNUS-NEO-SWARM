# Phase 07: Expert Language Models + Router — Research

**Researched:** 2026-07-16
**Domain:** ELM orchestration, rule-based router extension, sequential execution chains
**Confidence:** HIGH — all key findings verified against the existing codebase

## Summary

This phase deploys 10 ELMs (7 role-based, 3 domain) behind a new `IELM` interface, extends the rule-based router with six heuristic chain-building triggers, and integrates sequential `ExecutionChain` execution into `ApiServer`. The existing codebase already contains all the primitives: `InferenceEngine::Infer()` for shared-backbone prompt-in/text-out, `ISpecialist` with a near-identical interface to `IELM`, `RuleBasedRouter` + `PromptAnalyzer` covering 4 of 6 triggers, the full knowledge pipeline for `GroundingELM`, and a `MockEngine` test pattern.

**Primary recommendation:** Extend what exists, do not rebuild. `GrammarSpecialist`/`MathSpecialist` are already proto-ELMs — wrap them with adapter classes. `PromptAnalyzer` needs 2 new feature detectors, not a rewrite. `RuleBasedRouter` keeps its current responsibilities; a new `ELMChainBuilder` translates route decisions into chains. The threading risk is low (ApiServer is synchronous, sequential chain execution is trivially safe at the MNN engine level).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Prompt classification & feature extraction | API / Backend | — | `PromptAnalyzer` runs in-process before any model invocation |
| Route decision (SingleNode / Specialist / Chain) | API / Backend | — | `RuleBasedRouter` owns mode selection and target specialist |
| Chain construction (decision → ordered steps) | API / Backend | — | New `ELMChainBuilder` converts route + features to `ExecutionChain` |
| Shared-backbone inference (role ELMs) | API / Backend | — | All role ELMs call the same `InferenceEngine::Infer()` with role-specific prompt templates |
| Per-ELM model inference (domain ELMs) | API / Backend | — | Domain ELMs may own a dedicated `MNNInferenceEngine` instance with own `.mnn` file |
| Legacy specialist execution (Grammar/Math) | API / Backend | — | Adapters delegate to existing `ISpecialist` instances via composition |
| Knowledge retrieval & fact validation | API / Backend | — | `GroundingELM` wraps the existing `knowledge/` pipeline (no new dependencies) |
| JSON config loading (`elms` section) | API / Backend | — | `main.cpp` `LoadConfigFile()` — same nlohmann/json pattern as existing keys |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `outcome::result<T>` | libp2p outcome | Error propagation for all ELM interfaces | Project-wide standard; `BOOST_OUTCOME_TRY` macro in all existing code [VERIFIED: src/common/error.hpp] |
| Google Test | (thirdparty) | Unit/integration tests | Existing 15 test files all use GTest [VERIFIED: test/CMakeLists.txt] |
| `nlohmann/json` | (thirdparty) | JSON config parsing for `elms` section | Already used in `main.cpp` for config file parsing [VERIFIED: src/main.cpp:98-137] |
| spdlog | (header-only) | Component logging | `CreateLogger("tag")` pattern in all modules [VERIFIED: src/common/logging.hpp] |
| MNN (inference) | (thirdparty) | Core model execution | `MNNInferenceEngine` is the only InferenceEngine implementation [VERIFIED: src/core/engine/] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `<boost/asio/io_context.hpp>` | Boost.Asio | Async I/O for SGProcessing path | Already linked; ELMs don't need it (sequential, synchronous) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| New `IELM` interface from scratch | Extending `ISpecialist` with role/context params | Decision D-05 locks `IELM` as new interface — `ISpecialist` stays untouched for backward compatibility |

**Installation:**
```bash
# No new third-party dependencies. Phase 7 uses only already-linked libraries.
```

## Architecture Patterns

### System Architecture Diagram

```
User Task
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│  ApiServer::Process()                                            │
│                                                                   │
│  1. m_router->Route(task) ──► RouteDecision                       │
│       │                                                           │
│       ▼                                                           │
│  2. (new) m_chainBuilder->Build(decision, features) ──► ExecutionChain
│       │                                                           │
│       ▼                                                           │
│  3. (new) RunELMChain(chain, task)                                │
│       │                                                           │
│       │  ExecutionChain steps:                                     │
│       │  [Planner] → [Domain ELM] → [Verifier] → [Refiner]        │
│       │      │            │              │             │           │
│       │      ▼            ▼              ▼             ▼           │
│       │  ┌────────┐  ┌────────┐    ┌────────┐   ┌────────┐       │
│       │  │IELM    │  │IELM    │    │IELM    │   │IELM    │       │
│       │  │(shared │  │(own    │    │(shared │   │(adapter│       │
│       │  │backbone│  │engine) │    │backbone│   │wraps   │       │
│       │  │+prompt │  │        │    │+prompt │   │Grammar │       │
│       │  │template│  │        │    │template│   │Spec)   │       │
│       │  └────────┘  └────────┘    └────────┘   └────────┘       │
│       │       │            │              │             │          │
│       │       ▼            ▼              ▼             ▼          │
│       │  output₁ ───► output₂ ──────► output₃ ───► final_output   │
│       │  (via ELMContext accumulated state)                        │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
InferenceResponse
```

### Recommended Project Structure
```
src/
├── api/
│   └── api_server.{hpp,cpp}        # Gain: RunELMChain(), ELM registry
├── common/
│   └── types.hpp                   # Gain: ELMRole enum, ELMContext struct, ExecutionChain
├── elm/                            # NEW directory
│   ├── i_elm.hpp                   # IELM interface
│   ├── role_elm.hpp                # Shared-backbone role ELM (Planner, Verifier, etc.)
│   ├── role_elm.cpp
│   ├── domain_elm.hpp              # Domain ELM with optional own model
│   ├── domain_elm.cpp
│   ├── grounding_elm.hpp           # Wraps knowledge/ pipeline
│   ├── grounding_elm.cpp
│   ├── tool_support_elm.hpp        # Stub (pass-through)
│   ├── tool_support_elm.cpp
│   ├── specialist_adapter.hpp      # Wraps ISpecialist as IELM
│   ├── specialist_adapter.cpp
│   ├── elm_chain_builder.hpp       # RuleDecision + Features → ExecutionChain
│   ├── elm_chain_builder.cpp
│   └── CMakeLists.txt              # neoswarm_elm library target
├── router/
│   ├── prompt_analyzer.{hpp,cpp}   # Gain: has_grounding_request, has_formatting_request
│   └── rule_based_router.{hpp,cpp} # Unchanged (Route remains same)
└── main.cpp                        # Gain: "elms" JSON config section parsing
```

### Pattern 1: Shared-Backbone Role ELM
**What:** A concrete `IELM` that constructs a role-specific prompt template (e.g., `"[INST] You are a Verifier. Check the following..."`) and calls `m_engine->Infer()` on the shared `InferenceEngine`. Identical pattern to how `GrammarSpecialist::BuildPrompt()` + `m_engine->Infer()` works today [VERIFIED: src/specialists/grammar_specialist.cpp:45-80].

**When to use:** Every role ELM (Planner, PrimaryDraft, Verifier, Arbiter, Refiner) when no dedicated model path is configured.

**Example (conceptual, based on existing GrammarSpecialist pattern):**
```cpp
// Source pattern: src/specialists/grammar_specialist.cpp:56-81
outcome::result<std::string> RoleELM::Process(const std::string& input, const ELMContext& ctx)
{
    if (!m_loaded || !m_engine)
    {
        m_lastConfidence = 0.0f;
        return outcome::success(input);  // graceful degradation
    }

    Task task;
    task.m_id = /* role-specific ID */;
    task.m_prompt = BuildPrompt(input, ctx);  // role template
    task.m_maxTokens = 512;
    task.m_temperature = 0.1f;  // low temp for deterministic roles

    auto res = m_engine->Infer(task);
    if (!res.has_value())
    {
        m_lastConfidence = 0.0f;
        return outcome::success(input);  // fail-close: return input unchanged
    }

    m_lastConfidence = 1.0f - std::min(res.value().m_perplexity / 10.0f, 1.0f);
    return outcome::success(res.value().m_output);
}
```

### Pattern 2: Adapter (ISpecialist → IELM)
**What:** Composition-based wrapper. Holds `std::shared_ptr<ISpecialist>` (or `std::unique_ptr`), maps `IELM::Process(input, ELMContext)` → `ISpecialist::Process(input)`. The `ELMContext` is logged but not passed through (ISpecialist doesn't accept it). Decision D-06/D-07 lock this pattern.

**When to use:** Refiner/Formatter wrapping GrammarSpecialist; Math domain wrapping MathSpecialist.

```cpp
// Conceptual — maps to ISpecialist::Process(std::string) signature
// Source: src/specialists/i_specialist.hpp:38-43
outcome::result<std::string> SpecialistAdapter::Process(const std::string& input, const ELMContext& /*ctx*/)
{
    return m_specialist->Process(input);  // ISpecialist only takes string
}
```

### Pattern 3: ELMChainBuilder (RouteDecision → ExecutionChain)
**What:** Stateless function/class that takes `RouteDecision` + `PromptFeatures` and produces an `ExecutionChain` — a flat `vector<ChainStep>` where each step is `{ELMRole, optional domain}`. Implements the six heuristic triggers from doc 03 §6.2.

**When to use:** Called by `ApiServer::Process()` after routing, before execution.

**Trigger mapping:**
| Trigger | Condition | Chain |
|---------|-----------|-------|
| Numeric density | `numeric_density_ > threshold` | Math → Verifier |
| Code syntax | `has_code_syntax_ == true` | Planner → Code |
| Grounding-sensitive | `has_grounding_request_` (NEW) | Grounding → PrimaryDraft → Verifier |
| Formatting-sensitive | `has_formatting_request_` (NEW) | PrimaryDraft → Refiner |
| Low complexity | `complexity_ < lowThreshold` | PrimaryDraft only |
| High complexity | `complexity_ > highThreshold` | Planner → Domain → Verifier → Refiner |

### Pattern 4: Sequential Chain Execution
**What:** `ApiServer::RunELMChain()` iterates through `ExecutionChain` steps. For each step: looks up the ELM by role/domain from the ELM registry, calls `elm->Process(accumulatedText, context)`, feeds output into the next step via `ELMContext`.

**When to use:** The new fourth execution path in `ApiServer::Process()`.

### Anti-Patterns to Avoid
- **Multiple MNNInferenceEngine instances sharing the same model file:** Each engine loads independently. For shared-backbone ELMs, all must share a single engine. Create per-ELM engines only when `model_path` is explicitly set.
- **Parallel ELM execution in Phase 7:** Deferred to Phase 9. ExecutionChain is flat and sequential.
- **Modifying ISpecialist interface:** D-05 explicitly keeps ISpecialist untouched. Adapt via composition.
- **Using `std::this_thread::sleep_for` in tests:** Project standard forbids this. But ELM chain execution is synchronous; no wait conditions needed.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Prompt template construction | Custom formatting library | `std::string` concatenation / `fmt::format` | Existing specialists already do this; keep it simple [VERIFIED: grammar_specialist.cpp:45-51] |
| JSON config parsing | Hand-written parser | `nlohmann/json` (already linked) | `LoadConfigFile()` in main.cpp already uses it [VERIFIED: main.cpp:98-137] |
| Role/domain string → enum mapping | If-else chains | Static `std::unordered_map<std::string, ELMRole>` | Performant, declarative, easy to test |
| ELM registry (role → ELM instance) | Custom container | `std::unordered_map<ELMRole, std::shared_ptr<IELM>>` | Standard C++17, sufficient for sequential lookup |
| Confidence aggregation across chain | Custom math | Product of per-step confidences or min confidence | Per-step confidence already computed by each ELM::Process() |

## User Constraints (from CONTEXT.md)

### Locked Decisions
- D-01/02: Hybrid ELM backing — shared backbone (core MNN model + role prompt template) by default, optional per-role model path. [VERIFIED: feasible — `RoleELM` holds `shared_ptr<InferenceEngine>`, `DomainELM` may own its own `unique_ptr<MNNInferenceEngine>`]
- D-05..08: New `IELM` interface; adapters wrap GrammarSpecialist/MathSpecialist via composition; `ELMRole` enum + `ELMContext` struct in `common/types.hpp`.
- D-09..13: Flat sequential `ExecutionChain`; `ELMChainBuilder` separate from `RuleBasedRouter`; `ApiServer::RunELMChain`.
- D-14..16: `elms` JSON config section, lazy loading default.
- D-17/18: `GroundingELM` wraps knowledge/ pipeline; `ToolSupportELM` is a stub.

### OpenCode's Discretion
- Exact `ELMContext` field set (must carry: original task, accumulated step outputs, per-step confidence)
- Role prompt template wording
- Chain-step timeout and confidence-threshold defaults
- File layout for ELM implementations (recommendation: `src/elm/` as new directory)
- Whether Science ELM ships as shared-backbone-only in Phase 7 (no trained model exists)

### Deferred Ideas (OUT OF SCOPE)
- Multi-domain parallel dispatch + arbiter-mediated synthesis — Phase 9
- Learned classifier router — Phase 7.5 / doc 03 §6.3 stage 2
- Cognitive planner producing full execution graphs — Phase 8+ (needs GAML memory)
- Real Tool-Support logic — Phase 10
- User-editable role prompt templates — future
- Legal/Compliance, Operations, Customer Support, Finance domain ELMs — future

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ELM-01 | Deploy 7 role-based ELMs behind IELM interface | Shared-backbone `RoleELM` class + role prompt templates; verified against existing GrammarSpecialist pattern |
| ELM-02 | Deploy 3 domain ELMs (Math, Code, Science) | Math ELM via `SpecialistAdapter<MathSpecialist>`; Code/Science via `DomainELM` (shared backbone for Science, optional model for Code) |
| ELM-03 | ELMRole enum + ELMContext in common/types.hpp | New enum added to existing types.hpp alongside existing ExecutionMode/RouteTarget enums |
| ELM-04 | Adapters wrap GrammarSpecialist → Refiner, MathSpecialist → Math domain | `SpecialistAdapter` class — composition of `ISpecialist`, verified against i_specialist.hpp signatures |
| ELM-05 | ELMChainBuilder produces ExecutionChain from RouteDecision + PromptFeatures | New class consuming existing `PromptFeatures` + `RouteDecision` structs; 6 trigger rules from doc 03 §6.2 |
| ELM-06 | ApiServer::RunELMChain executes chains sequentially | New private method alongside existing RunSingleNode/RunSpecialist/RunSwarm; verified against Process() switch in api_server.cpp:448-456 |
| ELM-07 | GroundingELM wraps knowledge/ pipeline | Wraps `KnowledgeRetrieval::Retrieve()` + `ContextInjection::Inject()` + engine Infer + `FactValidation::Validate()` |
| ELM-08 | ToolSupportELM is a pass-through stub | Returns input unchanged, logs "not implemented", confidence=0.0 |
| ELM-09 | elms JSON config section with lazy loading | Extends `LoadConfigFile()` in main.cpp:89-138 with per-role `model` and `eager` fields |
| ELM-10 | Router unchanged; new chain builder is separate | RuleBasedRouter keeps producing RouteDecision; ELMChainBuilder is new class |

## Existing Code Analysis

### Q1: Core MNN Model Invocation API (for shared-backbone ELMs)

**File:** `src/core/engine/inference_engine.hpp` [VERIFIED]
**Interface:** `InferenceEngine::Infer(const Task&) → outcome::result<InferenceResponse>`

```cpp
// Exact signatures (from inference_engine.hpp:30-37)
virtual outcome::result<void> LoadModel(const std::string& model_path) = 0;
virtual outcome::result<InferenceResponse> Infer(const Task& task) = 0;
virtual bool IsLoaded() const = 0;
```

**Task struct** (from `common/types.hpp:41-49`):
```cpp
struct Task {
    std::string m_id;
    std::string m_prompt;
    ExecutionMode m_mode = ExecutionMode::SingleNode;
    uint32_t m_maxTokens = 512;
    float m_temperature = 0.7f;
    std::string m_nodeId;
};
```

**InferenceResponse** (from `common/types.hpp:54-66`):
```cpp
struct InferenceResponse {
    std::string m_output;
    std::string m_taskId;
    ExecutionMode m_modeUsed;
    RouteTarget m_routeUsed;
    double m_totalLatencyMs = 0.0;
    float m_perplexity = 1.0f;
    double m_latencyMs = 0.0;
    std::string m_nodeId;
    bool m_success = true;
    std::string m_errorMessage;
};
```

**Existing pattern for role-specific prompts** (from `grammar_specialist.cpp:45-51, 56-81`):
1. Construct role prompt via `BuildPrompt(input)` 
2. Create `Task` with the prompt
3. Call `engine->Infer(task)`
4. Compute confidence from perplexity
5. Return output on success, input unchanged on failure (graceful degradation)

This is exactly the pattern every shared-backbone RoleELM will follow.

### Q2: ApiServer::Process() Branching — Where RunELMChain Integrates

**File:** `src/api/api_server.cpp` [VERIFIED]

Current `Process()` flow (lines 425-458):
```
Process(task)
  → m_router->Route(t)
  → switch(route.m_mode):
      SingleNode → RunSingleNode(t, route)
      Specialist → RunSpecialist(t, route)      // Core → Grammar OR Core → Math
      Swarm      → RunSwarm(t, route)
```

**Integration plan:** Add a new `ExecutionMode::ElmAssisted` value. The ELM chain path replaces the single-specialist path for multi-step routing. The switch becomes:
```cpp
case ExecutionMode::ElmAssisted:
    return RunELMChain(t, route);
```

Alternatively, keep `ExecutionMode::Specialist` for single-step (backward compat), and add `ExecutionMode::ElmAssisted` for multi-step. Decision D-09..13 says `RunELMChain` is a new method. The `ExecutionMode` enum in `common/types.hpp:20-25` needs a new value.

### Q3: What RuleBasedRouter + PromptAnalyzer Already Extract

**File:** `src/router/prompt_analyzer.cpp` [VERIFIED]

Current `PromptFeatures` struct (from `common/types.hpp:82-90`):
```cpp
struct PromptFeatures {
    float numeric_density_ = 0.0f;   // ratio of numeric tokens
    bool has_code_syntax_ = false;
    float complexity_ = 0.0f;        // log(token_count) × vocab_diversity
    size_t token_count_ = 0;
    bool has_math_keywords_ = false;
    bool has_grammar_request_ = false;
};
```

**Six doc 03 §6.2 triggers — coverage analysis:**

| # | Trigger | Covered? | Code |
|---|---------|----------|------|
| 1 | Numeric density → Math | ✅ YES | `ComputeNumericDensity()` (prompt_analyzer.cpp:45-74), threshold at 0.30 |
| 2 | Code syntax → Code | ✅ YES | `DetectCodeSyntax()` (prompt_analyzer.cpp:79-85) — regex-based detection |
| 3 | Grounding-sensitive → Grounding | ❌ NO | No grounding/factuality detector exists |
| 4 | Formatting-sensitive → Refiner | ⚠️ PARTIAL | `HasGrammarRequest()` (prompt_analyzer.cpp:142-161) — detects grammar/spelling requests but not general formatting |
| 5 | Low complexity → Core only | ✅ YES | `EstimateComplexity()` (prompt_analyzer.cpp:90-111) — log(token)×diversity |
| 6 | High complexity → multi-stage | ⚠️ PARTIAL | Complexity > swarm threshold triggers swarm mode, not multi-stage chain |

**New features needed:**
- `PromptFeatures::has_grounding_request_` — detects factual claims, "is it true", "verify", "according to", "fact check" keywords
- `PromptFeatures::has_formatting_request_` — detects structure/style requests beyond grammar: "format as", "make this look", "structure this", "organize", output schema keywords

**RuleBasedRouter::Route()** (from `rule_based_router.cpp:63-100`):
- Currently produces `RouteDecision` with lower-confidence code routing (`CoreOnly` for code, not `CorePlusCode`)
- `SelectMode()` (lines 32-58) decides `ExecutionMode`
- ELMChainBuilder uses the same `PromptFeatures` but produces `ExecutionChain` instead of `RouteDecision`

### Q4: Exact ISpecialist Signatures (for Adapters)

**File:** `src/specialists/i_specialist.hpp` [VERIFIED, lines 20-50]

```cpp
class ISpecialist {
public:
    virtual ~ISpecialist() = default;
    virtual std::string GetName() const = 0;
    virtual bool IsLoaded() const = 0;
    virtual outcome::result<void> Load(const std::string& model_path) = 0;
    virtual outcome::result<std::string> Process(const std::string& input) = 0;
    virtual float GetConfidence() const = 0;
};
```

**Key difference from IELM (D-05):** `ISpecialist::Process(input)` takes just a `std::string`; `IELM::Process(input, ELMContext)` takes both. The adapter must drop `ELMContext` when forwarding to `ISpecialist::Process()`.

**Concrete specialists to adapt:**
- `GrammarSpecialist` (grammar_specialist.hpp:22-49) — `GetName()` returns "GrammarSpecialist"
- `MathSpecialist` (math_specialist.hpp:24-55) — includes `SymbolicFallback`; `GetName()` returns "MathSpecialist"

Both take `shared_ptr<InferenceEngine>` in constructor, call `engine->Infer(Task)` in `Process()`, return input unchanged on failure.

### Q5: Knowledge Pipeline API (for GroundingELM)

**3-stage pipeline** [VERIFIED: src/knowledge/]:

1. **KnowledgeRetrieval::Retrieve(query)** (knowledge_retrieval.hpp:57)
   ```cpp
   outcome::result<std::vector<KnowledgeFact>> Retrieve(const std::string& query) const;
   ```
   Returns top-k `KnowledgeFact` structs (source, content, relevanceScore). TF-IDF stub [VERIFIED: knowledge_retrieval.cpp:107-136].

2. **ContextInjection::Inject(prompt, facts)** (context_injection.hpp:37)
   ```cpp
   std::string Inject(const std::string& prompt, const std::vector<KnowledgeFact>& facts) const;
   ```
   Prepends Grokipedia facts to the prompt. Already used in `ApiServer::AugmentPrompt()` [VERIFIED: api_server.cpp:204-217].

3. **FactValidation::Validate(output, facts)** (fact_validation.hpp:47)
   ```cpp
   ValidationResult Validate(const std::string& output, const std::vector<KnowledgeFact>& grounding_facts) const;
   ```
   Checks claims against facts, returns `ValidationResult { passed_, contradictionScore, contradictions, suggestion_ }`.

**GroundingELM::Process() flow:**
```
1. Retrieve(query) → facts
2. Inject(task + facts) → augmented prompt
3. engine->Infer(augmented_prompt) → output
4. FactValidation::Validate(output, facts) → validation result
5. If contradicting → log warning, set low confidence
6. Return output
```

All three components already exist and are wired in `ApiServer`. `GroundingELM` composes them identically.

### Q6: JSON Config Parsing — Where the `elms` Section Hooks In

**File:** `src/main.cpp` [VERIFIED, lines 89-138, 264-288]

Current `LoadConfigFile()` pattern:
```cpp
// Pattern for each key: check exists, only set if default value
if (j.contains("model") && args.m_modelPath.empty())
    args.m_modelPath = j["model"].get<std::string>();
```

Config flows into `api::ApiServer::Config` (api_server.hpp:50-66):
```cpp
struct Config {
    std::string m_modelPath;
    std::string m_grammarModelPath;
    std::string m_mathModelPath;
    std::string m_reputationDbPath;
    bool m_enableNetwork = false;
    // ... etc
};
```

**Integration for `elms` section:**

Add to `ApiServer::Config`:
```cpp
struct ElmEntry {
    std::string role;     // e.g. "planner", "verifier", "math"
    std::string model;    // optional model path
    bool eager = false;   // load at Initialize() vs lazy
};
std::vector<ElmEntry> m_elmConfigs;
```

In `LoadConfigFile()`, iterate `j["elms"]` array (if present):
```cpp
if (j.contains("elms") && j["elms"].is_array()) {
    for (const auto& e : j["elms"]) {
        ElmEntry entry;
        if (e.contains("role")) entry.role = e["role"].get<std::string>();
        if (e.contains("model")) entry.model = e["model"].get<std::string>();
        if (e.contains("eager")) entry.eager = e["eager"].get<bool>();
        cfg.m_elmConfigs.push_back(std::move(entry));
    }
}
```

### Q7: Existing Test Patterns

**Pattern 1 — MockEngine (synchronous, no wait conditions):**
From `test/specialists/test_grammar_specialist.cpp:17-46` [VERIFIED]:
```cpp
class MockEngine : public core::InferenceEngine {
    outcome::result<InferenceResponse> Infer(const Task& task) override {
        InferenceResponse resp;
        resp.m_output = task.m_prompt + " [corrected]";
        resp.m_perplexity = 1.0f;
        return outcome::success(resp);
    }
    // ... other virtuals stubbed
};
```
This pattern is directly reusable for ELM tests. Each ELM test creates a MockEngine, constructs the ELM with it, calls `Process()`, and checks output/confidence.

**Pattern 2 — Integration tests with ApiServer stub mode:**
From `test/integration/test_pipeline.cpp:13-30` [VERIFIED]:
```cpp
class PipelineTest : public ::testing::Test {
    void SetUp() override {
        ApiServer::Config cfg;
        cfg.m_modelPath = "";  // stub mode
        // ...
        server_ = std::make_unique<ApiServer>(cfg);
        ASSERT_TRUE(server_->Initialize().has_value());
    }
};
```
Reusable for chain execution integration tests.

**Pattern 3 — CMake test registration:**
From `test/CMakeLists.txt:42-53` [VERIFIED]:
```cmake
neoswarm_test(test_router router/test_router.cpp "neoswarm_router;neoswarm_common")
```
New tests will use `neoswarm_test(test_elm elm/test_elm.cpp "neoswarm_elm;neoswarm_common")`.

### Q8: Threading, Memory, and Pitfalls

**Threading model of ApiServer:** Synchronous throughout. `ApiServer::Process()` is called sequentially per request (interactive REPL mode in main.cpp:228). No thread pool, no concurrent Process() calls. Every internal operation is synchronous. [VERIFIED: api_server.cpp — no threads, no async, no mutex on Process()]

**MNN engine thread safety:** Not thread-safe at the model level. `MNNInferenceEngine` has single `mnn_llm_` pointer, single `m_session`, single `m_interpreter` (mnn_inference_engine.hpp:146-150). Concurrent calls to `Infer()` on the same instance would race on internal MNN state. This is NOT a concern for Phase 7 because:
- Chain execution is sequential (D-09: "flat ordered list of steps")
- Each `Infer()` call completes before the next step begins
- No concurrent ELM execution

**Memory when loading a second model:** Each `MNNInferenceEngine` instance owns its model. `RoleELM` with shared backbone uses `shared_ptr<InferenceEngine>` (no second model). `DomainELM` with its own `.mnn` path creates a new `MNNInferenceEngine` instance → separate model in memory. Acceptable for Phase 7 (local-only, consumer hardware). Memory pressure becomes a concern for Phase 9+ (many concurrent models).

**Stub/graceful degradation:** `MNNInferenceEngine::Infer()` returns `"[stub response — no model loaded]"` when uninitialized (mnn_inference_engine.cpp:250-257). `GrammarSpecialist::Process()` returns input unchanged when not loaded (grammar_specialist.cpp:60-63). ELMs must follow the same fail-close pattern.

**ExecutionMode enum collision risk:** Adding `ElmAssisted = 3` to `ExecutionMode` (types.hpp:20-25) is backward-safe — existing switch statements in Process() will hit the `default` case if a chain mode arrives before the handler is added. The planner must ensure `RunELMChain` is added before `Chain` mode is produced by the router.

## Environment Availability

Step 2.6: AUDITED — all dependencies are code-only (no new external tools, services, or runtimes). Phase 7 uses only already-linked libraries (MNN, Boost.Asio, nlohmann/json, spdlog, Google Test). No new environment dependencies to verify.

**Skip condition met:** No new external dependencies identified. All required libraries are already linked in the existing CMake build.

## Validation Architecture

**nyquist_validation: true** (from config.json)

### Test Framework
| Property | Value |
|----------|-------|
| Framework | Google Test (thirdparty) |
| Config file | `test/CMakeLists.txt` |
| Quick run command | `cd build/OSX/Debug && ninja test_router && ./test_router` |
| Full suite command | `cd build/OSX/Debug && ctest` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ELM-01 | RoleELM::Process with MockEngine returns template-augmented output | unit | `ninja test_elm && ./test_elm --gtest_filter="*RoleELM*"` | ❌ Wave 0 |
| ELM-02 | DomainELM::Process with shared backbone / per-ELM engine | unit | `ninja test_elm && ./test_elm --gtest_filter="*DomainELM*"` | ❌ Wave 0 |
| ELM-03 | ELMRole enum values, ELMContext carries accumulated outputs | unit | `ninja test_common_types && ./test_common_types` | ❌ (extend existing) |
| ELM-04 | SpecialistAdapter delegates to ISpecialist correctly | unit | `ninja test_elm && ./test_elm --gtest_filter="*Adapter*"` | ❌ Wave 0 |
| ELM-05 | ELMChainBuilder produces correct chain for each of 6 triggers | unit | `ninja test_elm && ./test_elm --gtest_filter="*ChainBuilder*"` | ❌ Wave 0 |
| ELM-06 | ApiServer::RunELMChain processes 3-step chain end-to-end | integration | `ninja test_pipeline && ./test_pipeline --gtest_filter="*Chain*"` | ❌ (extend existing) |
| ELM-07 | GroundingELM calls knowledge pipeline in order | unit | `ninja test_elm && ./test_elm --gtest_filter="*Grounding*"` | ❌ Wave 0 |
| ELM-08 | ToolSupportELM returns input unchanged with confidence=0 | unit | `ninja test_elm && ./test_elm --gtest_filter="*ToolSupport*"` | ❌ Wave 0 |
| ELM-09 | elms JSON config parses correctly; eager ELMs load at init | integration | `ninja test_pipeline && ./test_pipeline` | ❌ (extend existing) |
| ELM-10 | RuleBasedRouter tests still pass unchanged after chain builder added | regression | `ninja test_router && ./test_router` | ✅ exists |

### Sampling Rate
- **Per task commit:** `ninja test_elm && ./test_elm`
- **Per wave merge:** `ctest` (full suite)
- **Phase gate:** All ELM tests + existing tests green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `test/elm/test_elm.cpp` — covers RoleELM, DomainELM, SpecialistAdapter, ELMChainBuilder, GroundingELM, ToolSupportELM
- [ ] Extend `test/common/test_types.cpp` — ELMRole enum, ELMContext struct validation
- [ ] Extend `test/integration/test_pipeline.cpp` — ApiServer chain execution, ELM config loading
- [ ] Framework: `test/elm/` directory + CMakeLists entry

## Common Pitfalls

### Pitfall 1: ExecutionMode Enum Collision
**What goes wrong:** Adding `ExecutionMode::ElmAssisted = 3` before the `Process()` switch handles it crashes or silently falls through to `InternalError` return.
**Why it happens:** `ExecuteMode::Chain` could be produced by the router before `RunELMChain` is implemented.
**How to avoid:** Add the `case ExecutionMode::ElmAssisted:` branch in Process() FIRST, then update the router/chain builder to produce chain mode. Or use a temporary route: during Wave 1, chain builder produces single-step chains that use the existing `Specialist` mode path.
**Warning signs:** `InternalError` responses when chain mode is auto-selected.

### Pitfall 2: Shared MNNInferenceEngine State Races (Does Not Apply)
**What goes wrong:** N/A for Phase 7. Sequential chain execution means only one ELM calls `Infer()` at a time.
**Why it doesn't happen:** Decision D-09 (flat ordered list, no parallel edges) guarantees sequential execution.
**How to handle in future:** Phase 9 (parallel dispatch) will need per-ELM engines or an inference queue.

### Pitfall 3: ELMContext Accumulation Causing Prompt Bloat
**What goes wrong:** Each chain step receives all prior outputs in `ELMContext`. For a 5-step chain, step 5 sees step 1-4 outputs concatenated → prompt exceeds model's context window.
**Why it happens:** Naive concatenation doubles or triples prompt size per step.
**How to avoid:** Each ELM's prompt template should select only the immediately prior output, not the full history. `ELMContext` carries `m_lastOutput` (short) + `m_originalTask` (reference). Intermediate steps reference outputs, not concatenate all.

### Pitfall 4: Confidence Degradation in Long Chains
**What goes wrong:** Each step has confidence < 1.0. A 4-step chain where each step has 0.8 confidence gives 0.8⁴ = 0.41 final confidence — potentially below any useful threshold.
**Why it happens:** Perplexity-based confidence is conservative by design.
**How to avoid:** Use max-per-step or min-per-step confidence, not product. Report per-step confidence in `ELMContext` for debugging. Don't fail chains based on aggregate confidence in Phase 7 (leave threshold tuning for Phase 10).

### Pitfall 5: PromptAnalyzer Clean Extension
**What goes wrong:** Adding `has_grounding_request_` and `has_formatting_request_` to `PromptFeatures` breaks existing serialization/deserialization if any exists.
**Why it happens:** Struct layout changes when fields are added at the end.
**How to avoid:** `PromptFeatures` is a plain struct with no serialization. Adding fields at the end is safe. Existing test assertions checking specific field values may need updates but existing tests use EXPECT_GT/EXPECT_LT not exact values.

## Code Examples

### Role Prompt Template (Planner)
```cpp
// Source pattern: grammar_specialist.cpp:45-51 — BuildPrompt() convention
std::string PlannerELM::BuildPrompt(const std::string& input, const ELMContext& ctx)
{
    return "[INST] You are a Planner. Analyze the following task and determine:\n"
           "1. The primary domain (Math/Code/Science/General)\n"
           "2. Estimated complexity (Low/Medium/High)\n"
           "3. Recommended execution steps\n\n"
           "Task: " + input + "\n\n"
           "Analysis: [/INST]";
}
```

### ExecutionChain Struct
```cpp
// Based on D-09: flat ordered list, designed for future DAG extension
struct ChainStep {
    ELMRole m_role = ELMRole::PrimaryDraft;
    std::optional<std::string> m_domain;  // e.g. "math", "code" — for domain ELMs
};

struct ExecutionChain {
    std::vector<ChainStep> m_steps;
    std::string m_reasoning;              // why this chain was chosen
    float m_chainConfidence = 0.0f;       // builder's confidence in this chain
};
```

### ELMContext
```cpp
// OpenCode's discretion — minimum field set (D-05 requires: task, outputs, confidence)
struct ELMContext {
    std::string m_originalTask;            // the user's original prompt
    std::string m_lastOutput;              // output of the immediately prior step
    std::vector<std::pair<ELMRole, float>> m_stepConfidences;  // (role, confidence) per completed step
    std::vector<KnowledgeFact> m_groundingFacts;  // facts from GroundingELM, if any
};
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| RouteDecision with single target | ExecutionChain with ordered steps | Phase 7 (this phase) | Router still produces RouteDecision; ChainBuilder adds the chain |
| Hardcoded specialist dispatch in RunSpecialist() | ELM registry + RunELMChain | Phase 7 (this phase) | New ELMs added via config + registry, not code edits |

**Deprecated/outdated:**
- `RouteTarget::CorePlusGrammar` — becomes an internal detail of the Refiner adapter, not a top-level routing target (Phase 10+ cleanup, not Phase 7)
- `RouteTarget::CorePlusCode` (marked "Future") — Code ELM will be a full chain step, not a CorePlus mode

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `MNNInferenceEngine::mnn_llm_->response()` is safe for sequential calls on the same instance (no internal state corruption between calls) | Q8 Threading | Chain execution would produce garbled output or crash. Mitigation: MockEngine for tests; monitoring in integration tests |
| A2 | Adding `ExecutionMode::ElmAssisted = 3` to the enum does not break binary compatibility with existing compiled tests | Q2 Integration | Test binaries would need recompilation. Mitigation: enum already has 3 values; adding a 4th is standard C++ and wire-safe for this local-only project |
| A3 | Science ELM ships as shared-backbone-only (no trained model exists per gnus-poc scope boundary) | ELM-02 Domain ELMs | If a Science model appears, config already supports per-ELM model paths — just add to `elms` JSON |
| A4 | `PromptFeatures` struct has no external serialization dependencies — adding fields is backward-safe | Q3 PromptAnalyzer | Risk is minimal; `PromptFeatures` is a plain struct used only in-memory within the router pipeline |

## Open Questions (RESOLVED)

1. **Should Chain execution replace Specialist mode entirely, or coexist?**
   - What we know: D-09 says `RunELMChain` is new. Current `RunSpecialist` is a 2-step hardcoded path (Core → Specialist). A chain `[PrimaryDraft, Specialist]` achieves the same result via the chain executor.
   - What's unclear: Whether to remove `RunSpecialist` or keep as optimization shortcut for single-specialist chains.
   - Recommendation: Keep `ExecutionMode::Specialist` for backward compat in Phase 7; route single-specialist tasks through it. Use `ExecutionMode::ElmAssisted` only for multi-step (3+) chains. Deprecate `Specialist` mode in Phase 10.

2. **Per-step timeout: what default value?**
   - What we know: D-05/D-11 reference chain-step timeout as OpenCode's discretion. No existing chain timeout infrastructure.
   - What's unclear: MNN inference is synchronous and blocking — adding timeout requires `std::future` or `boost::asio` wrapping.
   - Recommendation: Defer per-step timeout to Phase 10 (along with safety profiles). Phase 7 uses synchronous blocking calls; the MNN engine's token-generation loop is the natural timeout (maxTokens-based).

3. **How are role prompt templates versioned?**
   - What we know: D-03 says templates live as "named constants/resources in the ELM implementations — not user-editable config." But templates shape ELM behavior significantly — changing them is a behavioral change.
   - What's unclear: Whether template changes require version bumps or just code review.
   - Recommendation: Document each template as a `static const char*` in the ELM class header (not cpp). Add a version comment. Not a blocking question for Phase 7.

## Security Domain

**security_enforcement: true** (from config.json — absent, treated as enabled)

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | Phase 1 already handles NodeIdentity |
| V3 Session Management | No | Stateless inference |
| V4 Access Control | No | Phase 10 (Tool Intermediary) |
| V5 Input Validation | Yes | Prompt sanitization before injection into role templates — avoid prompt injection via user input appearing in [INST] blocks |
| V6 Cryptography | No | No new crypto in this phase |

### Known Threat Patterns for C++ Inference Engine

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Prompt injection via user input in role template | Spoofing | Role prompt templates use structural delimiters (`[INST]...[/INST]`); user input is always placed AFTER the role instruction, never inline. Input is treated as data, not instruction. |
| ELM output used directly as next ELM input without sanitization | Elevation | D-09 chain is designed for trusted ELM-to-ELM handoff. For Phase 7 (local, single-user), this is acceptable. Sanitization gates added in Phase 10. |
| Malformed JSON config crashing the parser | Denial of Service | `nlohmann/json` exceptions caught by existing `try/catch` in `LoadConfigFile()` [VERIFIED: main.cpp:99-107] |

## Sources

### Primary (HIGH confidence)
- `src/core/engine/inference_engine.hpp` — InferenceEngine interface, Infer() signature
- `src/core/engine/mnn_inference_engine.{hpp,cpp}` — MNNInferenceEngine implementation, stub mode, InferViaMnnLlm path
- `src/api/api_server.{hpp,cpp}` — Process() switch, RunSingleNode/RunSpecialist/RunSwarm, Initialize flow
- `src/router/i_router.hpp` — IRouter interface, RouteDecision
- `src/router/rule_based_router.{hpp,cpp}` — RuleBasedRouter::Route(), SelectMode()
- `src/router/prompt_analyzer.{hpp,cpp}` — PromptFeatures extraction, all 5 analyzers
- `src/specialists/i_specialist.hpp` — ISpecialist interface (exact signatures)
- `src/specialists/grammar_specialist.{hpp,cpp}` — BuildPrompt pattern, Process flow, graceful degradation
- `src/specialists/math_specialist.{hpp,cpp}` — SymbolicFallback integration, confidence computation
- `src/specialists/symbolic_fallback.hpp` — kConfidenceThreshold constant
- `src/knowledge/knowledge_retrieval.{hpp,cpp}` — Retrieve() API, TF-IDF stub
- `src/knowledge/context_injection.hpp` — Inject() API
- `src/knowledge/fact_validation.hpp` — Validate() API, ValidationResult struct
- `src/common/types.hpp` — Task, InferenceResponse, RouteDecision, PromptFeatures, ExecutionMode, RouteTarget
- `src/common/error.hpp` — Error enum, outcome namespace
- `src/common/logging.hpp` — CreateLogger pattern
- `src/main.cpp` — LoadConfigFile pattern, CLI→config flow, Args struct
- `test/router/test_router.cpp` — Router test patterns
- `test/specialists/test_grammar_specialist.cpp` — MockEngine pattern, ELM test patterns
- `test/integration/test_pipeline.cpp` — Full pipeline test pattern
- `test/CMakeLists.txt` — neoswarm_test macro, library linking
- `.planning/workstreams/neoswarm/config.json` — nyquist_validation: true
- `../../docs/architecture/03-model-and-router.md` — ELM definition, router design, 6 triggers
- `../../docs/architecture/11-distributed-swarm-thinking-context.md` — §16.8 specialist taxonomy

### Secondary (MEDIUM confidence)
- None — all findings verified against primary sources

### Tertiary (LOW confidence)
- None — no unverified websearch findings

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependencies; all libraries already linked
- Architecture: HIGH — all integration points verified against live source code with exact file:line references
- Pitfalls: HIGH — pitfalls derived from code analysis (enum collision risk, prompt bloat from context accumulation)
- Test patterns: HIGH — MockEngine and integration test patterns directly reusable

**Research date:** 2026-07-16
**Valid until:** 2026-08-16
