---
phase: 01-foundation-bug-fixes
reviewed: 2026-05-27T18:30:00Z
depth: deep
files_reviewed: 21
files_reviewed_list:
  - gnus-poc/training/tokenizer_utils.py
  - gnus-poc/training/train_specialists_mlx.py
  - gnus-poc/training/train_specialists.py
  - gnus-poc/training/__init__.py
  - gnus-poc/data/scripts/prepare_datasets.py
  - gnus-poc/data/scripts/__init__.py
  - gnus-poc/data/scripts/extract_source_niches.py
  - gnus-poc/tests/test_chat_template.py
  - gnus-poc/tests/test_skip_logic.py
  - gnus-poc/tests/conftest.py
  - gnus-poc/tests/__init__.py
  - gnus-poc/config/pipeline.yaml
  - gnus-poc/config/specialists/medical.yaml
  - gnus-poc/config/specialists/code.yaml
  - gnus-poc/config/specialists/qa_technical.yaml
  - gnus-poc/config/specialists/encyclopedic.yaml
  - gnus-poc/config/specialists/patents.yaml
  - gnus-poc/config/experiments/example_experiment.yaml
  - gnus-poc/config/__init__.py
  - gnus-poc/requirements.txt
  - gnus-poc/pyproject.toml
findings:
  critical: 3
  warning: 7
  info: 6
  total: 16
status: issues_found
---

# Phase 01: Foundation & Bug Fixes — Code Review Report

**Reviewed:** 2026-05-27T18:30:00Z
**Depth:** deep (cross-file tracing, import graphs, data flow analysis)
**Files Reviewed:** 21
**Status:** issues_found — 3 BLOCKER, 7 WARNING, 6 INFO

## Summary

Phase 01 addressed four tracked bugs (FOUND-01 through FOUND-04): chat template mismatch, skip-on-existing false completions, directory restructure, and config/infrastructure. The work was executed in three sub-plans with TDD, summary docs, and milestone self-checks.

**Three BLOCKER issues found:**
1. **Pitfall #16 fix is dead code** — StackExchange metadata is never propagated from `extract_niche_samples()` to `format_for_training()`; the `qa_technical` niche will never use structured Q&A pairs
2. **Tokenizer model mismatch** — the code specialist uses Qwen3-Coder but all datasets are formatted with Qwen3-Instruct's chat template
3. **train_specialists.py lacks skip logic** — the non-MLX training script has none of the FOUND-02 fixes, silently allowing incomplete/training retrains

Plus 7 warnings (data flow gaps, fragile asserts, untestable config loader) and 6 informational items.

---

## Critical Issues

### CR-01: Pitfall #16 Fix Is Dead Code — Metadata Not Propagated to Samples

**File:** `gnus-poc/data/scripts/prepare_datasets.py:115-119`, `:168`, `:180-194`
**Issue:** The `extract_niche_samples()` function constructs sample dicts with only three keys (`text`, `source`, `niche`) at line 115-119:

```python
samples.append({
    'text': text,
    'source': source,
    'niche': niche_name
})
```

The `meta` field from the original dataset example (`example.get('meta', {})`) is **not propagated** to the sample dict. When `format_for_training()` later reads `meta = sample.get('meta', {})` at line 168, it always receives an empty dict `{}`.

This means the entire Pitfall #16 StackExchange Q&A structured metadata detection at lines 182-187 is **unreachable dead code**:

```python
# L182-187 — NEVER executes because meta is always {}
if isinstance(meta, dict) and 'question' in meta and 'answer' in meta:
    question = meta['question']
    answer = meta['answer']
elif isinstance(meta, dict) and 'Question' in meta and 'Answer' in meta:
    question = meta['Question']
    answer = meta['Answer']
```

All `qa_technical` samples will fall through to the `'Q:' in text` heuristic (line 188) or the generic fallback `"Explain this technical concept:"` (line 193), losing structured StackExchange question/answer data.

The 01-01-SUMMARY.md claims this fix was applied ("Pitfall #16: Check metadata for StackExchange question/answer keys") but the data pipeline doesn't pass metadata through.

**Fix:**
```python
# In extract_niche_samples() at line 115-119:
samples.append({
    'text': text,
    'source': source,
    'niche': niche_name,
    'meta': meta           # ← Propagate metadata for format_for_training()
})
```

Also add a test in `test_skip_logic.py` or a new `test_format_for_training.py` that passes a sample dict with a `meta` key containing `question`/`answer` and verifies the correct branch is taken.

---

### CR-02: Tokenizer Model Mismatch — Code Specialist Uses Wrong Chat Template

**File:** `gnus-poc/data/scripts/prepare_datasets.py:21`
**Issue:** The module-level tokenizer is loaded once for the **Qwen3-Instruct** model:

