"""Head-to-head benchmark comparison across training variants."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from eval.evaluator import SpecialistEvaluator
from eval.metric_store import MetricStore

logger = logging.getLogger(__name__)


class Benchmarker:
    def __init__(
        self,
        project_root: Optional[Path] = None,
        evaluator: Optional[SpecialistEvaluator] = None,
        config: Optional[dict] = None,
    ):
        if project_root is None:
            project_root = Path(__file__).resolve().parent.parent
        self._project_root = project_root
        self._evaluator = evaluator or SpecialistEvaluator(project_root)
        self._benchmarks_dir = project_root / "artifacts" / "benchmarks"
        self._benchmarks_dir.mkdir(parents=True, exist_ok=True)
        self._config = config or {}
        self._metric_store = MetricStore(project_root)
        self._gate_state_dir = project_root / "artifacts" / ".gate_state"
        self._gate_state_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Comparison (unchanged from original)
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Gate checking (new — D-09: SGFP4 metrics as eval gate dimensions)
    # ------------------------------------------------------------------

    def gate_check(self, niche_name: str, config: dict = None) -> dict:
        """Evaluate SGFP4 quantization metrics against configurable thresholds.

        Follows the Phase 2 auto-gating pattern: each gate dimension has a
        numeric threshold and a consecutive-failure count that triggers
        a blocking state.

        Args:
            niche_name: Specialist niche to evaluate.
            config: Effective config dict containing the ``eval_gates`` block.
                If None, uses ``self._config`` set during construction.

        Returns:
            Dict with keys: ``niche``, ``passed``, ``checks``, ``blocking``,
            ``consecutive_failures``, and ``detail``.
        """
        effective_config = config if config is not None else self._config

        if not effective_config or "eval_gates" not in effective_config:
            return {
                "niche": niche_name,
                "passed": True,
                "checks": [],
                "blocking": False,
                "consecutive_failures": {},
                "detail": "No eval_gates configured",
            }

        eval_gates = effective_config["eval_gates"]

        # Load SGFP4 metrics for this niche
        metrics = self._metric_store.load_sgfp4_metrics(niche_name)
        if metrics is None:
            return {
                "niche": niche_name,
                "passed": True,
                "checks": [],
                "blocking": False,
                "consecutive_failures": {},
                "detail": "No SGFP4 metrics available yet",
            }

        qm = metrics.get("quantization_metrics", {})

        # Evaluate each SGFP4 gate dimension
        checks = []
        all_passed = True
        now_consecutive_failures = {}

        for dim_name in ("fp4_mse", "fp4_effective_bitrate", "fp4_t158_ratio"):
            if dim_name not in eval_gates:
                continue

            dim_config = eval_gates[dim_name]
            actual_value = qm.get(dim_name, 0.0)

            dim_passed, detail_msg = self._check_dimension(dim_name, actual_value, dim_config)
            checks.append({
                "dimension": dim_name,
                "value": actual_value,
                "threshold": dim_config,
                "passed": dim_passed,
                "detail": detail_msg,
            })

            if not dim_passed:
                all_passed = False
                now_consecutive_failures[dim_name] = 1
            else:
                now_consecutive_failures[dim_name] = 0

        # Load previous gate state, update consecutive_failures counters
        prev_state = self._load_gate_state(niche_name)
        consecutive_failures = self._update_consecutive_failures(
            prev_state, now_consecutive_failures
        )

        # Determine blocking
        blocking = False
        for dim_name, count in consecutive_failures.items():
            dim_config = eval_gates.get(dim_name, {})
            threshold = dim_config.get("consecutive_failures_to_block", 999)
            if count >= threshold:
                blocking = True
                break

        # Persist updated gate state
        self._save_gate_state(niche_name, consecutive_failures, checks)

        return {
            "niche": niche_name,
            "passed": all_passed,
            "checks": checks,
            "blocking": blocking,
            "consecutive_failures": consecutive_failures,
        }

    # ------------------------------------------------------------------
    # Gate helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _check_dimension(dim_name: str, actual_value: float, dim_config: dict):
        """Check a single gate dimension.

        Args:
            dim_name: Dimension name (fp4_mse, fp4_effective_bitrate, fp4_t158_ratio).
            actual_value: Measured value from metrics.
            dim_config: Threshold config dict (max/min + consecutive_failures_to_block).

        Returns:
            Tuple of (passed: bool, detail: str).
        """
        if "min" in dim_config:
            threshold_min = float(dim_config["min"])
            if actual_value < threshold_min:
                return (
                    False,
                    f"{dim_name} {actual_value:.6f} is below min {threshold_min}"
                )
        if "max" in dim_config:
            threshold_max = float(dim_config["max"])
            if actual_value > threshold_max:
                return (
                    False,
                    f"{dim_name} {actual_value:.6f} exceeds max {threshold_max}"
                )

        return (True, f"{dim_name} {actual_value:.6f} within threshold")

    @staticmethod
    def _update_consecutive_failures(
        prev_state: dict,
        now_failures: dict,
    ) -> dict:
        """Update consecutive failure counters.

        For each dimension: increment the counter if it failed this check,
        reset to 0 if it passed.

        Args:
            prev_state: Previous gate state dict (may be empty).
            now_failures: Current check results: {dim_name: 1 if failed, 0 if passed}.

        Returns:
            Updated consecutive_failures dict.
        """
        prev_counters = prev_state.get("consecutive_failures", {})
        result = {}
        for dim_name, failed in now_failures.items():
            prev = prev_counters.get(dim_name, 0)
            if failed:
                result[dim_name] = prev + 1
            else:
                result[dim_name] = 0
        return result

    # ------------------------------------------------------------------
    # Gate state persistence (T-03-11, T-03-13 mitigations)
    # ------------------------------------------------------------------

    def _gate_state_path(self, niche_name: str) -> Path:
        """Return the gate state file path for a niche."""
        return self._gate_state_dir / f"{niche_name}_gate_state.json"

    def _load_gate_state(self, niche_name: str) -> dict:
        """Load the persisted gate state for a niche.

        T-03-11 mitigation: Corrupt state files are caught and recreated fresh.
        Gate defaults to passing when state is unreadable (fail-open for POC).

        Returns:
            Gate state dict, or empty dict if no state exists or state is corrupt.
        """
        path = self._gate_state_path(niche_name)
        if not path.exists():
            return {}

        try:
            with path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning(
                "Gate state file %s is corrupt; recreating fresh (fail-open). Error: %s",
                path, exc,
            )
            try:
                path.unlink()
            except OSError:
                pass
            return {}

    def _save_gate_state(
        self,
        niche_name: str,
        consecutive_failures: dict,
        checks: list,
    ):
        """Persist gate state for a niche.

        Stores consecutive failure counters and a truncated history of recent
        gate check results (max 20 entries).

        T-03-13 mitigation: Gate state stored in artifacts/.gate_state/ which
        is not user-writable during normal pipeline execution.

        Args:
            niche_name: Specialist niche name.
            consecutive_failures: Updated failure counters dict.
            checks: Current gate check results list.
        """
        prev_state = self._load_gate_state(niche_name)
        history = prev_state.get("history", [])
        history.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "consecutive_failures": dict(consecutive_failures),
            "checks": checks,
        })

        # Truncate history to 20 most recent entries
        if len(history) > 20:
            history = history[-20:]

        state = {
            "niche": niche_name,
            "last_check_timestamp": datetime.now(timezone.utc).isoformat(),
            "consecutive_failures": consecutive_failures,
            "history": history,
        }

        path = self._gate_state_path(niche_name)
        with path.open("w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
