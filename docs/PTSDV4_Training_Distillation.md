# Genius LLM PTDS v4

*(Training and Architecture Specification — Teacher → Parent → Specialist Pipeline)*\
Version 4.0 — June 2026

## 1. Overview

Genius LLM v4 defines a hierarchical training and deployment architecture that replaces monolithic fine‑tuning with a distributed **Teacher → Parent → Specialist** pipeline.\
Each stage reduces model size, precision, and domain scope while preserving reasoning quality through structured distillation and adaptive quantization (SGFP4).

Training objectives:

* Maintain reasoning fidelity of large teacher models while reducing compute cost.

* Enable modular specialist models for domain or role tasks (Planner, Solver, Verifier, Arbiter).

* Support decentralized retraining (EGGROLL) using LoRA adapters merged via CRDT consensus.

* Operate within a GPU/edge‑friendly quantization regime (SGFP4 hybrid 4‑bit format).

## 2. Hierarchical Model Roles

| Level          | Purpose                                                            | Typical Size | Precision           | Notes                                                                                        |
| -------------- | ------------------------------------------------------------------ | ------------ | ------------------- | -------------------------------------------------------------------------------------------- |
| **Teacher**    | Full‑scale reference model (e.g., DeepSeek‑V3‑R1 70B, Qwen3.5‑72B) | 30–70 B      | FP16 / BF16         | Provides ground‑truth reasoning traces and logits for distillation.                          |
| **Parent**     | Mid‑size distilled model                                           | 7–13 B       | SGFP4 (4‑bit hybrid) | Trained via Unsloth LoRA from Teacher; acts as generalist router and high‑accuracy fallback. |
| **Specialist** | Domain or role‑specific micro‑model                                | 0.2–3 B      | SGFP4 or INT4        | Derived from Parent using LoRA distillation or adapter pruning.                              |

## 3. Training Pipeline Summary

1. **Teacher → Parent Distillation**

    * Load Teacher in FP16 (quantized for inference only).

    * Train Parent using Unsloth’s `FastLanguageModel` with LoRA adapters.

    * Objective: minimize KL divergence between Teacher logits and Parent outputs on curated reasoning traces.

    * Dataset: mixture of general reasoning, math, code, and dialogue corpora.

2. **Parent → Specialist Distillation**

    * Freeze Parent backbone.

    * Train small specialists (Math, Grammar, Planner, Verifier, Arbiter) using LoRA or low‑rank deltas.

    * Each specialist receives filtered data by task type.

    * Distinguish two artifact classes when a specialist exposes both language and bounded judgment:
      * **ELM artifact** - language-generation/transformation adapter or micro-model.
      * **EJM artifact** - bounded judgment adapter, candidate readout, decision head, or equivalent processor binding.

    * One specialist lineage may publish both artifacts against the same backbone without forcing them into one training dataset or one promotion lifecycle.

3. **Quantization (SGFP4)**

    * After training, weights are quantized into SGFP4 format:

        * 64×64 macroblocks

        * per‑block FP16 scale/bias header

        * 16‑byte alignment with 4 LSB offset flags (mode + log)

    * Payload fixed at 2048 bytes per block.

4. **Swarm Retraining (EGGROLL)**

    * Specialists periodically retrained on local data.

    * Nodes push LoRA deltas to CRDT store.

    * Aggregator merges adapters using weighted averaging by reputation.

5. **Evaluation / Promotion**

    * Specialists validated via perplexity, consistency, latency, and reputation metrics.

    * High‑performing adapters promoted to Parent or distributed via swarm.

## 4. Model Architecture Components

### 4.1 Semantic Core

* Base transformer (Llama 3 8B or Mistral 7B derivative).

* Quantized with SGFP4 for inference, FP16 for training.

* Provides shared tokenizer, embeddings, and rotary positional encodings.

### 4.2 Router Module

* Lightweight classifier that selects which specialist(s) to invoke.

* Inputs: task embedding, numeric density, token entropy, recent role context.

* Outputs: route vector (probabilities over specialists).

* Implemented as small MLP or SLM (Sub‑Language Model) running on device.

### 4.3 Specialist Types (v4)

