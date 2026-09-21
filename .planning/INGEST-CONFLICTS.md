## Conflict Detection Report

Generated: 2026-07-19 | Mode: merge (re-ingest of 14 changed docs post-d100f68) | Precedence: ADR > SPEC > PRD > DOC

---

### BLOCKERS (0)

No locked decisions (ADRs) in ingest set. No existing locked decisions in CONTEXT.md. No LOCKED-vs-LOCKED contradictions.

Two navigational cross-ref cycles detected between documentation pairs (auto-resolved as non-blocking structural artifacts):
  Found: sgfp4-format.md <-> model-and-router.md (bidirectional "see also" links)
  Found: speculative-decoding-and-vtg.md <-> frozen-mtp-and-vtg.md (bidirectional companion doc links)
  Rationale: These are navigational cross-references in the linear architecture document series, not semantic dependency cycles. Per-document extraction is unaffected. Consistent with prior ingest precedent (2026-07-18, 15 similar navigational cycles auto-resolved).

---

### WARNINGS (2)

[WARNING] Adapter-based vs standalone specialist models — RESOLVED (2026-08-17 annotation)
  Source: docs/architecture/distributed-swarm-thinking-context.md (not in the 14 changed docs; content unchanged)
  Found: Section describing both adapter-based ELMs (fine-tuning a shared base) and standalone specialist models
  Impact: Implementation strategy choice affects model loading, memory usage, and inference batching
  Resolution: Resolved for the poc workstream by poc/PROJECT.md Key Decision 1
    (2026-06-18): specialists are LoRA adapters on a shared Qwen3-30B-A3B backbone.
    Implemented across poc Phases 1-2 (MLX LoRA training, adapter artifacts).
    neoswarm Phase 7 (ELMs + Router) completed with the same adapter-based design.
  Original note: Defer to neoswarm Phase 7 (ELM Router) for benchmark-driven resolution.

[WARNING] Undefined quantization policy per specialist role — RESOLVED (2026-08-17 annotation)
  Source: docs/architecture/distributed-swarm-thinking-context.md (not in the 14 changed docs; content unchanged)
  Found: Section mentioning per-specialist quantization without defining the mapping
  Impact: Without per-role quantization policy, SGFP4 processor configuration is underspecified for ELM specialists
  Resolution: Resolved by poc/PROJECT.md Key Decision 2 (2026-06-18): per-specialist
    quantization policy — FP4_AFFINE for accuracy-critical specialists, T158_AFFINE
    for latency-tolerant, adaptive per-block mode selection; configurable per
    specialist in config/specialists/<niche>.yaml. Implemented in poc Phase 3
    (SGFP4 v2, D-01..D-10 in 03-CONTEXT.md; UAT 97/97 passing).
  Original note: Define quantization levels per ELM role type in Phase 4 (SGProcessing Integration).

---

### INFO (6)

[INFO] 14 changed docs re-ingested with fresh classifications (commit d100f68, 2026-07-19)
  Source: 38 classification files in .planning/intel/classifications/ — deduplicated to 14 distinct source documents with new classifications taking precedence over old
  Note: 9 SPECs + 5 DOCs in the changed set. Old classifications for unchanged docs preserved.
  Details: See .planning/intel/SYNTHESIS.md for final type breakdown.

[INFO] 4 documents reclassified in this ingest
  eggroll-swarm-retraining: DOC -> SPEC (defines concrete training primitive, fitness packet schema, worker execution model)
  sgfp4-format: DOC -> SPEC (was "Ultra FP4 Format" DOC, now "SGFP4 Adaptive Quantization Format" SPEC with formal container layout, mode flags, decode procedure)
  forecast-driven-cognition: DOC -> SPEC (defines ACE/CES component interfaces, forecast graph, preparation policy)
  frozen-mtp-and-vtg: DOC -> SPEC (defines technical parameters: MTP head budget 5-50MB, speculative depth 1-4 tokens, commitment rule)
  epistemic-arbitration: SPEC -> DOC (reclassified; technical sketches are illustrative, not contractual)

[INFO] 8 new documents added to neoswarm intel (not present in prior 2026-06-18 ingest)
  execution-integrity-system, openai-compatible-api-router, speculative-decoding-and-vtg, frozen-mtp-and-vtg, objective-memory-vtg, forecast-driven-cognition, agent-module-development-inventory, local-cognitive-second-brain, capability-system, README, sloth-integration
  Note: Previous neoswarm ingest covered 16 architecture docs. Current ingest covers 27.

[INFO] Architecture scope broader than neoswarm
  Note: The 27 ingested architecture docs describe the full Genius Cognitive System (GCS). GNUS-NEO-SWARM implements the NEO Swarm inference engine subset. Newly added docs cover EIS (execution integrity), Objective Memory/VTG, Speculative Decoding, Forecast-Driven Cognition, Capability System, and Local Cognitive Second Brain — all GCS-level subsystems that may extend beyond neoswarm's immediate scope.

[INFO] 10 SPEC-classified docs contain normative technical detail
  Note: reputation-consensus, secure-agent-architecture, sgfp4-format, eggroll-swarm-retraining, speculative-decoding-and-vtg, frozen-mtp-and-vtg, objective-memory-vtg, forecast-driven-cognition, execution-integrity-system, openai-compatible-api-router are SPEC-classified. Their constraints are captured in .planning/intel/constraints.md.

[INFO] No ADRs or PRDs in ingest set
  Note: All 27 docs are DOC (17) or SPEC (10). No locked decisions (ADR) or formal product requirements (PRD) were found. MERGE routing will derive phase-level requirements from DOC/SPEC content using lower-precedence extraction.
