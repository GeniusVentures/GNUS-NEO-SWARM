# 16 Distributed Swarm Thinking Context Architecture
## 16.1 Purpose

This document extends the Genius LLM v1 architecture with a swarm-native thinking context model that explains how routing, memory, experts, synthesis, verification, and user-visible reasoning traces work together.

The goal is to make Genius LLM more than a routed collection of specialists. Instead, the system should support structured collaborative reasoning across local and distributed workers, while keeping the reasoning process inspectable, modular, grounded, and efficient.

## 16.2 Why this section exists

The current architecture describes:

- a Semantic Core
- role-based ELMs
- domain-specific experts
- a router plus planner
- swarm execution with reputation-weighted consensus
- grounding, verification, and secure agent execution

That is a strong foundation, but it does not fully describe the emerging architecture implied by the distributed swarm discussions:

- router plus memory governor behavior
- bridge block and fact-based context construction
- primary and secondary expert orchestration
- synthesis of multiple expert outputs into one coherent answer
- user-visible swarm thinking traces

This document formalizes those concepts so future routing, specialist, grounding, and quantization decisions have a shared reference.

## 16.3 Architectural intent

Genius LLM should evolve from a simple routed model into a distributed swarm reasoning system with five cooperating layers:

1. **Context and memory layer**
2. **Routing and planning layer**
3. **Primary and secondary expert execution layer**
4. **Verification, grounding, and synthesis layer**
5. **User-visible thinking context layer**

This allows the system to divide cognitive labor across smaller, specialized reasoning units instead of forcing one dense model to perform planning, solving, verification, formatting, grounding, and reconciliation all at once.

## 16.4 Core design principles

### 16.4.1 Structured collaborative reasoning over monolithic reasoning

Instead of distilling one global reasoning style into one model, Genius LLM should let multiple experts contribute distinct reasoning functions such as planning, solving, checking, grounding, and refinement.

### 16.4.2 Memory-guided context instead of brute-force long context

The system should retrieve and assemble compact, high-value context using Bridge Blocks, facts, policies, and user preferences rather than pushing large raw histories into the prompt.

### 16.4.3 Inspectable swarm thinking

The system should preserve a structured record of which experts were called, what context they used, what they produced, and how the final answer was formed.

### 16.4.4 Reputation-aware specialization

Consensus and routing should consider role-specific and domain-specific reputation rather than relying only on generic node quality.

### 16.4.5 Quantization-aware modularity

Specialist boundaries should be chosen so that FP4 Ultra, Turbo Quant, and Sparse-V can be applied efficiently to the Semantic Core, experts, and execution stages without unnecessary coupling.

## 16.5 System overview

### 16.5.1 High-level flow

1. User sends a request.
2. Router and memory governor determine task type, complexity, grounding needs, and required context.
3. Relevant Bridge Blocks, facts, policies, private knowledge sources, and user preferences are assembled.
4. A primary expert is selected for fast draft generation.
5. Optional secondary experts are selected for critique, verification, grounding, formatting, or domain augmentation.
6. A synthesis stage merges outputs into a single user-facing response.
7. A structured thinking trace is recorded and optionally exposed in the interface.
8. New facts, events, and Bridge Blocks are written back to memory.

## 16.6 Thinking context model

### 16.6.1 Definition

A thinking context is the structured, inspectable representation of how the swarm arrived at an answer.

It is not raw hidden chain-of-thought. Instead, it is a high-level event and artifact record that may include:

- routing decisions
- memory blocks selected
- facts and policies used
- private knowledge sources consulted
- grounding sources consulted
- primary draft identity and latency
- secondary expert critiques
- synthesis decisions
- final answer lineage

### 16.6.2 Why this matters

This lets Genius LLM provide the benefits of inspectable reasoning without depending on exposing unrestricted internal token-level chain-of-thought.

It also creates a reusable debugging and training artifact for improving routing, verification, grounding, and consensus.

## 16.7 Memory and context construction

### 16.7.1 Bridge Blocks

Bridge Blocks are structured memory chunks that summarize short windows of prior interaction, task state, or workflow history. They should be small enough to retrieve efficiently and rich enough to preserve multi-step context.

Suggested contents:

- topic or task label
- turn span
- summary
- entities and files involved
- timestamps
- confidence and freshness metadata

### 16.7.2 Fact store

The fact store contains typed memory entries such as:

- user preferences
- project conventions
- tool configuration
- active branch, environment, or file references
- confirmed constraints and invariants

