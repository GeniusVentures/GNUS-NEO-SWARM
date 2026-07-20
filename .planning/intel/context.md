# Context

> Running notes extracted from DOC-classified source documents. DOC is lowest precedence in the default ordering (ADR > SPEC > PRD > DOC). Entries are grouped by topic with source attribution.
>
> **2026-07-19 ingest update:** Re-ingested 14 changed documents. EGGROLL Swarm Retraining and SGFP4 Format moved to constraints.md (reclassified as SPEC). New DOC entries added for Agent/Module Development Inventory, GCS Capability System, Local Cognitive Second Brain Mode, and README navigation index.

---

## System Identity and Objectives

**Source:** `docs/architecture/executive-summary.md`

GeniusCognitiveSystem is a distributed, modular, reputation-weighted cognitive system built on GNUS.ai infrastructure, with Genius Expert Language Model (Genius ELM) as the semantic core inference engine.

The system is a Specialized Adaptable Intelligence Fabric (not AGI).

Primary goals: distributed inference and cognitive execution across GNUS nodes; efficient quantized Semantic Core deployment; modular expert execution through ELMs and specialist services; reputation-weighted output consensus; knowledge grounding via Grokipedia and private retrieval layers; measurable improvement vs naive single-model baseline; structured memory and inspectable swarm reasoning; secure agentic workflows through mandatory tool intermediation; private customization for enterprise and SMB deployments.

Secondary goals: energy-efficient inference; scalability across nodes; future compatibility with latent models; private customization through memory, retrieval, and expert adaptation; clear separation between general reasoning and focused expert cognition.

---

## System Architecture Overview

**Source:** `docs/architecture/system-overview.md`

### Layer Model (7 layers)

1. Client and API Layer -- session lifecycle, authentication, request submission, policy attachment, response delivery.
2. Orchestration Layer -- router, planner, memory governor, execution mode selector, policy evaluator, task decomposition logic.
3. Expert Execution Layer -- Semantic Core, role-based ELMs, domain-specific ELMs, local or distributed inference services.
4. Consensus and Grounding Layer -- reputation-weighted consensus, verification, critique, arbitration, Grokipedia integration, private knowledge grounding.
5. Security and Tool Intermediary Layer -- dry-run, sanitization, permission checks, approval gates, execution attestations.
6. Memory Layer -- GAML-based structured memory, bridge blocks, facts, policies, retrieval pipelines, CRDT-backed replication.
7. Distributed Infrastructure Layer -- messaging, discovery, storage propagation, scheduling, health monitoring, settlement integration.

### Compute Layer

- MNN: Model runtime for optimized deep learning inference.
- Vulkan/MoltenVK: GPU acceleration (MoltenVK for Apple platforms).
- SGFP4 codec: Weight compression via adaptive format with 64x64 macroblocks, fixed 2048-byte payloads, per-block affine decode, dual-mode (FP4_AFFINE / T158_AFFINE) selection.
- CUDA/Vulkan shaders: Tile-based decode and matmul.

### Distributed Layer

- libp2p: Task broadcast, distributed coordination, result aggregation.
- IPFS-lite: Model and artifact distribution.
- RocksDB: Local caching and structured memory support.
- CRDTs: Reputation synchronization and memory convergence.
- gRPC: API and service interface.

### Security Layer

- libsecp256k1: Node identity.
- ed25519: Message signing.
- OpenSSL: Secure transport (TLS/SSL).
- wallet-core: Reputation and secure state storage.
- Tool Intermediary boundary: Mandatory choke-point between expert reasoning and real-world side effects.

### Core Architectural Distinction

Two main cognitive classes: Semantic Core (broad reasoning, synthesis, default response) and Expert Language Models / ELMs (narrower specialized units for expertise, verification, structure, grounding, action).

---

## Model and Router Design

**Source:** `docs/architecture/model-and-router.md`

### Semantic Core

