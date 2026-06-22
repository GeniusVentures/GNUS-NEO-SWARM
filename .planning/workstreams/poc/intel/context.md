# Context

> Running notes extracted from DOC-classified source documents (14 found). DOC is lowest precedence in the default ordering (ADR > SPEC > PRD > DOC). Entries are grouped by topic with source attribution.

---

## System Identity and Objectives

**Source:** `docs/architecture/01-executive-summary.md`

GeniusCognitiveSystem is a distributed, modular, reputation-weighted cognitive system built on GNUS.ai infrastructure, with Genius Expert Language Model (Genius ELM) as the semantic core inference engine.

The system is a Specialized Adaptable Intelligence Fabric (not AGI).

Primary goals: distributed inference and cognitive execution across GNUS nodes; efficient quantized Semantic Core deployment; modular expert execution through ELMs and specialist services; reputation-weighted output consensus; knowledge grounding via Grokipedia and private retrieval layers; measurable improvement vs naive single-model baseline; structured memory and inspectable swarm reasoning; secure agentic workflows through mandatory tool intermediation; private customization for enterprise and SMB deployments.

Secondary goals: energy-efficient inference; scalability across nodes; future compatibility with latent models; private customization through memory, retrieval, and expert adaptation; clear separation between general reasoning and focused expert cognition.

---

## System Architecture Overview

**Source:** `docs/architecture/02-system-overview.md`

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

**Source:** `docs/architecture/15-epistemic-arbitration-and-cognitive-os.md`

### Cognitive OS Extension (7th layer)

The Epistemic Arbitration Layer sits between consensus and final synthesis, providing formal, configurable reasoning over how viable outputs should be judged, challenged, and synthesized. The Requestor Node (already the temporary orchestrator and consensus coordinator) is extended into the system's Epistemic Arbiter.

Runtime: GQHSM (data-driven hierarchical state machine) -- JSON-defined machines with generic callback registration, tiny shared-library framework plugins, future WASM-compatible.

Supported framework families:
- Sanskrit epistemology (Nyaya/pramana-based): Samshaya (doubt) -> Pramana (knowledge sources) -> Pancha Avayava (inferential construction) -> Tarka (challenge/debate) -> Hetvabhasa (fallacy detection) -> Nirnaya (final judgment).
- Kripke modal reasoning: World construction -> Accessibility checks -> Modal evaluation -> Contradiction pressure -> Fixed-point resolution -> World selection.
- Hybrid: Sequential or parallel combination of Sanskrit and Kripke branches.

Generic callbacks: initializeContext, classifyProblem, gatherKnowledgeSources, constructReasoningModel, critiqueAndValidate, performInference, resolveAndSynthesize, computeEpistemicWeights, emitTrace, finalizeOutput.

Guard callbacks: hasSufficientReputation, hasValidKnowledgeSources, hasNoCriticalContradictions, isHybridMergeReady, requiresHumanReview.

Plugin ABI: `GQHSM_RegisterEpistemicPlugin(Registry&, EpistemicContext&)`, `GQHSM_GetPluginName()`, `GQHSM_GetPluginVersion()`, `GQHSM_GetSupportedFrameworks()`.

---

## Model and Router Design

**Source:** `docs/architecture/03-model-and-router.md`

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

**Future Router Evolution:** Heuristic MVP -> Lightweight classifier router (compact learned routing model) -> Cognitive planner (task decomposition into multi-step workflows). Future routing should incorporate latency budget, policy constraints, privacy mode, prior expert success, disagreement risk, tenant boundary requirements.

---

## Execution Modes and Performance Targets

**Source:** `docs/architecture/07-execution-and-performance.md`

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
- Verification/formatting quality: measurable improvement.
- Multi-node scaling: near-linear up to initial swarm targets where network conditions permit.
- Tool safety overhead: bounded and separately reported from inference latency.
- Customization efficiency: choose lowest-cost path among retrieval, memory, private ELM invocation, and swarm consensus that satisfies quality and policy.

