# Phase 04: Benchmark Evaluation - Research

**Researched:** 2026-06-28
**Domain:** LLM benchmark evaluation, lm-eval-harness integration, quality gating
**Confidence:** MEDIUM

## Summary

Phase 04 layers benchmark evaluation onto quantized specialist models (from Phase 3) using EleutherAI's lm-evaluation-harness as the primary scoring engine. Five of seven required benchmarks (MMLU, HumanEval, MedMCQA, GPQA) are natively supported by lm-eval v0.4.12. Two benchmarks (PubMedQA, BIGPATENT) require custom YAML task definitions — a well-documented pattern in lm-eval-harness. One benchmark (FRAMES) is not publicly available as a dataset and requires a custom data acquisition strategy. Google Patents has no official REST API; BigQuery public patent data is the recommended integration path.

The Python API (`simple_evaluate()`) is preferred over subprocess invocation — it returns structured results directly, avoids overhead, and integrates with the existing MetricStore pattern. Integration with the pipeline runner follows the established subprocess stage pattern (add a "benchmark" stage after "quantize"). The existing `Benchmarker.gate_check()` pattern from Phase 3 provides the foundation for tiered gating (D-06), extended with benchmark-specific dimensions.

**Primary recommendation:** Use `lm-eval` v0.4.12 as a Python library (not subprocess), create custom task YAML files for PubMedQA and BIGPATENT, use BigQuery for Google Patents data, and treat FRAMES as a Phase 5 deferral if the dataset is not obtainable.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01: Multi-mode benchmark source.** Config-driven selection: `local` (downloaded dataset files), `huggingface` (datasets API), `api` (DeepSeek v4 Pro API evaluation). Switchable per benchmark via `pipeline.yaml` `benchmark_source:` field.
- **D-02: lm-eval-harness format.** Use EleutherAI's `lm-evaluation-harness` standard protocols. Each benchmark uses its established shot count (MMLU=5-shot, HumanEval=0-shot, etc.). Scores are comparable to published results.
- **D-03: Per-benchmark prompt templates.** Each benchmark uses its official prompt template from lm-eval-harness. Per-benchmark template overrides configurable in `config/benchmarks/<name>.yaml`.
- **D-04: MMLU universal baseline.** Every specialist runs MMLU (57 subjects). Plus at least one domain-specific benchmark.
- **D-05: Specialist-benchmark mapping:** code(HumanEval), medical(MedMCQA+PubMedQA), qa_technical(GPQA STEM subsets), encyclopedic(FRAMES), patents(BIGPATENT+Google Patents).
- **D-06: Tiered gating.** Warning on first below-threshold, block on consecutive failures.
- **D-07: Per-benchmark, per-category thresholds.** Reference each benchmark's own category baselines. Published baselines where available; configurable overrides in `pipeline.yaml`.
- **D-08: Composite production-ready.** 2 of 3 dimensions: (1) benchmark scores above threshold, (2) regression <= configurable % (default 10%), (3) deviation from baseline model <= configurable % (default 20%).
- **D-09: Per-benchmark sensitivity deltas.** MMLU: aggregate <=2% drop significant. HumanEval: <=5% drop. GPQA: <=3% drop.
- **D-10: Auto-config-adjust + manual escalation.** Below-threshold triggers automatic config adjustment. After 3 consecutive failures, blocks and requires manual intervention.
- **D-11: Separate trend storage.** Persisted in `artifacts/trends/` with per-specialist trend files.