```python
_TOKENIZER = load_tokenizer("mlx-community/Qwen3-30B-A3B-Instruct-2507-bf16")
```

But the **code specialist** uses a **different base model** (`Qwen3-Coder-30B-A3B-Instruct-bf16` per `train_specialists_mlx.py:42` and `config/specialists/code.yaml:5`). The Qwen3-Coder model has a different chat template (code-oriented special tokens and formatting) than Qwen3-Instruct.

All 5 specialists' datasets are formatted through the single `_TOKENIZER` via `format_chat(messages, _TOKENIZER)` at line 232. The `code` niche datasets will be formatted with the wrong chat template, creating a persistent format mismatch between data preparation and training — the exact class of bug that FOUND-01 was meant to prevent.

**Fix:**
```python
# In prepare_datasets.py, replace the module-level _TOKENIZER with:
import sys
from training.tokenizer_utils import load_tokenizer, format_chat

# Map specialist to its correct tokenizer model path
_SPECIALIST_TOKENIZER_MODELS = {
    "medical":      "mlx-community/Qwen3-30B-A3B-Instruct-2507-bf16",
    "qa_technical": "mlx-community/Qwen3-30B-A3B-Instruct-2507-bf16",
    "code":         "mlx-community/Qwen3-Coder-30B-A3B-Instruct-bf16",
    "encyclopedic": "mlx-community/Qwen3-30B-A3B-Instruct-2507-bf16",
    "patents":      "mlx-community/Qwen3-30B-A3B-Instruct-2507-bf16",
}

_tokenizer_cache = {}

def _get_tokenizer_for_niche(niche_name):
    model_path = _SPECIALIST_TOKENIZER_MODELS[niche_name]
    if model_path not in _tokenizer_cache:
        _tokenizer_cache[model_path] = load_tokenizer(model_path)
    return _tokenizer_cache[model_path]
```

Then in `format_for_training()`, load the correct tokenizer:
```python
# Line 232, replace:
tokenizer = _get_tokenizer_for_niche(niche_name)
formatted_text = format_chat(messages, tokenizer)
```

---

### CR-03: train_specialists.py Lacks All FOUND-02 Fixes

**File:** `gnus-poc/training/train_specialists.py` (entire file, 237 lines)
**Issue:** The non-MLX training script (`train_specialists.py`) was moved during Phase 01-02 (directory restructure) but was **never modified** to include the FOUND-02 skip-logic fixes. Comparing against `train_specialists_mlx.py`:

| Feature | train_specialists_mlx.py | train_specialists.py |
|---|---|---|
| `--force-retrain` flag | ✓ Line 236-240 | ✗ Missing |
| Milestone file check | ✓ Lines 262-295 | ✗ Missing |
| `TRAINING_STATUS.json` | ✓ Lines 206-214 | ✗ Missing |
| `status: "complete"` in metadata | ✓ Line 200 | ✗ Missing |
| Metadata iters validation | ✓ Lines 274-285 | ✗ Missing |
| Skip-on-complete logic | ✓ Lines 281-285 | ✗ Missing |

Running `train_specialists.py` will silently re-train all specialists on every invocation (FOUND-02 regression). It also won't write `TRAINING_STATUS.json`, so downstream consumers expecting that file will fail.

If `train_specialists.py` is intentionally deprecated, add an explicit warning or deprecation notice. If it's intended to remain active, it needs the same skip logic as the MLX version.

**Fix:** Either:
- **Option A (deprecation):** Add a prominent warning at the top and `sys.exit(1)` with a message directing users to `train_specialists_mlx.py`
- **Option B (feature parity):** Backport the skip logic, force-retrain flag, TRAINING_STATUS.json writing, and status metadata field from `train_specialists_mlx.py` lines 200-295

---

## Warnings

### WR-01: NoneType Crash Risk in extract_niche_samples

**File:** `gnus-poc/data/scripts/prepare_datasets.py:107-108`
**Issue:** `text = example.get('text', example.get('content', ''))` — if `example` has key `'text'` with value `None`, the fallback `example.get('content', '')` is **not triggered** (`.get` only falls through when the key is absent, not when the value is falsy). The subsequent `len(text)` call on line 110 would raise `TypeError: object of type 'NoneType' has no len()`.

**Fix:**
```python
text = example.get('text') or example.get('content') or ''
```

---

### WR-02: Assert Statement Used for Runtime Validation

**File:** `gnus-poc/training/tokenizer_utils.py:80`
**Issue:** `assert result and len(result) > 0, "format_chat produced empty output"` — `assert` statements are stripped when Python runs with `-O` (optimization) flag. If this code ever runs in an optimized context, the empty-output guard disappears silently, potentially writing empty prompts to training data.

**Fix:**
```python
if not result or len(result) == 0:
    raise RuntimeError("format_chat produced empty output")
```

