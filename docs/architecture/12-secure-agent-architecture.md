# 17 Architecture for Facilitating AI Agents in the GNUS.ai Decentralized AI System (Chat Genius-Integrated)
## 17.1 Product Technical Design Specification

This document specifies the architecture for the Chat Genius AI Agents subsystem running
on the GNUS.ai Swarm Operating System. It is integrated with the Chat Genius MVP plan and
defines how specialist micro/nano SLMs, Mixture-of-Agents (MoA) collaboration, surprise-
gated memory, universal subspaces, security hardening, and trust-aware decentralized
execution operate end-to-end on GNUS.ai's P2P networking, Fast-DAG blockchain
settlement, and MPC privacy layer.

This version expands the original architecture into a more implementation-ready Product
Technical Design Specification (PTDS). It preserves the original system shape and extends
it with detailed service responsibilities, data contracts, security controls, pseudocode,
state transitions, and implementation notes. It also incorporates the Security Hardening
Layer additions requested for Tool Intermediary gating, zero-trust sandboxing, signed
WASM modules, and provenance-aware memory.

### 17.1.1 Goals and Success Criteria

#### 17.1.1.1 Primary goals

Decentralized agent execution
Route each request to the smallest set of best-fit experts across the swarm while preserving
latency, quality, and auditability.

High-quality synthesis
Combine multiple specialist proposals using MoA-style aggregation, with explicit reasoning
about disagreement, evidence quality, and trust provenance.

Persistent intelligence
Store and retrieve long-term memory using surprise-gated updates to minimize noise,
prevent contamination, and improve future routing and responses.

Teachability at scale
Deploy many specialist models by leveraging universal subspaces derived from teacher
models, minimizing training cost and enabling frequent specialist refreshes.

Trust and economics built-in
Every job has attestations, policy envelopes, and settlement over the Fast-DAG ledger,
with privacy controls via MPC and security boundaries via zero-trust sandboxing.

Security by default
No specialist, aggregator, or tool adapter may directly cause side effects without passing
through a deterministic, auditable, capability-scoped security choke-point.

#### 17.1.1.2 MVP targets (from plan)

Quality retention
- Less than 0.2 perplexity drop after the teaching + compression pipeline target.

Speed
- Less than 10 ms swarm overhead for routing/dispatch under local swarm conditions.
- Tool Intermediary overhead target for dry-run + sanitization should remain bounded and
  reported separately from model inference latency.

Utility
- Greater than 60 percent on an AlpacaEval subset.

Security targets
- 100 percent of tool executions must have a valid intermediary attestation.
- 0 direct side-effect executions from specialists.
- 100 percent of Trusted Memory writes must contain provenance metadata and consensus
  attestation where required.

#### 17.1.1.3 Non-goals for MVP

- Full formal verification of all WASM modules.
- Universal support for arbitrary third-party tools.
- Perfect steganography detection across all media types.
- Global cross-swarm consensus for all memory writes. MVP scope is local swarm consensus
  for Trusted Memory promotion.

### 17.1.2 System Overview (Agent Subsystem on GNUS Swarm OS)

#### 17.1.2.1 Layer model

The subsystem is decomposed into layers to preserve separation of concerns and to allow
independent scaling, auditing, and policy hardening.

- Client/API layer
  - chat session lifecycle
  - authentication and authorization
  - request submission
  - user-visible approvals and status updates

- Agent orchestration layer
  - router
  - MoA planner
  - aggregator
  - policy engine bindings
  - execution plan generation

- Expert execution layer
  - specialist SLM workers
  - tool proposal emitters
  - local structured post-processing

- Tool Intermediary layer
  - deterministic dry-run simulation
  - output sanitization and trap detection
  - capability enforcement
  - tool execution attestation
  - side-effect gating

- Memory layer
  - surprise gate
  - indexing
  - retrieval
  - provenance scoring
  - CRDT replication
  - trusted vs untrusted partitioning

- Swarm OS layer
  - P2P transport
  - storage
  - scheduling
  - node discovery
  - health reporting

- Trust/economics layer
  - Fast-DAG settlement
  - task attestations
  - accounting
  - payout triggers

- Privacy layer
  - MPC execution modes
  - secure aggregation where required
  - privacy policy enforcement

##### 17.1.2.1.1 Layer interactions