---

## Grounding and Retrieval

**Source:** `docs/architecture/05-grounding.md`

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

**Note on retrieval limitations:** Retrieval helps the system know WHAT information to use; it does not teach HOW to reason, format, triage, or act in tenant-specific workflows. Retrieval, structured memory, and private ELM adaptation are complementary.

---

## Agentic Memory Layer (GAML v1)

**Source:** `docs/architecture/06-agentic-memory-layer.md`

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

**Source:** `docs/architecture/11-distributed-swarm-thinking-context.md`

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
- Quantization-aware modularity (specialist boundaries chosen for efficient FP4 Ultra / Turbo Quant / Sparse-V application)

### Thinking Context Model

High-level event and artifact record including: routing decisions, memory blocks selected, facts and policies used, private knowledge sources, grounding sources, primary draft identity and latency, secondary expert critiques, synthesis decisions, final answer lineage.

### Specialist Taxonomy

**Role Specialists:** Planner and Memory Governor, Primary Draft, Verifier, Synthesizer/Arbiter, Refiner and Formatter, Grounding.

**Domain Specialists:** Numeric, Symbolic Math, Tool and Execution, Code, Domain Grounding/Workflow.

### Recommended Evolution

- Near-term: Semantic Core + Planner/Memory Governor + Numeric Specialist + Math Verifier + Refiner/Formatter + Grounding Specialist.
- Medium-term: Add Primary Draft role, Symbolic Math, Verifier, Synthesizer/Arbiter, Tool/Execution, Code Specialist.

### Execution Patterns

- Core-only response (simple requests)
- Sequential specialist chain (Planner -> Primary Draft -> Verifier -> Refiner)
- Distributed swarm execution (parallel draft + review + synthesis)
- Streaming draft with delayed refinement

### Thinking Trace Schema

Suggested fields: request ID, user query, routing decision, selected Bridge Blocks, selected facts/policies, grounding sources, chosen primary expert, draft latency, secondary expert outputs, synthesis actions, final answer ID, reputation updates triggered.

### Adapter and Distillation Open Questions (see WARNINGS)

The architecture does not yet lock in: which specialists are full models vs adapters, how adapters are composed/switched, whether synthesis/verifier/planner roles use shared or independent backbones, what teacher data is used for each specialist, what evaluation sets measure each specialist role.

**Recommended documentation additions:** specify adapter-vs-model decisions, adapter composition/switching, backbone sharing, teacher data, role-specific evaluation sets.

### Quantization Open Questions (see WARNINGS)

Undefined: which specialists should share a backbone vs remain separate models, whether adapter composition should be preferred over multiple standalone specialists, whether role and domain specialists should use the same quantization policy, how reputation should interact with quantization-induced quality drift.

---

## Execution Roadmap and Risks

**Source:** `docs/architecture/08-roadmap-and-risks.md`

### Phase 1 -- Semantic Core Foundations

Base model selection, FP4 v3 quantization pipeline, validate activation error, deploy across initial nodes. Deliverable: `genius-core-alpha`.

### Phase 2 -- Experts + Router/Planner

Initial role-based expert integration, initial domain-specialist integration, routing and planning logic implementation, grounding path selection, memory governor introduction. Deliverable: `genius-modular-alpha`.

### Phase 3 -- Reputation, Memory, and Consensus

Implement reputation storage, weighted consensus and arbiter path, CRDT sync, structured memory retrieval and write governance, multi-node task execution. Deliverable: `genius-swarm-beta`.

### Phase 4 -- Grounding, Private Customization, Secure Agent Path, Benchmarks

Grokipedia retrieval integration, private grounding support, private memory and private ELM customization path, tool intermediary and attestation path, stress test, publish benchmark comparison. Deliverable: `GeniusCognitiveSystem v1 Beta`.

### Risk Analysis