### 16.7.3 Profile layer

A profile layer stores stable user or project preferences such as tone, preferred language, formatting preferences, and workflow constraints.

### 16.7.4 Retrieval flow

1. Lightweight prefilter based on tags, recency, task type, and entities.
2. Memory governor selects the most relevant Bridge Blocks, facts, and policies.
3. Temporal, provenance, and policy conflicts are resolved.
4. A compact context packet is generated for experts.

## 16.8 Specialist taxonomy

The current architecture distinguishes between the Semantic Core, role specialists, and domain specialists.

### 16.8.1 Role specialists

#### 16.8.1.1 Planner and Memory Governor Specialist

Responsibilities:

- classify requests
- estimate complexity
- decide whether retrieval is needed
- select Bridge Blocks, facts, and policies
- decide whether to use core only, an expert path, or swarm mode

#### 16.8.1.2 Primary Draft Specialist

Responsibilities:

- generate the first coherent draft quickly
- optimize for latency and acceptable quality
- stream output to the user and to subscribing specialists

This may be the Semantic Core in some requests, but should be treated as a role with explicit performance targets.

#### 16.8.1.3 Verifier Specialist

Responsibilities:

- check candidate answers for logical or arithmetic consistency
- compare draft outputs against retrieved facts, grounded sources, and tool results
- flag contradictions, omissions, and invalid assumptions

#### 16.8.1.4 Synthesizer or Arbiter Specialist

Responsibilities:

- compare multiple candidate outputs and critiques
- merge, select, or revise them into one coherent answer
- preserve the strongest parts of each contributor
- generate a trace of what changed and why

#### 16.8.1.5 Refiner and Formatter Specialist

Responsibilities:

- improve clarity, concision, and structure
- enforce output schemas or response templates
- apply user or project style preferences
- separate language cleanup from logical verification

#### 16.8.1.6 Grounding Specialist

Responsibilities:

- retrieve or align evidence from approved public or private sources
- support factual validation
- help correction or regeneration when conflicts are found

### 16.8.2 Domain specialists

#### 16.8.2.1 Numeric Specialist

Focused on arithmetic, ratios, finance-style calculations, word problems, and numeric decomposition.

#### 16.8.2.2 Symbolic Math Specialist

Focused on algebraic manipulation, equations, symbolic forms, and mathematically structured derivations.

#### 16.8.2.3 Tool and Execution Specialist

Focused on:

- formatting tool calls
- waiting for tool responses
- parsing results
- integrating tool outputs safely into ongoing reasoning

#### 16.8.2.4 Code Specialist

Focused on source-level reasoning, patch generation, implementation details, and development workflows.

#### 16.8.2.5 Domain Grounding or Workflow Specialist

Focused on retrieval-backed answer shaping, evidence-aware response drafting, and tenant-specific workflow support.

## 16.9 Recommended evolution from current specialists

### 16.9.1 Current state

- Semantic Core
- initial role experts
- initial domain experts

### 16.9.2 Recommended near-term state

- Semantic Core
- Planner and Memory Governor
- Numeric Specialist
- Math Verifier
- Refiner and Formatter Specialist
- Grounding Specialist

### 16.9.3 Recommended medium-term state

- Semantic Core
- Planner and Memory Governor
- Primary Draft role
- Numeric Specialist
- Symbolic Math Specialist
- Verifier Specialist
- Synthesizer or Arbiter Specialist
- Refiner and Formatter Specialist
- Tool and Execution Specialist
- Grounding Specialist
- Code Specialist

## 16.10 Routing model

### 16.10.1 MVP routing

The current rule-based router can be extended without major architectural changes.

Suggested routing heuristics:

- low complexity and no special constraints: Semantic Core only
- high numeric density: Numeric Specialist
- numeric answer with moderate or high risk: Numeric Specialist followed by Math Verifier
- rewrite, cleanup, or style-sensitive output: Refiner and Formatter Specialist
- structured output request: Refiner and Formatter Specialist with formatting mode
- tool-using task: Tool and Execution Specialist plus Tool Intermediary path
- grounding-sensitive request: Grounding Specialist or grounding service
- ambiguous or multi-part task: Planner and Memory Governor first
- high complexity or uncertainty: swarm mode with synthesis

### 16.10.2 Future learned routing

A learned router can later use features such as:

- prompt embeddings
- complexity estimate
- prior specialist success by domain
- latency budget
- confidence of primary draft
- disagreement between nodes or specialists
- required grounding level
- private corpus match quality
- execution traces

