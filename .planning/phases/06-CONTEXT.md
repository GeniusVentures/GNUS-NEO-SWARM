# Phase 6: Orchestration & Pipeline Unification — Context

**Gathered:** 2026-05-27 | **Status:** Ready

## Phase Boundary

Single-command DAG runner tying all pipeline stages together with checkpoint detection and CLI entry point.

**In scope:** ORCH-01 (PipelineRunner), ORCH-02 (CLI entry point)
**Decisions:** Sequential stage execution, checkpoint via artifact existence checks, `orchestrate.py --niche --from-stage --config` CLI