| Risk | Mitigation |
|------|-----------|
| FP4 underperforms | Fallback to INT4 or adjusted quantization policy |
| Reputation gaming | Require minimum history and verifier-aware scoring |
| Swarm latency high | Limit swarm width, prefer smallest effective cognitive set |
| Routing instability | Keep rule-based v1, phase in learned routing carefully |
| Memory contamination | Provenance-aware write gates and trust classes |
| Unsafe tool execution | Require intermediary attestation and approval gates |
| Customization path confusion | Keep retrieval, memory, and private ELM adaptation as separate governed levers |

---

## Future Compatibility and Strategic Positioning

**Source:** `docs/architecture/09-future-and-positioning.md`

### Future Compatibility

When latent world models or stronger reasoning substrates mature: replace or extend Semantic Core -> Latent World Model Core. Keep: ELMs and specialist roles, reputation system, grounding layer, structured memory layer, distributed swarm coordination, secure tool intermediation, hardware-efficient deployment, private customization layers.

### Strategic Positioning

GeniusCognitiveSystem v1 is: distributed, reputation-weighted, knowledge-grounded, memory-aware, hardware-efficient, modular, future-ready, agent-capable under secure execution constraints, customizable for enterprise/SMB.

Aligns with: Superhuman Adaptable Intelligence (SAI), specialization over monolithic scaling, distributed AI ecosystems, structured and inspectable cognition, layered private adaptation paths.

---

## AI Safety Philosophy

**Source:** `docs/architecture/10-ai-safety.md`

### Safety Model

No centralized safety gateway. Safety enforcement is: node-local, reputation-enforced, cryptographically declared, client-selectable, applied throughout routing, retrieval, memory, grounding, and tool execution.

### Four Safety Layers

1. **Node-Level Enforcement (Authoritative):** Each node runs local safety screening, applies policy thresholds, signs output with declared safety profile hash. Violations reduce reputation.
2. **Reputation-Based Enforcement:** `Δreputation_safety = -λ × violation_score`. Repeated violations lose swarm influence.
3. **Client-Side Preference Filtering:** Clients require specific safety profile hashes, reject incompatible nodes, run optional local filtering.
4. **Tool Intermediary Enforcement:** Dry-run, sanitize, capability check, approve, block unattested side effects.

### Safety Profile Declaration

Each node advertises: model_version, safety_profile_hash, region_profile, reputation_score. Profiles are versioned, cryptographically signed, distributed via IPFS, immutable once adopted. No GeoIP enforcement -- region profile is node-declared, filtered by client preference.

### Safety in Swarm Mode

All nodes run local safety checks -> Orchestrator verifies safety flags -> Policy-violating outputs excluded or down-weighted -> Verification/grounding further constrain -> Reputation updates applied. Safety is emergent through local enforcement, weighted consensus, reputation decay, verification, and grounding.

---

## SGFP4 Adaptive Quantization Format

**Source:** `docs/architecture/16-sgfp4-format.md`

### Design Goals

Runs everywhere (Vulkan, MoltenVK, MNN-compatible); consistent answers across devices; fast decode (per-workgroup branching, vectorized bit-unpack, fixed per-block payloads); simple paging (all macroblocks use same 2048-byte payload).

### Macroblocks (Tiling)

Weight tensors of shape [O, I] partitioned into 64x64 macroblocks. Zero-padded to multiple of 64. Each block maps to row-major grid coordinates.

### Container Layout

Three parallel arrays + shape metadata:
- `headers[B]` (uint32): Packed half2 scale + bias per block (high 16 bits = scale_fp16, low 16 bits = bias_fp16).
- `offsets[B]` (uint32): Byte offset into codes blob, with low 4 bits as per-block mode flags.
- `codes_blob[]` (bytes): B * 2048 bytes, concatenated fixed-size per-block payloads, 16-byte aligned.

### Per-Block Mode Flags (low 4 bits of offsets)

- Bit 0 (0x1): MODE -- 0 = FP4_AFFINE, 1 = T158_AFFINE
- Bit 1 (0x2): ERROR_HINT -- 0 = L2-selected, 1 = Pyramid-selected
- Bits 2-3: reserved

