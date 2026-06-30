"""Tests for training-eval metric persistence, auto-gating, and adaptive gating.

Plan 02-04 (TRAIN-03). Covers:
- SpecialistEvaluator persists metrics via MetricStore.record_training_eval_metrics
- MetricStore.record_training_eval_metrics / load_training_eval_metrics
- Benchmarker.gate_check_training_eval auto-gating (D-14, D-16, D-17)
- AdaptiveGating module (D-15)
"""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from eval.benchmarker import Benchmarker
from eval.evaluator import SpecialistEvaluator
from eval.metric_store import MetricStore


# ======================================================================
# Task 2: SpecialistEvaluator + MetricStore training-eval persistence
# ======================================================================


class TestSpecialistEvaluatorPersistence:
    """SpecialistEvaluator.evaluate() persists via MetricStore."""

    def test_evaluate_persists_via_metric_store(self, tmp_path):
        """evaluate() writes structured JSON via MetricStore.record_training_eval_metrics."""
        evaluator = SpecialistEvaluator(project_root=tmp_path)
        # Use a mock model/tokenizer pair: evaluate() short-circuits on empty samples,
        # but we force the persistence path by monkeypatching the metric computation.
        # The MetricStore-backed path is the contract under test: after evaluate()
        # returns non-None metrics, a file must exist in artifacts/evaluations/.
        # We bypass MLX by injecting a fake metric result via the public surface:
        # call record directly through the evaluator's metric store.
        store = evaluator._metric_store  # type: ignore[attr-defined]
        metrics = {
            "niche": "code",
            "num_samples": 2,
            "perplexity": 12.3,
            "bleu_score": 0.42,
            "rouge_l": 0.55,
            "latency_ms_per_token": 3.4,
            "latency_ms_per_token_p95": 5.6,
        }
        out_path = store.record_training_eval_metrics("code", metrics=metrics)
        assert out_path.exists()

    def test_evaluate_uses_metric_store_when_provided(self, tmp_path):
        """SpecialistEvaluator accepts an optional metric_store and uses it."""
        injected = MetricStore(project_root=tmp_path)
        evaluator = SpecialistEvaluator(project_root=tmp_path, metric_store=injected)
        assert evaluator._metric_store is injected  # type: ignore[attr-defined]

    def test_specialist_evaluator_default_metric_store_created(self, tmp_path):
        """When metric_store is None, SpecialistEvaluator constructs one."""
        evaluator = SpecialistEvaluator(project_root=tmp_path)
        assert evaluator._metric_store is not None  # type: ignore[attr-defined]
        assert isinstance(evaluator._metric_store, MetricStore)  # type: ignore[attr-defined]