The normal query path is:
Client/API -> Router -> Experts -> Tool Intermediary (if tools proposed) -> Aggregator ->
Memory -> Settlement -> Client/API

The normal learning path is:
Memory write candidate -> surprise gate + provenance gate -> CRDT merge -> learning queue ->
router/specialist/subspace updates

##### 17.1.2.1.2 Security hardening insertion rationale

The Tool Intermediary layer exists specifically because tool-using agents introduce a
fundamentally different threat model than pure generation. A specialist that can browse,
open files, parse PDFs, or emit shell-like commands can be manipulated by hostile external
content. Therefore the architecture requires a mandatory intermediary choke-point between
all proposal logic and all side effects. This design preserves the MoA architecture while
reducing the attack surface of prompt injection, memory poisoning, hidden instructions,
and capability escalation.

#### 17.1.2.2 Node roles (typical deployment)

A GNUS node may host one or more roles. Local 10-node swarms use the same interfaces as
wide-area deployments.

- Ingress/API node
  - session handling
  - auth and rate limiting
  - UI status events

- Router node
  - policy + expert selection
  - execution plan generation
  - memory-mode selection

- Expert worker node
  - specialist inference
  - evidence packaging
  - tool proposal generation only

- Aggregator node
  - proposal synthesis
  - divergence handling
  - final answer packaging

- Memory/index node
  - storage
  - retrieval
  - indexing
  - CRDT replication

- Settlement/verifier node
  - task attestations
  - DAG transaction finalization
  - payout and reputation recording

- Tool Intermediary node
  - dry-run engine
  - sanitizer pipeline
  - capability enforcement
  - human approval pause logic
  - attestation generation

##### 17.1.2.2.1 Node colocation rules

- Small swarms MAY co-locate Router + Aggregator + Tool Intermediary on one node.
- Expert worker nodes SHOULD remain isolated from the settlement role.
- High-trust deployments SHOULD isolate Tool Intermediary from Expert execution to reduce
  local privilege escalation risk.
- Memory/index nodes that handle Trusted Memory SHOULD run stronger audit logging and
  stricter policy envelopes than nodes that only hold Untrusted Memory.

##### 17.1.2.2.2 Trust tiers for node roles

Suggested trust ranking for routing and memory promotion:
- Tier A: Settlement/verifier, Tool Intermediary, Trusted Memory nodes
- Tier B: Router, Aggregator
- Tier C: Specialist workers
- Tier D: Opportunistic public compute nodes

### 17.1.3 Core Components

#### 17.1.3.1 Router Service (Query -> Plan)

##### 17.1.3.1.1 Responsibilities

The Router Service is responsible for converting a user query plus policy context into a
signed execution plan.

Responsibilities:
- classify request intent and domain
- choose the smallest effective expert set (typically 1 to 3)
- choose MoA topology (single answer, k proposals, sequential verify, etc.)
- decide execution constraints: max tokens, max wall time, max spend
- decide privacy mode: plaintext vs MPC path
- choose tool policy and memory mode
- emit a signed execution plan suitable for settlement and auditing

##### 17.1.3.1.2 Inputs

- user query
- conversation context
- user policy (privacy, cost, tools, memory constraints)
- memory hints (retrieved candidates)
- swarm health/reputation signals
- workspace/project policy

##### 17.1.3.1.3 Outputs

Execution plan fields:
- request_id
- query_hash
- experts[] and required capabilities
- moa_graph
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
  "experts": [
    {
      "expert_id": "string",
      "version": "string",
      "role": "proposer|verifier|formatter|aggregator_support",
      "capabilities": ["tool:web.fetch", "memory:retrieve"]
    }
  ],
  "moa_graph": {
    "topology": "single|fanout|fanout_verify|fanout_aggregate",
    "proposers": ["expert-a", "expert-b"],
    "aggregator": "agg-1"
  },
  "constraints": {
    "max_tokens": 4096,
    "max_wall_ms": 15000,
    "max_spend": 0.05
  },
  "privacy_mode": "plaintext|mpc_required|mpc_preferred",
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
  "memory_mode": "trusted_only",
  "sandbox_profile": {
    "default_deny": true,
    "platform": "server_firecracker"
  },
  "plan_signature": "ed25519:base64"
}
```

##### 17.1.3.1.5 Routing algorithm (conceptual pseudocode)

```ruby
function route(request, context, policy, memory_hints, swarm_state):
    intent = classify_intent(request, context)
    risk = classify_risk(request, policy)
    experts = choose_experts(intent, risk, swarm_state)
    moa_graph = choose_moa_topology(intent, risk, experts)
    constraints = choose_constraints(intent, policy)
    privacy_mode = choose_privacy_mode(policy, risk)
    tool_policy = choose_tool_policy(intent, risk, policy)
    memory_mode = choose_memory_mode(risk, policy)
    sandbox_profile = choose_sandbox_profile(platform, risk)
    plan = assemble_execution_plan(...)
    return sign(plan)
