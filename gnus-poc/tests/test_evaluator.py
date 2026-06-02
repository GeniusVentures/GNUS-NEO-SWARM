"""Tests for SpecialistEvaluator."""

from unittest.mock import MagicMock, patch

import numpy as np

from eval.evaluator import SpecialistEvaluator


class TestSpecialistEvaluator:
    def test_evaluate_empty_samples(self):
        evaluator = SpecialistEvaluator()
        mock_model = MagicMock()
        mock_tokenizer = MagicMock()
        result = evaluator.evaluate(mock_model, mock_tokenizer, [], "test")
        assert result["niche"] == "test"
        assert result["num_samples"] == 0

    def test_rouge_l_identical(self):
        evaluator = SpecialistEvaluator()
        score = evaluator._rouge_l("hello world", "hello world")
        assert score == 1.0

    def test_rouge_l_different(self):
        evaluator = SpecialistEvaluator()
        score = evaluator._rouge_l("hello world", "goodbye mars")
        assert score < 0.5

    def test_rouge_l_empty(self):
        evaluator = SpecialistEvaluator()
        assert evaluator._rouge_l("", "hello") == 0.0
        assert evaluator._rouge_l("hello", "") == 0.0

    def test_lcs_length(self):
        evaluator = SpecialistEvaluator()
        assert evaluator._lcs_length(["a", "b", "c"], ["a", "b", "c"]) == 3
        assert evaluator._lcs_length(["a", "b", "c"], ["x", "y"]) == 0
        assert evaluator._lcs_length(["a", "b", "c"], ["a", "x", "b", "c"]) == 3