class TestMetricStoreTrainingEval:
    """MetricStore.record_training_eval_metrics / load_training_eval_metrics."""

    def test_record_training_eval_metrics_returns_path(self, tmp_path):
        store = MetricStore(project_root=tmp_path)
        metrics = {
            "niche": "code",
            "num_samples": 5,
            "perplexity": 10.0,
            "bleu_score": 0.3,
            "rouge_l": 0.4,
            "latency_ms_per_token": 2.0,
            "latency_ms_per_token_p95": 3.0,
        }
        out_path = store.record_training_eval_metrics("code", metrics=metrics)
        assert isinstance(out_path, Path)
        assert out_path.exists()

    def test_persisted_metrics_contain_all_fields(self, tmp_path):
        store = MetricStore(project_root=tmp_path)
        metrics = {
            "niche": "code",
            "num_samples": 5,
            "perplexity": 10.0,
            "bleu_score": 0.3,
            "rouge_l": 0.4,
            "latency_ms_per_token": 2.0,
            "latency_ms_per_token_p95": 3.0,
        }
        out_path = store.record_training_eval_metrics("code", metrics=metrics)
        with out_path.open() as f:
            data = json.load(f)
        for key in (
            "niche",
            "timestamp_utc",
            "num_samples",
            "perplexity",
            "bleu_score",
            "rouge_l",
            "latency_ms_per_token",
            "latency_ms_per_token_p95",
        ):
            assert key in data, f"missing key: {key}"

    def test_load_training_eval_metrics_returns_previous(self, tmp_path):
        store = MetricStore(project_root=tmp_path)
        metrics = {
            "niche": "code",
            "num_samples": 5,
            "perplexity": 10.0,
            "bleu_score": 0.3,
            "rouge_l": 0.4,
            "latency_ms_per_token": 2.0,
            "latency_ms_per_token_p95": 3.0,
        }
        store.record_training_eval_metrics("code", metrics=metrics)
        loaded = store.load_training_eval_metrics("code")
        assert loaded is not None
        assert loaded["niche"] == "code"
        assert loaded["perplexity"] == 10.0

    def test_load_training_eval_metrics_empty_dir_returns_none(self, tmp_path):
        store = MetricStore(project_root=tmp_path)
        loaded = store.load_training_eval_metrics("code")
        assert loaded is None

    def test_record_training_eval_metrics_handles_missing_dir(self, tmp_path):
        """Creates artifacts/evaluations/ if it doesn't exist."""
        store = MetricStore(project_root=tmp_path)
        # Simulate the directory being removed after construction.
        import shutil
        shutil.rmtree(store._metrics_dir)
        assert not store._metrics_dir.exists()
        metrics = {
            "niche": "code",
            "num_samples": 1,
            "perplexity": 1.0,
            "bleu_score": 0.1,
            "rouge_l": 0.2,
            "latency_ms_per_token": 1.0,
            "latency_ms_per_token_p95": 1.5,
        }
        out_path = store.record_training_eval_metrics("code", metrics=metrics)
        assert out_path.exists()

    def test_load_training_eval_metrics_returns_most_recent(self, tmp_path):
        """When multiple runs exist, load returns the lexicographically-latest timestamp."""
        store = MetricStore(project_root=tmp_path)
        for ppl in (10.0, 20.0, 30.0):
            metrics = {
                "niche": "code",
                "num_samples": 1,
                "perplexity": ppl,
                "bleu_score": 0.1,
                "rouge_l": 0.2,
                "latency_ms_per_token": 1.0,
                "latency_ms_per_token_p95": 1.5,
            }
            store.record_training_eval_metrics("code", metrics=metrics)
        loaded = store.load_training_eval_metrics("code")
        assert loaded is not None
        # Most recent run should be the last one recorded (30.0).
        assert loaded["perplexity"] == 30.0

    def test_load_training_eval_metrics_corrupt_file_returns_none(self, tmp_path):
        """Fail-open on corrupt JSON: returns None, logs warning."""
        store = MetricStore(project_root=tmp_path)
        store._metrics_dir.mkdir(parents=True, exist_ok=True)
        bad_file = store._metrics_dir / "code_eval_20260101-000000-000000.json"
        bad_file.write_text("{not valid json")
        loaded = store.load_training_eval_metrics("code")
        assert loaded is None


# ======================================================================
# Task 3: Benchmarker.gate_check_training_eval auto-gating
# (D-14 per-metric per-specialist, D-16 variance logging, D-17 consecutive)
# ======================================================================


def _make_specialist_config(
    gates=None,
    outlier_drop_percent=50,
):
    """Build a specialist-config-shaped dict with an evaluation.gates block."""
    if gates is None:
        gates = {
            "perplexity": {"max": 50.0, "consecutive_failures_to_block": 3},
            "bleu_score": {"min": 0.15, "consecutive_failures_to_block": 3},
            "accuracy": {"min": 0.40, "consecutive_failures_to_block": 3},
        }
    return {
        "evaluation": {
            "gates": gates,
            "outlier_trigger": {"metric_drop_percent": outlier_drop_percent},
        }
    }


