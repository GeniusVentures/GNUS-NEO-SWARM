"""Structured persistence for SGFP4 quantization metrics per specialist/run.

MetricStore reads the stats.json format produced by FP4Exporter.export_to_file
(Plan 03-01) and persists gate-relevant derived metrics (fp4_mse, fp4_effective_bitrate,
fp4_t158_ratio) alongside the raw stats for auditability.

Implements D-09: SGFP4 error metrics become gate dimensions in eval_gates.

Plan 04-04 (D-11): MetricStore is the source of truth for benchmark results too.
``record_benchmark_results`` / ``load_benchmark_results`` /
``load_all_benchmark_results`` / ``load_benchmark_run_by_fingerprint`` extend the
Phase 3 SGFP4 API without altering it.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


# Required keys for a benchmark results payload (Plan 04-01 schema, D-02).
_BENCHMARK_REQUIRED_KEYS = (
    "niche",
    "timestamp_utc",
    "mode",
    "fingerprint",
    "results",
)


class MetricStore:
    """Structured persistence for SGFP4 quantization metrics.

    Reads the stats dict produced by FP4Exporter (Plan 03-01), derives gate-relevant
    metrics, and persists them to `artifacts/evaluations/{niche}_sgfp4_metrics.json`.

    This class does not depend on SpecialistEvaluator or Benchmarker — it reads the
    stats.json format by contract (dict shape), not by code import.
    """

    def __init__(self, project_root: Optional[Path] = None):
        """Initialize MetricStore.

        Args:
            project_root: Root of the gnus-poc project. Auto-located if None.
        """
        if project_root is None:
            project_root = Path(__file__).resolve().parent.parent
        self._project_root = project_root
        self._metrics_dir = project_root / "artifacts" / "evaluations"
        self._metrics_dir.mkdir(parents=True, exist_ok=True)
        # Plan 04-04 (D-11): benchmark results live in artifacts/benchmarks/
        self._benchmarks_dir = project_root / "artifacts" / "benchmarks"
        self._benchmarks_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record_sgfp4_metrics(self, niche_name: str, fp4_stats: dict, **kwargs) -> Path:
        """Record SGFP4 quantization metrics for a specialist niche/run.

        Extracts and computes gate-relevant metrics from the fp4_stats dict
        produced by FP4Exporter.export_to_file (Plan 03-01).

        Metrics derived:
        - ``fp4_mse``: Weighted average of per-block mean squared error.
          If ``fp4_stats["per_block_errors"]`` is present and non-empty,
          the mean is used directly. Otherwise a proxy is computed from
          effective bitrate deviation: ``max(0.0, (effective_bpw - 2.5) / 100.0)``.
          **Note:** The proxy is a placeholder until Phase 4 benchmark data
          provides true per-block MSE values. Replace when ``per_block_errors``
          becomes available from the benchmark pipeline.
        - ``fp4_effective_bitrate``: Directly from ``fp4_stats["effective_bpw"]``.
        - ``fp4_t158_ratio``: ``t158_blocks / (fp4_blocks + t158_blocks)``
          if total blocks > 0, else 0.0.

        Args:
            niche_name: Specialist niche name (e.g., "code", "medical").
            fp4_stats: Stats dict from FP4Exporter.export_to_file.
                Expected keys: shape, num_superblocks, layout_distribution,
                fp4_blocks, t158_blocks, effective_bpw, total_bytes.
                Optional: per_block_errors (list of float).
            **kwargs: Additional metadata (reserved for future use).

        Returns:
            Path to the written JSON file.

        Raises:
            ValueError: If required keys are missing or metric values are non-numeric.
        """
        self._validate_stats_dict(fp4_stats, niche_name)

        # Extract gate-relevant metrics
        fp4_mse = self._compute_fp4_mse(fp4_stats)
        fp4_effective_bitrate = float(fp4_stats["effective_bpw"])
        fp4_t158_ratio = self._compute_t158_ratio(fp4_stats)

        metrics_record = {
            "niche": niche_name,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "quantization_metrics": {
                "fp4_mse": fp4_mse,
                "fp4_effective_bitrate": fp4_effective_bitrate,
                "fp4_t158_ratio": fp4_t158_ratio,
            },
            "raw_stats": fp4_stats,
        }

        out_path = self._metrics_dir / f"{niche_name}_sgfp4_metrics.json"
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(metrics_record, f, indent=2)

        logger.info(
            "Recorded SGFP4 metrics for niche=%s: mse=%.6f bitrate=%.2f t158_ratio=%.4f -> %s",
            niche_name, fp4_mse, fp4_effective_bitrate, fp4_t158_ratio, out_path,
        )
        return out_path

    def load_sgfp4_metrics(self, niche_name: str) -> Optional[dict]:
        """Load the most recent SGFP4 metrics file for a given niche.

        Globs ``{metrics_dir}/{niche_name}_sgfp4_metrics.json``.
        Since timestamp filenames sort lexicographically (ISO 8601),
        returns the last matched file.

        Args:
            niche_name: Specialist niche name.

        Returns:
            Parsed metrics dict, or None if no metrics file exists.
        """
        pattern = f"{niche_name}_sgfp4_metrics.json"
        candidates = sorted(self._metrics_dir.glob(pattern))
        if not candidates:
            return None

        target = candidates[-1]
        try:
            with target.open("r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load metrics file %s: %s", target, exc)
            return None

    def list_all_metrics(self) -> Dict[str, dict]:
        """Load all SGFP4 metrics files.

        Globs all ``*_sgfp4_metrics.json`` files and returns a dict
        mapping niche_name to the parsed metrics dict.

        Returns:
            Dict mapping niche_name -> metrics dict. Empty if no files exist.
        """
        result = {}
        for file_path in sorted(self._metrics_dir.glob("*_sgfp4_metrics.json")):
            # Extract niche name: "code_sgfp4_metrics.json" -> "code"
            niche_name = file_path.stem.replace("_sgfp4_metrics", "")
            try:
                with file_path.open("r", encoding="utf-8") as f:
                    result[niche_name] = json.load(f)
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Skipping unreadable metrics file %s: %s", file_path, exc)
        return result

    # ==================================================================
    # Plan 04-04: Benchmark result persistence (D-11 source of truth)
    #
    # These methods are ADDITIVE to the Phase 3 SGFP4 API above. The Phase 3
    # methods (record_sgfp4_metrics, load_sgfp4_metrics, list_all_metrics) are
    # unchanged and write to a separate directory (artifacts/evaluations/).
    # ==================================================================

    def record_benchmark_results(
        self,
        niche_name: str,
        benchmark_name: str,
        results: dict,
    ) -> Path:
        """Persist a benchmark results payload as the source of truth (D-11).

        Writes ``results`` to
        ``artifacts/benchmarks/{niche}_{benchmark}_{YYYYMMDD-HHMMSS}.json``.
        Validates the required payload keys before writing and flags an invalid
        fingerprint non-destructively (T-04-16: bad input is recorded with a
        ``fingerprint_valid: False`` flag rather than silently dropping data).

        Args:
            niche_name: Specialist niche (e.g. ``"medical"``).
            benchmark_name: Benchmark identifier (e.g. ``"mmlu"``).
            results: Results payload per the Plan 04-01 schema. Must contain
                ``niche``, ``timestamp_utc``, ``mode``, ``fingerprint``, ``results``.

        Returns:
            Path to the written JSON file.

        Raises:
            ValueError: If a required key is missing.
        """
        for key in _BENCHMARK_REQUIRED_KEYS:
            if key not in results:
                raise ValueError(
                    f"Missing required key '{key}' in benchmark results for "
                    f"niche '{niche_name}' / benchmark '{benchmark_name}'"
                )

        # Compute fingerprint validity (T-04-16: flag but still store).
        # Local import keeps benchmark_fingerprint optional at module load time.
        fingerprint_valid = True
        try:
            from eval.benchmark_fingerprint import validate_fingerprint

            fingerprint_valid, _missing = validate_fingerprint(results["fingerprint"])
        except Exception:  # noqa: BLE001 - any validation failure is non-fatal
            fingerprint_valid = False

        # Build the persisted record. We do not mutate the caller's dict.
        record = dict(results)
        record["fingerprint_valid"] = bool(fingerprint_valid)
        # Store the computed fingerprint hash so regression comparisons can
        # locate the exact previous run (load_benchmark_run_by_fingerprint).
        try:
            from eval.benchmark_fingerprint import fingerprint_hash

            record["fingerprint_hash"] = fingerprint_hash(results["fingerprint"])
        except Exception:  # noqa: BLE001 - best-effort; absent hash is tolerated
            record["fingerprint_hash"] = None

        # Use microsecond precision in the filename timestamp so successive
        # writes within the same second still produce distinct, lexicographically
        # ordered filenames (later writes sort after earlier ones). This keeps
        # ``load_benchmark_results`` glob-sort contract intact without any
        # collision-mitigation suffix that would break ordering.
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
        out_path = (
            self._benchmarks_dir
            / f"{niche_name}_{benchmark_name}_{timestamp}.json"
        )
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(record, f, indent=2)

        logger.info(
            "Recorded benchmark results niche=%s benchmark=%s fingerprint_valid=%s -> %s",
            niche_name, benchmark_name, fingerprint_valid, out_path,
        )
        return out_path

    def load_benchmark_results(
        self,
        niche_name: str,
        benchmark_name: Optional[str] = None,
    ) -> Optional[dict]:
        """Load the most recent benchmark result for a niche (+ optional benchmark).

        Per D-11 the artifacts/benchmarks/ directory is the source of truth.
        Files are named ``{niche}_{benchmark}_{timestamp}.json`` and timestamps
        sort lexicographically (``YYYYMMDD-HHMMSS``), so the lexicographic max
        is the most recent run.

        Args:
            niche_name: Specialist niche.
            benchmark_name: Optional benchmark filter. If ``None``, the most
                recent result for ANY benchmark for that niche is returned.

        Returns:
            Parsed results dict, or ``None`` if no results exist.
        """
        if benchmark_name is not None:
            pattern = f"{niche_name}_{benchmark_name}_*.json"
        else:
            pattern = f"{niche_name}_*_*.json"
        candidates = sorted(self._benchmarks_dir.glob(pattern))
        if not candidates:
            return None

        target = candidates[-1]
        try:
            with target.open("r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load benchmark results %s: %s", target, exc)
            return None

    def load_all_benchmark_results(self, niche_name: str) -> List[dict]:
        """Load ALL benchmark results for a niche, sorted by timestamp ascending.

        Args:
            niche_name: Specialist niche.

        Returns:
            List of parsed results dicts. Empty if no results exist.
        """
        pattern = f"{niche_name}_*_*.json"
        candidates = sorted(self._benchmarks_dir.glob(pattern))
        out: List[dict] = []
        for path in candidates:
            try:
                with path.open("r", encoding="utf-8") as f:
                    out.append(json.load(f))
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Skipping unreadable benchmark file %s: %s", path, exc)
        # ``candidates`` is sorted by filename; filename embeds the timestamp.
        # Stable order is already ascending; keep explicit sort for clarity.
        out.sort(key=lambda r: r.get("timestamp_utc", ""))
        return out

    def load_benchmark_run_by_fingerprint(
        self,
        niche_name: str,
        benchmark_name: str,
        fingerprint_hash_value: str,
    ) -> Optional[dict]:
        """Locate a specific run by its fingerprint hash (Plan 04-03 linkage).

        WR-09: reject ``None`` / empty ``fingerprint_hash_value`` up front and
        skip records whose own ``fingerprint_hash`` is ``None``. The earlier
        implementation compared ``payload.get("fingerprint_hash") ==
        fingerprint_hash_value``, so a caller passing ``None`` would match
        EVERY record whose hash failed to compute (set to ``None`` at write
        time), returning an arbitrary first record. ``None`` query now returns
        ``None`` (no match) and ``None`` records are skipped rather than
        spuriously matching.

        Args:
            niche_name: Specialist niche.
            benchmark_name: Benchmark identifier.
            fingerprint_hash_value: SHA256 hex digest from
                ``benchmark_fingerprint.fingerprint_hash``.

        Returns:
            Parsed results dict whose ``fingerprint_hash`` matches, or ``None``.
        """
        if not fingerprint_hash_value:
            return None
        pattern = f"{niche_name}_{benchmark_name}_*.json"
        for path in sorted(self._benchmarks_dir.glob(pattern)):
            try:
                with path.open("r", encoding="utf-8") as f:
                    payload = json.load(f)
            except (json.JSONDecodeError, OSError):
                continue
            record_hash = payload.get("fingerprint_hash")
            if record_hash is None:
                # Skip records whose hash failed to compute at write time
                # rather than letting them spuriously match a None query.
                continue
            if record_hash == fingerprint_hash_value:
                return payload
        return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_stats_dict(fp4_stats: dict, niche_name: str) -> None:
        """Validate required keys and types in the fp4_stats dict.

        T-03-10 mitigation: Validate fp4_stats dict keys before access;
        handle missing keys with clear error messages; reject non-numeric values.

        Args:
            fp4_stats: Stats dict from FP4Exporter.
            niche_name: Specialist niche name (for error messages).

        Raises:
            ValueError: If required keys are missing or have wrong types.
        """
        required_keys = [
            "shape", "num_superblocks", "layout_distribution",
            "fp4_blocks", "t158_blocks", "effective_bpw", "total_bytes",
        ]
        for key in required_keys:
            if key not in fp4_stats:
                raise ValueError(
                    f"Missing required key '{key}' in fp4_stats for niche '{niche_name}'"
                )

        # Validate numeric fields
        for key in ("fp4_blocks", "t158_blocks", "effective_bpw", "total_bytes"):
            value = fp4_stats[key]
            if not isinstance(value, (int, float)):
                raise ValueError(
                    f"Non-numeric value for '{key}' in fp4_stats for niche '{niche_name}': {value!r}"
                )

        # Validate layout_distribution is a dict
        if not isinstance(fp4_stats["layout_distribution"], dict):
            raise ValueError(
                f"Expected dict for 'layout_distribution' in fp4_stats for niche '{niche_name}'"
            )

    @staticmethod
    def _compute_fp4_mse(fp4_stats: dict) -> float:
        """Compute fp4_mse from available stats data.

        If per_block_errors is present and non-empty, returns the mean.
        Otherwise computes a proxy from effective bitrate deviation:
        ``max(0.0, (effective_bpw - 2.5) / 100.0)``.

        The proxy is a placeholder — replace when Phase 4 benchmark data
        provides true per-block MSE values.
        """
        per_block_errors = fp4_stats.get("per_block_errors")
        if per_block_errors:
            return float(sum(per_block_errors) / len(per_block_errors))

        # Proxy: effective bitrate deviation from 2.5 (baseline packed FP4 minimum)
        effective_bpw = float(fp4_stats["effective_bpw"])
        return max(0.0, (effective_bpw - 2.5) / 100.0)

    @staticmethod
    def _compute_t158_ratio(fp4_stats: dict) -> float:
        """Compute T158 ratio: t158_blocks / (fp4_blocks + t158_blocks).

        Returns 0.0 if total blocks is zero.
        """
        fp4_blocks = int(fp4_stats["fp4_blocks"])
        t158_blocks = int(fp4_stats["t158_blocks"])
        total = fp4_blocks + t158_blocks
        if total == 0:
            return 0.0
        return float(t158_blocks) / float(total)