Central reasoning substrate for foundational responses. Optimized for high-throughput distributed inference. Selected from high-performing, medium-sized model families suitable for quantized distributed deployment.

Quantized using SGFP4 adaptive format: 64x64 macroblocks, fixed 2048-byte payloads, per-block affine decode (scale + bias in packed FP16 header), dual-mode per block (FP4_AFFINE: 4-bit signed codes; T158_AFFINE: ternary ~1.58-bit class). GPU-decoded in shared memory at inference time via Vulkan/MoltenVK with MNN runtime.

### Expert Language Models (ELMs)

Specialist execution layer promoting specialization over monolithic scaling. An ELM may be implemented as: compact standalone SLM, distilled expert model, adapter-augmented expert on shared backbone, constrained service exposing LM interface, secure expert reasoning module behind policy boundary.

**Role-Based ELMs:** Planner, Primary Draft, Verifier, Arbiter, Refiner/Formatter, Grounding, Tool-Support.

**Domain-Specific Experts:** Math, Code, Scientific, Legal/Compliance, Operations/Workflow, Customer Support, Finance.

**Private ELMs:** Organizations may deploy private ELMs trained on proprietary data within tenant boundaries.

**Invocation Patterns:** single-pass support, sequential chain, parallel swarm participation, arbiter-mediated synthesis.

### Router Design

Critical initial processing point for client requests. Responsibilities: classify task type/complexity, decide retrieval need, select execution mode, select Semantic Core and required ELMs, decide verification/arbitration need, determine private grounding need, decide tenant-scoped/private memory loading, enforce policy constraints, determine latency/privacy/token/spend budgets, produce execution graph.

**MVP Router:** Rule-based detection system:
- Numeric density -> Math Specialist/Verifier path
- Code syntax -> Code Specialist path
- Grounding-sensitive -> Grounding path
- Formatting-sensitive -> Refiner/Formatter path
- Low complexity -> Semantic Core only
- High complexity/uncertainty -> multi-stage path (planner, verifier, arbiter, swarm)

**Future Router Evolution:** Heuristic MVP -> Lightweight classifier router (compact learned routing model) -> Cognitive planner (task decomposition into multi-step workflows).

---

## Execution Modes and Performance Targets

**Source:** `docs/architecture/execution-and-performance.md`

### Four Execution Modes

1. **Single Node:** Semantic Core only. Fast. Minimal overhead.
2. **ELM-Assisted:** Semantic Core + one or more role/domain experts. Sequential or lightly parallel.
3. **Swarm Mode:** Multiple nodes. Weighted consensus or arbiter-mediated synthesis. Reputation-based selection.
4. **Agent Mode:** Multi-step execution involving memory, grounding, verification, optional tool use. Secure tool path enforced through Tool Intermediary.

### Execution Strategy Principles

- Local-first, distributed-second.
- Small effective cognitive sets (smallest set of ELMs/services rather than large swarm by default).
- Roles over raw scale (right expert role over scaling one model).

### Performance Targets

- Tokens/sec: >= INT4 baseline where comparable.
- Memory usage: <= practical low-bit deployment envelope.
- Grounded quality: >= baseline single-model factual reliability.
- Multi-node scaling: near-linear up to initial swarm targets where network conditions permit.
- Tool safety overhead: bounded and separately reported from inference latency.

---

## Grounding and Retrieval

**Source:** `docs/architecture/grounding.md`

### Grokipedia Role

Primary public grounding layer: structured knowledge retrieval, trusted grounding, hallucination reduction, post-generation validation, reputation scoring reward for grounded outputs.

### Retrieval Pipeline

Query analysis -> Search Grokipedia index and approved public sources -> Inject top-k structured facts/references -> Tag for traceability -> Pass to generation/verification/arbitration.

### Validation Layer

Post-generation: check factual claims against Grokipedia. On contradiction: lower grounding/consistency score, trigger verification/correction/regeneration with enforced grounding.