### Claude's Discretion
- lm-eval-harness integration approach (subprocess vs Python API)
- Per-benchmark config file schema
- Benchmark dataset download and caching strategy
- Trend storage schema and diffing algorithm
- Gate dimension design for Benchmarker integration
- Per-benchmark sensitivity threshold defaults
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| BMARK-01 | Benchmark Suite Execution — score quantized models against established suites with per-category breakdown | lm-eval `simple_evaluate()` returns per-task results. Custom YAML tasks fill gaps for PubMedQA, BIGPATENT, FRAMES. |
| BMARK-02 | Quality Gate Threshold — per-benchmark thresholds flag failed specialists, block production-ready marker | Existing `Benchmarker.gate_check()` pattern extended with benchmark dimensions. Consecutive failure tracking from Phase 3 reused. |
| BMARK-03 | Trend Analysis and Feedback — comparable results across runs, score deltas, degradation warnings | Trend storage schema in `artifacts/trends/` with per-specialist JSON. Multi-run diff algorithm computes per-benchmark, per-category deltas. |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Benchmark dataset acquisition | API / Backend | — | `datasets` library downloads from HuggingFace; local caching is a backend concern |
| Model inference for benchmark scoring | API / Backend | — | MLX model runs locally; lm-eval orchestrates inference in-process |
| Benchmark scoring (lm-eval-harness) | API / Backend | — | Python library invoked directly; no browser/client involvement |
| Quality gate evaluation | API / Backend | — | Benchmarker runs server-side, gate state persisted to disk |
| Trend storage and diffing | Database / Storage | — | `artifacts/trends/` on local filesystem; no external database needed |
| Config loading (benchmark YAMLs) | API / Backend | — | ConfigLoader pattern from Phase 1 extended for benchmarks |
| Pipeline stage orchestration | API / Backend | — | Pipeline runner invokes benchmark stage after quantize |
| Google Patents data access | API / Backend | — | BigQuery or bulk download; not a client-side concern |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `lm-eval` | 0.4.12 | LLM benchmark evaluation framework | EleutherAI's standard; 60+ built-in benchmarks; `simple_evaluate()` Python API [VERIFIED: PyPI registry + slopcheck OK] |
| `datasets` | 4.0.0 (installed) / 5.0.0 (latest) | HuggingFace dataset download and caching | Already in requirements.txt; used by lm-eval internally; caches datasets to `~/.cache/huggingface/` [VERIFIED: PyPI registry + slopcheck OK] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `evaluate` | 0.4.6 | HuggingFace metrics library | lm-eval dependency; provides acc, f1, BLEU, ROUGE metrics |
| `sacrebleu` | 2.6.0 | Standardized BLEU scoring | lm-eval dependency for text generation benchmarks |
| `rouge-score` | 0.1.2 | ROUGE metric computation | lm-eval dependency; needed for BIGPATENT summarization scoring |
| `PyYAML` | 6.0.0+ | YAML config parsing | Already in requirements.txt; benchmark task YAML files |
| `google-cloud-bigquery` | [ASSUMED] | BigQuery client for Google Patents data | Only if `benchmark_source: api` for patents; install on demand |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| lm-eval Python API | lm-eval subprocess | Subprocess requires parsing CLI output; Python API returns structured dict directly. Python API preferred. |
| lm-eval v0.4.12 | lm-eval v0.3.x | v0.3 uses older Python-class-based tasks; v0.4 has YAML-based tasks and `simple_evaluate()`. v0.4 required. |
| Google Patents BigQuery | USPTO bulk XML downloads | BigQuery is queryable; USPTO bulk is 100GB+ XML. BigQuery preferred for targeted queries. |

**Installation:**
```bash
pip install lm-eval==0.4.12
# datasets already in requirements.txt
# For Google Patents BigQuery access (conditional):
pip install google-cloud-bigquery
```

**Version verification:**
```bash
pip index versions lm-eval        # 0.4.12 (LATEST)
pip index versions datasets       # 5.0.0 (LATEST), 4.0.0 (installed)
```

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| `lm-eval` | PyPI | 2+ yrs | High (EleutherAI flagship) | github.com/EleutherAI/lm-evaluation-harness | [OK] | Approved |
| `datasets` | PyPI | 5+ yrs | Very High (HuggingFace core) | github.com/huggingface/datasets | [OK] | Approved |
| `google-cloud-bigquery` | PyPI | [ASSUMED] | [ASSUMED] | [ASSUMED] | Not checked | Conditional — only if patents via BigQuery |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none
**Cross-ecosystem confusion check:** `lm-eval` returns 404 on npm registry — confirmed Python-only package.

## Architecture Patterns

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     PIPELINE RUNNER (pipeline/runner.py)                │
│                                                                         │
│  data_prep → synthetic_data → dedup → train → evaluate → distill →     │
│  quantize ──→ [NEW] benchmark ──→ quality_gate_report                  │
│                     │                                                   │
└─────────────────────┼───────────────────────────────────────────────────┘
                      │ subprocess: python eval/benchmark_runner.py --niche {niche}
                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                  BENCHMARK RUNNER (eval/benchmark_runner.py)             │
