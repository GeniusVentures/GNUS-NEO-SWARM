# Feature Landscape: gnus-poc ELM Training & Distillation Pipeline

**Domain:** Expert Language Model training/distillation pipeline for decentralized specialist swarm
**Researched:** 2026-05-27
**Confidence:** HIGH (existing codebase audited, strategic docs reviewed)

---

## Executive Feature Summary

The gnus-poc codebase already has a functional **data → train** pipeline that produces LoRA adapters for 5 source-aligned specialists (medical, qa_technical, code, encyclopedic, patents) on Qwen3-30B-MoE bases using MLX-LM. The milestone v1.1 target spans 7 additional capability areas that are entirely absent: synthetic data generation, knowledge distillation, evaluation/benchmarking, experiment tracking, FP4 quantization integration, deployment/packaging, and orchestration. The roadmap must add these capabilities sequentially, respecting that distillation depends on working evaluation, and orchestration depends on repeatable training+eval loops.

---

## Table Stakes

Features users (or the system) expect. Missing = milestone incomplete.

| Feature | Why Expected | Complexity | Status | Notes |
|---------|--------------|------------|--------|-------|
| Niche discovery & data extraction | Must identify new specialist domains from Common Pile | Medium | **EXISTS** | `analyze_common_pile.py` (TF-IDF clustering), `extract_source_niches.py` (source-label extraction). Produces `source_based_niches.json` with 5 viable niches |
| Dataset preparation with train/val/test splits | Required for any supervised fine-tuning | Low | **EXISTS** | `prepare_datasets.py` creates HF `DatasetDict` per niche, Qwen chat-template formatting, quality filters (100-50k char range) |
| LoRA fine-tuning pipeline | Core training mechanism for specialists | Medium | **EXISTS** | `train_specialists_mlx.py` uses `mlx_lm.lora.train_model()`. 30B MoE bases, rank=16, 1000 iters, GPU-skipping checkpoint logic. Produces `adapters.safetensors` |
| Synthetic data generation via teacher model | Distillation requires teacher-generated training examples | High | **MISSING** | No API client for DeepSeek v4 pro. No prompt templates, no quality filtering, no diversity strategies. Must be built from scratch |
| Per-specialist evaluation & benchmarking | Must verify specialists actually improved vs. base model | High | **MISSING** | No held-out accuracy measurement, no latency benchmarks, no parameter efficiency metrics. No task-specific metrics per niche |
| Knowledge distillation (teacher→student) | Core milestone deliverable: subspace extraction, logit transfer | High | **MISSING** | No distillation code exists. Strategic docs reference 370B+ teacher → subspace extraction → distillation → FP4 quant workflow, but zero implementation |
| Experiment tracking | Must compare different LoRA ranks, base models, teacher prompts | Medium | **MISSING** | No run comparison, no hyperparameter search, no artifact management. Training metadata saved as per-specialist JSON but no cross-run aggregation |
| Orchestration layer | Must tie niche discovery → data prep → train → eval → deploy into a single command | High | **MISSING** | Each step is a standalone script. No DAG, no retry logic, no resource allocation, no parallel training orchestration |
| Deployment packaging | Trained adapters must be exportable to MNN/Vulkan runtime | High | **MISSING** | No adapter merging code. No MLX → MNN/ONNX format conversion. No model+adapter bundling. FP4 quantization exists in C++ (`FP4Codec.hpp`) but is not integrated into the Python pipeline |

---

## Differentiators

Features that set the gnus-poc approach apart. Not expected by generic pipelines, but create competitive advantage for the dAMoE architecture.

| Feature | Value Proposition | Complexity | Status | Notes |
|---------|-------------------|------------|--------|-------|
| FP4 pyramid-based quantization integrated into pipeline | Takes the novel FP4 method (Gaussian/Laplacian pyramids, spline blending, macro-block scales) from prototype in `FP4Codec.hpp` and folds it into the training/deployment workflow | High | **MISSING** | Strategic docs describe a proprietary breakthrough; must bridge C++ codec with Python pipeline. Expected 0.2% storage overhead, 0.1-0.4 ppl degradation |
| Subspace extraction distillation (not just logit-based) | Per strategic docs, extract specialized subspaces from 370B+ teacher rather than simple output mimicry. Potentially better specificity than vanilla knowledge distillation | Very High | **MISSING** | Referenced in docs as "teaching phase workflow." No existing open-source implementation for this approach. Requires research-phase feasibility assessment |
| Multi-model base support per specialist | Current code already maps code specialist to Qwen3-Coder, others to Qwen3-Instruct. Extending this to per-niche best open-source model (e.g., DeepSeek-Math for math niches) leverages dAMoE's heterogeneous expert advantage | Medium | **PARTIAL** | `SPECIALIST_BASE_MODELS` dict exists. Extending requires model-specific tokenizer/format handling, which is not yet generalized |
| Human feedback LoRA loops | Strategic docs describe thumbs-up/down → reputation adjustment → LoRA retraining feedback cycle. This is the "RLHF for decentralized specialists" differentiator | High | **MISSING** | No feedback collection, no rating storage, no retraining trigger. Requires swarm-side integration (not just pipeline) |
| Niche auto-discovery → auto-train pipeline | Existing clustering scripts can discover 20+ niches. Automating the pipeline so new niches trigger dataset prep + training without manual intervention creates dAMoE's organic expert growth | High | **MISSING** | `analyze_common_pile.py` discovers but doesn't trigger. Needs quality gating (data sufficiency thresholds, domain coverage metrics) |
| Swarm-ready adapter packaging | Training produces per-niche adapters; the differentiator is packaging them for P2P distribution (adapter checksums, versioning, LoRA signatures) | Medium | **MISSING** | No versioning scheme, no checksum, no LoRA identity for swarm advertisement messages |
| Cost-tracking & resource estimation | Before scaling to 1024 specialists, the pipeline should estimate GPU hours per specialist, enabling the strategic docs' cost projections ($134k for 8×H100 over 2 weeks) | Low | **MISSING** | Training metadata logs duration but doesn't project forward. Simple time-per-iteration × target-specialists math would enable planning |

