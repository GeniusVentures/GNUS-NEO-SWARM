# **02. System Overview**

[Previous: 01 Executive Summary](./01-executive-summary.md) | [Architecture Index](./INDEX.md) | [Next: 03 Model and Router](./03-model-and-router.md)

---

# **3\. System Architecture Overview**

Client API  
↓ Router Layer  
↓ Task Broadcast (libp2p)  
↓ Execution Nodes      
├── Core LLM (FP4 v3)      
├── Grammar Specialist      
├── Math Specialist      
└── Future Modules  
↓ Results Aggregation  
↓ Reputation-Weighted Consensus  
↓ Grokipedia Grounding & Validation  
↓ Final Response

---

# **4\. GNUS Component Mapping**

## 4.1 Compute Layer

## The Compute Layer handles the hardware-level execution and optimization of the models on the GNUS nodes, ensuring high-throughput and energy-efficient inference, in line with the system's primary goals.

* **MNN: Model runtime**  
  This serves as the optimized deep learning inference engine responsible for executing the Core LLM and Specialist Modules efficiently on the diverse hardware found across the GNUS network.
* **Vulkan / MoltenVK: GPU acceleration**  
  These components provide GPU acceleration for inference operations. Vulkan is the cross-platform standard, while MoltenVK specifically enables Vulkan compatibility on Apple platforms, ensuring wide hardware reach.
* **FP4 v3 codec: Weight compression**  
  This component manages weight compression, directly enabling the system's objective of using an FP4 v3 quantized core model for energy-efficient inference.
* **CUDA/Vulkan shaders: Tile-based decode & matmul**  
  These are leveraged for high-performance, optimized numerical operations, specifically for tile-based decode and matrix multiplication (matmul) of the compressed weights during runtime.

### FP4 Design

## The custom quantization uses the FP4 v3 codec, which is designed for minimal overhead and maximum efficiency. It operates using **64x64 macroblocks** with a **per-block scale**. The design includes an **Activation-aware scale search** and ensures that the compressed weights are **decoded in shared memory at inference time** for ultra-low latency execution.

---

## **4.2 Distributed Layer**

The **Distributed Layer** is fundamental to operating Genius LLM v1 as a decentralized system across GNUS nodes. It utilizes specialized technologies to manage communication, data transfer, and state consistency.

* **libp2p:** This is used for **Task broadcast & result aggregation**. It handles the propagation of tasks from the Router Layer to the Execution Nodes and the subsequent collection of results for the Reputation-Weighted Consensus process.
* **IPFS-lite:** The system relies on IPFS-lite for **Model distribution**, ensuring that the Core LLM and Specialist Modules are efficiently available to all participating nodes.
* **RocksDB:** Serves as the component for **Local caching**. It is used for general-purpose local storage and specifically for maintaining local copies of the Reputation Data.
* **CRDTs:** These Conflict-free Replicated Data Types are critical for **Reputation synchronization**. They are used to replicate the reputation state across the distributed network, ensuring concurrent updates remain consistent.
* **gRPC:** This functions as the primary **API interface**, providing the mechanism for external clients to interact with the system.

---

## **4.3 Security Layer**

The **4.3 Security Layer** is designed to establish trust, ensure data integrity, and protect communication channels across the decentralized network, utilizing established cryptographic primitives and secure storage methods.

* **libsecp256k1: Node Identity**  
  This elliptic curve digital signature algorithm is foundational for establishing unique identities within the Genius LLM v1 ecosystem. It is used to generate the cryptographic keys that uniquely identify each GNUS node, which is a prerequisite for both participation and the integrity of the Reputation-Weighted Consensus system.
* **ed25519: Message Signing**  
  A high-speed, secure public-key signature system is employed for message signing across the network. This ensures the authenticity and integrity of all inter-node communications, such as task broadcasts and result submissions, preventing tampering and providing non-repudiation proof that a specific node generated the message.
* **OpenSSL: Secure Transport**  
  The system relies on OpenSSL to provide secure, encrypted transport layers (TLS/SSL) for all network communication. This secures data in transit, protecting sensitive information and maintaining the confidentiality of communication between the Client API, the Router Layer, and the Execution Nodes.
* **wallet-core: Reputation Storage**  
  This component is used for the secure and robust storage of reputation data. It provides the necessary abstraction for managing the persistent storage of node-specific reputation metrics (e.g., `Global_score`, `Latency_score`, `Consistency_score`) which are crucial inputs for the Weighted Consensus Algorithm.

---

[Previous: 01 Executive Summary](./01-executive-summary.md) | [Architecture Index](./INDEX.md) | [Next: 03 Model and Router](./03-model-and-router.md)