│                                                                         │
│  1. Load config (pipeline.yaml + config/benchmarks/<name>.yaml)         │
│  2. Determine benchmark source mode (local/huggingface/api)             │
│  3. For each benchmark in specialist mapping:                           │
│     ├── Load model (MLX)                                                │
│     ├── Run lm-eval simple_evaluate()                                   │
│     ├── Collect per-category scores                                     │
│     └── Write results to artifacts/benchmarks/                          │
│  4. Run Benchmarker.gate_check()                                        │
│  5. Update trend storage (artifacts/trends/)                            │
└─────────────────────────────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        LM-EVAL-HARNESS (v0.4.12)                        │
│                                                                         │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐      │
│  │ Built-in Tasks    │  │ Custom Tasks      │  │ Model Wrapper     │      │
│  │ (YAML in package) │  │ (config/benchmarks│  │ (subclass of      │      │
│  │                   │  │  /<name>.yaml)    │  │  lm_eval.api.LM)  │      │
│  │ • mmlu            │  │ • pubmedqa        │  │                   │      │
│  │ • humaneval       │  │ • bigpatent        │  │  wraps MLX model  │      │
│  │ • medmcqa         │  │ • frames (custom)  │  │  for lm-eval API  │      │
│  │ • gpqa_main_n_shot│  │                    │  │                   │      │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘      │
│                                                                         │
│  simple_evaluate(model=mlx_wrapper, tasks=[...], num_fewshot=N)         │
│  → returns {"results": {"task": {"metric": value, ...}}, ...}           │
└─────────────────────────────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      DATA SOURCES (per D-01 mode)                       │
│                                                                         │
│  local:          data/benchmarks/<name>/   (pre-downloaded files)       │
│  huggingface:    ~/.cache/huggingface/     (datasets library cache)     │
│  api:            DeepSeek v4 Pro API       (remote evaluation)          │
│  google_patents: BigQuery patents-public-data (SQL queries)             │
└─────────────────────────────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      PERSISTENCE LAYER                                   │
│                                                                         │
│  artifacts/benchmarks/<niche>_<benchmark>_<timestamp>.json  (BMARK-01)  │
│  artifacts/trends/<niche>_trend.json                          (BMARK-03)│
│  artifacts/.gate_state/<niche>_bench_gate_state.json          (BMARK-02)│
│  artifacts/.gate_state/<niche>_gate_state.json  (existing Phase 3)      │
└─────────────────────────────────────────────────────────────────────────┘
```

### Recommended Project Structure
```
gnus-poc/
├── config/
│   ├── pipeline.yaml              # Extended: benchmarks, benchmark_gates sections
│   ├── benchmarks/
│   │   ├── mmlu.yaml              # Per-benchmark config: prompt template, shots, thresholds
│   │   ├── humaneval.yaml
│   │   ├── medmcqa.yaml
│   │   ├── pubmedqa.yaml          # Custom task: dataset_path, splits, template
│   │   ├── gpqa.yaml
│   │   ├── frames.yaml            # Custom task (if dataset obtained)
│   │   ├── bigpatent.yaml         # Custom task: big_patent HuggingFace dataset
│   │   └── google_patents.yaml    # BigQuery-backed custom task
│   └── specialists/
│       └── <niche>.yaml           # Extended: benchmark_overrides per niche
├── eval/
│   ├── benchmarker.py             # Existing — extended with benchmark gate dimensions
│   ├── benchmark_runner.py        # NEW — main entry point for benchmark stage
│   ├── benchmark_mlx_model.py     # NEW — MLX model wrapper for lm-eval (subclass LM)
│   ├── benchmark_tasks.py         # NEW — TaskManager setup, custom task registration
│   ├── benchmark_config.py        # NEW — ConfigLoader._validate_benchmarks()
│   ├── benchmark_trends.py        # NEW — Trend storage, diffing, degradation detection
│   ├── evaluator.py               # Existing — unchanged
│   └── metric_store.py            # Existing — extended with benchmark methods
├── data/
│   └── benchmarks/                # Cache for local benchmark mode (D-01)
│       ├── mmlu/
│       ├── humaneval/
│       └── ...
└── artifacts/
    ├── benchmarks/                # BMARK-01: per-run benchmark results
    │   └── <niche>_<benchmark>_<timestamp>.json
    ├── trends/                    # BMARK-03 / D-11: per-specialist trend files
    │   └── <niche>_trend.json
    └── .gate_state/               # Existing Phase 3 + new benchmark gate state
        ├── <niche>_gate_state.json
        └── <niche>_bench_gate_state.json
```

### Pattern 1: lm-eval Python API Integration (over subprocess)
**What:** Use `lm_eval.simple_evaluate()` as a library call, not a subprocess invocation. Wrap the MLX model in an `lm_eval.api.model.LM` subclass for direct in-process inference.

**When to use:** Always — this is the recommended approach. Subprocess would require parsing CLI output; the Python API returns a structured dict.

**Example:**
```python
# Adapted from lm-eval docs: docs/python-api.md [CITED]
from lm_eval import simple_evaluate
from lm_eval.tasks import TaskManager
# custom_mlx_model is an instance of a class that subclasses lm_eval.api.model.LM
results = simple_evaluate(
    model=custom_mlx_model,           # pre-initialized LM subclass
    tasks=["mmlu", "humaneval"],      # task names (built-in or custom)
    num_fewshot=5,                    # per D-02: MMLU=5, HumanEval=0 override per-task
    batch_size=1,                     # MLX inference is sequential
    task_manager=task_manager,        # includes custom tasks via include_path
    log_samples=False,                # don't log every sample (disk heavy)
)
# results["results"] -> {"mmlu": {"acc": 0.72, "acc_stderr": 0.01}, ...}
```

### Pattern 2: Custom Task via YAML + include_path
**What:** For benchmarks NOT in lm-eval's built-in task list (PubMedQA, BIGPATENT, FRAMES), define YAML task configs in `config/benchmarks/` and load via `TaskManager(include_path=...)`.

**When to use:** For any benchmark not natively in lm-eval-harness.

**Example (PubMedQA):**
```yaml
# config/benchmarks/pubmedqa.yaml
# Source: lm-eval docs/new_task_guide.md [CITED]
task: pubmedqa
dataset_path: qiaojin/PubMedQA         # HuggingFace dataset ID [ASSUMED - verify at runtime]
dataset_name: pqa_labeled              # labeled subset with ground truth
test_split: train                      # PubMedQA uses 'train' split for test (no dedicated test split)
output_type: multiple_choice
doc_to_text: "{{question}}\nA. {{context['contexts'][0] if context['contexts'] else ''}}\nAnswer:"
doc_to_target: "{{final_decision}}"    # yes/no/maybe
doc_to_choice: ["yes", "no", "maybe"]
metric_list:
  - metric: acc
    aggregation: mean
    higher_is_better: true
metadata:
  version: 0
