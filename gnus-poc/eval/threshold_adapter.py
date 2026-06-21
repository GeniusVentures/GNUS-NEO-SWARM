"""LLM-based adaptive gate threshold recommendations.

Uses the Phase 1 ``TeacherClient`` to prompt an LLM with structured evaluation
metrics and prior-run context, asking it to recommend updated gate thresholds
with justification.

Auto-apply gate (T-02-10): Recommendations are only applied automatically when
the LLM's confidence exceeds ``confidence_minimum`` AND every recommended
change is less than ``max_adjustment_percent`` of the current threshold.
Otherwise the recommendation is logged for human review only.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt template (Pattern 4 from 02-RESEARCH.md)
# ---------------------------------------------------------------------------

THRESHOLD_EVALUATION_PROMPT = """You are an ML training quality analyst. Review the following specialist evaluation metrics and recommend updated gate thresholds.

## Specialist: {niche}
## Current Thresholds
- Perplexity max: {current_ppl_max}
- BLEU score min: {current_bleu_min}
- Consecutive failures to block: {current_consecutive_failures}

## Current Run Metrics
- Perplexity: {ppl:.3f}
- BLEU Score: {bleu:.4f}
- ROUGE-L: {rouge_l:.4f}
- Latency (ms/token): {latency:.2f}

## Prior Run Metrics (for trend analysis)
{prior_runs}

## Instructions
1. Compare current metrics against thresholds and prior runs.
2. If metrics are improving (PPL decreasing, BLEU increasing), recommend tightening thresholds.
3. If metrics are degrading, recommend keeping or loosening thresholds.
4. Identify any anomalous metric deltas that warrant human review.
5. Provide your recommendations in the following JSON format:

```json
{{
  "recommended_thresholds": {{
    "perplexity": {{"max": <float>, "reasoning": "<str>"}},
    "bleu_score": {{"min": <float>, "reasoning": "<str>"}},
    "consecutive_failures_to_block": {{"value": <int>, "reasoning": "<str>"}}
  }},
  "anomalies_detected": [{{"metric": "<str>", "delta_pct": <float>, "severity": "low|medium|high"}}],
  "confidence": <float 0.0-1.0>,
  "notes": "<str>"
}}
```

