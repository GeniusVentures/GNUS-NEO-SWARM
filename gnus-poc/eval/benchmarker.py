"""Head-to-head benchmark comparison across training variants."""

import glob
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from eval.evaluator import SpecialistEvaluator
from eval.metric_store import MetricStore

logger = logging.getLogger(__name__)


class MissingBaselineError(Exception):
    """Raised when an internal baseline (D-07) is required but not present.

    Distinct from the optional SGFP4 unquantized baseline: the internal
    backbone baseline is a hard dependency for deviation computation.
    """


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

    # ==================================================================
    # Plan 04-03: Benchmark quality gates (D-06/D-07/D-08/D-09)
    #
    # These methods are ADDITIVE to the Phase 3 SGFP4 gate_check() above.
    # The existing gate_check() behavior is unchanged; benchmark gating
    # lives in gate_check_benchmarks() and uses a SEPARATE gate-state file
    # (artifacts/.gate_state/{niche}_bench_gate_state.json) so Phase 3
    # SGFP4 counters are never disturbed.
    # ==================================================================

    def _load_yaml(self, path: Path) -> dict:
        """Load a YAML file; returns {} if missing. Import yaml lazily.

        Args:
            path: YAML file path.

        Returns:
            Parsed dict, or empty dict if the file does not exist.
        """
        if not path.exists():
            return {}
        import yaml  # local import keeps module importable without pyyaml

        with path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def _load_specialist_mapping(self, niche_name: str) -> dict:
        """Load blocking/diagnostic benchmark lists for a specialist (D-05).

        Args:
            niche_name: Specialist niche key.

        Returns:
            Dict with ``blocking_benchmarks`` and ``diagnostic_benchmarks`` lists.
            Returns empty lists if the mapping file or specialist is absent.
        """
        mapping_path = (
            self._project_root / "config" / "benchmarks" / "specialist_mapping.yaml"
        )
        mapping = self._load_yaml(mapping_path)
        specialist = (mapping.get("specialists") or {}).get(niche_name, {})
        return {
            "blocking_benchmarks": list(specialist.get("blocking_benchmarks") or []),
            "diagnostic_benchmarks": list(specialist.get("diagnostic_benchmarks") or []),
        }

    def _load_benchmark_threshold(self, benchmark_name: str) -> dict:
        """Load per-benchmark threshold config (D-08 hard_floor, regression, deviation).

        Args:
            benchmark_name: Benchmark identifier.

        Returns:
            Dict with ``hard_floor``, ``regression_max_pct``, ``deviation_max_pct``.
            Defaults: hard_floor=0.0, regression_max_pct=0.10, deviation_max_pct=0.20.
        """
        cfg_path = (
            self._project_root / "config" / "benchmarks" / f"{benchmark_name}.yaml"
        )
        cfg = self._load_yaml(cfg_path)
        return {
            "hard_floor": float(cfg.get("hard_floor", 0.0)),
            "regression_max_pct": float(cfg.get("regression_max_pct", 0.10)),
            "deviation_max_pct": float(cfg.get("deviation_max_pct", 0.20)),
        }

    def _bench_gate_state_path(self, niche_name: str) -> Path:
        """Return the BENCHMARK gate state file path (separate from SGFP4 state)."""
        return self._gate_state_dir / f"{niche_name}_bench_gate_state.json"

    def _load_bench_gate_state(self, niche_name: str) -> dict:
        """Load benchmark gate state. Fail-open on corrupt files (Phase 3 pattern)."""
        path = self._bench_gate_state_path(niche_name)
        if not path.exists():
            return {}
        try:
            with path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning(
                "Bench gate state %s corrupt; recreating (fail-open). Error: %s",
                path, exc,
            )
            try:
                path.unlink()
            except OSError:
                pass
            return {}

    def _save_bench_gate_state(
        self, niche_name: str, consecutive_failures: dict, checks: list
    ):
        """Persist benchmark gate state with history (T-04-12 audit trail)."""
        prev_state = self._load_bench_gate_state(niche_name)
        history = prev_state.get("history", [])
        history.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "consecutive_failures": dict(consecutive_failures),
            "checks": checks,
        })
        if len(history) > 20:
            history = history[-20:]
        state = {
            "niche": niche_name,
            "last_check_timestamp": datetime.now(timezone.utc).isoformat(),
            "consecutive_failures": consecutive_failures,
            "history": history,
        }
        path = self._bench_gate_state_path(niche_name)
        with path.open("w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)

    def _find_canonical_results(self, niche_name: str, quantized_only: bool = False):
        """Find the most recent canonical-mode benchmark results JSON for a niche.

        Per D-03: diagnostic-mode results are NEVER used for gating.

        Args:
            niche_name: Specialist niche.
            quantized_only: If True, restrict to quantized model results only.

        Returns:
            Parsed results dict, or None if no canonical result found.
        """
        pattern = f"{niche_name}_canonical_*.json"
        candidates = sorted(
            self._benchmarks_dir.glob(pattern),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for path in candidates:
            try:
                with path.open("r", encoding="utf-8") as f:
                    payload = json.load(f)
            except (json.JSONDecodeError, OSError):
                continue
            # D-03: skip diagnostic-mode results defensively
            if payload.get("mode") != "canonical":
                continue
            if quantized_only and "unquantized" in path.name:
                continue
            return payload
        return None

    def _load_baseline_scores(self, niche_name: str) -> dict:
        """Load internal untrained-backbone baseline scores (D-07).

        The baseline is the untrained backbone model run through the same
        benchmarks -- the floor against which deviation is measured.

        Args:
            niche_name: Specialist niche.

        Returns:
            Dict of {benchmark_name: score}.

        Raises:
            MissingBaselineError: If no baseline file exists for the niche.
        """
        path = self._benchmarks_dir / f"{niche_name}_baseline.json"
        if not path.exists():
            raise MissingBaselineError(
                f"no internal baseline for niche '{niche_name}' at {path}"
            )
        with path.open("r", encoding="utf-8") as f:
            payload = json.load(f)
        # Normalize: {benchmark: {"score": x}} -> {benchmark: x}
        results = payload.get("results", {})
        return {
            name: (val.get("score") if isinstance(val, dict) else val)
            for name, val in results.items()
        }

    def _extract_score(self, result_entry) -> float:
        """Extract a scalar score from a benchmark result entry.

        Handles both ``{"score": x}`` and ``{"pass@1": x}`` schemas.

        Args:
            result_entry: Dict from benchmark results.

        Returns:
            Scalar score, or 0.0 if no score key is found.
        """
        if not isinstance(result_entry, dict):
            return float(result_entry) if result_entry is not None else 0.0
        for key in ("score", "pass@1", "acc"):
            if key in result_entry:
                return float(result_entry[key])
        return 0.0

    def composite_2_of_3(
        self, scores_pass: bool, regression_pass: bool, deviation_pass: bool
    ) -> dict:
        """D-08 composite gate: passes when at least 2 of 3 dimensions pass.

        Args:
            scores_pass: True iff ALL blocking benchmark scores >= hard_floor.
            regression_pass: True iff regression from previous run <= threshold.
            deviation_pass: True iff deviation from baseline <= threshold.

        Returns:
            Dict with ``passed`` (bool), ``passed_count`` (int 0-3),
            and ``dimensions`` mapping each dimension name to {passed, detail}.
        """
        dims = {
            "scores": {"passed": bool(scores_pass), "detail": "hard floors" + ("" if scores_pass else " not") + " met"},
            "regression": {"passed": bool(regression_pass), "detail": "regression within threshold" if regression_pass else "regression exceeds threshold"},
            "deviation": {"passed": bool(deviation_pass), "detail": "deviation within threshold" if deviation_pass else "deviation exceeds threshold"},
        }
        passed_count = sum(1 for d in dims.values() if d["passed"])
        return {
            "passed": passed_count >= 2,
            "passed_count": passed_count,
            "dimensions": dims,
        }

    def _sgfp4_regression_check(
        self, niche_name: str, current_scores: dict
    ) -> dict:
        """D-08 mandatory SGFP4 regression check.

        Compares unquantized adapter benchmark scores against SGFP4 quantized
        model scores. Isolates "model got worse because of training" from
        "model got worse because SGFP4 damaged it."

        Per D-09: a full bootstrap CI is the target; here we use a simple
        per-benchmark percentage threshold as a placeholder and flag
        ``needs_bootstrap: true`` for Plan 04-04 to upgrade.

        Args:
            niche_name: Specialist niche.
            current_scores: Current (quantized) results dict {benchmark: entry}.

        Returns:
            Dict with ``passed`` (bool), ``deltas`` ({benchmark: delta}),
            ``needs_bootstrap`` (bool), and ``detail`` (str).

        Note:
            Does NOT block on first run when no unquantized baseline exists.
        """
        # Load unquantized adapter result (Plan 04-01 schema: *_unquantized*.json)
        pattern = f"{niche_name}_canonical_*unquantized*.json"
        candidates = sorted(
            self._benchmarks_dir.glob(pattern),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        unquantized = None
        for path in candidates:
            try:
                with path.open("r", encoding="utf-8") as f:
                    candidate = json.load(f)
            except (json.JSONDecodeError, OSError):
                continue
            if candidate.get("mode") == "canonical":
                unquantized = candidate
                break

        if unquantized is None:
            return {
                "passed": True,
                "deltas": {},
                "needs_bootstrap": True,
                "detail": "No unquantized baseline -- SGFP4 regression check skipped (first run?)",
            }

        unquant_results = unquantized.get("results", {})
        deltas = {}
        max_pct = float(
            self._config.get("eval_gates", {})
            .get("sfgp4_regression", {})
            .get("max_regression_pct", 0.10)
        )
        all_within = True
        for benchmark, current_entry in current_scores.items():
            if benchmark not in unquant_results:
                continue
            ref_score = self._extract_score(unquant_results[benchmark])
            cur_score = self._extract_score(current_entry)
            if ref_score <= 0:
                continue
            delta = (ref_score - cur_score) / ref_score  # positive = regression
            deltas[benchmark] = delta
            if delta > max_pct:
                all_within = False

        return {
            "passed": all_within,
            "deltas": deltas,
            "needs_bootstrap": True,
            "detail": "SGFP4 regression within threshold" if all_within else "SGFP4 regression exceeds threshold",
        }

    def gate_check_benchmarks(
        self,
        niche_name: str,
        benchmark_results_path: Optional[Path] = None,
        config: Optional[dict] = None,
    ) -> dict:
        """Evaluate canonical benchmark results against quality gates.

        Implements D-06 (tiered gating), D-07 (internal baseline deviation),
        D-08 (hard floors + 2-of-3 composite + mandatory SGFP4 regression),
        D-09 (bootstrap placeholder).

        Args:
            niche_name: Specialist niche.
            benchmark_results_path: Optional explicit path to results JSON.
                If None, the most recent canonical result is loaded.
            config: Optional effective config dict. If None, uses self._config.

        Returns:
            Dict with keys: ``niche``, ``passed``, ``checks`` (per-benchmark),
            ``blocking``, ``consecutive_failures``, ``composite_result``,
            ``sgfp4_regression``, and ``detail``.
        """
        effective_config = config if config is not None else self._config

        # Load specialist blocking/diagnostic lists
        mapping = self._load_specialist_mapping(niche_name)
        blocking_benchmarks = mapping["blocking_benchmarks"]

        # Load canonical results (D-03: diagnostic-only is skipped)
        if benchmark_results_path is not None:
            with Path(benchmark_results_path).open("r", encoding="utf-8") as f:
                results_payload = json.load(f)
        else:
            results_payload = self._find_canonical_results(niche_name, quantized_only=True)

        if results_payload is None:
            return {
                "niche": niche_name,
                "passed": True,
                "checks": [],
                "blocking": False,
                "consecutive_failures": {},
                "composite_result": None,
                "sgfp4_regression": None,
                "detail": "No canonical benchmark results available yet",
            }

        if results_payload.get("mode") != "canonical":
            return {
                "niche": niche_name,
                "passed": True,
                "checks": [],
                "blocking": False,
                "consecutive_failures": {},
                "composite_result": None,
                "sgfp4_regression": None,
                "detail": "No canonical-mode results; diagnostic-only skipped (D-03)",
            }

        current_results = results_payload.get("results", {})

        # ---- Hard floor check (D-08) ----
        checks = []
        hard_floor_all_pass = True
        now_failures = {}
        for benchmark in blocking_benchmarks:
            thresholds = self._load_benchmark_threshold(benchmark)
            entry = current_results.get(benchmark, {})
            score = self._extract_score(entry)
            passed = score >= thresholds["hard_floor"]
            checks.append({
                "benchmark": benchmark,
                "category": "hard_floor",
                "score": score,
                "threshold": thresholds["hard_floor"],
                "passed": passed,
                "detail": (
                    f"{benchmark} score {score:.4f} >= hard_floor {thresholds['hard_floor']:.4f}"
                    if passed else
                    f"{benchmark} score {score:.4f} BELOW hard_floor {thresholds['hard_floor']:.4f}"
                ),
            })
            now_failures[benchmark] = 0 if passed else 1
            if not passed:
                hard_floor_all_pass = False

        # ---- Regression vs previous run (D-08 dim 2) ----
        # Load previous canonical result (second-most-recent)
        previous_payload = self._find_previous_canonical(niche_name)
        regression_pass = True
        if previous_payload is not None:
            prev_results = previous_payload.get("results", {})
            for benchmark in blocking_benchmarks:
                if benchmark not in prev_results:
                    continue
                thresholds = self._load_benchmark_threshold(benchmark)
                prev_score = self._extract_score(prev_results[benchmark])
                cur_score = self._extract_score(current_results.get(benchmark, {}))
                if prev_score <= 0:
                    continue
                regression = (prev_score - cur_score) / prev_score
                if regression > thresholds["regression_max_pct"]:
                    regression_pass = False
                    break

        # ---- Deviation from internal baseline (D-07, D-08 dim 3) ----
        deviation_pass = True
        try:
            baseline_scores = self._load_baseline_scores(niche_name)
            for benchmark in blocking_benchmarks:
                if benchmark not in baseline_scores:
                    continue
                thresholds = self._load_benchmark_threshold(benchmark)
                baseline = baseline_scores[benchmark]
                cur_score = self._extract_score(current_results.get(benchmark, {}))
                if baseline <= 0:
                    continue
                deviation = (baseline - cur_score) / baseline
                if deviation > thresholds["deviation_max_pct"]:
                    deviation_pass = False
                    break
        except MissingBaselineError:
            # No baseline -> deviation dimension skipped (treat as pass for POC)
            deviation_pass = True

        # ---- Composite 2-of-3 gate (D-08) ----
        composite = self.composite_2_of_3(
            scores_pass=hard_floor_all_pass,
            regression_pass=regression_pass,
            deviation_pass=deviation_pass,
        )

        # ---- Mandatory SGFP4 regression check (D-08) ----
        sgfp4_regression = self._sgfp4_regression_check(niche_name, current_results)

        # ---- Hard floor precondition (D-08): overrides composite ----
        # If any blocking benchmark fails its hard floor, overall passed=False
        # regardless of the composite score.
        overall_passed = hard_floor_all_pass and composite["passed"]

        # ---- Consecutive failure tracking (D-06) ----
        # 1st failure = warning (passed may already be False), 3rd consecutive = blocking.
        bench_threshold = (
            effective_config.get("eval_gates", {})
            .get("benchmark_composite", {})
            .get("consecutive_failures_to_block", 3)
            if effective_config else 3
        )
        prev_state = self._load_bench_gate_state(niche_name)
        prev_counters = prev_state.get("consecutive_failures", {})
        consecutive_failures = {}
        for benchmark, failed in now_failures.items():
            prev = prev_counters.get(benchmark, 0)
            consecutive_failures[benchmark] = prev + 1 if failed else 0

        blocking = any(count >= bench_threshold for count in consecutive_failures.values())

        # Persist benchmark gate state
        self._save_bench_gate_state(niche_name, consecutive_failures, checks)

        return {
            "niche": niche_name,
            "passed": overall_passed,
            "checks": checks,
            "blocking": blocking,
            "consecutive_failures": consecutive_failures,
            "composite_result": composite,
            "sgfp4_regression": sgfp4_regression,
            "detail": "Benchmark gate evaluated",
        }

    def _find_previous_canonical(self, niche_name: str):
        """Find the SECOND-most-recent canonical quantized result (for regression).

        Returns None if fewer than two canonical results exist.
        """
        pattern = f"{niche_name}_canonical_*.json"
        candidates = [
            p for p in sorted(
                self._benchmarks_dir.glob(pattern),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if "unquantized" not in p.name
        ]
        canonical = []
        for path in candidates:
            try:
                with path.open("r", encoding="utf-8") as f:
                    payload = json.load(f)
            except (json.JSONDecodeError, OSError):
                continue
            if payload.get("mode") == "canonical":
                canonical.append(payload)
        return canonical[1] if len(canonical) >= 2 else None
