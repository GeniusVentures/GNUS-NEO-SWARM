# Constraints

> Extracted from SPEC-classified source documents (10 found). SPEC types carry higher precedence than DOC in default ordering (ADR > SPEC > PRD > DOC).

---

## SPEC-01: Reputation-Based Consensus System

- **Source:** `docs/architecture/reputation-consensus.md`
- **Title:** 7 Reputation-Based Consensus System
- **Confidence:** medium
- **Type:** api-contract | protocol

### Reputation Data Model

Each node maintains role-aware and domain-aware reputation signals: Identity_key, Global_score, Planner_score, Math_score, Grounding_score, Verification_score, Formatting_score, Latency_score, Consistency_score, Safety_score. Stored via wallet-core, RocksDB, CRDT replicated state.

### Reputation Update Formula

After each task, scores are updated by weighted components:
- **Accuracy/Quality:** `Δscore = α * (quality - baseline_quality)` when ground truth available; `Δscore = β * (agreement_with_weighted_consensus)` otherwise; `Δscore_validation = -μ * contradiction_severity` on contradiction.
- **Latency:** `Δscore_latency = -γ * (latency / median_latency)`.
- **Consistency:** `Δscore_consistency = δ * (consistency_signal)`.
- **Safety:** `Δscore_safety = λ * (safe_policy_compliance - violation_penalty)`.
- Final: `new_score = old_score + Δscore + Δscore_validation + Δscore_latency + Δscore_consistency + Δscore_safety`. Scores clipped to [0, 1].

### Weighted Consensus Algorithm

Weight per node/expert: `weight_i = f(r_i, c_i, v_i)` where r_i = reputation, c_i = confidence, v_i = verification quality. Two output selection modes:
- **Option A (Weighted Voting):** Select `O_k` where `Σ weight_i(O_i == O_k)` is max.
- **Option B (Best Weighted Synthesis):** Select, merge, or revise candidates using arbiter/synthesis stage informed by weights and divergence severity.

### Consensus Engine Architecture (Protocol Layer)

Operates at the application layer, independent of GNUS blockchain consensus. Task-level deterministic weighted coordination, not ledger agreement. Design principles:
1. Fully Peer-to-Peer (no permanent central coordinator)
2. Requestor Node as Orchestrator (temporary router/planner)
3. Reputation-Weighted Agreement
4. Liveness over Perfection (bounded completion over infinite retry)
5. Deterministic Finalization (reproducible output selection and attestation)
6. Arbitration over flat voting when needed

### Swarm Execution Flow

1. Client submits request to GNUS node (Requestor-Orchestrator).
2. Orchestrator selects candidate nodes by reputation, role/domain relevance, latency, policy compatibility; broadcasts task via libp2p.
3. Execution nodes run Semantic Core or expert inference, apply local safety policy, sign response, return output + metadata.
4. Optional verifier/grounding/arbiter participants check outputs.
5. Orchestrator applies weighted consensus or arbiter-mediated synthesis, validates safety compliance, produces final response.

### Consensus Message Types

- TASK_PROPOSAL: prompt, routing metadata, safety profile hash, request ID, requested role/domain.
- TASK_RESULT: output text/structured payload, confidence, latency, safety flag, node signature.
- VERIFICATION_RESULT: findings, grounding/policy notes, contradiction flags, signature.
- CONSENSUS_FINAL: selected/synthesized output, weight breakdown, reputation deltas, signed by requestor.

### Liveness Model

- Sufficient valid responses arrive: finalize.
- Insufficient quorum after timeout: degrade to single-node or reduced-mode.
- Heavy conflict: select highest-weight valid response or escalate to arbiter-mediated synthesis.
Timeout and quorum thresholds are tunable per execution mode.

### Byzantine Tolerance

Addressed failure modes: malicious output, low-quality output, latency manipulation, non-response, policy-incompatible output. Mitigations: reputation decay, consistency penalties, latency penalties, verifier/grounding checks, minimum history requirement before high influence.

### Reputation-Gated Participation

Nodes below reputation threshold, with safety violations above limit, high divergence rate, or failed attestation history may be excluded from routing pool, have reduced weight, or be temporarily quarantined.

### Genesis Anchor Model