## Constraints
- Do not recommend thresholds that would immediately fail the current run.
- Threshold changes should be gradual (max 20% adjustment per evaluation).
- If confidence in recommendations is below 0.7, flag for human review.
"""

# Regex to extract JSON code block from LLM response
_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class ThresholdRecommendation:
    """Structured result from LLM threshold evaluation.

    ``auto_applied`` is ``True`` only when the confidence and change
    magnitude meet the auto-apply criteria (T-02-10).
    """

    niche: str
    recommended_thresholds: Dict[str, Any]
    anomalies_detected: List[Dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0
    notes: str = ""
    auto_applied: bool = False
    updated_thresholds: Optional[Dict[str, Any]] = None
    raw_llm_response: Optional[str] = None


# ---------------------------------------------------------------------------
# ThresholdAdapter
# ---------------------------------------------------------------------------

class ThresholdAdapter:
    """LLM-based adaptive threshold evaluator via TeacherClient.

    Sends structured evaluation metrics to an LLM, parses the JSON
    recommendation, and conditionally auto-applies threshold changes
    when confidence and magnitude criteria are met.

    Args:
        teacher_client: Phase 1 ``TeacherClient`` instance for LLM calls.
        project_root: Root of the gnus-poc project (for config loading).
        config: Optional dict of ``adaptive_thresholding`` settings.
            Loaded from ``config/pipeline.yaml`` if not provided.
    """

    def __init__(
        self,
        teacher_client,
        project_root: Optional[Path] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self._teacher = teacher_client

        if project_root is None:
            project_root = Path(__file__).resolve().parent.parent
        self._project_root = project_root

        if config is None:
            config = self._load_config(project_root)
        self._config = config

        self._confidence_minimum = float(config.get("confidence_minimum", 0.9))
        self._max_adjustment_percent = float(config.get("max_adjustment_percent", 20.0))
        self._enabled = bool(config.get("enabled", False))

    # ------------------------------------------------------------------
    # Config
    # ------------------------------------------------------------------

    def _load_config(self, project_root: Path) -> Dict[str, Any]:
        """Load ``adaptive_thresholding`` section from pipeline.yaml."""
        config_path = project_root / "config" / "pipeline.yaml"
        try:
            with config_path.open() as f:
                raw = yaml.safe_load(f)
            return raw.get("adaptive_thresholding", {})
        except (OSError, yaml.YAMLError) as exc:
            logger.warning(
                "Could not load adaptive_thresholding config from %s: %s",
                config_path,
                exc,
            )
            return {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate_thresholds(
        self,
        niche: str,
        current_metrics: Dict[str, Any],
        current_thresholds: Dict[str, Any],
        prior_runs: Optional[List[Dict[str, Any]]] = None,
        model_name: Optional[str] = None,
    ) -> ThresholdRecommendation:
        """Prompt the LLM for threshold recommendations and conditionally apply.

        Args:
            niche: Specialist niche name.
            current_metrics: Dict with keys ``ppl``, ``bleu``, ``rouge_l``,
                ``latency`` matching the current evaluation run.
            current_thresholds: Dict with keys ``ppl_max``, ``bleu_min``,
                ``consecutive_failures``.
            prior_runs: Optional list of prior-run metric dicts.
            model_name: Optional teacher model override.

        Returns:
            ``ThresholdRecommendation`` with the LLM's analysis and any
            auto-applied threshold updates.
        """
        if prior_runs is None:
            prior_runs = []

        prompt = self._build_prompt(niche, current_metrics, current_thresholds, prior_runs)
        response = self._call_llm(prompt, model_name=model_name)
        parsed = self._parse_response(response)

        recommendation = ThresholdRecommendation(
            niche=niche,
            recommended_thresholds=parsed.get("recommended_thresholds", {}),
            anomalies_detected=parsed.get("anomalies_detected", []),
            confidence=float(parsed.get("confidence", 0.0)),
            notes=parsed.get("notes", ""),
            raw_llm_response=response,
        )

        if self._should_auto_apply(recommendation, current_thresholds):
            recommendation.auto_applied = True
            recommendation.updated_thresholds = self._compute_updated_thresholds(
                recommendation, current_thresholds
            )
            logger.info(
                "ThresholdAdapter: auto-applied threshold update for %s "
                "(confidence=%.2f, changes within %d%%)",
                niche,
                recommendation.confidence,
                self._max_adjustment_percent,
            )
        else:
            logger.info(
                "ThresholdAdapter: recommendation logged for human review "
                "(niche=%s, confidence=%.2f, auto_apply criteria not met)",
                niche,
                recommendation.confidence,
            )

        return recommendation

    # ------------------------------------------------------------------
    # Prompt building (T-02-09: prior metrics are structured JSON in code block)
    # ------------------------------------------------------------------

    def _build_prompt(
        self,
        niche: str,
        current_metrics: Dict[str, Any],
        current_thresholds: Dict[str, Any],
        prior_runs: List[Dict[str, Any]],
    ) -> str:
        """Format the THRESHOLD_EVALUATION_PROMPT with runtime data.

        Prior run metrics are embedded as a JSON code block to prevent
        prompt injection (T-02-09 mitigation).
        """
        prior_text = "No prior runs available."
        if prior_runs:
            # Format as JSON code block for T-02-09 mitigation
            prior_json = json.dumps(prior_runs, indent=2)
            prior_text = f"```json\n{prior_json}\n```"

        return THRESHOLD_EVALUATION_PROMPT.format(
            niche=niche,
            current_ppl_max=current_thresholds.get("ppl_max", 50.0),
            current_bleu_min=current_thresholds.get("bleu_min", 0.15),
            current_consecutive_failures=current_thresholds.get("consecutive_failures", 3),
            ppl=current_metrics.get("ppl", 0.0),
            bleu=current_metrics.get("bleu", 0.0),
            rouge_l=current_metrics.get("rouge_l", 0.0),
            latency=current_metrics.get("latency", 0.0),
            prior_runs=prior_text,
        )

    # ------------------------------------------------------------------
    # LLM call
    # ------------------------------------------------------------------

    def _call_llm(self, prompt: str, model_name: Optional[str] = None) -> str:
        """Send the prompt to TeacherClient and return the content string."""
        messages = [
            {"role": "user", "content": prompt},
        ]
        response = self._teacher.generate(model_name=model_name, messages=messages)
        return response.choices[0].message.content

    # ------------------------------------------------------------------
    # Response parsing
    # ------------------------------------------------------------------

    def _parse_response(self, content: str) -> Dict[str, Any]:
        """Extract JSON from an LLM response string.

        Attempts to find a JSON code block first, then falls back to
        parsing the entire content as JSON.  Returns an empty dict on
        parse failure to avoid crashing the pipeline.
        """
        # Try JSON code block extraction
        match = _JSON_BLOCK_RE.search(content)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError as exc:
                logger.warning(
                    "ThresholdAdapter: JSON code block parse failed: %s",
                    exc,
                )

        # Fallback: try parsing entire response
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            logger.error(
                "ThresholdAdapter: could not parse LLM response as JSON: %s",
                exc,
            )
            return {}

    # ------------------------------------------------------------------
    # Auto-apply gate (T-02-10: confidence > 0.9 AND change < 20%)
    # ------------------------------------------------------------------

    def _should_auto_apply(
        self,
        recommendation: ThresholdRecommendation,
        current_thresholds: Dict[str, Any],
    ) -> bool:
        """Check whether the recommendation meets auto-apply criteria.

        Two conditions must BOTH be true (T-02-10):
        1. ``confidence`` > ``confidence_minimum`` (default 0.9)
        2. Every recommended threshold change is < ``max_adjustment_percent``
           (default 20%) of the current value.
        """
        if not self._enabled:
            logger.debug("ThresholdAdapter: adaptive thresholding is disabled in config")
            return False

        if recommendation.confidence <= self._confidence_minimum:
            return False

        # Check every recommended change against the max adjustment cap
        recs = recommendation.recommended_thresholds
        if not recs:
            return False

        if not self._all_changes_within_cap(recs, current_thresholds):
            return False

        return True

    def _all_changes_within_cap(
        self,
        recs: Dict[str, Any],
        current_thresholds: Dict[str, Any],
    ) -> bool:
        """Return True if ALL recommended changes are within the adjustment cap."""
        # Map recommendation keys to current threshold keys
        key_map = {
            "perplexity": ("ppl_max", "max"),
            "bleu_score": ("bleu_min", "min"),
            "consecutive_failures_to_block": ("consecutive_failures", "value"),
        }

        for rec_key, (current_key, value_key) in key_map.items():
            rec_entry = recs.get(rec_key)
            if rec_entry is None:
                continue

            current_val = float(current_thresholds.get(current_key, 0))
            if current_val == 0:
                continue

            recommended_val = float(rec_entry.get(value_key, current_val))
            change_pct = abs(recommended_val - current_val) / current_val * 100.0

            if change_pct >= self._max_adjustment_percent:
                logger.info(
                    "ThresholdAdapter: %s change of %.1f%% exceeds max %d%% — "
                    "skip auto-apply",
                    rec_key,
                    change_pct,
                    self._max_adjustment_percent,
                )
                return False

        return True

    # ------------------------------------------------------------------
    # Threshold computation
    # ------------------------------------------------------------------

    def _compute_updated_thresholds(
        self,
        recommendation: ThresholdRecommendation,
        current_thresholds: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Build the updated thresholds dict from the recommendation."""
        recs = recommendation.recommended_thresholds
        updated: Dict[str, Any] = {}

        ppl_rec = recs.get("perplexity", {})
        if "max" in ppl_rec:
            updated["ppl_max"] = float(ppl_rec["max"])

        bleu_rec = recs.get("bleu_score", {})
        if "min" in bleu_rec:
            updated["bleu_min"] = float(bleu_rec["min"])

        cfb_rec = recs.get("consecutive_failures_to_block", {})
        if "value" in cfb_rec:
            updated["consecutive_failures"] = int(cfb_rec["value"])

        return updated

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def confidence_minimum(self) -> float:
        return self._confidence_minimum

    @property
    def max_adjustment_percent(self) -> float:
        return self._max_adjustment_percent
