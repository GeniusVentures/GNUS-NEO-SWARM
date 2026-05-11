# 17 Secure Agent Architecture for the GNUS.ai Decentralized Cognitive System
## 17.1 Product Technical Design Specification

This document specifies the secure agent execution architecture within the GNUS.ai decentralized cognitive system. It supersedes the older Chat Genius subsystem framing in this file and aligns agent execution with the broader GNUS cognitive stack of routing, structured memory, grounding, reputation-weighted consensus, secure tool intermediation, decentralized safety, and swarm-native adaptation.

Rather than treating agents as a standalone Mixture-of-Agents subsystem, this document treats agent execution as one operating mode of the GNUS cognitive system. In that model, the Semantic Core, Expert Language Models (ELMs), memory services, grounding services, verification layers, and tool intermediaries cooperate under explicit policy and trust controls.

This version preserves the implementation-oriented depth of the prior PTDS while replacing outdated assumptions that all specialist cognition is best described as micro/nano SLMs coordinated primarily through an MoA aggregator. Where the older design referenced specialists, MoA topology, surprise-gated memory, and universal subspaces, those ideas are retained only when still compatible with the updated architecture and are otherwise replaced by the current concepts of role-based and domain-specific ELM execution, structured memory governance, inspectable reasoning, grounding-aware verification, and mandatory secure tool intermediation.

### 17.1.1 Goals and Success Criteria

#### 17.1.1.1 Primary goals

Distributed agent execution
Route each request to the smallest effective set of Semantic Core services, ELMs, memory services, grounding services, verification services, and tool intermediaries across the swarm while preserving latency, quality, privacy, and auditability.

High-quality synthesis
Combine multiple candidate drafts, critiques, verifications, and grounding results using structured arbitration and reputation-weighted consensus, with explicit handling of disagreement, evidence quality, and trust provenance.

Persistent intelligence
Store and retrieve long-term memory using structured memory classes, bridge blocks, facts, policies, events, provenance metadata, and gated writeback so future reasoning becomes more context-aware without relying on brute-force transcript replay.

Grounded and policy-safe action
Allow the system to propose and coordinate tool use while forcing all side-effecting operations through a deterministic, auditable, capability-scoped Tool Intermediary boundary.

Trust and economics built-in
Every job has attestations, policy envelopes, and settlement hooks, with privacy controls via policy-constrained execution and security boundaries via zero-trust sandboxing.

Security by default
No Semantic Core worker, ELM, verifier, arbiter, formatter, or tool-support component may directly cause side effects without passing through a deterministic, auditable, capability-scoped security choke-point.

#### 17.1.1.2 Operational targets

Quality retention
- Quality should improve over naive single-model execution through routing, verification, grounding, and arbitration rather than through uncontrolled fan-out.

Speed
- Swarm overhead for routing, dispatch, verification, and arbitration should remain bounded and separately observable from model inference latency.
- Tool Intermediary overhead target for dry-run, sanitization, and attestation should remain bounded and reported separately from reasoning latency.

Utility
- The architecture should improve factual reliability, task completion quality, and auditability relative to direct single-model execution.

Security targets
- 100 percent of tool executions must have a valid intermediary attestation.
- 0 direct side-effect executions from Semantic Core or ELM workers.
- 100 percent of durable memory writes derived from tools or external content must contain provenance metadata and policy-compatible trust classification.

#### 17.1.1.3 Non-goals for MVP

- Full formal verification of all execution modules.
- Universal support for arbitrary third-party tools.
- Perfect steganography detection across all media types.
- Global cross-swarm consensus for all memory writes. MVP scope may use local consensus thresholds for higher-trust memory promotion.

### 17.1.2 System Overview

#### 17.1.2.1 Layer model

The secure agent architecture is decomposed into layers to preserve separation of concerns and to allow independent scaling, auditing, and policy hardening.

- Client/API layer
  - chat session lifecycle
  - authentication and authorization
  - request submission
  - policy attachment
  - user-visible approvals and status updates

- Orchestration layer
  - router
  - planner
  - memory governor
  - execution mode selection
  - policy evaluation
  - execution graph generation

- Expert execution layer
  - Semantic Core workers
  - role-based ELM workers
  - domain-specific ELM workers
  - verifier and arbiter services
  - formatter and grounding services
  - tool-support execution helpers

- Consensus and grounding layer
  - verification
  - critique
  - arbitration
  - grounding checks
  - reputation-weighted consensus

- Tool Intermediary layer
  - deterministic dry-run simulation
  - output sanitization and trap detection
  - capability enforcement
  - tool execution attestation
  - side-effect gating

