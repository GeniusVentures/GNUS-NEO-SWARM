# GNUS Secure Agent Architecture
# Protocol Technical Design Specification (PTDS v1.0)

---

# 1. Executive Overview

The GNUS Secure Agent Architecture defines a decentralized, deterministic, capability-scoped execution framework for AI agents operating within the GNUS DAG + CRDT + MPC ecosystem.

The system is designed to:

- Prevent AI privilege escalation
- Eliminate direct AI-to-action authority
- Enforce deterministic policy gating
- Support Byzantine fault tolerance
- Enable multi-node AI consensus
- Ensure auditability and replay validation
- Remain mobile-first (no Node.js required)

This architecture replaces traditional “AI tool-calling” systems with a **blockchain-grade secure AI runtime**.

---

# 2. Architectural Layers

The system consists of six primary layers:

```
User / External Input
        ↓
Secure Agent Runtime
        ↓
GNUS Host ABI (Security Boundary)
        ↓
Policy Engine (Deterministic)
        ↓
Multi-Node Consensus (Optional)
        ↓
GNUS DAG + CRDT + MPC
```

Each layer is independently hardened.

---

# 3. Core Components

## 3.1 Secure Agent

A Secure Agent is a versioned, signed execution unit defined by:

```json
{
  "agent_id": "string",
  "version": "semver",
  "code_hash": "sha256",
  "capability_hash": "sha256",
  "policy_hash": "sha256",
  "abi_version": "gsa-abi.v1",
  "security_level": "low | medium | high | critical"
}
```

All hashes are registered on the DAG.

Agents cannot mutate their capabilities at runtime.

---

## 3.2 Execution Types

Supported execution engines:

- WASM Capsule (primary)
- GNUS Agent Language (GAL)
- Hybrid (WASM + GAL)

All execution engines must use the GNUS Host ABI as their only system interface.

---

# 4. Capability Permission System

Capabilities are declared via a Capability Profile.

### Domains:

- Memory
- CRDT
- DAG
- Experts (MoE)
- Capsule Invocation
- Network (default disabled)
- Secrets (MPC-gated)
- Compute (gas)

Default model: deny everything unless explicitly enabled.

Example:

```json
"dag": {
  "submit_tx": true,
  "allowed_tx_types": ["trade.execute"],
  "max_tx_per_minute": 5,
  "max_value_per_tx": 1000
}
```

Capabilities are:

- Hash-bound to agent version
- Immutable per execution
- Enforced at Host ABI boundary
- Visible on-chain
- Auditable

---

# 5. GNUS Secure Agent Host ABI (GSA-ABI v1)

The ABI is the sole syscall interface between agent and GNUS core.

### Design Principles

- Hardcoded function table
- JSON structured I/O
- No raw memory access
- Gas metered
- Capability gated
- Deterministic

### Allowed Functions

| ID | Function |
|----|----------|
| 0x01 | invoke_expert |
| 0x02 | read_crdt |
| 0x03 | request_crdt_write |
| 0x04 | request_tx |
| 0x05 | invoke_capsule |
| 0x06 | submit_decision |
| 0x07 | get_gas_remaining |

If it is not in this table, it does not exist.

No:

- Filesystem
- Raw network
- System time
- Random entropy
- Thread creation
- Dynamic module loading

---

# 6. Deterministic Policy Engine

AI outputs are advisory only.

AI must return structured output:

```json
{
  "decision": "allow | deny | escalate",
  "confidence": 0.91,
  "risk_score": 0.08
}
```

The Policy Engine:

- Is pure deterministic C++
- Does not call AI
- Cannot mutate capabilities
- Evaluates rules against AI output
- Produces final action

Rule example:

```json
if confidence < 0.6 → escalate
if risk_score > 0.8 → quarantine
else allow
```

AI never executes actions directly.

---

# 7. Multi-Node Consensus Protocol (GSAMCP v1)

Activated when:

- security_level ≥ high
- OR capability profile requires multi-node

## 7.1 Node Assignment

DAG selects N nodes:

- Deterministic pseudo-random selection
- Weighted by stake/reputation
- Rotation enforced

N defaults:

- High → 3 nodes
- Critical → 5–7 nodes

---

## 7.2 Execution

Each node:

1. Verifies agent hash
2. Executes independently
3. Calls expert locally
4. Produces structured output
5. Signs result

Nodes do not see each other’s output.

---

## 7.3 Consensus Modes

### Mode A: Majority Vote
- ≥ 2/3 agreement required

