"""Tests for benchmark_repair (Plan 04-04 Task 2, D-10).

D-10: repair suggestions, NOT auto-mutation. The system advises; the operator
acts. 3rd consecutive failure blocks pipeline promotion -- manual intervention
required.
"""

import json
from pathlib import Path

import pytest

from eval.benchmark_repair import (
    generate_repair_report,
    save_repair_report,
    should_block_pipeline,
    _compute_severity,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _gate_result(niche: str, passed: bool, consecutive: dict, blocking: bool = False) -> dict:
    """Build a gate_check_benchmarks result shape (Plan 04-03)."""
    return {
        "niche": niche,
        "passed": passed,
        "checks": [],
        "blocking": blocking,
        "consecutive_failures": consecutive,
        "composite_result": None,
        "sgfp4_regression": None,
        "detail": "Benchmark gate evaluated",
    }


def _benchmark_results(niche: str, scores: dict, per_category: dict = None) -> dict:
    """Build a benchmark results payload.

    Args:
        niche: Specialist niche.
        scores: {benchmark: aggregate_score}
        per_category: {benchmark: {category: score}} -- optional.
    """
    results = {}
    per_category = per_category or {}
    for benchmark, score in scores.items():
        entry = {"score": score}
        if benchmark in per_category:
            entry["per_category"] = per_category[benchmark]
        else:
            entry["per_category"] = {"aggregate": score}
        results[benchmark] = entry
    return {
        "niche": niche,
        "timestamp_utc": "2026-06-28T14:30:00Z",
        "mode": "canonical",
        "fingerprint": {},
        "results": results,
    }


def _config(thresholds: dict = None) -> dict:
    """Build a config dict with per-benchmark hard_floor thresholds."""
    thresholds = thresholds or {}
    cfg = {"eval_gates": {}, "benchmarks": {}}
    for benchmark, floor in thresholds.items():
        cfg["benchmarks"][benchmark] = {"hard_floor": floor}
    return cfg


# ---------------------------------------------------------------------------
# Tests 1-2: Basic report generation
# ---------------------------------------------------------------------------

class TestRepairReportGeneration:
    """Tests for generate_repair_report structure and pass/fail handling."""

    def test_below_threshold_produces_full_report(self):
        """Test 1: below-threshold results produce full structured report."""
        gate = _gate_result("medical", passed=False, consecutive={"medmcqa": 1})
        results = _benchmark_results("medical", {"medmcqa": 0.28, "mmlu": 0.72})
        cfg = _config({"medmcqa": 0.30, "mmlu": 0.50})

        report = generate_repair_report("medical", gate, results, config=cfg)

        assert report["niche"] == "medical"
        assert "timestamp_utc" in report
        assert report["status"] == "failures"
        assert report["severity"] == "warning"
        assert report["consecutive_failures"] == 1
        assert len(report["underperforming_categories"]) >= 1
        assert "suggested_config_adjustments" in report
        assert report["action_required"] == "review_and_adjust"
        assert "report_id" in report

        # Underperformance entry for medmcqa
        under = report["underperforming_categories"][0]
        assert under["benchmark"] == "medmcqa"
        assert under["score"] == pytest.approx(0.28)
        assert under["threshold"] == pytest.approx(0.30)
        assert under["margin"] == pytest.approx(-0.02)

    def test_all_passing_report(self):
        """Test 2: all-passing results produce all_passing status, severity none."""
        gate = _gate_result("medical", passed=True, consecutive={})
        results = _benchmark_results("medical", {"medmcqa": 0.40, "mmlu": 0.72})
        cfg = _config({"medmcqa": 0.30, "mmlu": 0.50})

        report = generate_repair_report("medical", gate, results, config=cfg)

        assert report["status"] == "all_passing"
        assert report["severity"] == "none"
        assert report["underperforming_categories"] == []
        assert report["action_required"] == "none"

    def test_medical_medmcqa_below_hard_floor(self):
        """Test 3: medical MedMCQA at -0.12 below hard floor triggers suggestions."""
        gate = _gate_result("medical", passed=False, consecutive={"medmcqa": 2})
        results = _benchmark_results(
            "medical",
            {"medmcqa": 0.18, "mmlu": 0.70},
            per_category={"medmcqa": {"aggregate": 0.18}},
        )
        cfg = _config({"medmcqa": 0.30, "mmlu": 0.50})

        report = generate_repair_report("medical", gate, results, config=cfg)

        medmcqa_entries = [
            u for u in report["underperforming_categories"]
            if u["benchmark"] == "medmcqa"
        ]
        assert len(medmcqa_entries) >= 1
        entry = medmcqa_entries[0]
        assert entry["margin"] == pytest.approx(-0.12)

        # Severity 2 -> critical
        assert report["severity"] == "critical"

        # Should suggest distillation config adjustments
        suggestions = report["suggested_config_adjustments"]
        assert len(suggestions) >= 1
        params = {s["parameter"] for s in suggestions}
        # At least one distillation-related parameter is suggested
        assert any("distill" in p or "iterations" in p for p in params)


# ---------------------------------------------------------------------------
# Tests 4-5: Severity escalation (D-10)
# ---------------------------------------------------------------------------

class TestSeverityEscalation:
    """Tests for _compute_severity per D-10 escalation rules."""

    def test_first_failure_warning(self):
        """Test 4: 1st consecutive failure -> warning."""
        assert _compute_severity({"medmcqa": 1}) == "warning"

    def test_second_failure_critical(self):
        """Test 4: 2nd consecutive failure -> critical."""
        assert _compute_severity({"medmcqa": 2}) == "critical"

    def test_third_failure_blocking(self):
        """Test 4: 3rd+ consecutive failure -> blocking."""
        assert _compute_severity({"medmcqa": 3}) == "blocking"
        assert _compute_severity({"medmcqa": 4}) == "blocking"

    def test_zero_failures_none(self):
        """No failures -> severity none."""
        assert _compute_severity({}) == "none"
        assert _compute_severity({"medmcqa": 0}) == "none"

    def test_highest_failure_count_used(self):
        """Test 5: severity uses the HIGHEST consecutive count across benchmarks."""
        # mmlu at 1, medmcqa at 3 -> blocking (highest wins)
        assert _compute_severity({"mmlu": 1, "medmcqa": 3}) == "blocking"
        # mmlu at 2, medmcqa at 1 -> critical
        assert _compute_severity({"mmlu": 2, "medmcqa": 1}) == "critical"

    def test_consecutive_failure_counter_maps_to_severity(self):
        """Test 5 (cont.): gate state consecutive_failures maps to severity."""
        gate = _gate_result("code", passed=False, consecutive={"humaneval": 3},
                            blocking=True)
        results = _benchmark_results("code", {"humaneval": 0.10})
        cfg = _config({"humaneval": 0.50})

        report = generate_repair_report("code", gate, results, config=cfg)

        assert report["severity"] == "blocking"
        assert report["consecutive_failures"] == 3


# ---------------------------------------------------------------------------
# Test 6: JSON-serializable
# ---------------------------------------------------------------------------

class TestReportSerialization:
    """Tests for JSON serialization of repair reports."""

    def test_report_is_json_serializable(self):
        """Test 6: report contains only JSON-safe types."""
        gate = _gate_result("medical", passed=False, consecutive={"medmcqa": 2})
        results = _benchmark_results("medical", {"medmcqa": 0.28, "mmlu": 0.72})
        cfg = _config({"medmcqa": 0.30, "mmlu": 0.50})

        report = generate_repair_report("medical", gate, results, config=cfg)

        # Must round-trip through JSON without error
        serialized = json.dumps(report)
        deserialized = json.loads(serialized)
        assert deserialized["niche"] == "medical"
        assert deserialized["severity"] == "critical"


# ---------------------------------------------------------------------------
# Test 7: Missing baseline
# ---------------------------------------------------------------------------

class TestMissingBaseline:
    """Tests for graceful handling of missing baseline."""

    def test_handles_missing_baseline(self):
        """Test 7: missing baseline is flagged, absolute threshold used."""
        gate = _gate_result("medical", passed=False, consecutive={"medmcqa": 1})
        results = _benchmark_results("medical", {"medmcqa": 0.28})
        cfg = _config({"medmcqa": 0.30})

        report = generate_repair_report("medical", gate, results, config=cfg)

        # No previous baseline -> report should still work using absolute threshold
        assert report["status"] == "failures"
        # Flag that no baseline was available for relative comparison
        assert report.get("no_baseline_available") is True


# ---------------------------------------------------------------------------
# Test 8: Per-category breakdown
# ---------------------------------------------------------------------------

class TestPerCategoryBreakdown:
    """Tests for per-benchmark, per-category underperformance breakdown."""

    def test_per_category_breakdown(self):
        """Test 8: report includes per-category underperformance entries."""
        gate = _gate_result("encyclopedic", passed=False, consecutive={"mmlu": 1})
        results = _benchmark_results(
            "encyclopedic",
            {"mmlu": 0.50},
            per_category={
                "mmlu": {
                    "clinical_knowledge": 0.35,
                    "college_medicine": 0.55,
                    "aggregate": 0.50,
                }
            },
        )
        # Per-category threshold of 0.50 for clinical_knowledge
        cfg = {
            "eval_gates": {},
            "benchmarks": {
                "mmlu": {
                    "hard_floor": 0.50,
                    "per_category_hard_floor": {"clinical_knowledge": 0.50},
                }
            },
        }

        report = generate_repair_report("encyclopedic", gate, results, config=cfg)

        cats = report["underperforming_categories"]
        # clinical_knowledge at 0.35 is below 0.50
        clin = [c for c in cats if c.get("category") == "clinical_knowledge"]
        assert len(clin) == 1
        assert clin[0]["score"] == pytest.approx(0.35)
        assert clin[0]["threshold"] == pytest.approx(0.50)
        assert clin[0]["margin"] == pytest.approx(-0.15)


# ---------------------------------------------------------------------------
# Tests for save_repair_report + should_block_pipeline
# ---------------------------------------------------------------------------

class TestSaveAndBlock:
    """Tests for save_repair_report and should_block_pipeline."""

    def test_save_repair_report_writes_json(self, tmp_path):
        """save_repair_report writes JSON to artifacts/repair_reports/."""
        gate = _gate_result("medical", passed=False, consecutive={"medmcqa": 2})
        results = _benchmark_results("medical", {"medmcqa": 0.28})
        cfg = _config({"medmcqa": 0.30})
        report = generate_repair_report("medical", gate, results, config=cfg)

        out = save_repair_report("medical", report, project_root=tmp_path)
        assert out.exists()
        assert out.parent == tmp_path / "artifacts" / "repair_reports"
        with out.open() as f:
            loaded = json.load(f)
        assert loaded["niche"] == "medical"

    def test_should_block_pipeline_true_at_3_failures(self):
        """should_block_pipeline returns True when blocking + 3+ failures."""
        gate = _gate_result("medical", passed=False, consecutive={"medmcqa": 3},
                            blocking=True)
        assert should_block_pipeline(gate) is True

    def test_should_block_pipeline_false_below_threshold(self):
        """should_block_pipeline returns False below 3 consecutive failures."""
        gate = _gate_result("medical", passed=False, consecutive={"medmcqa": 2},
                            blocking=False)
        assert should_block_pipeline(gate) is False

    def test_should_block_pipeline_false_when_not_blocking(self):
        """should_block_pipeline returns False when gate is not blocking."""
        gate = _gate_result("medical", passed=True, consecutive={"medmcqa": 0},
                            blocking=False)
        assert should_block_pipeline(gate) is False