- Memory layer
  - bridge blocks
  - facts
  - policies and invariants
  - events and outcomes
  - retrieval governance
  - provenance scoring
  - CRDT replication
  - trust-class handling where required by policy

- Distributed infrastructure layer
  - P2P transport
  - storage
  - scheduling
  - node discovery
  - health reporting

- Trust/economics layer
  - task attestations
  - accounting
  - payout triggers
  - settlement integration

- Privacy layer
  - privacy policy enforcement
  - secure collaboration modes where required

##### 17.1.2.1.1 Layer interactions

The normal query path is:
Client/API -> Router/Planner -> Memory Governor + Grounding Selection -> Semantic Core / ELM Execution -> Tool Intermediary (if tools proposed) -> Verification / Arbitration / Consensus -> Memory Write Evaluation -> Settlement / Attestation -> Client/API

The normal learning path is:
Memory write candidate -> novelty / utility / provenance gate -> replication / convergence -> evaluation queue -> router / ELM / policy / memory-governor improvements

##### 17.1.2.1.2 Security hardening insertion rationale

The Tool Intermediary layer exists specifically because tool-using agents introduce a fundamentally different threat model than pure generation. A Semantic Core worker or ELM that can browse, open files, parse documents, call APIs, or emit shell-like commands can be manipulated by hostile external content. Therefore the architecture requires a mandatory intermediary choke-point between all proposal logic and all side effects. This design preserves useful agentic behavior while reducing the attack surface of prompt injection, memory poisoning, hidden instructions, and capability escalation.

#### 17.1.2.2 Node roles (typical deployment)

A GNUS node may host one or more roles. Local swarms use the same interfaces as wide-area deployments.

- Ingress/API node
  - session handling
  - auth and rate limiting
  - UI status events

- Router / Planner node
  - task classification
  - execution mode selection
  - policy and expert selection
  - memory-mode selection

- Semantic Core node
  - broad reasoning
  - synthesis fallback
  - default draft generation

- ELM worker node
  - role-specific or domain-specific expert inference
  - evidence packaging
  - tool proposal generation only

- Verifier / Arbiter node
  - critique
  - conflict handling
  - final answer packaging

- Memory / Index node
  - storage
  - retrieval
  - indexing
  - CRDT replication

- Grounding node
  - public or private knowledge retrieval
  - claim validation
  - grounding evidence packaging

- Settlement / Reputation node
  - task attestations
  - payout and reputation recording

- Tool Intermediary node
  - dry-run engine
  - sanitizer pipeline
  - capability enforcement
  - human approval pause logic
  - attestation generation

##### 17.1.2.2.1 Node colocation rules

- Small swarms MAY co-locate Router / Planner + Verifier / Arbiter + Tool Intermediary on one node.
- Expert worker nodes SHOULD remain isolated from the settlement role.
- High-trust deployments SHOULD isolate Tool Intermediary from expert execution to reduce local privilege escalation risk.
- Memory / index nodes that handle higher-trust memory classes SHOULD run stronger audit logging and stricter policy envelopes than nodes that only hold lower-trust or externally derived memory.

##### 17.1.2.2.2 Trust tiers for node roles

Suggested trust ranking for routing and memory promotion:
- Tier A: Settlement / reputation, Tool Intermediary, higher-trust memory nodes
- Tier B: Router / Planner, Verifier / Arbiter, Grounding nodes
- Tier C: Semantic Core and ELM workers
- Tier D: Opportunistic public compute nodes

### 17.1.3 Core Components

#### 17.1.3.1 Router and Planner Service (Query -> Execution Graph)

##### 17.1.3.1.1 Responsibilities

The Router and Planner Service is responsible for converting a user query plus policy context into a signed execution plan.

Responsibilities:
- classify request intent and domain
- choose the smallest effective execution set
- choose execution topology: single-node, ELM-assisted, swarm, or agent mode
- decide whether memory hydration and grounding are required
- decide whether verification or arbitration is required
- decide execution constraints: max tokens, max wall time, max spend
- decide privacy mode
- choose tool policy and memory mode
- emit a signed execution plan suitable for settlement and auditing

##### 17.1.3.1.2 Inputs

- user query
- conversation context
- user policy (privacy, cost, tools, memory constraints)
- memory hints (retrieved candidates)
- grounding requirements
- swarm health / reputation signals
- workspace / project policy

##### 17.1.3.1.3 Outputs

