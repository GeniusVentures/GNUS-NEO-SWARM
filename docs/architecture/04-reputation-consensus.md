
# **7 Reputation-Based Consensus System**

This is the core differentiator.

---

## **7.1 Reputation Data Model**

Each node maintains:

```json
Node {  
  Identity_key  
  Global_score  
  Math_score  
  Grammar_score  
  Latency_score  
  Consistency_score  
}
```

Stored via:

* wallet-core
* RocksDB
* CRDT replicated state

---

## **7.2 Reputation Update Formula**

After each task:

### **7.2.1 Accuracy Component**

If ground truth available:

Δscore = α * (accuracy - baseline_accuracy)

If no ground truth:

Δscore = β * (agreement_with_weighted_consensus)

---

### **7.2.2 Latency Component**

Δscore_latency = -γ * (latency / median_latency)

---

### **7.2.3 Consistency Component**

Δscore_consistency = δ * (perplexity_inverse_normalized)

---

### **7.2.4 Final Update**

new_score = old_score  
+ Δscore  
+ Δscore_latency  
+ Δscore_consistency

Scores clipped to range [0, 1].

---

## **7.3 Weighted Consensus Algorithm**

Each node i returns output O_i with:

* perplexity p_i
* reputation r_i

Compute:

weight_i = r_i / (p_i + ε)

Final output selected by:

Option A (Weighted Voting):

Select O_k where Σ weight_i(O_i == O_k) is max

Option B (Best Weighted Score):

Select O_i maximizing weight_i

---
## **7.4 Consensus Engine Architecture (Protocol Layer)**

The Genius LLM v1 consensus system operates entirely at the application layer and is independent of GNUS blockchain consensus.

This layer governs:

* Swarm inference coordination
* Result aggregation
* Reputation-weighted selection
* Byzantine tolerance
* Liveness guarantees

Unlike blockchain consensus, this is a **task-level deterministic weighted quorum system**, not a ledger agreement protocol.

---

### **7.4.1 Consensus Design Principles**

The system follows these principles:

1. **Fully Peer-to-Peer** — no gateway, no central coordinator.
2. **Requestor Node as Orchestrator** — the node initiating the request acts as the temporary router.
3. **Reputation-Weighted Agreement** — nodes influence outcome proportionally to performance history.
4. **Liveness over Perfection** — the system prioritizes completion over infinite retry loops.
5. **Deterministic Finalization** — final output selection must be reproducible.

---

### **7.4.2 Swarm Execution Flow**

1. Client submits request to a GNUS node.
2. That node becomes the **Requestor-Orchestrator**.
3. Orchestrator:
    - Selects candidate nodes based on:
        - Reputation score
        - Specialist relevance
        - Latency history
    - Broadcasts task via libp2p.
4. Execution nodes:
    - Run inference locally.
    - Apply local safety policy.
    - Sign response.
    - Return output + metadata.
5. Orchestrator:
    - Applies weighted consensus algorithm.
    - Validates safety profile compliance.
    - Produces final response.

No permanent leader exists.  
Each request defines its own temporary orchestration context.

---

### **7.4.3 Consensus Message Types**

The consensus engine defines the following message types:

* **TASK_PROPOSAL**
    - Prompt
    - Specialist routing metadata
    - Safety profile hash
    - Request ID

* **TASK_RESULT**
    - Output text
    - Perplexity
    - Latency
    - Safety flag
    - Node signature

* **CONSENSUS_FINAL**
    - Selected output
    - Weight breakdown
    - Reputation deltas
    - Signed by requestor

---

### **7.4.4 Liveness Model**

Consensus must terminate within bounded time.

Liveness rules:

* If quorum of ≥ 2 nodes responds → finalize.
* If insufficient quorum after timeout → degrade to single-node mode.
* If responses conflict heavily → select highest weighted valid response.

Timeout and quorum thresholds are tunable per execution mode.

---

### **7.4.5 Byzantine Tolerance**

This is a weighted stochastic agreement system.

Failure modes addressed:

* Malicious output
* Low-quality output
* Latency manipulation
* Non-response

Mitigations:

* Reputation decay
* Consistency penalties
* Latency penalties
* Minimum history requirement before high influence

System is tolerant of:

* ≤ 33% malicious weighted reputation under default thresholds.

---

### **7.4.6 Reputation-Gated Participation**

Nodes with:

* Reputation < threshold
* Safety violations above limit
* High divergence rate

May:

* Be excluded from routing pool
* Have reduced weight
* Be temporarily quarantined

This preserves swarm integrity without central enforcement.

---

### **7.4.7 Genesis Anchor Model**

The initial network state includes a Genesis node (or nodes) with:

* Bootstrap reputation = 1.0
* Full participation rights

However:

* Reputation decays proportionally as network grows.
* New nodes can achieve equivalent weight over time.
* No permanent privilege is retained.

This ensures bootstrapping without long-term centralization.

[Previous: Model and Router](./03-model-and-router.md) | [Architecture Index](./INDEX.md) | [Next: Grounding and Retrieval](./05-grounding.md)

