# Phase 02: Training & Distillation Quality - Pattern Map

**Mapped:** 2026-06-29
**Files analyzed:** 27 (7 new source, 5 new test, 10 modified source, 5 modified config)
**Analogs found:** 23 / 27

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `gnus-poc/distill/convergence.py` | utility | event-driven (per-step updates) | `gnus-poc/eval/benchmarker.py` (gate_check + consecutive failure tracking) | role-match |
| `gnus-poc/training/validation.py` | utility | file-I/O + model I/O | `gnus-poc/training/train_specialists_mlx.py` (MLX loading + metadata pattern) | exact |
| `gnus-poc/router/__init__.py` | package init | N/A | `gnus-poc/eval/__init__.py` (standard Python package init) | exact |
| `gnus-poc/router/engine.py` | utility | event-driven (state transitions) | `gnus-poc/distill/cascade.py` (orchestration + confidence checks) | role-match |
| `gnus-poc/router/rules.py` | utility | transform (query->match) | `gnus-poc/distill/distillation.py` (computational utility with I/O) | role-match |
| `gnus-poc/router/schema.py` | utility | transform (validate) | `gnus-poc/eval/metric_store.py` (_validate_stats_dict) | partial |
| `gnus-poc/router/classifier.py` | service | request-response (query->plan) | `gnus-poc/distill/cascade.py` (execute() + fallback chaining) | exact |
| `gnus-poc/config/router_rules.yaml` | config | N/A | `gnus-poc/config/pipeline.yaml` (section-based YAML) | exact |
| `gnus-poc/config/router_rules.json` | config (exported JSON) | N/A | GQHSM StateProto conceptual model (no code analog) | no-analog |
| `gnus-poc/distill/distillation.py` (EXTEND) | utility | CRUD/batch transform | itself (`distillation.py` already exists) | self |
| `gnus-poc/training/train_specialists_mlx.py` (EXTEND) | service | batch training | itself (`train_specialists_mlx.py` already exists) | self |
| `gnus-poc/eval/evaluator.py` (EXTEND) | utility | compute/transform | itself + `MetricStore` (persistence pattern) | self |
| `gnus-poc/eval/metric_store.py` (EXTEND) | utility | file-I/O persistence | itself (`metric_store.py` already exists) | self |
| `gnus-poc/eval/benchmarker.py` (EXTEND) | utility | gate-check/event-driven | itself (`benchmarker.py` already exists) | self |
| `gnus-poc/config/specialists/code.yaml` (EXTEND) | config | N/A | `gnus-poc/config/pipeline.yaml` (eval_gates block) | exact |
| `gnus-poc/config/specialists/encyclopedic.yaml` (EXTEND) | config | N/A | `gnus-poc/config/pipeline.yaml` (eval_gates block) | exact |
| `gnus-poc/config/specialists/medical.yaml` (EXTEND) | config | N/A | `gnus-poc/config/pipeline.yaml` (eval_gates block) | exact |
| `gnus-poc/config/specialists/patents.yaml` (EXTEND) | config | N/A | `gnus-poc/config/pipeline.yaml` (eval_gates block) | exact |
| `gnus-poc/config/specialists/qa_technical.yaml` (EXTEND) | config | N/A | `gnus-poc/config/pipeline.yaml` (eval_gates block) | exact |
| `gnus-poc/tests/test_convergence.py` | test | unit-test | `gnus-poc/tests/test_distillation.py` | exact |
| `gnus-poc/tests/test_training_validation.py` | test | unit/integration-test | `gnus-poc/tests/test_benchmarker.py` (tmp_path + fixture pattern) | exact |
| `gnus-poc/tests/test_router_rules.py` | test | unit-test | `gnus-poc/tests/test_distillation.py` | exact |
| `gnus-poc/tests/test_router_engine.py` | test | unit-test | `gnus-poc/tests/test_benchmarker.py` (class-based + pytest) | exact |
| `gnus-poc/tests/test_synthetic_quality.py` | test | unit-test | `gnus-poc/tests/test_dedup.py` | partial |
| `gnus-poc/tests/test_training_config.py` | test | unit-test | `gnus-poc/tests/test_config.py` | partial |
| `gnus-poc/tests/test_eval_persistence.py` | test | unit-test | `gnus-poc/tests/test_metric_store.py` | exact |
| `gnus-poc/tests/test_distillation.py` (EXTEND) | test | unit-test | itself | self |