Execution plan fields:
- request_id
- query_hash
- selected_core
- selected_elms[] and required capabilities
- execution_graph
- constraints { max_tokens, max_wall_ms, max_spend }
- privacy_mode
- attestation_requirements
- tool_policy
- memory_mode
- sandbox_profile
- plan_signature

##### 17.1.3.1.4 Execution plan schema

Example JSON schema:

```json
{
  "request_id": "uuid",
  "query_hash": "sha256",
  "selected_core": {
    "core_id": "string",
    "version": "string"
  },
  "selected_elms": [
    {
      "elm_id": "string",
      "version": "string",
      "role": "planner|primary_draft|verifier|arbiter|refiner|formatter|grounding|tool_support|domain_expert",
      "capabilities": ["tool:web.fetch", "memory:retrieve"]
    }
  ],
  "execution_graph": {
    "mode": "single_node|elm_assisted|swarm|agent",
    "topology": "single|sequential|parallel|parallel_with_arbiter",
    "stages": ["memory", "draft", "verify", "ground", "tool", "synthesize"]
  },
  "constraints": {
    "max_tokens": 4096,
    "max_wall_ms": 15000,
    "max_spend": 0.05
  },
  "privacy_mode": "plaintext|restricted|private_boundary",
  "attestation_requirements": {
    "require_task_attestation": true,
    "require_tool_attestation": true,
    "min_reputation": 0.7
  },
  "tool_policy": {
    "require_dry_run": true,
    "human_approval": false,
    "capability_whitelist": ["tool:web.fetch.readonly"],
    "allowlisted_domains": ["docs.gnus.ai"],
    "allowlisted_paths": []
  },
  "memory_mode": "policy_scoped",
  "sandbox_profile": {
    "default_deny": true,
    "platform": "server_firecracker"
  },
  "plan_signature": "ed25519:base64"
}
```

##### 17.1.3.1.5 Routing algorithm (conceptual pseudocode)

```ruby
function route(request, context, policy, memory_hints, grounding_hints, swarm_state):
    intent = classify_intent(request, context)
    risk = classify_risk(request, policy)
    mode = choose_execution_mode(intent, risk, policy, swarm_state)
    memory_mode = choose_memory_mode(risk, policy)
    grounding_mode = choose_grounding_mode(intent, risk, policy)
    experts = choose_core_and_elms(intent, risk, mode, swarm_state)
    graph = choose_execution_graph(mode, experts, grounding_mode)
    constraints = choose_constraints(intent, policy)
    privacy_mode = choose_privacy_mode(policy, risk)
    tool_policy = choose_tool_policy(intent, risk, policy)
    sandbox_profile = choose_sandbox_profile(platform, risk)
    plan = assemble_execution_plan(...)
    return sign(plan)
```

#### 17.1.3.2 Semantic Core and ELM Services

##### 17.1.3.2.1 Responsibilities

The Semantic Core provides broad reasoning, synthesis, and fallback response generation. ELM services provide specialized reasoning optimized for specific roles, domains, or workflow constraints.

Responsibilities:
- produce answer candidates, critiques, verifications, or structured outputs
- emit evidence and references where applicable
- emit confidence and uncertainty
- optionally propose tool_calls[]
- never directly execute side effects

##### 17.1.3.2.2 Key properties

- role specialization through planner, verifier, arbiter, refiner, formatter, grounding, and tool-support roles
- domain specialization through math, code, science, legal, finance, operations, customer support, or private enterprise experts
- versioned artifacts: model + config + policy manifest
- execution may be local or distributed

##### 17.1.3.2.3 Expert output package schema

```json
{
  "request_id": "uuid",
  "expert_id": "string",
  "expert_version": "string",
  "expert_role": "semantic_core|planner|primary_draft|verifier|arbiter|refiner|formatter|grounding|tool_support|domain_expert",
  "answer": "string or structured payload",
  "confidence": 0.0,
  "evidence": [
    {"type": "memory_pointer", "ref": "cid://..."},
    {"type": "citation", "ref": "https://..."}
  ],
  "tool_calls": [
    {
      "tool_call_id": "uuid",
      "tool_name": "web.fetch",
      "arguments": {"url": "https://example.com"},
      "reason": "Need current policy text",
      "expected_side_effects": "none"
    }
  ],
  "expert_signature": "ed25519:base64"
}
```

##### 17.1.3.2.4 Expert packaging and runtime rules

All expert execution artifacts should be versioned, content-addressed, and policy-constrained.

