# Project: gnus-poc

## Identity

| Field | Value |
|-------|-------|
| **Name** | gnus-poc |
| **Full Name** | GNUS-POC ELM Training & Distillation Pipeline |
| **Language** | Python 3.10+ |
| **Target Platform** | Apple Silicon (MLX), with paths for cross-platform |
| **Version** | v0.1.0 (pre-roadmap) |

## Core Value

A Python proof-of-concept that trains specialized Expert Language Models (ELMs) through teacher-student knowledge distillation and evolutionary (EGGROLL-style) retraining, producing quantized (SGFP4) specialists deployable on Apple Silicon via MLX.

## Description

gnus-poc is the training and distillation subset of the GeniusCognitiveSystem architecture. It takes a DeepSeek v4 Pro teacher model, generates synthetic domain-specific data, trains LoRA adapter specialists on a Qwen3-30B-A3B backbone, distills knowledge through logit-based KD, evaluates quality, and exports quantized models in SGFP4 format.

The current v0.1.0 implements a 7-stage sequential pipeline (data_prep -> synthetic_data -> dedup -> train -> evaluate -> distill -> quantize) for 5 specialist niches (medical, qa_technical, code, encyclopedic, patents).

## Key Constraints

1. **Apple Silicon first**: MLX is the primary training runtime. Cross-platform paths (CUDA/Vulkan) are deferred.
2. **Single-machine**: No distributed execution. Sequential pipeline with checkpoint resume.
3. **Python 3.10+**: No C++ runtime dependency. Leverages MLX, PyTorch-compatible tooling.
4. **Adapter-based architecture**: Specialists are LoRA adapters on a shared backbone, not standalone models (see Key Decisions).
5. **SGFP4 export format**: 64x64 macroblocks, dual-mode (FP4_AFFINE/T158_AFFINE), per-block affine decode.

## Key Decisions

### Decision 1: Adapter-Based Specialist Architecture

**Status:** Decided (2026-06-18)
**Decision:** Specialists are implemented as LoRA adapters on a shared Qwen3-30B-A3B backbone.
**Rationale:**
- Current codebase already uses LoRA adapters with MLX.
- Architecture docs (doc 11 Section 16.15) propose adapter-based as preferred option.
- Adapters share backbone weights, reducing storage and enabling faster specialist switching.
- EGGROLL retraining targets adapters as primary optimization surface (doc 13 Section 16.7).
- Standalone models would require per-specialist full model storage (~15GB each vs ~200MB adapters).

### Decision 2: Per-Specialist Quantization Policy

**Status:** Decided (2026-06-18)
**Decision:** Each specialist role may use a different quantization mode based on accuracy-sensitivity profiling.
**Rationale:**
- Doc 11 Section 16.14.5 identifies this as an open question.
- FP4_AFFINE (4-bit signed) for accuracy-critical specialists (medical, legal/compliance).
- T158_AFFINE (ternary ~1.58-bit) for latency-tolerant specialists (encyclopedic, formatting).
- Adaptive mode selection per block during encoding (doc 16 Section 16.5).
- Policy configurable per specialist in `config/specialists/<niche>.yaml`.

### Decision 3: Scope Boundary — Training Pipeline Only

**Status:** Decided (2026-06-19)
**Decision:** gnus-poc is scoped to the ELM teacher→student training and distillation pipeline through benchmark validation. EGGROLL retraining, GAML memory, reputation/consensus, and epistemic arbitration belong to the GNUS-NEO-SWARM C++ parent repo.

## Architecture Reference

gnus-poc implements the ELM training subset of the GeniusCognitiveSystem 7-layer model:

| Layer | Architecture Doc | gnus-poc Scope |
|-------|-----------------|---------------|
| 1. Client/API | doc 12 | Not in scope |
| 2. Orchestration (Router/Planner) | doc 03 | Phase 4 (rule-based router) |
| 3. Expert Execution (ELMs) | doc 03, 11 | Core — specialist training |
| 4. Consensus & Grounding | doc 04, 05 | Phase 6 (grounding) |
| 5. Tool Intermediary | doc 12 | Not in scope (needs C++ infra) |
| 6. Memory (GAML) | doc 06 | Phase 6 (memory store) |
| 7. Distributed Infrastructure | doc 02, 04 | Not in scope |

Additional:
- SGFP4 Format: doc 16 — Core (quantization export)
- EGGROLL Retraining: doc 13 — Phase 5
- Reputation: doc 04 — Phase 7
- Hierarchical Critics (HCTS): doc 14 — v2 deferred
- Epistemic Arbitration: doc 15 — v2 deferred

## Scope Boundaries

**In scope (v1):**
- Pipeline hardening with subprocess execution and validated checkpoints
- Multi-teacher cascade (DSv4 Fast → domain-routed Level 2) with dual-backend API (OpenAI + Anthropic)
- Budget enforcement, retry with exponential backoff, circuit breaker
- Knowledge distillation with KD loss and temperature sweeping
- LoRA specialist training with MLX
- Model evaluation metrics (accuracy, perplexity, latency)
- Rules-based specialist routing (YAML-driven, not learned)
- SGFP4 quantization export with dual-mode selection and provenance manifests
- Benchmark evaluation gate (MMLU, HumanEval, GSM8K, domain suites)

**Out of scope (belongs to GNUS-NEO-SWARM C++ parent repo):**
- EGGROLL swarm retraining and evolutionary optimization
- GAML agentic memory layer
- Reputation-weighted consensus
- Distributed swarm execution (needs libp2p, IPFS-lite)
- Tool Intermediary / secure agent architecture (needs sandboxing)
- Multi-node consensus/arbitration
- GPU decode shaders for FP4 (needs Vulkan/MoltenVK)
- Hierarchical Critical Thinking Specialists (HCTS)
- Epistemic Arbitration / GQHSM
- Grounding/retrieval integration
