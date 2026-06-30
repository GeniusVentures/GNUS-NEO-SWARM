---
title: Unsloth Training Backend
trigger_condition: GPU infrastructure (CUDA/NVIDIA) available for gnus-poc training
planted_date: 2026-06-21
---

# Seed: Unsloth Training Backend

**Idea:** Add Unsloth as a parallel training backend to gnus-poc, following the Phase 1 multi-backend pattern (`distill/backends/` for teachers). The `TrainingBackend` abstraction dispatches to MLX or Unsloth based on config.

**Trigger:** When GPU infrastructure (CUDA-capable) is available — AWS p5, local RTX 4090, or equivalent.

**Design pattern:**
```python
# Following Phase 1 TeacherClient backend pattern
class TrainingBackend(ABC):
    def train(self, config: TrainingConfig) -> AdapterResult: ...

class MLXBackend(TrainingBackend): ...     # existing, Apple Silicon
class UnslothBackend(TrainingBackend): ...  # new, CUDA
```

**Dependencies:**
- Unsloth `FastLanguageModel`
- PyTorch 2.2+
- bitsandbytes with SGFP4 quant hooks
- CUDA-capable GPU

**Relationship to PTDS v4:** This seed is the first step toward full PTDS v4 compliance. The full 3-tier pipeline (Teacher→Parent→Specialist) and role-based specialist taxonomy are separate concerns addressed in a future PTDS v4 Unsloth Integration phase.

**See also:** `.planning/workstreams/poc/notes/ptds-v4-unsloth-strategy.md`