### Quantization Modes

**FP4_AFFINE (MODE=0):** 4-bit signed codes q in [-8, 7], two's complement nibbles. 8 codes per uint32, 4096 codes total = 2048 bytes. Decode: w_hat = S * q + Bias.

**T158_AFFINE (MODE=1):** Ternary codes t in {-1, 0, +1} as 2-bit symbols (00=0, 01=+1, 10=-1, 11 reserved). 16 codes per uint32. Active data in uint32[0..255] (1024 bytes); uint32[256..511] zero-filled. Decode: w_hat = S * t + Bias. Ternary codebook with affine scale/bias stays in ~1.58-bit class.

### Adaptive Mode Selection (Encoding)

Encoder evaluates both modes per block, chooses better one. Selection rule: prefer ternary when err_t158 <= (1.0 + delta) * err_fp4 (typical delta 0.05-0.20). Error metric: default L2 norm; optional pyramid-weighted error preserves low-frequency structure.

### GPU Decode Procedure

Per block: unpack S, Bias from header; decode flags4 and baseBytes from offset; load 512 uint32 from codes_blob; branch on mode; unpack nibbles/2-bit symbols; compute w = S * code + Bias; write decoded 64x64 block to padded tensor; crop to (O, I). Single GPU workgroup per macroblock.

---

## EGGROLL Swarm Retraining Architecture

**Source:** `docs/architecture/13-eggroll-swarm-retraining.md`

### Purpose

Adds a swarm-native retraining layer to GeniusCognitiveSystem using deterministic perturbation reconstruction, compact fitness aggregation, and reputation-gated promotion mapped onto GNUS.ai processing-room infrastructure. Retraining is a first-class GNUS.ai operating system primitive.

### Architectural Position

Five major architectural roles: Semantic Core + Experts (inference), Router + Swarm Thinking Context (execution/reasoning), GAML (memory), Reputation + Consensus (trust/output selection), EGGROLL Swarm Retraining (specialist refresh/adaptation).

EGGROLL complements current design rather than replacing it: Adapter-style specialization remains valid; Expert-based routed execution remains inference strategy; EGGROLL becomes distributed retraining and expert-refresh mechanism.

### Why EGGROLL Fits GNUS.ai

Traditional distributed backpropagation assumes tightly coupled GPUs, high-bandwidth gradient exchange, large optimizer state sync, low-latency datacenter networking -- does not match GNUS.ai. EGGROLL fits because workers: receive model version reference, reconstruct low-rank perturbation from deterministic seed, evaluate local fitness, return only compact fitness values and metadata. Converts retraining into inference-like workload with minimal per-step network payload.

### Design Principles

1. Locality First: Training within local beehives/sub-swarms that already hold relevant artifacts.
2. Deterministic Reconstruction over Tensor Shipment: Low-rank perturbations from deterministic seeds.
3. Compact Fitness over Gradient Exchange: Compact fitness signals, validation metadata, attestations.
4. Adapter-Oriented Evolution: Preferred first targets are expert adapters or specialist micro-models.
5. Reputation-Gated Promotion: Validation, safety checks, and reputation-aware acceptance required before promotion.
6. Hierarchical Swarm Aggregation: Local room coordinators to higher-level aggregators.

### Core Training Primitive

`base model reference + target adapter reference + deterministic perturbation seed + task shard + reward function -> compact fitness packet`

Required job fields: target model version/base model CID, target adapter CID/expert artifact ID, perturbation rank, perturbation scale/sigma, perturbation seed/seed range, task shard reference, reward/objective definition, validation policy, safety policy hash, promotion policy.

### GNUS Processing Room Mapping

Processing room host -> local retraining coordinator. Worker peers -> perturbation evaluators. Data chunk/sub-block -> task shard or seed assignment. Processing result -> compact fitness packet. Room lifecycle -> one training generation.

### Beehives (Locality-Aware Sub-Swarms)