### Private Knowledge Grounding

Supports tenant-specific deployments using internal documents, SOPs, support playbooks, CRM exports, internal wikis, contracts, product catalogs, ticket histories, workflow artifacts, structured databases, knowledge graphs.

### Grounding Modes

Public grounding, private tenant grounding, hybrid grounding. May be invoked during draft generation, verification, or arbiter-mediated synthesis.

### Grounding as Expert Role

Deployed as dedicated Grounding ELM or grounding service invoked only when needed.

**Note on retrieval limitations:** Retrieval helps the system know WHAT information to use; it does not teach HOW to reason, format, triage, or act in tenant-specific workflows.

---

## Agentic Memory Layer (GAML v1)

**Source:** `docs/architecture/agentic-memory-layer.md`

### Purpose

Structured, reasoning-oriented long-term memory. Unlike traditional RAG (embedding similarity + vector DBs only), GAML treats retrieval as governed cognitive process with bridge blocks, facts, policies, events, trust metadata, and orchestration-aware selection.

### Memory Object Model

```
MemoryObject {
  id: UUID
  entity: string
  type: {bridge_block, fact, policy, event, tenant_operational}
  payload: structured JSON
  timestamp: int64
  source_node: NodeID
  confidence_score: float
  provenance_score: float
  trust_class: {higher_trust, lower_trust}
}
```

Stored via RocksDB (local), IPFS-lite (distributed replication), CRDT synchronization (conflict resolution).

### Ingestion Pipeline

1. Fact Extraction -- convert raw output into atomic structured facts.
2. Context Mapping -- associate with session, task, workflow, user context.
3. Temporal Tracking -- resolve updates, contradictions, stale state.
4. Write Evaluation -- score novelty, expected utility, provenance, contamination risk before durable storage.

### Agentic Retrieval Mechanism

Staged retrieval: metadata prefiltering -> semantic matching -> temporal resolution -> policy/tenant boundary checks -> memory governor selection of final context set. Results merged using reputation-weighted, policy-aware selection when multiple nodes return conflicting state.

### Swarm Memory Consensus

When multiple nodes return conflicting memory states: score by node reputation, confidence, recency, provenance/trust class; resolve via CRDT + policy-aware weighted selection; inject resolved memory into inference/grounding/verification context.

### Strategic Impact

Transforms GeniusCognitiveSystem v1 from Distributed Inference Engine into Distributed Cognitive System.

---

## Distributed Swarm Thinking Context

**Source:** `docs/architecture/distributed-swarm-thinking-context.md`

### Purpose

Extends the architecture with a swarm-native thinking context model explaining how routing, memory, experts, synthesis, verification, and user-visible reasoning traces work together. Five cooperating layers:

1. Context and memory layer
2. Routing and planning layer
3. Primary and secondary expert execution layer
4. Verification, grounding, and synthesis layer
5. User-visible thinking context layer

### Core Design Principles

- Structured collaborative reasoning over monolithic reasoning
- Memory-guided context instead of brute-force long context
- Inspectable swarm thinking (structured record of experts called, context used, outputs produced, how final answer formed)
- Reputation-aware specialization (role-specific and domain-specific reputation)
- Quantization-aware modularity (specialist boundaries chosen for efficient SGFP4 / Turbo Quant / Sparse-V application)

### Thinking Context Model

High-level event and artifact record including: routing decisions, memory blocks selected, facts and policies used, private knowledge sources, grounding sources, primary draft identity and latency, secondary expert critiques, synthesis decisions, final answer lineage.

### Specialist Taxonomy

**Role Specialists:** Planner and Memory Governor, Primary Draft, Verifier, Synthesizer/Arbiter, Refiner and Formatter, Grounding.

**Domain Specialists:** Numeric, Symbolic Math, Tool and Execution, Code, Domain Grounding/Workflow.

### Execution Patterns

