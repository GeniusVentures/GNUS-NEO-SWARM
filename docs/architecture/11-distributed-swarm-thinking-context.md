# 11 Distributed Swarm Thinking Context Architecture

## Purpose

This document extends the Genius LLM v1 architecture with a swarm-native thinking context model that explains how routing, memory, specialists, synthesis, and user-visible reasoning traces work together. It is intended to complement the existing v1 documents rather than replace them.

The goal is to make Genius LLM more than a routed collection of specialists. Instead, the system should support structured collaborative reasoning across local and distributed workers, while keeping the reasoning process inspectable, modular, and efficient.

## Why this section exists

The current v1 documentation describes:

- a Semantic Core
- a Grammar Specialist
- a Math Specialist
- a rule-based router
- swarm execution with reputation-weighted consensus

That is a strong MVP foundation, but it does not yet fully describe the emerging architecture implied by the distributed swarm discussions:

- router plus memory governor behavior
- Bridge Block and fact-based context construction
- primary and secondary expert orchestration
- synthesis of multiple expert outputs into one coherent answer
- user-visible swarm thinking traces

This document formalizes those concepts so future routing, specialist, and quantization decisions have a shared reference.

## Architectural intent

Genius LLM should evolve from a simple routed model into a distributed swarm reasoning system with five cooperating layers:

1. **Context and memory layer**
2. **Routing and planning layer**
3. **Primary and secondary expert execution layer**
4. **Verification and synthesis layer**
5. **User-visible thinking context layer**

This allows the system to divide cognitive labor across small, specialized models instead of forcing one dense model to perform planning, solving, verification, formatting, and reconciliation all at once.

## Core design principles

### 1. Structured collaborative reasoning over monolithic reasoning

Instead of distilling one global reasoning style into one model, Genius LLM should let multiple specialists contribute distinct reasoning functions such as planning, solving, checking, and refinement.

### 2. Memory-guided context instead of brute-force long context

The system should retrieve and assemble compact, high-value context using Bridge Blocks, facts, and user preferences rather than pushing large raw histories into the prompt.

### 3. Inspectable swarm thinking

The system should preserve a structured record of which specialists were called, what context they used, what they produced, and how the final answer was formed.

### 4. Reputation-aware specialization

Consensus and routing should consider specialist-specific reputation rather than relying only on generic node quality.

### 5. Quantization-aware modularity

Specialist boundaries should be chosen so that FP4 Ultra, Turbo Quant, and Sparse-V can be applied efficiently to the core model, specialists, and execution stages without unnecessary coupling.

## System overview

### High-level flow

1. User sends a request.
2. Router and memory governor determine task type, complexity, and required context.
3. Relevant Bridge Blocks, facts, and user preferences are assembled.
4. A primary expert is selected for fast draft generation.
5. Optional secondary experts are selected for critique, verification, grounding, formatting, or domain augmentation.
6. A synthesis stage merges outputs into a single user-facing response.
7. A structured thinking trace is recorded and optionally exposed in the interface.
8. New facts and Bridge Blocks are written back to memory.

## Thinking context model

### Definition

A thinking context is the structured, inspectable representation of how the swarm arrived at an answer.

It is not raw hidden chain-of-thought. Instead, it is a high-level event and artifact record that may include:

- routing decisions
- memory blocks selected
- facts used
- primary draft identity and latency
- secondary expert critiques
- synthesis decisions
- final answer lineage

### Why this matters

This lets Genius LLM provide the benefits of inspectable reasoning without depending on exposing unrestricted internal token-level chain-of-thought.

It also creates a reusable debugging and training artifact for improving routing, verification, and consensus.

## Memory and context construction

### Bridge Blocks

Bridge Blocks are structured memory chunks that summarize short windows of prior interaction, task state, or workflow history. They should be small enough to retrieve efficiently and rich enough to preserve multi-step context.

Suggested contents:

- topic or task label
- turn span
- summary
- entities and files involved
- timestamps
- confidence and freshness metadata

### Fact store

The fact store contains typed memory entries such as:

- user preferences
- project conventions
- tool configuration
- active branch, environment, or file references
- confirmed constraints and invariants

### Profile layer

A profile layer stores stable user or project preferences such as tone, preferred language, formatting preferences, and workflow constraints.

### Retrieval flow

