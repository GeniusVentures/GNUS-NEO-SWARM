# gnus-poc ELM Training & Distillation Pipeline — Architecture

**Project:** GNUS-NEO-SWARM v1.1 ELM Pipeline (gnus-poc)
**Researched:** 2026-05-27
**Confidence:** HIGH (existing code analyzed, all integration points mapped)

---

## 1. Current State (Ground Truth)

### What Exists

**C++ codebase (`src/`):** 4 stub files only — `elm_base.h/cpp` (hello world) + `genius_elm_chat_c.h/cpp` (FFI stub). The elaborate architecture in `.planning/codebase/ARCHITECTURE.md` (router, specialists, FP4 codec, etc.) does NOT exist in code. These are aspirational design docs for Phase 4+.

**Python POC (`gnus-poc/`):** 5 working scripts, flat layout, no tests:

| Script | What It Does | Output |
|--------|-------------|--------|
| `data/analyze_common_pile.py` | TF-IDF + k-means niche discovery | `data/analysis/niches.json`, `cluster_map.pkl` |
| `data/extract_source_niches.py` | Source-label niche extraction | `data/analysis/source_based_niches.json` |
| `data/prepare_datasets.py` | Train/val/test splits + Qwen2.5 formatting (5 niches) | `data/specialists/<niche>/` (HF), `<niche>_mlx/` (JSONL) |
| `models/train_specialists.py` | LoRA on Qwen3-7B-Instruct via mlx-lm | `models/specialists/<niche>/adapters.safetensors` |
| `models/train_specialists_mlx.py` | LoRA on Qwen3-30B-A3B (MoE) via mlx-lm | `models/specialists_mlx/<niche>/adapters.safetensors` |

5 niches (medical, qa_technical, code, encyclopedic, patents) have full train/val/test splits and trained adapters. All artifacts gitignored.

### What's Missing (v1.1)

- Teacher-driven synthetic data (DeepSeek v4 pro API)
- Knowledge distillation (logit transfer, subspace extraction)
- Per-specialist evaluation (accuracy, latency, perplexity)
- Orchestration layer (pipeline runner, experiment tracking)
- FP4 quantization pipeline for deployed specialists
- Experimentation framework (A/B test LoRA ranks, layers, prompts)
- Configuration management (YAML configs)
- Structured artifact storage
- API abstraction (DeepSeek client with retry/backoff/cost tracking)
- Any tests

---

## 2. Proposed Directory Tree