```

### Pattern 3: MLX Model Wrapper for lm-eval
**What:** Subclass `lm_eval.api.model.LM` to wrap the MLX quantized model for lm-eval's inference protocol. Must implement `loglikelihood()`, `generate_until()`, and `loglikelihood_rolling()`.

**When to use:** For every benchmark run — lm-eval needs a model object implementing the LM interface.

**Key methods to implement:**
```python
# Source: lm-eval docs/python-api.md [CITED]
from lm_eval.api.model import LM

class MLXBenchmarkModel(LM):
    def __init__(self, model_path: str, adapter_path: str = None):
        super().__init__()
        # Load MLX model + optional LoRA adapter
        ...

    def loglikelihood(self, requests) -> list[tuple[float, bool]]:
        """Return (logprob, is_greedy) for each request."""
        ...

    def generate_until(self, requests) -> list[str]:
        """Generate text until stop condition for each request."""
        ...

    def loglikelihood_rolling(self, requests) -> list[tuple[float, bool]]:
        """Return (logprob, is_greedy) for rolling loglikelihood requests."""
        ...
```

### Pattern 4: Tiered Gating Extension (D-06, D-07, D-08)
**What:** Extend the existing `Benchmarker.gate_check()` pattern from Phase 3 with benchmark-specific gate dimensions. Reuse the consecutive-failure tracking and gate state persistence.

**When to use:** After each benchmark run completes, before marking production-ready.

**Gate dimensions per D-08:**
1. **Scores above threshold**: Per-benchmark, per-category score >= configured minimum
2. **Regression check**: Current score >= (previous_score * (1 - regression_threshold))
3. **Baseline deviation**: Current score >= (baseline_score * (1 - deviation_threshold))

**Production-ready requires 2 of 3 dimensions to pass.**

### Pattern 5: Trend Storage and Diffing (D-11, BMARK-03)
**What:** Append-only JSON per specialist in `artifacts/trends/`. Each run appends a record with: timestamp, benchmark name, per-category scores, model version, quantization config hash. Diff algorithm loads the two most recent records and computes per-benchmark, per-category deltas.

**When to use:** After each benchmark run.

**Schema:**
```json
{
  "niche": "medical",
  "runs": [
    {
      "timestamp": "2026-06-28T14:30:00Z",
      "model_version": "sgfp4-v2-abc123",
      "quantization_config": {...},
      "results": {
        "mmlu": {
          "acc": 0.72,
          "subjects": {
            "anatomy": 0.68,
            "clinical_knowledge": 0.75,
            "...": "..."
          }
        },
        "medmcqa": {"acc": 0.54},
        "pubmedqa": {"acc": 0.62}
      }
    }
  ]
}
```

### Anti-Patterns to Avoid
- **Subprocess lm-eval:** Parsing CLI output is fragile; the Python API returns a structured dict directly.
- **Batch evaluation across specialists:** Each specialist has a different model (different LoRA adapter or base model). Don't try to batch them — run sequentially per specialist.
- **Re-downloading datasets per run:** lm-eval + datasets library cache to `~/.cache/huggingface/`. First run downloads; subsequent runs use cache. Don't implement a separate caching layer.
- **Storing all sample outputs:** `log_samples=True` in `simple_evaluate()` produces massive files (~hundreds of MB). Only use for debugging.
- **Using MMLU aggregate without subcategories:** D-07 requires per-category thresholds. MMLU aggregate alone is insufficient — must capture all 57 subject scores.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| LLM benchmark evaluation | Custom benchmark runner | `lm-eval` v0.4.12 `simple_evaluate()` | 60+ standardized benchmarks, published protocols, comparable scores. Custom runner would miss edge cases in prompting, few-shot sampling, metric aggregation. |
| Dataset download/caching | Custom downloader with manual cache | `datasets` library (HuggingFace) | Handles sharding, streaming, caching, checksums, resume-download. Already a transitive dependency of lm-eval. |
| BLEU/ROUGE scoring | Custom metric implementation | `sacrebleu`, `rouge-score` (lm-eval deps) | Standardized implementations with known tokenization behavior. lm-eval already includes them. |
| Consecutive failure tracking | New gate state system | Extend existing `Benchmarker._gate_state_*` | Phase 3 pattern is proven. Reuse the persistence, corruption recovery, and history truncation logic. |
| Model inference for benchmarks | New inference loop | MLX model loaded directly; lm-eval LM subclass delegates to it | MLX is the project's inference runtime. Don't introduce vLLM or HF inference. |
| Trend diffing/comparison | Custom time-series database | JSON files + in-memory diff algorithm | The data volume is small (~dozens of records per specialist, KB each). A database is overkill. |

**Key insight:** lm-eval-harness is the industry standard for a reason — it handles few-shot sampling, prompt construction, metric aggregation, and decontamination in ways that are hard to get right independently. Custom benchmark runners almost always produce non-comparable scores because they get details wrong (tokenization, prompt format, few-shot selection, metric normalization).

## Runtime State Inventory

> **SKIPPED:** This is a greenfield phase (new benchmark evaluation pipeline). No existing runtime state to migrate. The phase builds ON TOP of Phase 3 artifacts (quantized models in `models/` directory) but does not rename, refactor, or migrate them.

## Common Pitfalls

### Pitfall 1: lm-eval Version Mismatch with Task Definitions
**What goes wrong:** Task YAML format changed between v0.3 and v0.4. v0.3 tasks use Python class-based definitions; v0.4 uses YAML-based. Mixing versions causes silent failures or incorrect results.
**Why it happens:** The lm-eval API is evolving rapidly. Training data may reference v0.3 patterns.
**How to avoid:** Pin `lm-eval==0.4.12`. All custom task YAML files must follow v0.4 YAML format (documented in `docs/new_task_guide.md`).
**Warning signs:** `KeyError` on task config fields, tasks silently returning empty results.

### Pitfall 2: MMLU Few-Shot Sampling Variance
**What goes wrong:** MMLU scores can vary by 1-2% across runs due to few-shot example sampling. This can trigger false regression warnings if not accounted for.
**Why it happens:** MMLU uses `fewshot_split: dev` with `sampler: first_n` in lm-eval's default config. Different samplers produce different scores.
**How to avoid:** Use `sampler: first_n` (deterministic) for reproducibility. Set sensitivity delta at 2% per D-09 to avoid false positives from sampling variance.
**Warning signs:** Score fluctuations of 1-3% between runs with identical models.

### Pitfall 3: MLX Model Loading Overhead in lm-eval
**What goes wrong:** lm-eval expects a Python object that returns logprobs/generations. MLX models need to be loaded, which is expensive. Naive per-task loading can take minutes.
**Why it happens:** MLX model loading is O(model size). Loading the model once per benchmark task (instead of once per specialist) multiplies overhead.
**How to avoid:** Load the MLX model once per specialist, then pass it to `simple_evaluate()` with multiple tasks in the `tasks` list. lm-eval will run all tasks against the same model instance.
**Warning signs:** Benchmark stage takes longer than expected, multiple "Loading model..." messages.

### Pitfall 4: PubMedQA Dataset Structure
**What goes wrong:** PubMedQA's HuggingFace dataset has an unusual structure — the labeled subset uses the `train` split (not `test`), and the answer field may be named `final_decision` or `reasoning_required_pred`.
**Why it happens:** PubMedQA was designed before the standard train/val/test split convention became universal for benchmarks.
**How to avoid:** Verify dataset structure at implementation time. Use `datasets.load_dataset("qiaojin/PubMedQA", "pqa_labeled")` and inspect columns. Test the custom task YAML with `scripts.write_out` before full evaluation. [ASSUMED: dataset field names — verify at implementation time]
**Warning signs:** Empty results, `KeyError` on expected column names.

### Pitfall 5: FRAMES Dataset Availability
**What goes wrong:** FRAMES (Google DeepMind) may not have a publicly available dataset. Research found no HuggingFace dataset entry and no lm-eval task.
**Why it happens:** FRAMES was published as a research paper. The dataset may be available only upon request or through Google's internal systems.
**How to avoid:** Attempt to locate FRAMES dataset at implementation time. If unavailable, fall back to using MMLU alone for the encyclopedic specialist (D-04 still satisfied since MMLU is the universal baseline). Flag as Phase 5 enhancement.
**Warning signs:** No dataset on HuggingFace, no response to dataset access requests.

### Pitfall 6: Google Patents API — No REST Endpoint
**What goes wrong:** Google Patents does not offer a public REST API. Attempts to programmatically access patents.google.com will fail or trigger rate limiting.
**Why it happens:** Google provides patent data through BigQuery public datasets, not a web API.
**How to avoid:** Use Google BigQuery `patents-public-data` dataset. If BigQuery access is not available, fall back to USPTO bulk XML downloads from `bulkdata.uspto.gov`. The BigQuery approach is preferred — it allows targeted SQL queries for specific patent domains rather than downloading terabytes of data.
**Warning signs:** HTTP 403/429 from patents.google.com, no documented API endpoint.

## Code Examples

Verified patterns from official sources:

### simple_evaluate() with Custom Model and Custom Tasks
```python
# Source: lm-eval docs/python-api.md + new_task_guide.md [CITED]
# Verified against lm-eval 0.4.12 installed package
from lm_eval import simple_evaluate
from lm_eval.tasks import TaskManager