---

## Anti-Features

Features to explicitly NOT build in this milestone.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Full pretraining from scratch | Milestone is about distillation/LoRA from existing base models. Pretraining 1B+ models requires cluster-scale compute (docs estimate $135k+ for 8×H100 over 2 weeks) and is out of scope | Use Qwen3, DeepSeek, Llama open-source bases as starting points |
| Real-time serving/inference endpoints | Pipeline is offline training. Serving belongs in the C++ `genius_node` via MNN, not in the Python gnus-poc pipeline | Keep pipeline output as adapter files; serving is C++ layer concern |
| Multi-teacher distillation (aggregating multiple frontier models simultaneously) | Docs acknowledge licensing restrictions on OpenAI/Anthropic outputs for derivative training. Multi-teacher also multiplies API costs (estimated $480k+ for 400M token dataset via Claude) | Use single DeepSeek v4 pro API as teacher (you have API access). Concentrate on distillation quality not teacher diversity |
| Dynamic adapter loading/hot-swapping during inference | Belongs in the C++ runtime, not the Python training pipeline | C++ layer handles adapter activation; pipeline just produces the files |
| AutoML/hyperparameter optimization frameworks (Optuna, Ray Tune) | Adds significant dependency surface and complexity for a pipeline that currently runs on a Mac Studio. Premature optimization for a PoC | Manual A/B testing via experiment tracking config files is sufficient for 5→N specialists |
| Streaming/distributed training across multiple Macs | Pipeline runs on single Mac Studio M2 Ultra. Distributed training infrastructure is a swarm networking problem (Phase 6), not a training pipeline problem | Keep single-machine training. Orchestration can sequence specialists, but parallelization is out of scope |
| Proprietary model distillation (GPT-4, Claude, Gemini outputs) | Strategic docs explicitly conclude: "The GNUS.ai decentralized specialist system should be 100% open-model-based." API ToS prohibit derivative training. Grok license prohibits training other language models | Use DeepSeek v4 pro API (you have access). Verify license terms for derivative use. Fall back to open-source teacher distillations if needed |
| On-the-fly FP4 quantization during LoRA training (QAT) | FP4 codec is a post-training quantization pipeline per strategic docs. QAT would require modifying the training loop in MLX-LM, which is brittle and complex | Apply FP4 quantization as a post-training step after LoRA adapters are saved. Keep training in FP16/BF16 |

---

## Feature Dependencies

```
Source Niche Discovery ───► Dataset Preparation ───► LoRA Training ───► Evaluation ───► Quantization ───► Deployment
        (EXISTS)              (EXISTS)                (EXISTS)          (MISSING)      (MISSING)        (MISSING)
                                    │
                                    ▼
                          Synthetic Data Generation ◄── Teacher API Client
                                (MISSING)                  (MISSING)
                                    │
                                    ▼
                          Knowledge Distillation ───► LoRA Training
                                (MISSING)               (reuses EXISTS)
                                    │
                                    ▼
                          Experiment Tracking ◄── requires Evaluation + Distillation
                                (MISSING)
                                    │
                                    ▼
                          Orchestration Layer ◄── requires ALL above
                                (MISSING)
```