- Core-only response (simple requests)
- Sequential specialist chain (Planner -> Primary Draft -> Verifier -> Refiner)
- Distributed swarm execution (parallel draft + review + synthesis)
- Streaming draft with delayed refinement

### Adapter and Distillation Open Questions (see INGEST-CONFLICTS.md WARNINGS)

The architecture does not yet lock in: which specialists are full models vs adapters, how adapters are composed/switched, whether synthesis/verifier/planner roles use shared or independent backbones, what teacher data is used for each specialist, what evaluation sets measure each specialist role.

### Quantization Open Questions (see INGEST-CONFLICTS.md WARNINGS)

Undefined: which specialists should share a backbone vs remain separate models, whether adapter composition should be preferred over multiple standalone specialists, whether role and domain specialists should use the same quantization policy, how reputation should interact with quantization-induced quality drift.

---

## Execution Roadmap and Risks

**Source:** `docs/architecture/roadmap-and-risks.md`

### Phase 1 -- Semantic Core Foundations

Base model selection, SGFP4 quantization pipeline, validate activation error, deploy across initial nodes.

### Phase 2 -- Experts + Router/Planner

Initial role-based expert integration, initial domain-specialist integration, routing and planning logic implementation, grounding path selection, memory governor introduction.

### Phase 3 -- Reputation, Memory, and Consensus

Implement reputation storage, weighted consensus and arbiter path, CRDT sync, structured memory retrieval and write governance, multi-node task execution.

### Phase 4 -- Grounding, Private Customization, Secure Agent Path, Benchmarks

Grokipedia retrieval integration, private grounding support, private memory and private ELM customization path, tool intermediary and attestation path, stress test, publish benchmark comparison.

### Risk Analysis

| Risk | Mitigation |
|------|-----------|
| SGFP4 underperforms | Fallback to INT4 or adjusted quantization policy |
| Reputation gaming | Require minimum history and verifier-aware scoring |
| Swarm latency high | Limit swarm width, prefer smallest effective cognitive set |
| Routing instability | Keep rule-based v1, phase in learned routing carefully |
| Memory contamination | Provenance-aware write gates and trust classes |
| Unsafe tool execution | Require intermediary attestation and approval gates |
| Customization path confusion | Keep retrieval, memory, and private ELM adaptation as separate governed levers |

---

## Future Compatibility and Strategic Positioning

**Source:** `docs/architecture/future-and-positioning.md`

### Future Compatibility

When latent world models or stronger reasoning substrates mature: replace or extend Semantic Core -> Latent World Model Core. Keep: ELMs and specialist roles, reputation system, grounding layer, structured memory layer, distributed swarm coordination, secure tool intermediation, hardware-efficient deployment, private customization layers.

### Strategic Positioning

GeniusCognitiveSystem v1 is: distributed, reputation-weighted, knowledge-grounded, memory-aware, hardware-efficient, modular, future-ready, agent-capable under secure execution constraints, customizable for enterprise/SMB.

Aligns with: Superhuman Adaptable Intelligence (SAI), specialization over monolithic scaling, distributed AI ecosystems, structured and inspectable cognition, layered private adaptation paths.

---

## AI Safety Philosophy

**Source:** `docs/architecture/ai-safety.md`

### Safety Model

No centralized safety gateway. Safety enforcement is: node-local, reputation-enforced, cryptographically declared, client-selectable, applied throughout routing, retrieval, memory, grounding, and tool execution.

### Four Safety Layers

1. **Node-Level Enforcement (Authoritative):** Each node runs local safety screening, applies policy thresholds, signs output with declared safety profile hash. Violations reduce reputation.
2. **Reputation-Based Enforcement:** `Δreputation_safety = -λ × violation_score`. Repeated violations lose swarm influence.
3. **Client-Side Preference Filtering:** Clients require specific safety profile hashes, reject incompatible nodes, run optional local filtering.
4. **Tool Intermediary Enforcement:** Dry-run, sanitize, capability check, approve, block unattested side effects.