```
gnus-poc/
├── pipeline/              # NEW — Orchestration
│   ├── __init__.py
│   ├── pipeline.py        # PipelineRunner: coordinates all stages
│   └── experiment.py      # ExperimentTracker: logs, metadata, A/B variants
│
├── distill/               # NEW — Teacher API + knowledge distillation
│   ├── __init__.py
│   ├── teacher.py         # DeepSeek v4 pro client (retry/backoff/cost tracking)
│   ├── synthetic.py       # SyntheticDataGenerator: teacher → instruction/response pairs
│   └── distillation.py    # Distiller: logit transfer, subspace extraction
│
├── training/              # REFACTOR from models/
│   ├── __init__.py
│   ├── config.py          # TrainingConfig dataclass (replaces scattered OVERRIDES dicts)
│   ├── train_specialists.py       # Qwen3-7B (moved from models/, secondary)
│   └── train_specialists_mlx.py   # Qwen3-30B-A3B (moved from models/, PRIMARY)
│
├── eval/                  # NEW — Evaluation & benchmarking
│   ├── __init__.py
│   ├── evaluate.py        # Evaluator: accuracy/perplexity/latency per specialist
│   └── benchmark.py       # Benchmarker: head-to-head comparison across variants
│
├── quantize/              # NEW — FP4 quantization + C++ engine export
│   ├── __init__.py
│   └── fp4_export.py      # FP4Exporter: safetensors → FP4 binary + metadata JSON
│
├── data/                  # EXISTING — restructured
│   ├── scripts/           # MOVED from data/
│   │   ├── analyze_common_pile.py
│   │   ├── extract_source_niches.py
│   │   └── prepare_datasets.py
│   ├── analysis/          # Gitignored: niches.json, cluster_map.pkl
│   ├── specialists/       # Gitignored: HF datasets per niche
│   ├── specialists_mlx/   # Gitignored: JSONL data per niche
│   └── synthetic/         # Gitignored: teacher-generated data (NEW)
│
├── models/                # EXISTING — gitignored
│   └── specialists_mlx/   # Trained LoRA safetensors per niche
│
├── config/                # NEW — YAML configuration
│   ├── pipeline.yaml      # Global: model paths, API key env-var refs, defaults
│   ├── specialists/       # Per-specialist: medical.yaml, code.yaml, etc.
│   └── experiments/       # Per-run experiment overrides for A/B testing
│
├── artifacts/             # NEW — gitignored, structured outputs for C++ engine
│   ├── adapters/          # FP4 binaries (*_fp4.bin + *_fp4_meta.json)
│   │   ├── manifest.json  # Specialist catalog for C++ engine
│   │   └── subspace_vectors.npy  # Niche embedding vectors for C++ router
│   ├── eval_results/      # Per-specialist evaluation JSON reports
│   └── experiment_logs/   # Pipeline run logs (per run_id/)
│
├── tests/                 # NEW — test suite
│   ├── unit/              # test_teacher.py, test_synthetic.py, test_fp4_export.py, etc.
│   ├── integration/       # test_synthetic_to_training.py, test_full_pipeline.py
│   ├── fixtures/          # mock_teacher_responses.json, tiny_dataset.jsonl
│   └── conftest.py        # Shared pytest fixtures
│
├── .venv/                 # Virtual environment (gitignored)
├── requirements.txt       # Python dependencies
├── pyproject.toml         # Package metadata + tool config (pytest, ruff)
└── README.md              # POC-specific docs
```

---

## 3. Data Flow

```
                              ┌─────────────────────┐
                              │  Common Pile (HF)    │
                              └──────────┬──────────┘
                                         │
                    ┌────────────────────┼────────────────────┐
                    ▼                    ▼                    ▼
           ┌───────────────┐   ┌───────────────┐   ┌───────────────┐
           │ Niche          │   │ Source-Based   │   │ Synthetic     │
           │ Discovery      │   │ Extraction     │   │ Data Gen      │
           │ (clustering)   │   │ (metadata)     │   │ (teacher API) │
           └───────┬───────┘   └───────┬───────┘   └───────┬───────┘
                   │                   │                   │
                   ▼                   ▼                   ▼
           data/analysis/      data/analysis/        data/synthetic/
           niches.json         source_based_niches   <niche>/*.jsonl
                   │                   │                   │
                   └─────────┬─────────┘                   │
                             ▼                             │
                    ┌──────────────────┐                   │
                    │  Dataset Prep    │◄──────────────────┘
                    │  (augment with   │
                    │   synthetic if   │
                    │   available)     │
                    └────────┬─────────┘
                             │
                             ▼
                    data/specialists/<niche>_mlx/
                    {train,valid,test}.jsonl
                             │
                             ▼
                    ┌──────────────────┐
                    │  LoRA Training   │
                    │  (mlx-lm)        │
                    └────────┬─────────┘
                             │
                             ▼
                    models/specialists_mlx/<niche>/
                    adapters.safetensors + adapter_config.json
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
     ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
     │ Distillation │ │ Evaluation   │ │ FP4 Export   │
     │ (logit xfer, │ │ (accuracy,   │ │ (quantize +  │
     │  subspace)   │ │  perplexity, │ │  package)    │
     │              │ │  latency)    │ │              │
     └──────┬───────┘ └──────┬───────┘ └──────┬───────┘
            │                │                │
            ▼                ▼                ▼
     artifacts/        artifacts/        artifacts/adapters/
     subspace_vecs     eval_results/     <niche>_fp4.bin
     .npy              <niche>_eval.json <niche>_fp4_meta.json
                                                │
                                                ▼
                                       ┌──────────────────┐
                                       │  C++ Engine       │
                                       │  (Phase 4: load   │
                                       │   FP4 adapters,   │
                                       │   inference via   │
                                       │   MNN/Vulkan)     │
                                       └──────────────────┘
```