---

### WR-03: test_skip_logic.py Only Does Structural Checks — No Behavioral Tests

**File:** `gnus-poc/tests/test_skip_logic.py` (entire file, 65 lines)
**Issue:** All 4 tests search for string patterns in the source code file (`train_specialists_mlx.py`) using `ast.parse` and substring matching. None of them actually **execute** the skip logic or verify its behavior. This means:
- A refactor that renames variables but preserves behavior could break tests
- The tests can't detect that `force_retrain` deletes the directory only if it exists (but what if it's a read-only directory? a symlink? etc.)
- The milestone-check ordering (force → milestone → metadata) is untested

This is a test-quality gap — structural tests are useful for detecting regressions in what code exists, but they don't validate that the code does the right thing.

**Fix:** Add at least one integration test that:
1. Creates a mock adapter directory with `0001000_adapters.safetensors` and valid `training_metadata.json`
2. Runs `main()` from a test harness
3. Verifies that `train_specialist()` is NOT called for that niche (skip behavior)

Use the `tmp_path` fixture from `conftest.py` and monkeypatch `OUTPUT_DIR`.

---

### WR-04: Hardcoded Iteration Count in Skip Logic Could Diverge

**File:** `gnus-poc/training/train_specialists_mlx.py:263, :219`
**Issue:** The skip logic in `main()` reads `configured_iters = OVERRIDES["iters"]` (line 263) and constructs the milestone filename independently. Simultaneously, `train_specialist()` uses `args.iters` (which is also `OVERRIDES["iters"]` after `build_args_for_niche`). If OVERRIDES is ever modified at runtime or a per-specialist override changes `args.iters` without updating `configured_iters`, the milestone check will look for the wrong file.

Currently the values are consistent because both pull from the same `OVERRIDES` dict, but this is fragile coupling — two independent reads of the same dict with no cross-verification.

**Fix:** Read `configured_iters` from the metadata file, not from OVERRIDES:
```python
else:
    meta_file = adapter_path / "training_metadata.json"
    if meta_file.exists():
        with meta_file.open() as f:
            meta = json.load(f)
        meta_status = meta.get("status")
        # Check if the milestone file for THIS training's iters exists
        meta_iters = meta.get("iters")
        if meta_iters:
            milestone_file = f"{meta_iters:07d}_adapters.safetensors"
            if (adapter_path / milestone_file).exists() and meta_status == "complete":
                ...
```

---

### WR-05: config/__init__.py Has No Loader Implementation