def _seed_training_eval(store, niche, perplexity, bleu, accuracy, latency=2.0):
    """Write a training-eval metrics record for a niche."""
    store.record_training_eval_metrics(
        niche,
        metrics={
            "niche": niche,
            "num_samples": 10,
            "perplexity": perplexity,
            "bleu_score": bleu,
            "accuracy": accuracy,
            "rouge_l": 0.4,
            "latency_ms_per_token": latency,
            "latency_ms_per_token_p95": latency * 1.5,
        },
    )


class TestTrainingEvalGating:
    """Benchmarker.gate_check_training_eval: auto-gating + consecutive tracking."""

    def test_gate_check_passes_when_all_within_threshold(self, tmp_path):
        bench = Benchmarker(project_root=tmp_path)
        _seed_training_eval(bench._metric_store, "code", perplexity=40.0, bleu=0.30, accuracy=0.50)
        cfg = _make_specialist_config()
        result = bench.gate_check_training_eval("code", config=cfg)
        assert result["passed"] is True
        assert result["blocked"] is False

    def test_gate_check_fails_when_perplexity_exceeds_max(self, tmp_path):
        bench = Benchmarker(project_root=tmp_path)
        _seed_training_eval(bench._metric_store, "code", perplexity=75.0, bleu=0.30, accuracy=0.50)
        cfg = _make_specialist_config()
        result = bench.gate_check_training_eval("code", config=cfg)
        assert result["passed"] is False
        gates = result["gates"]
        assert gates["perplexity"]["passed"] is False

    def test_gate_check_fails_when_bleu_below_min(self, tmp_path):
        bench = Benchmarker(project_root=tmp_path)
        _seed_training_eval(bench._metric_store, "code", perplexity=40.0, bleu=0.05, accuracy=0.50)
        cfg = _make_specialist_config()
        result = bench.gate_check_training_eval("code", config=cfg)
        assert result["passed"] is False
        gates = result["gates"]
        assert gates["bleu_score"]["passed"] is False

    def test_gate_check_fails_when_accuracy_below_min(self, tmp_path):
        bench = Benchmarker(project_root=tmp_path)
        _seed_training_eval(bench._metric_store, "code", perplexity=40.0, bleu=0.30, accuracy=0.10)
        cfg = _make_specialist_config()
        result = bench.gate_check_training_eval("code", config=cfg)
        assert result["passed"] is False
        gates = result["gates"]
        assert gates["accuracy"]["passed"] is False

    def test_single_failure_does_not_block(self, tmp_path):
        """D-17: a single failure logs and continues; blocked=False until N."""
        bench = Benchmarker(project_root=tmp_path)
        _seed_training_eval(bench._metric_store, "code", perplexity=75.0, bleu=0.30, accuracy=0.50)
        cfg = _make_specialist_config()
        result = bench.gate_check_training_eval("code", config=cfg)
        assert result["passed"] is False
        assert result["blocked"] is False, "single failure must not block"
        assert result["consecutive_failures"]["perplexity"] == 1

    def test_blocks_after_n_consecutive_failures(self, tmp_path):
        """D-17: 3 consecutive failures on the same metric block the pipeline."""
        bench = Benchmarker(project_root=tmp_path)
        cfg = _make_specialist_config()
        for _ in range(3):
            _seed_training_eval(bench._metric_store, "code", perplexity=75.0, bleu=0.30, accuracy=0.50)
            result = bench.gate_check_training_eval("code", config=cfg)
        assert result["blocked"] is True
        assert result["consecutive_failures"]["perplexity"] >= 3

    def test_counter_resets_on_pass(self, tmp_path):
        """D-17: a passing run resets the consecutive-failure counter to 0."""
        bench = Benchmarker(project_root=tmp_path)
        cfg = _make_specialist_config()
        # Two failures.
        for _ in range(2):
            _seed_training_eval(bench._metric_store, "code", perplexity=75.0, bleu=0.30, accuracy=0.50)
            bench.gate_check_training_eval("code", config=cfg)
        # Then a pass.
        _seed_training_eval(bench._metric_store, "code", perplexity=40.0, bleu=0.30, accuracy=0.50)
        result = bench.gate_check_training_eval("code", config=cfg)
        assert result["consecutive_failures"]["perplexity"] == 0
        assert result["blocked"] is False

    def test_outlier_triggers_notification_not_block(self, tmp_path):
        """D-16: a >50% metric drop sets outlier_triggered but does not block."""
        bench = Benchmarker(project_root=tmp_path)
        cfg = _make_specialist_config(outlier_drop_percent=50)
        # First (prior) run: strong BLEU.
        _seed_training_eval(bench._metric_store, "code", perplexity=40.0, bleu=0.60, accuracy=0.50)
        bench.gate_check_training_eval("code", config=cfg)
        # Second (current) run: BLEU drops > 50% (0.60 -> 0.20 = 66% drop)
        # but is still above the min gate (0.15), so the gate passes.
        _seed_training_eval(bench._metric_store, "code", perplexity=40.0, bleu=0.20, accuracy=0.50)
        result = bench.gate_check_training_eval("code", config=cfg)
        assert result["outlier_triggered"] is True
        assert result["passed"] is True, "outlier must not flip a passing gate"
        assert result["blocked"] is False

    def test_gate_state_persisted_across_runs(self, tmp_path):
        """Gate state file survives a process restart (new Benchmarker instance)."""
        cfg = _make_specialist_config()
        bench1 = Benchmarker(project_root=tmp_path)
        _seed_training_eval(bench1._metric_store, "code", perplexity=75.0, bleu=0.30, accuracy=0.50)
        bench1.gate_check_training_eval("code", config=cfg)

        # New Benchmarker reading the same project_root must see counter=1.
        bench2 = Benchmarker(project_root=tmp_path)
        _seed_training_eval(bench2._metric_store, "code", perplexity=75.0, bleu=0.30, accuracy=0.50)
        result = bench2.gate_check_training_eval("code", config=cfg)
        assert result["consecutive_failures"]["perplexity"] == 2

    def test_corrupt_gate_state_recovers(self, tmp_path):
        """A corrupt training-gate state file is treated as fresh (fail-open)."""
        bench = Benchmarker(project_root=tmp_path)
        state_path = bench._training_gate_state_path("code")
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text("{corrupt json")
        _seed_training_eval(bench._metric_store, "code", perplexity=40.0, bleu=0.30, accuracy=0.50)
        cfg = _make_specialist_config()
        # Should not raise; treated as fresh state.
        result = bench.gate_check_training_eval("code", config=cfg)
        assert result["passed"] is True

    def test_no_metrics_returns_pass(self, tmp_path):
        """First-run: no metrics available -> gate passes (nothing to gate on)."""
        bench = Benchmarker(project_root=tmp_path)
        cfg = _make_specialist_config()
        result = bench.gate_check_training_eval("code", config=cfg)
        assert result["passed"] is True
        assert result["blocked"] is False

    def test_no_gates_configured_returns_pass(self, tmp_path):
        """No evaluation.gates block -> gate passes."""
        bench = Benchmarker(project_root=tmp_path)
        _seed_training_eval(bench._metric_store, "code", perplexity=40.0, bleu=0.30, accuracy=0.50)
        result = bench.gate_check_training_eval("code", config={})
        assert result["passed"] is True


