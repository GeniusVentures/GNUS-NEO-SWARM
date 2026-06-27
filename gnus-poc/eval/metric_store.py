"""Structured persistence for SGFP4 quantization metrics per specialist/run.

MetricStore reads the stats.json format produced by FP4Exporter.export_to_file
(Plan 03-01) and persists gate-relevant derived metrics (fp4_mse, fp4_effective_bitrate,
fp4_t158_ratio) alongside the raw stats for auditability.

Implements D-09: SGFP4 error metrics become gate dimensions in eval_gates.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)


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