**File:** `gnus-poc/config/__init__.py`
**Issue:** The YAML config hierarchy (pipeline.yaml → specialist/*.yaml → experiments/*.yaml) exists on disk but `config/__init__.py` contains only a docstring — no loader function, merger logic, or env-var interpolation. Per 01-03-SUMMARY.md, this is deferred to Phase 3, but the module is created and importable now. Downstream code that tries `from config import load_pipeline_config` will get an `ImportError` with no indication that the feature is pending.

**Fix:** Add a minimal stub:
```python
"""GNUS-POC configuration — YAML hierarchy loader."""

def load_pipeline_config():
    """Load pipeline configuration (deferred to Phase 3)."""
    raise NotImplementedError(
        "Config YAML hierarchy loading is deferred to Phase 3. "
        "Hardcoded defaults in training scripts are used for Phase 1-2."
    )
```

---

### WR-06: train_specialists.py Missing status Field in Metadata

**File:** `gnus-poc/training/train_specialists.py:180-192`
**Issue:** The metadata dict written by `train_specialist()` lacks the `status` field that the MLX version includes. This means:
- If a downstream script migrates from MLX to non-MLX, the metadata validation logic will treat all non-MLX outputs as "incomplete"
- The `TRAINING_STATUS.json` file is also not written

This compounds CR-03.

**Fix:** Add `"status": "complete"` to the metadata dict (line 180-189) and write `TRAINING_STATUS.json` after `training_metadata.json`.

---

### WR-07: pipeline.yaml Comments Reference ${DEEPSEEK_API_KEY} But Not Used Anywhere

**File:** `gnus-poc/config/pipeline.yaml:16`
**Issue:** The comment `"Resolved from .env at load time (Phase 3: os.path.expandvars resolves ${DEEPSEEK_API_KEY})"` describes planned behavior. However, `api_key_env` stores the env var name as a plain string (`"DEEPSEEK_API_KEY"`), not as `${DEEPSEEK_API_KEY}`. No code currently reads this value either. The comment accurately says this is Phase 3 work, but the discrepancy between the env var name format and the `${...}` syntax mentioned in the comment could cause confusion when Phase 3 development starts.

**Fix:** Clarify the comment:
```yaml
api_key_env: "DEEPSEEK_API_KEY"  # Phase 3: resolved from .env via os.getenv(this_value)
```

---

## Info

### IN-01: Duplicated MockTokenizer Classes

**Files:** `gnus-poc/tests/test_chat_template.py:41-43`, `:65-67`
**Issue:** Two test functions define nearly identical `MockTokenizer` inline classes. Consolidating into a single `conftest.py` fixture or a helper function would reduce duplication and make the mock easier to maintain if the `apply_chat_template` interface changes.

**Fix:** Move to `conftest.py`:
```python
@pytest.fixture
def mock_tokenizer():
    from unittest.mock import MagicMock
    tok = MagicMock()
    tok.apply_chat_template = MagicMock(
        return_value="<mock_template>system\nHi\n</mock_template>\n<mock_template>user\nHello\n</mock_template>"
    )
    return tok
```

---

### IN-02: tokenizer_utils.py Missing __all__

**File:** `gnus-poc/training/tokenizer_utils.py`
**Issue:** The module defines two public functions (`load_tokenizer`, `format_chat`) but has no `__all__` list. This means `from training.tokenizer_utils import *` would import these plus any future private helpers.

**Fix:** Add after imports:
```python
__all__ = ["load_tokenizer", "format_chat"]
```

---

### IN-03: Missing .env.example Template

**Files:** `.gitignore:2`, `gnus-poc/config/pipeline.yaml:16`
**Issue:** `.env` is correctly gitignored, but there's no `.env.example` file documenting which environment variables are needed (e.g., `DEEPSEEK_API_KEY`). New developers or CI/CD will need to discover this from reading source YAML comments.

**Fix:** Create `gnus-poc/.env.example`:
```
# GNUS-POC environment variables (copy to .env and fill in values)
DEEPSEEK_API_KEY=your_key_here
```

---

### IN-04: Module-Level Tokenizer Load Makes Module Unimportable Offline

**File:** `gnus-poc/data/scripts/prepare_datasets.py:21`
**Issue:** `_TOKENIZER = load_tokenizer("mlx-community/Qwen3-30B-A3B-Instruct-2507-bf16")` runs at import time. If the module is imported for any reason (test discovery, documentation generation, `dir()` exploration) without internet access or without the transformers library installed, the import will fail with a `RuntimeError`. This is a CLI script, so the impact is low, but it violates the principle of making modules importable without side effects.

**Fix:** Lazy-load the tokenizer:
```python
_TOKENIZER = None

def _get_tokenizer():
    global _TOKENIZER
    if _TOKENIZER is None:
        _TOKENIZER = load_tokenizer("mlx-community/Qwen3-30B-A3B-Instruct-2507-bf16")
    return _TOKENIZER
```

---

### IN-05: sys.path Manipulation Is Fragile

**Files:** `gnus-poc/tests/test_chat_template.py:19`, `gnus-poc/tests/conftest.py:17`, `gnus-poc/data/scripts/prepare_datasets.py:15-16`
**Issue:** Multiple files insert the project root into `sys.path` at import time:
- `test_chat_template.py:19`: `sys.path.insert(0, str(Path(__file__).resolve().parent.parent))`
- `conftest.py:17`: same pattern
- `prepare_datasets.py:15-16`: `sys.path.insert(0, str(PROJECT_ROOT))`

While `pyproject.toml:22` sets `pythonpath = ["."]` (which should handle test imports), the scripts use `sys.path.insert` as a fallback. This is inconsistent and potentially masks import errors in production — if `pyproject.toml` is ever removed, the scripts would fail silently until they hit the `sys.path` hack.

**Fix:** Rely on `pyproject.toml` pythonpath exclusively for tests. For scripts like `prepare_datasets.py`, consider using `pip install -e .` for a proper editable install, or add a `PYTHONPATH=.` instruction to the README.

---

### IN-06: Gitignored Directory Contains Runtime Dependencies

**File:** `.gitignore:3` — `gnus-poc/data/analysis`
**Issue:** `prepare_datasets.py:38` reads from `data/analysis/source_based_niches.json`, which is generated by `extract_source_niches.py`. Since `data/analysis/` is gitignored, the JSON file won't be tracked. This means:
- New clones cannot run `prepare_datasets.py` without first running `extract_source_niches.py`
- There's no README or Makefile documenting this prerequisite

This may be intentional (the JSON is large/derived), but it's undocumented.

**Fix:** Either:
- Track a small metadata-only version of the JSON (if under ~50KB)
- Add a check-and-generate step in `prepare_datasets.py` with a helpful error message:
  ```
  if not niche_config_file.exists():
      print("Run: python data/scripts/extract_source_niches.py first")
      sys.exit(1)
  ```
- Document in `gnus-poc/README.md` that `extract_source_niches.py` must run before `prepare_datasets.py`

---

_Reviewed: 2026-05-27T18:30:00Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: deep_