## 16.11 Execution patterns

### 16.11.1 Core-only response

For simple requests, the Semantic Core can answer directly.

### 16.11.2 Sequential specialist chain

The system can run:

- Planner -> Primary Draft -> Verifier -> Refiner

This is useful on a single node or where network overhead must be minimized.

### 16.11.3 Distributed swarm execution

A fast primary expert generates a draft while secondary experts review, ground, or augment it in parallel. A synthesis stage combines outputs into one final answer.

### 16.11.4 Streaming draft with delayed refinement

The system may stream the primary draft to the user immediately while:

- secondary experts subscribe to the draft
- verifier and formatter specialists prepare improvements
- synthesizer produces a final revision or patch

This provides low latency while preserving swarm quality improvements.

## 16.12 Thinking trace schema

A thinking trace should be a structured artifact, not an opaque text blob.

Suggested fields:

- request ID
- user query
- routing decision
- selected Bridge Blocks
- selected facts and policies
- grounding sources
- chosen primary expert
- draft latency
- secondary expert outputs
- synthesis actions
- final answer ID
- reputation updates triggered

### 16.12.1 Example trace sections

- Routing
- Memory used
- Grounding used
- Draft generation
- Verification and critique
- Synthesis changes
- Final response lineage

## 16.13 Relation to consensus and reputation

The reputation and consensus layer should evolve from broad domain scores toward role-aware and specialist-aware scores.

### 16.13.1 Current score types

The current design tracks global and skill-oriented scores such as math, grounding, formatting, and verification.

### 16.13.2 Recommended future score types

- Planner score
- Numeric solve score
- Math verify score
- Tool execution support score
- Formatting score
- Grounding score
- Synthesis score

This allows the swarm to weight outputs not only by node quality but also by demonstrated competence in specific reasoning roles.

## 16.14 Interaction with FP4 Ultra, Turbo Quant, and Sparse-V

### 16.14.1 Semantic Core

The Semantic Core is the best target for aggressive compression, because it is always active and dominates memory footprint.

### 16.14.2 Small specialists

Role and domain specialists can often be smaller and more targeted. This makes them strong candidates for task-specific quantization strategies, including more aggressive compression where accuracy permits.

### 16.14.3 Verifier and router models

Verifier, planner, and formatting specialists may benefit from different compression tradeoffs than the primary draft model. They often prioritize consistency and control over raw generative breadth.

### 16.14.4 Sparse-V implications

Sparse-V style execution is especially attractive for verifier, planner, and gating models if activation patterns are predictable and routing decisions can be made cheaply.

### 16.14.5 Open quantization questions

The existing documentation does not yet define:

- which specialists should share a backbone versus remain separate models
- whether adapter composition should be preferred over multiple standalone specialists
- whether role specialists and domain specialists should use the same quantization policy
- how reputation should interact with quantization-induced quality drift

These should be documented in future revisions.

## 16.15 Adapter and distillation implications

The current architecture discussions suggest multiple possible implementation paths:

1. separate small specialist models
2. shared semantic backbone with multiple specialist adapters

Both are compatible with the swarm-thinking design, but the documentation does not yet lock in one choice.

### 16.15.1 Recommended documentation additions

The architecture set should later specify:

- which specialists are full models versus adapters
- how adapters are composed or switched
- whether synthesis, verifier, and planner roles use shared or independent backbones
- what teacher data is used for each specialist
- what evaluation sets measure each specialist role

### 16.15.2 Distillation targets by role

Potential distillation targets include:

- planner traces
- verifier judgments
- synthesis revisions
- tool call correction traces
- formatting and schema repair examples

This is different from monolithic reasoning distillation and should be described as role-specific distillation rather than only domain-specific fine-tuning.

## 16.16 Summary

The distributed swarm thinking context architecture turns Genius LLM from a simple modular model into a collaborative reasoning system.

It does this by making the following explicit:

- memory-guided context assembly
- role-based specialist decomposition
- primary and secondary expert orchestration
- grounding-aware verification
- synthesis and arbitration
- visible reasoning traces
- future specialist-aware consensus

This architecture is the bridge between the current Genius LLM v1 execution model and a more advanced distributed SLM swarm capable of transparent, modular, grounded, and reputation-aware reasoning.

---
[Previous: AI Safety](./10-ai-safety.md) | [Architecture Index](./INDEX.md) | [Next: Secure Agent Architecture](./12-secure-agent-architecture.md)