# 1. Set up task manager with custom benchmark YAMLs
task_manager = TaskManager(include_path="config/benchmarks")

# 2. Create MLX model wrapper (subclass of lm_eval.api.model.LM)
mlx_model = MLXBenchmarkModel(
    model_path=f"models/specialists_mlx/{niche}/",
    adapter_path=f"models/specialists_mlx/{niche}/adapters.safetensors",
)

# 3. Run evaluation
results = simple_evaluate(
    model=mlx_model,
    tasks=["mmlu", "medmcqa", "pubmedqa"],  # built-in + custom tasks
    num_fewshot=5,            # override per-task below
    batch_size=1,
    task_manager=task_manager,
    log_samples=False,
)

# 4. Access per-benchmark results
for task_name, metrics in results["results"].items():
    print(f"{task_name}: {metrics}")  # e.g., {"acc": 0.72, "acc_stderr": 0.01}
```

### MMLU Subcategory Extraction
```python
# MMLU in lm-eval is a group task. Running "mmlu" returns aggregate + per-subject.
# To get per-subject (per-category per D-07), run individual subjects:
mmlu_subjects = [
    "mmlu_anatomy", "mmlu_astronomy", "mmlu_clinical_knowledge",
    "mmlu_college_biology", "mmlu_college_medicine", "mmlu_professional_medicine",
    "mmlu_medical_genetics", "mmlu_nutrition", "mmlu_virology",
    # ... all 57 subjects
]
# Or use the group directly: "mmlu" task returns all subjects aggregated.
# The group result includes per-subtask metrics in the results dict.
results = simple_evaluate(model=mlx_model, tasks=["mmlu"], num_fewshot=5, ...)
# results["results"]["mmlu"] contains aggregate acc
# results["results"]["mmlu_anatomy"] contains per-subject acc
```

### Trend Diff Algorithm
```python
# Source: Phase 04 design (Claude's discretion area)
# Compares two most recent runs, flags degradation per D-09 thresholds
def compute_trend_deltas(trend_file: Path) -> dict:
    """Load trend file, diff two most recent runs."""
    with open(trend_file) as f:
        data = json.load(f)

    runs = data["runs"]
    if len(runs) < 2:
        return {"status": "insufficient_data", "deltas": {}}

    prev = runs[-2]["results"]
    curr = runs[-1]["results"]

    deltas = {}
    for benchmark_name in curr:
        if benchmark_name not in prev:
            continue  # new benchmark, no delta
        deltas[benchmark_name] = {
            metric: curr[benchmark_name][metric] - prev[benchmark_name][metric]
            for metric in curr[benchmark_name]
            if isinstance(curr[benchmark_name][metric], (int, float))
        }

    return {"status": "ok", "deltas": deltas}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| lm-eval v0.3 (Python class tasks) | lm-eval v0.4 (YAML tasks + `simple_evaluate()`) | 2024 | Custom tasks are YAML-based, no Python classes needed. Breaking changes to task format. |