Requirements:
- Artifact is versioned and content-addressed.
- Signature verification occurs before artifact load on every node where signing is required by deployment policy.
- Manifest declares required capabilities.
- Runtime executes under capability-scoped host interfaces only.
- Direct host escape, unrestricted filesystem access, unrestricted network, and direct credential access are prohibited.

##### 17.1.3.2.5 Capability manifest format

Example manifest:

```json
{
  "module_name": "grounding-elm",
  "module_version": "1.2.0",
  "artifact_hash": "sha256:...",
  "signature": "ed25519:...",
  "required_capabilities": [
    {
      "name": "memory.retrieve",
      "scope": "readonly",
      "constraints": {"memory_mode": ["policy_scoped", "trusted_only"]}
    },
    {
      "name": "tool.web.fetch",
      "scope": "proposal_only",
      "constraints": {"domains": ["docs.gnus.ai"]}
    }
  ],
  "sandbox_requirements": {
    "network": "disabled",
    "filesystem": "disabled",
    "clock": "coarse",
    "randomness": "host_attested"
  }
}
```

##### 17.1.3.2.6 Tool proposals are proposals only

Experts may emit tool_calls[] but MUST NOT execute them. All tool_calls[] are proposals only. A proposal becomes executable only after:
- Tool Intermediary dry-run passes
- capability policy check passes
- required human approval is obtained
- signed attestation is produced

#### 17.1.3.3 Verification, Arbitration, and Synthesis Service

##### 17.1.3.3.1 Responsibilities

- synthesize multiple drafts, critiques, and grounding results into a final response
- resolve conflicts and low-confidence disagreements
- enforce policy constraints and consistency checks
- trigger fallback experts if needed
- verify intermediary attestation on any tool-derived data
- produce final metadata for memory writeback and settlement

##### 17.1.3.3.2 Inputs

- original query + context
- Semantic Core and ELM outputs
- retrieved memory snippets
- grounding evidence
- tool intermediary attestations and sanitized tool outputs
- policy constraints

##### 17.1.3.3.3 Outputs

- final response
- agreement / divergence score
- selected sources
- selected sanitized tool outputs
- memory write suggestions
- synthesis signature

##### 17.1.3.3.4 Aggregation logic pseudocode

```ruby
function synthesize(query, expert_outputs, tool_outputs, memory, policy, grounding):
    verified_tool_outputs = filter_attested(tool_outputs)
    policy_scoped_memory = filter_memory(memory, policy.memory_mode)
    grounded_context = filter_grounding(grounding, policy)
    disagreement = measure_divergence(expert_outputs)
    if disagreement > threshold:
        expert_outputs = escalate_or_arbitrate(expert_outputs, grounded_context)
    final = compose(query, expert_outputs, verified_tool_outputs, policy_scoped_memory, grounded_context)
    return final
```

#### 17.1.3.4 Structured Memory Service

##### 17.1.3.4.1 Responsibilities

- decide what to store, when to store it, and how to index it
- provide retrieval for routing, grounding, and generation support
- maintain provenance and trust metadata
- replicate and converge memory state across the swarm

##### 17.1.3.4.2 Memory classes

Primary logical classes:
- Bridge Blocks
- Facts
- Policies and Invariants
- Events and Outcomes
- Tenant Operational Memory

Trust handling overlay where required by policy:
- Higher-trust memory
- Lower-trust or externally derived memory

##### 17.1.3.4.3 Higher-trust memory definition

Higher-trust memory includes information that may safely influence:
- routing
- policy decisions
- invariants
- long-lived user preferences
- stable facts with strong provenance

A higher-trust memory candidate typically must satisfy:
- source from user-approved or verified origin
- strong provenance chain
- safe_to_memorize = true from Tool Intermediary when tool-derived
- policy-compatible local attestation threshold where required

##### 17.1.3.4.4 Lower-trust memory definition

Lower-trust or externally derived memory includes:
- raw or summarized web content
- tool outputs
- episodic external data
- imported documents not yet validated

This memory may be used only for grounding and reasoning support after summarization and instruction-scrub passes. It MUST NOT directly define user invariants, routing rules, or system policy.

##### 17.1.3.4.5 Write gate formula

Conceptually:

write_score = w1 * novelty + w2 * expected_utility + w3 * consistency - w4 * contamination_risk
trusted_score = p1 * provenance_score + p2 * consensus_score + p3 * attestation_score

Promotion rules:
- If write_score < write_threshold: reject
- Else if trusted_score >= trusted_threshold: write as higher-trust memory
- Else: write as lower-trust memory or reject depending on policy

##### 17.1.3.4.6 Retrieval rule