### Safety Profile Declaration

Each node advertises: model_version, safety_profile_hash, region_profile, reputation_score. Profiles are versioned, cryptographically signed, distributed via IPFS, immutable once adopted.

### Safety in Swarm Mode

All nodes run local safety checks -> Orchestrator verifies safety flags -> Policy-violating outputs excluded or down-weighted -> Verification/grounding further constrain -> Reputation updates applied. Safety is emergent through local enforcement, weighted consensus, reputation decay, verification, and grounding.

---

## Targeted Retraining and Hierarchical Critical Thinking Specialists (2026-07-19 update)

**Source:** `docs/architecture/cognitive-retaining-system.md`

### Targeted Retraining

Continuous, fine-grained adaptation of user-specific and role-specific cognitive behavior through lightweight updates to adapters, routing weights, critic weights, verification behavior, memory, and arbitration behavior -- without full base-model replacement.

Key properties: local adaptation (user/tenant/node level), lightweight (adapters, routing weights, critic/verifier weight distributions, memory structures, arbitration logic), non-differentiable optimization (reinforcement-style feedback, Evolution Strategies/EGGROLL-compatible).

### EGGROLL-Based Optimization

Traditional gradient-based training insufficient for user preference alignment, reasoning path correction, bias weighting, long-horizon decision validation. EGGROLL enables low-rank perturbation updates, efficient on-device or swarm-assisted training, optimization without explicit loss functions.

Optimization targets: adapter parameters, routing decisions, critic/verifier weighting distributions, exploration vs alignment balance, arbitration strategies.

Reward signals: user acceptance/rejection, user edits (delta-based correction), argument/disagreement intensity, delayed outcome validation, surprise/novelty effectiveness.

### Hierarchical Critical Thinking Specialists (HCTS)

Layers: Generic Human Critic -> Country/Cultural Critic -> Regional/Social Context Critic -> Professional/Domain Critic -> Organizational/Team Critic -> Individual Cognitive Critic -> Contrarian/Adversarial Critic.

Each critic performs: assumption detection, evidence validation, bias identification, frame-dependent reasoning evaluation, risk analysis, alternative interpretation generation. Outputs are multi-perspective evaluations, not binary judgments.

### Bias-Aware Reasoning

Bias is explicitly modeled, tagged, and evaluated across multiple reasoning frames (Individual, Founder/Operator, Risk-Averse, Contrarian, First-Principles). System compares conclusions across contexts to detect instability and hidden assumptions.

### Cognitive Resistance Layer

Modes: Mirror (minimal resistance), Nudge (light alternative framing), Challenge (explicit tradeoffs/contradictions), Adversarial (strong opposing arguments). Adaptive friction triggers: high-confidence/low-evidence outputs, high-impact decisions, repeated user bias patterns, disagreement across critic layers, high novelty potential.

### Continuous Learning Loop

Each interaction generates a Cognitive Training Event:
```json
{
  "prompt": "...",
  "response": "...",
  "critics_used": [...],
  "user_feedback": "accepted | edited | rejected",
  "edit_delta": "...",
  "confidence": 0.0,
  "surprise_score": 0.0,
  "outcome": "unknown | validated | invalidated"
}
```

Drives Targeted Retraining via weight adjustments, adapter updates, critic influence tuning, routing refinement, arbitration refinement.

---

## Epistemic Arbitration and Cognitive OS Extensions (2026-07-19 update, reclassified DOC)

**Source:** `docs/architecture/epistemic-arbitration-and-cognitive-os.md`

> **Reclassification note:** Previously classified as SPEC; reclassified as DOC because technical details (JSON machine config, callback registry, plugin ABI, trace format) serve illustrative rather than contractual purposes.

### Cognitive OS Extension