## Pattern Assignments

### `gnus-poc/distill/convergence.py` (utility, event-driven per-step updates)

**Analog:** `gnus-poc/eval/benchmarker.py` (gate state tracking + consecutive failure counters)

**Imports pattern** (benchmarker.py lines 1-13):
```python
"""<module docstring describing purpose>."""

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)
```

**Core pattern — stateful tracker with per-step updates** (benchmarker.py lines 108-203, gate_check method):
- Class receives configurable thresholds at `__init__`
- Per-step method (`step()`) returns status string
- Internal state tracks counters, history
- Public method returns structured result dict

**Consecutive failure tracking pattern** (benchmarker.py lines 238-263, `_update_consecutive_failures`):
```python
@staticmethod
def _update_consecutive_failures(prev_state: dict, now_failures: dict) -> dict:
    """Update counters: increment on failure, reset to 0 on pass."""
    prev_counters = prev_state.get("consecutive_failures", {})
    result = {}
    for name, failed in now_failures.items():
        prev = prev_counters.get(name, 0)
        if failed:
            result[name] = prev + 1
        else:
            result[name] = 0
    return result
```

**Error handling pattern** — No exceptions in hot path. Returns status strings: `'continue'`, `'warning'`, `'converged'`, `'early_stop'`, `'hard_stop'`. Caller decides action.

---

### `gnus-poc/training/validation.py` (utility, file-I/O + model loading)

**Analog:** `gnus-poc/training/train_specialists_mlx.py` (MLX model loading + metadata writing)

**Imports pattern** (train_specialists_mlx.py lines 24-34):
```python
import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from mlx_lm import utils as mlx_utils
from mlx_lm import lora as mlx_lora
```

**MLX model loading pattern** (train_specialists_mlx.py lines 174-178):
```python
model, tokenizer = mlx_utils.load(
    model_id,
    tokenizer_config={"trust_remote_code": True},
)
```

**Try/except for loadability check** (train_specialists_mlx.py lines 298-305, error handling in main()):
```python
try:
    meta = train_specialist(niche)
    all_meta[niche] = meta
except Exception as e:
    print(f"\n✗ Error training {niche}: {e}")
    import traceback
    traceback.print_exc()
    continue
```

**Metadata persistence pattern** (train_specialists_mlx.py lines 191-201):
```python
metadata = {
    "niche": niche_name,
    "base_model": base_model,
    "trained_at": datetime.now().isoformat(),
    "status": "complete",
}
with open(f"{adapter_path}/training_metadata.json", "w") as f:
    json.dump(metadata, f, indent=2)
```

**Project root detection** (train_specialists_mlx.py line 36):
```python
PROJECT_ROOT = Path(__file__).resolve().parent.parent
```

---

### `gnus-poc/router/__init__.py` (package init)

**Analog:** `gnus-poc/eval/__init__.py` (standard empty/minimal package init)

Pattern: Empty `__init__.py` or re-exporting key symbols. Follow `eval/__init__.py` convention.

---

### `gnus-poc/router/engine.py` (utility, event-driven state machine)

**Analog:** `gnus-poc/distill/cascade.py` (orchestrator with confidence checks + fallback)

**Imports pattern** (cascade.py lines 1-22):
```python
"""<module docstring — GQHSM-compatible state machine runtime>."""

import math
# transitions library import
from transitions import Machine
```

