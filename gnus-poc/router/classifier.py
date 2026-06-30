"""High-level rules-based router classifier with fallback chaining.

Implements D-12 (fallback chaining mirroring the ``TeacherCascade`` pattern
from ``distill/cascade.py``) and D-13 (GQHSM-compatible JSON export written
alongside the YAML config).

The public entry point is ``RouterClassifier.classify()``, which returns an
execution plan dict::

    {
        "primary_specialist": str,
        "execution_mode": "single" | "fallback",
        "confidence": float,
        "matched_rule": str,
        "fallback_chain": [str],
    }

Classification is purely rules-based (D-09/D-11 explicitly reject learned
routing). The teacher API is never invoked by ``classify()`` — an optional
confidence recheck via the teacher is a future enhancement.

T-02-07 mitigation: ``router_rules.yaml`` is loaded with ``yaml.safe_load``
and validated at construction time via ``schema.validate_router_rules()``.
T-02-09 mitigation: the encyclopedic ``always_match`` rule at priority 0 is
the ultimate safety net — no query goes unhandled.
"""

import json
import logging
from pathlib import Path
from typing import Optional

import yaml

from router.engine import RouterStateMachine, _DEFAULT_STATES
from router.rules import RuleMatcher
from router.schema import validate_router_rules

logger = logging.getLogger(__name__)

# Confidence used when a plan is built from a fallback (not a direct match).
# Fallback selection is deterministic, not confidence-scored; recording 0.0
# makes the plan's provenance explicit to downstream consumers.
_FALLBACK_CONFIDENCE = 0.0

# Default GQHSM states written to router_rules.json when the classifier
# constructs the JSON export. These mirror the RouterStateMachine default model.
_GQHSM_STATES = [{"name": s} for s in _DEFAULT_STATES]