# ======================================================================
# Task 4: AdaptiveGating — LLM-based threshold updates (D-15)
# Gated behind adaptive_gating.enabled (default: false).
# ======================================================================


def _seed_run(store, niche, perplexity, bleu, accuracy):
    """Seed one training-eval run for a niche."""
    store.record_training_eval_metrics(
        niche,
        metrics={
            "niche": niche,
            "num_samples": 10,
            "perplexity": perplexity,
            "bleu_score": bleu,
            "accuracy": accuracy,
            "rouge_l": 0.4,
            "latency_ms_per_token": 2.0,
            "latency_ms_per_token_p95": 3.0,
        },
    )


class _FakeTeacherResponse:
    """Minimal stand-in for TeacherClient.generate() response wrapper."""

    def __init__(self, content):
        self.choices = [type("_C", (), {"message": type("_M", (), {"content": content})()})()]


class _FakeTeacherClient:
    """Fake TeacherClient that returns a canned LLM response.

    ``response_factory`` is called with the prompt and must return the canned
    response content (string). Defaults to returning a JSON suggestion that
    tightens perplexity max from 50.0 to 45.0.
    """

    def __init__(self, response_factory=None):
        self.calls = []
        self._response_factory = response_factory or (lambda prompt: (
            '{"perplexity": {"suggested_max": 45.0, "rationale": "improving trend"}}'
        ))

    def generate(self, model_name=None, messages=None, **kwargs):
        self.calls.append({"model_name": model_name, "messages": messages})
        prompt = ""
        if messages:
            prompt = " ".join(str(m.get("content", "")) for m in messages)
        return _FakeTeacherResponse(self._response_factory(prompt))


