# Technology Stack

**Project:** GNUS-POC ELM Training & Distillation Pipeline (Milestone v1.1)
**Researched:** 2026-05-27
**Confidence:** HIGH

## Recommended Stack

### Core Runtime

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Python | 3.11.6 | Runtime | Already in venv. Matches MLX minimum (3.10+). No reason to upgrade to 3.12/3.13. |

### ML Training (Existing — Keep, No Changes Needed)

| Library | Version | Purpose | Status |
|---------|---------|---------|--------|
| mlx | 0.30.0 | Apple Silicon tensor compute | Installed. Core training engine. |
| mlx-lm | 0.28.4 | LM LoRA training + inference | Installed. Uses `mlx_lm.lora.train_model()` directly. |
| mlx-metal | 0.30.0 | GPU acceleration backend | Installed. Required for MPS compute. |
| torch | 2.7.1 | Tensor operations (supplementary) | Installed. Used only for non-MLX ops (scikit-learn integration, data prep). |
| transformers | 4.54.1 | Tokenizer loading, HF Hub access | Installed. Used for tokenizer configs. |
| peft | 0.18.0 | LoRA adapter loading (supplementary) | Installed. May be used for adapter inspection but not for MLX training. |
| safetensors | 0.5.3 | Model weight format | Installed. |
| sentencepiece | 0.2.0 | Tokenizer backend | Installed. |

### API Integration — DeepSeek v4 Pro Teacher Model

| Library | Version | Purpose | Why |
|---------|---------|---------|-----|
| openai | 1.101.0 (installed) | DeepSeek API client | **Use directly, not `deepseek-sdk`.** DeepSeek API is OpenAI-compatible. The `openai` client is the official DeepSeek recommendation: set `base_url="https://api.deepseek.com"` and `api_key`. The third-party `deepseek-sdk` (v0.1.1, Oct 2025) is a thin wrapper adding nothing beyond what `openai` already provides, is maintained by a single individual, and lags the official SDK. |
| tenacity | 9.1.2 (installed) | Retry with exponential backoff | Already installed. Use for API rate-limit handling and transient error recovery. |
| python-dotenv | 1.1.1 (installed) | Environment config | Already installed. Use for API key management (`.env` file, never committed). |

**Integration pattern:** Direct OpenAI client usage:
```python
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

client = OpenAI(
    api_key=os.environ["DEEPSEEK_API_KEY"],
    base_url="https://api.deepseek.com",
)

@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=60))
def generate(prompt: str, model: str = "deepseek-chat") -> str:
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=4096,
    )
    return response.choices[0].message.content
```

### Experiment Tracking

| Library | Version | Purpose | Why |
|---------|---------|---------|-----|
| mlflow | 3.12.0 | Experiment tracking, metrics, model registry | **RECOMMENDED over W&B.** MLflow v3.x is production-stable, has native DeepSeek integration (listed in official integrations), supports LLM tracing and evaluation, runs locally without cloud dependency, and has a lightweight UI (`mlflow ui`). W&B requires cloud account + adds complexity. MLflow autolog works with OpenAI calls (teacher) and can track MLX training metrics. |
| rich | 13.9.4 (installed) | CLI output formatting, progress bars | Already installed. Use for pipeline progress visualization. |

**Why not W&B?** Cloud-dependent for full functionality, heavier install, overkill for a local macOS PoC pipeline. MLflow provides equivalent tracking with zero external dependencies.

### Data Management

| Library | Version | Purpose | Why |
|---------|---------|---------|-----|
| datasets | 4.0.0 (installed) | HF Arrow-based dataset loading/saving | Already used in `prepare_datasets.py`. Keep for train/val/test split management and `save_to_disk`. |
| pyarrow | 21.0.0 (installed) | Columnar data format | Required by `datasets`. Already installed. |
| huggingface-hub | 0.34.3 (installed) | Model/dataset downloading | Already used by `mlx_lm.utils.load`. |

**Data format decision:** The existing split between HF Arrow format (`save_to_disk`) for training data storage and JSONL (`{"text": "..."}`) for MLX-LM ingestion works well. Continue this pattern. **No DVC needed for v1.1** — dataset versioning adds complexity without benefit at this scale. Use timestamped output directories instead (already done with `training_metadata.json`).

### Synthetic Data Generation — Teacher-Driven

No new libraries. Use the existing `openai` client directed at DeepSeek:

| Concern | Approach |
|---------|----------|
| Prompt templates | Structured JSON prompts with niche-specific system messages, requesting `{"instruction": ..., "response": ...}` pairs in `response_format={"type": "json_object"}` |
| Batch processing | Sequential with `tenacity` retry. No async needed for v1.1 batch sizes (hundreds to low thousands of samples). |
| Rate limiting | Exponential backoff via `tenacity`. DeepSeek rate limits are generous for pro tier. |
| Output format | Generate JSONL directly, then convert to HF `Dataset` format using existing `datasets.Dataset.from_list()` pattern. |

### Model Evaluation

| Library | Version | Purpose | Why |
|---------|---------|---------|-----|
| lm-eval | 0.4.12 | Standard benchmark evaluation | **Install with `pip install "lm_eval[hf]"`.** EleutherAI's standard harness. v0.4.x has lighter base install (no torch/transformers by default — install the `[hf]` extra). Use for standard tasks (MMLU, HellaSwag, ARC, GSM8K) on the base Qwen models for calibration. |
| Custom eval scripts | N/A | Per-specialist accuracy/latency/parameter-efficiency | **Must write custom.** `lm-eval` does not directly support MLX models. Build a thin evaluation wrapper that: (1) loads the MLX model + LoRA adapter, (2) runs inference on niche-specific test sets, (3) computes accuracy, token-level perplexity, and inference latency. Use existing JSONL test splits from `data/specialists/<niche>_mlx/`. |

**Evaluation architecture:**
- **Standard benchmarks** (MMLU, HellaSwag): Use `lm-eval` via CLI on base Qwen models via HF backend for calibration baselines.
- **Specialist accuracy**: Custom script that loads trained adapters via `mlx_lm.utils.load()` + adapter, evaluates on niche-specific test sets, computes per-token accuracy and BLEU/ROUGE against held-out test data.
- **Latency**: Custom timing harness using `mlx_lm.generate` with varied sequence lengths.
- **Parameter efficiency**: Simple ratio comparison (adapter params / base model params) computed from adapter config.

| Evaluation Concern | Tool | Reasoning |
|--------------------|------|-----------|
| Standard academic benchmarks | `lm-eval` (CLI, HF backend) | Gold standard, reproducible |
| Niche-specific accuracy | Custom Python script | MLX not supported by lm-eval |
| Perplexity | Custom using `mlx_lm` loss | Direct model access |
| Token-level quality | Custom BLEU/ROUGE via `nltk` | Already installed (nltk 3.9.1) |
| Latency benchmarking | Custom timing harness | Need MLX-specific measurement |
| Parameter efficiency | JSON metadata analysis | Already in `training_metadata.json` |

### Knowledge Distillation

No new libraries. Pure Python using existing stack:

| Component | Implementation |
|-----------|---------------|
| Teacher logit extraction | `openai` client with `logprobs=True` on DeepSeek API (supports `logprobs` parameter) |
| Student logit extraction | `mlx_lm.generate` with logit output enabled |
| KL divergence loss | `numpy` (1.26.4) — compute KL(student_logits || teacher_logits) as additional training signal |
| Subspace extraction | SVD on teacher logit matrices via `scikit-learn` (1.7.1, installed) |

**Note:** DeepSeek's `deepseek-chat` model supports `logprobs`, enabling logit-level distillation without needing local teacher model access. This is the key enabler for the "no local GPU cluster" architecture.

### Quantization for Deployment

| Library | Version | Purpose | Why |
|---------|---------|---------|-----|
| mlx.core.quantize | Built-in (0.30.0) | Weight quantization for deployment | **Use MLX native.** `mlx.core.quantize` supports `mode="mxfp4"`, `mode="nvfp4"`, and `mode="affine"` with configurable `group_size` and `bits`. This is the Apple Silicon-native path. The PyTorch FP4 code in `docs/code-in-markdown.md` is legacy research code — do not port to MLX. MLX's native quantize is hardware-optimized for Apple Silicon Neural Engine. |

**Quantization strategy:**
- **Training:** BF16 (no quantization) — already what `train_specialists_mlx.py` uses.
- **Deployment:** Apply `mlx.core.quantize(w, group_size=128, bits=4, mode="mxfp4")` to trained adapter weights + base model, then save quantized safetensors.
- **FP4 pyramid:** The pyramid architecture from `docs/code-in-markdown.md` describes a multi-resolution quantization scheme for images. For LLM weight quantization, use MLX's native group-wise FP4 quantization instead. The pyramid concept maps to: group_size (resolution granularity) × bits (precision) trade-offs.

### Orchestration & Scheduling