| Role         | Function                                                          | Notes               |
| ------------ | ----------------------------------------------------------------- | ------------------- |
| **Planner**  | Decomposes prompt, sets task plan.                                | Small SLM (~200 M). |
| **Solver**   | Generates candidate answers (math, code, reasoning).              | 1–3 B.              |
| **Verifier** | Checks solver outputs for consistency and arithmetic correctness. | 0.3–0.7 B.          |
| **Arbiter**  | Compares multiple candidate outputs, synthesizes final answer.    | 0.5–1 B.            |
| **Refiner**  | Polishes grammar, structure, and formatting.                      | 0.2–0.5 B.          |

## 5. Training Stack

### 5.1 Frameworks

* **Unsloth** for LoRA training, FP4/FP8 mixed precision, and adapter export.

* **PyTorch 2.2+** backend.

* **bitsandbytes** patched with SGFP4 quant hooks.

* **DeepSpeed Zero‑3** or **FSDP** for large‑model distillation.

* **EGGROLL** (custom) for distributed adapter retraining.

### 5.2 Data Flow

```text
Teacher outputs
    ↓
Parent LoRA fine-tune
    ↓
Parent checkpoints
    ↓
Specialist distillation
    ├── ELM generation artifact
    └── EJM judgment artifact / readout
    ↓
SGFP4 / adapter export
    ↓
Swarm retraining
```

### 5.3 Loss Functions

* **Teacher -> Parent:** KL divergence + cross-entropy on reasoning traces.

* **Parent -> Specialist ELM:** task-specific CE + language/logit distillation loss.

* **Parent -> Specialist EJM:** bounded decision loss over semantic choice distributions, including cross-entropy/KL where appropriate plus calibration-aware objectives such as Brier score or log loss.

* **Verifier training:** binary or multi-choice correctness judgment; generation of an explanation is a separate ELM capability when needed.

* **Arbiter training:** ranking or bounded-choice loss over candidate outputs; generated synthesis remains a separate ELM capability.

Canonical EJM teacher targets should store semantic choice IDs/descriptions and probabilities rather than target-token IDs so the same decision record can be compiled for multiple student tokenizers/readout architectures.

### 5.3.1 EJM Distillation Storage and Sharding

EJM decision data is stored in two forms:

1. **Canonical decision corpus** - shared semantic state plus isolated decision branches, content-addressed and reusable across compatible expert lineages.
2. **Target-specific distillation views** - compiled manifests for one target model/expert lineage, tokenizer/template version, judgment family, readout/head type, and governance scope.

Shared state is stored once. Decision branches reference the state by content ID. Independent branches may share the same state/prefix computation during training but must not observe sibling questions or sibling answers.

```text
Canonical State
    ├── Decision Branch 1
    ├── Decision Branch 2
    └── Decision Branch 3
            ↓
Target-Specific Distillation View
            ↓
State Shard + Branch Shard
            ↓
ELM/EJM lineage-specific retraining
```

This lets Code, Math, Grounding, Verifier, Router, or other experts reference overlapping canonical decision data while retraining independently. The primary training partition is the **target model lineage + expert + capability + judgment family**, not merely an ELM name.

For EJM targets, EGGROLL task shards should resolve to content-addressed manifests that identify:

* target backbone/model lineage
* target expert/adapter/readout
* state-shard reference
* branch-shard reference
* training objective
* validation policy
* tokenizer/template/readout version where applicable
* effective privacy/training policy

Beehive placement should prefer nodes that already cache the target model, target adapter/head, referenced state shard, and compatible policy scope.

### 5.4 Optimizers

* AdamW or Lion with learning rate warmup.

* LoRA rank 8–16 typical.

* Weight decay 0.01; gradient checkpointing enabled.

## 6. Quantization (SGFP4 Hybrid v2 — Adaptive Macroblock)

SGFP4 v2 uses adaptive macroblock sizing with encode-side Laplacian error analysis to select the optimal block size per region. This transforms the format from fixed "4-bit quantization" into a **variable effective bitrate weight codec**.

### 6.1 Macroblock Hierarchy

```
64×64 superblock → 32×32 → 16×16 → 8×8 → 4×4
```

Encoding process:
1. Try the largest block (64×64).
2. Fit FP4_AFFINE and T158_AFFINE modes.
3. Measure Laplacian-weighted error.
4. If acceptable, keep block at current size.
5. If error exceeds threshold, split into 4 children.
6. Repeat down to 4×4 minimum.

The final tensor becomes a **quadtree of quantized blocks**: large smooth regions use 64×64 (low metadata overhead), high-detail/outlier regions fall to 4×4 (NVFP4-class local scaling), and sparse regions use T158_AFFINE.