Bootstrap nodes may start with reputation = 1.0 and full participation rights. Reputation decays proportionally as network grows; new nodes can achieve equivalent weight over time; no permanent privilege retained.

---

## SPEC-02: Secure Agent Architecture (2026-07-19 update)

- **Source:** `docs/architecture/secure-agent-architecture.md`
- **Title:** 18 Secure Agent Architecture for the GNUS.ai Decentralized Cognitive System
- **Confidence:** high
- **Type:** api-contract | protocol | nfr

> **Update note:** Chapter renumbered from 17 to 18. Document supersedes older Chat Genius subsystem framing. Agent execution is treated as one operating mode of the GNUS cognitive system, not a standalone Mixture-of-Agents subsystem.

### Goals and Success Criteria

**Primary goals:**
- Distributed agent execution: route each request to the smallest effective set of Semantic Core, ELMs, memory, grounding, verification, and tool intermediaries.
- High-quality synthesis: combine candidate drafts, critiques, verifications, grounding results via structured arbitration and reputation-weighted consensus.
- Persistent intelligence: store/retrieve long-term memory using structured memory classes, bridge blocks, facts, policies, events, provenance metadata, gated writeback.
- Grounded and policy-safe action: propose and coordinate tool use, forcing side-effects through a deterministic, auditable, capability-scoped Tool Intermediary.
- Trust and economics built-in: every job has attestations, policy envelopes, settlement hooks, privacy controls, zero-trust sandboxing.
- Security by default: no component may directly cause side effects without passing through the security choke-point.

**Operational targets:**
- Quality should improve over naive single-model execution through routing, verification, grounding, arbitration.
- Swarm overhead bounded and separately observable from model inference latency.
- Tool Intermediary overhead bounded and separately reported from reasoning latency.
- Factual reliability, task completion quality, auditability improved vs direct single-model execution.

**Security targets (hard):**
- 100% of tool executions must have a valid intermediary attestation.
- 0 direct side-effect executions from Semantic Core or ELM workers.
- 100% of durable memory writes derived from tools/external content must contain provenance metadata and policy-compatible trust classification.

### Layer Model (9 layers)

1. Client/API layer: session lifecycle, auth, request submission, policy attachment, user-visible approvals.
2. Orchestration layer: router, planner, memory governor, execution mode selection, policy evaluation, execution graph generation.
3. Expert execution layer: Semantic Core workers, role-based ELM workers, domain-specific ELM workers, verifier/arbiter/formatter/grounding/tool-support services.
4. Consensus and grounding layer: verification, critique, arbitration, grounding checks, reputation-weighted consensus.
5. Tool Intermediary layer: deterministic dry-run simulation, output sanitization and trap detection, capability enforcement, tool execution attestation, side-effect gating.
6. Memory layer: bridge blocks, facts, policies, events, retrieval governance, provenance scoring, CRDT replication, trust-class handling.
7. Distributed infrastructure layer: P2P transport, storage, scheduling, node discovery, health reporting.
8. Trust/economics layer: task attestations, accounting, payout triggers, settlement integration.
9. Privacy layer: privacy policy enforcement, secure collaboration modes.

### Normal Query Path (mandated)

Client/API -> Router/Planner -> Memory Governor + Grounding Selection -> Semantic Core / ELM Execution -> Tool Intermediary (if tools proposed) -> Verification / Arbitration / Consensus -> Memory Write Evaluation -> Settlement / Attestation -> Client/API

### Tool Intermediary (Security Choke-Point)

**Mandatory constraint:** No Semantic Core worker, ELM, verifier, arbiter, formatter, or tool-support component may directly cause side effects without passing through the Tool Intermediary.

Expert output `tool_calls[]` are proposals only. A proposal becomes executable only after:
1. Tool Intermediary dry-run passes
2. Capability policy check passes
3. Required human approval obtained (if applicable)
4. Signed attestation produced

### Tool Intermediary Service Contract

**Inputs:** original query + execution plan, proposed tool_calls[], capability manifest, tool adapter policy profile, current session/user/workspace policy.

**Outputs:** dry_run_result, attestation, sanitized_data, human_approval_required, rejection_reason.

**Dry-run result schema:** tool_call_id, dry_run_ok, simulated_effects (network_requests, filesystem_access, secrets_required), mock_output, risk_flags, human_approval_required.

