"""Head-to-head benchmark comparison across training variants."""

import json
from pathlib import Path
from typing import Optional

from eval.evaluator import SpecialistEvaluator


class Benchmarker:
    def __init__(self, project_root: Optional[Path] = None, evaluator: Optional[SpecialistEvaluator] = None):
        if project_root is None:
            project_root = Path(__file__).resolve().parent.parent
        self._project_root = project_root
        self._evaluator = evaluator or SpecialistEvaluator(project_root)
        self._benchmarks_dir = project_root / "artifacts" / "benchmarks"
        self._benchmarks_dir.mkdir(parents=True, exist_ok=True)

    def compare_variants(
        self,
        niche_name: str,
        variant_results: list,
    ) -> dict:
        comparison = {
            "niche": niche_name,
            "variants": variant_results,
            "best": {},
        }

        if not variant_results:
            return comparison

        metrics = ["perplexity", "bleu_score", "rouge_l"]
        for metric in metrics:
            best_variant = min(variant_results, key=lambda v: v.get(metric, float("inf")))
            comparison["best"][metric] = {
                "variant": best_variant.get("variant", "unknown"),
                "value": best_variant.get(metric),
            }

        latency_best = min(variant_results, key=lambda v: v.get("latency_ms_per_token", float("inf")))
        comparison["best"]["latency_ms_per_token"] = {
            "variant": latency_best.get("variant", "unknown"),
            "value": latency_best.get("latency_ms_per_token"),
        }

        return comparison

    def save_comparison(self, niche_name: str, comparison: dict):
        out = self._benchmarks_dir / f"{niche_name}_comparison.json"
        with out.open("w") as f:
            json.dump(comparison, f, indent=2)

    def print_comparison_table(self, comparison: dict):
        variants = comparison.get("variants", [])
        if not variants:
            return

        header = f"{'Variant':<20} {'PPL':>8} {'BLEU':>8} {'ROUGE-L':>8} {'Latency':>10}"
        sep = "-" * len(header)
        print(f"\n{comparison['niche'].upper()} Benchmark Comparison")
        print(sep)
        print(header)
        print(sep)
        for v in variants:
            print(
                f"{v.get('variant', '?')[:19]:<20} "
                f"{v.get('perplexity', 0):>8.2f} "
                f"{v.get('bleu_score', 0):>8.4f} "
                f"{v.get('rouge_l', 0):>8.4f} "
                f"{v.get('latency_ms_per_token', 0):>9.2f}ms"
            )
        print(sep)
        print(f"Best PPL: {comparison['best'].get('perplexity', {}).get('variant', '?')}")
        print(f"Best BLEU: {comparison['best'].get('bleu_score', {}).get('variant', '?')}")