class RouterClassifier:
    """Rules-based specialist router with fallback chaining.

    The classifier loads ``router_rules.yaml`` from
    ``{project_root}/config/router_rules.yaml`` at construction time,
    validates it against the GQHSM schema, and writes a derived
    ``router_rules.json`` (the compatibility contract for the future C++
    GQHSM integration).

    Attributes:
        project_root: The directory whose ``config/`` holds the router rules.
        rules: The validated list of rule dicts (priority-sorted).
    """

    def __init__(self, project_root: Optional[Path] = None):
        """Load and validate the router rules from YAML.

        Args:
            project_root: Root directory containing ``config/router_rules.yaml``.
                Defaults to the parent of this file's package directory (i.e.
                the ``gnus-poc`` root).

        Raises:
            FileNotFoundError: If ``router_rules.yaml`` is missing.
            ValueError: If the loaded YAML fails schema validation.
        """
        self.project_root = Path(project_root) if project_root else self._default_root()
        self._config_dir = self.project_root / "config"
        self._rules_path = self._config_dir / "router_rules.yaml"
        self._json_path = self._config_dir / "router_rules.json"

        self._rules_config = self._load_yaml(self._rules_path)
        validation = validate_router_rules(self._build_gqhsm_json(self._rules_config))
        if not validation["valid"]:
            raise ValueError(
                "Invalid router rules configuration: " + "; ".join(validation["errors"])
            )

        self._matcher = RuleMatcher(self._rules_config)
        self._rules = self._matcher.rules
        # Build the state machine from the derived GQHSM JSON (D-09, D-10).
        self._machine = RouterStateMachine(self._build_gqhsm_json(self._rules_config))

        # Persist the GQHSM JSON export (D-13) — self-correcting if tampered
        # with because it is regenerated from YAML on every init (T-02-08).
        self._write_json_export()

        logger.debug(
            "RouterClassifier loaded %d rules from %s",
            len(self._rules),
            self._rules_path,
        )

    @property
    def rules(self) -> list:
        """Return the validated, priority-sorted rule list."""
        return list(self._rules)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def classify(self, query: str) -> dict:
        """Classify ``query`` and return an execution plan.

        Mirrors the ``TeacherCascade.execute()`` pattern (D-12):

        1. Match all rules; iterate in priority order.
        2. If a match's confidence >= its rule threshold -> single-mode plan.
        3. Otherwise, walk each rule's ``fallback`` specialist (fallback mode).
        4. Ultimate fallback: the encyclopedic ``always_match`` rule (never fail).

        Args:
            query: The raw user query string.

        Returns:
            Execution plan dict with keys ``primary_specialist``,
            ``execution_mode``, ``confidence``, ``matched_rule``,
            ``fallback_chain``.
        """
        matches = self._matcher.match_rules(query)
        fallback_chain = []

        # Step 1-2: try each rule in priority order for a direct match.
        # ``always_match``-only rules (the default safety net) are skipped here
        # so that they do not preempt a higher-priority rule's fallback chain
        # (D-12). They are reached only via the ultimate-fallback step below.
        for rule_name, confidence, specialist in matches:
            rule = self._rule_by_name(rule_name)
            if not rule:
                continue
            if self._is_always_match_only(rule):
                continue
            if confidence >= rule.get("confidence_threshold", 0.0):
                return self._build_plan(
                    rule, confidence, mode="single", fallback_chain=fallback_chain
                )
            # Track fallbacks offered by rules that didn't clear their threshold.
            fallback = rule.get("fallback")
            if fallback and fallback not in fallback_chain:
                fallback_chain.append(fallback)

        # Step 3: fallback chaining — try each configured fallback specialist.
        for specialist_name in list(fallback_chain):
            fallback_rule = self._matcher.get_rule_by_specialist(specialist_name)
            if fallback_rule:
                return self._build_plan(
                    fallback_rule,
                    _FALLBACK_CONFIDENCE,
                    mode="fallback",
                    fallback_chain=fallback_chain,
                )

        # Step 4: ultimate safety net — encyclopedic specialist (T-02-09).
        ultimate = self._matcher.get_rule_by_specialist("encyclopedic")
        if ultimate:
            return self._build_plan(
                ultimate,
                _FALLBACK_CONFIDENCE,
                mode="fallback",
                fallback_chain=fallback_chain or ["encyclopedic"],
            )

        # Defensive: no rules at all. Return a syntactically valid empty plan.
        logger.error("RouterClassifier has no rules; returning empty plan")
        return {
            "primary_specialist": None,
            "execution_mode": "fallback",
            "confidence": _FALLBACK_CONFIDENCE,
            "matched_rule": None,
            "fallback_chain": fallback_chain,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_plan(
        self, rule: dict, confidence: float, mode: str, fallback_chain: list
    ) -> dict:
        """Assemble an execution plan dict from a selected rule."""
        return {
            "primary_specialist": rule.get("specialist"),
            "execution_mode": mode,
            "confidence": confidence,
            "matched_rule": rule.get("name"),
            "fallback_chain": list(fallback_chain),
        }

    def _rule_by_name(self, name: str) -> dict:
        """Return the rule dict with the given name, or ``{}``."""
        for rule in self._rules:
            if rule.get("name") == name:
                return rule
        return {}

    @staticmethod
    def _is_always_match_only(rule: dict) -> bool:
        """True when a rule's triggers are exclusively ``always_match``.

        Such rules are the default safety net and are skipped during the
        single-mode selection pass so they cannot preempt a higher-priority
        rule's fallback chain (D-12).
        """
        triggers = rule.get("triggers", [])
        if not triggers:
            return False
        return all(t.get("type") == "always_match" for t in triggers)

    @staticmethod
    def _load_yaml(path: Path) -> dict:
        """Safely load YAML from ``path`` (T-02-07: always ``safe_load``)."""
        if not path.exists():
            raise FileNotFoundError(f"Router rules YAML not found: {path}")
        with path.open("r", encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}

    def _write_json_export(self) -> None:
        """Write the derived GQHSM JSON export (D-13)."""
        gqhsm = self._build_gqhsm_json(self._rules_config)
        self._config_dir.mkdir(parents=True, exist_ok=True)
        with self._json_path.open("w", encoding="utf-8") as fh:
            json.dump(gqhsm, fh, indent=2)

    @staticmethod
    def _build_gqhsm_json(rules_config: dict) -> dict:
        """Construct the GQHSM-compatible JSON document from the YAML rules.

        The JSON carries the default GQHSM state model plus the rule-derived
        transitions. The same document feeds both the Python state machine and
        the future C++ GQHSM integration (D-10, D-13).
        """
        return {
            "states": _GQHSM_STATES,
            "transitions": _default_gqhsm_transitions(),
            "initial": _DEFAULT_STATES[0],
            "rules": rules_config.get("router", {}).get("rules", []),
        }

    @staticmethod
    def _default_root() -> Path:
        """Return the gnus-poc root derived from this file's location."""
        return Path(__file__).resolve().parent.parent


def _default_gqhsm_transitions() -> list:
    """Return the GQHSM transition list written into router_rules.json."""
    return [
        {
            "trigger": "begin_keyword",
            "source": "pre_classify",
            "dest": "keyword_match",
            "conditions": [],
            "unless": [],
            "actions": [],
        },
        {
            "trigger": "matched_keywords",
            "source": "keyword_match",
            "dest": "select_specialist",
            "conditions": ["confidence_above_threshold"],
            "unless": [],
            "actions": ["set_specialist_from_match"],
        },
        {
            "trigger": "no_match",
            "source": "keyword_match",
            "dest": "regex_match",
            "conditions": [],
            "unless": [],
            "actions": [],
        },
        {
            "trigger": "matched_regex",
            "source": "regex_match",
            "dest": "select_specialist",
            "conditions": ["confidence_above_threshold"],
            "unless": [],
            "actions": ["set_specialist_from_match"],
        },
        {
            "trigger": "no_match",
            "source": "regex_match",
            "dest": "syntax_density",
            "conditions": [],
            "unless": [],
            "actions": [],
        },
        {
            "trigger": "matched_density",
            "source": "syntax_density",
            "dest": "select_specialist",
            "conditions": ["confidence_above_threshold"],
            "unless": [],
            "actions": ["set_specialist_from_match"],
        },
        {
            "trigger": "no_match",
            "source": "syntax_density",
            "dest": "fallback_chain",
            "conditions": [],
            "unless": [],
            "actions": [],
        },
        {
            "trigger": "fallback_selected",
            "source": "fallback_chain",
            "dest": "select_specialist",
            "conditions": [],
            "unless": [],
            "actions": ["set_specialist_from_match"],
        },
        {
            "trigger": "finalise",
            "source": "select_specialist",
            "dest": "classified",
            "conditions": [],
            "unless": [],
            "actions": ["log_classification"],
        },
        {
            "trigger": "finalise",
            "source": "fallback_chain",
            "dest": "classified",
            "conditions": [],
            "unless": [],
            "actions": ["log_classification"],
        },
    ]
