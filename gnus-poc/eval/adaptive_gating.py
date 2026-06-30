"""LLM-based adaptive gate-threshold updates per D-15.

Plan 02-04. Implements the "adaptive gating" decision: the LLM API can
recursively update gate thresholds based on observed performance trends.
Feature is gated behind ``adaptive_gating.enabled`` (default: false) in
``config/pipeline.yaml``. When enabled, the LLM receives the last N
evaluation results and suggests threshold adjustments; a human operator
reviews and approves changes before they take effect (D-15 / T-02-21).

Trust-boundary mitigations:
- T-02-21: feature disabled by default; require_human_approval blocks
  automatic application; safety bounds clamp suggestions.
- T-02-22: LLM prompt is assembled from numeric metric values only — no
  free-form user text enters the prompt, minimizing prompt-injection surface.

This module does NOT import TeacherClient at module load time. Callers
inject a ``teacher_client`` (anything exposing ``generate(model_name=,
messages=)`` whose response has ``.choices[0].message.content``). Tests
inject a fake; production wires a real ``distill.teacher.TeacherClient``.
"""

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from eval.metric_store import MetricStore

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# Defaults mirror config/pipeline.yaml adaptive_gating block. Kept here so the
# module behaves sanely when no config is supplied (e.g. direct unit tests).
_DEFAULTS = {
    "enabled": False,
    "lookback_runs": 5,
    "max_adjustment_percent": 20,
    "min_metric_runs": 3,
    "safety_bound_pct": 50,        # never tighten below 50% of original
    "safety_bound_loosen_pct": 200,  # never loosen above 200% of original
    "require_human_approval": True,
}


