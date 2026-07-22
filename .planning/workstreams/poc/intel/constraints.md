# Constraints

> Extracted from SPEC-classified source documents (2 found). SPEC types carry higher precedence than DOC in default ordering (ADR > SPEC > PRD > DOC).

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

## SPEC-02: Secure Agent Architecture

- **Source:** `docs/architecture/secure-agent-architecture.md`
- **Title:** 17 Secure Agent Architecture for the GNUS.ai Decentralized Cognitive System
- **Confidence:** high
- **Type:** api-contract | protocol | nfr

### Layer Model (7+2 layers)

1. Client/API layer: session lifecycle, auth, request submission, policy attachment, user-visible approvals.
2. Orchestration layer: router, planner, memory governor, execution mode selection, policy evaluation, execution graph generation.
3. Expert execution layer: Semantic Core workers, role-based ELM workers, domain-specific ELM workers, verifier/arbiter/formatter/grounding/tool-support services.
4. Consensus and grounding layer: verification, critique, arbitration, grounding checks, reputation-weighted consensus.
5. Tool Intermediary layer: deterministic dry-run simulation, output sanitization, capability enforcement, attestation, side-effect gating.
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

**Security targets (hard):**
- 100% of tool executions must have a valid intermediary attestation.
- 0 direct side-effect executions from Semantic Core or ELM workers.
- 100% of durable memory writes derived from tools/external content must contain provenance metadata and policy-compatible trust classification.

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