### 6.2 Layout Enum

Each 64×64 superblock uses a small layout enum in its header:

```
0 = one 64×64 block
1 = four 32×32 blocks
2 = sixteen 16×16 blocks
3 = sixty-four 8×8 blocks
4 = mixed quadtree
5 = full 4×4 stamps
```

### 6.3 Block Payload

Payload scales with block area, not fixed 2048 bytes:
- 64×64 (4096 weights): FP4 = 2048 bytes, T158 = 1024 bytes
- 32×32 (1024 weights): FP4 = 512 bytes, T158 = 256 bytes
- 16×16 (256 weights): FP4 = 128 bytes, T158 = 64 bytes
- 8×8 (64 weights): FP4 = 32 bytes, T158 = 16 bytes
- 4×4 (16 weights): FP4 = 8 bytes, T158 = 4 bytes

### 6.4 Per-Block Header

Each block stores:
- Two FP16 values (scale, bias) in packed uint32 header
- 4 LSB offset flags:
  - bit 0: format (0 = FP4_AFFINE, 1 = T158_AFFINE)
  - bit 1: mode (0 = Linear, 1 = Log)
  - bit 2-3: reserved
- Layout enum in superblock header

### 6.5 Decode

- Linear decode: `x = scale * q + bias`
- Log decode: `x = sign(q) * exp(scale * q + bias)`
- GPU/Vulkan shader performs fused decode + matmul using shared LUT for log mode
- Superblock container enables fixed outer page addressing; internal layout enum drives per-block dispatch

### 6.6 Effective Bitrate

| Region Type | Block Size | Mode | Effective bpw |
|-------------|-----------|------|---------------|
| Smooth / low-error | 64×64 | T158 | ~1.6 |
| Moderate | 32×32 / 16×16 | FP4 | ~2.5-3.5 |
| Sensitive / high-detail | 8×8 / 4×4 | FP4 | ~4.0-5.0 |
| **Typical average** | mixed | mixed | **~2.7-3.3** |

### 6.7 Encode-Side Laplacian Error Selection

The Laplacian pyramid operates at encode time only — decode is a simple table-driven dispatch. It separates low-frequency structure from high-frequency residual error:

`W ≈ smooth_base + quantized_residual`

This prevents outliers from dominating per-block scale, makes T158 more viable on residuals near zero, and preserves low-frequency structure (perceptual error metric). The pyramid is NOT decoded at runtime — it only informs block-size selection during encoding.

### 6.8 Comparison

| Dimension | NVFP4 | SGFP4 v1 | SGFP4 v2 (Adaptive) |
|-----------|-------|-------------|---------------------|
| Block size | Fixed 16-value | Fixed 64×64 | Variable 4×4–64×64 |
| Scale granularity | Per 16 values | Per 4096 weights | Adaptive per block |
| Metadata overhead | Moderate | Low | Variable |
| Effective bitrate | ~4.0 bpw | ~4.0 bpw | ~2.7-3.3 bpw |
| GPU decode | Tensor-core native | Portable (Vulkan) | Portable (Vulkan), layout-driven |

## 7. Swarm Retraining (EGGROLL)

### 7.1 Overview

Distributed retraining layer allowing specialists to evolve autonomously.

### 7.2 Process

1. Each node fine‑tunes local LoRA adapter on new data.

2. Adapter deltas stored in CRDT database.

3. Periodic merge:

    * weighted average by node reputation

    * conflict resolution via timestamp and reputation

4. Updated adapter redistributed to nodes.

### 7.3 Reputation Factors

* accuracy on validation tasks

* latency

* consistency with consensus

* contribution frequency

## 8. Distillation Implementation Notes

### 8.1 Teacher → Parent

```python
from unsloth import FastLanguageModel

teacher = load_teacher_model("DeepSeek-V3", dtype="float16")
parent, tok = FastLanguageModel.from_pretrained("meta-llama/Llama-3-8B", load_in_4bit=True)
parent = FastLanguageModel.get_peft_model(parent, r=8, lora_alpha=16, lora_dropout=0.05)

train_distillation(teacher, parent, dataset, loss="kl_div")
parent.save_pretrained("parent_adapter")
```

### 8.2 Parent → Specialist

```python
base = load_parent_model("parent_adapter", quant="gfp4")
specialist = attach_lora(base, r=4)
train_task(specialist, dataset_filtered)
export_gfp4(specialist, "math_solver.gfp4")
```