**Key dependency constraints:**
- Evaluation MUST be built before distillation (can't measure distillation quality without eval)
- Synthetic data generation MUST be built before distillation (teacher → student requires teacher-generated data)
- Experiment tracking SHOULD be built alongside evaluation (eval results are what you track)
- Deployment CAN be built in parallel with evaluation+distillation (independent output path)
- Orchestration is the LAST feature (wraps everything else)

---

## What the 5 Existing Specialists Provide vs. What's Missing

| Capability | Existing (5 specialists) | Missing for N specialists |
|------------|--------------------------|--------------------------|
| **Data source** | 5 hardcoded niches in `TARGET_NICHES` dict (`extract_source_niches.py`) | Dynamic niche selection from clustering results (`analyze_common_pile.py` produces 20 clusters, but only 5 source-mapped) |
| **Base models** | Qwen3-30B-MoE-Instruct, Qwen3-Coder-30B-MoE | No model registry. Adding new base models requires manual dict entries. No per-niche model recommendation logic |
| **LoRA config** | Single config: rank=16, dropout=0.05, scale=20.0, iters=1000 | No A/B testing for rank, target modules, layers. One-size-fits-all may not be optimal for new niches |
| **Training data format** | Qwen3 chat template (`<|im_start|>` tags) hardcoded in `format_for_training()` | Adding new base models with different chat templates requires code changes. No template registry |
| **Quality filtering** | 100-50000 char range, source matching | No perplexity filtering, no deduplication, no language detection, no content safety screening |
| **Checkpoint management** | Checkpoints saved per 200 iters, final adapter at end | No checkpoint comparison, no best-checkpoint selection by validation loss, no pruning of old checkpoints |
| **Training metadata** | Per-specialist JSON with duration, config | No cross-specialist comparison, no benchmark scores, no model card generation |
| **Adapter storage** | `adapters.safetensors` per niche directory | No adapter merging (combining multiple LoRAs), no adapter diffing (what changed between versions), no adapter hashing for swarm identity |

---

## MVP Recommendation for Milestone v1.1

**Prioritize in this order:**

### Phase A: Foundational Gaps (build first, everything depends on them)
1. **Synthetic data generation** — DeepSeek v4 pro API client with prompt templates per niche, quality filtering, output diversity checks
2. **Per-specialist evaluation framework** — held-out perplexity, task-specific accuracy, latency benchmarks, parameter efficiency metrics

### Phase B: Core Milestone Deliverables
3. **Knowledge distillation pipeline** — logit-based (temperature-scaled KL divergence) + subspace extraction approach, reusing existing LoRA training loop
4. **Experiment tracking** — run comparison across LoRA ranks (4, 8, 16, 32), teacher prompt variants, niche clusters; artifact management

### Phase C: Pipeline Unification
5. **Orchestration layer** — CLI-driven DAG: `niche-discover → data-prep → synth-gen → distill → train → eval → quantize → package`
6. **FP4 quantization integration** — bridge `FP4Codec.hpp` logic into Python post-training step, validate on existing specialists
7. **Deployment packaging** — adapter merging, MLX→ONNX export, checksum + versioning

**Defer:**
- Human feedback LoRA loops (requires swarm runtime, not just pipeline)
- Auto-niche discovery triggers (needs quality gates validated on current 5 before automating)
- Multi-model base support generalization (current 2-base approach is sufficient for PoC)

---

## Complexity Assessment

| Feature | Complexity | Reason |
|---------|------------|--------|
| Synthetic data generation | **High** | API client integration, prompt engineering per niche, quality filtering pipeline. But well-understood pattern; many open-source examples |
| Evaluation framework | **High** | Requires per-niche metrics design (coding ≠ medical ≠ Q&A). Perplexity is easy; task-specific BLEU/ROUGE/F1 requires domain judgment |
| Knowledge distillation | **Very High** | Logit-based is straightforward (temperature scaling + KL loss). Subspace extraction is research-grade with no existing implementation in this codebase. May need phased approach: logit-based first, subspace later |
| Experiment tracking | **Medium** | MLflow or Weights & Biases integration. Or lightweight CSV/JSON approach for PoC. Pattern is well-established |
| FP4 quantization integration | **High** | Bridging C++ FP4Codec logic into Python. May need pybind11 or reimplementation. Per-docs, this is proprietary novel IP |
| Deployment packaging | **Medium** | MLX→ONNX has known paths. Adapter merging is `mlx_lm.fuse()`. Versioning is convention. Well-understood, just needs wiring |
| Orchestration layer | **Medium** | CLI entry point, sequential step execution, error handling. Not a real DAG scheduler — just a script orchestrator for PoC |

---

## Sources

- **Codebase audit (HIGH):** All 6 Python files in `gnus-poc/` read and analyzed. 5 specialist checkpoints confirmed in `gnus-poc/models/specialists_mlx/`. Source niche analysis results in `gnus-poc/data/analysis/source_based_niches.json`.
- **Strategic docs (HIGH):** ChatGPT Idea Vetting (dAMoE architecture), Grok Vetting (FP4 pyramid quantization, Common Pile rationale), Grok Idea Vetting (feasibility assessment by Grok of ChatGPT's analysis), gnus_llm_tech_spec (placeholder — no substantive content).
- **Roadmap context (HIGH):** `.planning/ROADMAP.md` Phase 4 ELM Expansion requires real inference (Phase 3 MNN) before C++ ELM integration. gnus-poc is the training pipeline that produces ELMs for the C++ runtime.
- **PROJECT.md (HIGH):** Milestone v1.1 explicitly targets synthetic data, LoRA training, distillation, evaluation, orchestration, FP4 quantization, and experimentation.
