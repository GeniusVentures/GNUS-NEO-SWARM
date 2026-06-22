---
title: PTDS v4 Unsloth Integration Strategy
date: 2026-06-21
context: Explored during /gsd:explore after Phase 2 shipped
---

# Decision: Keep MLX, Add Unsloth as Parallel Backend

**Decision:** gnus-poc retains MLX (Apple Silicon) as active training runtime. Unsloth becomes a parallel training backend following the Phase 1 multi-backend pattern (OpenAI/Anthropic for teachers → MLX/Unsloth for training).

**Rationale:**
- MLX is working, tested (70 tests), and shipped — dropping it would lose proven functionality
- Unsloth per PTDS v4 §5.1 is the long-term target, but requires new GPU infra (CUDA, bitsandbytes)
- PTDS v4 3-tier architecture (Teacher→Parent→Specialist) is a bigger change than a backend swap — needs its own phase
- Phase 1 TeacherClient proved multi-backend works: config-driven dispatch, uniform interface, no code changes to add backends

**What stays:**
- MLX LoRA training (`train_specialists_mlx.py`)
- 7-stage pipeline (data_prep → synthetic → dedup → train → evaluate → distill → quantize)
- 5 domain specialists (medical, code, qa_technical, encyclopedic, patents)
- All Phase 1-2 hardening (checkpoints, budget, cascade, router)

**What Unsloth adds (future phase):**
- `FastLanguageModel` with LoRA — faster training, lower VRAM
- 3-tier distillation: Teacher → Parent → Specialist
- SGFP4 hybrid quantization (FP4/Ternary + Log mode) per PTDS v4 §6
- Role-based specialists (Planner, Solver, Verifier, Arbiter, Refiner) per §4.3

**Pattern to follow:** Phase 1 `distill/backends/` — `TrainingBackend` base class, `MLXBackend` and `UnslothBackend` implementations, config-driven dispatch via `pipeline.yaml`.

**Reference:** `docs/PTSDV4_Training_Distillation.md` — full PTDS v4 spec
