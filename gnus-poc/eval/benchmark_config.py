"""ConfigLoader extension for per-benchmark YAML configs and specialist mapping.

Per Phase 04-02 Task 2: validates the schema of every per-benchmark config YAML
in ``config/benchmarks/`` (required fields: name, task_name, num_fewshot,
output_type, blocking, hard_floor, regression_max_pct, deviation_max_pct per
D-04/D-08) and loads the specialist-to-benchmark mapping per D-05
(``specialist_mapping.yaml``).

Threat mitigations:
- T-04-06: ``yaml.safe_load`` exclusively — never ``yaml.load`` or full_load.
- T-04-08: ``load_specialist_mapping`` cross-validates referenced benchmark
  names against the validated per-benchmark config set.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
BENCHMARKS_CONFIG_DIR: Path = _PROJECT_ROOT / "config" / "benchmarks"

# Filename of the specialist mapping (NOT a per-benchmark config — skipped by
# validate_benchmarks_config).
SPECIALIST_MAPPING_FILENAME = "specialist_mapping.yaml"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class ConfigError(Exception):
    """Raised when a benchmark config or specialist mapping fails validation.

    The error message names the file and the missing/invalid field so the
    operator can pinpoint the bad YAML without a stack dive.
    """


# ---------------------------------------------------------------------------
# Required-fields contract
# ---------------------------------------------------------------------------

# Per D-04/D-08: every per-benchmark YAML must carry these fields.
# Tuple of (field_name, expected_python_type). ``bool`` is checked strictly
# (Python bool is a subclass of int, so ``isinstance(x, int)`` accepts True;
# the per-field validator special-cases bool to reject string "true"/"false").
BENCHMARK_REQUIRED_FIELDS: Tuple[Tuple[str, type], ...] = (
    ("name", str),
    ("task_name", str),
    ("num_fewshot", int),
    ("output_type", str),
    ("blocking", bool),
    ("hard_floor", float),
    ("regression_max_pct", float),
    ("deviation_max_pct", float),
)

# Thresholds that must be strictly positive (random baselines are > 0).
_THRESHOLD_FIELDS: Tuple[str, ...] = (
    "hard_floor",
    "regression_max_pct",
    "deviation_max_pct",
)


# ---------------------------------------------------------------------------
# Per-benchmark config validation
# ---------------------------------------------------------------------------

def validate_benchmarks_config(config_dir: Path | None = None) -> Dict[str, Dict[str, Any]]:
    """Read and validate every per-benchmark YAML in ``config_dir``.

    Each YAML must define all fields in ``BENCHMARK_REQUIRED_FIELDS`` with the
    correct type. Threshold fields (hard_floor, regression_max_pct,
    deviation_max_pct) must be strictly positive floats. ``num_fewshot`` must
    be a non-negative int. ``blocking`` must be a Python ``bool`` (string
    "true"/"false" from a misconfigured YAML is rejected).

    Args:
        config_dir: Directory containing per-benchmark YAML files. Defaults to
            ``<project_root>/config/benchmarks/``.

    Returns:
        Dict mapping ``name`` field -> validated config dict.

    Raises:
        ConfigError: If any YAML is missing a required field, has an invalid
            type, or fails a value-range check. The error message names the
            file and the offending field.
        FileNotFoundError: If ``config_dir`` does not exist.
    """
    resolved_dir = config_dir if config_dir is not None else BENCHMARKS_CONFIG_DIR

    if not resolved_dir.is_dir():
        raise FileNotFoundError(
            f"Benchmarks config directory not found: {resolved_dir}"
        )

    validated: Dict[str, Dict[str, Any]] = {}

    # Sort for deterministic error ordering across platforms.
    for yaml_path in sorted(resolved_dir.glob("*.yaml")):
        # The specialist mapping has its own schema — skip it here.
        if yaml_path.name == SPECIALIST_MAPPING_FILENAME:
            continue

        # Skip YAMLs that aren't per-benchmark configs. A per-benchmark config
        # MUST have a top-level `name:` field (distinct from the lm-eval
        # `task:` field used by pubmedqa.yaml/bigpatent.yaml — those YAMLs
        # carry BOTH, so the `name:` check picks them up correctly).
        with yaml_path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        if not isinstance(data, dict):
            raise ConfigError(
                f"{yaml_path.name}: expected a YAML mapping at the top level, "
                f"got {type(data).__name__}"
            )
        if "name" not in data:
            # Not a per-benchmark config (e.g. some future non-benchmark YAML).
            # Skip silently — only files that opt in via `name:` are validated.
            continue

        _validate_one_benchmark(yaml_path.name, data)
        validated[data["name"]] = data

    return validated


def _validate_one_benchmark(filename: str, data: Dict[str, Any]) -> None:
    """Validate a single per-benchmark config dict in place.

    Args:
        filename: YAML filename (for error messages).
        data: Parsed YAML dict.

    Raises:
        ConfigError: On any schema violation.
    """
    for field_name, expected_type in BENCHMARK_REQUIRED_FIELDS:
        if field_name not in data:
            raise ConfigError(
                f"{filename}: missing required field '{field_name}'"
            )

        value = data[field_name]
        _validate_field_type(filename, field_name, value, expected_type)

    # Range checks
    num_fewshot = data["num_fewshot"]
    if num_fewshot < 0:
        raise ConfigError(
            f"{filename}.num_fewshot: must be >= 0, got {num_fewshot}"
        )

    for thr_field in _THRESHOLD_FIELDS:
        val = data[thr_field]
        if val <= 0.0:
            raise ConfigError(
                f"{filename}.{thr_field}: must be > 0.0, got {val}"
            )
        if val > 1.0:
            raise ConfigError(
                f"{filename}.{thr_field}: must be <= 1.0 (it is a fraction), "
                f"got {val}"
            )


def _validate_field_type(
    filename: str,
    field_name: str,
    value: Any,
    expected_type: type,
) -> None:
    """Type-check a single field, with bool-special-casing.

    Python ``bool`` is a subclass of ``int``, so ``isinstance(True, int)`` is
    True. To catch a YAML that says ``blocking: "false"`` (string) or
    ``num_fewshot: true`` (bool), we:
      - reject bool where int is expected (num_fewshot=true is a type error),
      - reject non-bool where bool is expected (blocking="false" is an error).

    For float fields, int is accepted and coerced (YAML parses 0.25 as float
    already, but 1 parses as int — accept both for thresholds).

    Args:
        filename: YAML filename (for error messages).
        field_name: Field name.
        value: The parsed value.
        expected_type: Expected Python type.

    Raises:
        ConfigError: If the value is not the expected type.
    """
    if expected_type is bool:
        if not isinstance(value, bool):
            raise ConfigError(
                f"{filename}.{field_name}: must be a boolean, got "
                f"{type(value).__name__} ({value!r})"
            )
        return

    if expected_type is int:
        # Reject bool (Python: isinstance(True, int) is True).
        if isinstance(value, bool) or not isinstance(value, int):
            raise ConfigError(
                f"{filename}.{field_name}: must be an integer, got "
                f"{type(value).__name__} ({value!r})"
            )
        return

    if expected_type is float:
        # Accept int (YAML may parse 0 as int). Reject bool.
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ConfigError(
                f"{filename}.{field_name}: must be a number, got "
                f"{type(value).__name__} ({value!r})"
            )
        return

    if not isinstance(value, expected_type):
        raise ConfigError(
            f"{filename}.{field_name}: must be a {expected_type.__name__}, "
            f"got {type(value).__name__}"
        )


# ---------------------------------------------------------------------------
# Specialist mapping
# ---------------------------------------------------------------------------

def load_specialist_mapping(config_dir: Path | None = None) -> Dict[str, Dict[str, List[str]]]:
    """Load and validate ``specialist_mapping.yaml`` per D-05.

    Validates that:
      - the file exists and parses as a YAML mapping,
      - the top-level key is ``specialists``,
      - each specialist entry has both ``blocking_benchmarks`` and
        ``diagnostic_benchmarks`` lists,
      - every referenced benchmark exists in the per-benchmark config set
        (T-04-08 mitigation).

    Args:
        config_dir: Directory containing ``specialist_mapping.yaml``. Defaults
            to ``<project_root>/config/benchmarks/``.

    Returns:
        Dict mapping specialist name -> {
            "blocking_benchmarks": [...],
            "diagnostic_benchmarks": [...],
        }.

    Raises:
        ConfigError: On any schema violation, including a referenced benchmark
            that does not have a per-benchmark config YAML.
        FileNotFoundError: If the file or directory does not exist.
    """
    resolved_dir = config_dir if config_dir is not None else BENCHMARKS_CONFIG_DIR
    mapping_path = resolved_dir / SPECIALIST_MAPPING_FILENAME

    if not mapping_path.is_file():
        raise FileNotFoundError(
            f"Specialist mapping not found: {mapping_path}"
        )

    with mapping_path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)

    if not isinstance(data, dict):
        raise ConfigError(
            f"{SPECIALIST_MAPPING_FILENAME}: expected a YAML mapping, got "
            f"{type(data).__name__}"
        )

    if "specialists" not in data:
        raise ConfigError(
            f"{SPECIALIST_MAPPING_FILENAME}: missing top-level 'specialists' key"
        )

    specialists = data["specialists"]
    if not isinstance(specialists, dict) or not specialists:
        raise ConfigError(
            f"{SPECIALIST_MAPPING_FILENAME}.specialists: must be a non-empty mapping"
        )

    result: Dict[str, Dict[str, List[str]]] = {}
    for spec_name, spec_mapping in specialists.items():
        prefix = f"{SPECIALIST_MAPPING_FILENAME}.specialists.{spec_name}"
        if not isinstance(spec_mapping, dict):
            raise ConfigError(
                f"{prefix}: must be a mapping with blocking_benchmarks "
                f"and diagnostic_benchmarks"
            )
        for required_list in ("blocking_benchmarks", "diagnostic_benchmarks"):
            if required_list not in spec_mapping:
                raise ConfigError(
                    f"{prefix}: missing required key '{required_list}'"
                )
            value = spec_mapping[required_list]
            if not isinstance(value, list):
                raise ConfigError(
                    f"{prefix}.{required_list}: must be a list, got "
                    f"{type(value).__name__}"
                )
            for item in value:
                if not isinstance(item, str):
                    raise ConfigError(
                        f"{prefix}.{required_list}: entries must be strings, "
                        f"got {type(item).__name__}"
                    )

        result[spec_name] = {
            "blocking_benchmarks": list(spec_mapping["blocking_benchmarks"]),
            "diagnostic_benchmarks": list(spec_mapping["diagnostic_benchmarks"]),
        }

    # T-04-08 mitigation: cross-validate referenced benchmark names against
    # the per-benchmark config set. Skip when config_dir is non-default and
    # has no per-benchmark YAMLs (unit-test convenience).
    try:
        validated_benchmarks = validate_benchmarks_config(resolved_dir)
        available = set(validated_benchmarks.keys())
        for spec_name, spec_mapping in result.items():
            for ref in spec_mapping["blocking_benchmarks"] + spec_mapping["diagnostic_benchmarks"]:
                if ref not in available:
                    raise ConfigError(
                        f"{SPECIALIST_MAPPING_FILENAME}.specialists.{spec_name}: "
                        f"references unknown benchmark '{ref}'; "
                        f"available: {sorted(available)}"
                    )
    except FileNotFoundError:
        # config_dir has specialist_mapping.yaml but no per-benchmark YAMLs —
        # skip cross-validation (unit-test scenarios).
        pass

    return result


def get_benchmarks_for_specialist(
    specialist: str,
    mapping: Dict[str, Dict[str, List[str]]],
) -> Tuple[List[str], List[str]]:
    """Return ``(blocking_benchmarks, diagnostic_benchmarks)`` for a specialist.

    Args:
        specialist: Specialist name (e.g. "medical", "code").
        mapping: Loaded specialist mapping (output of ``load_specialist_mapping``).

    Returns:
        Tuple of (blocking_benchmarks, diagnostic_benchmarks) lists.

    Raises:
        KeyError: If *specialist* is not in *mapping*.
    """
    if specialist not in mapping:
        raise KeyError(
            f"Unknown specialist '{specialist}'. "
            f"Valid: {sorted(mapping.keys())}"
        )
    entry = mapping[specialist]
    return (
        list(entry["blocking_benchmarks"]),
        list(entry["diagnostic_benchmarks"]),
    )


# ---------------------------------------------------------------------------
# Self-test (run: python eval/benchmark_config.py)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    passed = 0
    failed = 0

    def check(name: str, condition: bool, detail: str = "") -> None:
        global passed, failed
        if condition:
            passed += 1
            print(f"  PASS  {name}")
        else:
            failed += 1
            print(f"  FAIL  {name}{' — ' + detail if detail else ''}")

    # Per-benchmark configs validate
    try:
        validated = validate_benchmarks_config()
        check("validate_benchmarks_config() succeeds", True)
    except Exception as exc:  # pragma: no cover
        check("validate_benchmarks_config() succeeds", False, str(exc))
        sys.exit(1)

    expected_benchmarks = {"mmlu", "humaneval", "medmcqa", "gpqa", "pubmedqa", "bigpatent"}
    check(
        "all 6 per-benchmark YAMLs present",
        expected_benchmarks.issubset(validated.keys()),
        f"missing: {expected_benchmarks - set(validated.keys())}",
    )

    # MMLU blocking=False per D-04
    check(
        "mmlu blocking=False per D-04",
        validated.get("mmlu", {}).get("blocking") is False,
    )

    # Domain benchmarks blocking=True per D-04
    for name in ("humaneval", "medmcqa", "gpqa", "pubmedqa", "bigpatent"):
        check(
            f"{name} blocking=True",
            validated.get(name, {}).get("blocking") is True,
        )

    # Specialist mapping loads
    try:
        mapping = load_specialist_mapping()
        check("load_specialist_mapping() succeeds", True)
    except Exception as exc:  # pragma: no cover
        check("load_specialist_mapping() succeeds", False, str(exc))
        sys.exit(1)

    expected_specialists = {"code", "medical", "qa_technical", "encyclopedic", "patents"}
    check(
        "all 5 specialists in mapping per D-05",
        set(mapping.keys()) == expected_specialists,
        f"got: {sorted(mapping.keys())}",
    )

    # medical -> medmcqa+pubmedqa blocking, mmlu diagnostic
    block, diag = get_benchmarks_for_specialist("medical", mapping)
    check(
        "medical blocking=[medmcqa, pubmedqa]",
        set(block) == {"medmcqa", "pubmedqa"},
        str(block),
    )
    check("medical diagnostic=[mmlu]", diag == ["mmlu"], str(diag))

    print(f"\n  {passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