**Key decisions:**
- Synthetic data **augments** (not replaces) source-extracted data. Pipeline runs without teacher API using source-extracted data alone.
- Distillation is optional — skips with warning if teacher API unavailable.
- FP4 export is the hard integration point with C++. Binary format must match the planned `FP4Codec` spec.

---

## 4. Module Boundaries & Interfaces

### 4.1 `pipeline/` — Orchestration (NEW)

Top-level pipeline runner. Owns the lifecycle: config → stage execution → logging → artifact collection. No ML logic.

```python
@dataclass
class PipelineConfig:
    specialists: List[str]
    teacher_api_key: Optional[str]        # None = skip teacher stages
    teacher_model: str
    training_base_model: str
    lora_config: TrainingConfig
    distillation_enabled: bool
    eval_enabled: bool
    fp4_export_enabled: bool
    output_dir: Path

class PipelineRunner:
    def __init__(self, config: PipelineConfig) -> None: ...
    def run(self) -> PipelineResult: ...
    def run_stage(self, stage_name: str) -> StageResult: ...

class ExperimentTracker:
    def start_run(self, config: PipelineConfig) -> str: ...  # Returns run_id
    def log_stage(self, run_id: str, stage: str, result: StageResult) -> None: ...
    def complete_run(self, run_id: str) -> None: ...
```

### 4.2 `distill/` — Teacher API + Distillation (NEW)

Depends on external DeepSeek API. Must degrade gracefully when unavailable.

```python
class TeacherClient:
    """DeepSeek v4 pro API client. OpenAI-compatible endpoint."""
    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> TeacherResponse: ...
    def batch_generate(self, prompts: List[str],
                       system_prompt: Optional[str] = None) -> List[TeacherResponse]: ...
    def get_cost_summary(self) -> CostSummary: ...

class SyntheticDataGenerator:
    """Generates instruction/response pairs per niche from teacher."""
    def generate_for_niche(self, niche_name: str, num_samples: int = 1000) -> Path: ...
    def augment_dataset(self, niche_name: str, original_data_dir: Path) -> Path: ...

class Distiller:
    """Logit transfer + subspace extraction for C++ router."""
    def distill(self, teacher: TeacherClient, student_adapter_path: Path,
                niche_name: str) -> DistillationResult: ...
    def extract_subspace_vector(self, adapter_path: Path) -> np.ndarray: ...
```

### 4.3 `training/` — LoRA Training (REFACTOR from models/)

```python
@dataclass
class TrainingConfig:
    """Single source of truth for all LoRA hyperparams."""
    fine_tune_type: str = "lora"
    optimizer: str = "adamw"
    batch_size: int = 4
    iterations: int = 1000
    learning_rate: float = 1e-5
    num_layers: int = 16
    lora_rank: int = 16
    lora_dropout: float = 0.05
    lora_scale: float = 20.0
    seed: int = 42
    # ... (full set of 18 params from existing OVERRIDES dicts)

class SpecialistTrainer:
    def __init__(self, config: TrainingConfig) -> None: ...
    def train(self, niche_name: str, base_model: str,
              data_dir: Path, output_dir: Path) -> TrainingResult: ...
    def train_all(self, configs: Dict[str, SpecialistConfig]) -> Dict[str, TrainingResult]: ...
```

### 4.4 `eval/` — Evaluation (NEW)

```python
@dataclass
class EvalResult:
    niche: str
    accuracy: float
    perplexity: float
    avg_latency_ms: float
    parameter_count: int
    adapter_size_bytes: int
    comparison_to_baseline: Optional[float]

class Evaluator:
    def evaluate(self, adapter_path: Path, test_data_dir: Path,
                 niche_name: str) -> EvalResult: ...

class Benchmarker:
    def benchmark(self, specialists: List[EvalResult]) -> BenchmarkReport: ...
```