Share cached model artifacts, cached adapter artifacts, domain-specific task shards, geographic/network proximity, hardware similarity, policy/privacy boundary. May specialize around: model family, domain specialist, language/region, application domain, user-data enclave, hardware class.

### Deterministic Perturbation Reconstruction

`seed = H(model_version, adapter_version, layer_id, worker_id, generation_id, perturbation_id)`. Enables reproducible evaluation, auditability, replay for dispute resolution, compact job descriptions, lower storage overhead, selective fraud checking.

### Worker Execution Model

1. Resolve base model and adapter artifacts from local cache or IPFS-lite.
2. Reconstruct perturbation from assigned seed and rank.
3. Apply perturbation to target adapter/expert parameters.
4. Execute assigned task shard locally.
5. Compute fitness according to declared reward function.
6. Package fitness output, latency, and attestation metadata.
7. Return compact result packet to room coordinator.

### Fitness Packet Design

```json
{
  "training_job_id": "uuid",
  "worker_node": "node_id",
  "artifact_target": "math_verifier_adapter_v3",
  "seed_range": [100000, 100255],
  "fitness_values": "packed_or_scalar_payload",
  "latency_ms": 123,
  "validation_flags": {"self_check_passed": true, "policy_hash_match": true},
  "result_signature": "ed25519"
}
```

### Aggregation Model

Local coordinator aggregates worker fitness packets: verify signatures and policy compatibility, reconstruct perturbations from seeds, weight valid worker fitness, reject malformed/suspicious results, compute generation-level update candidates, run validation checks before publication. Hierarchical: worker -> room host -> beehive aggregator -> broader promotion/merge layer.

### Reputation Extensions for Retraining

New dimensions: Trainer_score, Validation_score, Adapter_promotion_score, Domain_trainer_score (by specialist area). Redundancy mechanisms: sampled assignment redundancy, challenge tasks, hidden validation shards, consistency checks, reputation penalties for deviation, minimum reputation thresholds for high-value jobs.

### Embedded Retraining Loop

Normal inference path: Route -> Execute -> Aggregate -> Ground/Safety/Memory evaluate -> Final response. Learning event creation when: exact correctness known, verifier disagreement identifies recoverable failure, grounding validation identifies contradiction, formatting/schema checks fail, user feedback strongly positive/negative, repeated workflow success creates strong pattern. Retraining targets: planner, router, numeric specialist, math verifier, formatter, grounding specialist, code specialist, synthesizer/arbiter.

### Best Initial Retraining Targets

1. Numeric Specialist / Math Verifier (exact-match correctness, symbolic verification success, arithmetic consistency)
2. Router / Planner Specialist (quality improvement vs baseline, latency-adjusted utility, specialist selection accuracy)
3. Formatter / Schema Specialist (JSON validity, schema compliance, formatting correctness, user preference match)
4. Grounding Specialist (factual agreement, contradiction reduction, citation alignment)
5. Code Specialist (test pass rate, compile success, static analysis success, minimal-diff acceptance)

### Rollout Plan

Phase 1: Single-Machine Proof (deterministic perturbation, specialist adapter target, compact fitness, validation loop). Phase 2: Local Beehive (10-50 peers, one room host, local task shards). Phase 3: GNUS Processing Room Integration (training-room lifecycle, IPFS-lite artifact addressing, gRPC/libp2p coordination, signed results). Phase 4: Reputation and Redundancy (duplicate assignments, challenge tasks, trainer scores, suspicious worker quarantine). Phase 5: Hierarchical Swarm Aggregation (beehive aggregators, cross-beehive promotion, canary rollout).

---

## Targeted Retraining and Hierarchical Critical Thinking Specialists

**Source:** `docs/architecture/14-cognitive-retaining-system.md`

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

### System Outcome

Personalized reasoning evolution, bias-aware critical thinking, non-echo-chamber cognition, continuous improvement without full retraining, efficient deployment on low-end GPU devices. Transforms static inference into dynamic, self-improving cognitive process.

---
