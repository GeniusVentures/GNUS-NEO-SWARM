"""Tests for knowledge distillation module — logit-based KD with teacher logprobs."""

import numpy as np

from distill.distillation import Distiller


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