### 4.5 `quantize/` — FP4 Export (NEW) **CRITICAL C++ INTEGRATION POINT**

```python
@dataclass
class FP4ExportResult:
    niche: str
    binary_path: Path
    metadata_path: Path
    original_size_bytes: int
    compressed_size_bytes: int
    compression_ratio: float

class FP4Exporter:
    """
    Converts LoRA safetensors to FP4-packed binary for C++ FP4Codec.

    Binary format (per weight matrix, little-endian):
      Header: [num_rows: uint32, num_cols: uint32, scale_factor: float32]
      Body:   fp4_packed_weights (2 weights per byte)
    """
    def export_adapter(self, adapter_path: Path, niche_name: str) -> FP4ExportResult: ...
    def export_all(self, adapter_dir: Path) -> List[FP4ExportResult]: ...
    def write_manifest(self, results: List[FP4ExportResult]) -> Path: ...
```

---

## 5. Integration Points

### 5.1 With Existing Python (gnus-poc/)

| Existing File | Action | New Path | Rationale |
|--------------|--------|----------|-----------|
| `data/analyze_common_pile.py` | **Move** + fix paths | `data/scripts/analyze_common_pile.py` | Preserves working code |
| `data/extract_source_niches.py` | **Move** + fix paths | `data/scripts/extract_source_niches.py` | Same |
| `data/prepare_datasets.py` | **Move** + fix paths | `data/scripts/prepare_datasets.py` | Later: add `--synthetic-data` flag |
| `models/train_specialists.py` | **Move** | `training/train_specialists.py` | 7B variant, secondary |
| `models/train_specialists_mlx.py` | **Move** + refactor | `training/train_specialists_mlx.py` | PRIMARY; extract TrainingConfig |
| `models/train_specialists-old.py` | **Delete** | — | Exact duplicate |
| `data/specialists/`, `data/specialists_mlx/`, `models/specialists_mlx/` | **Keep** (gitignored) | Same | Existing artifacts |

### 5.2 With C++ Engine (Phase 4)

| Integration Point | Python Producer | C++ Consumer | Contract |
|-------------------|----------------|--------------|----------|
| FP4 adapter binaries | `FP4Exporter.export_adapter()` | `FP4Codec` (planned, `src/core/fp4/`) | Binary format spec (Section 4.5) |
| Specialist manifest | `FP4Exporter.write_manifest()` | `GeniusAPIServer` / specialist loader | JSON schema (Section 5.3) |
| Subspace vectors | `Distiller.extract_subspace_vector()` | Router (planned, `src/router/`) | `.npy` float32, one per specialist |
| Tokenizer config | Copied from mlx-lm cache | `SentencePieceTokenizer` | JSON tokenizer config |
| Niche metadata | `source_based_niches.json` | Router config | JSON — niche descriptions, sources |

### 5.3 C++ Manifest Format (Contract)

```json
{
  "version": "1.0.0",
  "generated_at": "2026-05-27T12:00:00Z",
  "pipeline_run_id": "run_001",
  "base_model": "mlx-community/Qwen3-30B-A3B-Instruct-2507-bf16",
  "tokenizer_config": "qwen3_tokenizer.json",
  "specialists": [
    {
      "name": "medical",
      "adapter_binary": "medical_fp4.bin",
      "adapter_metadata": "medical_fp4_meta.json",
      "subspace_vector": "subspace_vectors.npy",
      "subspace_index": 0,
      "niche_description": "Medical research, clinical studies, biomedical science",
      "base_layers": ["model.layers.0", "model.layers.1", "model.layers.15"],
      "lora_rank": 16,
      "lora_alpha": 20.0,
      "eval_accuracy": 0.92,
      "eval_perplexity": 3.4,
      "compressed_size_bytes": 245760,
      "original_size_bytes": 983040,
      "compression_ratio": 4.0
    }
  ]
}
```

