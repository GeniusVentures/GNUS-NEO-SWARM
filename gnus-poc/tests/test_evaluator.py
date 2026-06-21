"""Tests for SpecialistEvaluator, MetricStore, ThresholdAdapter, and evaluation persistence."""

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from eval.evaluator import SpecialistEvaluator
from eval.metric_store import EvalMetrics, MetricStore


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


class TestMetricStore:
    """Tests for structured evaluation persistence (TRAIN-03)."""

    @pytest.fixture
    def metric_store(self, tmp_path):
        """Create a MetricStore scoped to a temporary directory."""
        return MetricStore(project_root=tmp_path)

    @pytest.fixture
    def sample_metrics(self):
        """Valid EvalMetrics with typical evaluation data."""
        return EvalMetrics(
            niche="medical",
            timestamp_utc="2026-06-21T12:00:00+00:00",
            num_samples=100,
            perplexity=12.5,
            bleu_score=0.45,
            rouge_l=0.55,
            latency_ms_mean=2.3,
            latency_ms_p95=5.1,
            gates_passed={
                "perplexity": {"passed": True, "threshold": 50.0, "value": 12.5},
                "bleu_score": {"passed": True, "threshold": 0.15, "value": 0.45},
            },
        )

    # --- Behavior 1: persist writes timestamped, versioned JSON ---
    def test_persist_creates_valid_json(self, metric_store, sample_metrics):
        out_path = metric_store.persist(sample_metrics)
        assert out_path.exists()
        data = json.loads(out_path.read_text(encoding="utf-8"))
        assert data["niche"] == "medical"
        assert data["version"] == "1.0"
        assert data["perplexity"] == 12.5
        assert "timestamp_utc" in data

    # --- Behavior 2: schema validation rejects invalid data ---
    def test_schema_validation_rejects_invalid(self, metric_store):
        with pytest.raises(ValueError, match="Missing required eval fields"):
            metric_store._validate({"niche": "test"})

    def test_schema_validation_accepts_valid(self, metric_store, sample_metrics):
        try:
            metric_store._validate(sample_metrics.__dict__)
        except ValueError:
            pytest.fail("Validation raised ValueError for valid EvalMetrics")

    # --- Behavior 3: load_prior retrieves prior runs for trend analysis ---
    def test_load_prior_retrieves_runs(self, metric_store, sample_metrics):
        # Persist two runs for the same niche
        metric_store.persist(sample_metrics)
        time.sleep(0.01)
        m2 = EvalMetrics(
            niche="medical",
            timestamp_utc="2026-06-21T13:00:00+00:00",
            num_samples=120,
            perplexity=11.0,
            bleu_score=0.48,
            rouge_l=0.57,
            latency_ms_mean=2.1,
            latency_ms_p95=4.8,
            gates_passed={},
            version="1.0",
        )
        metric_store.persist(m2)

        prior = metric_store.load_prior("medical")
        assert len(prior) == 2
        assert prior[0]["perplexity"] == 12.5
        assert prior[1]["perplexity"] == 11.0

    def test_load_prior_empty_for_unknown_niche(self, metric_store):
        prior = metric_store.load_prior("nonexistent")
        assert prior == []

    # --- Behavior 4: compute_deltas produces metric deltas ---
    def test_compute_deltas_basic(self, metric_store, sample_metrics):
        prior_run = {
            "niche": "medical",
            "perplexity": 15.0,
            "bleu_score": 0.40,
            "rouge_l": 0.50,
            "latency_ms_mean": 2.8,
            "latency_ms_p95": 6.0,
            "num_samples": 80,
        }
        deltas = metric_store.compute_deltas(sample_metrics.__dict__, [prior_run])
        assert "perplexity" in deltas
        # PPL dropped from 15.0 to 12.5 = improvement
        assert deltas["perplexity"]["delta_pct"] < 0  # negative means improvement
        assert deltas["bleu_score"]["delta_pct"] > 0   # positive means improvement

    def test_compute_deltas_no_prior(self, metric_store, sample_metrics):
        deltas = metric_store.compute_deltas(sample_metrics.__dict__, [])
        assert deltas == {}

    def test_compute_deltas_uses_most_recent(self, metric_store, sample_metrics):
        recent = {
            "niche": "medical",
            "perplexity": 20.0,
            "bleu_score": 0.30,
            "rouge_l": 0.40,
            "latency_ms_mean": 3.0,
            "latency_ms_p95": 7.0,
            "num_samples": 90,
            "timestamp_utc": "2026-06-21T14:00:00+00:00",
        }
        older = {
            "niche": "medical",
            "perplexity": 10.0,
            "bleu_score": 0.60,
            "rouge_l": 0.70,
            "latency_ms_mean": 1.0,
            "latency_ms_p95": 2.0,
            "num_samples": 50,
            "timestamp_utc": "2026-06-21T10:00:00+00:00",
        }
        deltas = metric_store.compute_deltas(sample_metrics.__dict__, [older, recent])
        # Should compare against the most recent (20.0), not the older (10.0)
        assert deltas["perplexity"]["prior_value"] == 20.0

    # --- Behavior 5: corrupt JSON caught, logged, skipped (T-02-08) ---
    def test_corrupt_json_skipped_during_load(self, metric_store, sample_metrics):
        metric_store.persist(sample_metrics)
        # Write a corrupt file into the evaluations directory
        eval_dir = Path(metric_store._eval_dir)
        corrupt_path = eval_dir / "medical_corrupt.json"
        corrupt_path.write_text("this is not valid json{{{")

        prior = metric_store.load_prior("medical")
        # Should only load the valid file, skip the corrupt one
        assert len(prior) == 1
        assert prior[0]["niche"] == "medical"