| MMLU as primary LLM benchmark | MMLU-Pro, MMLU-Redux emerging | 2024-2025 | Original MMLU is saturating (>90% for frontier models). For POC, original MMLU is sufficient — our quantized models will score far below saturation. |
| HumanEval pass@1 | HumanEval+, SWE-Bench for harder eval | 2024 | HumanEval is saturating for frontier models. Still valid for quantized specialist models where performance is expected to be lower. |
| Manual benchmark threshold setting | Per-benchmark sensitivity deltas (D-09) | Phase 04 design | Config-driven deltas replace hardcoded "5% drop is bad" heuristic. |

**Deprecated/outdated:**
- **lm-eval CLI as primary interface:** The Python API (`simple_evaluate()`) is now the recommended programmatic interface. CLI is for ad-hoc use only.
- **HuggingFace `evaluate` library as standalone:** Now integrated as lm-eval dependency; don't import directly unless needed for custom metric computation.
- **MMLU-Pro for this POC:** MMLU-Pro is harder but less standardized. Original MMLU provides better comparability with published baselines.

## Assumptions Log

> List all claims tagged `[ASSUMED]` in this research. The planner and discuss-phase use this section to identify decisions that need user confirmation before execution.

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | PubMedQA HuggingFace dataset ID is `qiaojin/PubMedQA` with config `pqa_labeled` and `train` split | Standard Stack, Code Examples | Custom task YAML will fail to load dataset; needs manual verification of actual dataset path and column names |
| A2 | FRAMES dataset is NOT publicly available on HuggingFace (negative claim from search) | Common Pitfalls #5 | If FRAMES IS actually available, encyclopedic specialist gets a domain benchmark. If not, fall back to MMLU-only. |
| A3 | Google Patents BigQuery `patents-public-data` dataset is accessible and suitable for benchmark evaluation | Common Pitfalls #6 | If BigQuery access requires payment or the schema doesn't support QA-style evaluation, Google Patents benchmark may not be feasible |
| A4 | `lm-eval` v0.4.12 supports passing a custom `TaskManager` with `include_path` to `simple_evaluate()` | Architecture Patterns | If the API has changed, custom tasks need a different loading mechanism |
| A5 | MMLU group task in lm-eval returns per-subject results accessible via `results["results"]["mmlu_<subject>"]` | Code Examples | Per-category thresholds (D-07) require per-subject scores; if lm-eval only returns aggregate, subjects must be enumerated individually |
| A6 | DeepSeek v4 Pro API supports remote model evaluation (benchmark_source: api mode per D-01) | Architecture Patterns | If the API doesn't support evaluation-as-a-service, the `api` benchmark source mode is not viable |
| A7 | MLX model can be wrapped in `lm_eval.api.model.LM` without significant performance degradation | Architecture Patterns | If lm-eval's LM interface is incompatible with MLX's execution model (e.g., batching expectations), a shim layer may be needed |
| A8 | Google Cloud BigQuery Python client (`google-cloud-bigquery`) is installable and compatible with the project's Python environment | Standard Stack | If BigQuery SDK has conflicts with existing dependencies, fall back to USPTO bulk XML download |

## Open Questions

