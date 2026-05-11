# **3 System Architecture Overview**

Client API  
↓ Router / Planner Layer  
↓ Memory Governor + Grounding Selection  
↓ Execution Nodes      
├── Semantic Core      
├── Role-Based ELMs      
├── Domain-Specific ELMs      
└── Tool-Support / Verification Services  
↓ Verification / Arbitration / Synthesis  
↓ Reputation-Weighted Consensus  
↓ Grokipedia Grounding & Private Knowledge Validation  
↓ Final Response

---

# **4 GNUS Component Mapping**

## 4.1 Compute Layer

The Compute Layer handles the hardware-level execution and optimization of the Semantic Core and expert modules on GNUS nodes, ensuring high-throughput and energy-efficient inference in line with the system's primary goals.

* **MNN: Model runtime**  
  This serves as the optimized deep learning inference engine responsible for executing the Semantic Core and expert modules efficiently on the diverse hardware found across the GNUS network.
* **Vulkan / MoltenVK: GPU acceleration**  
  These components provide GPU acceleration for inference operations. Vulkan is the cross-platform standard, while MoltenVK specifically enables Vulkan compatibility on Apple platforms, ensuring wide hardware reach.
* **FP4 v3 codec: Weight compression**  
  This component manages weight compression, directly enabling efficient low-bit deployment of the Semantic Core and selected expert modules.
* **CUDA/Vulkan shaders: Tile-based decode & matmul**  
  These are leveraged for high-performance, optimized numerical operations, specifically for tile-based decode and matrix multiplication of compressed weights during runtime.

### 4.1.1 FP4 Design

The custom quantization uses the FP4 v3 codec, which is designed for minimal overhead and maximum efficiency. It operates using **64x64 macroblocks** with a **per-block scale**. The design includes an **activation-aware scale search** and ensures that compressed weights are **decoded in shared memory at inference time** for ultra-low latency execution.

The Semantic Core is expected to be the primary beneficiary of aggressive compression, while role-based and domain-specific experts may use different quantization tradeoffs depending on whether they optimize for breadth, control, verification quality, deterministic formatting, or workflow specialization.

---

## **4.2 Distributed Layer**

The **Distributed Layer** is fundamental to operating Genius LLM v1 as a decentralized cognitive system across GNUS nodes. It utilizes specialized technologies to manage communication, data transfer, memory convergence, and task coordination.

* **libp2p:** This is used for **task broadcast, distributed coordination, and result aggregation**. It handles propagation of execution plans from the orchestration layer to participating nodes and the subsequent collection of expert results for verification, arbitration, and reputation-weighted consensus.
* **IPFS-lite:** The system relies on IPFS-lite for **model and artifact distribution**, ensuring that the Semantic Core, expert modules, manifests, and supporting assets are efficiently available to participating nodes.
* **RocksDB:** Serves as the component for **local caching and structured memory support**. It is used for general-purpose local storage and for maintaining local copies of memory objects, indexes, and reputation data.
* **CRDTs:** These Conflict-free Replicated Data Types are critical for **reputation synchronization and memory convergence**. They are used to replicate selected state across the distributed network while preserving consistency under concurrent updates.
* **gRPC:** This functions as a primary **API and service interface**, providing the mechanism for external clients and internal services to interact with the system.

### **4.2.1 Layered Cognitive Stack**

The broader cognitive stack is organized into the following layers:

1. **Client and API Layer** — session lifecycle, authentication, request submission, policy attachment, and response delivery.
2. **Orchestration Layer** — router, planner, memory governor, execution mode selector, policy evaluator, and task decomposition logic.
3. **Expert Execution Layer** — Semantic Core, role-based ELMs, domain-specific ELMs, and local or distributed inference services.
4. **Consensus and Grounding Layer** — reputation-weighted consensus, verification, critique, arbitration, Grokipedia integration, and private knowledge grounding.
5. **Security and Tool Intermediary Layer** — dry-run, sanitization, permission checks, approval gates, and execution attestations.
6. **Memory Layer** — GAML-based structured memory, bridge blocks, facts, policies, retrieval pipelines, and CRDT-backed replication.
7. **Distributed Infrastructure Layer** — messaging, discovery, storage propagation, scheduling, health monitoring, and settlement integration.

---

## **4.3 Security Layer**

The **4.3 Security Layer** is designed to establish trust, ensure data integrity, and protect communication and execution boundaries across the decentralized network.

* **libsecp256k1: Node Identity**  
  This elliptic curve digital signature algorithm is foundational for establishing unique identities within the Genius LLM ecosystem. It is used to generate the cryptographic keys that uniquely identify GNUS nodes, which is a prerequisite for participation, attestation, and reputation-weighted coordination.
* **ed25519: Message Signing**  
  A high-speed, secure public-key signature system is employed for message signing across the network. This ensures the authenticity and integrity of inter-node communications, such as plan distribution, expert result submission, tool attestations, and finalization records.
* **OpenSSL: Secure Transport**  
  The system relies on OpenSSL to provide secure, encrypted transport layers (TLS/SSL) for network communication. This secures data in transit, protecting sensitive information and maintaining the confidentiality of communication between the Client API, orchestration services, and execution nodes.
* **wallet-core: Reputation and secure state storage**  
  This component is used for secure and robust storage of reputation-related data and other persistent trust state required by distributed task execution.
* **Tool Intermediary boundary:**  
  Secure agent execution requires a mandatory intermediary choke-point between expert reasoning and real-world side effects. This boundary enforces deterministic dry-runs, sanitization, capability checks, approvals, and tool attestations before any side effect is allowed.

### **4.3.1 Core Architectural Distinction**

The system is built around two main cognitive classes:

* **Semantic Core** — a broadly capable reasoning substrate responsible for general understanding, synthesis, and default response generation.
* **Expert Language Models (ELMs)** — narrower specialized units invoked when additional expertise, verification, structure, grounding, or action competence is required.

This distinction is foundational. GNUS.ai does not assume that every task should be solved by a single general-purpose model.

---

[Previous: Executive Summary](./01-executive-summary.md) | [Architecture Index](./INDEX.md) | [Next: Model and Router](./03-model-and-router.md)