Before any retrieved chunk is injected into a reasoning prompt:
- run instruction scrubber when source class requires it
- annotate provenance class
- downgrade or exclude if policy requires trusted_only behavior

##### 17.1.3.4.7 Replication rule change

- Higher-trust memory requires policy-compatible local consensus before CRDT merge where such controls are enabled.
- Lower-trust memory may replicate with weaker thresholds but MUST retain provenance flags.

##### 17.1.3.4.8 Memory event schema

```json
{
  "memory_event_id": "uuid",
  "request_id": "uuid",
  "memory_class": "bridge_block|fact|policy|event|tenant_operational",
  "trust_class": "higher_trust|lower_trust",
  "content_hash": "sha256",
  "source_type": "user|tool|web|expert|synthesis",
  "source_reputation": 0.0,
  "attestation_refs": ["cid://..."],
  "provenance_score": 0.0,
  "safe_to_memorize": false,
  "instruction_scrubbed": true,
  "consensus_state": "pending|approved|rejected",
  "payload_ref": "cid://..."
}
```

#### 17.1.3.5 Grounding Service

##### 17.1.3.5.1 Responsibilities

- retrieve public or private knowledge relevant to the query
- validate important factual claims against trusted sources
- package grounding evidence for verifiers, arbiters, and final synthesis
- trigger correction or regeneration on conflict

##### 17.1.3.5.2 Grounding paths

- public grounding
- private tenant grounding
- hybrid grounding

##### 17.1.3.5.3 Grounding integration rule

Grounding outputs may influence synthesis only if provenance, policy scope, and freshness satisfy the query's constraints.

#### 17.1.3.6 Task Settlement and Attestations

##### 17.1.3.6.1 Responsibilities

- represent work as auditable tasks
- tie compute to accounting or payout logic
- support re-run sampling, checksums, and proof receipts
- store references to intermediary attestations and memory events

##### 17.1.3.6.2 Task record schema

```json
{
  "task_id": "uuid",
  "request_id": "uuid",
  "plan_hash": "sha256",
  "expert_result_hashes": ["sha256"],
  "tool_attestation_hashes": ["sha256"],
  "memory_event_hashes": ["sha256"],
  "final_response_hash": "sha256",
  "settlement_signature": "ed25519:..."
}
```

#### 17.1.3.7 Privacy and Secure Collaboration

##### 17.1.3.7.1 Responsibilities

- enforce privacy policies for sensitive prompts, memory, or learning signals
- support secure collaboration where multi-node outputs must be combined without overexposing raw inputs

##### 17.1.3.7.2 Privacy attachment points

- expert inference boundary
- synthesis boundary
- memory write boundary
- learning boundary

#### 17.1.3.8 Tool Intermediary Service

##### 17.1.3.8.1 Purpose

The Tool Intermediary Service is the mandatory security choke-point between any agent logic and any real-world side effects, and between external tool outputs and durable memory. It exists to neutralize tool-output prompt injection, prompt traps, capability escalation, and unsafe memory contamination.

##### 17.1.3.8.2 Responsibilities

The Tool Intermediary Service MUST:
- receive every tool_calls[] from Semantic Core support flows, ELMs, or synthesis services
- perform a deterministic dry-run in an isolated environment with no real side effects
- sanitize and scan tool outputs for traps
- enforce zero-trust capabilities declared in the signed execution plan
- emit a signed attestation before allowing real execution or memory writeback
- support optional human approval gating

##### 17.1.3.8.3 Inputs

- original query + execution plan
- proposed tool_calls[]
- capability manifest from expert runtime artifact or adapter
- tool adapter policy profile
- current session / user / workspace policy

##### 17.1.3.8.4 Outputs

- dry_run_result
- attestation
- sanitized_data
- human_approval_required
- rejection_reason when blocked

##### 17.1.3.8.5 Dry-run result schema

```json
{
  "tool_call_id": "uuid",
  "dry_run_ok": true,
  "simulated_effects": {
    "network_requests": ["GET https://docs.gnus.ai/..."],
    "filesystem_access": [],
    "secrets_required": false
  },
  "mock_output": {
    "content_type": "text/plain",
    "preview": "Example simulated output"
  },
  "risk_flags": ["external_html", "instruction_like_text"],
  "human_approval_required": false
}
```

##### 17.1.3.8.6 Attestation schema

```json
{
  "request_id": "uuid",
  "tool_call_id": "uuid",
  "dry_run_ok": true,
  "safe_to_execute": true,
  "safe_to_memorize": false,
  "provenance_hash": "sha256",
  "capability_hash": "sha256",
  "policy_hash": "sha256",
  "sanitizer_version": "1.0.0",
  "intermediary_node_id": "node-123",
  "timestamp_ms": 1775410000000,
  "reason_code": "OK",
  "intermediary_signature": "ed25519:..."
}
```

