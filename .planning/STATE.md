---
gsd_state_version: 1.0
milestone: v1.1
milestone_name: ELM Training & Distillation Pipeline (gnus-poc)
status: planning
last_updated: "2026-05-27T20:10:07.770Z"
last_activity: 2026-05-27 — ROADMAP.md written
progress:
  total_phases: 7
  completed_phases: 1
  total_plans: 3
  completed_plans: 3
  percent: 14
---

# Project State

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-05-27)

**Core value:** Python POC pipeline for training and distilling Expert Language Models using DeepSeek v4 pro API as teacher
**Current focus:** Roadmap defined; ready for Phase 1 planning

## Current Position

Phase: 1 (Foundation & Bug Fixes) — COMPLETE
Plan: 3/3 complete
Status: Ready for Phase 2 planning
Last activity: 2026-05-27 — Phase 1 plans 01-01, 01-02, 01-03 executed

Progress: [███░░░░░░░░░░░░░░░░░░░] 14%

## Performance Metrics

**Velocity:**
- Total plans completed: 3
- Average duration: ~22 minutes/plan
- Total execution time: ~1.1 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-foundation-bug-fixes | 3 | 01:05 | 00:22 |

**Recent Trend:**
- Last 5 plans: 01-02 (15m), 01-01 (30m), 01-03 (20m)
- Trend: Steady — avg 22 min/plan

*Updated after each plan completion*

## Accumulated Context

### Decisions

- Teacher model: DeepSeek v4 pro API (not local GPU cluster) — fundamental architecture decision
- Target: `gnus-poc/` subdirectory only — Python POC, feeds into C++ engine Phase 4 later
- Existing assets: 5 trained MLX-LoRA specialists, FP4 pyramid code, Common Pile niche discovery
- Built on `docs/` strategic vision: dAMoE, FP4 quantization, teaching phase workflow
- 7-phase sequential roadmap: Foundation → Teacher API → Training → Eval → Distillation → Orchestration → FP4 Deploy
- DISTILL-03 (subspace extraction) is optional — research spike, may be deferred
- Phase 2 gated on teacher licensing decision (DeepSeek v4 pro API ToS compliance)
- 01-02: Use Path(__file__).resolve().parent convention for all project paths
- 01-02: PROJECT_ROOT = parent.parent for training/, parent.parent.parent for data/scripts/
- 01-01: Use HuggingFace AutoTokenizer for chat template (not mlx_lm) in tokenizer_utils.py
- 01-01: 3-phase skip logic: force-retrain → milestone file → metadata validation
- 01-01: TRAINING_STATUS.json with iters_completed for skip check
- 01-01: Metadata field validation (RuntimeError on Common Pile schema drift)
- 01-03: YAML config hierarchy: pipeline.yaml → specialist/*.yaml → experiments/*.yaml
- 01-03: code.yaml uses Qwen3-Coder base model (different from default)
- 01-03: ${DEEPSEEK_API_KEY} placeholder for Phase 3 env-var interpolation

### Pending Todos

None yet.

### Blockers/Concerns

- **Teacher licensing decision (BLOCKING Phase 2):** DeepSeek v4 pro API ToS may prohibit synthetic data generation for training derivative models. User must resolve before Phase 2 code is written. Fallback: open-source teacher (DeepSeek-V3, Llama 3.1, Qwen 3).
- **API cost explosion:** Hard dollar budget cap must be implemented with the API client — retrofitting after an incident is too late.
- **Apple Silicon OOM:** Qwen3-30B-A3B (~55GB bf16) + optimizer states push 64GB Mac Studio limits. qLoRA mitigation in Phase 3.
- **C++ `FP4Codec` alignment:** Python FP4 binary format must match C++ codec spec exactly. Round-trip test in Phase 7 is non-negotiable.
- **MNN adapter format conversion:** No off-the-shelf MLX-LoRA → MNN converter. Defer decision to Phase 7 planning.

## Deferred Items

Items from v1.0 C++ engine milestone (not in gnus-poc scope):

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| C++ Engine | Phase 1-8 (bug fixes through advanced cognitive) | Separate workstream | 2026-05-27 |

## Session Continuity

Last session: 2026-05-27
Stopped at: Completed Phase 1 (3/3 plans) — Foundation & Bug Fixes
Resume file: `.planning/phases/01-foundation-bug-fixes/01-03-SUMMARY.md`