**Attestation schema:** request_id, tool_call_id, dry_run_ok, safe_to_execute, safe_to_memorize, provenance_hash, capability_hash, policy_hash, sanitizer_version, intermediary_node_id, timestamp_ms, reason_code, intermediary_signature.

**Sanitized data schema:** tool_call_id, source_hash, content_type, plain_text, structured_fields, strip_report (removed_zero_width_chars, removed_active_content, instruction_scrub_applied).

### Trap Detection Categories (minimum)

- Prompt injection phrases
- "ignore previous instructions"-style overrides
- Hidden or zero-width text
- HTML script/event handlers
- PDF active objects or layered overlays
- Suspicious high-entropy payload markers in media metadata
- Encoded content markers requiring additional review

### Human Approval Gating (required when)

- Tool writes or mutates external state
- Tool accesses secrets or credentials
- Tool touches non-readonly files
- Tool result contains severe risk flags
- User/session/workspace policy requires step-by-step mode

### Memory Classes and Trust

**Higher-trust memory:** May influence routing, policy decisions, invariants, long-lived user preferences, stable facts with strong provenance. Requires: user-approved or verified origin, strong provenance chain, safe_to_memorize = true from Tool Intermediary when tool-derived, policy-compatible local attestation threshold.

**Lower-trust memory:** Raw web content, tool outputs, episodic external data, imported documents not yet validated. May be used only for grounding and reasoning after summarization and instruction-scrub passes. Must NOT directly define user invariants, routing rules, or system policy.

**Write gate formula:** `write_score = w1*novelty + w2*expected_utility + w3*consistency - w4*contamination_risk`. `trusted_score = p1*provenance_score + p2*consensus_score + p3*attestation_score`. Promotion: reject below write_threshold; write as higher-trust above trusted_threshold; write as lower-trust or reject otherwise.

### Node Trust Tiers

- Tier A: Settlement/reputation, Tool Intermediary, higher-trust memory nodes
- Tier B: Router/Planner, Verifier/Arbiter, Grounding nodes
- Tier C: Semantic Core and ELM workers
- Tier D: Opportunistic public compute nodes

### Zero-Trust Sandbox Rules (mandatory)

- Default-deny capability model
- Firecracker micro-VM on servers where feasible
- OS-level sandbox on iOS/Android
- Capability-based host interfaces only for sandboxed modules
- No ambient network, filesystem, credential, or device permissions
- Clock, randomness, and IPC mediated by host policy

### Execution Plan Schema

Mandated fields: request_id, query_hash, selected_core (core_id, version), selected_elms[] (elm_id, version, role, capabilities), execution_graph (mode, topology, stages), constraints (max_tokens, max_wall_ms, max_spend), privacy_mode, attestation_requirements, tool_policy, memory_mode, sandbox_profile (default_deny, platform), plan_signature.

### Expert Packaging and Runtime Rules (mandatory)

- Artifact is versioned and content-addressed.
- Signature verification occurs before artifact load on every node where signing is required.
- Manifest declares required capabilities.
- Runtime executes under capability-scoped host interfaces only.
- Direct host escape, unrestricted filesystem, unrestricted network, direct credential access are prohibited.

---

## SPEC-03: SGFP4 Adaptive Quantization Format (2026-07-19 new)

- **Source:** `docs/architecture/sgfp4-format.md`
- **Title:** 22 SGFP4 Adaptive Quantization Format
- **Confidence:** high
- **Type:** api-contract | protocol

> **Update note:** Renamed from "16 Ultra FP4 Format" to "22 SGFP4 Adaptive Quantization Format". Replaces the earlier FP4 v3 codec with an adaptive mixed-bit scheme.

### Design Goals

- Runs everywhere: Vulkan, MoltenVK, MNN-compatible decode kernels for low-end through high-end GPUs.
- Consistent answers: devices differ in throughput and caching, not model precision tiers.
- Fast decode: per-workgroup branching with vectorized bit-unpack; fixed per-block payloads.
- Simple paging: all macroblocks use the same 2048-byte payload, enabling uniform memory addressing.

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

**T158_AFFINE (MODE=1):** Ternary codes t in {-1, 0, +1} as 2-bit symbols (00=0, 01=+1, 10=-1, 11 reserved). 16 codes per uint32. Active data in uint32[0..255] (1024 bytes); uint32[256..511] zero-filled. Decode: w_hat = S * t + Bias. Ternary codebook with affine scale/bias in ~1.58-bit class.