##### 17.1.3.8.7 Sanitized data schema

```json
{
  "tool_call_id": "uuid",
  "source_hash": "sha256",
  "content_type": "text/plain|application/json|text/markdown",
  "plain_text": "sanitized text",
  "structured_fields": {"title": "...", "body": "..."},
  "strip_report": {
    "removed_zero_width_chars": 2,
    "removed_active_content": true,
    "instruction_scrub_applied": true
  }
}
```

##### 17.1.3.8.8 Deterministic dry-run logic pseudocode

```ruby
function dry_run_tool_call(query, plan, tool_call, manifest, policy):
    assert plan.tool_policy.require_dry_run == true
    assert capability_allowed(tool_call, plan, manifest, policy)
    sandbox = start_isolated_dry_run_sandbox(policy.sandbox_profile)
    simulated = simulate(tool_call, sandbox)
    sanitized = sanitize_output(simulated.mock_output)
    risk_flags = detect_traps(simulated.mock_output, sanitized)
    approval = requires_human_approval(tool_call, risk_flags, policy)
    attestation = sign_attestation(
        dry_run_ok = simulated.ok,
        safe_to_execute = simulated.ok and not blocked(risk_flags, policy),
        safe_to_memorize = memorization_allowed(risk_flags, sanitized, policy),
        provenance_hash = hash(sanitized),
        capability_hash = hash(manifest.required_capabilities),
        policy_hash = hash(policy)
    )
    return simulated, sanitized, attestation, approval
```

##### 17.1.3.8.9 Instruction scrubber pseudocode

```ruby
function instruction_scrub(text):
    normalized = normalize_utf8(text)
    normalized = remove_zero_width_and_control_chars(normalized)
    lines = split_lines(normalized)
    kept = []
    findings = []
    for line in lines:
        if matches_prompt_injection_pattern(line):
            findings.append({"line": line, "reason": "prompt_injection_pattern"})
            continue
        if contains_hidden_command_semantics(line):
            findings.append({"line": line, "reason": "hidden_instruction"})
            continue
        kept.append(line)
    scrubbed = join_lines(kept)
    return scrubbed, findings
```

##### 17.1.3.8.10 Trap detection categories

The detector should support at least:
- prompt injection phrases
- "ignore previous instructions"-style overrides
- hidden or zero-width text
- HTML script/event handlers
- PDF active objects or layered overlays when extractable
- suspicious high-entropy payload markers in media metadata
- encoded content markers requiring additional review

##### 17.1.3.8.11 Human approval gating policy

Human approval should be required when one or more are true:
- tool writes or mutates external state
- tool accesses secrets or credentials
- tool touches non-readonly files
- tool result contains severe risk flags
- user / session / workspace policy requires step-by-step mode

##### 17.1.3.8.12 Real execution after approval

Only after a valid attestation and any required approval may the real tool execution happen. Real execution should run in a sandbox profile at least as strict as the dry-run profile, except for explicitly granted side-effect capabilities.

##### 17.1.3.8.13 Zero-trust sandbox rules

Mandatory rules for all experts and intermediaries:
- default-deny capability model
- Firecracker micro-VM on servers where feasible
- OS-level sandbox on iOS / Android
- capability-based host interfaces only for sandboxed modules
- no ambient network, filesystem, credential, or device permissions
- clock, randomness, and IPC should be mediated by host policy

### 17.1.4 End-to-End Data Flows

#### 17.1.4.1 Primary inference flow (user query)

1. Ingress receives request, authenticates session, loads policy.
2. Memory retrieval fetches relevant context snippets.
3. Router / Planner produces signed execution plan.
4. Swarm dispatch routes tasks to selected Semantic Core and ELM nodes via P2P.
5. Experts compute drafts, critiques, verifications, or grounding outputs and return signed results.
6. Any tool_calls[] are routed to Tool Intermediary Service.
7. Tool Intermediary performs dry-run, sanitization, capability check, and optional human approval pause.
8. If dry_run_ok and policy allows, real execution proceeds.
9. Verifier / Arbiter / synthesis services compose final response using only attested tool outputs and policy-permitted memory.
10. Structured memory evaluates candidate updates and commits approved memory events.
11. Settlement finalizes task record, verifies attestations, and allocates accounting outcomes.

##### 17.1.4.1.1 Detailed sequence notes

