"""Rules-based specialist router.

Loads YAML-defined classification rules and classifies input queries
via keyword, regex, and syntax-density matching.  Produces
``ExecutionPlan`` objects consumed by the pipeline runner.

Key design properties:
- All rules live in YAML — no hardcoded matching logic in Python.
- Priority ordering resolves rule conflicts deterministically.
- Input size is bounded (100 KB) to prevent regex DoS.
- Fallback chaining mirrors the Phase 1 teacher cascade pattern.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import yaml

from router.plan import ExecutionPlan

logger = logging.getLogger(__name__)

# Maximum input size in bytes before we reject a query (T-02-11).
_kMaxInputSizeBytes: int = 100 * 1024  # 100 KB

# Maximum fallback chain iterations (T-02-14).
_kMaxFallbackIterations: int = 5


class RouterConfigError(Exception):
    """Raised when router rule configuration is invalid.

    Covers schema violations, duplicate priorities, and malformed rules.
    """


# ---------------------------------------------------------------------------
# RuleEngine
# ---------------------------------------------------------------------------


class RuleEngine:
    """Loads YAML rules and classifies queries via deterministic matching.

    Construct from a YAML file path or a YAML string.  Validation runs at
    construction time — a ``RouterConfigError`` is raised for any schema
    violation (missing fields, duplicate priorities, etc.).

    Args:
        rules_path: Path to a ``router_rules.yaml`` file on disk.
        rules_str: Inline YAML string with rule definitions (for testing).
            Mutually exclusive with *rules_path*.
        confidence_threshold: Minimum confidence before fallback chaining
            is triggered (default 0.5).

    Raises:
        RouterConfigError: If the rules YAML fails schema validation.
    """

    def __init__(
        self,
        rules_path: Optional[Path] = None,
        rules_str: Optional[str] = None,
        confidence_threshold: float = 0.5,
    ) -> None:
        self._confidence_threshold: float = confidence_threshold
        self._rules: List[Dict[str, Any]] = []
        self._default_specialist: str = "encyclopedic"

        if rules_path is not None and rules_str is not None:
            raise RouterConfigError(
                "Provide exactly one of rules_path or rules_str, not both"
            )

        if rules_str is not None:
            self._load_from_string(rules_str)
        elif rules_path is not None:
            self._load_from_file(rules_path)
        else:
            # Try default path relative to project root
            default_path = Path("config") / "router_rules.yaml"
            self._load_from_file(default_path)

    # -- public API ----------------------------------------------------------

    def classify(self, query: str) -> ExecutionPlan:
        """Classify *query* and return an ExecutionPlan.

        The classification pipeline:
        1. Input size validation (100 KB limit)
        2. Run all non-default rules in priority order (lower = higher pri)
        3. First match with confidence >= threshold → return immediately
        4. If no match passes threshold, run fallback chain over remaining
           matches (bounded to 5 iterations)
        5. If fallback exhausted or nothing matched, return default specialist

        Args:
            query: The raw input text to classify.

        Returns:
            ExecutionPlan with the selected specialist and routing metadata.

        Raises:
            RouterConfigError: If the input exceeds the 100 KB size limit.
        """
        self._validate_input_size(query)

        # Collect all matches sorted by priority (ascending = higher priority)
        matches = self._collect_matches(query)

        if not matches:
            return ExecutionPlan(
                primary_specialist=self._default_specialist,
                execution_mode="local_lora",
                confidence=0.0,
                matched_rules=[],
            )

        # First-match with confidence above threshold
        for idx, (rule, confidence) in enumerate(matches):
            if confidence >= self._confidence_threshold:
                return ExecutionPlan(
                    primary_specialist=rule["specialist"],
                    execution_mode=rule.get("execution_mode", "local_lora"),
                    confidence=confidence,
                    matched_rules=[rule["name"]],
                )

        # Fallback: try remaining matches in order, bounded
        fallback_chain: List[str] = []
        best_plan: Optional[ExecutionPlan] = None

        for iteration in range(min(len(matches), _kMaxFallbackIterations)):
            rule, confidence = matches[iteration]
            fallback_chain.append(rule["specialist"])

            if best_plan is None or confidence > best_plan.confidence:
                best_plan = ExecutionPlan(
                    primary_specialist=rule["specialist"],
                    execution_mode=rule.get("execution_mode", "local_lora"),
                    confidence=confidence,
                    matched_rules=[rule["name"]],
                    fallback_chain=list(fallback_chain),
                )

            if confidence >= self._confidence_threshold:
                break

        if best_plan is not None:
            return best_plan

        # Exhausted — return default
        return ExecutionPlan(
            primary_specialist=self._default_specialist,
            execution_mode="local_lora",
            confidence=0.0,
            matched_rules=[],
            fallback_chain=fallback_chain,
        )

    def reload(self, rules_str: Optional[str] = None, rules_path: Optional[Path] = None) -> None:
        """Reload rules from a new YAML source without reinstantiating.

        Useful for YAML-driven-rule tests that rewrite config and re-classify.
        """
        if rules_str is not None:
            self._load_from_string(rules_str)
        elif rules_path is not None:
            self._load_from_file(rules_path)
        else:
            raise RouterConfigError("reload requires rules_str or rules_path")

    # -- private: loading ----------------------------------------------------

    def _load_from_file(self, path: Path) -> None:
        if not path.exists():
            raise RouterConfigError(f"Rules file not found: {path}")
        raw = path.read_text(encoding="utf-8")
        self._load_from_yaml(yaml.safe_load(raw), source=str(path))

    def _load_from_string(self, yaml_str: str) -> None:
        self._load_from_yaml(yaml.safe_load(yaml_str), source="<string>")

    def _load_from_yaml(self, data: Any, source: str) -> None:
        if not isinstance(data, dict):
            raise RouterConfigError(f"Router rules YAML must be a dict, got {type(data).__name__}")

        rules = data.get("rules")
        if not isinstance(rules, list):
            raise RouterConfigError(f"'rules' must be a list in {source}")

        normalized: List[Dict[str, Any]] = []
        for idx, rule in enumerate(rules):
            if not isinstance(rule, dict):
                raise RouterConfigError(f"rule[{idx}] must be a dict, got {type(rule).__name__}")
            self._validate_rule(rule, idx, source)
            normalized.append(rule)

        self._validate_priorities(normalized)
        self._rules = normalized

        # Extract default specialist from is_default rule if present
        for rule in normalized:
            if rule.get("is_default"):
                self._default_specialist = rule["specialist"]
                break

        logger.info(
            "Loaded %d router rules from %s (default: %s)",
            len(normalized), source, self._default_specialist,
        )

    @staticmethod
    def _validate_rule(rule: Dict[str, Any], idx: int, source: str) -> None:
        required = ["name", "priority", "type", "specialist", "execution_mode"]
        for field in required:
            if field not in rule:
                raise RouterConfigError(
                    f"rule[{idx}] in {source}: missing required field '{field}'"
                )

        valid_types = ("keyword", "regex", "syntax_density")
        if rule.get("type") not in valid_types:
            raise RouterConfigError(
                f"rule[{idx}] in {source}: 'type' must be one of {valid_types}, "
                f"got '{rule['type']}'"
            )

        if not isinstance(rule["priority"], int):
            raise RouterConfigError(
                f"rule[{idx}] in {source}: 'priority' must be an integer"
            )

        if rule.get("type") == "keyword" or rule.get("type") == "regex":
            if "patterns" not in rule or not isinstance(rule["patterns"], list):
                raise RouterConfigError(
                    f"rule[{idx}] in {source}: '{rule['type']}' rules require "
                    f"a 'patterns' list"
                )

        if rule.get("type") == "syntax_density":
            if "threshold" not in rule:
                raise RouterConfigError(
                    f"rule[{idx}] in {source}: 'syntax_density' rules require "
                    f"a 'threshold' field"
                )
            if not isinstance(rule["threshold"], (int, float)):
                raise RouterConfigError(
                    f"rule[{idx}] in {source}: 'threshold' must be a number"
                )

    @staticmethod
    def _validate_priorities(rules: List[Dict[str, Any]]) -> None:
        """Ensure no duplicate priorities across non-default rules (T-02-12)."""
        seen: Dict[int, str] = {}
        for rule in rules:
            if rule.get("is_default"):
                continue
            pri = rule["priority"]
            if pri in seen:
                raise RouterConfigError(
                    f"Duplicate priority {pri}: rule '{rule['name']}' and "
                    f"'{seen[pri]}' both use priority {pri}"
                )
            seen[pri] = rule["name"]

    # -- private: matching ---------------------------------------------------

    def _collect_matches(self, query: str) -> List:
        """Return list of (rule, confidence) sorted by priority ascending.

        Default rules (is_default=True) are excluded.
        """
        scored: List = []

        for rule in self._rules:
            if rule.get("is_default"):
                continue

            confidence = self._compute_confidence(rule, query)
            if confidence > 0.0:
                scored.append((rule, confidence))

        scored.sort(key=lambda item: item[0]["priority"])
        return scored

    def _compute_confidence(self, rule: Dict[str, Any], query: str) -> float:
        rule_type = rule["type"]

        if rule_type == "keyword":
            return self._keyword_confidence(rule, query)
        elif rule_type == "regex":
            return self._regex_confidence(rule, query)
        elif rule_type == "syntax_density":
            return self._syntax_density_confidence(rule, query)
        else:
            return 0.0

    @staticmethod
    def _keyword_confidence(rule: Dict[str, Any], query: str) -> float:
        patterns = rule.get("patterns", [])
        if not patterns:
            return 0.0

        query_lower = query.lower()
        matched = sum(1 for p in patterns if p.lower() in query_lower)

        if matched == 0:
            return 0.0

        return min(matched / len(patterns), 1.0)

    @staticmethod
    def _regex_confidence(rule: Dict[str, Any], query: str) -> float:
        patterns = rule.get("patterns", [])
        if not patterns:
            return 0.0

        for pattern in patterns:
            try:
                if re.search(pattern, query, re.IGNORECASE):
                    return 1.0
            except re.error as exc:
                logger.warning(
                    "Invalid regex pattern '%s' in rule '%s': %s",
                    pattern, rule["name"], exc,
                )
                continue

        return 0.0

    @staticmethod
    def _syntax_density_confidence(rule: Dict[str, Any], query: str) -> float:
        threshold = rule.get("threshold", 0.3)
        category = rule.get("category", "numeric")

        if category == "numeric":
            # Count tokens that are purely numeric
            tokens = query.split()
            if not tokens:
                return 0.0

            numeric_count = 0
            for token in tokens:
                # Strip surrounding punctuation for token classification
                stripped = token.strip(".,;:!?()[]{}\"'")
                if stripped and _is_numeric_token(stripped):
                    numeric_count += 1

            density = numeric_count / len(tokens)
            if density < threshold:
                return 0.0

            return min(density / threshold, 1.0)

        return 0.0

    # -- private: validation ---------------------------------------------------

    @staticmethod
    def _validate_input_size(query: str) -> None:
        if len(query.encode("utf-8")) > _kMaxInputSizeBytes:
            raise RouterConfigError(
                f"Input size {len(query.encode('utf-8'))} bytes exceeds "
                f"maximum {_kMaxInputSizeBytes} bytes (100 KB)"
            )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_numeric_token(token: str) -> bool:
    """Return True if *token* is purely numeric (integer or float format)."""
    if not token:
        return False
    # Handle optional leading sign
    if token[0] in ("+", "-"):
        token = token[1:]
    if not token:
        return False
    # Count dots — at most one for float format
    return token.replace(".", "", 1).isdigit()
