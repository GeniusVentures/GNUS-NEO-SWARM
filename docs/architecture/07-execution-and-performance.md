# **9. Execution and Performance - Execution Modes and Performance Targets**

## **9.1 Mode 1 — Single Node**

* Semantic Core only.
* Fast.
* Minimal overhead.

---

## **9.2 Mode 2 — ELM-Assisted Mode**

* Semantic Core + one or more role-based or domain-specific experts.
* Typically sequential or lightly parallel execution.
* Used when specialist assistance improves quality without full swarm overhead.

---

## **9.3 Mode 3 — Swarm Mode**

* Multiple nodes execute.
* Weighted consensus or arbiter-mediated synthesis.
* Reputation-based selection.

---

## **9.4 Mode 4 — Agent Mode**

* Multi-step execution involving memory, grounding, verification, and optional tool use.
* Secure tool path enforced through the Tool Intermediary.
* Used for higher-complexity workflows.

---

## **9.5 Execution Strategy Principles**

* **Local-first, distributed-second:** Execute locally when possible and escalate only when justified.
* **Small effective cognitive sets:** Select the smallest effective set of ELMs and services rather than activating a large swarm by default.
* **Roles over raw scale:** Prefer assigning the right expert role over scaling one model indiscriminately.

---

# **10. Performance Targets**

Metric

Target

Tokens/sec

≥ INT4 baseline where comparable

Memory usage

≤ practical low-bit deployment envelope

Grounded quality

≥ baseline single-model factual reliability

Verification / formatting quality

measurable improvement

Multi-node scaling

near-linear up to initial swarm targets where network conditions permit

Tool safety overhead

bounded and separately reported from inference latency

Customization efficiency

choose the lowest-cost path among retrieval, memory, private ELM invocation, and swarm consensus that still satisfies quality and policy requirements

---

[Previous: Agentic Memory Layer (GAML v1)](./06-agentic-memory-layer.md) | [Architecture Index](./INDEX.md) | [Next: Roadmap and Risks](./08-roadmap-and-risks.md)