- Experts may return immediately with an answer and optional tool proposal.
- Synthesis may either wait for tool results or produce a provisional answer depending on tool criticality.
- Tool-derived outputs that fail sanitization may still be retained in audit logs but must not enter reasoning prompts or higher-trust memory.

#### 17.1.4.2 Learning flow (post-task improvement)

1. Memory write evaluation approves a memory update and emits a learning event.
2. Learning events are queued by domain, role, and policy scope and fed into:
   - router tuning
   - ELM tuning
   - verifier or arbiter improvement
   - memory-governor improvement

##### 17.1.4.2.1 Learning flow security note

- Lower-trust memory MUST NOT directly enter training or adaptation pipelines without additional curation and policy approval.
- Higher-trust promotion criteria must be stricter for training use than for retrieval use.

### 17.1.5 Interfaces and Data Contracts

#### 17.1.5.1 Agent service contracts

Each agent service exposes:
- request schema
- response schema
- error schema
- attestation schema where applicable

#### 17.1.5.2 Processing definitions

Agent work is expressible as processing passes:
- inference
- compute
- data_transform
- verification
- retrieval
- retrain

##### 17.1.5.2.1 Updated processing schema entries

Suggested new schema entities:
- ToolProposal
- ToolPolicy
- ToolAttestation
- SanitizedData
- CapabilityManifest
- MemoryProvenanceMetadata
- TrustClass

##### 17.1.5.2.2 Example ToolProposal schema

```json
{
  "$id": "gnus://schema/ToolProposal",
  "type": "object",
  "properties": {
    "tool_call_id": {"type": "string"},
    "tool_name": {"type": "string"},
    "arguments": {"type": "object"},
    "reason": {"type": "string"},
    "expected_side_effects": {"type": "string"}
  },
  "required": ["tool_call_id", "tool_name", "arguments"]
}
```

##### 17.1.5.2.3 Example ToolAttestation schema

```json
{
  "$id": "gnus://schema/ToolAttestation",
  "type": "object",
  "properties": {
    "tool_call_id": {"type": "string"},
    "dry_run_ok": {"type": "boolean"},
    "safe_to_execute": {"type": "boolean"},
    "safe_to_memorize": {"type": "boolean"},
    "provenance_hash": {"type": "string"},
    "capability_hash": {"type": "string"},
    "policy_hash": {"type": "string"},
    "intermediary_signature": {"type": "string"}
  },
  "required": ["tool_call_id", "dry_run_ok", "safe_to_execute", "provenance_hash"]
}
```

### 17.1.6 Reliability, Fault Tolerance, and Quality Control

#### 17.1.6.1 Fault tolerance

- retry on node failure
- reroute to next-best expert
- allow partial execution-graph completion when acceptable
- exclude unstable nodes using health-aware routing

##### 17.1.6.1.1 Tool Intermediary fault handling

- If intermediary unavailable, block tool execution rather than bypassing policy.
- If dry-run times out, classify as failure and require retry or human intervention.
- If sanitizer fails closed, tool output is unusable for reasoning and memory.

#### 17.1.6.2 Quality safeguards

- cross-expert agreement checks
- fallback expert escalation for high divergence
- verification sampling and reputation impacts via attestations
- tool dry-run attestation verification
- provenance-aware memory retrieval

##### 17.1.6.2.1 Additional safety gates

- synthesis rejects proposal payloads incorporating un-attested tool outputs
- router may request trusted_only behavior for high-stakes queries
- high-risk tools require human approval by default

### 17.1.7 MVP Implementation Mapping

Phase 1 Foundations
- Router / Planner baseline + expert registry + policy envelope
- Basic memory read path and indexing
- Task lifecycle integration points for attestations
- Initial execution plan schema

Phase 2 Expert execution + memory governance
- Deploy initial Semantic Core and role/domain ELM set
- Implement write scoring + structured memory writes
- Validate memory replication in a local swarm
- Add trust_class and provenance metadata to memory records

Phase 3 Verification + secure tool path
- Wire draft, verify, ground, and synthesize stages end-to-end
- Implement Tool Intermediary Service (dry-run engine + baseline sanitizers)
- Add capability manifest + capability enforcement
- Introduce higher-trust / lower-trust memory split and provenance fields

Phase 4 Hardening and demonstration
- Latency breakdown (routing / dispatch / compute / verification / synthesis)
- Quality evaluation
- Reliability tests (node loss, timeouts, reroute)
- Zero-trust sandbox integration
- End-to-end dry-run + attestation tests
- Human-in-the-loop UI hooks for tool gating