| Approach | Purpose | Why |
|----------|---------|-----|
| Python script with dependency graph | Pipeline orchestration | **Custom, no framework needed.** The pipeline stages have a clear DAG: Data Gen → Training → Distillation → Eval → Quantize. A simple Python orchestrator script (`gnus-poc/orchestrate.py`) that reads a YAML/JSON config, runs stages in order, skips completed stages (checkpointing), and logs to MLflow. |
| Resumability | Checkpoint detection | Already partially implemented in `train_specialists_mlx.py` (line 223: `if final_adapter.exists(): skip`). Extend this pattern to all stages. |

**Why not Prefect/Airflow/Luigi?** Overkill for v1.1. The pipeline runs on a single macOS machine with sequential stages. Adding a workflow framework introduces deployment complexity (schedulers, databases) with no benefit at this scale. If orchestration needs grow in v2.0, consider Prefect (lightweight, Python-native) then.

### Testing

| Library | Version | Purpose | Why |
|---------|---------|---------|-----|
| pytest | 8.3.5 (installed) | Test runner | Already installed. Use. |
| pytest-mock | latest | Mocking framework (API calls, file I/O) | **Add.** Essential for mocking `openai` API calls in synthetic data generation tests without hitting real endpoints. |
| pytest-cov | latest | Code coverage | **Add.** Track test coverage across pipeline modules. |
| pytest-timeout | latest | Test timeout enforcement | **Add.** Prevent API-dependent tests from hanging. |
| responses | 0.25.7 (installed) | HTTP response mocking | Already installed. Use with `pytest-mock` for DeepSeek API call simulation. |
| unittest.mock | Built-in | Mocking `mlx_lm` calls | Standard library. Use for mocking MLX model loads in unit tests (no actual model loading). |

**What NOT to add for testing:**
- `pytest-asyncio` — unnecessary. The v1.1 pipeline uses synchronous API calls via `openai` client. No async code.
- `pytest-xdist` — unnecessary for single-machine test suite.

### Supporting Utilities (Already Installed — Keep)

| Library | Version | Purpose | Why Keep |
|---------|---------|---------|----------|
| scikit-learn | 1.7.1 | TF-IDF, KMeans, SVD for niche discovery | Core to `analyze_common_pile.py`. |
| numpy | 1.26.4 | Numerical operations | Ubiquitous dependency. |
| tqdm | 4.66.5 | Progress bars | Used throughout existing scripts. |
| PyYAML | 6.0.2 | Config files | Use for pipeline config YAML. |
| nltk | 3.9.1 | Text processing, BLEU scoring | Use for evaluation metrics. |

## Alternatives Considered & Rejected

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| API client | `openai` (existing) | `deepseek-sdk` (0.1.1) | Third-party, single-maintainer, thin wrapper. `openai` is the documented DeepSeek recommendation. |
| Experiment tracking | mlflow 3.12.0 | W&B | Cloud-dependent, heavier, overkill for local pipeline. |
| MLX alternative | mlx 0.30.0 | PyTorch + MPS | MLX is 2-3x faster on Apple Silicon for LLM workloads. Already in use. |
| Quantization | `mlx.core.quantize` | Custom PyTorch FP4 | MLX native is hardware-optimized, tested, supports mxfp4/nvfp4 modes. |
| Orchestration | Custom Python script | Prefect / Airflow / Luigi | Overkill for single-machine sequential pipeline. |
| Data versioning | Timestamped dirs + MLflow | DVC | Unnecessary complexity for v1.1 data volumes (<10GB). |
| Evaluation | lm-eval + custom scripts | langfuse (2.44.0, installed) | Langfuse is observability/tracing, not benchmark evaluation. Already installed from open-webui dependency. |
| Async API | N/A (sync only) | `aiohttp` / `httpx` async | Batch sizes are small enough that sync is simpler and sufficient. |

## Installation

```bash
# Core — already installed in gnus-poc/.venv
# No pip install needed for: mlx, mlx-lm, torch, transformers, datasets,
#   openai, peft, safetensors, scikit-learn, numpy, rich, tenacity,
#   python-dotenv, pyyaml, nltk, pytest, responses, tqdm

# New additions for v1.1 pipeline:
pip install mlflow==3.12.0            # Experiment tracking
pip install "lm_eval[hf]"            # Standard benchmark evaluation
pip install pytest-mock              # Mocking for tests
pip install pytest-cov               # Test coverage
pip install pytest-timeout           # Test timeout enforcement
```