The Epistemic Arbitration Layer sits between consensus and final synthesis, providing formal, configurable reasoning over how viable outputs should be judged, challenged, and synthesized. The Requestor Node (already the temporary orchestrator and consensus coordinator) is extended into the system's Epistemic Arbiter.

Runtime: GQHSM (data-driven hierarchical state machine) -- JSON-defined machines with generic callback registration, tiny shared-library framework plugins, future WASM-compatible.

### Supported Framework Families

- **Sanskrit epistemology (Nyaya/pramana-based):** Samshaya (doubt) -> Pramana (knowledge sources) -> Pancha Avayava (inferential construction) -> Tarka (challenge/debate) -> Hetvabhasa (fallacy detection) -> Nirnaya (final judgment).
- **Kripke modal reasoning:** World construction -> Accessibility checks -> Modal evaluation -> Contradiction pressure -> Fixed-point resolution -> World selection.
- **Hybrid:** Sequential or parallel combination of Sanskrit and Kripke branches.

### Generic Callbacks

initializeContext, classifyProblem, gatherKnowledgeSources, constructReasoningModel, critiqueAndValidate, performInference, resolveAndSynthesize, computeEpistemicWeights, emitTrace, finalizeOutput.

### Guard Callbacks

hasSufficientReputation, hasValidKnowledgeSources, hasNoCriticalContradictions, isHybridMergeReady, requiresHumanReview.

### Plugin ABI

`GQHSM_RegisterEpistemicPlugin(Registry&, EpistemicContext&)`, `GQHSM_GetPluginName()`, `GQHSM_GetPluginVersion()`, `GQHSM_GetSupportedFrameworks()`.

---

## Agent and Module Development Inventory (2026-07-19 new)

**Source:** `docs/architecture/agent-module-development-inventory.md`

### Purpose

Consolidates the agents, deterministic services, runtime modules, data stores, adapters, user interfaces, security boundaries, and distributed infrastructure required across the GeniusCognitiveSystem architecture. Translates architecture documents into an implementation inventory decomposable into workstreams, milestones, repositories, service interfaces, schemas, tests, deployment targets, and operational ownership.

### Component Classes

| Class | Description |
|-------|-------------|
| **Agent** | Model-assisted or adaptive component that interprets context, makes bounded judgments, proposes actions, or produces structured cognitive output |
| **Deterministic Service** | Component with reproducible decisions from explicit inputs, schemas, policies, and state |
| **Runtime Module** | Compute, inference, storage, networking, cryptographic, indexing, or execution module used by services/agents |
| **Connector Adapter** | Protocol/provider-specific adapter exposing external/local operations as canonical GCS capabilities |
| **Data Service** | Structured store, graph, index, artifact registry, queue, event log, or replicated state service |
| **Control Surface** | User, administrator, developer, reviewer, or operator interface |

### Covered Workstreams

Executive Controller, Semantic Core, ELMs, GAML Cognitive Memory, Objective Memory and VTG, Secure Tool Intermediary, Capability System and Connectors, Forecast-Driven Cognition (ACE/CES), Grounding and Verification, Arbitration and Synthesis, Execution Integrity System (EIS), EGGROLL Adaptive Learning, Reputation and Consensus, Distributed GNUS Infrastructure, OpenAI-Compatible API, Local Cognitive Second Brain, Deployment Profiles.

### Implementation Philosophy

A component may be implemented as a deterministic library, in-process service, model-assisted function, local daemon, private node service, distributed GNUS service, constrained WASM module, role-based ELM, domain-specific ELM, or user-facing application. Prefer the smallest implementation that satisfies required behavior, trust boundary, performance target, and deployment model.

---

## GCS Capability System (2026-07-19 new)

**Source:** `docs/architecture/capability-system.md`

### Purpose

Provides a protocol-neutral way for GeniusCognitiveSystem to discover, describe, govern, route, execute, and evaluate external and local capabilities.

Core architectural rule:

> GCS reasons about capabilities, not connector protocols. Connectors expose capabilities, and every capability is translated into a canonical internal contract before execution.

