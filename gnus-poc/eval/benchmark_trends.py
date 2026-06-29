"""Derived trend views over MetricStore benchmark records (Plan 04-04 Task 1).

Per D-11: MetricStore (``artifacts/benchmarks/``) is the source of truth. The
``artifacts/trends/{niche}_trend.json`` files produced here are DERIVED views --
they can be regenerated from MetricStore at any time and carry no independent
state.

Per D-09: trend significance is determined by bootstrap 95% confidence intervals
on per-benchmark score differences. A regression is significant when the CI
excludes zero AND the point estimate (mean delta) is negative.
"""

import json
import logging
import random
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# T-04-18 mitigations: cap bootstrap input/output sizes to bound runtime.
_K_MAX_N_BOOTSTRAP = 100_000
_K_MAX_INPUT_SAMPLES = 10_000
_K_DEFAULT_N_BOOTSTRAP = 10_000
_K_DEFAULT_CONFIDENCE = 0.95


def _trends_dir(project_root: Optional[Path]) -> Path:
    """Return (creating if needed) the artifacts/trends/ directory."""
    root = Path(project_root) if project_root is not None else Path.cwd()
    trends = root / "artifacts" / "trends"
    trends.mkdir(parents=True, exist_ok=True)
    return trends


def _trend_path(niche_name: str, project_root: Optional[Path] = None) -> Path:
    """Return the trend JSON path for a niche."""
    return _trends_dir(project_root) / f"{niche_name}_trend.json"


def append_to_trend_file(
    niche_name: str,
    results: dict,
    project_root: Optional[Path] = None,
) -> Path:
    """Append a run record to ``artifacts/trends/{niche}_trend.json`` (D-11).

    Schema (per RESEARCH.md Pattern 5)::

        {
          "niche": "<niche_name>",
          "runs": [
            {
              "timestamp": "<ISO8601 utc>",
              "model_version": "<str>",
              "quantization_config": {...},
              "results": {"<benchmark>": {"score": float, "per_category": {...}}}
            },
            ...
          ]
        }

    The file is created if it does not exist. If it exists but is corrupt
    (T-04-20 mitigation), the corrupt file is replaced with a fresh run list
    rather than raising -- the MetricStore remains the recoverable source.

    Args:
        niche_name: Specialist niche.
        results: Benchmark results payload (Plan 04-01 schema).
        project_root: Project root. Defaults to cwd.

    Returns:
        Path to the trend file.
    """
    path = _trend_path(niche_name, project_root)

    run_record = {
        "timestamp": results.get("timestamp_utc"),
        "model_version": results.get("model_version"),
        "quantization_config": results.get("quantization_config", {}),
        "results": results.get("results", {}),
    }
    # Include fingerprint hash if present so trend rows can be correlated
    # back to the MetricStore source-of-truth record.
    if "fingerprint_hash" in results:
        run_record["fingerprint_hash"] = results["fingerprint_hash"]

    trend = load_trend_file(niche_name, project_root)
    trend.setdefault("runs", []).append(run_record)

    with path.open("w", encoding="utf-8") as f:
        json.dump(trend, f, indent=2)

    logger.info(
        "Appended run to trend file niche=%s total_runs=%d -> %s",
        niche_name, len(trend["runs"]), path,
    )
    return path


def load_trend_file(
    niche_name: str, project_root: Optional[Path] = None
) -> dict:
    """Load the full trend JSON for a niche.

    T-04-20 mitigation: corrupt trend files fail open -- the caller gets a fresh
    empty runs list and a warning is logged. MetricStore remains authoritative.

    Args:
        niche_name: Specialist niche.
        project_root: Project root.

    Returns:
        Dict with ``niche`` and ``runs`` keys. ``runs`` is ``[]`` if the file
        does not exist or is unreadable.
    """
    path = _trend_path(niche_name, project_root)
    if not path.exists():
        return {"niche": niche_name, "runs": []}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning(
            "Trend file %s is corrupt; returning empty runs (fail-open per T-04-20). "
            "Error: %s",
            path, exc,
        )
        return {"niche": niche_name, "runs": []}

    data.setdefault("niche", niche_name)
    data.setdefault("runs", [])
    return data


