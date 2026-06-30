"""Tests for benchmark_trends + MetricStore benchmark persistence (Plan 04-04 Task 1).

Covers:
- MetricStore.record_benchmark_results / load_benchmark_results / load_all_benchmark_results
- Trend file append/load
- Trend delta computation
- Bootstrap CI (deterministic with seed)
- Degradation significance detection (D-09)
- Fingerprint validation non-breaking on bad fingerprint
"""

import json
from pathlib import Path

import pytest

from eval.metric_store import MetricStore
from eval.benchmark_trends import (
    append_to_trend_file,
    load_trend_file,
    compute_trend_deltas,
    bootstrap_ci,
    is_degradation_significant,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _sample_results(niche: str = "medical", score: float = 0.72) -> dict:
    """Build a valid benchmark results payload per Plan 04-01 schema."""
    return {
        "niche": niche,
        "timestamp_utc": "2026-06-28T14:30:00Z",
        "model_version": "v0.1.0",
        "quantization_config": {"effective_bpw": 3.2},
        "mode": "canonical",
        "fingerprint": {
            "harness_commit": "abc123",
            "task_name": "mmlu",
            "task_revision": None,
            "dataset_revision": None,
            "prompt_hash": "deadbeef",
            "fewshot_seed": 42,
            "chat_template_hash": "none",
            "answer_extraction": "default",
            "generation_params": {"temperature": 0.0},
            "model_manifest_sha256": "ff" * 32,
            "sgfp4_manifest_sha256": "ee" * 32,
        },
        "results": {
            "mmlu": {"score": score, "per_category": {"clinical_knowledge": score - 0.05}},
            "medmcqa": {"score": score - 0.1, "per_category": {"aggregate": score - 0.1}},
        },
    }


# ---------------------------------------------------------------------------
# Task 1 Tests 1-3: MetricStore benchmark persistence
# ---------------------------------------------------------------------------

class TestMetricStoreBenchmarkResults:
    """Tests for MetricStore benchmark result persistence (D-11 source of truth)."""

    def test_record_benchmark_results_writes_json(self, tmp_path):
        """Test 1: record_benchmark_results() writes results JSON to artifacts/benchmarks/."""
        store = MetricStore(project_root=tmp_path)
        results = _sample_results("medical", 0.72)

        out_path = store.record_benchmark_results("medical", "mmlu", results)

        assert isinstance(out_path, Path)
        assert out_path.exists()
        bench_dir = tmp_path / "artifacts" / "benchmarks"
        assert out_path.parent == bench_dir
        # Filename pattern: niche_benchmark_timestamp.json
        assert out_path.name.startswith("medical_mmlu_")
        assert out_path.suffix == ".json"

        with out_path.open() as f:
            data = json.load(f)
        assert data["niche"] == "medical"
        assert data["mode"] == "canonical"
        assert data["results"]["mmlu"]["score"] == 0.72

    def test_load_benchmark_results_most_recent(self, tmp_path):
        """Test 2: load_benchmark_results(niche, benchmark) returns most recent result."""
        store = MetricStore(project_root=tmp_path)

        old = _sample_results("medical", 0.50)
        old["timestamp_utc"] = "2026-06-01T00:00:00Z"
        store.record_benchmark_results("medical", "mmlu", old)

        new = _sample_results("medical", 0.80)
        new["timestamp_utc"] = "2026-06-28T00:00:00Z"
        store.record_benchmark_results("medical", "mmlu", new)

        loaded = store.load_benchmark_results("medical", "mmlu")
        assert loaded is not None
        # Most recent should be the higher-scoring run
        assert loaded["results"]["mmlu"]["score"] == 0.80

    def test_load_benchmark_results_none_when_empty(self, tmp_path):
        """Test 2 (cont.): load_benchmark_results returns None when no results exist."""
        store = MetricStore(project_root=tmp_path)
        loaded = store.load_benchmark_results("medical", "mmlu")
        assert loaded is None

    def test_load_all_benchmark_results_sorted(self, tmp_path):
        """Test 3: load_all_benchmark_results returns all results sorted by timestamp asc."""
        store = MetricStore(project_root=tmp_path)

        r1 = _sample_results("medical", 0.50)
        r1["timestamp_utc"] = "2026-06-01T00:00:00Z"
        store.record_benchmark_results("medical", "mmlu", r1)

        r2 = _sample_results("medical", 0.65)
        r2["timestamp_utc"] = "2026-06-15T00:00:00Z"
        store.record_benchmark_results("medical", "medmcqa", r2)

        r3 = _sample_results("medical", 0.80)
        r3["timestamp_utc"] = "2026-06-28T00:00:00Z"
        store.record_benchmark_results("medical", "mmlu", r3)

        all_results = store.load_all_benchmark_results("medical")
        assert len(all_results) == 3
        # Sorted ascending by timestamp
        assert all_results[0]["timestamp_utc"] == "2026-06-01T00:00:00Z"
        assert all_results[-1]["timestamp_utc"] == "2026-06-28T00:00:00Z"

    def test_record_benchmark_results_missing_required_keys(self, tmp_path):
        """record_benchmark_results raises ValueError when required keys are missing."""
        store = MetricStore(project_root=tmp_path)
        bad = {"niche": "medical"}  # missing timestamp_utc, mode, fingerprint, results
        with pytest.raises(ValueError):
            store.record_benchmark_results("medical", "mmlu", bad)

    def test_record_benchmark_results_invalid_fingerprint_flagged(self, tmp_path):
        """Test 10: results without a valid fingerprint hash are flagged but stored."""
        store = MetricStore(project_root=tmp_path)
        results = _sample_results("medical", 0.72)
        # Corrupt the fingerprint -- missing required field
        results["fingerprint"] = {"task_name": "mmlu"}  # incomplete

        out_path = store.record_benchmark_results("medical", "mmlu", results)
        assert out_path.exists()  # still stored (non-breaking)

        with out_path.open() as f:
            data = json.load(f)
        assert data.get("fingerprint_valid") is False

    def test_load_benchmark_run_by_fingerprint(self, tmp_path):
        """load_benchmark_run_by_fingerprint locates a run by its fingerprint hash."""
        store = MetricStore(project_root=tmp_path)
        results = _sample_results("medical", 0.72)

        store.record_benchmark_results("medical", "mmlu", results)

        # Compute the fingerprint hash the way the store does
        from eval.benchmark_fingerprint import fingerprint_hash
        fp_hash = fingerprint_hash(results["fingerprint"])

        found = store.load_benchmark_run_by_fingerprint("medical", "mmlu", fp_hash)
        assert found is not None
        assert found["results"]["mmlu"]["score"] == 0.72

    def test_phase3_sgfp4_methods_unchanged(self, tmp_path):
        """Existing Phase 3 SGFP4 API must remain intact."""
        store = MetricStore(project_root=tmp_path)
        fp4_stats = {
            "shape": [4096, 256],
            "num_superblocks": 4,
            "layout_distribution": {0: 3, 1: 1, 2: 0, 3: 0, 4: 0, 5: 0},
            "fp4_blocks": 100,
            "t158_blocks": 15,
            "effective_bpw": 3.2,
            "total_bytes": 8192,
        }
        out = store.record_sgfp4_metrics("code", fp4_stats)
        assert out.exists()
        loaded = store.load_sgfp4_metrics("code")
        assert loaded is not None
        all_metrics = store.list_all_metrics()
        assert "code" in all_metrics


# ---------------------------------------------------------------------------
# Task 1 Tests 4-5: Trend deltas
# ---------------------------------------------------------------------------

class TestTrendDeltas:
    """Tests for compute_trend_deltas (D-11 derived views)."""

    def test_compute_trend_deltas_with_two_runs(self, tmp_path):
        """Test 4: compute_trend_deltas returns per-benchmark delta with 2+ runs."""
        r1 = _sample_results("medical", 0.80)
        r1["timestamp_utc"] = "2026-06-01T00:00:00Z"
        append_to_trend_file("medical", r1, project_root=tmp_path)

        r2 = _sample_results("medical", 0.70)
        r2["timestamp_utc"] = "2026-06-28T00:00:00Z"
        append_to_trend_file("medical", r2, project_root=tmp_path)

        result = compute_trend_deltas("medical", project_root=tmp_path)
        assert result["status"] == "ok"
        # delta = curr (0.70 region) - prev (0.80 region) = negative (regression)
        assert "mmlu" in result["deltas"]
        assert result["deltas"]["mmlu"]["score"] == pytest.approx(0.70 - 0.80)
        assert "medmcqa" in result["deltas"]

    def test_compute_trend_deltas_insufficient_data(self, tmp_path):
        """Test 5: compute_trend_deltas with <2 records returns insufficient_data."""
        r1 = _sample_results("medical", 0.80)
        append_to_trend_file("medical", r1, project_root=tmp_path)

        result = compute_trend_deltas("medical", project_root=tmp_path)
        assert result["status"] == "insufficient_data"
        assert result["deltas"] == {}

    def test_compute_trend_deltas_skips_new_benchmark(self, tmp_path):
        """Benchmarks only present in one run are skipped (no delta)."""
        r1 = _sample_results("medical", 0.80)
        r1["timestamp_utc"] = "2026-06-01T00:00:00Z"
        # r1 has mmlu + medmcqa
        append_to_trend_file("medical", r1, project_root=tmp_path)

        r2 = _sample_results("medical", 0.70)
        r2["timestamp_utc"] = "2026-06-28T00:00:00Z"
        # r2 adds a brand-new benchmark not in r1
        r2["results"]["pubmedqa"] = {"score": 0.60, "per_category": {}}
        append_to_trend_file("medical", r2, project_root=tmp_path)

        result = compute_trend_deltas("medical", project_root=tmp_path)
        assert result["status"] == "ok"
        assert "pubmedqa" not in result["deltas"]  # new benchmark skipped
        assert "mmlu" in result["deltas"]  # shared benchmark reported


# ---------------------------------------------------------------------------
# Task 1 Tests 6-8: Bootstrap CI + degradation significance (D-09)
# ---------------------------------------------------------------------------

class TestBootstrapCI:
    """Tests for bootstrap_ci and is_degradation_significant (D-09)."""

    def test_bootstrap_ci_excludes_zero_when_all_negative(self):
        """Test 6: CI excludes zero when all bootstrap replicates are negative."""
        diffs = [-0.05, -0.08, -0.10, -0.04, -0.06, -0.07, -0.09, -0.03]
        lower, upper = bootstrap_ci(diffs, n_bootstrap=2000, confidence=0.95, seed=42)
        # All deltas negative -> CI entirely below zero
        assert upper < 0.0, f"expected upper bound < 0, got {upper}"
        assert lower < upper

    def test_bootstrap_ci_includes_zero_when_centered(self):
        """Test 7: CI includes zero when differences are zero-centered."""
        diffs = [-0.02, -0.01, 0.0, 0.01, 0.02, -0.015, 0.015, 0.005, -0.005]
        lower, upper = bootstrap_ci(diffs, n_bootstrap=2000, confidence=0.95, seed=42)
        assert lower <= 0.0 <= upper, f"expected CI to include 0, got ({lower}, {upper})"

    def test_bootstrap_ci_deterministic_with_seed(self):
        """Bootstrap CI is deterministic given the same seed."""
        diffs = [-0.05, -0.08, -0.10, -0.04, -0.06, -0.07]
        ci_a = bootstrap_ci(diffs, n_bootstrap=1000, seed=123)
        ci_b = bootstrap_ci(diffs, n_bootstrap=1000, seed=123)
        assert ci_a == ci_b

    def test_bootstrap_ci_different_seeds_may_differ(self):
        """Different seeds can produce different CIs (sanity check on seeding)."""
        diffs = [-0.05, -0.08, -0.10, -0.04, -0.06, -0.07]
        # With a small sample the percentile endpoints can be identical across seeds;
        # just confirm it runs without error and returns finite bounds.
        ci_a = bootstrap_ci(diffs, n_bootstrap=500, seed=1)
        ci_b = bootstrap_ci(diffs, n_bootstrap=500, seed=999)
        assert all(isinstance(x, float) for x in ci_a)
        assert all(isinstance(x, float) for x in ci_b)

    def test_bootstrap_ci_empty_input(self):
        """bootstrap_ci with empty input returns (0.0, 0.0) without raising."""
        lower, upper = bootstrap_ci([], n_bootstrap=100, seed=0)
        assert lower == 0.0
        assert upper == 0.0

    def test_is_degradation_significant_true_when_ci_excludes_zero_and_negative(self):
        """Test 8: significant regression when CI excludes zero AND delta negative."""
        # Strong negative differences -- a real regression
        prev_scores = {"mmlu": {"score": 0.80, "per_category": {"a": 0.85, "b": 0.78, "c": 0.82, "d": 0.75}}}
        curr_scores = {"mmlu": {"score": 0.60, "per_category": {"a": 0.60, "b": 0.55, "c": 0.62, "d": 0.58}}}

        result = is_degradation_significant(curr_scores, prev_scores, seed=42)
        assert "mmlu" in result
        assert result["mmlu"]["significant"] is True
        assert result["mmlu"]["mean_delta"] < 0.0
        assert result["mmlu"]["ci_upper"] < 0.0

    def test_is_degradation_significant_false_when_ci_includes_zero(self):
        """Test 8 (cont.): NOT significant when CI includes zero (no real regression)."""
        prev_scores = {"mmlu": {"score": 0.70, "per_category": {"a": 0.72, "b": 0.68, "c": 0.71, "d": 0.69}}}
        # Small mixed-sign differences around zero
        curr_scores = {"mmlu": {"score": 0.705, "per_category": {"a": 0.71, "b": 0.72, "c": 0.68, "d": 0.71}}}

        result = is_degradation_significant(curr_scores, prev_scores, seed=42)
        assert result["mmlu"]["significant"] is False


# ---------------------------------------------------------------------------
# Task 1 Test 9: Trend file append
# ---------------------------------------------------------------------------

class TestTrendFileAppend:
    """Tests for append_to_trend_file (D-11 derived view)."""

    def test_append_creates_trend_file(self, tmp_path):
        """Test 9: append_to_trend_file creates file if it does not exist."""
        results = _sample_results("medical", 0.72)
        out_path = append_to_trend_file("medical", results, project_root=tmp_path)

        assert isinstance(out_path, Path)
        assert out_path.exists()
        trends_dir = tmp_path / "artifacts" / "trends"
        assert out_path.parent == trends_dir
        assert out_path.name == "medical_trend.json"

        with out_path.open() as f:
            data = json.load(f)
        assert data["niche"] == "medical"
        assert len(data["runs"]) == 1
        run = data["runs"][0]
        assert run["timestamp"] == "2026-06-28T14:30:00Z"
        assert run["model_version"] == "v0.1.0"
        assert "mmlu" in run["results"]

    def test_append_to_existing_trend_file(self, tmp_path):
        """append_to_trend_file appends to existing file without overwriting."""
        r1 = _sample_results("medical", 0.50)
        r1["timestamp_utc"] = "2026-06-01T00:00:00Z"
        append_to_trend_file("medical", r1, project_root=tmp_path)

        r2 = _sample_results("medical", 0.80)
        r2["timestamp_utc"] = "2026-06-28T00:00:00Z"
        append_to_trend_file("medical", r2, project_root=tmp_path)

        loaded = load_trend_file("medical", project_root=tmp_path)
        assert len(loaded["runs"]) == 2
        assert loaded["runs"][0]["timestamp"] == "2026-06-01T00:00:00Z"
        assert loaded["runs"][1]["timestamp"] == "2026-06-28T00:00:00Z"

    def test_load_trend_file_missing_returns_empty(self, tmp_path):
        """load_trend_file returns empty runs list when file does not exist."""
        loaded = load_trend_file("nonexistent", project_root=tmp_path)
        assert loaded["runs"] == []
        assert loaded["niche"] == "nonexistent"
