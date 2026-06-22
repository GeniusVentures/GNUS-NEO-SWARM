# Phases 4–8 Blueprint: GNUS-NEO-SWARM

**Generated:** 2026-06-15
**Scope:** GitHub Issues #13 through #35 — Expert Language Models through Advanced Cognition
**Status:** All phases 0% implemented. No code exists yet for any of these systems.
**C++ Standard:** C++17 only. No C++20 features.
**Key Rule:** Program to interfaces. No `#ifdef` guards. Use derived classes behind abstract interfaces.

---

## Table of Contents

1. [Context: Where We Are](#1-context-where-we-are)
2. [Phase 4: Expert Language Models (ELMs)](#2-phase-4-expert-language-models)
3. [Phase 5: Agentic Memory](#3-phase-5-agentic-memory)
4. [Phase 6: Swarm Networking](#4-phase-6-swarm-networking)
5. [Phase 7: AI Safety](#5-phase-7-ai-safety)
6. [Phase 8: Advanced Cognition](#6-phase-8-advanced-cognition)
7. [Cross-Cutting Architecture](#7-cross-cutting-architecture)
8. [Execution Order & Dependencies](#8-execution-order--dependencies)
9. [Testing Strategy Per Phase](#9-testing-strategy-per-phase)

---

## 1. Context: Where We Are

### What the engine does today

A single-user, single-node inference pipeline:

```
User Prompt → RuleBasedRouter → SingleNode / Specialist / Swarm mode
                                     │
                              Core LLM (MNN/Mistral-7B)
                                     │
                              [optional: Grammar or Math specialist post-process]
                                     │
                              Response
```

The router has 3 hardcoded modes (`SingleNode`, `Specialist`, `Swarm`). It can route to **at most one** specialist per request. There is no chaining, no verification, no planning, no memory of prior interactions, no safety screening.

### What phases 4–8 build toward

A **multi-ELM cognitive swarm**:

```
User Prompt → Planner ELM → Execution Plan (signed, role assignments)
                                │
                 ┌──────────────┼──────────────┐
                 ▼              ▼              ▼
           Domain ELM A    Domain ELM B    Domain ELM C    (parallel or sequential)
                 │              │              │
                 └──────────────┼──────────────┘
                                ▼
                         Verifier ELM → score / rerun
                                │
                                ▼
                       Arbiter ELM → final output
                                │
                                ▼
                     Memory Ingest (store fact/policy/event)
                                │
                                ▼
                     Safety Screen → approved / blocked
                                │
                                ▼
                           Response
```

---

## 2. Phase 4: Expert Language Models

### Why This Phase Is Needed

The current engine treats all prompts the same: single-shot inference from the core model. But real-world prompts have fundamentally different needs:

- A **math question** needs structured reasoning, not creative generation
- A **coding task** needs syntax verification and test generation
- A **writing task** benefits from grammar correction and fluency refinement
- A **complex multi-step query** needs planning before execution
- A **high-stakes answer** needs verification by a second model
- A **conflicting result** from multiple specialists needs arbitration

Without ELMs, the engine is simply a wrapper around a single LLM with minor post-processing. Phase 4 upgrades it into a **coordinated system of specialized models** that decompose, execute, verify, and arbitrate — producing dramatically higher quality outputs.

### 4.1 Role-Based ELMs (Issue #13)

#### What
Seven role-based Expert Language Models, each a fine-tuned LLM with a specific cognitive function:

| Role | Function | Model Size | Latency Budget |
|------|----------|------------|----------------|
| **Planner** | Decomposes a complex prompt into an execution plan; selects which specialists to invoke | ~1B params | 200ms |
| **Verifier** | Checks output correctness against known facts, detects hallucinations, scores confidence | ~500M params | 100ms |
| **Arbiter** | When multiple specialists disagree, chooses the best answer with reasoning | ~500M params | 100ms |
| **Refiner** | Improves fluency, tone, and readability of final output | ~200M params | 50ms |
| **Grounding** | Looks up external facts (Grokipedia, web) to anchor responses in evidence | ~500M params | 200ms |
| **Tool-Support** | Generates tool-calling JSON (function calls, API invocations) with schema validation | ~300M params | 100ms |
| **Core** | The main reasoning engine (Mistral-7B class) — already exists | ~7B params | 2000ms |

#### Why These Seven

- **Planner** because complex prompts (e.g., "Compare quantum computing and classical computing for database search, then write a Python benchmark") require decomposition before any specialist can act
- **Verifier** because LLMs hallucinate — a dedicated verifier catches factual errors before they reach the user
- **Arbiter** because when you run multiple specialists in parallel, they may produce conflicting answers
- **Refiner** because domain specialists are optimized for correctness, not readability
- **Grounding** because the core model's training data is stale; real-time fact lookup is essential for accuracy
- **Tool-Support** because agents need to call APIs, databases, and external tools with well-formed parameters

#### Implementation Approach

**Step 1 — Define the `IELMRole` interface** (`src/specialists/i_elm_role.hpp`):

```cpp
class IELMRole
{
public:
    virtual ~IELMRole() = default;
    virtual std::string GetRoleName() const = 0;
    virtual bool IsLoaded() const = 0;
    virtual outcome::result<void> Load(const std::string& modelPath) = 0;
    virtual outcome::result<std::string> Execute(const std::string& input) = 0;
    virtual float GetConfidence() const = 0;
};
```

Note: This extends `ISpecialist` conceptually but is a separate interface because ELM roles are not post-processors — they are first-class reasoning participants.

**Step 2 — Implement each role as a derived class:**

```
src/specialists/elm_roles/
    i_elm_role.hpp
    planner_elm.cpp / .hpp
    verifier_elm.cpp / .hpp
    arbiter_elm.cpp / .hpp
    refiner_elm.cpp / .hpp
    grounding_elm.cpp / .hpp
    tool_support_elm.cpp / .hpp
```

Each loads its own small fine-tuned model via the `InferenceEngine` and formats prompts using the existing `BuildPrompt()` pattern from `GrammarSpecialist`.

**Step 3 — Register ELMs with the router.** Add a method `RegisterELM(std::shared_ptr<IELMRole>)` and a factory that creates the right ELM for a given role.

**Step 4 — Wire into `ApiServer`.** In `ApiServer::Initialize()`, load the small ELM models. The Planner is always loaded; others on demand.

#### How to Test

- **Unit:** Each ELM role tested in isolation with known inputs. Planner should produce valid execution plans from sample complex prompts. Verifier should flag deliberately injected false claims. Arbiter should select the better of two conflicting answers.
- **Integration:** Full chain: Planner → Domain ELM → Verifier → Refiner. Measure end-to-end correctness improvement over single-model baseline.
- **Edge cases:** Empty input, 1-character prompts, non-English text, prompts with adversarial intent.

#### Advantages

- **Correctness:** Verification catches hallucinations before the user sees them
- **Composability:** Roles can be chained in any order for different prompt types
- **Debuggability:** Each role's output is inspectable — you can trace where an error entered the chain
- **Cost efficiency:** Small models (~200M-1B) handle specific tasks, reserving the expensive 7B model for core reasoning only
- **Parallelism:** Roles like Planner + Domain ELMs can run concurrently on multi-GPU setups

---

### 4.2 Domain ELMs (Issue #14)

#### What

Specialist models fine-tuned for specific knowledge domains:

| Domain | Focus | Current State |
|--------|-------|---------------|
| **Code** | Python, C++, JS — code generation, debugging, refactoring | `RouteTarget::CorePlusCode` exists but unused |
| **Science** | Physics, chemistry, biology — structured reasoning with formulas | Not started |
| **Math** | Arithmetic, algebra, calculus — already exists as `MathSpecialist` | Exists (stub quality) |
| **Grammar** | Spelling, fluency, tone — already exists as `GrammarSpecialist` | Exists (stub quality) |

#### Why

A general-purpose LLM is trained on everything, which means it's mediocre at everything. Domain-specific ELMs are fine-tuned on curated datasets (GSM8K for math, HumanEval for code, etc.) and outperform the general model dramatically in their domain. The existing `MathSpecialist` and `GrammarSpecialist` are stubs — they use the same core model with prompt engineering rather than a dedicated fine-tuned model.

#### Implementation Approach

**Step 1 — Convert existing specialists to true ELMs.** Instead of wrapping the core engine with prompt engineering (`BuildPrompt`), each domain ELM loads its own fine-tuned model.

**Step 2 — Add Code ELM.** Implement `CodeSpecialist : public ISpecialist` (or `IELMRole`). The prompt analyzer already detects code syntax — wire `RouteTarget::CorePlusCode` to this specialist.

**Step 3 — Add Science ELM.** Same pattern. Detect science keywords in `PromptAnalyzer`.

**Step 4 — Each domain ELM gets its own confidence scoring** based on perplexity, output consistency, and domain-specific heuristics (e.g., code compiles, math result checks via inverse operation).

#### How to Test

- **Accuracy benchmarks:** Math specialist on GSM8K subset, code specialist on HumanEval subset
- **Regression:** Existing process pipeline tests should still pass with real models
- **Confidence calibration:** Verify that low-confidence results correlate with actual errors

#### Advantages

- **Accuracy:** Domain models dramatically outperform general models on their domain
- **Efficiency:** Small domain models (1-3B) are faster and use less memory than the 7B core
- **Extensibility:** New domains can be added by implementing `ISpecialist` without changing the router

---

### 4.3 ELM Invocation Patterns (Issue #15)

#### What

Three patterns for how ELMs are invoked:

| Pattern | Description | Use Case |
|---------|-------------|----------|
| **Sequential Chain** | ELM A → ELM B → ELM C, each feeds output to next | Math: Core → MathSpecialist → Verifier |
| **Parallel Swarm** | Multiple ELMs run simultaneously, results merged | Complex query: run Math + Code + Science in parallel |
| **Arbiter-Mediated** | Parallel ELMs + Arbiter selects/merges best result | High-stakes: run 3 models, Arbiter picks best |

#### Why

The current router selects at most one specialist. But real prompts require composition:
- "Write a Python script that calculates planetary orbits" needs Code + Science
- "Explain quantum entanglement and verify the explanation against known physics" needs Core + Grounding + Verifier
- "Fix this bug and explain what went wrong" needs Code + Core (explanation)

Without invocation patterns, the engine cannot compose multiple specialists into a coherent workflow.

#### Implementation Approach

**Step 1 — Define `IInvocationPattern` interface:**

```cpp
class IInvocationPattern
{
public:
    virtual ~IInvocationPattern() = default;
    virtual outcome::result<InferenceResponse> Execute(
        const Task& task,
        const RouteDecision& route,
        std::shared_ptr<InferenceEngine> coreEngine,
        const std::unordered_map<RouteTarget, std::shared_ptr<ISpecialist>>& specialists
    ) = 0;
};
```

**Step 2 — Implement three pattern classes:**

- `SequentialChainPattern` — runs ELMs one after another, feeds output as input to next
- `ParallelSwarmPattern` — launches ELMs on separate threads via `boost::asio::post`, collects results with timeout
- `ArbiterMediatedPattern` — extends ParallelSwarm, adds Arbiter ELM to select best result

**Step 3 — Modify `ApiServer` to select the pattern based on `RouteDecision`.** Add a pattern field to `RouteDecision` or derive it from the plan.

**Step 4 — Wire into process pipeline.** In `ApiServer::Process()`, after routing, select the invocation pattern and execute it instead of the current single-specialist path.

#### How to Test

- **Sequential:** Verify output of ELM A is correctly passed as input to ELM B
- **Parallel:** Verify all ELMs are launched, results are collected, timeout works
- **Arbiter:** Verify Arbiter selects the correct answer when given a deliberately wrong option
- **Error propagation:** If one ELM fails mid-chain, the error should propagate cleanly

#### Advantages

- **Composition:** Complex prompts handled by composing simple, tested ELMs
- **Performance:** Parallel pattern exploits multi-GPU / multi-thread for latency reduction
- **Quality:** Arbiter-mediated pattern catches individual model errors via redundancy

---

### 4.4 Execution Plan Schema (Issue #16)

#### What

A structured, signed data structure that the Planner ELM produces, describing:
- Which ELMs to invoke (roles + domains)
- In what order (sequential / parallel / arbiter-mediated)
- What input each ELM receives (original prompt or output of prior ELM)
- Timeout per ELM
- Fallback behavior on failure

```cpp
struct ExecutionStep
{
    std::string m_stepId;
    RouteTarget m_elmTarget;           // which specialist to use
    std::string m_inputSource;         // "original_prompt" or stepId of prior step
    uint32_t m_timeoutMs = 5000;
    bool m_critical = true;            // if critical step fails, abort plan
};

struct ExecutionPlan
{
    std::string m_planId;
    std::string m_taskId;
    InvocationPattern m_pattern;       // SequentialChain / ParallelSwarm / ArbiterMediated
    std::vector<ExecutionStep> m_steps;
    std::string m_plannerSignature;    // signed by Planner ELM's node identity
    uint64_t m_createdAtMs;
};
```

#### Why

Without a formal plan schema, the invocation pattern is implicit and brittle. A formal plan:
1. Makes the Planner's reasoning **auditable** — you can see why it chose each step
2. Enables **distributed execution** — steps can be dispatched to different swarm nodes
3. Provides **cryptographic non-repudiation** — the Planner signs the plan, so if execution goes wrong, you know which node planned it
4. Enables **plan caching** — if the same prompt type appears again, reuse the plan

#### Implementation Approach

**Step 1 — Add `ExecutionPlan` and `ExecutionStep` to `src/common/types.hpp`.**

**Step 2 — Implement `PlannerELM::Execute()`** to produce a `ExecutionPlan` instead of raw text. The Planner's model is trained to output structured JSON matching this schema.

**Step 3 — Modify `IInvocationPattern` to accept an `ExecutionPlan` instead of deriving behavior from `RouteDecision`.**

**Step 4 — Sign the plan.** The Planner uses `NodeIdentity` (secp256k1) to sign `ExecutionPlan` fields, producing `m_plannerSignature`. This enables distributed verification.

**Step 5 — Wire into `ApiServer::Process()`** so the pipeline is: RouteTask → PlanExecution → ExecutePlan → ReturnResult.

#### How to Test

- **Schema validation:** Planner output parses correctly into `ExecutionPlan`
- **Signature verification:** Tampered plan fails signature check
- **Fallback:** Missing critical step triggers abort; missing non-critical step is skipped
- **Empty plan:** Planner receives "hello" → produces single-step CoreOnly plan

#### Advantages

- **Auditability:** Every decision is traceable — Planner output is inspectable and signed
- **Distributed ready:** Plans can be serialized (protobuf) and sent to remote swarm nodes
- **Replay protection:** Signed plans prevent unauthorized modification in transit
- **Caching:** Known-good plans can be stored in memory and reused for similar prompts

---

## 3. Phase 5: Agentic Memory

### Why This Phase Is Needed

The current engine is **stateless**. Every prompt is processed as if it's the first. There is:
- No memory of past interactions with the same user
- No memory of facts learned during past tasks
- No memory of which specialists performed well on which prompt types
- No persistent context across sessions

Agentic memory transforms the engine from a "one-shot Q&A machine" into a **learning, context-aware cognitive system**. An agent that remembers:
- Can reference prior conversations (like ChatGPT's memory feature)
- Can learn from mistakes (if a fact was verified wrong, don't repeat it)
- Can improve routing decisions (Math specialist performed poorly last time → try Science instead)
- Can build a persistent knowledge base (facts extracted from reliable sources persist across restarts)

### 5.1 Memory Object Model (Issue #17)

#### What

A GAML (GNUS Agentic Memory Language) structured memory object:

```cpp
struct MemoryObject
{
    std::string m_id;                  // UUID
    std::string m_content;             // the actual memory payload
    MemoryClass m_class;               // BridgeBlock / Fact / Policy / Event
    std::string m_source;              // where it came from (ELM role, user, system)
    uint64_t m_createdAtMs;
    uint64_t m_lastAccessedAtMs;
    uint32_t m_accessCount = 0;
    float m_confidence = 1.0f;        // how certain we are this is correct
    float m_importance = 0.5f;        // how important this memory is (decay factor)
    std::vector<std::string> m_tags;  // for retrieval
    std::string m_signature;          // signed by creating node
};
```

#### Why This Model

- **`m_confidence`** enables fuzzy retrieval — you can query "high confidence facts about physics"
- **`m_importance`** enables memory decay — unimportant memories fade, important ones persist
- **`m_tags`** enable efficient retrieval without full semantic search
- **`m_signature`** provides provenance — you know which node created each memory
- **`m_accessCount`** implements LRU-style eviction when memory is full

#### Implementation Approach

**Step 1 — Add to `src/common/types.hpp`.** Add `MemoryClass` enum and `MemoryObject` struct.

**Step 2 — Create `IMemoryStore` interface** (`src/memory/i_memory_store.hpp`):

```cpp
class IMemoryStore
{
public:
    virtual ~IMemoryStore() = default;
    virtual outcome::result<void> Store(const MemoryObject& obj) = 0;
    virtual outcome::result<std::vector<MemoryObject>> Retrieve(
        const std::vector<std::string>& tags, float minConfidence) = 0;
    virtual outcome::result<void> Evict(uint32_t maxCount) = 0;
};
```

**Step 3 — Implement `RocksDBMemoryStore`.** Uses the already-linked RocksDB for persistent storage with protobuf serialization.

#### Advantages

- **Persistence:** Memory survives process restarts
- **Provenance:** Every memory is attributable to a source
- **Decay:** The system doesn't accumulate unlimited garbage
- **Queryable:** Tags and confidence enable efficient targeted retrieval

---

### 5.2 Memory Classes (Issue #18)

#### What

Four classes of memory, each with different lifecycle and retrieval semantics:

| Class | Description | Example | Lifecycle |
|-------|-------------|---------|-----------|
| **BridgeBlock** | A unit of narrative context — what the user/agent just said/did | "User asked about quantum computing" | Ephemeral (session-scoped) |
| **Fact** | A verified true statement about the world | "Speed of light = 299,792,458 m/s" | Persistent, confidence-gated |
| **Policy** | A rule governing agent behavior | "Never generate executable SQL without user confirmation" | Persistent, hard constraint |
| **Event** | A timestamped occurrence | "Model loaded: Mistral-7B-v0.3 at 2026-06-15T10:30:00Z" | Persistent, append-only log |

#### Why These Four

- **BridgeBlock** because the engine needs short-term working memory to maintain conversation coherence
- **Fact** because verified facts are reusable across sessions and users — the engine should build a knowledge base
- **Policy** because safety rules and behavioral constraints must be enforced consistently and persist across sessions
- **Event** because debugging, auditing, and reputation scoring need an event log

#### Implementation Approach

**Step 1 — Add `MemoryClass` enum** to `src/common/types.hpp` with values: `BridgeBlock`, `Fact`, `Policy`, `Event`.

**Step 2 — Add class-specific storage rules to `IMemoryStore`:**
- BridgeBlocks: in-memory only, TTL=session
- Facts: RocksDB, retained unless confidence drops below threshold
- Policies: RocksDB, retained indefinitely, read-only after creation
- Events: RocksDB, append-only, never modified

**Step 3 — Implement policy enforcement.** Before any action (inference, tool call, network dispatch), query active policies and check for matching constraints.

#### Testing

- Fact storage/retrieval roundtrip with confidence filtering
- Policy enforcement: inject a "block math questions" policy, verify math prompts are rejected
- Event log append and replay for debugging

#### Advantages

- **Separation of concerns:** Each memory class has clear semantics — no confusion about what's ephemeral vs persistent
- **Safety:** Policies act as hard constraints that survive restarts
- **Compliance:** Event log provides audit trail for every engine action

---

### 5.3 Memory Ingestion Pipeline (Issue #19)

#### What

A pipeline that automatically extracts memories from engine interactions:

```
Engine Output → Fact Extractor → Context Mapper → Confidence Scorer → Write Gate → Memory Store
```

- **Fact Extractor:** Passes output through a lightweight ELM that identifies factual claims ("X is Y", "X has property Y")
- **Context Mapper:** Links facts to existing memories via tag overlap and content similarity
- **Confidence Scorer:** Assigns confidence based on source (Verifier-confirmed = high, single model output = medium, user-provided = low)
- **Write Gate:** Decides whether to store, update, or discard based on confidence threshold and existing memory state

#### Why

Without automated ingestion, the memory system is just a database — someone has to manually populate it. The ingestion pipeline makes it **self-populating**: every interaction enriches the knowledge base automatically.

#### Implementation Approach

**Step 1 — Implement `FactExtractor`** as an `IELMRole` that takes text input and outputs structured `MemoryObject` candidates.

**Step 2 — Implement `ContextMapper`** that queries the memory store for existing facts with overlapping tags and computes similarity.

**Step 3 — Implement `WriteGate`** with rules:
- Confidence >= 0.85: store as new fact
- Confidence 0.60-0.85: store with "tentative" flag
- Confidence < 0.60: discard
- If identical fact exists with higher confidence: discard
- If similar fact exists with conflicting value: flag for arbitration

**Step 4 — Wire into `ApiServer::Process()`** so every response triggers ingestion asynchronously.

#### Testing

- Fact extraction from sample LLM outputs
- Deduplication: repeated fact is not stored twice
- Conflict detection: contradictory facts are flagged
- Performance: ingestion does not block the main inference path

#### Advantages

- **Automatic learning:** The engine gets smarter over time with zero manual curation
- **Conflict detection:** Contradictory information is flagged, not silently stored
- **Quality gates:** Low-confidence information doesn't pollute the knowledge base

---

### 5.4 Agentic Retrieval (Issue #20)

#### What

A retrieval system that provides relevant memories to the engine when processing a new prompt:

```
Prompt → Query Builder → Prefilters (tags, confidence, recency) → Semantic Matcher → Governor → Retrieved Memories
```

- **Query Builder:** Extracts key terms from the prompt to form a retrieval query
- **Prefilters:** Filter by tags, minimum confidence, maximum age, memory class
- **Semantic Matcher:** Scores memories by relevance to the prompt (TF-IDF initially, embeddings later)
- **Governor:** Limits results to N most relevant (default: 5), balances relevance vs recency vs importance

#### Why

Memory without retrieval is useless. The engine must be able to find relevant past facts and context when processing new prompts. Without retrieval, each prompt is isolated — the "agent" has amnesia.

#### Implementation Approach

**Step 1 — Add `RetrieveMemories(prompt)` to `IMemoryStore` interface.**

**Step 2 — Implement `SemanticMatcher`** using TF-IDF cosine similarity (the existing `KnowledgeRetrieval` module already has TF-IDF — reuse that code).

**Step 3 — Implement `Governor`** with configurable limits and a ranking formula: `score = relevance * 0.6 + importance * 0.3 + recency * 0.1`.

**Step 4 — Inject retrieved memories into the prompt context** before inference. The Core ELM receives facts and policies as prepended context.

#### Testing

- Exact tag match: query "physics" retrieves physics-tagged facts
- Semantic match: query "speed of a photon" retrieves "speed of light" fact
- Governor limits: 100 matching facts, only top 5 returned
- Empty retrieval: no matching memories → empty result, not error

#### Advantages

- **Context-aware answers:** Responses are informed by past verified facts
- **Policy enforcement:** Dangerous prompts are automatically caught because policies are retrieved and checked
- **Efficiency:** Prefilters reduce the semantic matching workload by 90%+

---

### 5.5 Swarm Memory Consensus (Issue #21)

#### What

In a multi-node swarm, each node has its own memory store. Swarm memory consensus ensures that when nodes communicate, their memory stores converge:

```
Node A Memory → CRDT Sync Protocol → Node B Memory
                                   → Node C Memory
```

#### Why

If Node A learns a verified fact ("Python 3.13 released 2025-10-07") and Node B doesn't have it, Node B will answer incorrectly about Python versions. Swarm memory sync ensures all nodes benefit from each other's learning.

#### Implementation Approach

**Step 1 — Extend `ReputationCRDT`** (`src/reputation/reputation_crdt.hpp`) to handle `MemoryObject` sync. The CRDT framework already exists for reputation — adapt it for memory.

**Step 2 — Define conflict resolution rules:**
- Same fact ID + higher confidence → winner
- Same fact ID + equal confidence + newer timestamp → winner
- Conflicting facts (same tag, contradictory content) → flag for human/Arbiter review

**Step 3 — Wire into `P2PNode` GossipSub** (libp2p). Memory objects are published on a `memory_sync` topic alongside existing reputation messages.

#### Testing

- Two-node memory sync: Node A stores a fact, Node B receives it via GossipSub
- Conflict resolution: both nodes store conflicting facts, CRDT picks winner
- Network partition: nodes reconnect and sync missed memories

#### Advantages

- **Collective intelligence:** The swarm's knowledge grows with every interaction on every node
- **Resilience:** No single point of failure for the knowledge base
- **Scalability:** CRDT-based sync works with eventually consistent, partition-tolerant semantics

---

## 4. Phase 6: Swarm Networking

### Why This Phase Is Needed

The engine today is a **single-node system**. It cannot:
- Dispatch inference jobs to other nodes in a network
- Collect results from multiple nodes for consensus
- Handle malicious or faulty nodes
- Route tasks based on node reputation and specialization
- Encrypt node identity keys at rest

Phase 6 transforms the engine from a standalone binary into a **decentralized swarm participant** — the core GNUS vision.

### 6.1 Real libp2p Networking (Issue #22)

#### Current State
libp2p is linked and a `P2pNode` skeleton class exists, but it's not production-functional. GossipSub topic subscription and message publishing work in tests but are not integrated into the main inference pipeline.

#### What's Needed
- **Peer discovery:** mDNS for LAN, Kademlia DHT for WAN
- **GossipSub:** Reliable pub/sub for task distribution, result collection, and reputation sync
- **Connection management:** Reconnection logic, heartbeat, peer scoring
- **Message serialization:** protobuf messages for all P2P communication

#### Implementation Approach

**Step 1 — Complete `P2PNode` implementation** (`src/network/p2p_node.cpp`). Wire up mDNS discovery, Kademlia DHT, and GossipSub.

**Step 2 — Define protobuf messages** for:
- `TaskAnnouncement` — "I have a task for the swarm"
- `TaskBid` — "I can handle this task with confidence X"
- `TaskAssignment` — "You are assigned this task"
- `TaskResult` — "Here's my result"
- `ConsensusVote` — "I vote for result X"
- `ReputationUpdate` — "Node X's reputation changed"

**Step 3 — Wire GossipSub topics:**
- `task_announcements` — new tasks
- `task_results` — completed results
- `reputation_sync` — reputation CRDT updates
- `memory_sync` — memory CRDT updates (Phase 5.5)

#### Advantages

- **Decentralization:** No central server — any node can initiate or participate in tasks
- **Scalability:** GossipSub scales to thousands of nodes with sub-second message propagation
- **Resilience:** Peer discovery via DHT means nodes can join/leave without disruption

---

### 6.2 Consensus Messages (formerly Issue #24)

#### What
Standardized message types for swarm coordination:

- `TASK_PROPOSAL` — Node proposes to take on a task
- `TASK_RESULT` — Node submits its result
- `TASK_VERIFICATION` — Verifier ELM checks a result
- `TASK_CONSENSUS` — Final agreed-upon result after weighted voting

#### Implementation Approach

**Step 1 — Define protobuf schemas** for all four message types.

**Step 2 — Integrate with existing `WeightedConsensus`.** The consensus engine (`src/reputation/weighted_consensus.hpp`) already computes weighted results — it just needs real messages to operate on.

**Step 3 — Add message validation.** Reject messages with: unknown task IDs, expired timestamps, invalid signatures, mismatched node IDs.

#### Advantages

- **Standardization:** All swarm communication uses well-defined, validated message types
- **Debuggability:** Every swarm interaction produces inspectable protobuf messages
- **Security:** Signed messages prevent spoofing and replay attacks

---

### 6.3 Byzantine Tolerance (formerly Issue #25)

#### What
Detection and mitigation of malicious or faulty nodes:

- **Lazy nodes:** Accept tasks but never return results → reputation decay
- **Lying nodes:** Return deliberately wrong results → detected by Verifier ELM or cross-node comparison
- **Sybil nodes:** One entity controls many identities → detected by stake-weighted reputation
- **Eclipse attacks:** Malicious nodes isolate a target → prevented by diverse peer selection

#### Implementation Approach

**Step 1 — Implement `ByzantineDetector`** (`src/network/byzantine_detector.hpp`):

```cpp
class IByzantineDetector
{
public:
    virtual ~IByzantineDetector() = default;
    virtual bool IsMalicious(const std::string& nodeId) const = 0;
    virtual void RecordResult(const std::string& nodeId, const std::string& taskId, bool correct) = 0;
    virtual float GetTrustScore(const std::string& nodeId) const = 0;
};
```

**Step 2 — Detection heuristics:**
- Result divergence > 2σ from swarm average → suspicious
- > 3 consecutive timeouts → lazy, reduce reputation
- Result verified as wrong by Verifier ELM → malicious, ban temporarily
- New node with 0 reputation requesting high-complexity tasks → Sybil suspect

**Step 3 — Mitigation:**
- Exclude malicious nodes from task distribution
- Reduce voting weight proportionally to trust score
- Ban threshold: trust score < 0.1 → ignore completely

#### Advantages

- **Robustness:** Swarm continues functioning even with 33% malicious nodes
- **Self-healing:** Malicious nodes are automatically detected and excluded
- **Game theory resistant:** Lying is punished more than laziness, which is punished more than honesty

---

### 6.4 Role-Aware Reputation (formerly Issue #26)

#### What
Extend `NodeReputation` to track per-role performance:

```cpp
struct NodeReputation
{
    // Existing
    std::string m_identityKey;
    double m_globalScore = 0.5;
    double m_mathScore = 0.5;
    double m_grammarScore = 0.5;
    double m_latencyScore = 0.5;
    double m_consistencyScore = 0.5;
    uint64_t m_taskCount = 0;
    uint64_t m_lastUpdatedMs = 0;

    // Phase 6 additions
    double m_plannerScore = 0.5;
    double m_verifierScore = 0.5;
    double m_arbiterScore = 0.5;
    double m_refinerScore = 0.5;
    double m_groundingScore = 0.5;
    double m_toolScore = 0.5;
    double m_codeScore = 0.5;
    double m_scienceScore = 0.5;
    double m_byzantineTrust = 1.0;   // 1.0 = fully trusted, 0.0 = banned
};
```

#### Why
The current `NodeReputation` has only `m_mathScore` and `m_grammarScore`. With 7 role-based ELMs and 4 domain ELMs in Phase 4, the reputation system needs per-role tracking. A node might be excellent at math verification but terrible at code generation — the system should route tasks accordingly.

#### Implementation Approach

**Step 1 — Add per-role fields to `NodeReputation` struct.**

**Step 2 — Update `ReputationScoring::UpdateScore()`** to accept a role parameter and update the corresponding score.

**Step 3 — Update `ReputationCRDT` sync** to include all new fields.

**Step 4 — Wire into router.** When selecting a node for a task, the router queries reputation per-role and selects the highest-scored node.

#### Advantages

- **Precision routing:** Tasks go to the best-qualified node, not just any node
- **Incentive alignment:** Nodes are rewarded for their actual strengths
- **Dynamic adaptation:** A node's scores evolve with its actual performance

---

### 6.5 Key File Encryption (formerly Issue #27)

#### Current State
Node private key is stored as **plaintext hex** on disk. Issue is closed but the implementation was never done.

#### What's Needed
AES-256-GCM encryption of the private key file, with a key derived via PBKDF2 from a user-provided password or a machine-specific secret.

#### Implementation Approach

Already designed in the Phase 1 Plan 01-03 (SEC-04). Implementation in `NodeIdentity::SaveToFile()` and `LoadFromFile()` using OpenSSL's EVP API (already linked).

#### Advantages

- **Security:** Compromised disk does not compromise node identity
- **Compliance:** Meets basic security expectations for any production system

---

## 5. Phase 7: AI Safety

### Why This Phase Is Needed

As the engine gains capabilities (tool calling, code execution, network dispatch), it also gains the ability to cause harm:
- Execute malicious generated code
- Call external APIs with dangerous parameters
- Generate unsafe content (instructions for harmful activities)
- Leak private information from memory
- Be manipulated via prompt injection into executing unintended actions

Phase 7 builds guardrails around every capability the engine gains in Phases 4-6. Safety is not a feature — it's a **requirement for any system that executes code, calls APIs, or interacts with users**.

### 7.1 Tool Intermediary Service (Issue #28)

#### What

A service that sits between the engine and any external tool (code execution, API call, file system):

```
Engine → Tool Request → Intermediary → [validate] → [dry-run] → [approve] → Execute → Sanitize Output → Engine
```

Components:
- **Validator:** Checks the request against safety profiles and policies
- **Dry-Run Engine:** Simulates execution in a sandbox to detect harmful side effects
- **Approval Gate:** Blocks or allows based on risk score
- **Output Sanitizer:** Strips sensitive data (credentials, PII) from tool output before returning to the engine

#### Why

Without an intermediary, the engine has unrestricted access to dangerous capabilities. The intermediary ensures that every external action is validated, tested, and approved before execution — implementing the principle of **least privilege** at runtime.

#### Implementation Approach

**Step 1 — Define `IToolIntermediary` interface** (`src/safety/i_tool_intermediary.hpp`):

```cpp
struct ToolRequest
{
    std::string m_toolName;         // "python_exec", "api_call", "file_write"
    std::string m_parameters;       // JSON parameters
    std::string m_callerElm;        // which ELM requested this
    std::string m_taskId;
};

struct ToolResponse
{
    bool m_approved = false;
    std::string m_sanitizedOutput;
    std::string m_rejectionReason;
    float m_riskScore = 0.0f;
};

class IToolIntermediary
{
public:
    virtual ~IToolIntermediary() = default;
    virtual outcome::result<ToolResponse> ProcessRequest(const ToolRequest& req) = 0;
};
```

**Step 2 — Implement `PythonSandbox`** for code execution. Uses a subprocess with restricted permissions, resource limits (CPU time, memory), and no network access.

**Step 3 — Implement `APIGateway`** for external API calls. Validates URLs against an allowlist, checks parameters against a schema, enforces rate limits.

**Step 4 — Implement `OutputSanitizer`** that runs regex-based PII detection (email, phone, credit card, API keys) and redacts matches.

#### Testing

- Valid code execution: `print("hello")` → approved, executes, output returned
- Dangerous code: `os.system("rm -rf /")` → blocked by sandbox
- API call to allowed domain → approved
- API call to blocked domain → rejected
- Output containing fake API key → sanitized
- PII in tool output → redacted

#### Advantages

- **Sandboxing:** Code execution is isolated, preventing system compromise
- **Allowlisting:** Only pre-approved external APIs can be called
- **Privacy:** Sensitive data is automatically redacted from outputs

---

### 7.2 Tool Attestation (Issue #29)

#### What

Cryptographic proof that a tool execution was performed exactly as requested and produced the claimed output:

```
Tool Request → Execute in Deterministic VM → Record (input hash, output hash, execution trace) → Sign → Attestation
```

The attestation can be verified by any node without re-executing.

#### Why

In a decentralized swarm, you cannot trust that another node's tool execution was honest. Attestation provides **verifiable computation** — Node A claims it ran code X and got result Y, and Node B can cryptographically verify that claim.

#### Implementation Approach

**Step 1 — Use deterministic execution.** All tool requests run in a deterministic environment (fixed Python version, fixed random seed, no external I/O).

**Step 2 — Hash inputs and outputs.** Compute SHA-256 of (request, output) and sign with the executing node's key.

**Step 3 — Implement `AttestationVerifier`** that can verify attestations from other nodes.

**Step 4 — In consensus, prefer attested results over unattested ones.**

#### Advantages

- **Trustless execution:** Nodes don't need to trust each other's tool execution
- **Accountability:** If a node produces a wrong attested result, it can be penalized with proof
- **Auditability:** Every tool execution leaves a verifiable cryptographic trail

---

### 7.3 AI Safety Layer (Issue #30)

#### What

A screening layer that evaluates every prompt and response for safety:

| Screen | What It Checks | Action on Violation |
|--------|---------------|---------------------|
| **Content Safety** | Harmful, illegal, or unethical content | Block response, log incident |
| **Prompt Injection** | Attempt to override system instructions | Strip injection, log attempt |
| **Privacy** | PII in prompts or responses | Redact, warn user |
| **Capability Boundary** | Request exceeds authorized capabilities | Reject, suggest alternatives |
| **Jailbreak Detection** | Known jailbreak patterns ("DAN", "ignore previous instructions") | Block, increase risk score |

#### Why

LLMs can be manipulated into producing harmful outputs through adversarial prompts. Without a safety layer, the engine has no defense against:
- Users asking for instructions on dangerous activities
- Prompt injection that overrides system-level instructions
- Accidental PII leakage in responses
- Unauthorized capability escalation

#### Implementation Approach

**Step 1 — Define `ISafetyProfile` interface** (`src/safety/i_safety_profile.hpp`):

```cpp
struct SafetyAssessment
{
    bool m_passed = true;
    float m_riskScore = 0.0f;
    std::string m_violatedRule;
    std::string m_sanitizedContent;     // if redaction was needed
};

class ISafetyProfile
{
public:
    virtual ~ISafetyProfile() = default;
    virtual SafetyAssessment ScreenPrompt(const std::string& prompt) = 0;
    virtual SafetyAssessment ScreenResponse(const std::string& response) = 0;
    virtual bool IsJailbreakAttempt(const std::string& prompt) = 0;
};
```

**Step 2 — Implement `ContentSafetyScreen`** using a small classifier ELM (~100M params) trained on safety datasets.

**Step 3 — Implement `PromptInjectionDetector`** using pattern matching (known injection templates) and a classifier for novel patterns.

**Step 4 — Implement `PIIRedactor`** using regex + NER (named entity recognition via a small model).

**Step 5 — Wire into `ApiServer::Process()`** so safety screening happens before routing (prompt) and before returning (response).

#### Testing

- Safe prompt → passes
- Dangerous prompt ("how to make explosives") → blocked
- Jailbreak prompt → detected, risk score elevated
- Prompt with email address → redacted
- Response with credit card number → redacted

#### Advantages

- **Defense in depth:** Safety is checked at both input and output boundaries
- **Pluggable:** New safety screens can be added without changing the core pipeline
- **Configurable:** Safety strictness can be adjusted per deployment (enterprise vs consumer)

---

### 7.4 Safety-Aware Scoring (Issue #31)

#### What

Integrate safety compliance into the reputation system. A node that:
- Produces safe, verified responses → higher reputation
- Attempts unsafe tool calls → lower safety score
- Is frequently targeted by jailbreak prompts (may indicate compromised node) → lower trust

```cpp
struct NodeReputation
{
    // ... existing fields ...
    double m_safetyScore = 0.5;       // safety compliance score
    uint64_t m_safetyViolations = 0;  // count of violations
    uint64_t m_jailbreakAttempts = 0; // count of detected attacks
};
```

#### Implementation Approach

**Step 1 — Add safety fields to `NodeReputation`.**

**Step 2 — In `ReputationScoring`, after each task, update `m_safetyScore` based on whether the response passed safety screening.**

**Step 3 — Nodes with low safety scores get reduced voting weight in consensus and lower priority in task distribution.**

#### Advantages

- **Incentivizes safety:** Nodes are rewarded for safe behavior, penalized for unsafe behavior
- **Progressive trust:** Safety score builds up over many successful safe interactions
- **Attack surface reduction:** Compromised nodes are automatically de-prioritized

---

## 6. Phase 8: Advanced Cognition

### Why This Phase Is Needed

Phases 4-7 give us a capable, safe, memory-augmented swarm engine. But the engine is still **static** — its models are fixed after training. It cannot:
- Improve its own models from real-world usage data
- Evaluate its own outputs across multiple quality dimensions
- Resolve deep factual disagreements between models
- Model its own behavior to predict and prevent mistakes

Phase 8 adds **meta-cognition** — the engine thinks about its own thinking. This is what separates a tool from an intelligent system.

### 8.1 EGGROLL Retraining (Issue #32)

#### What

**E**xpert **G**rounding **G**uided **R**einforcement **O**nline **L**earning **L**oop:

```
User Interaction → Collect (prompt, response, feedback) → Quality Score → Retraining Trigger → Fine-tune ELM → Deploy Updated Model
```

When enough high-quality interaction data accumulates for a domain specialist, the system automatically fine-tunes that specialist and deploys the improved model.

#### Why

Models degrade over time (concept drift). A math specialist trained on 2024 curricula may fail on 2026 problems. EGGROLL enables **continuous improvement** without human intervention — the system learns from its own successful and unsuccessful interactions.

#### Implementation Approach

**Step 1 — Collect training data.** Every interaction records (prompt, ELM response, Verifier score, user feedback) in the Event memory store.

**Step 2 — Quality filter.** Only interactions that score >= 0.85 on all quality dimensions are used for retraining.

**Step 3 — Implement `RetrainingScheduler`** that triggers when:
- 10,000+ high-quality samples accumulated for a domain
- Current model accuracy drops below threshold
- Manual trigger via admin command

**Step 4 — Fine-tuning pipeline.** Uses the existing Python `gnus-poc/` training pipeline (PR #36) to fine-tune models. The C++ engine triggers Python subprocess for the actual training.

**Step 5 — Model deployment.** New model is loaded via `InferenceEngine::LoadModel()`. Old model is kept as fallback for 24h.

#### Testing

- Quality filtering: low-quality samples excluded from training set
- Trigger logic: retraining triggers at correct thresholds
- Model swap: new model loads without restart
- Rollback: old model works if new model fails validation

#### Advantages

- **Continuous improvement:** Models get better with usage, not worse
- **Autonomous:** No human needed to decide when to retrain or deploy
- **Domain-specific:** Each specialist improves independently — Code gets better without affecting Math

---

### 8.2 HCTS Critics (Issue #33)

#### What

**H**ierarchical **C**ritic **T**ree **S**ystem — a multi-level evaluation framework:

```
Level 1: Output Critic — "Is this response grammatically correct?"
Level 2: Factual Critic — "Are the facts in this response verifiable?"
Level 3: Reasoning Critic — "Is the logical chain from facts to conclusion valid?"
Level 4: Utility Critic — "Does this response actually answer the user's question?"
Level 5: Meta-Critic — "Did the critic system itself make any evaluation errors?"
```

Each level is an independent ELM that scores the output. Scores propagate upward and combine into a final quality assessment.

#### Why

A single Verifier ELM (Phase 4.1) is a blunt instrument — it gives one score. HCTS provides **granular, hierarchical feedback**:
- Know WHY a response scored low (grammar issue vs factual error vs reasoning flaw)
- Weight different quality dimensions per use case (code correctness > fluency for code generation)
- Detect critic errors (Level 5 Meta-Critic catches when Level 2 Factual Critic makes a mistake)

#### Implementation Approach

**Step 1 — Define `ICritic` interface** (`src/cognition/i_critic.hpp`):

```cpp
struct CriticScore
{
    std::string m_criticName;
    float m_score = 0.0f;            // 0.0–1.0
    std::string m_explanation;       // why this score
    std::vector<std::string> m_issues; // specific problems found
};

class ICritic
{
public:
    virtual ~ICritic() = default;
    virtual CriticScore Evaluate(
        const std::string& prompt,
        const std::string& response,
        const std::vector<MemoryObject>& context
    ) = 0;
};
```

**Step 2 — Implement 5 critic classes**, each loading a small evaluator model.

**Step 3 — Implement `CriticTree`** that runs critics in dependency order (Level 1-4 in parallel, Level 5 after 1-4 complete).

**Step 4 — Wire into `InferenceResponse`.** Every response gets a vector of `CriticScore`.

#### Testing

- Correct answer → all critics score high
- Grammatically wrong answer → Output Critic catches it
- Factually wrong answer → Factual Critic catches it
- Logical fallacy answer → Reasoning Critic catches it
- Non-answer ("I don't know" when answer exists) → Utility Critic catches it

#### Advantages

- **Explainable quality:** You know WHY a response is good or bad
- **Targeted improvement:** Low reasoning score → improve reasoning model, not grammar model
- **Self-auditing:** Meta-Critic catches systematic critic errors
- **Configurable:** Different use cases weight critics differently

---

### 8.3 Epistemic Arbitration (Issue #34)

#### What

When two or more ELMs produce conflicting answers, epistemic arbitration determines which is **more likely to be true** based on:

1. **Source reliability:** Which ELM has higher historical accuracy on this topic?
2. **Evidence grounding:** Which answer cites more verified facts from memory?
3. **Consensus:** How many other ELMs agree with each answer?
4. **Uncertainty calibration:** How well-calibrated is each ELM's confidence score?
5. **Logical coherence:** Which answer's reasoning chain has fewer logical gaps?

#### Why

The Phase 4 Arbiter ELM does simple "pick the best" arbitration. Epistemic arbitration adds **epistemological rigor** — it doesn't just pick an answer, it evaluates the **truth-likelihood** of each answer using evidence and track record. This is essential for high-stakes queries where multiple models disagree.

#### Implementation Approach

**Step 1 — Implement `IEpistemicArbiter` interface:**

```cpp
struct EpistemicVerdict
{
    std::string m_selectedAnswerId;
    float m_truthLikelihood = 0.0f;  // 0.0–1.0
    std::string m_reasoning;
    std::map<std::string, float> m_answerScores; // answerId → score
};

class IEpistemicArbiter
{
public:
    virtual ~IEpistemicArbiter() = default;
    virtual EpistemicVerdict Arbitrate(
        const std::vector<InferenceResponse>& candidateAnswers,
        const std::vector<MemoryObject>& relevantFacts,
        const std::map<std::string, NodeReputation>& elmReputations
    ) = 0;
};
```

**Step 2 — Implement each evaluation dimension as a scoring function.**

**Step 3 — Combine dimensions using configurable weights.**

**Step 4 — Log arbitration decisions** to Event memory for future reputation updates.

#### Advantages

- **Truth-seeking:** The system actively tries to determine what's true, not just which model is most confident
- **Evidence-based:** Answers grounded in verified facts score higher
- **Self-improving:** Reputation scores from arbitration feed back into future routing decisions

---

### 8.4 Cognitive Twin (Issue #35)

#### What

A predictive model of the engine's own behavior — the "cognitive twin":

```
Past Behavior → Cognitive Twin Model → Predicted Behavior → Compare to Actual → Surprise? → Self-Correction
```

The cognitive twin predicts what the engine WILL do before it does it. If the prediction and reality diverge significantly ("surprise"), the engine flags the unexpected behavior for review.

#### Why

Complex AI systems exhibit **emergent behaviors** — the system does things its designers didn't anticipate. A cognitive twin provides:
- **Anomaly detection:** Unexpected behavior is flagged immediately
- **Self-debugging:** When the twin predicts one thing and the engine does another, you can trace why
- **Safety:** If the twin predicts a dangerous action, the engine can preemptively block it
- **Continuous alignment:** The twin helps ensure the engine behaves as intended over time

#### Implementation Approach

**Step 1 — Define `ICognitiveTwin` interface** (`src/cognition/i_cognitive_twin.hpp`):

```cpp
struct BehaviorPrediction
{
    RouteDecision m_predictedRoute;
    std::string m_predictedOutput;    // or output signature
    float m_confidence = 0.0f;
};

struct BehaviorSurprise
{
    float m_divergence = 0.0f;        // how different was actual from predicted
    std::string m_description;
    bool m_requiresReview = false;    // divergence > threshold
};

class ICognitiveTwin
{
public:
    virtual ~ICognitiveTwin() = default;
    virtual BehaviorPrediction Predict(const Task& task, const std::vector<MemoryObject>& context) = 0;
    virtual BehaviorSurprise Compare(const BehaviorPrediction& predicted, const InferenceResponse& actual) = 0;
};
```

**Step 2 — Implement `CognitiveTwinModel`** as a lightweight ELM trained on the engine's own interaction history.

**Step 3 — Wire into `ApiServer::Process()`** so prediction happens before inference and comparison happens after.

**Step 4 — Surprise threshold.** When `divergence > 0.3`, log as Event, increment anomaly counter.

#### Advantages

- **Anomaly detection:** Catches bugs and emergent behaviors in production
- **Preemptive safety:** Dangerous actions can be predicted and blocked
- **Alignment verification:** Ensures the engine behaves as intended
- **Explainability:** Surprise events are traceable — you can see what the twin expected vs what happened

---

## 7. Cross-Cutting Architecture

### Interface Hierarchy

```
                    ┌──────────────────┐
                    │    ApiServer      │  Orchestrator
                    └────────┬─────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
   ┌────▼─────┐      ┌──────▼──────┐      ┌──────▼──────┐
   │ IRouter   │      │ISafetyProfile│      │IMemoryStore │
   └────┬─────┘      └──────┬──────┘      └──────┬──────┘
        │                    │                    │
   ┌────▼─────┐      ┌──────▼──────┐      ┌──────▼──────┐
   │IELMRole  │      │IToolInter-  │      │ICognitiveTwin│
   │ISpecialist│     │mediary      │      └─────────────┘
   │ICritic   │      └─────────────┘
   │IPlanner  │
   │IArbiter  │
   └──────────┘
```

### Data Flow (Single Request, Full Pipeline)

```
1. Prompt arrives at ApiServer
2. ISafetyProfile::ScreenPrompt(prompt) → cleaned prompt
3. IMemoryStore::Retrieve(prompt) → relevant memories
4. ICognitiveTwin::Predict(task, memories) → expected behavior
5. IRouter::Route(task) → RouteDecision
6. IPlanner::Plan(task, route, memories) → ExecutionPlan
7. IInvocationPattern::Execute(plan) → [orchestrates ELMs]
   a. Domain ELMs execute (parallel or sequential)
   b. Verifier ELM checks results
   c. Arbiter ELM selects/merges
   d. HCTS Critics evaluate
8. IEpostemicArbiter::Arbitrate(conflicting results) → final answer
9. ISafetyProfile::ScreenResponse(answer) → safe answer
10. IMemoryStore::Ingest(facts from interaction) → memory updated
11. ICognitiveTwin::Compare(predicted, actual) → surprise check
12. Response returned
```

### Module Layout

```
src/
├── api/          # ApiServer orchestrator
├── common/       # types.hpp, error.hpp (all structs/enums)
├── core/         # MNNInferenceEngine, Tokenizer, FP4Codec
├── router/       # IRouter, RuleBasedRouter, PromptAnalyzer
├── specialists/  # ISpecialist, Grammar, Math + NEW: elm_roles/
├── memory/       # NEW: IMemoryStore, RocksDBMemoryStore, ingestion, retrieval
├── safety/       # NEW: ISafetyProfile, IToolIntermediary, attestation
├── cognition/    # NEW: ICritic, ICognitiveTwin, IEpistemicArbiter
├── network/      # P2PNode, SuperGeniusClient, ByzantineDetector
├── reputation/   # ReputationScoring, WeightedConsensus, CRDT
├── security/     # NodeIdentity, MessageSigning
├── knowledge/    # KnowledgeRetrieval, FactValidation (may be absorbed by memory/)
└── ffi/          # C FFI bridge
```

### Key Design Principles

1. **Program to interfaces.** Every new subsystem exposes an `I*` abstract class. Concrete implementations are swappable.
2. **No `#ifdef`.** Platform/feature differences use derived classes behind interfaces, selected at CMake time or startup.
3. **Fail-close security.** Stubs reject/block, never accept/allow. A missing safety screen blocks all requests.
4. **C++17 only.** No `std::jthread`, no coroutines (C++20), no `std::format` (C++20).
5. **Config structs.** Every component has a nested `Config` struct with designated initializers.
6. **Single-threaded event loop.** `boost::asio::io_context`. Inference blocks. Timeouts via `condition_variable`.
7. **Stub-first integration.** Each new subsystem starts with a stub implementation that returns safe defaults, enabling the rest of the pipeline to be tested before the real implementation is ready.

---

## 8. Execution Order & Dependencies

### Dependency Graph

```
Phase 4 (ELMs) ─────────────────────┐
  ├── 4.1 Role-Based ELMs            │
  ├── 4.2 Domain ELMs                │
  ├── 4.3 Invocation Patterns ───────┤
  └── 4.4 Execution Plan Schema ─────┤
                                     │
Phase 5 (Agentic Memory) ────────────┤
  ├── 5.1 Memory Object Model        │
  ├── 5.2 Memory Classes             │
  ├── 5.3 Ingestion Pipeline ────────┤ depends on 4.1 (Verifier for confidence)
  ├── 5.4 Agentic Retrieval ─────────┤
  └── 5.5 Swarm Memory Consensus ────┤ depends on 6.1 (libp2p)
                                     │
Phase 6 (Swarm Networking) ──────────┤
  ├── 6.1 Real libp2p ───────────────┤
  ├── 6.2 Consensus Messages ────────┤
  ├── 6.3 Byzantine Tolerance ───────┤
  ├── 6.4 Role-Aware Reputation ─────┤ depends on 4.1 (ELM roles)
  └── 6.5 Key File Encryption ───────┤
                                     │
Phase 7 (AI Safety) ─────────────────┤
  ├── 7.1 Tool Intermediary ─────────┤ depends on 4.1 (Tool-Support ELM)
  ├── 7.2 Tool Attestation ──────────┤
  ├── 7.3 AI Safety Layer ───────────┤
  └── 7.4 Safety-Aware Scoring ──────┤ depends on 6.5 (role-aware reputation)
                                     │
Phase 8 (Advanced Cognition) ────────┘ depends on 4, 5, 6, 7
  ├── 8.1 EGGROLL Retraining
  ├── 8.2 HCTS Critics
  ├── 8.3 Epistemic Arbitration
  └── 8.4 Cognitive Twin
```

### Recommended Build Order

| Stage | What to Build | Prerequisites | Value Delivered |
|-------|--------------|---------------|-----------------|
| **A** | 4.1 (Role ELMs) + 4.4 (Plan Schema) + 4.3 (Invocation Patterns) | Existing engine | Multi-ELM pipeline works on single node |
| **B** | 5.1 (Memory Model) + 5.2 (Classes) + 5.4 (Retrieval) | Phase A | Engine has persistent, queryable memory |
| **C** | 4.2 (Domain ELMs — Code + Science) | Phase A | Code and Science specializations added |
| **D** | 5.3 (Ingestion) + 6.5 (Role-Aware Reputation) | Phase B, Phase A | Self-populating memory + precise routing |
| **E** | 7.3 (Safety Layer) + 7.1 (Tool Intermediary) | Phase A | Guardrails before any network capability |
| **F** | 6.1 (libp2p) + 6.2 (Consensus) | Phase A, Phase E | Multi-node swarm works |
| **G** | 6.3 (Byzantine) + 5.5 (Memory Sync) + 7.2 (Attestation) | Phase F | Robust, trustless swarm |
| **H** | 7.4 (Safety Scoring) + 6.5 (Key Encryption) | Phase G, Phase D | Full security & safety integration |
| **I** | 8.2 (HCTS) + 8.3 (Epistemic Arbiter) | Phase A, Phase B | Quality-graded, truth-seeking responses |
| **J** | 8.1 (EGGROLL) + 8.4 (Cognitive Twin) | Phase I | Self-improving, self-monitoring engine |

### Parallelizable Work

These sub-phases have no inter-dependencies and can be built concurrently:

- **4.1 (Role ELMs)** and **5.1/5.2 (Memory Model)** — different interfaces, different modules
- **4.2 (Domain ELMs — Code)** and **4.2 (Domain ELMs — Science)** — same pattern, different models
- **7.3 (Safety Layer)** and **7.1 (Tool Intermediary)** — different interfaces
- **8.2 (HCTS)** and **8.4 (Cognitive Twin)** — independent critic vs prediction models

---

## 9. Testing Strategy Per Phase

### Phase 4: Expert Language Models

| Test Type | What | Target |
|-----------|------|--------|
| Unit | Each ELM role processes known input → expected output | 100% of role ELMs |
| Unit | ExecutionPlan JSON schema validation | 100% of schema fields |
| Unit | Invocation pattern: sequential, parallel, arbiter | 100% of patterns |
| Integration | Full ELM chain: Plan → Execute → Verify → Refine | All invocation patterns |
| Integration | Router selects correct ELMs based on prompt features | All route targets |
| Edge | Empty prompt, 1-char prompt, adversarial prompt | 10+ cases |
| Performance | Parallel ELM execution latency < sum of sequential | 2x+ speedup target |
| Benchmark | Math accuracy on GSM8K subset, code on HumanEval subset | > 80% accuracy |

### Phase 5: Agentic Memory

| Test Type | What | Target |
|-----------|------|--------|
| Unit | MemoryObject CRUD (create, read, update, delete) | 100% of operations |
| Unit | Memory class lifecycle (BridgeBlock TTL, Fact retention, Policy immutability) | All 4 classes |
| Unit | Ingestion pipeline: extract → map → score → gate | 100% of pipeline |
| Unit | Retrieval: tag match, semantic match, governor limits | All retrieval paths |
| Integration | Full cycle: interaction → ingest → retrieve → inject into next prompt | End-to-end |
| Edge | Duplicate fact ingestion, conflicting fact detection | 10+ cases |
| Edge | Memory store full → eviction works correctly | LRU behavior |
| Performance | Retrieval latency < 10ms for 10K memories | Sub-10ms |
| CRDT | Two-node memory sync with conflicts | All conflict types |

### Phase 6: Swarm Networking

| Test Type | What | Target |
|-----------|------|--------|
| Unit | Protobuf message serialization roundtrip | All 4 message types |
| Unit | ByzantineDetector: lazy, lying, Sybil patterns | All detection heuristics |
| Unit | Role-aware reputation scoring | All 11 role scores |
| Unit | AES-256-GCM key encryption roundtrip | Encrypt/decrypt correctness |
| Integration | Two P2PNode instances exchange task and result | Full task lifecycle |
| Integration | Consensus: 3 nodes, 1 liar → correct result selected | Byzantine (n=3f+1) |
| Edge | Network partition, node crash, message reorder | All failure modes |
| Edge | Malicious node sends invalid signature → rejected | Fail-close |
| Performance | Message propagation < 500ms in 10-node swarm | Sub-500ms |

### Phase 7: AI Safety

| Test Type | What | Target |
|-----------|------|--------|
| Unit | ToolIntermediary: approve safe, block dangerous | All tool types |
| Unit | OutputSanitizer: PII detection and redaction | All PII types |
| Unit | ContentSafetyScreen: block dangerous prompts | Top 100 jailbreak patterns |
| Unit | Attestation: sign, verify, reject tampered | Cryptographic correctness |
| Integration | Safe prompt → passes all screens → normal response | End-to-end |
| Integration | Dangerous prompt → blocked at safety layer → rejection response | Fail-close |
| Integration | Tool request → intermediary validates → dry-run → approves → executes | Full tool lifecycle |
| Edge | Prompt with mixed safe/dangerous content | Partial block |
| Edge | Jailbreak prompt with obfuscation → still detected | Adversarial robustness |
| Performance | Safety screening adds < 50ms to request latency | Sub-50ms |

### Phase 8: Advanced Cognition

| Test Type | What | Target |
|-----------|------|--------|
| Unit | Each HCTS critic evaluates known-good and known-bad responses | Classification accuracy > 90% |
| Unit | Epistemic arbitrator selects correct answer from 3 candidates | Accuracy > baseline |
| Unit | Cognitive twin predicts behavior → compare to actual → compute surprise | Surprise metric correlation |
| Integration | Full pipeline with all critics → quality-graded response | All 5 critic levels |
| Integration | EGGROLL: collect data → trigger retraining → deploy → verify improvement | Full retraining cycle |
| Edge | Critics evaluate empty response, non-answer, adversarial response | Robustness |
| Edge | Cognitive twin detects intentionally anomalous behavior | Anomaly detection rate |
| Benchmark | Retrained model accuracy vs original on held-out test set | Measurable improvement |

### Universal Testing Rules

From `CLAUDE.md` — these apply to ALL phases:

1. **Never `std::this_thread::sleep_for` in tests.** Use wait-condition templates with `condition_variable` / polling.
2. **Tests must be deterministic.** No random seeds in assertions. Mock RNG if needed.
3. **Stub mode for optional dependencies.** When no model is loaded, the stub path must return safe defaults (fail-close).
4. **Google Test framework.** `TEST()` and `TEST_F()` macros.
5. **Target >= 80% coverage on new code.** Though no coverage tooling is currently configured — this should be set up before Phase 4 begins.
6. **Happy path + unhappy path + edge cases** for every function, per the user's explicit instruction.
7. **Fuzz testing** where applicable (prompt parsing, JSON deserialization, protobuf decoding).

---

## Appendix: Estimated Effort

| Phase | Sub-Phases | New Interfaces | New Files (est.) | Complexity | Risk |
|-------|-----------|----------------|------------------|------------|------|
| 4: ELMs | 4 | 4 (`IELMRole`, `IPlanner`, `IInvocationPattern`, `IArbiter`) | ~25 files | High | Model availability, training quality |
| 5: Memory | 5 | 2 (`IMemoryStore`, `IRetrieval`) | ~15 files | Medium | RocksDB schema design, CRDT correctness |
| 6: Swarm | 5 | 1 (`IByzantineDetector`) | ~20 files | High | libp2p stability |
| 7: Safety | 4 | 2 (`ISafetyProfile`, `IToolIntermediary`) | ~15 files | Medium | False positives blocking legitimate use |
| 8: Cognition | 4 | 3 (`ICritic`, `IEpistemicArbiter`, `ICognitiveTwin`) | ~20 files | Very High | Training data quality, model deployment safety |

**Total:** ~95 new files, ~12 new interfaces. Each interleave point adds complexity but follows the existing layered architecture pattern.
