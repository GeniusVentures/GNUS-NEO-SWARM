# **Model and Router**
# **5 Model Architecture**

---

## **5.1 Semantic Core**

The Semantic Core serves as the central reasoning substrate for generating foundational responses within Genius LLM v1. It is optimized for high-throughput, distributed inference across the decentralized network and provides broad comprehension, synthesis, and fallback response generation when specialist escalation is not required.

### 5.1.1 Base Model

The Semantic Core is intentionally selected from high-performing, medium-sized model families, with candidate classes including efficient general-purpose backbones suitable for quantized distributed deployment. This choice supports the system's objective of distributed inference and modularity, contrasting with monolithic scaling.

### 5.1.2 Quantization

To achieve energy-efficient inference and minimize memory usage, the Semantic Core is heavily optimized using custom weight compression techniques:

* **FP4 v3 Macroblocks:** The model weights are quantized using the FP4 v3 codec, which operates via 64x64 macroblocks.
* **Scale Search:** Quantization involves a **32-step scale search** and is performed with a per-block scale.
* **Activation-Aware Tuning:** The system includes the capability for optional activation-aware tuning, and the weights are decoded in shared memory during inference time.

The Semantic Core runs efficiently on the **GNUS compute nodes** using the MNN model runtime and GPU acceleration via Vulkan / MoltenVK.

---

## **5.2 Expert Language Models (ELMs) and Specialist Modules**

The specialist execution layer is now better described as a set of **Expert Language Models (ELMs)** and supporting specialist modules rather than only a narrow set of fixed micro-models. This architecture promotes **specialization over monolithic scaling** by allowing the system to deploy targeted expertise for distinct reasoning roles and subject domains.

### 5.2.1 ELM Definition and Flexibility

An ELM is a specialized language-model-based expert optimized for a specific reasoning role, subject domain, operational function, or action-support task.

An ELM may be implemented as:

* a compact standalone SLM
* a distilled expert model
* an adapter-augmented expert on a shared backbone
* a constrained service exposing a language-model interface
* a secure expert reasoning module behind a policy boundary

### 5.2.2 Role-Based ELMs

Representative role-based ELMs include:

* **Planner ELM:** Interprets the task, estimates complexity, and recommends an execution path.
* **Primary Draft ELM:** Produces an initial answer quickly when a specialist draft is preferred over direct Semantic Core output.
* **Verifier ELM:** Checks correctness, consistency, and policy adherence.
* **Arbiter ELM:** Resolves conflicts between multiple drafts or critiques.
* **Refiner / Formatter ELM:** Improves clarity, structure, style, or schema compliance.
* **Grounding ELM:** Aligns claims with trusted public or private knowledge sources.
* **Tool-Support ELM:** Helps prepare tool calls and interpret tool results before intermediary enforcement.

### 5.2.3 Domain-Specific Experts

Representative domain-specific experts include:

* **Math Specialist / ELM:** Focused on numerical and structured mathematical reasoning.
* **Code Specialist:** Focused on source reasoning, implementation support, and development workflows.
* **Scientific Specialist:** Focused on scientific reasoning and evidence-heavy tasks.
* **Legal / Compliance Specialist:** Focused on regulated reasoning and policy-heavy domains.
* **Operations or Workflow Specialist:** Focused on tenant-specific procedures and internal execution patterns.
* **Customer Support Specialist:** Focused on support workflows and user-facing operational tasks.
* **Finance Specialist:** Focused on finance-heavy reasoning and structured analytical tasks.

### 5.2.4 Private ELMs

Organizations may deploy private ELMs trained or adapted on proprietary data, workflows, and response patterns. These private ELMs may run fully inside a tenant boundary, on local infrastructure, on permissioned GNUS nodes, or within restricted private or hybrid swarms.

### 5.2.5 ELM Invocation Patterns

ELMs may be invoked in several ways:

* **single-pass support** — one ELM supports the Semantic Core
* **sequential chain** — one ELM drafts, another verifies, another refines
* **parallel swarm participation** — multiple ELMs produce competing or complementary views
* **arbiter-mediated synthesis** — an Arbiter ELM resolves or merges distributed proposals

### 5.2.6 Legacy MVP Specialists

The earlier Grammar Specialist and Math Specialist remain compatible as concrete instances of the broader ELM architecture. In the updated model, grammar correction belongs naturally under refiner / formatter roles, while math remains one domain-specific specialist family.

---

# 6 Router Design

The Router Layer serves as the critical initial processing point for client requests, acting as the task orchestrator in the system's architecture. Its primary function is to intelligently route incoming tasks to the appropriate execution mode, Semantic Core path, ELM set, grounding path, memory path, and verification strategy.

## 6.1 Router and Planner Responsibilities

The orchestration path is responsible for:

* classifying task type and complexity
* deciding whether retrieval is required
* selecting execution mode
* selecting the Semantic Core and required ELMs
* deciding whether verification or arbitration is required
* determining whether private knowledge grounding is required
* deciding whether tenant-scoped or private memory should be loaded
* enforcing policy constraints
* determining latency, privacy, token, and spend budgets
* producing an execution graph for local or distributed completion

## 6.2 Initial MVP Router

The initial implementation relies on a **rule-based detection** system for rapid deployment and predictable routing behavior. This system analyzes the characteristics of the incoming prompt to determine the required execution path:

* **Numeric density -> Math Specialist / Verifier path:** Prompts containing a high density of numerical data or mathematical keywords are routed to a math-oriented specialist path, optionally followed by verification.
* **Code syntax -> Code Specialist path:** Queries identified as containing code syntax or complex programming logic are routed toward code-capable execution.
* **Grounding-sensitive request -> Grounding path:** Questions that require factual validation or trusted references trigger grounding retrieval and validation.
* **Formatting-sensitive request -> Refiner / Formatter path:** Requests that require structured or style-constrained output trigger formatting-aware expert support.
* **Low complexity -> Semantic Core only:** Simple or general-purpose prompts that require only foundational language understanding are routed exclusively to the Semantic Core.
* **High complexity / uncertainty -> multi-stage path:** Complex, ambiguous, or high-stakes prompts may trigger a planner, verifier, arbiter, or swarm-assisted execution path.

## 6.3 Future Router Evolution

The roadmap includes upgrading the router to a more sophisticated model-based system to enhance routing accuracy and performance. This future iteration can progress through multiple stages:

* **Heuristic MVP router:** fast rule-based triggers for numeric, code, formatting, grounding, tool, and workflow cues.
* **Lightweight classifier router:** a compact learned routing model trained on prompt embeddings, task outcomes, and execution traces.
* **Cognitive planner:** a planner-level expert capable of decomposing tasks into multi-step workflows involving reasoning, retrieval, tools, verification, arbitration, and private ELM selection.

* **Execution Awareness:** Future routing should incorporate latency budget, policy constraints, privacy mode, prior expert success, disagreement risk, and tenant boundary requirements.

---

[Previous: System Overview](./02-system-overview.md) | [Architecture Index](./INDEX.md) | [Next: Reputation and Consensus](./04-reputation-consensus.md)