### Adaptive Mode Selection (Encoding)

Encoder evaluates both modes per block, chooses better one. Selection rule: prefer ternary when err_t158 <= (1.0 + delta) * err_fp4 (typical delta 0.05-0.20). Error metric: default L2 norm; optional pyramid-weighted error for low-frequency structure preservation.

### GPU Decode Procedure

Per block: unpack S, Bias from header; decode flags4 and baseBytes from offset; load 512 uint32 from codes_blob; branch on mode; unpack nibbles/2-bit symbols; compute w = S * code + Bias; write decoded 64x64 block to padded tensor; crop to (O, I). Single GPU workgroup per macroblock.

---

## SPEC-04: EGGROLL Swarm Retraining Architecture (2026-07-19 reclassified)

- **Source:** `docs/architecture/eggroll-swarm-retraining.md`
- **Title:** EGGROLL Swarm Retraining Architecture
- **Confidence:** medium
- **Type:** protocol | api-contract

> **Reclassification note:** Previously classified as DOC; now SPEC based on concrete technical contracts (core training primitive with required fields, JSON fitness packet schema, seed derivation protocol, worker execution model steps).

### Architectural Position

Five major architectural roles: Semantic Core + Experts (inference), Router + Swarm Thinking Context (execution/reasoning), GAML (memory), Reputation + Consensus (trust/output selection), EGGROLL Swarm Retraining (specialist refresh/adaptation).

EGGROLL complements rather than replacing: adapter-style specialization remains valid; expert-based routed execution remains inference strategy; EGGROLL becomes distributed retraining and expert-refresh mechanism.

### Why EGGROLL Fits GNUS.ai

Traditional distributed backpropagation assumes tightly coupled GPUs, high-bandwidth gradient exchange, large optimizer state sync, low-latency datacenter networking -- does not match GNUS.ai. EGGROLL fits because workers: receive model version reference, reconstruct low-rank perturbation from deterministic seed, evaluate local fitness, return only compact fitness values and metadata. Converts retraining into inference-like workload with minimal per-step network payload.

### Design Principles

1. Locality First: Training within local beehives/sub-swarms that already hold relevant artifacts.
2. Deterministic Reconstruction over Tensor Shipment: Low-rank perturbations from deterministic seeds.
3. Compact Fitness over Gradient Exchange: Compact fitness signals, validation metadata, attestations.
4. Adapter-Oriented Evolution: Preferred first targets are expert adapters or specialist micro-models.
5. Reputation-Gated Promotion: Validation, safety checks, and reputation-aware acceptance before promotion.
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

### Fitness Packet Format

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

New dimensions: Trainer_score, Validation_score, Adapter_promotion_score, Domain_trainer_score (by specialist area). Redundancy: sampled assignment redundancy, challenge tasks, hidden validation shards, consistency checks, reputation penalties for deviation, minimum reputation thresholds for high-value jobs.

### Embedded Retraining Loop

Normal inference path: Route -> Execute -> Aggregate -> Ground/Safety/Memory evaluate -> Final response. Learning event creation when: exact correctness known, verifier disagreement identifies recoverable failure, grounding validation identifies contradiction, formatting/schema checks fail, user feedback strongly positive/negative, repeated workflow success creates strong pattern.

### Best Initial Retraining Targets

1. Numeric Specialist / Math Verifier (exact-match correctness, symbolic verification, arithmetic consistency)
2. Router / Planner Specialist (quality improvement vs baseline, latency-adjusted utility, specialist selection accuracy)
3. Formatter / Schema Specialist (JSON validity, schema compliance, formatting correctness, user preference match)
4. Grounding Specialist (factual agreement, contradiction reduction, citation alignment)
5. Code Specialist (test pass rate, compile success, static analysis success, minimal-diff acceptance)

### Rollout Plan

Phase 1: Single-Machine Proof. Phase 2: Local Beehive (10-50 peers). Phase 3: GNUS Processing Room Integration. Phase 4: Reputation and Redundancy. Phase 5: Hierarchical Swarm Aggregation.

---

## SPEC-05: Speculative Decoding and VTG Candidate Scheduling (2026-07-19 new)

