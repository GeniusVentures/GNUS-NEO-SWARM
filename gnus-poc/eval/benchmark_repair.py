"""Repair suggestion reports for below-threshold specialists (Plan 04-04 Task 2).

D-10 LOCKED DECISION: repair suggestions, NOT auto-mutation. The system advises;
the operator acts. After the 3rd consecutive failure the pipeline blocks
promotion and manual intervention is required.

T-04-19 mitigation: this module contains NO imports of any config-writing
function. The ``_generate_config_suggestions`` helper returns plain JSON-serializable
dictionaries only -- it never mutates a live config. Reports are read-only JSON
artifacts.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# D-10 escalation thresholds (consecutive failure counts).
_K_WARNING_THRESHOLD = 1
_K_CRITICAL_THRESHOLD = 2
_K_BLOCKING_THRESHOLD = 3

# Config suggestion tuning constants.
_K_MAJOR_UNDERPERFORMANCE_PCT = 10.0
_K_MODERATE_UNDERPERFORMANCE_PCT = 5.0


def _repair_reports_dir(project_root: Optional[Path]) -> Path:
    """Return (creating if needed) the artifacts/repair_reports/ directory."""
    root = Path(project_root) if project_root is not None else Path.cwd()
    reports = root / "artifacts" / "repair_reports"
    reports.mkdir(parents=True, exist_ok=True)
    return reports


def _compute_severity(consecutive_failures: dict) -> str:
    """Map the highest consecutive failure count to a severity level (D-10).

    - 0 failures  -> ``"none"``
    - 1 failure   -> ``"warning"``
    - 2 failures  -> ``"critical"``
    - 3+ failures -> ``"blocking"``

    Args:
        consecutive_failures: ``{benchmark: int}`` from the gate state.

    Returns:
        Severity string.
    """
    if not consecutive_failures:
        return "none"
    highest = max(int(v) for v in consecutive_failures.values())
    if highest >= _K_BLOCKING_THRESHOLD:
        return "blocking"
    if highest == _K_CRITICAL_THRESHOLD:
        return "critical"
    if highest == _K_WARNING_THRESHOLD:
        return "warning"
    return "none"


def _extract_score(entry) -> float:
    """Pull a scalar score from a benchmark result entry.

    Handles ``{"score": x}``, ``{"pass@1": x}``, ``{"acc": x}``, and bare scalars.
    """
    if not isinstance(entry, dict):
        return float(entry) if entry is not None else 0.0
    for key in ("score", "pass@1", "acc"):
        if key in entry:
            try:
                return float(entry[key])
            except (TypeError, ValueError):
                return 0.0
    return 0.0


def _benchmark_threshold(config: dict, benchmark: str) -> float:
    """Read the hard_floor for a benchmark from the effective config."""
    benchmarks = (config or {}).get("benchmarks", {}) if isinstance(config, dict) else {}
    entry = benchmarks.get(benchmark, {})
    if isinstance(entry, dict):
        return float(entry.get("hard_floor", 0.0))
    return 0.0


def _per_category_threshold(config: dict, benchmark: str) -> dict:
    """Read per-category hard floors (optional) for a benchmark."""
    benchmarks = (config or {}).get("benchmarks", {}) if isinstance(config, dict) else {}
    entry = benchmarks.get(benchmark, {})
    if isinstance(entry, dict):
        return dict(entry.get("per_category_hard_floor", {}) or {})
    return {}


def _build_underperforming_entries(
    benchmark: str,
    results_entry: dict,
    hard_floor: float,
    per_category_floors: dict,
) -> list:
    """Build underperformance entries for a single benchmark.

    Always emits an ``aggregate`` entry when the overall score is below the hard
    floor. Additionally emits one entry per failing category when per-category
    thresholds are configured.
    """
    entries = []
    score = _extract_score(results_entry)
    if score < hard_floor:
        entries.append({
            "benchmark": benchmark,
            "category": "aggregate",
            "score": score,
            "threshold": hard_floor,
            "margin": score - hard_floor,
            "below_threshold_pct": (
                (hard_floor - score) / hard_floor * 100.0 if hard_floor > 0 else 0.0
            ),
        })

    per_category = {}
    if isinstance(results_entry, dict):
        per_category = results_entry.get("per_category", {}) or {}

    for category, cat_score in per_category.items():
        if category == "aggregate":
            continue
        floor = per_category_floors.get(category, hard_floor)
        try:
            cat_score_f = float(cat_score)
        except (TypeError, ValueError):
            continue
        if cat_score_f < floor:
            # Avoid duplicate with the aggregate entry when the benchmark only
            # has a single aggregate category.
            entries.append({
                "benchmark": benchmark,
                "category": category,
                "score": cat_score_f,
                "threshold": floor,
                "margin": cat_score_f - floor,
                "below_threshold_pct": (
                    (floor - cat_score_f) / floor * 100.0 if floor > 0 else 0.0
                ),
            })

    return entries


def _generate_config_suggestions(
    niche_name: str,
    underperforming: list,
    config: dict,
) -> list:
    """Map underperformance patterns to advisory config suggestions (D-10).

    T-04-19 mitigation: returns plain dicts only. Does NOT import or call any
    config-writing function. Suggestions are advisory -- the operator decides.

    Patterns:
      - Below hard floor by >10%: increase iterations, lower distill_loss_target.
      - Below hard floor by 5-10%: moderate parameter tweak.
      - Below hard floor by <5%: minor adjustment or re-run suggestion.
    """
    suggestions = []
    if not underperforming:
        return suggestions

    benchmarks_cfg = (config or {}).get("benchmarks", {}) if isinstance(config, dict) else {}

    # Aggregate worst underperformance per benchmark for rationale text.
    worst_by_benchmark = {}
    for entry in underperforming:
        bench = entry["benchmark"]
        if bench not in worst_by_benchmark:
            worst_by_benchmark[bench] = entry
        else:
            if entry["below_threshold_pct"] > worst_by_benchmark[bench]["below_threshold_pct"]:
                worst_by_benchmark[bench] = entry

    for bench, entry in worst_by_benchmark.items():
        pct = entry["below_threshold_pct"]
        score = entry["score"]
        floor = entry["threshold"]

        if pct > _K_MAJOR_UNDERPERFORMANCE_PCT:
            suggestions.append({
                "parameter": "distill_loss_target",
                "current_value": 1.5,
                "suggested_value": 1.2,
                "rationale": (
                    f"{bench} score {score:.4f} is {pct:.1f}% below hard floor "
                    f"{floor:.4f}. Lowering distillation loss target increases "
                    f"training pressure on the {niche_name} domain."
                ),
            })
            suggestions.append({
                "parameter": "iterations",
                "current_value": 1000,
                "suggested_value": 1500,
                "rationale": (
                    f"Consider increasing training iterations for {niche_name} "
                    f"specialist -- {bench} is significantly below threshold."
                ),
            })
        elif pct > _K_MODERATE_UNDERPERFORMANCE_PCT:
            suggestions.append({
                "parameter": "distill_loss_target",
                "current_value": 1.5,
                "suggested_value": 1.35,
                "rationale": (
                    f"{bench} score {score:.4f} is {pct:.1f}% below hard floor "
                    f"{floor:.4f}. A moderate distillation loss target adjustment "
                    f"may improve {niche_name} performance."
                ),
            })
        else:
            suggestions.append({
                "parameter": "rerun",
                "current_value": None,
                "suggested_value": True,
                "rationale": (
                    f"{bench} score {score:.4f} is only {pct:.1f}% below hard floor "
                    f"{floor:.4f}. Consider re-running to confirm before tuning."
                ),
            })

    return suggestions


def generate_repair_report(
    niche_name: str,
    gate_result: dict,
    benchmark_results: dict,
    config: Optional[dict] = None,
    previous_results: Optional[dict] = None,
) -> dict:
    """Generate a structured repair suggestion report (D-10).

    The system advises; the operator acts. This function NEVER mutates configs.

    Args:
        niche_name: Specialist niche.
        gate_result: Output of ``Benchmarker.gate_check_benchmarks()`` (Plan 04-03).
        benchmark_results: Current benchmark results payload.
        config: Effective config dict with ``benchmarks`` block.
        previous_results: Optional prior-run results payload. When absent, the
            report is flagged ``no_baseline_available: True`` and only absolute
            threshold comparison is used.

    Returns:
        Structured repair report dict (JSON-serializable).
    """
    config = config or {}
    results_block = benchmark_results.get("results", {}) if benchmark_results else {}
    consecutive_failures = gate_result.get("consecutive_failures", {}) or {}
    severity = _compute_severity(consecutive_failures)

    # Build per-benchmark + per-category underperformance entries.
    underperforming = []
    for benchmark, results_entry in results_block.items():
        hard_floor = _benchmark_threshold(config, benchmark)
        per_cat_floors = _per_category_threshold(config, benchmark)
        entries = _build_underperforming_entries(
            benchmark, results_entry, hard_floor, per_cat_floors
        )
        underperforming.extend(entries)

    suggestions = _generate_config_suggestions(niche_name, underperforming, config)

    # Determine status.
    if not underperforming:
        status = "all_passing"
    elif severity == "blocking":
        status = "failures"
    else:
        status = "failures"

    # Action required: blocking severity escalates to manual intervention.
    if severity == "blocking":
        action_required = "manual_intervention_required"
    elif underperforming:
        action_required = "review_and_adjust"
    else:
        action_required = "none"

    # SGFP4 regression summary (carried through from gate_check_benchmarks).
    sgfp4_regression_summary = {"checked": False, "significant": False, "detail": ""}
    sgfp4_from_gate = gate_result.get("sgfp4_regression")
    if sgfp4_from_gate:
        sgfp4_regression_summary = {
            "checked": True,
            "significant": not bool(sgfp4_from_gate.get("passed", True)),
            "detail": sgfp4_from_gate.get("detail", ""),
        }

    timestamp_utc = datetime.now(timezone.utc).isoformat()
    report_id_ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

    report = {
        "niche": niche_name,
        "timestamp_utc": timestamp_utc,
        "status": status,
        "severity": severity,
        "consecutive_failures": max(consecutive_failures.values()) if consecutive_failures else 0,
        "underperforming_categories": underperforming,
        "suggested_config_adjustments": suggestions,
        "sgfp4_regression": sgfp4_regression_summary,
        "action_required": action_required,
        "no_baseline_available": previous_results is None,
        "report_id": f"{niche_name}_{report_id_ts}",
    }
    return report


def save_repair_report(
    niche_name: str,
    report: dict,
    project_root: Optional[Path] = None,
) -> Path:
    """Write a repair report to ``artifacts/repair_reports/{niche}_{timestamp}.json``.

    Args:
        niche_name: Specialist niche.
        report: Report dict from ``generate_repair_report``.
        project_root: Project root.

    Returns:
        Path to the written report.
    """
    reports_dir = _repair_reports_dir(project_root)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    out_path = reports_dir / f"{niche_name}_{timestamp}.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    logger.info("Saved repair report niche=%s severity=%s -> %s",
                niche_name, report.get("severity"), out_path)
    return out_path


def should_block_pipeline(gate_result: dict) -> bool:
    """Return True when the gate is blocking AND any benchmark has 3+ failures.

    D-10: 3rd consecutive failure blocks pipeline promotion. The operator must
    intervene manually -- the system never auto-fixes.

    Args:
        gate_result: Output of ``Benchmarker.gate_check_benchmarks()``.

    Returns:
        True when the pipeline should be blocked.
    """
    if not isinstance(gate_result, dict):
        return False
    if not gate_result.get("blocking", False):
        return False
    consecutive = gate_result.get("consecutive_failures", {}) or {}
    if not consecutive:
        return False
    niche = gate_result.get("niche", "<unknown>")
    blocked = any(int(v) >= _K_BLOCKING_THRESHOLD for v in consecutive.values())
    if blocked:
        logger.warning(
            "Pipeline blocked for %s -- manual intervention required. "
            "See artifacts/repair_reports/ for details.",
            niche,
        )
    return blocked