1. Lightweight prefilter based on tags, recency, task type, and entities.
2. Memory governor selects the most relevant Bridge Blocks and facts.
3. Temporal and policy conflicts are resolved.
4. A compact context packet is generated for experts.

## Specialist taxonomy

The current v1 documents describe the Semantic Core, Grammar Specialist, and Math Specialist. The swarm architecture suggests a more explicit distinction between role specialists and domain specialists.

### Role specialists

#### Planner and Memory Governor Specialist

Responsibilities:

- classify requests
- estimate complexity
- decide whether retrieval is needed
- select Bridge Blocks and facts
- decide whether to use core only, a specialist, or swarm mode

This can initially be a mode of the existing router and later become a distinct specialist or adapter.

#### Primary Draft Specialist

Responsibilities:

- generate the first coherent draft quickly
- optimize for latency and acceptable quality
- stream output to the user and to subscribing specialists

This may be the Semantic Core in some requests, but should be treated as a role with explicit performance targets.

#### Verifier Specialist

Responsibilities:

- check candidate answers for logical or arithmetic consistency
- compare draft outputs against retrieved facts and tool results
- flag contradictions, omissions, and invalid assumptions

#### Synthesizer or Arbiter Specialist

Responsibilities:

- compare multiple candidate outputs and critiques
- merge, select, or revise them into one coherent answer
- preserve the strongest parts of each contributor
- generate a trace of what changed and why

#### Refiner and Formatter Specialist

Responsibilities:

- improve clarity, concision, and structure
- enforce output schemas or response templates
- apply user or project style preferences
- separate language cleanup from logical verification

### Domain specialists

#### Numeric Specialist

Focused on arithmetic, ratios, finance-style calculations, word problems, and numeric decomposition.

#### Symbolic Math Specialist

Focused on algebraic manipulation, equations, symbolic forms, and mathematically structured derivations.

#### Tool and Execution Specialist

Focused on:

- formatting tool calls
- waiting for tool responses
- parsing results
- retry logic
- integrating tool outputs safely into ongoing reasoning

#### Code Specialist

Focused on source-level reasoning, patch generation, implementation details, and development workflows.

#### Grounding Specialist

Focused on retrieval-backed answer shaping, claim alignment, and evidence-aware response drafting.

## Recommended evolution from current v1 specialists

### Current v1 state

- Semantic Core
- Grammar Specialist
- Math Specialist

### Recommended near-term v1.5 state

- Semantic Core
- Planner and Memory Governor
- Numeric Specialist
- Math Verifier
- Refiner and Formatter Specialist

### Recommended medium-term state

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

## Routing model

### MVP routing

The current rule-based router can be extended without major architectural changes.

Suggested routing heuristics:

- low complexity and no special constraints: Semantic Core only
- high numeric density: Numeric Specialist
- numeric answer with moderate or high risk: Numeric Specialist followed by Math Verifier
- rewrite, cleanup, or style-sensitive output: Refiner and Formatter Specialist
- structured output request: Refiner and Formatter Specialist with formatting mode
- tool-using task: Tool and Execution Specialist
- ambiguous or multi-part task: Planner and Memory Governor first
- high complexity or uncertainty: swarm mode with synthesis

### Future learned routing

A learned router can later use features such as:

- prompt embeddings
- complexity estimate
- prior specialist success by domain
- latency budget
- confidence of primary draft
- disagreement between nodes or specialists
- required grounding level

## Execution patterns

### 1. Core-only response

For simple requests, the Semantic Core can answer directly.

### 2. Sequential specialist chain

The system can run:

- Planner -> Primary Draft -> Verifier -> Refiner

This is useful on a single node or where network overhead must be minimized.

### 3. Distributed swarm execution

A fast primary expert generates a draft while secondary experts review or augment it in parallel. A synthesis stage combines outputs into one final answer.

### 4. Streaming draft with delayed refinement

The system may stream the primary draft to the user immediately while:

- secondary experts subscribe to the draft
- verifier and formatter specialists prepare improvements
- synthesizer produces a final revision or patch

This provides low latency while preserving swarm quality improvements.

## Thinking trace schema

A thinking trace should be a structured artifact, not an opaque text blob.

Suggested fields:

- request ID
- user query
- routing decision
- selected Bridge Blocks
- selected facts
- chosen primary expert
- draft latency
- secondary expert outputs
- synthesis actions
- final answer ID
- reputation updates triggered