- **Source:** `docs/architecture/speculative-decoding-and-vtg.md`
- **Title:** 24 Speculative Decoding and VTG Candidate Scheduling
- **Confidence:** high
- **Type:** protocol | api-contract

### Purpose

Defines the speculative decoding architecture for GeniusCognitiveSystem using micro-speculation. A node proposes a short local continuation, verifies it through the configured local path, commits only the accepted prefix, and publishes compact outcome metadata back into VTG and EGGROLL.

### Operating Envelope

GNUS speculative decoding profile optimized for constrained nodes:
- Active model/ELM budget: 100MB to 350MB
- Micro drafter or MTP head: 5MB to 50MB
- Hot VTG shard: 10MB to 100MB
- Remaining local budget for runtime buffers, KV cache, shader state

Architectural rule: The swarm provides scale. The individual node provides a small verified contribution.

### Core Components

| Component | Responsibility |
|----------|----------------|
| Micro Drafter | Proposes a tiny future prefix or one small state block |
| Confidence Scheduler | Selects the portion of the proposal to verify |
| Local Verifier | Accepts the prefix using local target model, schema validator, tool dry-run, test result, or ELM verifier |
| VTG Hot Shard | Supplies locally relevant verified transition candidates |
| Swarm Learning Loop | Publishes compact outcome events for VTG and EGGROLL |

### Drafter Backends

- **Frozen Micro-MTP head:** Compact prediction head on frozen backbone (chapter 25).
- **Micro-diffusion block drafter:** Drafts content in a compressed latent space.
- **VTG lookup drafter:** Uses VTG hot shard for high-success-rate transitions.
- **Tiny causal tree drafting:** Proposes and verifies small branching patterns.
- **Rule/schema/grammar drafter:** Deterministic constrained-generation helpers.

### Node Capability Advertisement

JSON schema including: node ID, supported drafter backends, local verification paths, budget profile (MTP head sizes, VTG shard sizes), device class.

### Swarm Outcome Events

JSON schema including: request ID, node ID, drafter type, proposal count, accepted prefix length, acceptance rate, cost savings estimate.

---

## SPEC-06: Frozen Micro-MTP and VTG Edge Inference (2026-07-19 new)

- **Source:** `docs/architecture/frozen-mtp-and-vtg.md`
- **Title:** 25 Frozen Micro-MTP and VTG Edge Inference
- **Confidence:** medium
- **Type:** protocol | api-contract

### Purpose

Defines the GNUS edge-inference form of Frozen Multi-Token Prediction: Frozen Micro-MTP. Attaches a small multi-token prediction head to an already deployed frozen Semantic Core or ELM backbone. The backbone remains unchanged.

### Core Design Principle

> If the local model already computed the context, the drafter should reuse that state.

A constrained node should use Frozen Micro-MTP when the memory overhead of the head is lower than the cost of repeated autoregressive steps or a separate drafter.

### Micro-MTP Budget

- MTP head size: 5MB to 50MB
- Speculative depth: 1 to 4 tokens
- Branch factor: 1
- Verification: mandatory
- Rollback tolerance: near zero

Key metric: verified accepted prefix length per megabyte and millisecond.

### Candidate Record

JSON schema recording: model CID, head CID, proposed tokens, accepted tokens, acceptance rate, latency savings.

### Capability Advertisement

Nodes advertise MTP head availability as part of node capability: model CID, head CID, head budget, measured acceptance rate, supported verification paths.

### Commitment Rule

Accepted prefix must be verified by local verifier path before commitment. No unverified tokens may enter the committed output.

---

## SPEC-07: Objective Memory and Verified Transition Graph (2026-07-19 new)

- **Source:** `docs/architecture/objective-memory-vtg.md`
- **Title:** 23 Objective Memory and Verified Transition Graph (VTG)
- **Confidence:** medium
- **Type:** api-contract | protocol

### Purpose

Defines the Objective Memory layer and Verified Transition Graph (VTG) -- a verified cognitive execution substrate that records reusable low-entropy transitions discovered during inference, verification, tool use, grounding, and swarm consensus.

### Architectural Position

