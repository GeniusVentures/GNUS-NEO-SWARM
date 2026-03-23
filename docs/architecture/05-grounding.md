# **05. Grounding and Retrieval**

[Previous: 04 Reputation and Consensus](./04-reputation-consensus.md) | [Architecture Index](./INDEX.md) | [Next: 06 Agentic Memory Layer](./06-agentic-memory-layer.md)

---

# **8\. Grokipedia Integration**

---

## **8.1 Grokipedia Role**

Grokipedia replaces Wikipedia.

Functions:

* Structured knowledge retrieval.
* Trusted grounding layer.
* Reduces hallucinations.

---

## **8.2 Retrieval Pipeline**

1. Query embedding.
2. Search Grokipedia index.
3. Inject top-k structured facts into prompt.
4. Tag injected context for traceability.

---

## **8.3 Validation Layer**

After generation:

* Check factual claims against Grokipedia.
* If contradiction detected:
    * Lower node consistency score.
    * Trigger regeneration with enforced grounding.

---

## **8.4 Extended Grounding Memory**

The GNUS Agentic Memory Layer (GAML v1) extends the grounding architecture with structured long-term memory and distributed retrieval.

* [Read GAML v1 in the architecture set](./06-agentic-memory-layer.md)

---

[Previous: 04 Reputation and Consensus](./04-reputation-consensus.md) | [Architecture Index](./INDEX.md) | [Next: 06 Agentic Memory Layer](./06-agentic-memory-layer.md)

