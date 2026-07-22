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

[WARNING] Adapter-based vs standalone specialist models — STILL UNRESOLVED
  Source: docs/architecture/distributed-swarm-thinking-context.md (not in the 14 changed docs; content unchanged)
  Found: Section describing both adapter-based ELMs (fine-tuning a shared base) and standalone specialist models
  Impact: Implementation strategy choice affects model loading, memory usage, and inference batching
  Status: This doc was not part of the d100f68 update. The architecture does not mandate one path over the other.
  -> Defer to neoswarm Phase 7 (ELM Router) for benchmark-driven resolution.
  -> Suggested: Both paths remain viable; choose based on per-specialist benchmarks.

[WARNING] Undefined quantization policy per specialist role — STILL UNRESOLVED
  Source: docs/architecture/distributed-swarm-thinking-context.md (not in the 14 changed docs; content unchanged)
  Found: Section mentioning per-specialist quantization without defining the mapping
  Impact: Without per-role quantization policy, SGFP4 processor configuration is underspecified for ELM specialists
  Status: This doc was not part of the d100f68 update. The warning predates the SGFP4 format renaming (from FP4 Ultra).
  -> Define quantization levels per ELM role type (Grammar=Q4, Math=Q8, etc.) in Phase 4 (SGProcessing Integration).
  -> The updated SGFP4 format spec (constraints.md SPEC-03) now defines dual-mode FP4_AFFINE/T158_AFFINE but does not address per-role policy.

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