### 8.3 Adapter Merge (EGGROLL)

```python
adapters = collect_adapters_from_nodes()
merged = weighted_merge(adapters, weights=reputation_scores)
save_adapter(merged, "merged_parent_adapter")
```

## 9. Evaluation Metrics

| Metric                | Description            | Target                  |
| --------------------- | ---------------------- | ----------------------- |
| **Perplexity**        | Language modeling loss | < +5% vs Teacher        |
| **AlpacaEval subset** | Instruction following  | > 60%                   |
| **Latency**           | Token generation time  | < 10 ms/token           |
| **Memory**            | VRAM footprint         | < 8 GB (Parent)         |
| **Adapter size**      | LoRA delta             | < 50 MB                 |
| **Reputation gain**   | Post‑merge improvement | + > 0.1 score per epoch |

## 10. Training Infrastructure

| Component                      | Role                                        |
| ------------------------------ | ------------------------------------------- |
| **AWS p5.48xlarge / RTX 4090** | Teacher → Parent distillation               |
| **Local GPUs / swarm nodes**   | Specialist training, EGGROLL retraining     |
| **Storage**                    | RocksDB + IPFS for adapter and dataset sync |
| **Messaging**                  | libP2P Pub/Sub for update propagation       |
| **Monitoring**                 | Prometheus + Grafana                        |

## 11. Data Pipeline

1. **Data Sources**

    * Common Pile, GSM8K, CodeAlpaca, Grokipedia, GNUS logs.

    * synthetic teacher-generated decision states and bounded choice distributions for EJM training.

2. **Canonicalization / Pre-processing**

    * tokenize generation corpora only when needed by the target ELM path

    * normalize EJM choices to semantic IDs/descriptions and probability targets before target-specific token compilation

    * deduplicate shared decision state and content-address it independently from decision branches

    * filtering by task type and complexity

    * memory context injection (GAML) where policy permits

3. **View Compilation**

    * select records by target model lineage, expert, capability, domain, and judgment family

    * bind tokenizer/template/readout metadata

    * compile semantic choices to target-specific token IDs or decision-head indices only inside the view

4. **Batching / Sharding**

    * dynamic sequence length for ELM generation data

    * group EJM branches by shared state where possible so one state load/prefill can serve multiple isolated decisions

    * shard state records independently from branch records for cache locality and deduplication

5. **Augmentation**

    * paraphrasing

    * reasoning trace expansion for Planner/Verifier language capabilities

    * option permutations and choice-description variants for EJM robustness

    * novel-symbol/compositional tasks for measuring latent decision generalization

## 12. Deployment Artifacts

| Artifact | Format | Description |
| --- | --- | --- |
| Parent model | `.gfp4` | Quantized generalist checkpoint |
| Specialist ELM artifacts | `.lora` or `.gfp4` | Role/domain language-generation adapters or micro-models |
| Specialist EJM artifacts | `.lora`, head/readout, or `.gfp4` | Bounded judgment adapters, heads, readouts, or micro-models |
| Distillation views | content-addressed manifest | Target lineage/tokenizer/template/readout mapping over canonical decision data |
| Training shards | content-addressed manifest | State-shard + branch-shard references and training objective/policy |
| Router weights | `.pt` | Task classifier or judgment artifact |
| Consensus logs | `.jsonl` | Reputation and merge history |

## 13. Future Extensions

* **Sparse‑V kernels** for further inference acceleration.

* **Dynamic LoRA stacking** for multi‑role specialists.

* **On‑device retraining** with Unsloth + EGGROLL mini runtime.

* **Latent world model integration** (PTDS v5).

## 14. Summary

Genius LLM PTDS v4 formalizes a modular, quantization‑aware training pipeline:

* Teacher → Parent → Specialist distillation with Unsloth.

* SGFP4 hybrid quantization for compact, GPU‑friendly deployment.

* Swarm retraining via EGGROLL CRDT merge.

* Role-based specialists (Planner, Solver, Verifier, Arbiter, Refiner) for distributed reasoning.

* Separate but composable ELM and EJM artifacts within one specialist lineage.

* Content-addressed canonical decision corpora plus target-specific EJM views and shards for locality-aware retraining.

This architecture enables Genius LLM to scale reasoning quality across decentralized hardware while maintaining inspectability and low cost.
