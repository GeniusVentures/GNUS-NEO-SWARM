"""Tests for Benchmarker."""

import json
from unittest.mock import MagicMock

from eval.benchmarker import Benchmarker
from eval.evaluator import SpecialistEvaluator


class TestBenchmarker:
    def test_compare_variants_empty(self):
        bench = Benchmarker()
        result = bench.compare_variants("test", [])
        assert result["niche"] == "test"
        assert result["variants"] == []
        assert result["best"] == {}

    def test_compare_variants_selects_best(self):
        bench = Benchmarker()
        variants = [
            {"variant": "rank8", "perplexity": 5.0, "bleu_score": 0.40, "rouge_l": 0.50, "latency_ms_per_token": 2.0},
            {"variant": "rank16", "perplexity": 4.5, "bleu_score": 0.45, "rouge_l": 0.55, "latency_ms_per_token": 2.5},
        ]
        result = bench.compare_variants("code", variants)
        assert result["best"]["perplexity"]["variant"] == "rank16"
        assert result["best"]["perplexity"]["value"] == 4.5

    def test_print_comparison_table_no_variants(self):
        bench = Benchmarker()
        bench.print_comparison_table({"niche": "test", "variants": [], "best": {}})

    def test_save_comparison(self, tmp_path):
        bench = Benchmarker(project_root=tmp_path)
        comparison = {"niche": "code", "variants": [], "best": {}}
        bench.save_comparison("code", comparison)
        out = tmp_path / "artifacts" / "benchmarks" / "code_comparison.json"
        assert out.exists()

    # ------------------------------------------------------------------
    # gate_check tests
    # ------------------------------------------------------------------

    def _make_sgfp4_metrics(self, tmp_path, niche_name, mse=0.005, bitrate=3.2, t158=0.15):
        """Helper: write SGFP4 metrics to MetricStore so gate_check can load them.

        Args:
            t158: Desired T158 ratio (derives t158_blocks / fp4_blocks accordingly).
        """
        from eval.metric_store import MetricStore

        store = MetricStore(project_root=tmp_path)
        total_blocks = 100
        t158_blocks = int(round(t158 * total_blocks))
        fp4_blocks = total_blocks - t158_blocks
        fp4_stats = {
            "shape": [4096, 256],
            "num_superblocks": 4,
            "layout_distribution": {0: 3, 1: 1},
            "fp4_blocks": fp4_blocks,
            "t158_blocks": t158_blocks,
            "effective_bpw": bitrate,
            "total_bytes": 8192,
            "per_block_errors": [mse] * 10,
        }
        store.record_sgfp4_metrics(niche_name, fp4_stats)
        return store

    def _make_gate_config(self, mse_max=0.01, mse_fail=3, bpw_max=4.0, bpw_fail=2, t158_min=0.05, t158_fail=2):
        """Helper: build config dict with eval_gates."""
        return {
            "eval_gates": {
                "fp4_mse": {"max": mse_max, "consecutive_failures_to_block": mse_fail},
                "fp4_effective_bitrate": {"max": bpw_max, "consecutive_failures_to_block": bpw_fail},
                "fp4_t158_ratio": {"min": t158_min, "consecutive_failures_to_block": t158_fail},
            }
        }

    def test_gate_check_all_pass(self, tmp_path):
        """gate_check returns passed=True when all SGFP4 metrics are within thresholds."""
        self._make_sgfp4_metrics(tmp_path, "code", mse=0.005, bitrate=3.2, t158=0.15)
        bench = Benchmarker(project_root=tmp_path)
        config = self._make_gate_config()
        result = bench.gate_check("code", config)
        assert result["passed"] is True
        assert result["blocking"] is False
        assert len(result["checks"]) == 3
        assert all(c["passed"] for c in result["checks"])

    def test_gate_check_mse_exceeds_max(self, tmp_path):
        """gate_check returns passed=False when fp4_mse exceeds max threshold."""
        self._make_sgfp4_metrics(tmp_path, "code", mse=0.05, bitrate=3.2, t158=0.15)
        bench = Benchmarker(project_root=tmp_path)
        config = self._make_gate_config(mse_max=0.01)
        result = bench.gate_check("code", config)
        assert result["passed"] is False
        mse_check = next(c for c in result["checks"] if c["dimension"] == "fp4_mse")
        assert mse_check["passed"] is False
        assert "exceeds max" in mse_check["detail"]

    def test_gate_check_bitrate_exceeds_max(self, tmp_path):
        """gate_check returns passed=False when effective_bitrate exceeds max threshold."""
        self._make_sgfp4_metrics(tmp_path, "code", mse=0.005, bitrate=4.5, t158=0.15)
        bench = Benchmarker(project_root=tmp_path)
        config = self._make_gate_config(bpw_max=4.0)
        result = bench.gate_check("code", config)
        assert result["passed"] is False
        bpw_check = next(c for c in result["checks"] if c["dimension"] == "fp4_effective_bitrate")
        assert bpw_check["passed"] is False

    def test_gate_check_t158_below_min(self, tmp_path):
        """gate_check returns passed=False when t158_ratio is below min threshold."""
        self._make_sgfp4_metrics(tmp_path, "code", mse=0.005, bitrate=3.2, t158=0.02)
        bench = Benchmarker(project_root=tmp_path)
        config = self._make_gate_config(t158_min=0.05)
        result = bench.gate_check("code", config)
        assert result["passed"] is False
        t158_check = next(c for c in result["checks"] if c["dimension"] == "fp4_t158_ratio")
        assert t158_check["passed"] is False
        assert "below min" in t158_check["detail"]

    def test_gate_check_no_metrics_available(self, tmp_path):
        """gate_check returns passed=True when no SGFP4 metrics exist (quantize not yet run)."""
        bench = Benchmarker(project_root=tmp_path)
        config = self._make_gate_config()
        result = bench.gate_check("code", config)
        assert result["passed"] is True
        assert result["blocking"] is False
        assert len(result["checks"]) == 0
        assert "No SGFP4 metrics" in result.get("detail", "")

    def test_gate_check_no_eval_gates_config(self, tmp_path):
        """gate_check returns passed=True when eval_gates config is missing."""
        self._make_sgfp4_metrics(tmp_path, "code")
        bench = Benchmarker(project_root=tmp_path)
        result = bench.gate_check("code", {})
        assert result["passed"] is True
        assert len(result["checks"]) == 0
        assert "No eval_gates configured" in result.get("detail", "")

    def test_gate_check_consecutive_failures_tracked(self, tmp_path):
        """Consecutive failures increment correctly: 1 failure -> counter=1, 2nd -> counter=2."""
        self._make_sgfp4_metrics(tmp_path, "code", mse=0.05, bitrate=3.2, t158=0.15)
        bench = Benchmarker(project_root=tmp_path)
        config = self._make_gate_config(mse_max=0.01)

        # First failure
        result1 = bench.gate_check("code", config)
        assert result1["consecutive_failures"]["fp4_mse"] == 1

        # Second failure (same metrics — still failing)
        result2 = bench.gate_check("code", config)
        assert result2["consecutive_failures"]["fp4_mse"] == 2

    def test_gate_check_blocking_true(self, tmp_path):
        """Blocking flag is True when consecutive_failures >= consecutive_failures_to_block."""
        self._make_sgfp4_metrics(tmp_path, "code", mse=0.05, bitrate=3.2, t158=0.15)
        bench = Benchmarker(project_root=tmp_path)
        config = self._make_gate_config(mse_max=0.01, mse_fail=2)

        # First failure: counter=1, not blocking
        result1 = bench.gate_check("code", config)
        assert result1["blocking"] is False
        assert result1["consecutive_failures"]["fp4_mse"] == 1

        # Second failure: counter=2 >= 2, blocking
        result2 = bench.gate_check("code", config)
        assert result2["blocking"] is True
        assert result2["consecutive_failures"]["fp4_mse"] == 2

    def test_gate_check_blocking_false_below_threshold(self, tmp_path):
        """Blocking flag is False when failures are below the threshold."""
        self._make_sgfp4_metrics(tmp_path, "code", mse=0.05, bitrate=3.2, t158=0.15)
        bench = Benchmarker(project_root=tmp_path)
        config = self._make_gate_config(mse_max=0.01, mse_fail=5)

        # Only 1 failure, threshold is 5 — not blocking
        result = bench.gate_check("code", config)
        assert result["blocking"] is False
        assert result["consecutive_failures"]["fp4_mse"] == 1

    def test_gate_check_passing_resets_counter(self, tmp_path):
        """Passing a dimension resets its consecutive_failures counter to 0."""
        self._make_sgfp4_metrics(tmp_path, "code", mse=0.05, bitrate=3.2, t158=0.15)
        bench = Benchmarker(project_root=tmp_path)
        config = self._make_gate_config(mse_max=0.01)

        # Fail once
        bench.gate_check("code", config)

        # Now write new metrics that pass
        self._make_sgfp4_metrics(tmp_path, "code", mse=0.005, bitrate=3.2, t158=0.15)
        result = bench.gate_check("code", config)
        assert result["consecutive_failures"]["fp4_mse"] == 0

    def test_gate_state_persisted(self, tmp_path):
        """Gate state is persisted to artifacts/.gate_state/{niche}_gate_state.json."""
        self._make_sgfp4_metrics(tmp_path, "code", mse=0.005, bitrate=3.2, t158=0.15)
        bench = Benchmarker(project_root=tmp_path)
        config = self._make_gate_config()
        bench.gate_check("code", config)

        gate_file = tmp_path / "artifacts" / ".gate_state" / "code_gate_state.json"
        assert gate_file.exists()

        with gate_file.open() as f:
            state = json.load(f)
        assert state["niche"] == "code"
        assert "consecutive_failures" in state
        assert "history" in state
        assert len(state["history"]) >= 1

    def test_gate_state_history_truncated(self, tmp_path):
        """Gate state history is truncated to 20 most recent entries."""
        self._make_sgfp4_metrics(tmp_path, "code", mse=0.005, bitrate=3.2, t158=0.15)
        bench = Benchmarker(project_root=tmp_path)
        config = self._make_gate_config()

        # Run gate_check 25 times
        for _ in range(25):
            bench.gate_check("code", config)

        gate_file = tmp_path / "artifacts" / ".gate_state" / "code_gate_state.json"
        with gate_file.open() as f:
            state = json.load(f)

        assert len(state["history"]) <= 20

    def test_gate_check_none_config(self, tmp_path):
        """gate_check with config=None uses self._config."""
        self._make_sgfp4_metrics(tmp_path, "code", mse=0.005, bitrate=3.2, t158=0.15)
        config = self._make_gate_config()
        bench = Benchmarker(project_root=tmp_path, config=config)
        result = bench.gate_check("code")  # no explicit config — use self._config
        assert result["passed"] is True

    def test_corrupt_gate_state_recovered(self, tmp_path):
        """Corrupt gate state files are recovered (fail-open)."""
        self._make_sgfp4_metrics(tmp_path, "code", mse=0.005, bitrate=3.2, t158=0.15)
        bench = Benchmarker(project_root=tmp_path)
        config = self._make_gate_config()

        # Write corrupt gate state file
        gate_dir = tmp_path / "artifacts" / ".gate_state"
        gate_dir.mkdir(parents=True, exist_ok=True)
        (gate_dir / "code_gate_state.json").write_text("not valid json {{{")

        # gate_check should not crash — fail-open behavior
        result = bench.gate_check("code", config)
        assert result["consecutive_failures"]["fp4_mse"] <= 1  # max 1 (first failure)
        # The corrupt file should have been deleted/replaced
        gate_file = gate_dir / "code_gate_state.json"
        assert gate_file.exists()
        with gate_file.open() as f:
            json.load(f)  # should be valid JSON now