```

#### 17.1.3.2 Specialist Expert Services (Micro/Nano SLMs)

##### 17.1.3.2.1 Responsibilities

Each Specialist Expert Service produces a proposal response optimized for a niche domain,
format, or role.

Responsibilities:
- produce an answer candidate
- emit evidence and references where applicable
- emit confidence and uncertainty
- optionally propose tool_calls[]
- never directly execute side effects

##### 17.1.3.2.2 Key properties

- domain specialization via niche data + instruction tuning
- optional teacher prior via universal subspaces
- versioned artifacts: model + config + policy manifest
- signed WASM packaging for non-core specialist logic

##### 17.1.3.2.3 Specialist output package schema

```json
{
  "request_id": "uuid",
  "expert_id": "string",
  "expert_version": "string",
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

##### 17.1.3.2.4 Signed WASM module rules

All non-core specialist logic runs as signed WASM modules.

Requirements:
- Module artifact is versioned and content-addressed.
- Module is signed by GNUS build pipeline or approved signer.
- Signature verification occurs before module load on every node.
- Module manifest declares required capabilities.
- Module executes via capability-based WASI interfaces only.
- Direct host escape, unrestricted filesystem access, unrestricted network, and direct
  credential access are prohibited.

##### 17.1.3.2.5 WASM capability manifest format

Example manifest:

```json
{
  "module_name": "math-specialist",
  "module_version": "1.2.0",
  "artifact_hash": "sha256:...",
  "signature": "ed25519:...",
  "required_capabilities": [
    {
      "name": "memory.retrieve",
      "scope": "readonly",
      "constraints": {"memory_mode": ["trusted_only", "trusted_plus_summarized_untrusted"]}
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

Specialists may emit tool_calls[] but MUST NOT execute them.
All tool_calls[] are proposals only. A proposal becomes executable only after:
- Tool Intermediary dry-run passes
- capability policy check passes
- required human approval is obtained
- signed attestation is produced

#### 17.1.3.3 MoA Aggregator Service (Proposals -> Final Answer)

##### 17.1.3.3.1 Responsibilities

- synthesize multiple proposals into a final response
- resolve conflicts and low-confidence disagreements
- enforce policy constraints and consistency checks
- trigger fallback experts if needed
- verify intermediary attestation on any tool-derived data
- produce final metadata for memory writeback and settlement

##### 17.1.3.3.2 Inputs

- original query + context
- specialist proposals
- retrieved memory snippets
- tool intermediary attestations and sanitized tool outputs
- policy constraints

##### 17.1.3.3.3 Outputs

- final response
- agreement/divergence score
- selected sources
- selected sanitized tool outputs
- memory write suggestions
- aggregator signature

##### 17.1.3.3.4 Aggregation logic pseudocode

```ruby
function aggregate(query, proposals, tool_outputs, memory, policy):
    verified_tool_outputs = filter_attested(tool_outputs)
    trusted_memory = filter_memory(memory, policy.memory_mode)
    disagreement = measure_divergence(proposals)
    if disagreement > threshold:
        proposals = escalate_or_verify(proposals)
    final = synthesize(query, proposals, verified_tool_outputs, trusted_memory)
    return final
```

#### 17.1.3.4 Surprise-Gated Memory Service

##### 17.1.3.4.1 Responsibilities

- decide what to store, when to store it, and how to index it
- provide retrieval for routing and generation grounding
- maintain provenance and trust class metadata
- replicate and converge memory state across the swarm

##### 17.1.3.4.2 Memory classes

Original logical classes:
- Episodic
- Semantic
- Invariants/policies
- Feedback

Trust partition overlay:
- Trusted Memory
- Untrusted Memory

##### 17.1.3.4.3 Trusted Memory definition

Trusted Memory includes information that may safely influence:
- routing
- policy decisions
- invariants
- long-lived user preferences
- stable facts with strong provenance

A Trusted Memory candidate typically must satisfy:
- source from user-approved or verified origin
- strong provenance chain
- safe_to_memorize = true from Tool Intermediary when tool-derived
- multi-node local swarm attestation threshold

##### 17.1.3.4.4 Untrusted Memory definition

Untrusted Memory includes:
- raw or summarized web content
- tool outputs
- episodic external data
- imported documents not yet validated

Untrusted Memory may be used only for grounding and reasoning support after summarization
and instruction-scrub passes. It MUST NOT directly define user invariants, routing rules,
or system policy.

##### 17.1.3.4.5 Surprise and provenance gate formula

Conceptually:

write_score = w1 * novelty + w2 * expected_utility + w3 * consistency - w4 * contamination_risk
trusted_score = p1 * provenance_score + p2 * consensus_score + p3 * attestation_score

Promotion rules:
- If write_score < write_threshold: reject
- Else if trusted_score >= trusted_threshold: write as Trusted Memory
- Else: write as Untrusted Memory or reject depending on policy

##### 17.1.3.4.6 Retrieval rule

Before any retrieved chunk is injected into a reasoning prompt:
- run instruction scrubber
- annotate provenance class
- downgrade or exclude if policy requires trusted_only

##### 17.1.3.4.7 Replication rule change

- Trusted Memory requires minimum 2/3 consensus in local swarm before CRDT merge.
- Untrusted Memory may replicate with weaker thresholds but MUST retain provenance flags.

##### 17.1.3.4.8 Memory event schema

```json
{
  "memory_event_id": "uuid",
  "request_id": "uuid",
  "memory_class": "episodic|semantic|invariant|feedback",
  "trust_class": "trusted|untrusted",
  "content_hash": "sha256",
  "source_type": "user|tool|web|expert|aggregator",
  "source_reputation": 0.0,
  "attestation_refs": ["cid://..."],
  "provenance_score": 0.0,
  "safe_to_memorize": false,
  "instruction_scrubbed": true,
  "consensus_state": "pending|approved|rejected",
  "payload_ref": "cid://..."
}
```

#### 17.1.3.5 Universal Subspace Service (Teaching/Distillation Plane)

##### 17.1.3.5.1 Responsibilities

- maintain low-dimensional subspace bases derived from teacher models
- train specialists by learning coefficients in that basis and optional adapters
- package and deploy specialists across the swarm with version control

##### 17.1.3.5.2 Pipeline

1. Teacher analysis
2. Universal subspace extraction
3. Specialist coefficient/adaptor training
4. Validation
5. Artifact packaging and signing
6. Swarm distribution and deployment attestation

#### 17.1.3.6 Task Settlement and Attestations (Fast-DAG)

##### 17.1.3.6.1 Responsibilities

- represent work as auditable tasks
- tie compute to escrow/payout logic
- support re-run sampling, checksums, and proof receipts
- store references to intermediary attestations

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

#### 17.1.3.7 Privacy and Secure Collaboration (MPC)

##### 17.1.3.7.1 Responsibilities

- enforce privacy policies for sensitive prompts, memory, or learning signals
- support secure aggregation where multi-node outputs must be combined without revealing
  raw inputs

##### 17.1.3.7.2 MPC attachment points

- expert inference boundary
- aggregation boundary
- memory write boundary
- federated learning boundary

#### 17.1.3.8 Tool Intermediary Service

##### 17.1.3.8.1 Purpose

The Tool Intermediary Service is the mandatory security choke-point between any agent logic
and any real-world side effects, and between external tool outputs and durable memory.
It exists to neutralize tool-output prompt injection, prompt traps, capability escalation,
and unsafe memory contamination.

##### 17.1.3.8.2 Responsibilities

The Tool Intermediary Service MUST:
- receive every tool_calls[] from specialists or the MoA Aggregator
- perform a deterministic dry-run in an isolated environment with no real side effects
- sanitize and scan tool outputs for traps
- enforce zero-trust capabilities declared in the signed execution plan
- emit a signed attestation before allowing real execution or memory writeback
- support optional human approval gating

##### 17.1.3.8.3 Inputs

- original query + execution plan
- proposed tool_calls[]
- capability manifest from signed WASM or C++ adapter
- tool adapter policy profile
- current session/user/workspace policy

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
    "network_requests": ["GET https://docs.gnus.ai/..."] ,
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
- user/session/workspace policy requires step-by-step mode

##### 17.1.3.8.12 Real execution after approval

Only after a valid attestation and any required approval may the real tool execution happen.
Real execution should run in a sandbox profile at least as strict as the dry-run profile,
except for explicitly granted side-effect capabilities.

##### 17.1.3.8.13 Zero-trust sandbox rules

Mandatory rules for all experts and intermediaries:
- default-deny capability model
- Firecracker micro-VM on servers where feasible
- OS-level sandbox on iOS/Android
- capability-based WASI interfaces only for WASM modules
- no ambient network, filesystem, credential, or device permissions
- clock, randomness, and IPC should be mediated by host policy

### 17.1.4 End-to-End Data Flows

#### 17.1.4.1 Primary inference flow (user query)

1. Ingress receives request, authenticates session, loads policy.
2. Memory retrieval fetches relevant context snippets.
3. Router produces signed execution plan.
4. Swarm dispatch routes tasks to selected expert nodes via P2P.
5. Experts compute proposals and return signed results.
6. Any tool_calls[] are routed to Tool Intermediary Service.
7. Tool Intermediary performs dry-run, sanitization, capability check, and optional human
   approval pause.
8. If dry_run_ok and policy allows, real execution proceeds.
9. Aggregator synthesizes final response using only attested tool outputs and policy-
   permitted memory.
10. Surprise-gated memory evaluates candidate updates and commits approved memory events.
11. Settlement finalizes task record, verifies attestations, allocates payouts.

##### 17.1.4.1.1 Detailed sequence notes

- Experts may return immediately with an answer and optional tool proposal.
- Aggregator may either wait for tool results or produce a provisional answer depending on
  tool criticality.
- Tool-derived outputs that fail sanitization may still be retained in audit logs but must
  not enter reasoning prompts or Trusted Memory.

#### 17.1.4.2 Learning flow (surprise-driven improvement)

1. Surprise gate approves a memory update and emits a learning event.
2. Learning events are queued by niche/domain and fed into:
   - router tuning
   - specialist tuning
   - aggregator improvement
   - subspace coefficient training updates

##### 17.1.4.2.1 Learning flow security note

- Untrusted Memory MUST NOT directly enter specialist training pipelines without additional
  curation and policy approval.
- Trusted Memory promotion criteria must be stricter for training use than for retrieval
  use.

### 17.1.5 Interfaces and Data Contracts

#### 17.1.5.1 Agent service contracts

Each agent service exposes:
- request schema
- response schema
- error schema
- attestation schema where applicable

#### 17.1.5.2 Processing definitions (GNUS processing schema alignment)

Agent work is expressible as processing passes:
- inference
- compute
- data_transform
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
- allow partial MoA completion when acceptable
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

- aggregator rejects proposal payloads incorporating un-attested tool outputs
- router may request trusted_only mode for high-stakes queries
- high-risk tools require human approval by default

### 17.1.7 MVP Implementation Mapping (4 Weeks)

Week 1 Foundations
- Router baseline + expert registry + policy envelope
- Basic memory read path and indexing
- Task lifecycle integration points for DAG + attestations
- Initial execution plan schema

Week 2 Specialists + Surprise-Gated Memory
- Train initial specialist set
- Implement surprise scoring + structured memory writes
- Validate memory replication in a local swarm
- Add trust_class and provenance metadata to memory records

Week 3 MoA Layering + Universal Subspaces
- Wire proposers + aggregator end-to-end
- Build subspace extraction and coefficient training loop
- Deploy multiple expert versions with manifesting and integrity checks
- Implement Tool Intermediary Service (dry-run engine + baseline sanitizers)
- Add signed WASM manifest + capability enforcement
- Introduce Trusted/Untrusted memory split and provenance fields

Week 4 Benchmarks, Hardening, and Demo
- Latency breakdown (routing/dispatch/compute/aggregation)
- Quality eval (perplexity + AlpacaEval subset)
- Reliability tests (node loss, timeouts, reroute)
- Zero-trust sandbox integration (Firecracker + iOS sandbox prototypes)
- End-to-end dry-run + attestation tests
- Human-in-the-loop UI hooks for tool gating

### 17.1.8 Metrics and Observability

#### 17.1.8.1 Minimum events to log per task

- routing decision + experts chosen + confidence
- per-expert latency, tokens, errors
- aggregation latency + agreement score
- memory: surprise score + write/skip + trust class
- settlement: attestation status + payout outcome
- tool intermediary: dry-run status + sanitizer findings + approval state

#### 17.1.8.2 Primary dashboard metrics

- end-to-end latency p50/p95
- routing overhead
- aggregation overhead
- expert win rate
- memory write rate and growth
- quality regression trends
- tool attestation failure rate by tool category
- sanitizer hit rate
- human approval rate and median approval latency
- untrusted-to-trusted promotion rate
- trusted memory 2/3 consensus latency

#### 17.1.8.3 Recommended alerting thresholds

- any direct tool execution without attestation: critical
- Trusted Memory write without consensus state: critical
- sanitizer failure rate spike above baseline: warning/critical
- dry-run timeout p95 over threshold: warning
- human approval queue backlog above threshold: warning

### 17.1.9 Open Decisions for Next Iteration

- standard expert capability ontology for routing
- attestation strictness vs latency tradeoffs
- MPC policy defaults by task category
- memory governance: per-user encryption keys, retention policies, revocation
- exact dry-run simulation depth per tool category
- WASM signing key rotation and revocation policy
- thresholds for provenance scoring and multi-node memory attestation
- default policy templates for step-by-step human gating per user/session
- sanitizer coverage requirements for HTML/PDF/media

### 17.1.10 Implementation Notes and Recommendations

#### 17.1.10.1 Why tool proposals must be indirect

The architecture intentionally prevents experts from executing tools directly because expert
models are optimized for task completion, not host security. The Tool Intermediary exists to
separate generation from authority. This makes prompt injection materially harder because
hostile content must pass through deterministic policy and sanitization before affecting the
world.

#### 17.1.10.2 Why trusted and untrusted memory must be separated

A system that learns from tools and the web will otherwise eventually poison its own
routing and invariants. The Trusted/Untrusted split prevents short-lived, tool-derived,
or unverified external data from silently becoming durable system guidance.

#### 17.1.10.3 Why signed WASM is preferable for specialist logic

Signed WASM provides:
- portable packaging
- versioned artifacts
- deterministic host mediation
- restricted interfaces
- auditable deployment

This is consistent with the GNUS Secure Agent Protocol direction and reduces the risk of
native plugin drift and capability abuse.

#### 17.1.10.4 Recommended first implementation order

1. Enforce tool proposals as proposals only.
2. Build Tool Intermediary dry-run + attestation path.
3. Add sanitization + instruction scrubber.
4. Add trust_class and provenance metadata to memory.
5. Add Trusted Memory promotion threshold + 2/3 local consensus.
6. Move specialist runtime into signed WASM with capability manifests.
7. Harden sandbox profiles per platform.

### 17.1.11 Hand-off Instructions for Next Engineer or LLM

Expand this PTDS into implementation tickets with the following deliverables:

- Final JSON schemas for execution plan, tool proposal, tool attestation, sanitized data,
  memory event, and capability manifest.
- Host ABI definition for WASM capability requests and denials.
- Sanitizer library selection and language/runtime bindings.
- Dry-run engine implementation per tool category.
- UI approval flow for step-by-step tool gating.
- gnus-processing-schema.json updates for ToolProposal, ToolAttestation,
  MemoryProvenanceMetadata, TrustClass, and ToolPolicy.
- Security test suite covering:
  - prompt injection in HTML
  - hidden text / zero-width payloads
  - malicious PDF layer text
  - attempted capability escalation
  - memory poisoning attempts
  - missing or forged attestations

### 17.1.12 Summary

This Product Technical Design Specification preserves the original GNUS.ai Chat Genius
agent architecture while making it substantially more implementation-ready. The design still
centers on decentralized routing, specialist experts, MoA aggregation, surprise-gated
memory, universal subspaces, Fast-DAG settlement, and MPC privacy. The principal addition
is a security hardening layer that inserts a Tool Intermediary choke-point, default-deny
sandboxing, signed WASM specialists, and provenance-aware memory promotion. Together,
these measures reduce the most important agent-specific attack classes without abandoning
the decentralized performance and auditability goals of the original system.

---
[Previous: Distributed Swarm Thinking Context Architecture](./11-distributed-swarm-thinking-context.md) | [Architecture Index](./INDEX.md) | [Next: Eggroll Swarm Retraining](./13-eggroll-swarm-retraining.md)