1. **FRAMES dataset availability**
   - What we know: FRAMES is a Google DeepMind benchmark for factuality + multi-hop retrieval. No HuggingFace dataset found. No lm-eval task.
   - What's unclear: Is the dataset publicly downloadable? Is there an access request process?
   - Recommendation: Attempt to locate at implementation time. If unavailable after reasonable effort, treat as Phase 5 deferral. Encyclopedic specialist falls back to MMLU-only (D-04 satisfied since MMLU is the universal baseline).

2. **DeepSeek v4 Pro API evaluation mode (D-01 `api` source)**
   - What we know: D-01 specifies `api` mode where DeepSeek v4 Pro API evaluates models. The API exists (used by the TeacherClient in Phase 1).
   - What's unclear: Does DeepSeek v4 Pro offer "evaluate a model against benchmarks" as an API endpoint? Or does `api` mode mean "use DeepSeek as the evaluation judge"?
   - Recommendation: Clarify with user. If the API supports benchmark evaluation, document endpoint and format. If not, `api` mode may mean "send model outputs to DeepSeek for scoring" rather than "DeepSeek runs the benchmarks."

3. **Google Patents benchmark design**
   - What we know: D-05 maps patents specialist to BIGPATENT + Google Patents. BIGPATENT is a summarization task. Google Patents has no standard benchmark format.
   - What's unclear: What exactly is the "Google Patents" benchmark? Is it a retrieval task? A QA task? A classification task?
   - Recommendation: Define the Google Patents evaluation task explicitly. If it's retrieval-based QA, design a custom dataset from BigQuery patent data. If undefined, treat as a custom benchmark requiring dataset construction.

4. **PubMedQA 3-way classification vs lm-eval multiple_choice**
   - What we know: PubMedQA answers are yes/no/maybe (3-way). lm-eval's `multiple_choice` output type typically expects A/B/C/D format.
   - What's unclear: Does lm-eval's `multiple_choice` support 3-option tasks natively? Does the `acc` metric handle yes/no/maybe normalization?
   - Recommendation: Test with a minimal PubMedQA YAML task before full implementation. Verify metric output format matches expectations.

## Environment Availability

> Skip this section if the phase has no external dependencies (code/config-only changes).

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11+ | All benchmark scripts | Yes | 3.11 | — |
| pip | Package installation | Yes | 25.2 | — |
| `lm-eval` | Benchmark evaluation engine | Installed | 0.4.12 | — |
| `datasets` | HF dataset download/cache | Installed | 4.0.0 | — |
| MLX | Model inference for benchmarks | In requirements.txt | >=0.14.0 | — |
| Google Cloud BigQuery | Google Patents data access | NOT checked | — | USPTO bulk XML download from bulkdata.uspto.gov |
| HuggingFace Hub (network) | Dataset download | Assumed yes | — | Pre-download to local mode |
| DeepSeek v4 Pro API | `api` benchmark source mode | Assumed yes | — | Fall back to `huggingface` or `local` mode |