**requirements.txt** to create (mirrors above for reproducibility):
```
# gnus-poc ELM Pipeline — v1.1 requirements
# Core (already installed, pinned for reproducibility)
mlx>=0.30.0,<0.31.0
mlx-lm>=0.28.0,<0.29.0
mlx-metal>=0.30.0,<0.31.0
torch>=2.7.0,<2.8.0
transformers>=4.54.0,<4.55.0
datasets>=4.0.0,<5.0.0
pyarrow>=21.0.0,<22.0.0
peft>=0.18.0,<0.19.0
openai>=1.100.0,<2.0.0
safetensors>=0.5.0,<0.6.0
scikit-learn>=1.7.0,<1.8.0
numpy>=1.26.0,<1.27.0
sentencepiece>=0.2.0,<0.3.0
huggingface-hub>=0.34.0,<0.35.0

# New for v1.1
mlflow>=3.12.0,<3.14.0
lm-eval>=0.4.12,<0.5.0

# Utilities
rich>=13.0.0
tenacity>=9.0.0
python-dotenv>=1.0.0
pyyaml>=6.0.0
nltk>=3.9.0
tqdm>=4.66.0

# Testing
pytest>=8.3.0,<9.0.0
pytest-mock>=3.14.0
pytest-cov>=6.0.0
pytest-timeout>=2.3.0
responses>=0.25.0
```

## Integration Points with Existing Code

| Existing File | v1.1 Integration |
|---------------|------------------|
| `gnus-poc/models/train_specialists_mlx.py` | **Extend** — add MLflow logging (`mlflow.log_params`, `mlflow.log_metrics`) after each training run. Wrap training loops in `mlflow.start_run()`. |
| `gnus-poc/data/analyze_common_pile.py` | **Use as-is** — niche discovery feeds into synthetic data generation prompt templates. |
| `gnus-poc/data/prepare_datasets.py` | **Extend** — add synthetic data generation step before HF dataset creation. Output goes to `data/specialists/<niche>_synthetic/`. |
| `gnus-poc/models/specialists_mlx/` | **Read from** — existing adapters are baselines for distillation experiments. |
| `gnus-poc/data/specialists/<niche>_mlx/` | **Read from** — existing JSONL files are validation sets for evaluation. |
| `docs/code-in-markdown.md` | **Reference only** — FP4 research context. Implementation uses MLX native quantization. |

## New Directory Structure (gnus-poc additions)

```
gnus-poc/
├── orchestrate.py              # Main pipeline orchestrator
├── config/
│   └── pipeline.yaml           # Pipeline configuration
├── distillation/
│   └── distill.py              # Knowledge distillation (teacher→student)
├── api/
│   ├── deepseek_client.py      # DeepSeek API wrapper with retry
│   └── synthetic_data_gen.py   # Teacher-driven data generation
├── evaluation/
│   ├── eval_specialist.py      # Custom MLX model evaluation
│   └── benchmarks.py           # Standard benchmark runner (lm-eval)
├── quantization/
│   └── quantize_specialist.py  # MLX native FP4 quantization
├── tests/
│   ├── test_api_client.py
│   ├── test_synthetic_data.py
│   ├── test_evaluation.py
│   ├── test_distillation.py
│   └── conftest.py             # Shared fixtures (mocked API, temp data)
└── requirements.txt            # Pinned dependencies
```

## Sources

- [MLX Quantization API](https://ml-explore.github.io/mlx/build/html/python/core/quantization.html) — Verified via `help(mlx.core.quantize)` in installed 0.30.0. Supports mxfp4, nvfp4, affine modes. **HIGH confidence.**
- [DeepSeek API Documentation](https://api-docs.deepseek.com/) — OpenAI-compatible, recommended client is `openai` Python SDK. **HIGH confidence.**
- [MLflow 3.12.0 Release](https://pypi.org/project/mlflow/3.12.0/) — Released May 5, 2026. DeepSeek integration confirmed in official integrations list. **HIGH confidence.**
- [lm-eval 0.4.12](https://pypi.org/project/lm-eval/0.4.12/) — Released May 11, 2026. HF backend via `pip install "lm_eval[hf]"`. **HIGH confidence.**
- [OpenAI Python SDK](https://github.com/openai/openai-python) — v1.101.0 installed. `base_url` parameter supports custom API endpoints. **HIGH confidence.**
- [deepseek-sdk](https://pypi.org/project/deepseek-sdk/0.1.1/) — v0.1.1, released Oct 2025, single maintainer, 5.3KB. **MEDIUM confidence** on recommendation to avoid (verified via PyPI).**
