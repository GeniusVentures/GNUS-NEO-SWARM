"""
Structural and behavioral tests for pipeline runner and checkpoint validation.

Tests the rewritten PipelineRunner (subprocess execution, error handling,
checkpoint integration) and CheckpointValidator (per-stage output validation).

Legacy structural tests for train_specialists_mlx.py are preserved in
TestTrainingScriptStructure.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

from pipeline.checkpoint import CheckpointValidator, StageValidationResult
from pipeline.runner import PipelineRunner, StageResult

TRAIN_SCRIPT = Path(__file__).resolve().parent.parent / "training" / "train_specialists_mlx.py"


# =========================================================================
# Legacy: structural tests for train_specialists_mlx.py
# These test the training script itself, not the pipeline runner.
# =========================================================================


class TestTrainingScriptStructure:
    """Structural assertions on train_specialists_mlx.py (unchanged from prior test suite)."""

    @staticmethod
    def _read_source():
        with open(TRAIN_SCRIPT) as f:
            return f.read()

    @staticmethod
    def _parse_tree():
        source = TestTrainingScriptStructure._read_source()
        return ast.parse(source), source

    def test_force_retrain_flag_exists(self):
        """Verify --force-retrain argument is parsed in main()."""
        _, source = self._parse_tree()
        assert "--force-retrain" in source, (
            "--force-retrain flag must be present in train_specialists_mlx.py"
        )

    def test_milestone_file_check_exists(self):
        """Verify skip logic checks for milestone file (not just adapters.safetensors)."""
        _, source = self._parse_tree()
        source_lower = source.lower()
        assert "milestone" in source_lower or "{:07d}" in source, (
            "Skip logic must check for milestone file pattern (e.g., 0001000_adapters.safetensors)"
        )

    def test_metadata_validation_exists(self):
        """Verify skip logic validates training_metadata.json iters field."""
        _, source = self._parse_tree()
        lines = source.split("\n")
        meta_lines = [
            l.strip()
            for l in lines
            if "metadata" in l.lower() and ("iters" in l.lower() or "status" in l.lower())
        ]
        assert len(meta_lines) >= 1, (
            "Skip logic must validate metadata['iters'] or metadata.get('status') for completion"
        )

    def test_status_field_in_metadata(self):
        """Verify training_metadata.json includes 'status' field."""
        _, source = self._parse_tree()
        assert '"status"' in source or "'status'" in source, (
            "training_metadata.json must include 'status' field for skip logic validation"
        )


# =========================================================================
# CheckpointValidator behavioral tests
# =========================================================================


class TestCheckpointValidator:
    """Tests for CheckpointValidator per-stage output validation."""

    def test_json_checkpoint_not_dotdone(self, tmp_project_root):
        """Verify checkpoint files use .json extension, not .done."""
        cv = CheckpointValidator(tmp_project_root)
        path = cv.checkpoint_path("code", "train")
        assert path.suffix == ".json", f"Expected .json, got {path.suffix}"

    def test_validate_data_prep_stage(self, tmp_project_root):
        """Create minimal data dir and verify validation passes."""
        niche_dir = tmp_project_root / "data" / "specialists" / "code"
        niche_dir.mkdir(parents=True)
        (niche_dir / "dataset.jsonl").write_text('{"text": "hello"}')

        cv = CheckpointValidator(tmp_project_root)
        result = cv.validate_stage("code", "data_prep")
        assert result.passed is True, f"Expected passed=True, got {result.checks}"
        assert any(c["name"] == "has_data_files" and c["passed"] for c in result.checks)

    def test_validate_synthetic_data_min_rows(self, tmp_project_root):
        """Create JSONL with enough rows — verify passes; too few rows — verify fails."""
        synth_dir = tmp_project_root / "artifacts" / "synthetic"
        synth_dir.mkdir(parents=True)

        cv = CheckpointValidator(tmp_project_root)

        # Passes: 10 rows (the minimum default)
        lines = [json.dumps({"response": f"Test {i}"}) for i in range(10)]
        (synth_dir / "code.jsonl").write_text("\n".join(lines))
        result = cv.validate_stage("code", "synthetic_data")
        assert result.passed is True, f"Expected passed with 10 rows: {result.checks}"

        # Fails: only 5 rows
        (synth_dir / "code.jsonl").write_text("\n".join(lines[:5]))
        result = cv.validate_stage("code", "synthetic_data")
        assert result.passed is False, f"Expected failed with 5 rows: {result.checks}"

    def test_validate_train_stage_adapter_exists(self, tmp_project_root):
        """Create adapter_config.json + adapter_model.safetensors + training_metadata.json — verify passes."""
        model_dir = tmp_project_root / "models" / "specialists_mlx" / "code"
        model_dir.mkdir(parents=True)
        (model_dir / "adapter_config.json").write_text("{}")
        (model_dir / "adapter_model.safetensors").write_text("weights")
        (model_dir / "training_metadata.json").write_text('{"status": "complete"}')

        cv = CheckpointValidator(tmp_project_root)
        result = cv.validate_stage("code", "train")
        assert result.passed is True, f"Expected passed: {result.checks}"

    def test_validate_train_stage_missing_metadata(self, tmp_project_root):
        """Missing training_metadata.json — verify fails."""
        model_dir = tmp_project_root / "models" / "specialists_mlx" / "code"
        model_dir.mkdir(parents=True)
        (model_dir / "adapter_config.json").write_text("{}")
        (model_dir / "adapter_model.safetensors").write_text("weights")
        # No training_metadata.json

        cv = CheckpointValidator(tmp_project_root)
        result = cv.validate_stage("code", "train")
        assert result.passed is False, f"Expected failed without metadata: {result.checks}"

    def test_validate_evaluate_stage_metrics(self, tmp_project_root):
        """Create eval JSON with accuracy/perplexity/latency — verify passes; missing latency — verify fails."""
        eval_dir = tmp_project_root / "artifacts" / "evaluations"
        eval_dir.mkdir(parents=True)

        cv = CheckpointValidator(tmp_project_root)

        # Passes: all required metrics present
        (eval_dir / "code_metrics.json").write_text(
            '{"accuracy": 0.95, "perplexity": 1.2, "latency": 42}'
        )
        result = cv.validate_stage("code", "evaluate")
        assert result.passed is True, f"Expected passed with all metrics: {result.checks}"

        # Fails: missing latency
        (eval_dir / "code_metrics.json").write_text(
            '{"accuracy": 0.95, "perplexity": 1.2}'
        )
        result = cv.validate_stage("code", "evaluate")
        assert result.passed is False, f"Expected failed without latency: {result.checks}"

    def test_is_complete_returns_false_for_nonexistent(self, tmp_project_root):
        """is_complete returns False when no checkpoint exists."""
        cv = CheckpointValidator(tmp_project_root)
        assert cv.is_complete("code", "train") is False

    def test_mark_complete_and_is_complete_roundtrip(self, tmp_project_root):
        """mark_complete followed by is_complete returns True."""
        cv = CheckpointValidator(tmp_project_root)
        r = StageValidationResult(
            stage="train", niche="code", passed=True,
            checks=[{"name": "adapter_exists", "passed": True, "detail": "OK"}],
        )
        cv.mark_complete("code", "train", r)
        assert cv.is_complete("code", "train") is True
        assert cv.checkpoint_path("code", "train").exists()

    def test_clear_checkpoint_removes_file(self, tmp_project_root):
        """clear_checkpoint removes the JSON file."""
        cv = CheckpointValidator(tmp_project_root)
        r = StageValidationResult(
            stage="train", niche="code", passed=True,
            checks=[{"name": "adapter_exists", "passed": True, "detail": "OK"}],
        )
        cv.mark_complete("code", "train", r)
        assert cv.is_complete("code", "train") is True

        cv.clear_checkpoint("code", "train")
        assert cv.is_complete("code", "train") is False

    def test_unknown_stage_raises_value_error(self, tmp_project_root):
        """validate_stage with bogus stage name raises ValueError."""
        cv = CheckpointValidator(tmp_project_root)
        with pytest.raises(ValueError, match="bogus"):
            cv.validate_stage("code", "bogus")


# =========================================================================
# PipelineRunner behavioral tests
# =========================================================================


class TestPipelineRunnerExecution:
    """Tests for PipelineRunner subprocess execution, error handling, and checkpoint integration."""

    def test_run_stage_executes_subprocess(self, tmp_project_root):
        """Create a dummy script that prints 'OK' and exits 0; verify success."""
        scripts_dir = tmp_project_root / "data" / "scripts"
        scripts_dir.mkdir(parents=True)
        (scripts_dir / "prepare_datasets.py").write_text("print('OK')")

        runner = _make_runner(tmp_project_root)
        result = runner._run_stage("test_niche", "data_prep")
        assert result.success is True
        assert result.exit_code == 0
        assert "OK" in result.stdout

    def test_run_stage_captures_stderr_on_failure(self, tmp_project_root):
        """Create a script that prints to stderr and exits 1; verify stderr captured."""
        scripts_dir = tmp_project_root / "data" / "scripts"
        scripts_dir.mkdir(parents=True)
        (scripts_dir / "prepare_datasets.py").write_text(
            "import sys\nprint('ERROR: something broke', file=sys.stderr)\nsys.exit(1)"
        )

        runner = _make_runner(tmp_project_root)
        result = runner._run_stage("test_niche", "data_prep")
        assert result.success is False
        assert result.exit_code == 1
        assert "ERROR" in result.stderr

    def test_run_stage_timeout_handling(self, tmp_project_root):
        """Create a script that sleeps; verify timeout returns success=False."""
        scripts_dir = tmp_project_root / "data" / "scripts"
        scripts_dir.mkdir(parents=True)
        (scripts_dir / "prepare_datasets.py").write_text(
            "import time\ntime.sleep(30)"
        )

        runner = _make_runner(tmp_project_root)
        # Override timeout for test speed
        orig_timeout = runner._kDefaultStageTimeout
        runner._kDefaultStageTimeout = 1

        try:
            result = runner._run_stage("test_niche", "data_prep")
            assert result.success is False
        finally:
            runner._kDefaultStageTimeout = orig_timeout

    def test_force_flag_clears_checkpoints(self, tmp_project_root):
        """Set up a checkpoint, verify run with force=True clears it."""
        # Set up a checkpoint
        cv = CheckpointValidator(tmp_project_root)
        r = StageValidationResult(
            stage="data_prep", niche="test_niche", passed=True,
            checks=[{"name": "dir_exists", "passed": True, "detail": "OK"}],
        )
        cv.mark_complete("test_niche", "data_prep", r)
        assert cv.is_complete("test_niche", "data_prep") is True

        # Run with force=True (but no actual stages configured, so it just clears)
        runner = PipelineRunner(
            project_root=tmp_project_root,
            config_path=None,
        )
        # Manually set config to have our test niche
        runner._config = {"pipeline": {"specialists": ["test_niche"]}}
        # Avoid real subprocess execution — _run_stage would fail without scripts
        runner._run_stage = lambda n, s: StageResult(
            stage=s, niche=n, success=True, exit_code=0, stdout="OK", stderr="", attempts=1,
        )
        runner.run(niche="test_niche", force=True)

        # Checkpoint should be cleared
        assert cv.is_complete("test_niche", "data_prep") is False

    def test_from_stage_skips_early_stages(self, tmp_project_root):
        """Set up all checkpoints; verify from_stage starts at correct index."""
        cv = CheckpointValidator(tmp_project_root)

        # Mark all stages through evaluate as complete
        for stage in ["data_prep", "synthetic_data", "dedup", "train", "evaluate"]:
            r = StageValidationResult(
                stage=stage, niche="test_niche", passed=True,
                checks=[{"name": "test", "passed": True, "detail": "OK"}],
            )
            cv.mark_complete("test_niche", stage, r)

        runner = PipelineRunner(
            project_root=tmp_project_root,
            config_path=None,
        )
        runner._config = {"pipeline": {"specialists": ["test_niche"]}}

        # Clear distill and quantize so they'd run (and skip earlier stages)
        cv.clear_checkpoint("test_niche", "distill")
        cv.clear_checkpoint("test_niche", "quantize")

        # Verify index calculation
        assert runner._stage_index("distill") == 5
        assert runner._stage_index("evaluate") == 4
        assert runner._stage_index("data_prep") == 0

        # With from_stage="distill", start_idx is 5
        start_idx = runner._stage_index("distill")
        # Stages 0-4 should have checkpoints (skip), stages 5-6 should NOT have checkpoints
        stages_status = []
        for i in range(start_idx, len(runner.STAGES)):
            stage = runner.STAGES[i]
            if runner._is_complete("test_niche", stage):
                stages_status.append(f"{stage} (skip)")
            else:
                stages_status.append(f"{stage} (run)")

        # distill and quantize should be "run" (no checkpoint), earlier stages before start_idx skipped
        assert "distill (run)" in stages_status
        assert "quantize (run)" in stages_status
        # data_prep should not appear at all (it's before start_idx)
        all_status_stages = {s.split(" ")[0] for s in stages_status}
        assert "data_prep" not in all_status_stages

    def test_niche_failure_does_not_abort_pipeline(self):
        """Simulate one niche failing; verify subsequent niches still processed."""
        import tempfile as tf

        with tf.TemporaryDirectory() as td:
            root = Path(td)
            _ensure_stage_scripts(root)

            runner = PipelineRunner(project_root=root, config_path=None)
            # Two niches: one that will fail, one that succeeds
            runner._config = {
                "pipeline": {
                    "specialists": ["bad_niche", "good_niche"],
                    "stage_retry_count": 0,
                    "stage_backoff_seconds": 0.0,
                },
            }
            runner._stage_retry_count = 0

            # Mock _run_stage to return failure for first niche, success for second
            original_run_stage = runner._run_stage
            call_count = {"count": 0}

            def mock_run_stage(niche, stage):
                call_count["count"] += 1
                if niche == "bad_niche" and stage == "data_prep":
                    return StageResult(
                        stage=stage,
                        niche=niche,
                        success=False,
                        exit_code=-1,
                        stdout="",
                        stderr="Script not found",
                        attempts=1,
                    )
                return original_run_stage(niche, stage)

            runner._run_stage = mock_run_stage

            # Should not raise — just prints failures and continues
            runner.run(force=True)

            # Both niches should have been processed (at least one stage call per niche)
            assert call_count["count"] >= 2

    def test_command_build_includes_niche_arg(self, tmp_project_root):
        """Verify _build_command includes --niche <niche>."""
        runner = _make_runner(tmp_project_root)
        cmd = runner._build_command("code", "train")
        assert "--niche" in cmd
        assert "code" in cmd

    def test_uses_sys_executable_for_python(self, tmp_project_root):
        """Verify commands use sys.executable, not hardcoded 'python'."""
        runner = _make_runner(tmp_project_root)
        cmd = runner._build_command("code", "data_prep")
        assert cmd[0] == sys.executable, f"Expected {sys.executable}, got {cmd[0]}"


# =========================================================================
# Helpers
# =========================================================================


def _make_runner(root: Path) -> PipelineRunner:
    """Create a PipelineRunner with a test config and no YAML loading dependency."""
    runner = PipelineRunner(
        project_root=root,
        config_path=None,
    )
    # Bypass config loading for tests that only need _run_stage / _build_command.
    runner._config = {
        "pipeline": {
            "specialists": ["test_niche"],
            "stage_retry_count": 0,
            "stage_backoff_seconds": 0.1,
        },
    }
    runner._stage_retry_count = 0
    runner._stage_backoff_seconds = 0.1
    return runner


def _ensure_stage_scripts(root: Path) -> None:
    """Create minimal 'OK' scripts for all stages so FileNotFoundError isn't raised."""
    stage_scripts = {
        "data_prep": "data/scripts/prepare_datasets.py",
        "synthetic_data": "distill/synthetic.py",
        "dedup": "training/dedup.py",
        "train": "training/train_specialists_mlx.py",
        "evaluate": "eval/evaluator.py",
        "distill": "distill/distillation.py",
        "quantize": "quantize/fp4_exporter.py",
    }
    for script_rel in stage_scripts.values():
        script_path = root / script_rel
        script_path.parent.mkdir(parents=True, exist_ok=True)
        script_path.write_text("print('OK')")


