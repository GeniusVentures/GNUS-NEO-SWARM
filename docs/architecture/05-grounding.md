# **8 Grounding and Retrieval**

---

## **8.1 Grokipedia Role**

Grokipedia acts as a primary public grounding layer.

Functions:

* Structured knowledge retrieval.
* Trusted grounding layer.
* Reduces hallucinations.
* Supports post-generation validation.
* Strengthens reputation scoring by rewarding grounded outputs.

---

## **8.2 Retrieval Pipeline**

1. Query analysis.
2. Search Grokipedia index and other approved public sources.
3. Inject top-k structured facts or references into the reasoning context.
4. Tag injected context for traceability.
5. Pass grounding evidence to generation, verification, or arbitration stages as required.

---

## **8.3 Validation Layer**

After generation:

* Check factual claims against Grokipedia or other approved grounding substrates.
* If contradiction detected:
    * Lower grounding or consistency score.
    * Trigger verification, correction, or regeneration with enforced grounding.

---

## **8.4 Private Knowledge Grounding**

The grounding architecture also supports private knowledge retrieval for enterprise or tenant-specific deployments.

Private grounding may include:

* internal documents
* SOPs
* support playbooks
* CRM exports
* internal wikis
* contracts
* product catalogs
* ticket histories
* workflow artifacts
* structured databases and knowledge graphs

This allows the system to answer using tenant-specific knowledge without requiring immediate model retraining.

---

## **8.5 Grounding Modes**

The architecture supports:

* **public grounding**
* **private tenant grounding**
* **hybrid grounding**, combining trusted public and private sources

Grounding may be invoked during draft generation, verification, or arbiter-mediated synthesis depending on task risk and complexity.

---

## **8.6 Grounding as an Expert Role**

Grounding can be deployed either as:

* a dedicated **Grounding ELM**
* a grounding service invoked only when needed

This keeps the system efficient while preserving high-integrity answer paths.

---

## **8.7 Why Retrieval Is Not Enough by Itself**

Retrieval-grounded reasoning is ideal for rapidly changing knowledge and traceable factual recall, but it does not fully replace adaptation.

Retrieval helps the system know **what** information to use.
It does not always teach the system **how** to reason, format, triage, or act in a tenant-specific workflow.

That is why retrieval, structured memory, and private ELM adaptation should be treated as complementary mechanisms.

---

### **8.7.1 Extended Grounding Memory**

The GNUS Agentic Memory Layer (GAML v1) extends the grounding architecture with structured long-term memory and distributed retrieval.

* [Read GAML v1 in the architecture set](./06-agentic-memory-layer.md)

---

[Previous: Reputation and Consensus](./04-reputation-consensus.md) | [Architecture Index](./INDEX.md) | [Next: Agentic Memory Layer](./06-agentic-memory-layer.md)