**Orchestration class pattern** (cascade.py lines 129-161, TeacherCascade):
- Constructor receives dependencies at init (not global state)
- Public method `execute()` as primary API entry point
- Internal helper methods prefixed with `_`
- Returns structured result object (not raw dicts)

**Confidence threshold gating pattern** (cascade.py lines 213-222):
```python
if level1_confidence >= self._confidence_threshold and level1_content is not None:
    return CascadeResult(
        final_content=level1_content,
        ...
    )
```

**Fallback chaining pattern** (cascade.py lines 224-308):
- Try primary
- If confidence below threshold, try next-best
- Ultimate fallback (never fails silently)
- Raise explicit error only if every attempt fails

---

### `gnus-poc/router/rules.py` (utility, query classification transform)

**Analog:** `gnus-poc/distill/distillation.py` (computational utility class)

**Imports pattern** (distillation.py lines 1-10):
```python
"""<module docstring>."""

import argparse
import json
import math
from typing import Optional

import numpy as np
```

**Utility class pattern** (distillation.py lines 13-17, Distiller):
```python
class Distiller:
    def __init__(self, temperature: float = 2.0, alpha: float = 0.5):
        self._temperature = temperature
        self._alpha = alpha
```

**Public method returning structured dict** (distillation.py lines 65-91, `sweep_temperature`):
```python
def sweep_temperature(self, ...) -> dict:
    results = {}
    for item in items:
        results[str(key)] = value
    return {
        "results": results,
        "best": best_value,
    }
```

---

### `gnus-poc/router/schema.py` (utility, JSON schema validation)

**Analog:** `gnus-poc/eval/metric_store.py` (_validate_stats_dict static method)

**Validation pattern** (metric_store.py lines 358-394):
```python
@staticmethod
def _validate_stats_dict(fp4_stats: dict, niche_name: str) -> None:
    """Validate required keys and types."""
    required_keys = [...]  # list of expected keys
    for key in required_keys:
        if key not in fp4_stats:
            raise ValueError(
                f"Missing required key '{key}' in fp4_stats for niche '{niche_name}'"
            )
    # Type checks for specific fields
    for key in numeric_keys:
        value = fp4_stats[key]
        if not isinstance(value, (int, float)):
            raise ValueError(
                f"Non-numeric value for '{key}': {value!r}"
            )
```

---

### `gnus-poc/router/classifier.py` (service, request-response query->plan)

**Analog:** `gnus-poc/distill/cascade.py` (execute() orchestration with confidence threshold + fallback)