def compute_trend_deltas(
    niche_name: str, project_root: Optional[Path] = None
) -> dict:
    """Compare the two most recent runs in the trend file.

    For each benchmark present in BOTH runs, compute ``{metric: curr - prev}``
    for every metric key in the benchmark's result entry (typically ``score``
    plus any per-category aggregates).

    Args:
        niche_name: Specialist niche.
        project_root: Project root.

    Returns:
        Dict with ``status`` (``"ok"`` or ``"insufficient_data"``), ``deltas``
        ({benchmark: {metric: delta}}), and ``previous_timestamp`` /
        ``current_timestamp`` for traceability.
    """
    trend = load_trend_file(niche_name, project_root)
    runs = trend.get("runs", [])
    if len(runs) < 2:
        return {
            "status": "insufficient_data",
            "deltas": {},
            "previous_timestamp": runs[-1].get("timestamp") if runs else None,
            "current_timestamp": runs[-1].get("timestamp") if runs else None,
        }

    prev = runs[-2]
    curr = runs[-1]
    prev_results = prev.get("results", {})
    curr_results = curr.get("results", {})

    deltas = {}
    for benchmark, curr_entry in curr_results.items():
        if benchmark not in prev_results:
            continue  # new benchmark -- no delta
        prev_entry = prev_results[benchmark]
        if not isinstance(curr_entry, dict) or not isinstance(prev_entry, dict):
            continue
        bench_deltas = {}
        for metric, curr_val in curr_entry.items():
            if metric == "per_category":
                continue
            if metric not in prev_entry:
                continue
            try:
                bench_deltas[metric] = float(curr_val) - float(prev_entry[metric])
            except (TypeError, ValueError):
                continue
        if bench_deltas:
            deltas[benchmark] = bench_deltas

    return {
        "status": "ok",
        "deltas": deltas,
        "previous_timestamp": prev.get("timestamp"),
        "current_timestamp": curr.get("timestamp"),
    }


def bootstrap_ci(
    sample_differences,
    n_bootstrap: int = _K_DEFAULT_N_BOOTSTRAP,
    confidence: float = _K_DEFAULT_CONFIDENCE,
    seed: Optional[int] = None,
) -> tuple:
    """Bootstrap 95% confidence interval for paired score differences (D-09).

    Standard percentile bootstrap: resample ``sample_differences`` with
    replacement ``n_bootstrap`` times, compute the mean of each replicate, and
    take the ``(alpha/2)`` and ``(1 - alpha/2)`` percentiles of the replicate
    means as the CI bounds.

    Determinism (T-04-18 + reproducibility): pass an integer ``seed``. The RNG
    is a fresh ``random.Random(seed)`` instance -- it does NOT touch the global
    ``random`` state, so test reproducibility is preserved.

    Args:
        sample_differences: Per-item (or per-category) paired score differences.
            Positive = improvement, negative = regression.
        n_bootstrap: Number of bootstrap replicates. Capped at 100,000.
        confidence: Confidence level (0..1). Default 0.95.
        seed: Optional integer seed for deterministic output.

    Returns:
        Tuple ``(lower, upper)`` of floats. Returns ``(0.0, 0.0)`` for empty
        input.
    """
    # T-04-18 mitigation: cap sizes.
    n_bootstrap = max(1, min(int(n_bootstrap), _K_MAX_N_BOOTSTRAP))

    samples = list(sample_differences)
    if len(samples) == 0:
        return (0.0, 0.0)
    if len(samples) > _K_MAX_INPUT_SAMPLES:
        # Truncate deterministically to the cap (T-04-18).
        samples = samples[:_K_MAX_INPUT_SAMPLES]

    # Coerce to floats; drop non-numeric entries.
    numeric = []
    for value in samples:
        try:
            numeric.append(float(value))
        except (TypeError, ValueError):
            continue
    if not numeric:
        return (0.0, 0.0)

    rng = random.Random(seed)
    n = len(numeric)
    means = []
    for _ in range(n_bootstrap):
        # Resample with replacement.
        total = 0.0
        for _i in range(n):
            total += numeric[rng.randrange(n)]
        means.append(total / n)

    means.sort()
    alpha = 1.0 - float(confidence)
    # Percentile via nearest-rank interpolation matching numpy's default 'linear'.
    def _percentile(sorted_vals: list, q: float) -> float:
        if len(sorted_vals) == 1:
            return float(sorted_vals[0])
        rank = q * (len(sorted_vals) - 1)
        lo = int(rank)
        hi = min(lo + 1, len(sorted_vals) - 1)
        frac = rank - lo
        return float(sorted_vals[lo] * (1.0 - frac) + sorted_vals[hi] * frac)

    lower = _percentile(means, alpha / 2.0)
    upper = _percentile(means, 1.0 - alpha / 2.0)
    return (lower, upper)