### Example trace sections

- Routing
- Memory used
- Draft generation
- Verification and critique
- Synthesis changes
- Final response lineage

## Relation to consensus and reputation

The reputation and consensus layer should evolve from broad domain scores toward role-aware and specialist-aware scores.

### Current score types

The current design tracks global and skill-oriented scores such as math and grammar.

### Recommended future score types

- Planner score
- Numeric solve score
- Math verify score
- Tool execution score
- Formatting score
- Grounding score
- Synthesis score

This allows the swarm to weight outputs not only by node quality but also by demonstrated competence in specific reasoning roles.

## Interaction with FP4 Ultra, Turbo Quant, and Sparse-V

### Semantic Core

The Semantic Core is the best target for aggressive compression, because it is always active and dominates memory footprint.

### Small specialists

Role and domain specialists can often be smaller and more targeted. This makes them strong candidates for task-specific quantization strategies, including more aggressive compression where accuracy permits.

### Verifier and router models

Verifier, planner, and formatting specialists may benefit from different compression tradeoffs than the primary draft model. They often prioritize consistency and control over raw generative breadth.

### Sparse-V implications

Sparse-V style execution is especially attractive for verifier, planner, and gating models if activation patterns are predictable and routing decisions can be made cheaply.

### Open quantization questions

The existing documentation does not yet define:

- which specialists should share a backbone versus remain separate micro-models
- whether LoRA composition should be preferred over multiple standalone specialists
- whether role specialists and domain specialists should use the same quantization policy
- how reputation should interact with quantization-induced quality drift

These should be documented in future revisions.

## LoRA and distillation implications

The current architecture discussions suggest two possible implementation paths:

1. separate small specialist models
2. shared semantic backbone with multiple specialist LoRA adapters

Both are compatible with the swarm-thinking design, but the documentation does not yet lock in one choice.

### Recommended documentation additions

The architecture set should later specify:

- which specialists are full models versus adapters
- how adapters are composed or switched
- whether synthesis, verifier, and planner roles use shared or independent backbones
- what teacher data is used for each specialist
- what evaluation sets measure each specialist role

### Distillation targets by role

Potential distillation targets include:

- planner traces
- verifier judgments
- synthesis revisions
- tool call correction traces
- formatting and schema repair examples

This is different from monolithic reasoning distillation and should be described as role-specific distillation rather than only domain-specific fine-tuning.

## Missing information to be added across the document set

The existing 01 to 10 documents describe the v1 system well, but the following items still need explicit treatment.

### In system overview documents

Add:

- swarm-thinking lifecycle
- primary versus secondary expert roles
- synthesis stage responsibilities
- inspectable thinking trace model

### In model and router documents

Add:

- planner and memory governor role
- distinction between routing for latency and routing for quality
- specialist selection for verification and synthesis

### In grounding documents

Add:

- when grounding is invoked before versus after drafting
- how grounding interacts with verifier and synthesizer roles

### In reputation and consensus documents

Add:

- specialist-role scores beyond math and grammar
- how synthesis and verification outputs update reputation
- disagreement handling between solver and verifier specialists

### In execution documents

Add:

- streaming draft plus delayed refinement mode
- cross-node pub-sub draft propagation
- single-node chained specialist execution versus distributed execution

### In memory documents

Add:

- Bridge Block schema
- fact schema
- trace schema
- memory writeback rules after synthesis

### In future-positioning documents

Add:

- how swarm thinking differentiates Genius from monolithic reasoning models
- why inspectable collaborative reasoning matters strategically

## Proposed updates to INDEX.md

Add this document to the table of contents after the existing ten sections.

Suggested entry:

- [11 Distributed Swarm Thinking Context Architecture](11-distributed-swarm-thinking-context.md)

## Summary

The distributed swarm thinking context architecture turns Genius LLM from a simple modular model into a collaborative reasoning system.

It does this by making the following explicit:

- memory-guided context assembly
- role-based specialist decomposition
- primary and secondary expert orchestration
- synthesis and arbitration
- visible reasoning traces
- future specialist-aware consensus

This architecture is the bridge between the current Genius LLM v1 MVP and a more advanced distributed SLM swarm capable of transparent, modular, and reputation-aware reasoning.