**Imports pattern** (cascade.py lines 1-3, 24-32 — import only what's needed):
```python
"""<module docstring>."""

import math

# Local domain-specific mappings
_DOMAIN_MAP = {
    "code": "coding",
    ...
}
```

**Service class pattern** (cascade.py lines 129-161, TeacherCascade):
```python
class TeacherCascade:
    def __init__(self, dependency1, dependency2, ...):
        self._dep1 = dependency1
        self._dep2 = dependency2

    def execute(self, messages, domain, **kwargs):
        # Step 1: Try primary
        # Step 2: Check confidence
        # Step 3: Fallback chain
        # Step 4: Best-effort return
```

**Result object pattern** (cascade.py lines 81-126, CascadeResult):
```python
class CascadeResult:
    def __init__(self, final_content, confidence, escalated, attempts, ...):
        self.final_content = final_content
        self.confidence = confidence
        self.escalated = escalated
        self.attempts = attempts

    def to_dict(self):
        return { ... }  # JSON-serializable
```

**Fallback chaining pattern** (cascade.py lines 249-303 — see RESEARCH.md §Pattern 3 for adapted version):
- Sort candidates by priority/score descending
- Try each; return on first confidence >= threshold
- Track best-available result
- Return best-available if none meets threshold
- Raise explicit error only if all attempts fail

---

### `gnus-poc/config/router_rules.yaml` (config, YAML)

**Analog:** `gnus-poc/config/pipeline.yaml` (section-based YAML with nested blocks)

**Top-level structure pattern** (pipeline.yaml lines 1-40):
```yaml
# COMMENT describing config
#
# Two-layer architecture:
#   section1: ...
#   section2: ...

# ---------------------------------------------------------------------------
# Section Name: description
# ---------------------------------------------------------------------------
section_name:
  key1: value1
  key2: value2
```

**Eval gates block pattern** (pipeline.yaml lines 126-152):
```yaml
eval_gates:
  gate_dimension:
    max: 0.01
    consecutive_failures_to_block: 3
  gate_dimension2:
    min: 0.05
    consecutive_failures_to_block: 2
```

---

### `gnus-poc/config/specialists/{code,encyclopedic,medical,patents,qa_technical}.yaml` (EXTEND config)

**Analog:** `gnus-poc/config/pipeline.yaml` eval_gates block (lines 126-152) + existing `gnus-poc/config/specialists/code.yaml` (lines 1-16)

**Additions per specialist** (per RESEARCH.md Pattern 1, lines 356-365):
```yaml
distillation:
  alpha: 0.7
  distill_loss_target: 2.5
  distill_loss_warning: 3.0
  distill_loss_hard_stop: 5.0
  patience: 100
  min_delta: 0.01

validation:
  validation_loss_threshold: 3.0
  behavioral_diff_threshold: 0.95
  test_split_path: "data/specialists/code/test.jsonl"
  min_test_samples: 50
```

---

### `gnus-poc/distill/distillation.py` (EXTEND — +ConvergenceTracker integration)

**Analog:** itself (`gnus-poc/distill/distillation.py`)

Extend existing `Distiller` class with:
- Import `ConvergenceTracker` from `distill.convergence`
- Optional `ConvergenceTracker` instance in `__init__`
- Call `tracker.step(loss, step)` in training loop
- Extend `sweep_temperature` to write structured JSON at `artifacts/sweeps/{niche}_sweep.json`

**Existing CLI pattern to follow** (distillation.py lines 93-113):
```python
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="...")
    parser.add_argument("--niche", required=True, help="...")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    out_dir = project_root / "artifacts" / "distill"
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / f"{args.niche}_loss.json").open("w") as f:
        json.dump(loss_log, f, indent=2)
```

---

### `gnus-poc/training/train_specialists_mlx.py` (EXTEND — +post-training validation)

**Analog:** itself (`gnus-poc/training/train_specialists_mlx.py`)

Extend `train_specialist()` function (lines 148-225):
- After `mlx_lora.train_model()` call (line 187), add validation pass:
  1. Import `validate_adapter` from `training.validation`
  2. Call `validate_adapter()` with test split (NOT training val_batches — D-06)
  3. Record validation results in metadata before writing `TRAINING_STATUS.json`
  4. If validation fails, set `status: "training_complete_validation_failed"` (not `"complete"`)

---

### `gnus-poc/eval/evaluator.py` (EXTEND — +structured metric persistence)

**Analog:** itself + `gnus-poc/eval/metric_store.py`

Currently writes minimal results to `artifacts/evaluations/{niche}_eval.json` (lines 182-186). Extend to:
1. Use `MetricStore` for timestamped per-run persistence
2. Write `{niche}_{timestamp}.json` files (follow MetricStore naming: `niche_benchmark_YYYYMMDD-HHMMSS.json`)
3. Include all metrics (PPL, BLEU, ROUGE-L, latency) with metadata

**Persistence pattern** (metric_store.py lines 177-249, `record_benchmark_results`):
```python
timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
out_path = self._out_dir / f"{niche_name}_eval_{timestamp}.json"
with out_path.open("w", encoding="utf-8") as f:
    json.dump(record, f, indent=2)
```

---

### `gnus-poc/eval/metric_store.py` (EXTEND — +training eval metrics)

**Analog:** itself (`gnus-poc/eval/metric_store.py`)

Extend the existing class:
- Add `record_training_eval_metrics(niche_name, metrics)` method following same pattern as `record_sgfp4_metrics` (lines 63-121)
- Add `load_training_eval_metrics(niche_name)` method following same pattern as `load_sgfp4_metrics` (lines 123-147)
- Write to `artifacts/evaluations/{niche}_training_eval.json` (separate from SGFP4 metrics)

---

### `gnus-poc/eval/benchmarker.py` (EXTEND — +per-specialist gating + trend analysis)

**Analog:** itself (`gnus-poc/eval/benchmarker.py`)

Existing `gate_check_benchmarks()` (lines 711-893) already implements:
- Hard floor checks
- Regression vs previous run
- Deviation from baseline
- 2-of-3 composite gate
- Consecutive failure tracking
- Gate state persistence

Extend with:
1. Add `gate_check_training_eval()` method following same pattern for training evaluation gates
2. Load training eval metrics from MetricStore (new `load_training_eval_metrics`)
3. Apply per-specialist thresholds from config/specialists/
4. Persist to separate gate state file: `artifacts/.gate_state/{niche}_training_gate_state.json`

---

## Shared Patterns

### Authentication / API Keys
**Not applicable to Phase 2** — all new modules are local Python pipeline utilities. Teacher API calls (for optional router confidence checks) use the existing Phase 1 TeacherClient with its built-in API key management. No new auth patterns needed.

### Error Handling
**Source:** `gnus-poc/training/train_specialists_mlx.py` lines 298-305 and `gnus-poc/eval/benchmarker.py` lines 269-298

**Apply to:** All new source files

Pattern: **Fail-open on corrupt state, structured result dicts over exceptions in hot paths.**

```python
# Corrupt state recovery (benchmarker.py lines 283-298)
try:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)
except (json.JSONDecodeError, OSError) as exc:
    logger.warning("State file %s is corrupt; recreating fresh. Error: %s", path, exc)
    return {}

# Training loop error handling (train_specialists_mlx.py lines 298-305)
try:
    result = do_work(...)
except Exception as e:
    print(f"\n✗ Error: {e}")
    import traceback
    traceback.print_exc()
    continue
```

### Logging
**Source:** `gnus-poc/eval/benchmarker.py` line 3, `gnus-poc/eval/metric_store.py` line 16

**Apply to:** All new source files

```python
import logging
logger = logging.getLogger(__name__)
```

Use `logger.info(...)`, `logger.warning(...)`, `logger.error(...)` for all diagnostic output. No `print()` in library code (CLI scripts can use `print()` for user-facing output).

### Project Root Detection
**Source:** `gnus-poc/training/train_specialists_mlx.py` line 36, `gnus-poc/eval/metric_store.py` lines 49-51

**Apply to:** All new source files that need filesystem access

```python
from pathlib import Path

# Module-level constant
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Or in __init__
def __init__(self, project_root: Optional[Path] = None):
    if project_root is None:
        project_root = Path(__file__).resolve().parent.parent
    self._project_root = project_root
```

### YAML Config Loading
**Source:** `gnus-poc/eval/benchmarker.py` lines 352-366

**Apply to:** `gnus-poc/router/rules.py` (router rule loading), config extensions

```python
def _load_yaml(self, path: Path) -> dict:
    """Load a YAML file; returns {} if missing."""
    if not path.exists():
        return {}
    import yaml  # local import keeps module importable without pyyaml

    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}
```

### JSON Persistence Pattern
**Source:** `gnus-poc/eval/metric_store.py` lines 232-248

**Apply to:** `gnus-poc/router/classifier.py`, `gnus-poc/training/validation.py`, `gnus-poc/distill/convergence.py`

```python
from datetime import datetime, timezone

timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
out_path = out_dir / f"{niche_name}_{description}_{timestamp}.json"
with out_path.open("w", encoding="utf-8") as f:
    json.dump(results, f, indent=2)
logger.info("Recorded %s for niche=%s -> %s", description, niche_name, out_path)
```

### Test File Structure
**Source:** `gnus-poc/tests/test_benchmarker.py` lines 1-80, `gnus-poc/tests/test_distillation.py` lines 1-51

**Apply to:** All new test files

```python
"""Tests for <module>."""

import json
from unittest.mock import MagicMock

import pytest

from <module.path> import <ClassUnderTest>
from <module.dep> import <DependencyClass>


class Test<ClassName>:
    def test_<scenario>(self, tmp_path):  # or `def test_<scenario>(self):`
        """One-line docstring or assertive description."""
        # Arrange
        obj = <ClassName>(project_root=tmp_path)

        # Act
        result = obj.<method>(...)

        # Assert
        assert result is not None
        assert result["key"] == expected_value

    def test_<error_scenario>(self):
        obj = <ClassName>()
        result = obj.<method>(invalid_input)
        assert result == <sentinel_value>  # or assert result == float("inf")
```

Key conventions:
- Class-based tests: `class Test<ClassName>:`
- `tmp_path` fixture from pytest for filesystem isolation
- Descriptive test names: `test_<scenario_description>`
- Arrange/Act/Assert structure
- Import modules at top of file (no lazy imports in tests)
- Helper methods prefixed with `_` inside test class

### Config Extension Pattern (per-specialist YAML)
**Source:** `gnus-poc/config/specialists/code.yaml` (existing structure) + `gnus-poc/config/pipeline.yaml` (eval_gates block)

**Apply to:** All 5 specialist config files

Existing specialist config (code.yaml):
```yaml
specialist:
  name: "code"
  base_model: "mlx-community/Qwen3-Coder-30B-A3B-Instruct-bf16"
  niche_sources: [...]
  system_prompt: "..."
  synthetic_prompts: [...]
  training:
    lora_rank: 16
    iterations: 1000
```

Add after `training:` block:
```yaml
distillation:
  alpha: 0.7
  distill_loss_target: 2.5       # DEFAULT — override per specialist
  distill_loss_warning: 3.0
  distill_loss_hard_stop: 5.0
  patience: 100
  min_delta: 0.01

validation:
  validation_loss_threshold: 3.0
  behavioral_diff_threshold: 0.95
  test_split_path: "data/specialists/<niche>/test.jsonl"
  min_test_samples: 50
```

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `gnus-poc/config/router_rules.json` | config (exported JSON) | N/A | No GQHSM-compatible JSON schema exists in codebase. This is the first router implementation. Design against the GQHSM StateProto conceptual model described in RESEARCH.md Pattern 3 (lines 402-429). |
| `gnus-poc/tests/test_synthetic_quality.py` | test | unit-test | No existing synthetic data quality test (dedup test is closest partial). Follow `test_distillation.py` unit test class structure. |
| `gnus-poc/tests/test_training_config.py` | test | unit-test | No analogous config validation test. Follow `test_config.py` class structure. |
| `gnus-poc/router/schema.py` | utility | validate/transform | No existing JSON schema validator in codebase. Follow `MetricStore._validate_stats_dict` static method pattern but use `jsonschema` library for JSON Schema validation against the GQHSM schema. |

For files with no analog: The planner should reference RESEARCH.md code examples directly:
- `router_rules.json` schema: RESEARCH.md lines 402-429 (GQHSM-Compatible JSON Schema)
- `schema.py`: Follow RESEARCH.md lines 526-528 ("YAML schema validation for router rules")
- Test files without analogs: Follow the test file structure pattern documented in Shared Patterns above

## Metadata

**Analog search scope:** `gnus-poc/distill/`, `gnus-poc/training/`, `gnus-poc/eval/`, `gnus-poc/config/`, `gnus-poc/tests/`
**Files scanned:** 15 existing source, config, and test files
**Pattern extraction date:** 2026-06-29