MCP is one supported connector protocol. It is not the internal authority model.

### Architectural Position

```
External/Local Systems (MCP, REST, GraphQL, gRPC, local APIs, OS services, DBs, WASM, GNUS network services)
    -> Connector Adapters
    -> Capability Discovery and Translation
    -> Canonical Capability Contract
    -> Router/Planner + Policy Evaluation
    -> Tool Intermediary
    -> Sandboxed and Attested Execution
    -> Sanitized Result -> Verification, GAML Write, Reputation Update
```

### Core Concepts

**Capability:** An operation available to GCS independent of transport protocol (e.g., `email.message.read`, `calendar.event.create`, `database.query.readonly`).

**Connector:** Implements communication with a provider or local system. One connector may expose many capabilities; one capability may have multiple connectors.

**Canonical Capability Contract:** Internal representation normalizing a capability before execution -- schema, constraints, required permissions, expected output shape.

**Connector Lifecycle:** Registration (declare capabilities, credentials, rate limits) -> Discovery (query available capabilities) -> Translation (external operation -> canonical contract) -> Execution (Tool Intermediary path) -> Result sanitization -> Reputation update.

### Credential Handling

Connectors declare credential requirements in their manifest. Credentials never exposed directly to expert/ELM reasoning. Tool Intermediary mediates credential access.

### Capability Routing

When multiple connectors expose the same capability, routing prefers: local connectors over remote, lower-latency over higher, higher-reputation over lower, policy-compatible over incompatible.

---

## Local Cognitive Second Brain Mode (2026-07-19 new)

**Source:** `docs/architecture/local-cognitive-second-brain.md`

### Purpose

Defines Local Cognitive Second Brain Mode for GCS -- private, user-owned memory and reasoning on a local device, workstation, SMB appliance, enterprise node, or private GNUS subnet.

Core architectural rule:

> The local second brain is a GCS agent mode backed by GAML, executed by local or private ELMs, coordinated by the orchestration layer, and improved over time through EGGROLL adaptation signals.

### Five GCS Components

- **Orchestration Layer:** Control plane -- decides local vs private vs public execution, memory scope, ELM/agent/tool selection.
- **GAML:** Structured memory substrate -- stores facts, claims, commitments, decisions, deadlines, tasks, preferences, project state, contradictions, reasoning traces.
- **Local or Private ELMs:** Reasoning engine executing within the privacy boundary.
- **Second Brain Agent:** Behavior layer providing proactive assistance, meeting preparation, commitment tracking, contradiction detection.
- **EGGROLL:** Adaptation loop improving second-brain behavior over time.

### Privacy Modes

- **Strictly Local:** All data stays on device; no external network access.
- **Private Subnet:** Data shared within a configured private GNUS subnet.
- **Enterprise:** Tenant-scoped with enterprise policy enforcement.

### Memory Lifecycle

Ingestion (structured extraction from conversations, documents, meetings) -> Storage (GAML objects with privacy scope) -> Retrieval (context-aware multi-hop reasoning) -> Writeback (version-aware updates with provenance) -> Contradiction Detection (flagging conflicting facts or commitments).

### Human-Readable Memory Mirror

Optional local file tree or dashboard exposing second-brain state in human-readable form for transparency and user oversight.

---

## Architecture Documentation Index

**Source:** `docs/architecture/README.md`

Navigation index and overview landing page for the Genius Cognitive System architecture documentation, covering product requirements, technical design, and system architecture blueprint across 30+ chapters.

---

## Sloth Integration Exploration

**Source:** `docs/architecture/exploratory/sloth-integration.md`

Explores integrating the Unsloth library into the GeniusLLM training pipeline for LoRA-based distillation and FP4/FP8 efficient training. Covers Teacher-Parent-Specialist pipeline, adapter merging, Sparse-V kernels, and surprise-gated memory integration.
