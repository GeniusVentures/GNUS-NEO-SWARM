# Phase 1: Foundation & Bug Fixes — Context

**Gathered:** 2026-05-27
**Status:** Ready for planning
**Mode:** Auto-generated (smart discuss)

## Phase Boundary

Fix two silent data-corrupting bugs in existing Python code, restructure gnus-poc/ directory layout, establish YAML config hierarchy, add pytest skeleton, and expand .gitignore.

**In scope:**
- FOUND-01: Fix chat template mismatch — extract `tokenizer_utils.py` with `apply_chat_template()` for both data prep and training
- FOUND-02: Fix skip-on-existing logic — check milestone file (e.g. `0001000_adapters.safetensors`), validate metadata iters field, add `--force-retrain`
- FOUND-03: Directory restructure — move `models/` → `training/`, `data/scripts/` for existing scripts; create empty `pipeline/`, `distill/`, `eval/`, `quantize/`, `config/`, `artifacts/`
- FOUND-04: YAML config hierarchy — `config/pipeline.yaml` (global), `config/specialists/<niche>.yaml`, `config/experiments/<exp>.yaml`; `${ENV_VAR}` interpolation

**Out of scope:**
- New training or distillation code (Phases 2-7)
- Evaluation framework (Phase 4)
- FP4 quantization (Phase 7)
- Any changes outside gnus-poc/ (except .gitignore)

## Implementation Decisions

### Chat template fix
Extract a shared `tokenizer_utils.py` in `gnus-poc/training/` that loads the actual tokenizer from the model and calls `tokenizer.apply_chat_template()`. Both `data/scripts/prepare_datasets.py` and `training/train_specialists.py` import it. This prevents future Qwen3/Qwen2.5 drift.

### Directory restructure
Move existing code, not symlink. Path updates in imports. Directory mapping:
- `models/train_specialists_mlx.py` → `training/train_specialists.py`
- `models/train_specialists.py` → deleted (duplicate of -mlx version)
- `models/train_specialists-old.py` → deleted (stale)
- `data/analyze_common_pile.py` → `data/scripts/analyze_common_pile.py`
- `models/specialists_mlx/` → stays (trained artifacts, not code)
- `data/specialists/` → stays (datasets, not code)
- New dirs: `pipeline/`, `distill/`, `eval/`, `quantize/`, `config/`, `artifacts/`

### Secrets management
`.env` file in `gnus-poc/` contains `DEEPSEEK_API_KEY`. YAML configs use `${DEEPSEEK_API_KEY}` interpolation via `python-dotenv` + `os.path.expandvars()`. `.env` is gitignored.

### Existing specialists
Keep in `gnus-poc/models/specialists_mlx/`. Add note to metadata that pre-Phase-1 specialists were trained with Qwen2.5 template on Qwen3 models. Useful for comparison post-fix.

### Testing
Add `gnus-poc/tests/` with `conftest.py` (pytest fixtures, temporary directories, mock model paths) and one smoke test validating the chat template fix. Full eval suite in Phase 4.

### .gitignore
Add Python patterns: `__pycache__/`, `*.pyc`, `*.egg-info/`, `.venv/`, `dist/`, `build/`. `.env` already covered.

## Existing Code Insights

- `train_specialists_mlx.py` (258 lines): Working MLX-LM LoRA pipeline with 5 specialist configs, but chat template bug and skip-logic bug
- `analyze_common_pile.py` (329 lines): TF-IDF + MiniBatchKMeans niche discovery, works as-is
- No tests exist anywhere in gnus-poc
- Training metadata JSON (per specialist) captures config but no performance metrics
- Existing OVERRIDES dicts duplicate config across specialists — TrainingConfig dataclass deferred to Phase 3

## Specific Ideas

- `tokenizer_utils.py`: Two functions — `load_tokenizer(model_path)` and `format_chat(messages, tokenizer)` returning prompt string
- Smoke test: Load tokenizer from a small test model, format a chat, verify output contains correct template tokens for Qwen3
- YAML config: Minimal `pipeline.yaml` with `data_dir`, `models_dir`, `artifacts_dir`, `api.base_url`, `api.model`, `api.budget_cap`
- Skip fix: After training, write `TRAINING_STATUS.json` with `iters_completed` and `status: "complete"`. Check this file, not adapter existence.

## Deferred Ideas

- TrainingConfig dataclass — Phase 3
- Pre-flight memory estimator — Phase 3
- MLflow integration — Phase 4
- Full evaluation suite — Phase 4
- Distillation — Phase 5
- Orchestration — Phase 6
- FP4 export — Phase 7