| Layer | Primary Question | Stored Object |
|-------|------------------|---------------|
| GAML | What does the system know or remember? | Facts, policies, events, bridge blocks, preferences, operational state |
| Swarm Thinking Context | How did this request move through the swarm? | Routing decisions, selected context, expert outputs, synthesis lineage |
| Epistemic Arbitration | How should viable outputs be judged and synthesized? | Arbitration framework state, contradiction pressure, synthesis decisions |
| EGGROLL | How should components improve over time? | Fitness packets, perturbation results, promotion signals |
| Objective Memory / VTG | Which low-entropy transitions have repeatedly worked? | Verified transition edges and candidate frontiers |

Objective Memory sits between context construction and execution: Router/Planner -> GAML Retrieval -> VTG Candidate Frontier -> SC + ELM Execution -> Verification/Arbitration/Synthesis.

### Objective vs. Subjective Cognition

- **Objective cognition:** Low-entropy continuations where one or few paths are measurably correct, valid, executable, grounded, or schema-compliant.
- **Subjective cognition:** High-entropy continuations where multiple paths may be valid depending on preference, style, bias context, tenant policy, or user intent.

### Transition Edge Schema

JSON structure recording: source state hash (cognitive state fingerprint), target state hash, transition type (token, action, schema, tool-call, etc.), verification signatures, confidence, usage count.

### State Identity Hashing

Cognitive states fingerprinted by hashing: prompt context, GAML context, expert outputs, verification results. Enables lookup of previously verified transitions.

### Storage and Distribution

VRF-sliced VTG shards replicated via IPFS-lite, local hot shards cached on nodes, CRDT-based conflict resolution.

---

## SPEC-08: Forecast-Driven Cognition and Predictive Prefetching (2026-07-19 new)

- **Source:** `docs/architecture/forecast-driven-cognition.md`
- **Title:** 28 Forecast-Driven Cognition and Predictive Prefetching
- **Confidence:** medium
- **Type:** api-contract | protocol

### Purpose

Defines Forecast-Driven Cognition (FDC) for GCS -- a subsystem that predicts future cognitive requirements (intent, memory, experts, tools, nodes) and prepares resources in advance. Core architectural rule:

> GCS should not merely react to the present. It should estimate the most probable near-future cognitive state, prepare for that state, measure prediction error, and improve its anticipatory behavior over time.

### Core Components

- **Anticipatory Cognition Engine (ACE):** Converts current cognitive state into a multi-hypothesis forecast graph.
- **Cognitive Execution Scheduler (CES):** Interprets the forecast graph and issues preparation directives.
- **Personal Forecast Models (PFM):** Per-user/tenant forecast policies learned over time.
- **Forecast Graph:** Directed acyclic representation of predicted cognitive requirements.
- **Anticipatory Distillation:** Compresses forecast policies for low-latency prediction.
- **Confidence-Based Preparation Policy:** Prepares resources proportional to forecast confidence.

### Forecast Targets

GAML memory objects, context-packet fragments, ELMs and micro-experts, model weights and adapters, KV-cache regions, local accelerators, remote GNUS nodes, archive shards, network routes, tools and APIs, authentication state, response candidates, speech synthesis state, verification and arbitration paths.

### Cognitive Cycle

```
Observe -> Forecast -> Prepare -> Compare Forecast with Reality -> Measure Prediction Error -> Update Forecasting Policy
```

### Bidirectional Voice Communication

First high-value application: low-latency bidirectional voice. System predicts the user's likely intent while listening and pre-stages appropriate resources before the user finishes speaking.

---

## SPEC-09: Execution Integrity System (2026-07-19 new)

- **Source:** `docs/architecture/execution-integrity-system.md`
- **Title:** 29 Execution Integrity System (EIS)
- **Confidence:** high
- **Type:** protocol | api-contract

### Purpose

The Execution Integrity System (EIS) is the GCS subsystem responsible for verifying that distributed computation was executed faithfully according to a declared execution contract. EIS verifies **execution honesty**, not semantic answer quality.

It answers: "Did this node run the declared model, adapter, SGFP4 container, kernel manifest, determinism class, sampling seed, and execution profile?"

It does not answer: "Is the answer true, useful, safe, well-grounded, or well-written?"

### Threat Model

The lazy-node / model-substitution attack: an operator advertises a 4B specialist, serves output from a 1B model, and bills full price. EIS makes honesty the best economic strategy through unpredictable teacher-forced spot checks, checkpoint-band comparison, fraud verdicts, slashing, and reputation penalties.