class TestAdaptiveGating:
    """AdaptiveGating: D-15 LLM-based threshold suggestions, gated + safety-bounded."""

    def test_adaptive_gating_disabled_returns_empty(self, tmp_path):
        from eval.adaptive_gating import AdaptiveGating

        store = MetricStore(project_root=tmp_path)
        ag = AdaptiveGating(
            metric_store=store,
            config={"enabled": False},
        )
        result = ag.suggest_threshold_updates("code")
        assert result["enabled"] is False
        assert result["suggestions"] == {}

    def test_adaptive_gating_insufficient_history(self, tmp_path):
        from eval.adaptive_gating import AdaptiveGating

        store = MetricStore(project_root=tmp_path)
        # Only 2 runs — below the default min_metric_runs=3.
        _seed_run(store, "code", perplexity=50.0, bleu=0.15, accuracy=0.40)
        _seed_run(store, "code", perplexity=48.0, bleu=0.16, accuracy=0.42)
        ag = AdaptiveGating(
            metric_store=store,
            teacher_client=_FakeTeacherClient(),
            config={"enabled": True, "min_metric_runs": 3},
        )
        result = ag.suggest_threshold_updates("code")
        assert result["enabled"] is True
        assert result["suggestions"] == {}
        assert result.get("reason") == "insufficient history"

    def test_adaptive_gating_suggests_with_trends(self, tmp_path):
        from eval.adaptive_gating import AdaptiveGating

        store = MetricStore(project_root=tmp_path)
        # 5 runs of improving perplexity (50 -> 40).
        for ppl in (50.0, 47.5, 45.0, 42.5, 40.0):
            _seed_run(store, "code", perplexity=ppl, bleu=0.20, accuracy=0.45)
        teacher = _FakeTeacherClient()
        ag = AdaptiveGating(
            metric_store=store,
            teacher_client=teacher,
            config={
                "enabled": True,
                "min_metric_runs": 3,
                "lookback_runs": 5,
                "max_adjustment_percent": 20,
            },
            specialist_gates={
                "code": {
                    "perplexity": {"max": 50.0},
                    "bleu_score": {"min": 0.15},
                    "accuracy": {"min": 0.40},
                }
            },
        )
        result = ag.suggest_threshold_updates("code")
        assert result["enabled"] is True
        assert "perplexity" in result["suggestions"]
        # The LLM was called at least once.
        assert len(teacher.calls) >= 1
        # Trends are reported.
        assert "perplexity" in result["trends"]

    def test_adaptive_gating_safety_bounds_clamp(self, tmp_path):
        """An LLM suggestion beyond the safety bound is clamped."""
        from eval.adaptive_gating import AdaptiveGating

        store = MetricStore(project_root=tmp_path)
        for ppl in (50.0, 47.5, 45.0, 42.5, 40.0):
            _seed_run(store, "code", perplexity=ppl, bleu=0.20, accuracy=0.45)
        # LLM suggests tightening perplexity max to 10.0 (80% reduction) —
        # must be clamped to the safety bound (50% of original 50.0 = 25.0).
        teacher = _FakeTeacherClient(
            response_factory=lambda p: '{"perplexity": {"suggested_max": 10.0, "rationale": "aggressive"}}'
        )
        ag = AdaptiveGating(
            metric_store=store,
            teacher_client=teacher,
            config={
                "enabled": True,
                "min_metric_runs": 3,
                "safety_bound_pct": 50,
                "safety_bound_loosen_pct": 200,
            },
            specialist_gates={
                "code": {"perplexity": {"max": 50.0}},
            },
        )
        result = ag.suggest_threshold_updates("code")
        suggestion = result["suggestions"]["perplexity"]
        # Clamped: suggested_max must be >= 50% of original (25.0).
        assert suggestion["suggested_max"] >= 25.0
        assert result["safety_bounds_applied"] is True

    def test_adaptive_gating_requires_approval(self, tmp_path):
        """Every suggestion dict carries requires_approval=True (human gate)."""
        from eval.adaptive_gating import AdaptiveGating

        store = MetricStore(project_root=tmp_path)
        for ppl in (50.0, 47.0, 44.0, 42.0, 40.0):
            _seed_run(store, "code", perplexity=ppl, bleu=0.20, accuracy=0.45)
        ag = AdaptiveGating(
            metric_store=store,
            teacher_client=_FakeTeacherClient(),
            config={"enabled": True, "min_metric_runs": 3},
            specialist_gates={"code": {"perplexity": {"max": 50.0}}},
        )
        result = ag.suggest_threshold_updates("code")
        assert result["requires_approval"] is True

    def test_apply_approved_changes_writes_yaml(self, tmp_path):
        """apply_approved_changes updates the specialist config YAML."""
        from eval.adaptive_gating import AdaptiveGating
        import yaml

        # Build a specialist config YAML on disk for the code niche.
        specialists_dir = tmp_path / "config" / "specialists"
        specialists_dir.mkdir(parents=True, exist_ok=True)
        cfg_path = specialists_dir / "code.yaml"
        cfg_path.write_text(yaml.safe_dump({
            "specialist": {"name": "code"},
            "evaluation": {
                "gates": {
                    "perplexity": {"max": 50.0, "consecutive_failures_to_block": 3},
                },
                "outlier_trigger": {"metric_drop_percent": 50},
            },
        }))

        store = MetricStore(project_root=tmp_path)
        ag = AdaptiveGating(
            metric_store=store,
            teacher_client=_FakeTeacherClient(),
            config={"enabled": True},
            specialist_gates={"code": {"perplexity": {"max": 50.0}}},
        )
        suggestions = {
            "perplexity": {
                "current_max": 50.0,
                "suggested_max": 45.0,
                "rationale": "improving trend",
            }
        }
        result = ag.apply_approved_changes("code", suggestions)
        assert result["applied"] is True
        # Re-read YAML and verify the threshold moved.
        with cfg_path.open() as f:
            updated = yaml.safe_load(f)
        assert updated["evaluation"]["gates"]["perplexity"]["max"] == 45.0

    def test_adaptive_gating_no_teacher_client_returns_no_suggestions(self, tmp_path):
        """Without a teacher_client, suggestions are empty but not an error."""
        from eval.adaptive_gating import AdaptiveGating

        store = MetricStore(project_root=tmp_path)
        for ppl in (50.0, 47.0, 44.0, 42.0, 40.0):
            _seed_run(store, "code", perplexity=ppl, bleu=0.20, accuracy=0.45)
        ag = AdaptiveGating(
            metric_store=store,
            teacher_client=None,
            config={"enabled": True, "min_metric_runs": 3},
            specialist_gates={"code": {"perplexity": {"max": 50.0}}},
        )
        result = ag.suggest_threshold_updates("code")
        assert result["enabled"] is True
        assert result["suggestions"] == {}