---

## 6. Configuration Management

**Principle:** YAML, hierarchical (global → specialist → experiment overrides), env vars for secrets.

### `config/pipeline.yaml` (Global)

```yaml
pipeline:
  specialists: ["medical", "qa_technical", "code", "encyclopedic", "patents"]

teacher:
  model: "deepseek-v4-pro"
  api_key_env: "DEEPSEEK_API_KEY"          # Resolved from env at load time
  max_tokens: 4096
  temperature: 0.7
  max_retries: 3
  backoff_base_seconds: 2.0

training:
  base_model: "mlx-community/Qwen3-30B-A3B-Instruct-2507-bf16"
  batch_size: 4
  iterations: 1000
  learning_rate: 1e-5
  lora_rank: 16

evaluation:
  test_split: "test"
  metrics: ["accuracy", "perplexity", "latency"]

fp4_export:
  target_bits: 4
  block_size: 64

artifacts:
  base_dir: "artifacts"
```

### `config/specialists/medical.yaml` (Per-Specialist)

```yaml
specialist:
  name: "medical"
  base_model: "mlx-community/Qwen3-30B-A3B-Instruct-2507-bf16"
  niche_sources: ["PubMed Abstracts", "PubMed Central", "NIH ExPorter"]
  system_prompt: "You are a medical research specialist."
  synthetic_prompts:
    - "Explain the mechanism of action for a novel drug target in oncology."
    - "Summarize recent advances in CRISPR-based gene therapy."
  training:
    lora_rank: 16
    iterations: 1000
```

### `config/experiments/example_experiment.yaml` (Experiment Override)

```yaml
experiment:
  id: "exp_lora_rank_32"
  description: "Test rank-32 LoRA vs baseline rank-16 on medical and code"
  overrides:
    medical:
      training:
        lora_rank: 32
    code:
      training:
        lora_rank: 32
```

**Loading logic:** `PipelineRunner` loads `pipeline.yaml` → merges per-specialist configs → applies experiment overrides. API keys resolved from `${VAR_NAME}` at load time.

---

## 7. Build Order (7 Phases)

### Phase A: Foundation (wiring + refactor)
No new ML logic. Safe — existing scripts still run.

1. Create all new directories
2. Move existing scripts to new locations; fix relative paths
3. Delete `models/train_specialists-old.py`
4. Create `config/pipeline.yaml` + per-specialist configs
5. Create `requirements.txt`, `pyproject.toml`
6. Set up `tests/conftest.py`
7. Update `.gitignore`: `artifacts/`, `data/synthetic/`, `tests/__pycache__/`

### Phase B: Teacher API (`distill/`)
1. `teacher.py` — `TeacherClient` with retry/backoff/cost tracking
2. `synthetic.py` — `SyntheticDataGenerator`
3. `tests/unit/test_teacher.py` (mock responses)
4. `tests/fixtures/mock_teacher_responses.json`

### Phase C: Pipeline Orchestration
1. `pipeline.py` — `PipelineRunner`
2. `experiment.py` — `ExperimentTracker`
3. `training/config.py` — `TrainingConfig` dataclass
4. `tests/unit/test_pipeline.py`
5. `tests/integration/test_synthetic_to_training.py`

### Phase D: Evaluation
1. `evaluate.py` — `Evaluator`
2. `benchmark.py` — `Benchmarker`
3. `tests/unit/test_evaluate.py`
4. `tests/integration/test_training_to_eval.py`

### Phase E: Knowledge Distillation
1. `distillation.py` — `Distiller`
2. `tests/unit/test_distillation.py`

### Phase F: FP4 Export (C++ Integration)
1. `fp4_export.py` — `FP4Exporter`
2. `tests/unit/test_fp4_export.py` (roundtrip test)
3. Align with C++ `FP4Codec` spec

### Phase G: Integration Testing
1. `tests/integration/test_full_pipeline.py`
2. `tests/fixtures/tiny_dataset.jsonl` (10-sample test dataset)
3. CI-compatible: mock teacher, skip GPU training