### Mode B: Threshold Agreement
- T identical outputs required

### Mode C: MPC Aggregation
- Encrypted shares
- Aggregated without revealing node-level outputs

---

## 7.4 Commit-Reveal (Optional)

1. Nodes submit hash(output)
2. After all commits received → reveal phase

Prevents output copying.

---

## 7.5 Disagreement Handling

If no threshold reached:

- Escalate to higher N
- Require human review
- Abort
- Default restrictive

System never auto-approves on disagreement.

---

# 8. Gas & Resource Model

Gas deducted for:

- WASM opcodes
- Expert tokens
- Memory allocation
- CRDT writes
- DAG submission

If gas ≤ 0 → abort.

Resource constraints include:

- max_execution_ms
- max_model_calls
- max_memory_bytes
- max_tx_rate
- max_write_bytes

Prevents DoS and infinite loops.

---

# 9. CRDT Integration

CRDT writes:

- Must pass capability check
- Must pass policy engine
- Must be namespace-scoped
- Are logged with execution_id

No raw CRDT mutation by AI.

---

# 10. DAG Integration

All state-changing actions:

- Are submitted as DAG transactions
- Include:
    - agent_version
    - capability_hash
    - node_ids
    - consensus_mode
    - aggregated_output_hash

Ensures auditability.

---

# 11. MPC Integration

Used for:

- Secret access
- Critical financial actions
- Encrypted aggregation

Secrets:

- Never exposed to AI directly
- Decrypted only through MPC quorum
- Bound to capability profile

---

# 12. Security Properties

The architecture guarantees:

- AI cannot escalate privileges
- AI cannot self-upgrade
- AI cannot modify capabilities
- AI cannot directly execute system actions
- Single node compromise cannot control outcome (high/critical modes)
- All decisions are replayable
- All actions are auditable

---

# 13. Threat Model Coverage

Defends against:

- Prompt injection
- Tool injection
- Privilege escalation
- Node compromise (≤ threshold)
- Model drift
- Recursive execution attacks
- CRDT poisoning
- Transaction flooding
- Secret leakage
- Collusion below threshold

Assumes:

- Less than 1/3 malicious nodes in majority mode
- Less than T malicious nodes in threshold mode

---

# 14. Upgrade & Governance Model

Upgrades require:

- New agent version
- New capability hash
- New policy hash
- DAG registration
- Optional governance vote

No runtime mutation allowed.

Revocation possible via:

- Owner signature
- Governance vote
- Automatic anomaly trigger

---

# 15. Audit & Replay

Each execution produces:

```json
{
  "execution_id": "...",
  "agent_version": "...",
  "node_ids": [...],
  "node_output_hashes": [...],
  "aggregated_result": {...},
  "final_action": "...",
  "signature_bundle": "..."
}
```

Anyone can:

- Verify signatures
- Verify threshold rule
- Replay policy logic
- Audit gas usage
- Confirm capability compliance

---

# 16. Mobile-First Compatibility

No Node.js required.

Mobile runtime includes:

- Embedded WASM engine
- GNUS Host ABI layer
- Deterministic policy engine
- CRDT client
- DAG client

All secure logic is C++ level.

WebView plugins may render UI, but:

- Cannot access device storage
- Cannot access network
- Can only call GNUS Host ABI

---

# 17. Performance Considerations

Multi-node cost scales linearly with N.

Security scales non-linearly.

Adaptive security model recommended:

- Low-value → single node
- Medium-risk → 3 nodes
- High-value → 5 nodes
- Critical → 5 + MPC

Parallel execution minimizes latency increase.

---

# 18. Reference Security Levels

| Level | Nodes | MPC | Use Case |
|-------|-------|-----|----------|
| Low | 1 | No | Low-risk classification |
| Medium | 1 | No | Deterministic policy gating |
| High | 3 | Optional | Financial routing |
| Critical | 5–7 | Yes | Bank-grade actions |

---

# 19. Strategic Positioning

This architecture combines:

- Smart contract determinism
- BFT consensus
- MPC privacy
- AI inference
- Capability-based security
- Mobile-native runtime

It is not a chatbot framework.

It is a decentralized AI execution protocol.

---

# 20. Conclusion

The GNUS Secure Agent Architecture transforms AI from an opaque decision engine into:

- A capability-scoped advisory layer
- Embedded inside a deterministic, auditable, consensus-driven runtime
- With blockchain-grade security guarantees

This PTDS defines a complete protocol-ready foundation for decentralized secure AI agents.