def is_degradation_significant(
    current_scores: dict,
    previous_scores: dict,
    confidence: float = _K_DEFAULT_CONFIDENCE,
    n_bootstrap: int = _K_DEFAULT_N_BOOTSTRAP,
    seed: Optional[int] = None,
) -> dict:
    """Per-benchmark degradation significance via bootstrap CI (D-09).

    For each benchmark present in BOTH score dicts, collect per-category score
    differences (``curr - prev``) as bootstrap samples, compute the 95% CI, and
    flag degradation when the CI excludes zero AND the mean delta is negative.

    NOTE: per Plan 04-04 Task 1, the bootstrap currently uses per-category
    scores as pseudo-samples (``n = number of categories``). When per-item
    scores become available from the harness, swap them in -- the CI tightens
    with more samples.

    Args:
        current_scores: ``{benchmark: {"score": float, "per_category": {...}}}``.
        previous_scores: Same shape as ``current_scores`` (prior run).
        confidence: Confidence level (0..1).
        n_bootstrap: Bootstrap replicate count.
        seed: Deterministic RNG seed.

    Returns:
        ``{benchmark: {significant, ci_lower, ci_upper, mean_delta, n_samples}}``.
        Benchmarks present in only one run are omitted.
    """
    result = {}
    for benchmark, curr_entry in current_scores.items():
        if benchmark not in previous_scores:
            continue
        prev_entry = previous_scores[benchmark]

        # Collect per-category paired differences as bootstrap samples.
        curr_cats = (
            curr_entry.get("per_category", {}) if isinstance(curr_entry, dict) else {}
        )
        prev_cats = (
            prev_entry.get("per_category", {}) if isinstance(prev_entry, dict) else {}
        )
        diffs = []
        for category, curr_val in curr_cats.items():
            if category not in prev_cats:
                continue
            try:
                diffs.append(float(curr_val) - float(prev_cats[category]))
            except (TypeError, ValueError):
                continue

        # If per_category is empty, fall back to the single aggregate delta so
        # callers still get a (wide) CI rather than an empty entry.
        if not diffs and isinstance(curr_entry, dict) and isinstance(prev_entry, dict):
            try:
                diffs = [float(curr_entry.get("score", 0.0))
                         - float(prev_entry.get("score", 0.0))]
            except (TypeError, ValueError):
                diffs = []

        if not diffs:
            continue

        lower, upper = bootstrap_ci(
            diffs, n_bootstrap=n_bootstrap, confidence=confidence, seed=seed
        )
        mean_delta = sum(diffs) / len(diffs)
        # D-09: degradation significant when CI excludes zero AND mean is negative.
        excludes_zero = (upper < 0.0) or (lower > 0.0)
        significant = bool(excludes_zero and mean_delta < 0.0)

        result[benchmark] = {
            "significant": significant,
            "ci_lower": lower,
            "ci_upper": upper,
            "mean_delta": mean_delta,
            "n_samples": len(diffs),
        }

    return result