---

## 8. Key Architectural Decisions

### 8.1 Flat modules, not a pip package
gnus-poc is a POC pipeline, not a library. `pyproject.toml` for deps/tooling only. The exit strategy is artifacts (FP4 binaries, manifest JSON), not a Python API.

### 8.2 YAML configs, not JSON or Python
Comments document hyperparameter choices. Anchors share configs across specialists. Human-editable by domain experts. Env-var interpolation keeps secrets out of committed files.

### 8.3 Augment (not replace) source data with synthetic
Source-extracted data provides grounded domain knowledge. Synthetic data adds instruction-following format and fills gaps. Both together > either alone.

### 8.4 FP4 export at pipeline end
C++ engine doesn't understand safetensors. FP4 is the bridge. Doing quantization in Python means: (a) done once in training pipeline, (b) C++ just loads pre-quantized adapters, (c) size verified before handoff.

### 8.5 `models/` != `artifacts/`
`models/` = raw training outputs (debugging/retraining). `artifacts/` = final packaged FP4 binaries for C++. Different consumers, different lifecycle.

### 8.6 `config/` at top level
Pipeline config spans all modules. Single load at pipeline start (global + specialist-specific + experiment override) is simpler than per-module config files.

---

## 9. Anti-Patterns to Avoid

### 9.1 Hardcoded paths in moved scripts
**What:** `OUTPUT_DIR = "data/analysis"` relative to script location.
**Fix:** Use `Path(__file__).parent.parent / "analysis"` or accept output dir as config/CLI argument.

### 9.2 Duplicate training configs
**What:** `train_specialists.py` and `train_specialists_mlx.py` each have their own `OVERRIDES` dict.
**Fix:** Extract `TrainingConfig` into `training/config.py` — single source of truth.

### 9.3 Teacher API hard-dependency
**What:** Pipeline breaks without API key.
**Fix:** Stages check `teacher_api_key is not None`; skip with warning if unavailable. Pipeline reports skipped stages.

### 9.4 Ignoring C++ interface
**What:** Designing FP4 binary format without C++ alignment.
**Fix:** Binary format spec in Section 4.5. Roundtrip test in Phase F validates contract.

### 9.5 Non-Apple-Silicon training
**What:** mlx-lm requires Apple Silicon.
**Fix:** Hard requirement documented. Tests mock training. CI skips GPU stages.

### 9.6 Forgetting gitignore
**What:** New directories without gitignore = accidental large binary commits.
**Fix:** Update `.gitignore` in Phase A for `artifacts/`, `data/synthetic/`, `tests/__pycache__/`.

---

## 10. New vs Modified Files Summary

| Category | New Files | Modified/Moved | Deleted |
|----------|-----------|----------------|---------|
| `pipeline/` | 3 (`__init__.py`, `pipeline.py`, `experiment.py`) | — | — |
| `distill/` | 4 (`__init__.py`, `teacher.py`, `synthetic.py`, `distillation.py`) | — | — |
| `training/` | 2 (`__init__.py`, `config.py`) | 2 (from `models/`) | — |
| `eval/` | 3 (`__init__.py`, `evaluate.py`, `benchmark.py`) | — | — |
| `quantize/` | 2 (`__init__.py`, `fp4_export.py`) | — | — |
| `data/` | 1 (`scripts/__init__.py`) | 3 (from `data/`) | — |
| `config/` | 7 (pipeline.yaml + 5 specialists + 1 experiment) | — | — |
| `artifacts/` | 0 (all generated, gitignored) | — | — |
| `tests/` | ~12 (unit + integration + fixtures + conftest) | — | — |
| Root | 2 (`requirements.txt`, `pyproject.toml`) | 1 (`.gitignore`) | 1 (`train_specialists-old.py`) |

**Total: ~34 new, 6 modified, 1 deleted.**

---

*Architecture research: 2026-05-27. All integration points validated against existing codebase.*
