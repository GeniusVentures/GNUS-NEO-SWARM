## Conflict Detection Report

Generated: 2026-07-18 | Mode: merge | Precedence: ADR > SPEC > PRD > DOC

---

### BLOCKERS (0)

All 15 potential blockers from the prior poc ingest were navigational cross-ref cycles (bidirectional "previous/next" links in the linear document series). These are structural artifacts of the document format, not semantic dependency cycles. No actual content contradictions exist between ingested architecture docs and the existing neoswarm planning artifacts.

Navigational cycles between doc pairs (all auto-resolved as non-blocking):
- 01-executive-summary <-> 02-system-overview
- 02-system-overview <-> 03-model-and-router
- 02-system-overview <-> 16-sgfp4-format
- 03-model-and-router <-> 04-reputation-consensus
- 03-model-and-router <-> 16-sgfp4-format
- 04-reputation-consensus <-> 05-model-and-router
- 05-model-and-router <-> 06-grounding
- 06-grounding <-> 07-execution-and-performance
- 07-execution-and-performance <-> 08-roadmap-and-risks
- 09-agentic-memory-layer <-> 10-distributed-swarm-thinking-context
- 11-future-and-positioning <-> 12-ai-safety
- 15-secure-agent-architecture <-> 16-sgfp4-format
- 16-sgfp4-format <-> 17-eggroll-swarm-retraining
- 18-epistemic-arbitration <-> 19-objective-memory-vtg
- 20-execution-integrity-system <-> 21-forecast-driven-cognition

---

### WARNINGS (2)

[WARNING] Adapter-based vs standalone specialist models
  Found: distributed-swarm-thinking-context.md Section 16.15 describes both adapter-based ELMs (fine-tuning a shared base) and standalone specialist models
  Impact: Implementation strategy choice affects model loading, memory usage, and inference batching
  → Both paths are viable. The architecture doc does not mandate one over the other. Defer decision to neoswarm Phase 7 (ELM Router) where it will be resolved with benchmarks.

[WARNING] Undefined quantization policy per specialist role
  Found: distributed-swarm-thinking-context.md Section 16.14.5 mentions per-specialist quantization but does not define the mapping
  Impact: Without per-role quantization policy, FP4_ULTRA processor configuration is underspecified
  → Define quantization levels per ELM role type (Grammar=Q4, Math=Q8, etc.) in Phase 4 (SGProcessing Integration)

---

### INFO (3)

[INFO] Architecture scope broader than neoswarm
  Note: The 27 ingested architecture docs describe the full Genius Cognitive System (GCS). GNUS-NEO-SWARM implements the NEO Swarm inference engine subset. Several described capabilities (GAML Cognitive Memory, Capability System Connectors, Local Cognitive Second Brain) span multiple submodules. These are captured as future-phase context but do not require immediate neoswarm planning.

[INFO] SPEC-classified docs (9) contain normative technical detail
  Note: reputation-consensus, secure-agent-architecture, sgfp4-format, execution-integrity-system, eggroll-swarm-retraining, epistemic-arbitration, objective-memory-vtg, speculative-decoding, and openai-compatible-api-router are SPEC-classified. Their constraints are captured in .planning/intel/constraints.md.

[INFO] No ADRs or PRDs in ingest set
  Note: All 27 docs are DOC (18) or SPEC (9). No locked decisions (ADR) or formal product requirements (PRD) were found. MERGE routing will derive phase-level requirements from DOC/SPEC content using lower-precedence extraction.
