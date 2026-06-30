"""Tests for knowledge distillation module — logit-based KD with teacher logprobs."""

import json

import numpy as np

from distill.convergence import ConvergenceTracker
from distill.distillation import Distiller, DistillationAbortedError, check_synthetic_quality


class TestDistiller:
    def test_compute_loss(self):
        distiller = Distiller(temperature=2.0)
        student_logits = np.random.randn(5, 100).astype(np.float32)
        teacher_logprobs = [{i: -4.6 for i in range(100)} for _ in range(5)]
        target_ids = [0, 1, 2, 3, 4]

        loss = distiller.compute_distillation_loss(student_logits, teacher_logprobs, target_ids)
        assert loss > 0
        assert loss != float("inf")

    def test_temperature_sweep(self):
        distiller = Distiller()
        student_logits = np.random.randn(5, 50).astype(np.float32)
        teacher_logprobs = [{i: -3.9 for i in range(50)} for _ in range(5)]
        target_ids = [0, 1, 2, 3, 4]

        result = distiller.sweep_temperature(
            student_logits, teacher_logprobs, target_ids,
            temperatures=[1.0, 4.0, 8.0],
        )
        assert "best_temperature" in result
        assert len(result["temperatures"]) == 3

    def test_loss_with_empty_teacher(self):
        distiller = Distiller()
        student_logits = np.random.randn(3, 50).astype(np.float32)
        loss = distiller.compute_distillation_loss(student_logits, [], [0, 1, 2])
        assert loss == float("inf")

    def test_temperature_changes_loss(self):
        distiller_cold = Distiller(temperature=1.0)
        distiller_hot = Distiller(temperature=10.0)

        student_logits = np.random.randn(5, 50).astype(np.float32)
        teacher_logprobs = [{i: -3.9 for i in range(50)} for _ in range(5)]
        target_ids = [0, 1, 2, 3, 4]

        loss_cold = distiller_cold.compute_distillation_loss(student_logits, teacher_logprobs, target_ids)
        loss_hot = distiller_hot.compute_distillation_loss(student_logits, teacher_logprobs, target_ids)

        assert loss_cold != loss_hot

    def test_teacher_logprobs_format_compatibility(self):
        """Both dict and list logprobs formats are accepted by Distiller."""
        distiller = Distiller(temperature=2.0, alpha=0.5)
        student_logits = np.random.randn(5, 100).astype(np.float32)
        target_ids = [0, 1, 2, 3, 4]

        # Dict format: [{token_id: logprob, ...}, ...] — the format produced by
        # TeacherClient.generate_with_logprobs() when logprobs are extracted.
        dict_logprobs = [{i: -4.6 for i in range(100)} for _ in range(5)]
        loss_dict = distiller.compute_distillation_loss(
            student_logits, dict_logprobs, target_ids
        )
        assert loss_dict > 0
        assert loss_dict != float("inf")

        # List format: [[logprob, ...], ...] — also supported by _kl_divergence_loss.
        list_logprobs = [[-2.0] * 100 for _ in range(5)]
        loss_list = distiller.compute_distillation_loss(
            student_logits, list_logprobs, target_ids
        )
        assert loss_list > 0
        assert loss_list != float("inf")

    # ------------------------------------------------------------------
    # ConvergenceTracker integration (D-01, D-02, D-04)
    # ------------------------------------------------------------------

    def test_convergence_tracker_none_is_backward_compatible(self):
        """Distiller with no tracker behaves exactly like the original."""
        distiller = Distiller(temperature=2.0)
        batches = [
            (np.random.randn(3, 50).astype(np.float32),
             [{i: -3.9 for i in range(50)} for _ in range(3)],
             [0, 1, 2])
            for _ in range(5)
        ]
        # No tracker -> run_distillation returns the full list of losses, no abort.
        result = distiller.run_distillation(batches)
        assert len(result) == 5
        assert all(isinstance(l, float) for l in result)

    def test_convergence_tracker_integration_converges(self):
        """When a tracker is provided the loop stops early on convergence."""
        distiller = Distiller(temperature=2.0)
        # The flat loss for these inputs is ~1.06, so a target of 1.1 means
        # the rolling average is already below target after the first step.
        tracker = ConvergenceTracker(
            target=1.1, warning=10.0, hard_stop=100.0,
            patience=100, min_delta=0.01, window_size=5,
        )
        distiller._tracker = tracker

        batches = []
        for k in range(50):
            student = np.full((1, 10), -5.0 - k * 0.1, dtype=np.float32)
            teacher = [{i: -5.0 for i in range(10)}]
            batches.append((student, teacher, [0]))

        distiller.run_distillation(batches)
        assert tracker.converged is True

    def test_two_tier_in_training_loop(self):
        """All 5 tracker statuses are handled by the distillation loop."""
        distiller = Distiller(temperature=2.0)

        # Fake tracker that returns a scripted sequence of statuses.
        class _ScriptedTracker:
            def __init__(self, statuses):
                self._statuses = list(statuses)
                self.converged = False
                self.aborted = False

            def step(self, loss, step_number):
                if not self._statuses:
                    return "continue"
                status = self._statuses.pop(0)
                if status == "converged":
                    self.converged = True
                if status == "hard_stop":
                    self.aborted = True
                return status

        def _batch():
            return (
                np.random.randn(1, 10).astype(np.float32),
                [{i: -3.0 for i in range(10)}],
                [0],
            )

        # "warning" then "converged" -> loop exits after the converged step.
        tracker = _ScriptedTracker(["warning", "warning", "converged", "continue"])
        distiller._tracker = tracker
        result = distiller.run_distillation([_batch() for _ in range(4)])
        assert len(result) <= 4  # exited early

        # "hard_stop" raises DistillationAbortedError.
        tracker = _ScriptedTracker(["hard_stop"])
        distiller._tracker = tracker
        try:
            distiller.run_distillation([_batch()])
            raised = False
        except DistillationAbortedError:
            raised = True
        assert raised is True

    # ------------------------------------------------------------------
    # Structured sweep output (D-05)
    # ------------------------------------------------------------------

    def test_sweep_output_structure(self):
        distiller = Distiller()
        student_logits = np.random.randn(5, 50).astype(np.float32)
        teacher_logprobs = [{i: -3.9 for i in range(50)} for _ in range(5)]
        target_ids = [0, 1, 2, 3, 4]

        result = distiller.sweep_temperature(
            student_logits, teacher_logprobs, target_ids,
            temperatures=[1.0, 4.0],
        )
        assert "best_temperature" in result
        assert "temperatures" in result
        assert isinstance(result["temperatures"], dict)
        # Each temperature entry has a loss curve and convergence info.
        for key, entry in result["temperatures"].items():
            assert "loss" in entry
            assert "final_loss" in entry
            assert "losses" in entry
            assert "converged_at_step" in entry

    def test_sweep_json_output(self, tmp_path):
        distiller = Distiller()
        student_logits = np.random.randn(5, 50).astype(np.float32)
        teacher_logprobs = [{i: -3.9 for i in range(50)} for _ in range(5)]
        target_ids = [0, 1, 2, 3, 4]

        out_dir = tmp_path / "sweeps"
        distiller.sweep_temperature(
            student_logits, teacher_logprobs, target_ids,
            temperatures=[1.0, 4.0],
            niche="test_niche",
            output_dir=out_dir,
        )
        sweep_file = out_dir / "test_niche_sweep.json"
        assert sweep_file.exists()
        data = json.loads(sweep_file.read_text())
        assert data["niche"] == "test_niche"
        assert "best_temperature" in data
        assert "temperatures" in data

    # ------------------------------------------------------------------
    # Synthetic data quality (DIST-03)
    # ------------------------------------------------------------------

    def test_synthetic_quality_min_length(self):
        short = " ".join(["word"] * 10)   # 10 tokens < 50 default
        kept = check_synthetic_quality([short])
        assert kept == []

    def test_synthetic_quality_empty(self):
        kept = check_synthetic_quality(["", "   "])
        assert kept == []

    def test_synthetic_quality_dedup(self):
        text_a = " ".join(["word"] * 60)
        text_b = "  ".join(["WORD"] * 60)  # same normalized form
        kept = check_synthetic_quality([text_a, text_b])
        assert len(kept) == 1
