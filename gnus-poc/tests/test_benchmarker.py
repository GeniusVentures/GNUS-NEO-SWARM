"""Tests for Benchmarker."""

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