### Determinism Classes

| Class | Name | Guarantee | Comparison | Redundancy |
|-------|------|-----------|-----------|------------|
| A | Reference-integer | Bit-exact | Output hash equality | k = 1-2 |
| B | Bounded-drift | Deterministic per device; bounded drift across devices | Checkpoint-band match | k = 2-3 |
| C | Non-deterministic | No cross-run guarantee | Checkpoint-band match, widened bands | k = 3-5 |

### Execution Contracts

At minimum includes: model hash, adapter version hash, SGFP4 container hash, kernel manifest ID, determinism class, sampling seed, checkpoint schedule, execution profile. A node accepting a job attests it executed under exactly this contract.

### Checkpoint-Band Matching

Compares a small set of checkpoint tensors (not per-op) in a reduced-precision comparison domain. Default target: FP12-width rounded/truncated representation. Honest hardware drift must be materially smaller than checkpoint-tensor distance between declared model and plausible substitutes.

### Registration Invariant

Registration fails if the band required to keep honest false-positive rates below target overlaps the substitution-detection margin. This turns "the band forgives hardware, not weights" into an enforced registration invariant.

### Teacher-Forced Spot-Check Protocol

VRF-based position sampling. O(prefill) cost profile -- verification cost must scale with prefill, not full generation. Sampling-consistency check to detect systematic cheating patterns.

### Kernel Registration

Every kernel must register a determinism class in its manifest. Unclassified kernels are not schedulable. Constraints on authors: no runtime condition-based reduction order changes, seeded sampling, exportable checkpoint tensors at negligible cost.

---

## SPEC-10: OpenAI-Compatible API Router and GCS Job Queue (2026-07-19 new)

- **Source:** `docs/architecture/openai-compatible-api-router-and-gcs-job-queue.md`
- **Title:** 26 OpenAI-Compatible API Router and GCS Job Queue Architecture
- **Confidence:** high
- **Type:** api-contract | protocol

### Purpose

Specifies an OpenAI-compatible API router that translates standard OpenAI API calls into signed GNUS.ai democratized queue jobs. Core design rule:

> The API router does not schedule inference directly. It translates OpenAI-compatible calls into signed GNUS.ai democratized queue jobs.

### API Surface

Developers switch by changing `base_url` and API key. Supported endpoints: `/v1/chat/completions`, `/v1/completions`, `/v1/models`, `/v1/embeddings`. Streaming via SSE (`stream: true`).

### GCS API Request Job Type

A higher-level queue job type distinct from raw processing chunk jobs. Encompasses: HTTP request/response lifecycle, streaming SSE, client disconnect handling, API key/tenant authorization, request-level policy/privacy envelope, OpenAI-compatible error format, usage accounting, node capability matching, model aliases, long-running orchestration, child task creation, partial result streaming, retry/requeue semantics.

### Architecture

```
OpenAI-compatible Client
    -> Cloudflare Edge
    -> GCS Gateway Node (API Router)
    -> Pub/Sub Channel
    -> GCS Worker Nodes (claim/lease, execute, stream back)
    -> Aggregator Node (optional, for swarm responses)
    -> Streaming Proxy (SSE back to client)
```

### Node Registration and Heartbeat

Workers advertise capabilities (model/ELM types, supported endpoints, device class, budget profile) via pub/sub. Periodic heartbeat with lease expiry.

### Job Claims, Locks, and Leases

Workers claim jobs from the democratized queue with lock semantics. Expired locks are released for reclamation. Workers that fail to complete in time are marked.

### CRDT Keyspace

Job state, worker registrations, leases, metering records managed through CRDT-backed keyspace in GlobalDB.

### Metering and Settlement

Usage accounting per API key/tenant. Hooks for billing, reward distribution, and reputation updates. Settlement integration with GNUS blockchain.

### Routing Policies

- **Public:** Jobs broadcast to the open GNUS network.
- **Private:** Jobs restricted to tenant-registered nodes.
- **Local-only:** Execution on the gateway node itself.
- **Gateway-local:** Execution on nodes in the same physical/logical cluster as the gateway.
- **Hybrid:** Fallback chain (local -> private -> public).
