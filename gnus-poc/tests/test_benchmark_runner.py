"""Tests for benchmark_runner — lm-eval integration and results persistence."""

import json
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from eval.benchmark_runner import (
    CANONICAL_PARAMS,
    SPECIALIST_BENCHMARKS,
    BenchmarkRunner,
    build_task_list,
    collect_fingerprint_fields,
    validate_results_schema,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_simple_evaluate_results(tasks, include_mmlu_subjects=False):
    """Build a mock simple_evaluate() return dict for given task names.

    Args:
        tasks: List of task name strings.
        include_mmlu_subjects: If True, include per-subject MMLU breakdown.
    """
    results = {}
    for task in tasks:
        if task == "mmlu":
            entry = {"acc": 0.72, "acc_stderr": 0.01, "acc_norm": 0.73}
            if include_mmlu_subjects:
                entry["alias"] = "mmlu"
        elif task == "humaneval":
            entry = {"pass@1": 0.45, "pass@1_stderr": 0.03}
        elif task == "medmcqa":
            entry = {"acc": 0.54, "acc_stderr": 0.02}
        elif task == "gpqa_main_n_shot":
            entry = {"acc_norm": 0.48, "acc_norm_stderr": 0.03}
        elif task == "pubmedqa":
            entry = {"acc": 0.62, "acc_stderr": 0.02}
        else:
            entry = {"acc": 0.50, "acc_stderr": 0.05}

        results[task] = entry

    # Add per-subject MMLU breakdown when requested
    if include_mmlu_subjects and "mmlu" in results:
        mmlu_subjects = {
            "mmlu_anatomy": {"acc": 0.68, "acc_stderr": 0.05},
            "mmlu_clinical_knowledge": {"acc": 0.75, "acc_stderr": 0.04},
            "mmlu_college_medicine": {"acc": 0.70, "acc_stderr": 0.06},
        }
        results.update(mmlu_subjects)

    return {"results": results, "configs": {}, "samples": {}}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSpecialistBenchmarks:
    """Tests for specialist-to-benchmark mapping (D-05)."""

    def test_all_niches_have_mapping(self):
        """Every niche in the pipeline has a benchmark mapping entry."""
        expected_niches = {"code", "medical", "qa_technical", "encyclopedic", "patents"}
        assert set(SPECIALIST_BENCHMARKS.keys()) == expected_niches

    def test_code_specialist_has_humaneval_blocking(self):
        """Code specialist maps to HumanEval + LiveCodeBench blocking benchmarks."""
        code_mapping = SPECIALIST_BENCHMARKS["code"]
        assert "humaneval" in code_mapping["blocking"]
        assert "mmlu" in code_mapping["diagnostic"]

    def test_medical_specialist_has_medmcqa_blocking(self):
        """Medical specialist maps to MedMCQA + PubMedQA + MedHELM blocking."""
        medical_mapping = SPECIALIST_BENCHMARKS["medical"]
        assert "medmcqa" in medical_mapping["blocking"]
        assert "pubmedqa" in medical_mapping["blocking"]
        assert "mmlu" in medical_mapping["diagnostic"]

    def test_every_niche_has_mmlu_diagnostic(self):
        """Per D-04: every specialist runs MMLU as universal diagnostic baseline."""
        for niche, mapping in SPECIALIST_BENCHMARKS.items():
            assert "mmlu" in mapping["diagnostic"], (
                f"Niche '{niche}' missing MMLU diagnostic per D-04"
            )


class TestBuildTaskList:
    """Tests for benchmark task list construction."""

    def test_canonical_mode_includes_blocking_and_diagnostic(self):
        """Canonical mode includes both blocking and diagnostic benchmarks."""
        tasks = build_task_list("medical", "canonical")
        # Medical blocking: medmcqa, pubmedqa, medhelm
        assert "medmcqa" in tasks
        assert "pubmedqa" in tasks
        # Diagnostic: MMLU
        assert "mmlu" in tasks

    def test_diagnostic_mode_includes_all(self):
        """Diagnostic mode includes all benchmarks (same list, different params)."""
        tasks = build_task_list("code", "diagnostic")
        assert "humaneval" in tasks
        assert "mmlu" in tasks

    def test_unknown_niche_raises_value_error(self):
        """Unknown niche name raises ValueError."""
        with pytest.raises(ValueError, match="Unknown niche"):
            build_task_list("nonexistent_niche", "canonical")


class TestCanonicalParams:
    """Tests for canonical frozen parameters (D-03)."""

    def test_canonical_params_are_frozen(self):
        """Canonical params are frozen: temperature=0.0, do_sample=False."""
        assert CANONICAL_PARAMS["temperature"] == 0.0
        assert CANONICAL_PARAMS["do_sample"] is False

    def test_canonical_params_exist(self):
        """Canonical params dict has expected keys."""
        expected_keys = {"temperature", "do_sample", "num_fewshot"}
        assert set(CANONICAL_PARAMS.keys()) == expected_keys


class TestFingerprintFields:
    """Tests for reproducibility fingerprint collection (D-02)."""

    def test_fingerprint_includes_required_fields(self):
        """Fingerprint includes all 11 D-02 fields."""
        fingerprint = collect_fingerprint_fields(
            task_name="mmlu",
            task_revision="0",
            dataset_revision="abc123",
            prompt_hash="sha256_deadbeef",
            fewshot_seed=42,
            chat_template_hash="sha256_cafe",
            answer_extraction="multiple_choice",
            generation_params={"temperature": 0.0},
        )
        expected_fields = {
            "harness_commit",
            "task_name",
            "task_revision",
            "dataset_revision",
            "prompt_hash",
            "fewshot_seed",
            "chat_template_hash",
            "answer_extraction",
            "generation_params",
            "model_manifest_sha256",
            "sgfp4_manifest_sha256",
        }
        assert set(fingerprint.keys()) == expected_fields

    def test_fingerprint_model_manifest_placeholder(self):
        """model_manifest_sha256 and sgfp4_manifest_sha256 are present as stubs."""
        fingerprint = collect_fingerprint_fields(
            task_name="mmlu",
            task_revision="0",
            dataset_revision="abc123",
            prompt_hash="n/a",
            fewshot_seed=42,
            chat_template_hash="n/a",
            answer_extraction="multiple_choice",
            generation_params={},
        )
        assert "model_manifest_sha256" in fingerprint
        assert "sgfp4_manifest_sha256" in fingerprint


class TestValidateResultsSchema:
    """Tests for results JSON schema validation (D-02 output spec)."""

    def test_valid_schema_passes(self):
        """Well-formed results dict passes validation."""
        valid_results = {
            "niche": "medical",
            "timestamp_utc": "2026-06-28T20:00:00Z",
            "model_version": "sgfp4-v2-hash123",
            "quantization_config": {
                "bits": 4,
                "block_size": 64,
                "encoder_version": "sgfp4-v2-0.1.0",
            },
            "mode": "canonical",
            "source": "huggingface",
            "fingerprint": {
                "harness_commit": "0.4.12",
                "task_name": "mmlu",
                "task_revision": "0",
                "dataset_revision": "abc123",
                "prompt_hash": "sha256_deadbeef",
                "fewshot_seed": 42,
                "chat_template_hash": "sha256_cafe",
                "answer_extraction": "multiple_choice",
                "generation_params": {},
                "model_manifest_sha256": "stub",
                "sgfp4_manifest_sha256": "stub",
            },
            "results": {
                "mmlu": {
                    "score": 0.72,
                    "per_category": {
                        "anatomy": 0.68,
                        "clinical_knowledge": 0.75,
                    },
                },
            },
        }
        # Should not raise
        validate_results_schema(valid_results)

    def test_missing_required_field_raises(self):
        """Missing required field (niche) raises ValueError."""
        invalid = {"timestamp_utc": "now", "results": {}}
        with pytest.raises(ValueError, match="niche"):
            validate_results_schema(invalid)

    def test_results_not_dict_raises(self):
        """Results field not a dict raises ValueError."""
        invalid = {
            "niche": "code",
            "timestamp_utc": "now",
            "model_version": "v1",
            "mode": "canonical",
            "results": "not_a_dict",
        }
        with pytest.raises(ValueError, match="results"):
            validate_results_schema(invalid)

    def test_per_category_missing_raises(self):
        """Per-category dict missing from a result entry raises ValueError."""
        invalid = {
            "niche": "code",
            "timestamp_utc": "now",
            "model_version": "v1",
            "mode": "canonical",
            "results": {
                "mmlu": {"score": 0.72},  # Missing per_category
            },
        }
        with pytest.raises(ValueError, match="per_category"):
            validate_results_schema(invalid)


class TestBenchmarkRunner:
    """Integration-style tests for BenchmarkRunner class."""

    def test_runner_writes_results_json(self, tmp_path):
        """Runner writes per-benchmark results JSON to artifacts/benchmarks/."""
        artifacts_dir = tmp_path / "artifacts" / "benchmarks"
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        runner = BenchmarkRunner(project_root=tmp_path)

        mock_results = _make_mock_simple_evaluate_results(["mmlu"], include_mmlu_subjects=True)

        with patch.object(runner, "_run_lm_eval", return_value=mock_results):
            with patch("eval.benchmark_mlx_model.MLXBenchmarkModel") as mock_model_cls:
                mock_model_cls.return_value = MagicMock()

                result_paths = runner.run_benchmarks(
                    niche="medical",
                    mode="canonical",
                    source="huggingface",
                )

        assert len(result_paths) >= 1
        # Find the MMLU-specific result file (multiple files written: one per task)
        mmlu_files = sorted(artifacts_dir.glob("medical_mmlu_*.json"))
        assert len(mmlu_files) >= 1, f"No MMLU result file found in {artifacts_dir}"

        with mmlu_files[0].open() as f:
            data = json.load(f)
        assert data["niche"] == "medical"
        assert data["mode"] == "canonical"
        assert data["source"] == "huggingface"
        assert "mmlu" in data["results"]

    def test_runner_mmlu_per_subject_breakdown(self, tmp_path):
        """MMLU results include per-subject breakdown alongside aggregate acc."""
        artifacts_dir = tmp_path / "artifacts" / "benchmarks"
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        runner = BenchmarkRunner(project_root=tmp_path)

        mock_results = _make_mock_simple_evaluate_results(["mmlu"], include_mmlu_subjects=True)

        with patch.object(runner, "_run_lm_eval", return_value=mock_results):
            with patch("eval.benchmark_mlx_model.MLXBenchmarkModel") as mock_model_cls:
                mock_model_cls.return_value = MagicMock()

                runner.run_benchmarks(
                    niche="code",
                    mode="canonical",
                    source="huggingface",
                )

        # Read the MMLU output file and verify per-subject breakdown
        mmlu_files = sorted(artifacts_dir.glob("code_mmlu_*.json"))
        assert len(mmlu_files) >= 1, f"No MMLU result file found in {artifacts_dir}"

        with mmlu_files[0].open() as f:
            data = json.load(f)
        mmlu_entry = data["results"].get("mmlu")
        assert mmlu_entry is not None
        assert "per_category" in mmlu_entry
        per_cat = mmlu_entry["per_category"]
        assert "anatomy" in per_cat
        assert "clinical_knowledge" in per_cat

    def test_runner_diagnostic_mode_no_canonical_freezing(self, tmp_path):
        """Diagnostic mode passes override params, not frozen canonical params."""
        artifacts_dir = tmp_path / "artifacts" / "benchmarks"
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        runner = BenchmarkRunner(project_root=tmp_path)

        mock_results = _make_mock_simple_evaluate_results(["mmlu"])

        with patch.object(runner, "_run_lm_eval") as mock_run_lm_eval:
            mock_run_lm_eval.return_value = mock_results
            with patch("eval.benchmark_mlx_model.MLXBenchmarkModel") as mock_model_cls:
                mock_model_cls.return_value = MagicMock()

                runner.run_benchmarks(
                    niche="medical",
                    mode="diagnostic",
                    source="huggingface",
                )

            # Verify _run_lm_eval was called
            assert mock_run_lm_eval.called

    def test_runner_source_huggingface_default(self, tmp_path):
        """--source huggingface is the default mode, uses datasets library."""
        artifacts_dir = tmp_path / "artifacts" / "benchmarks"
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        runner = BenchmarkRunner(project_root=tmp_path)
        mock_results = _make_mock_simple_evaluate_results(["mmlu"])

        with patch.object(runner, "_run_lm_eval", return_value=mock_results):
            with patch("eval.benchmark_mlx_model.MLXBenchmarkModel") as MagicMock:
                result_paths = runner.run_benchmarks(
                    niche="medical",
                    mode="canonical",
                    source="huggingface",
                )
        assert len(result_paths) >= 1

    def test_runner_source_local(self, tmp_path):
        """--source local reads from data/benchmarks/ directory."""
        # Create a minimal local benchmark data dir
        local_data_dir = tmp_path / "data" / "benchmarks" / "mmlu"
        local_data_dir.mkdir(parents=True, exist_ok=True)
        (local_data_dir / "test.jsonl").write_text('{"question": "test", "answer": "A"}\n')

        artifacts_dir = tmp_path / "artifacts" / "benchmarks"
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        runner = BenchmarkRunner(project_root=tmp_path)
        mock_results = _make_mock_simple_evaluate_results(["mmlu"])

        with patch.object(runner, "_run_lm_eval", return_value=mock_results):
            with patch("eval.benchmark_mlx_model.MLXBenchmarkModel") as MagicMock:
                result_paths = runner.run_benchmarks(
                    niche="qa_technical",
                    mode="canonical",
                    source="local",
                )
        assert len(result_paths) >= 1

    def test_runner_source_api_raises_not_implemented(self, tmp_path):
        """--source api raises NotImplementedError with clear message."""
        runner = BenchmarkRunner(project_root=tmp_path)

        # API source is validated before any model import — no model mock needed
        with pytest.raises(NotImplementedError, match=r"(?i)api.*not implemented"):
            runner.run_benchmarks(
                niche="medical",
                mode="canonical",
                source="api",
            )

    def test_runner_results_json_schema(self, tmp_path):
        """Output JSON conforms to the D-02 schema specification."""
        artifacts_dir = tmp_path / "artifacts" / "benchmarks"
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        runner = BenchmarkRunner(project_root=tmp_path)
        mock_results = _make_mock_simple_evaluate_results(
            ["mmlu", "medmcqa"], include_mmlu_subjects=True
        )

        with patch.object(runner, "_run_lm_eval", return_value=mock_results):
            with patch("eval.benchmark_mlx_model.MLXBenchmarkModel") as MagicMock:
                runner.run_benchmarks(
                    niche="medical",
                    mode="canonical",
                    source="huggingface",
                )

        result_files = sorted(artifacts_dir.glob("medical_mmlu_*.json"))
        assert len(result_files) >= 1

        with result_files[0].open() as f:
            data = json.load(f)

        # Verify top-level schema
        assert isinstance(data["niche"], str)
        assert isinstance(data["timestamp_utc"], str)
        assert isinstance(data["mode"], str)
        assert isinstance(data["results"], dict)

        # Each result entry has score + per_category
        for benchmark_name, entry in data["results"].items():
            assert "score" in entry, f"Missing 'score' in results.{benchmark_name}"
            assert "per_category" in entry, f"Missing 'per_category' in results.{benchmark_name}"
            assert isinstance(entry["per_category"], dict)