**Missing dependencies with no fallback:** none (all core deps verified installed)
**Missing dependencies with fallback:**
- Google Cloud BigQuery: fall back to USPTO bulk data if unavailable

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest >=8.0.0 |
| Config file | none — see Wave 0 |
| Quick run command | `python -m pytest tests/eval/test_benchmark_config.py -x -q` |
| Full suite command | `python -m pytest tests/eval/ -x -q` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| BMARK-01 | lm-eval integration loads MMLU task and runs against MLX model, returns valid scores | unit | `pytest tests/eval/test_benchmark_runner.py::test_lm_eval_mmlu_integration -x` | No (Wave 0) |
| BMARK-01 | Custom PubMedQA YAML task loads dataset and produces acc metric | unit | `pytest tests/eval/test_benchmark_tasks.py::test_custom_pubmedqa_task -x` | No (Wave 0) |
| BMARK-01 | Benchmark results written to artifacts/benchmarks/ with expected schema | unit | `pytest tests/eval/test_benchmark_runner.py::test_results_persistence -x` | No (Wave 0) |
| BMARK-02 | gate_check returns passed=False when MMLU score below configured threshold | unit | `pytest tests/eval/test_benchmarker.py::test_gate_check_below_threshold -x` | No (Wave 0) |
| BMARK-02 | Consecutive failures trigger blocking state after N failures | unit | `pytest tests/eval/test_benchmarker.py::test_consecutive_failure_blocking -x` | No (Wave 0) |
| BMARK-02 | 2-of-3 composite gate correctly evaluates (scores, regression, deviation) | unit | `pytest tests/eval/test_benchmarker.py::test_composite_gate_2_of_3 -x` | No (Wave 0) |
| BMARK-03 | Trend storage appends run record to per-specialist trend file | unit | `pytest tests/eval/test_benchmark_trends.py::test_trend_append -x` | No (Wave 0) |
| BMARK-03 | Trend diff computes per-benchmark deltas between two most recent runs | unit | `pytest tests/eval/test_benchmark_trends.py::test_trend_diff_deltas -x` | No (Wave 0) |
| BMARK-03 | Degradation flags triggered when score drop exceeds sensitivity delta | unit | `pytest tests/eval/test_benchmark_trends.py::test_degradation_detection -x` | No (Wave 0) |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/eval/test_benchmark_config.py tests/eval/test_benchmark_trends.py -x -q`
- **Per wave merge:** `python -m pytest tests/eval/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/eval/test_benchmark_runner.py` — covers BMARK-01 lm-eval integration, results persistence
- [ ] `tests/eval/test_benchmark_tasks.py` — covers BMARK-01 custom task YAML loading, PubMedQA/BIGPATENT task validation
- [ ] `tests/eval/test_benchmarker.py` — covers BMARK-02 gate checking, consecutive failures, composite gate 2-of-3 logic
- [ ] `tests/eval/test_benchmark_trends.py` — covers BMARK-03 trend storage, diff deltas, degradation detection
- [ ] `tests/eval/test_benchmark_config.py` — covers BMARK-01 config loading, per-benchmark YAML validation
- [ ] `tests/eval/conftest.py` — shared fixtures: mock MLX model, sample benchmark results, temp trend files
- [ ] Framework install: `pip install pytest>=8.0.0` — already in requirements.txt, but verify pytest is available in test environment

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | Benchmark evaluation runs locally, no user auth needed |
| V3 Session Management | No | No user sessions in benchmark pipeline |
| V4 Access Control | No | Single-machine execution, no multi-user access |
| V5 Input Validation | Yes | Benchmark YAML configs, dataset inputs, model outputs must be validated before storage |
| V6 Cryptography | No | No cryptographic operations in benchmark evaluation |

### Known Threat Patterns for Benchmark Evaluation

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malformed YAML config causing arbitrary code execution | Tampering | Use `yaml.safe_load()` (already in pipeline.yaml loading pattern); no `yaml.load()` with unsafe constructors |
| Dataset poisoning (compromised HF dataset with malicious payloads) | Tampering | Pin dataset versions via lm-eval YAML `metadata.version`; checksum verification via `datasets` library |
| Benchmark result tampering (manual edit of results JSON to pass gates) | Tampering | Store manifest hash alongside results (reuse Phase 3 QUANT-03 pattern); gate state in `artifacts/.gate_state/` directory |
| Prompt injection via dataset text | Spoofing | Datasets contain academic text, not user input; risk is minimal for benchmark evaluation. Use lm-eval's built-in `should_decontaminate` where available. |
| Information disclosure via benchmark results | Information Disclosure | Benchmark scores reveal model capabilities but not training data. Acceptable for POC. |

## Sources

### Primary (HIGH confidence)
- [lm-eval PyPI] - Package verified on PyPI v0.4.12, slopcheck [OK], installed and inspected. Task names confirmed via `TaskManager.all_tasks` enumeration.
- [lm-eval docs/python-api.md] - `simple_evaluate()` API signature, custom model integration pattern, return format. [CITED]
- [lm-eval docs/new_task_guide.md] - Custom YAML task creation, `include_path`, `TaskManager`, Jinja2 templates. [CITED]
- [lm-eval installed package task YAMLs] - MMLU default template (no num_fewshot in default, uses `sampler: first_n`), HumanEval `num_fewshot: 0`, GPQA `num_fewshot: 0` for zeroshot variants. Verified via direct file inspection.

### Secondary (MEDIUM confidence)
- [HuggingFace Datasets Hub] - Dataset availability confirmed: `cais/mmlu`, `openai/openai_humaneval`, `medmcqa`, `qiaojin/PubMedQA`, `Idavidrein/gpqa`, `big_patent`. [CITED from WebSearch + training knowledge]
- [Papers With Code / Open LLM Leaderboard] - Baseline thresholds: MMLU random 25%, expert ~89.8%. HumanEval pass@1 random ~0%, SOTA ~92%+. Attempted fetch, page content was loading state. [MEDIUM — baseline ranges confirmed by multiple training-knowledge sources but not verified against current leaderboard]

### Tertiary (LOW confidence)
- [WebSearch] - MedMCQA published scores (random 25%, SOTA 60-70%+) — multiple training-knowledge sources agree but not verified against current leaderboard.
- [WebSearch] - GPQA scores (human experts ~65-69%, SOTA ~50-59%) — from training knowledge, not verified.
- [WebSearch] - BIGPATENT ROUGE scores (PEGASUS ROUGE-1 52.7, ROUGE-L 43.4) — from training knowledge, not verified.
- [WebSearch] - Google Patents API availability (no official REST API) — negative claim from WebSearch, not confirmed via Google documentation.
- [WebSearch] - FRAMES dataset availability — negative claim (not found on HuggingFace), not confirmed via Google DeepMind.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — lm-eval v0.4.12 verified on PyPI, installed, slopcheck [OK], task names confirmed by enumeration, API docs fetched.
- Architecture: MEDIUM — lm-eval Python API integration pattern is well-documented. MLX model wrapper approach is [ASSUMED] (A7). Custom tasks for PubMedQA/BIGPATENT follow documented patterns but dataset field names are [ASSUMED] (A1).
- Pitfalls: MEDIUM — FRAMES availability and Google Patents API are LOW confidence (A2, A3). MMLU sampling variance and MLX loading overhead are HIGH confidence (based on lm-eval docs and MLX runtime characteristics).

**Research date:** 2026-06-28
**Valid until:** 2026-07-28 (30 days — stable libraries, but FRAMES/Google Patents may need re-checking)
