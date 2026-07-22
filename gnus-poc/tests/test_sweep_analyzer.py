"""Tests for SweepAnalyzer and convergence-integrated temperature sweeps."""

import json
from pathlib import Path

import numpy as np
import pytest

from distill.convergence import ConvergenceConfig
from distill.distillation import Distiller
from distill.sweep_analyzer import SweepAnalyzer


class TestSweepAnalyzer:
    """Behavior tests for SweepAnalyzer — structured sweep output and convergence integration."""

    def test_save_produces_structured_json(self, tmp_path):
        """SweepAnalyzer.save() writes valid JSON at artifacts/sweeps/<niche>_sweep.json."""
        analysis = {
            "niche": "medical",
            "sweep_date": "2026-06-21T00:00:00Z",
            "best_temperature": 4.0,
            "best_loss": 2.345,
            "temperatures": {
                "1.0": {"final_loss": 3.456, "best_loss": 3.200, "steps_run": 150, "converged": False, "hard_stopped": False},
                "4.0": {"final_loss": 2.345, "best_loss": 2.100, "steps_run": 120, "converged": True, "hard_stopped": False},
            },
            "convergence": {
                "1.0": {"loss_curve": [3.5, 3.4, 3.3, 3.2], "status_log": ["continue", "continue", "continue", "warning"]},
                "4.0": {"loss_curve": [2.5, 2.3, 2.1, 2.1], "status_log": ["continue", "continue", "converged", "converged"]},
            },
        }
        analyzer = SweepAnalyzer(project_root=tmp_path)
        out_path = analyzer.save("medical", analysis)

        assert out_path.exists()
        assert out_path.name == "medical_sweep.json"
        assert str(out_path.parent).endswith("artifacts/sweeps")

        loaded = json.loads(out_path.read_text())
        assert loaded["niche"] == "medical"
        assert loaded["best_temperature"] == 4.0
        assert "temperatures" in loaded
        assert "convergence" in loaded

    def test_load_reads_previously_saved_sweep(self, tmp_path):
        """SweepAnalyzer.load() can read back a previously saved sweep analysis."""
        analysis = {
            "niche": "code",
            "sweep_date": "2026-06-21T00:00:00Z",
            "best_temperature": 8.0,
            "best_loss": 1.567,
            "temperatures": {},
            "convergence": {},
        }
        analyzer = SweepAnalyzer(project_root=tmp_path)
        analyzer.save("code", analysis)

        loaded = analyzer.load("code")
        assert loaded is not None
        assert loaded["niche"] == "code"
        assert loaded["best_temperature"] == 8.0

    def test_load_returns_none_for_missing_sweep(self, tmp_path):
        """SweepAnalyzer.load() returns None when no sweep file exists for the niche."""
        analyzer = SweepAnalyzer(project_root=tmp_path)
        loaded = analyzer.load("nonexistent")
        assert loaded is None

    def test_save_creates_parent_directories(self, tmp_path):
        """SweepAnalyzer.save() creates the artifacts/sweeps directory if needed."""
        analysis = {"niche": "patents", "best_temperature": 2.0, "best_loss": 3.0, "temperatures": {}, "convergence": {}}
        analyzer = SweepAnalyzer(project_root=tmp_path)
        out_path = analyzer.save("patents", analysis)
        assert out_path.parent.exists()


class TestDistillerSweepConvergence:
    """Integration tests: Distiller.sweep_temperature() with ConvergenceConfig tracks per-temperature convergence."""

    def test_sweep_with_convergence_config_produces_convergence_data(self):
        """sweep_temperature with ConvergenceConfig includes per-temperature convergence fields."""
        distiller = Distiller(temperature=2.0)
        student_logits = np.random.randn(5, 50).astype(np.float32)
        teacher_logprobs = [{i: -3.9 for i in range(50)} for _ in range(5)]
        target_ids = [0, 1, 2, 3, 4]

        config = ConvergenceConfig(
            distill_loss_target=0.1,
            distill_loss_warning=100.0,
            distill_loss_hard_stop=100.0,
            patience=3,
            min_delta=0.001,
        )

        result = distiller.sweep_temperature(
            student_logits, teacher_logprobs, target_ids,
            temperatures=[1.0],
            convergence_config=config,
        )

        assert "temperatures" in result
        assert "convergence" in result
        assert "best_temperature" in result
        assert "first_loss" in result  # Phase 1 backward compatibility
        assert "temperatures_final_loss" in result

        temp_data = result["temperatures"]["1.0"]
        assert "final_loss" in temp_data
        assert "best_loss" in temp_data
        assert "converged" in temp_data
        assert "hard_stopped" in temp_data

        conv_data = result["convergence"]["1.0"]
        assert "loss_curve" in conv_data
        assert "status_log" in conv_data
        assert len(conv_data["loss_curve"]) > 0

    def test_sweep_without_convergence_config_still_works(self):
        """sweep_temperature without ConvergenceConfig works as before (backward compatible)."""
        distiller = Distiller()
        student_logits = np.random.randn(5, 50).astype(np.float32)
        teacher_logprobs = [{i: -3.9 for i in range(50)} for _ in range(5)]
        target_ids = [0, 1, 2, 3, 4]

        result = distiller.sweep_temperature(
            student_logits, teacher_logprobs, target_ids,
            temperatures=[1.0, 4.0],
        )

        assert "best_temperature" in result
        assert len(result["temperatures_final_loss"]) == 2

    def test_sweep_hard_stop_detected(self):
        """When loss exceeds hard_stop, the per-temperature result marks hard_stopped=True."""
        distiller = Distiller(temperature=2.0)

        # Create logits that will produce very high loss
        student_logits = np.random.randn(5, 50).astype(np.float32)
        teacher_logprobs = [{i: -3.9 for i in range(50)} for _ in range(5)]
        target_ids = [0, 1, 2, 3, 4]

        # Set hard_stop extremely low so any loss triggers it
        config = ConvergenceConfig(
            distill_loss_hard_stop=0.001,
            distill_loss_warning=100.0,
            distill_loss_target=0.0001,
            patience=100,
            min_delta=0.0001,
        )

        result = distiller.sweep_temperature(
            student_logits, teacher_logprobs, target_ids,
            temperatures=[1.0],
            convergence_config=config,
        )

        temp_data = result["temperatures"]["1.0"]
        assert temp_data["hard_stopped"] is True
        assert temp_data["converged"] is False
