# **7 Reputation-Based Consensus System**

This is a core differentiator of the GNUS cognitive architecture.

---

## **7.1 Reputation Data Model**

Each node maintains role-aware and domain-aware reputation signals.

```json
Node {
  Identity_key
  Global_score
  Planner_score
  Math_score
  Grounding_score
  Verification_score
  Formatting_score
  Latency_score
  Consistency_score
  Safety_score
}
```

Stored via:

* wallet-core
* RocksDB
* CRDT replicated state

---

## **7.2 Reputation Update Formula**

After each task:

### **7.2.1 Accuracy / Quality Component**

If stronger validation or ground truth is available:

Δscore = α * (quality - baseline_quality)

If no direct ground truth is available:

Δscore = β * (agreement_with_weighted_consensus)

If verifier or grounding evidence contradicts the result:

Δscore_validation = -μ * contradiction_severity

---

### **7.2.2 Latency Component**

Δscore_latency = -γ * (latency / median_latency)

---

### **7.2.3 Consistency Component**

Δscore_consistency = δ * (consistency_signal)

---

### **7.2.4 Safety and Policy Component**

Δscore_safety = λ * (safe_policy_compliance - violation_penalty)

---

### **7.2.5 Final Update**

new_score = old_score  
+ Δscore  
+ Δscore_validation  
+ Δscore_latency  
+ Δscore_consistency  
+ Δscore_safety

Scores clipped to range [0, 1].

---

## **7.3 Weighted Consensus Algorithm**

Each participating node or expert result `O_i` returns metadata such as:

* confidence c_i
* reputation r_i
* grounding / verification quality signals v_i

Compute:

weight_i = f( r_i, c_i, v_i )

Final output selected by:

Option A (Weighted Voting):

Select O_k where Σ weight_i(O_i == O_k) is max

Option B (Best Weighted Synthesis):

Select, merge, or revise the candidate set using an arbiter or synthesis stage informed by weight_i and divergence severity.

---
## **7.4 Consensus Engine Architecture (Protocol Layer)**

The Genius LLM v1 consensus system operates entirely at the application layer and is independent of GNUS blockchain consensus.

This layer governs:

* swarm inference coordination
* result aggregation
* verification and arbitration
* reputation-weighted selection
* Byzantine tolerance
* liveness guarantees

Unlike blockchain consensus, this is a **task-level deterministic weighted coordination system**, not a ledger agreement protocol.

---

### **7.4.1 Consensus Design Principles**

The system follows these principles:

1. **Fully Peer-to-Peer** — no mandatory permanent central coordinator.
2. **Requestor Node as Orchestrator** — the node initiating the request may act as the temporary router / planner.
3. **Reputation-Weighted Agreement** — nodes influence outcome proportionally to role-relevant performance history.
4. **Liveness over Perfection** — the system prioritizes bounded completion over infinite retry loops.
5. **Deterministic Finalization** — final output selection and attestation must be reproducible.
6. **Arbitration over flat voting when needed** — disagreements may be resolved through critique and synthesis rather than only majority selection.

---

### **7.4.2 Swarm Execution Flow**

1. Client submits request to a GNUS node.
2. That node becomes the **Requestor-Orchestrator**.
3. Orchestrator:
    - Selects candidate nodes based on:
        - Reputation score
        - Role or domain relevance
        - Latency history
        - Policy compatibility
    - Broadcasts task via libp2p.
4. Execution nodes:
    - Run Semantic Core or expert inference locally.
    - Apply local safety policy.
    - Sign response.
    - Return output + metadata.
5. Optional verifier, grounding, or arbiter participants:
    - Check candidate outputs.
    - Report contradictions, evidence alignment, or merge decisions.
6. Orchestrator:
    - Applies weighted consensus or arbiter-mediated synthesis.
    - Validates safety profile compliance.
    - Produces final response.

No permanent leader exists.  
Each request defines its own temporary orchestration context.

---

### **7.4.3 Consensus Message Types**

The consensus engine defines the following message types:

* **TASK_PROPOSAL**
    - Prompt
    - Routing metadata
    - Safety profile hash
    - Request ID
    - Requested role or domain

* **TASK_RESULT**
    - Output text or structured payload
    - Confidence
    - Latency
    - Safety flag
    - Node signature

* **VERIFICATION_RESULT**
    - Verification findings
    - Grounding or policy notes
    - Contradiction flags
    - Verifier signature

* **CONSENSUS_FINAL**
    - Selected or synthesized output
    - Weight breakdown
    - Reputation deltas
    - Signed by requestor

---

### **7.4.4 Liveness Model**

Consensus must terminate within bounded time.

Liveness rules:

* If sufficient valid responses arrive -> finalize.
* If insufficient quorum after timeout -> degrade to single-node or reduced-mode execution.
* If responses conflict heavily -> select highest-weight valid response or escalate to arbiter-mediated synthesis.

Timeout and quorum thresholds are tunable per execution mode.

---

### **7.4.5 Byzantine Tolerance**

This is a weighted stochastic agreement system.

Failure modes addressed:

* malicious output
* low-quality output
* latency manipulation
* non-response
* policy-incompatible output

Mitigations:

* reputation decay
* consistency penalties
* latency penalties
* verifier and grounding checks
* minimum history requirement before high influence

---

### **7.4.6 Reputation-Gated Participation**

Nodes with:

* Reputation < threshold
* Safety violations above limit
* High divergence rate
* Failed attestation history

May:

* Be excluded from routing pool
* Have reduced weight
* Be temporarily quarantined

This preserves swarm integrity without central enforcement.

---

### **7.4.7 Genesis Anchor Model**

The initial network state may include one or more bootstrap nodes with:

* Bootstrap reputation = 1.0
* Full participation rights

However:

* Reputation decays proportionally as network grows.
* New nodes can achieve equivalent weight over time.
* No permanent privilege is retained.

This ensures bootstrapping without long-term centralization.

[Previous: Model and Router](./03-model-and-router.md) | [Architecture Index](./INDEX.md) | [Next: Grounding and Retrieval](./05-grounding.md)