### 17.1.8 Metrics and Observability

#### 17.1.8.1 Minimum events to log per task

- routing decision + experts chosen + confidence
- per-expert latency, tokens, errors
- synthesis latency + agreement score
- memory: write score + write / skip + trust class
- settlement: attestation status + accounting outcome
- tool intermediary: dry-run status + sanitizer findings + approval state

#### 17.1.8.2 Primary dashboard metrics

- end-to-end latency p50 / p95
- routing overhead
- synthesis overhead
- expert win rate
- memory write rate and growth
- quality regression trends
- tool attestation failure rate by tool category
- sanitizer hit rate
- human approval rate and median approval latency
- lower-trust-to-higher-trust promotion rate
- higher-trust memory consensus latency

#### 17.1.8.3 Recommended alerting thresholds

- any direct tool execution without attestation: critical
- higher-trust memory write without required consensus state: critical
- sanitizer failure rate spike above baseline: warning / critical
- dry-run timeout p95 over threshold: warning
- human approval queue backlog above threshold: warning

### 17.1.9 Open Decisions for Next Iteration

- standard expert capability ontology for routing
- attestation strictness vs latency tradeoffs
- privacy policy defaults by task category
- memory governance: per-user encryption keys, retention policies, revocation
- exact dry-run simulation depth per tool category
- signing key rotation and revocation policy for constrained execution artifacts
- thresholds for provenance scoring and multi-node memory attestation
- default policy templates for step-by-step human gating per user / session
- sanitizer coverage requirements for HTML / PDF / media

### 17.1.10 Implementation Notes and Recommendations

#### 17.1.10.1 Why tool proposals must be indirect

The architecture intentionally prevents experts from executing tools directly because reasoning models are optimized for task completion, not host security. The Tool Intermediary exists to separate generation from authority. This makes prompt injection materially harder because hostile content must pass through deterministic policy and sanitization before affecting the world.

#### 17.1.10.2 Why higher-trust and lower-trust memory must be separated

A system that learns from tools and the web will otherwise eventually poison its own routing and invariants. The higher-trust / lower-trust split prevents short-lived, tool-derived, or unverified external data from silently becoming durable system guidance.

#### 17.1.10.3 Why constrained execution packaging is preferable for specialist logic

Constrained packaging provides:
- portable deployment
- versioned artifacts
- deterministic host mediation
- restricted interfaces
- auditable rollout

This is consistent with the GNUS secure agent direction and reduces the risk of plugin drift and capability abuse.

#### 17.1.10.4 Recommended first implementation order

1. Enforce tool proposals as proposals only.
2. Build Tool Intermediary dry-run + attestation path.
3. Add sanitization + instruction scrubber.
4. Add trust_class and provenance metadata to memory.
5. Add higher-trust memory promotion threshold + local consensus rule.
6. Harden expert packaging and capability manifests.
7. Harden sandbox profiles per platform.

### 17.1.11 Hand-off Instructions for Next Engineer or LLM

Expand this PTDS into implementation tickets with the following deliverables:

- Final JSON schemas for execution plan, tool proposal, tool attestation, sanitized data, memory event, and capability manifest.
- Host ABI definition for capability requests and denials.
- Sanitizer library selection and language / runtime bindings.
- Dry-run engine implementation per tool category.
- UI approval flow for step-by-step tool gating.
- Processing schema updates for ToolProposal, ToolAttestation, MemoryProvenanceMetadata, TrustClass, and ToolPolicy.
- Security test suite covering:
  - prompt injection in HTML
  - hidden text / zero-width payloads
  - malicious PDF layer text
  - attempted capability escalation
  - memory poisoning attempts
  - missing or forged attestations

### 17.1.12 Summary

This Product Technical Design Specification defines secure agent execution as part of the broader GNUS.ai decentralized cognitive system. The design centers on routing and planning, Semantic Core plus ELM execution, structured memory, grounding-aware verification, secure tool intermediation, reputation-aware trust controls, and auditable task completion. The principal security boundary remains the Tool Intermediary choke-point, reinforced by default-deny sandboxing, capability manifests, and provenance-aware memory promotion. Together, these measures reduce the most important agent-specific attack classes without abandoning the decentralized performance and auditability goals of the GNUS architecture.

---
[Previous: Distributed Swarm Thinking Context Architecture](./11-distributed-swarm-thinking-context.md) | [Architecture Index](./INDEX.md) | [Next: EGGROLL Swarm Retraining Architecture](./13-eggroll-swarm-retraining.md)
