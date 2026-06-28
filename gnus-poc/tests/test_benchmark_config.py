"""Tests for per-benchmark config validation and specialist mapping.

Per Plan 04-02 Task 2: per-benchmark YAML configs (mmlu, humaneval, medmcqa,
gpqa, pubmedqa, bigpatent) must have a validatable schema including
``hard_floor`` and ``blocking`` flag per D-04. The specialist mapping
(``specialist_mapping.yaml``) must map all 5 specialists per D-05.
``ConfigLoader.validate_benchmarks_config`` must reject missing/invalid fields.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
import yaml

from eval.benchmark_config import (
    BENCHMARK_REQUIRED_FIELDS,
    ConfigError,
    get_benchmarks_for_specialist,
    load_specialist_mapping,
    validate_benchmarks_config,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_MMLU = {
    "name": "mmlu",
    "task_name": "mmlu",
    "num_fewshot": 5,
    "output_type": "multiple_choice",
    "blocking": False,
    "description": "MMLU 57-subject multiple choice",
    "hard_floor": 0.25,
    "regression_max_pct": 0.10,
    "deviation_max_pct": 0.20,
    "dataset_revision": None,
}


def _write_benchmark_yaml(config_dir: Path, name: str, fields: dict) -> Path:
    """Write a benchmark YAML file with the given fields."""
    config_dir.mkdir(parents=True, exist_ok=True)
    path = config_dir / f"{name}.yaml"
    path.write_text(yaml.safe_dump(fields, sort_keys=False))
    return path


# ---------------------------------------------------------------------------
# Tests — per-benchmark config validation
# ---------------------------------------------------------------------------

class TestValidateBenchmarksConfig:
    """Per-benchmark YAML schema validation (Plan 04-02 Task 2, behavior 1, 2, 5)."""

    def test_valid_benchmark_yaml_passes(self, tmp_path):
        """Test 1: validate_benchmarks_config passes on valid YAML."""
        _write_benchmark_yaml(tmp_path, "mmlu", VALID_MMLU)

        result = validate_benchmarks_config(tmp_path)

        assert "mmlu" in result
        assert result["mmlu"]["hard_floor"] == 0.25
        assert result["mmlu"]["blocking"] is False

    def test_missing_required_field_raises_config_error(self, tmp_path):
        """Test 2: missing required field raises ConfigError naming the field."""
        broken = dict(VALID_MMLU)
        del broken["hard_floor"]
        _write_benchmark_yaml(tmp_path, "mmlu", broken)

        with pytest.raises(ConfigError) as excinfo:
            validate_benchmarks_config(tmp_path)

        message = str(excinfo.value)
        assert "hard_floor" in message, (
            f"error must name the missing field; got: {message}"
        )
        assert "mmlu" in message, (
            f"error must name the file/benchmark; got: {message}"
        )

    def test_non_numeric_threshold_raises_config_error(self, tmp_path):
        """Test 5: non-numeric threshold value raises ConfigError."""
        broken = dict(VALID_MMLU)
        broken["hard_floor"] = "not_a_number"
        _write_benchmark_yaml(tmp_path, "mmlu", broken)

        with pytest.raises(ConfigError) as excinfo:
            validate_benchmarks_config(tmp_path)

        assert "hard_floor" in str(excinfo.value)

    def test_non_numeric_regression_max_pct_raises(self, tmp_path):
        """Test 5b: regression_max_pct must be parseable as float."""
        broken = dict(VALID_MMLU)
        broken["regression_max_pct"] = ["not", "a", "number"]
        _write_benchmark_yaml(tmp_path, "mmlu", broken)

        with pytest.raises(ConfigError) as excinfo:
            validate_benchmarks_config(tmp_path)

        assert "regression_max_pct" in str(excinfo.value)

    def test_wrong_type_num_fewshot_raises(self, tmp_path):
        """num_fewshot must be int."""
        broken = dict(VALID_MMLU)
        broken["num_fewshot"] = "five"
        _write_benchmark_yaml(tmp_path, "mmlu", broken)

        with pytest.raises(ConfigError) as excinfo:
            validate_benchmarks_config(tmp_path)

        assert "num_fewshot" in str(excinfo.value)

    def test_wrong_type_blocking_raises(self, tmp_path):
        """blocking must be bool."""
        broken = dict(VALID_MMLU)
        broken["blocking"] = "false"  # string, not bool
        _write_benchmark_yaml(tmp_path, "mmlu", broken)

        with pytest.raises(ConfigError) as excinfo:
            validate_benchmarks_config(tmp_path)

        assert "blocking" in str(excinfo.value)

    def test_threshold_must_be_positive(self, tmp_path):
        """hard_floor <= 0 should be rejected (random baseline is always > 0)."""
        broken = dict(VALID_MMLU)
        broken["hard_floor"] = -0.1
        _write_benchmark_yaml(tmp_path, "mmlu", broken)

        with pytest.raises(ConfigError) as excinfo:
            validate_benchmarks_config(tmp_path)

        assert "hard_floor" in str(excinfo.value)

    def test_empty_config_dir_returns_empty_dict(self, tmp_path):
        """Empty config dir is valid — returns empty dict (no benchmarks)."""
        result = validate_benchmarks_config(tmp_path)
        assert result == {}


# ---------------------------------------------------------------------------
# Tests — shipped per-benchmark configs (the real YAMLs)
# ---------------------------------------------------------------------------

class TestShippedBenchmarkConfigs:
    """The shipped per-benchmark YAMLs must all validate (behavior 6)."""

    @pytest.fixture(scope="class")
    def shipped_configs(self):
        from eval.benchmark_config import BENCHMARKS_CONFIG_DIR
        return validate_benchmarks_config(BENCHMARKS_CONFIG_DIR)

    @pytest.mark.parametrize(
        "benchmark,expected_blocking,expected_hard_floor",
        [
            ("mmlu", False, 0.25),
            ("humaneval", True, 0.30),
            ("medmcqa", True, 0.30),
            ("gpqa", True, 0.25),
            ("pubmedqa", True, 0.35),
            ("bigpatent", True, 0.20),
        ],
    )
    def test_per_benchmark_schema(
        self, shipped_configs, benchmark, expected_blocking, expected_hard_floor
    ):
        """Test 6: each shipped per-benchmark YAML validates and matches D-04/D-05."""
        assert benchmark in shipped_configs, (
            f"{benchmark}.yaml not found or failed validation"
        )
        cfg = shipped_configs[benchmark]
        assert cfg["blocking"] is expected_blocking, (
            f"{benchmark}: expected blocking={expected_blocking}, "
            f"got {cfg['blocking']}"
        )
        assert cfg["hard_floor"] == expected_hard_floor, (
            f"{benchmark}: expected hard_floor={expected_hard_floor}, "
            f"got {cfg['hard_floor']}"
        )

    def test_mmlu_blocking_is_false(self, shipped_configs):
        """Per D-04: MMLU is diagnostic, NOT blocking."""
        assert shipped_configs["mmlu"]["blocking"] is False

    def test_domain_benchmarks_are_blocking(self, shipped_configs):
        """Per D-04: domain-specific benchmarks are blocking gates."""
        for name in ("humaneval", "medmcqa", "gpqa", "pubmedqa", "bigpatent"):
            assert shipped_configs[name]["blocking"] is True, (
                f"{name} should be blocking per D-04"
            )


# ---------------------------------------------------------------------------
# Tests — specialist mapping
# ---------------------------------------------------------------------------

class TestSpecialistMapping:
    """D-05 specialist-to-benchmark mapping (behavior 3, 4)."""

    @pytest.fixture(scope="class")
    def shipped_mapping(self):
        from eval.benchmark_config import BENCHMARKS_CONFIG_DIR
        return load_specialist_mapping(BENCHMARKS_CONFIG_DIR)

    def test_mapping_loads_all_five_specialists(self, shipped_mapping):
        """Test 3: specialist_mapping.yaml loads with all 5 specialists per D-05."""
        expected = {"code", "medical", "qa_technical", "encyclopedic", "patents"}
        assert set(shipped_mapping.keys()) == expected, (
            f"missing/extra specialists: {set(shipped_mapping.keys())}"
        )

    def test_each_specialist_has_blocking_and_diagnostic(self, shipped_mapping):
        """Each specialist must have both blocking_benchmarks and diagnostic_benchmarks."""
        for name, mapping in shipped_mapping.items():
            assert "blocking_benchmarks" in mapping, (
                f"{name} missing blocking_benchmarks"
            )
            assert "diagnostic_benchmarks" in mapping, (
                f"{name} missing diagnostic_benchmarks"
            )
            assert isinstance(mapping["blocking_benchmarks"], list)
            assert isinstance(mapping["diagnostic_benchmarks"], list)

    def test_medical_specialist_mapping(self, shipped_mapping):
        """Test 4: get_benchmarks_for_specialist('medical') returns expected lists."""
        blocking, diagnostic = get_benchmarks_for_specialist(
            "medical", shipped_mapping
        )
        assert set(blocking) == {"medmcqa", "pubmedqa"}
        assert diagnostic == ["mmlu"]

    def test_code_specialist_has_humaneval_blocking(self, shipped_mapping):
        """Per D-05: code -> HumanEval blocking."""
        blocking, _ = get_benchmarks_for_specialist("code", shipped_mapping)
        assert "humaneval" in blocking

    def test_patents_specialist_has_bigpatent_blocking(self, shipped_mapping):
        """Per D-05: patents -> BIGPATENT blocking."""
        blocking, _ = get_benchmarks_for_specialist("patents", shipped_mapping)
        assert "bigpatent" in blocking

    def test_qa_technical_specialist_has_gpqa_blocking(self, shipped_mapping):
        """Per D-05: qa_technical -> GPQA blocking."""
        blocking, _ = get_benchmarks_for_specialist(
            "qa_technical", shipped_mapping
        )
        assert "gpqa" in blocking

    def test_every_specialist_has_mmlu_diagnostic(self, shipped_mapping):
        """Per D-04: every specialist runs MMLU as universal diagnostic."""
        for name in shipped_mapping:
            _, diagnostic = get_benchmarks_for_specialist(name, shipped_mapping)
            assert "mmlu" in diagnostic, (
                f"{name} missing MMLU diagnostic per D-04"
            )

    def test_referenced_benchmarks_exist(self, shipped_mapping):
        """T-04-08 mitigation: all referenced benchmarks must exist in config dir."""
        from eval.benchmark_config import BENCHMARKS_CONFIG_DIR
        validated = validate_benchmarks_config(BENCHMARKS_CONFIG_DIR)
        available = set(validated.keys())
        for specialist, mapping in shipped_mapping.items():
            for ref in mapping["blocking_benchmarks"] + mapping["diagnostic_benchmarks"]:
                assert ref in available, (
                    f"{specialist} references unknown benchmark '{ref}'; "
                    f"available: {sorted(available)}"
                )

    def test_unknown_specialist_raises(self, shipped_mapping):
        """get_benchmarks_for_specialist on unknown name must raise."""
        with pytest.raises((KeyError, ValueError, ConfigError)):
            get_benchmarks_for_specialist("not_a_specialist", shipped_mapping)

    def test_load_specialist_mapping_rejects_missing_specialist_key(self, tmp_path):
        """A specialist missing 'specialists' top-level key raises ConfigError."""
        (tmp_path / "specialist_mapping.yaml").write_text(
            yaml.safe_dump({"wrong_key": {}})
        )
        with pytest.raises(ConfigError) as excinfo:
            load_specialist_mapping(tmp_path)

        assert "specialists" in str(excinfo.value).lower()

    def test_load_specialist_mapping_rejects_missing_lists(self, tmp_path):
        """A specialist entry missing blocking_benchmarks raises ConfigError."""
        (tmp_path / "specialist_mapping.yaml").write_text(
            yaml.safe_dump({
                "specialists": {
                    "code": {"blocking_benchmarks": ["humaneval"]},
                }
            })
        )
        with pytest.raises(ConfigError) as excinfo:
            load_specialist_mapping(tmp_path)

        assert "diagnostic_benchmarks" in str(excinfo.value)


# ---------------------------------------------------------------------------
# Tests — required-fields contract
# ---------------------------------------------------------------------------

class TestRequiredFieldsContract:
    """Required-fields sanity check (behavior 1)."""

    def test_required_fields_list_matches_schema(self):
        """BENCHMARK_REQUIRED_FIELDS must include all D-04 required fields."""
        for field in (
            "name",
            "task_name",
            "num_fewshot",
            "output_type",
            "blocking",
            "hard_floor",
            "regression_max_pct",
            "deviation_max_pct",
        ):
            assert field in BENCHMARK_REQUIRED_FIELDS, (
                f"{field} missing from BENCHMARK_REQUIRED_FIELDS"
            )