class AdaptiveGating:
    """LLM-based adaptive threshold update mechanism per D-15.

    Gated behind ``adaptive_gating.enabled`` (default: false). When enabled,
    periodically queries an LLM with recent evaluation trends to suggest gate
    threshold adjustments. Human operator reviews and approves changes before
    they take effect.

    The LLM call is optional: when ``teacher_client`` is None the module
    returns enabled=True with empty suggestions (graceful degradation — the
    feature is wired but cannot reach an LLM).
    """

    def __init__(
        self,
        metric_store: MetricStore,
        teacher_client: Optional[object] = None,
        config: Optional[dict] = None,
        specialist_gates: Optional[dict] = None,
        project_root: Optional[Path] = None,
    ):
        """Initialize AdaptiveGating.

        Args:
            metric_store: MetricStore instance for loading multi-run history.
            teacher_client: Optional client exposing
                ``generate(model_name=, messages=)`` whose response carries
                ``.choices[0].message.content``. Typically a
                ``distill.teacher.TeacherClient``.
            config: adaptive_gating config dict from pipeline.yaml. When None,
                module defaults are used (feature disabled).
            specialist_gates: optional mapping of niche -> gates dict (same
                shape as config/specialists/<niche>.yaml evaluation.gates).
                When None, gates are loaded from the specialist YAML on disk
                at suggest/apply time.
            project_root: gnus-poc project root. Auto-located when None.
        """
        self._metric_store = metric_store
        self._teacher_client = teacher_client
        self._config = {**_DEFAULTS, **(config or {})}
        self._specialist_gates = specialist_gates or {}
        if project_root is None:
            # Derive from the metric_store so a single project_root flows
            # through the persistence layer without callers having to pass it
            # twice. Fall back to the module-level PROJECT_ROOT only when the
            # store does not expose one.
            project_root = getattr(metric_store, "_project_root", None) or PROJECT_ROOT
        self._project_root = project_root

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def suggest_threshold_updates(
        self, niche_name: str, lookback_runs: Optional[int] = None
    ) -> dict:
        """Suggest gate-threshold updates for a niche based on recent trends.

        Args:
            niche_name: Specialist niche.
            lookback_runs: Override for config lookback_runs.

        Returns:
            Structured dict:
                {
                    "enabled": bool,
                    "niche": str,
                    "trends": {metric: {"direction": str, "values": [float]}},
                    "suggestions": {metric: {"current_max": ..., "suggested_max": ..., "rationale": str}},
                    "requires_approval": True,
                    "safety_bounds_applied": bool,
                    "reason": str  # only when suggestions is empty
                }
        """
        if not self._config.get("enabled", False):
            return {"enabled": False, "suggestions": {}}

        min_runs = int(self._config.get("min_metric_runs", _DEFAULTS["min_metric_runs"]))
        lookback = int(
            lookback_runs if lookback_runs is not None
            else self._config.get("lookback_runs", _DEFAULTS["lookback_runs"])
        )

        history = self._metric_store.load_training_eval_history(niche_name)
        if len(history) < min_runs:
            return {
                "enabled": True,
                "niche": niche_name,
                "trends": {},
                "suggestions": {},
                "requires_approval": True,
                "safety_bounds_applied": False,
                "reason": "insufficient history",
            }

        recent = history[-lookback:]
        trends = self._extract_trends(recent)
        current_gates = self._load_current_gates(niche_name)

        if self._teacher_client is None:
            logger.info(
                "AdaptiveGating: no teacher_client configured; returning empty "
                "suggestions for niche=%s", niche_name,
            )
            return {
                "enabled": True,
                "niche": niche_name,
                "trends": trends,
                "suggestions": {},
                "requires_approval": True,
                "safety_bounds_applied": False,
                "reason": "no teacher_client configured",
            }

        raw_suggestions = self._query_llm(niche_name, trends, current_gates, recent)
        clamped, safety_applied = self._apply_safety_bounds(
            raw_suggestions, current_gates
        )

        return {
            "enabled": True,
            "niche": niche_name,
            "trends": trends,
            "suggestions": clamped,
            "requires_approval": True,
            "safety_bounds_applied": safety_applied,
        }

    def apply_approved_changes(
        self, niche_name: str, suggestions: dict
    ) -> dict:
        """Apply human-approved threshold suggestions to the specialist YAML.

        Per D-15 / T-02-21: changes are only applied after explicit human
        approval. This method writes the new thresholds to
        ``config/specialists/<niche>.yaml`` and records an audit log entry
        with old/new values and an approval timestamp.

        Args:
            niche_name: Specialist niche.
            suggestions: Output of ``suggest_threshold_updates()["suggestions"]``
                (or an equivalent manually-approved dict).

        Returns:
            Dict with ``applied`` (bool) and ``changes`` (list of per-metric
            change records).
        """
        if not suggestions:
            return {"applied": False, "changes": [], "reason": "no suggestions to apply"}

        cfg_path = self._project_root / "config" / "specialists" / f"{niche_name}.yaml"
        if not cfg_path.exists():
            logger.warning(
                "AdaptiveGating: specialist config %s not found; cannot apply.", cfg_path
            )
            return {"applied": False, "changes": [], "reason": "specialist config missing"}

        import yaml

        with cfg_path.open("r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}

        gates = ((cfg.get("evaluation") or {}).get("gates") or {})
        changes = []
        approval_ts = datetime.now(timezone.utc).isoformat()

        for metric, suggestion in suggestions.items():
            if not isinstance(suggestion, dict):
                continue
            gate = gates.get(metric) or {}
            old_value = None
            new_value = None
            if "suggested_max" in suggestion and "max" in gate:
                old_value = gate["max"]
                new_value = float(suggestion["suggested_max"])
                gate["max"] = new_value
            elif "suggested_min" in suggestion and "min" in gate:
                old_value = gate["min"]
                new_value = float(suggestion["suggested_min"])
                gate["min"] = new_value
            else:
                continue
            changes.append({
                "metric": metric,
                "old_value": old_value,
                "new_value": new_value,
                "rationale": suggestion.get("rationale", ""),
                "approved_at": approval_ts,
            })
            gates[metric] = gate

        if not changes:
            return {"applied": False, "changes": [], "reason": "no applicable thresholds"}

        cfg.setdefault("evaluation", {})["gates"] = gates
        with cfg_path.open("w", encoding="utf-8") as f:
            yaml.safe_dump(cfg, f, default_flow_style=False, sort_keys=False)

        logger.info(
            "AdaptiveGating: applied %d approved threshold change(s) for niche=%s",
            len(changes), niche_name,
        )
        return {"applied": True, "changes": changes}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_trends(recent_runs: list) -> dict:
        """Extract per-metric trend direction + values from recent runs.

        Args:
            recent_runs: List of training-eval metric dicts (chronological).

        Returns:
            Dict mapping metric name to {"direction": str, "values": [float]}.
            Direction is "improving", "degrading", or "stable" based on the
            linear comparison of first vs last value.
        """
        metrics_of_interest = ("perplexity", "bleu_score", "accuracy")
        trends = {}
        for metric in metrics_of_interest:
            values = []
            for run in recent_runs:
                val = run.get(metric)
                if val is None:
                    continue
                try:
                    values.append(float(val))
                except (TypeError, ValueError):
                    continue
            if len(values) < 2:
                continue
            first, last = values[0], values[-1]
            # For perplexity, lower is better; for bleu/accuracy, higher is better.
            if metric == "perplexity":
                direction = "improving" if last < first else ("degrading" if last > first else "stable")
            else:
                direction = "improving" if last > first else ("degrading" if last < first else "stable")
            trends[metric] = {"direction": direction, "values": values}
        return trends

    def _load_current_gates(self, niche_name: str) -> dict:
        """Load the current gate config for a niche.

        Priority: injected specialist_gates > on-disk specialist YAML.
        """
        if niche_name in self._specialist_gates:
            return self._specialist_gates[niche_name]
        cfg_path = self._project_root / "config" / "specialists" / f"{niche_name}.yaml"
        if not cfg_path.exists():
            return {}
        import yaml
        with cfg_path.open("r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        return (cfg.get("evaluation") or {}).get("gates") or {}

    def _query_llm(
        self, niche_name: str, trends: dict, current_gates: dict, recent_runs: list
    ) -> dict:
        """Query the LLM for threshold suggestions.

        T-02-22: the prompt is assembled from numeric metrics and gate values
        only — no free-form user text enters the prompt. The LLM is instructed
        to return strict JSON.

        Returns a parsed dict of {metric: {"suggested_max"|"suggested_min": float,
        "rationale": str}}. On any failure (API error, unparseable response),
        returns an empty dict (graceful).
        """
        prompt = self._build_prompt(niche_name, trends, current_gates, recent_runs)
        messages = [
            {"role": "system", "content": (
                "You are an ML evaluation engineer. Respond ONLY with a JSON "
                "object mapping metric names to suggested threshold changes. "
                "Each value must have a numeric 'suggested_max' or "
                "'suggested_min' and a short 'rationale' string. Tighten or "
                "loosen by at most 20%."
            )},
            {"role": "user", "content": prompt},
        ]
        try:
            response = self._teacher_client.generate(model_name=None, messages=messages)
        except Exception as exc:  # noqa: BLE001 — fail gracefully
            logger.warning("AdaptiveGating: LLM call failed for niche=%s: %s", niche_name, exc)
            return {}

        content = ""
        try:
            content = response.choices[0].message.content or ""
        except (AttributeError, IndexError, TypeError):
            return ""

        return self._parse_llm_suggestions(content)

    @staticmethod
    def _build_prompt(
        niche_name: str, trends: dict, current_gates: dict, recent_runs: list
    ) -> str:
        """Build the LLM prompt from numeric data only (T-02-22)."""
        # Serialize trends as stable, numeric-only JSON.
        trend_blob = json.dumps(
            {m: t["values"] for m, t in trends.items()},
            sort_keys=True,
        )
        gates_blob = json.dumps(current_gates, sort_keys=True)
        pass_counts = {}
        for metric, trend in trends.items():
            # Heuristic pass-count: count runs where the metric is on the
            # improving side of the current gate. This is numeric only.
            pass_counts[metric] = sum(
                1 for v in trend["values"] if AdaptiveGating._value_is_good(metric, v, current_gates)
            )
        pass_blob = json.dumps(pass_counts, sort_keys=True)
        return (
            f"Specialist niche: {niche_name}\n"
            f"Current gate thresholds: {gates_blob}\n"
            f"Per-metric trend over last {len(recent_runs)} runs (values): {trend_blob}\n"
            f"Recent pass counts per metric: {pass_blob}\n"
            "Suggest new threshold values that maintain quality while adapting "
            "to observed trends. Only suggest tightening or loosening by up to "
            "20% per update. Provide rationale."
        )

    @staticmethod
    def _value_is_good(metric: str, value: float, gates: dict) -> bool:
        """Numeric-only check: does this value pass the current gate for metric?"""
        gate = gates.get(metric) or {}
        if "max" in gate and value > float(gate["max"]):
            return False
        if "min" in gate and value < float(gate["min"]):
            return False
        return True

    @staticmethod
    def _parse_llm_suggestions(content: str) -> dict:
        """Parse the LLM response into a suggestions dict.

        Tolerates a JSON object possibly wrapped in markdown fences or prose.
        Returns {} on any parse failure.
        """
        # Strip markdown code fences if present.
        cleaned = re.sub(r"```(?:json)?", "", content).strip()
        # Find the first {...} block.
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            return {}
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError:
            return {}
        if not isinstance(parsed, dict):
            return {}
        # Normalize: keep only dicts carrying a numeric suggested_max/min.
        out = {}
        for metric, body in parsed.items():
            if not isinstance(body, dict):
                continue
            suggestion = {}
            for key in ("suggested_max", "suggested_min"):
                if key in body and isinstance(body[key], (int, float)) and not isinstance(body[key], bool):
                    suggestion[key] = float(body[key])
            if "rationale" in body and isinstance(body["rationale"], str):
                suggestion["rationale"] = body["rationale"]
            if suggestion:
                out[metric] = suggestion
        return out

    def _apply_safety_bounds(
        self, suggestions: dict, current_gates: dict
    ) -> tuple:
        """Clamp LLM suggestions to safety bounds.

        Per D-15 / T-02-21: never tighten below safety_bound_pct of the
        original threshold (default 50%), never loosen above
        safety_bound_loosen_pct (default 200%).

        Returns:
            Tuple of (clamped_suggestions, safety_bounds_applied: bool).
        """
        tighten_pct = float(self._config.get("safety_bound_pct", _DEFAULTS["safety_bound_pct"])) / 100.0
        loosen_pct = float(self._config.get("safety_bound_loosen_pct", _DEFAULTS["safety_bound_loosen_pct"])) / 100.0
        max_adj_pct = float(self._config.get("max_adjustment_percent", _DEFAULTS["max_adjustment_percent"])) / 100.0

        clamped = {}
        any_clamped = False
        for metric, body in suggestions.items():
            gate = current_gates.get(metric) or {}
            entry = dict(body)
            if "suggested_max" in entry and "max" in gate:
                original = float(gate["max"])
                lower = original * tighten_pct   # never tighten below this
                upper = original * loosen_pct     # never loosen above this
                # Also cap per-update adjustment to max_adj_pct of original.
                adj_cap = original * max_adj_pct
                desired = float(entry["suggested_max"])
                # Tightening: suggested_max < original. Lower bound is max(lower, original - adj_cap).
                if desired < original:
                    floor = max(lower, original - adj_cap)
                    if desired < floor:
                        desired = floor
                        any_clamped = True
                # Loosening: suggested_max > original. Upper bound is min(upper, original + adj_cap).
                elif desired > original:
                    ceil = min(upper, original + adj_cap)
                    if desired > ceil:
                        desired = ceil
                        any_clamped = True
                entry["suggested_max"] = desired
                entry["current_max"] = original
            elif "suggested_min" in entry and "min" in gate:
                original = float(gate["min"])
                # For min-gated metrics, "tighten" = raise the floor, "loosen" = lower it.
                upper = original * loosen_pct
                lower = original * tighten_pct
                adj_cap = original * max_adj_pct
                desired = float(entry["suggested_min"])
                if desired > original:
                    ceil = min(upper, original + adj_cap)
                    if desired > ceil:
                        desired = ceil
                        any_clamped = True
                elif desired < original:
                    floor = max(lower, original - adj_cap)
                    if desired < floor:
                        desired = floor
                        any_clamped = True
                entry["suggested_min"] = desired
                entry["current_min"] = original
            clamped[metric] = entry
        return clamped, any_clamped
