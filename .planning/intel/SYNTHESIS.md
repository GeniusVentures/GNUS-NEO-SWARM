# Synthesis Summary

Generated: 2026-07-19 | Mode: merge (re-ingest of 14 changed docs post-d100f68) | Precedence: ADR > SPEC > PRD > DOC

## Ingest Overview

Re-ingest of 14 architecture documents changed in commit d100f68 (2026-07-19, 798 insertions/798 deletions across 16 files). Fresh classifications applied to the 14 changed substantive files, producing 9 SPECs and 5 DOCs. Old classifications retained for 13 unchanged documents. Total document set: 27.

The architecture documents describe the GeniusCognitiveSystem (GCS) -- a distributed, modular, reputation-weighted cognitive platform built on GNUS.ai infrastructure. GNUS-NEO-SWARM implements the NEO Swarm inference engine subset.

## Doc Counts by Type

| Type | Count | Confidence |
|------|-------|-----------|
| ADR | 0 | -- |
| SPEC | 10 | high (5), medium (5) |
| PRD | 0 | -- |
| DOC | 17 | high (12), medium (5) |
| UNKNOWN | 0 | -- |

### SPECs (10)

| # | Document | Confidence | Chapter |
|---|----------|-----------|---------|
| SPEC-01 | Reputation-Based Consensus System | medium | 7 |
| SPEC-02 | Secure Agent Architecture | high | 18 |
| SPEC-03 | SGFP4 Adaptive Quantization Format | high | 22 |
| SPEC-04 | EGGROLL Swarm Retraining Architecture | medium | -- |
| SPEC-05 | Speculative Decoding and VTG Candidate Scheduling | high | 24 |
| SPEC-06 | Frozen Micro-MTP and VTG Edge Inference | medium | 25 |
| SPEC-07 | Objective Memory and Verified Transition Graph | medium | 23 |
| SPEC-08 | Forecast-Driven Cognition and Predictive Prefetching | medium | 28 |
| SPEC-09 | Execution Integrity System (EIS) | high | 29 |
| SPEC-10 | OpenAI-Compatible API Router and GCS Job Queue | high | 26 |

### DOCs (17)

13 previously classified (unchanged) + 3 new + 1 reclassified:
- Executive Summary (1), System Overview (2), Model and Router (5), Grounding (8), Agentic Memory Layer (8.4), Execution and Performance (9), Roadmap and Risks (11-12), Future and Positioning, AI Safety (15), Distributed Swarm Thinking Context (16), Targeted Retraining (updated), Epistemic Arbitration (reclassified DOC from SPEC)
- NEW: Agent and Module Development Inventory (31), GCS Capability System (30), Local Cognitive Second Brain Mode (27)
- README (navigation index), Sloth Integration (exploratory)

## Decisions

- **Locked:** 0 (no ADR-classified documents in the ingest set)
- **Proposed:** 0

## Requirements

- **Total extracted:** 0 (no PRD-classified documents in the ingest set)

## Constraints

- **Total extracted:** 10 SPEC documents (up from 2 in prior ingest)
- **By type:**
  - api-contract / protocol: 10 (all SPECs define technical contracts, schemas, or protocols)
  - nfr: 2 (SPEC-02 includes security targets and performance bounds; SPEC-09 includes determinism constraints)
- **New constraints since 2026-06-18 ingest:**
  - SGFP4 container format with dual-mode FP4/ternary quantization (SPEC-03)
  - EGGROLL fitness packet schema and training primitive (SPEC-04)
  - Micro-speculation architecture with local drafters and VTG integration (SPEC-05)
  - Frozen Micro-MTP head budget (5-50MB) and commitment rules (SPEC-06)
  - VTG transition edge schema and state identity hashing (SPEC-07)
  - Forecast graph, ACE, CES component interfaces (SPEC-08)
  - Execution contracts with determinism classes A/B/C, checkpoint-band matching, teacher-forced spot checks (SPEC-09)
  - OpenAI-compatible API router with GCS job queue, CRDT keyspace, metering hooks (SPEC-10)

## Context Topics

- **Total topics extracted:** 17 DOC documents
- **Major topic areas:**
  - System identity, objectives, strategic positioning
  - System architecture overview (7-layer model, compute/distributed/security layers)
  - Model and router design (Semantic Core, ELMs, rule-based router)
  - Execution modes (4 modes) and performance targets
  - Grounding and retrieval (Grokipedia, private grounding, validation)
  - Agentic Memory Layer (GAML v1) -- structured memory model
  - Distributed Swarm Thinking Context -- specialist taxonomy, reasoning traces
  - Execution roadmap (4 phases) and risk analysis
  - Future compatibility and strategic positioning
  - AI safety philosophy (4-layer model)
  - Targeted Retraining and HCTS architecture (updated)
  - Epistemic Arbitration and Cognitive OS (reclassified DOC)
  - Agent and Module Development Inventory -- GCS-wide workstream catalog (NEW)
  - GCS Capability System -- protocol-neutral capability/connector model (NEW)
  - Local Cognitive Second Brain Mode -- private local reasoning (NEW)
  - Architecture documentation index (README)
  - Sloth integration exploration

## Conflicts

- **Blockers:** 0
- **Warnings (competing variants):** 2 (same as prior ingest, still unresolved)
  1. Adapter-based vs standalone specialist models (distributed-swarm-thinking-context.md, not updated)
  2. Undefined quantization policy per specialist role (distributed-swarm-thinking-context.md, not updated)
- **Auto-resolved:** 6 INFO items (doc reclassifications, navigational cycle resolution, scope note)

## Reclassification Summary (2026-07-19)

4 documents changed type in this ingest:
- eggroll-swarm-retraining: DOC -> SPEC (defines formal training primitive, fitness packet JSON schema, worker execution model)
- sgfp4-format: DOC -> SPEC (was "Ultra FP4 Format"; now formal container layout, mode flags, decode procedure)
- forecast-driven-cognition: DOC -> SPEC (defines ACE/CES interfaces, forecast graph, preparation policy)
- frozen-mtp-and-vtg: DOC -> SPEC (defines MTP head budget 5-50MB, speculative depth 1-4 tokens, commitment rules)
- epistemic-arbitration: SPEC -> DOC (reclassified; technical details are illustrative not contractual)

## Conflict Report

Full detail: `.planning/INGEST-CONFLICTS.md`

## Status

STATUS: AWAITING USER -- 2 competing-variant warnings still need resolution:
1. Choose adapter-based vs standalone model path for ELM specialists
2. Define quantization policy per specialist role

These warnings originate from distributed-swarm-thinking-context.md which was not among the 14 docs updated in this re-ingest. The new SGFP4 format spec (SPEC-03) defines the container format but does not address per-role policy.

## Intel Files

- Decisions: `.planning/intel/decisions.md` (empty -- no ADRs)
- Requirements: `.planning/intel/requirements.md` (empty -- no PRDs)
- Constraints: `.planning/intel/constraints.md` (10 SPECs extracted)
- Context: `.planning/intel/context.md` (17 DOCs extracted, organized by topic)
- This summary: `.planning/intel/SYNTHESIS.md`
