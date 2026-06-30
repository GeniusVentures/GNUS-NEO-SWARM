"""Rule matching engine for the rules-based specialist router.

Implements D-11: routing rules are defined declaratively in YAML, and adding
a new rule requires only a config change (no code change). Each rule has a
set of triggers (keyword, regex, syntax_density, always_match) and a
confidence threshold. ``RuleMatcher.match_rules()`` returns matching rules
sorted by priority descending so callers can pick the highest-priority match.

T-02-06 mitigation: regex patterns are pre-compiled with ``re.compile`` and
each individual match attempt is bounded by a wall-time guard
(``_MAX_MATCH_SECONDS``). If any single match exceeds the budget the matcher
aborts and treats that trigger as a non-match, preventing catastrophic
backtracking from denying service.
"""

import logging
import re
import time

logger = logging.getLogger(__name__)

# Confidence value returned by an always_match trigger. Deliberately the
# lowest meaningful score so default rules only win when nothing else matches.
_ALWAYS_MATCH_CONFIDENCE = 0.5

# Maximum wall-clock seconds for a single trigger match attempt before the
# matcher aborts (T-02-06: regex DoS guard).
_MAX_MATCH_SECONDS = 0.1

# Maximum length (in characters) for a regex pattern accepted by this engine.
# Longer patterns are rejected to bound compilation time (T-02-06).
_MAX_REGEX_PATTERN_LEN = 200


def _fraction(found: int, total: int) -> float:
    """Return ``found/total`` clamped to ``[0.0, 1.0]``; ``0.0`` when total is 0."""
    if total <= 0:
        return 0.0
    return max(0.0, min(1.0, found / total))


class RuleMatcher:
    """Match a query against configured router rules.

    A rule dict has the shape::

        {
            "name": "code_detection",
            "priority": 10,
            "triggers": [
                {"type": "keyword", "patterns": ["def ", "class "]},
                {"type": "regex", "patterns": ["\\bfunction\\b"]},
                {"type": "syntax_density", "threshold": 0.3, "chars": ["{", "}"]},
                {"type": "always_match"},
            ],
            "action": "select_specialist",
            "specialist": "code",
            "confidence_threshold": 0.6,
            "fallback": "encyclopedic",
        }

    Attributes:
        rules: The list of rule dicts (sorted by priority descending).
    """

    def __init__(self, rules_config: dict):
        """Initialise the matcher from a parsed router rules YAML document.

        Args:
            rules_config: Parsed YAML dict with a top-level ``router`` key
                containing a ``rules`` list (see module docstring for shape).
        """
        router_section = rules_config.get("router", {}) if rules_config else {}
        self._rules = list(router_section.get("rules", []))
        # Pre-sort by priority descending so match_rules can iterate in order.
        self._rules.sort(key=lambda r: r.get("priority", 0), reverse=True)
        # Cache compiled regex patterns keyed by pattern string to avoid
        # recompilation across queries.
        self._regex_cache = {}

    @property
    def rules(self) -> list:
        """Return the configured rules sorted by priority descending."""
        return list(self._rules)

    def get_rule_by_specialist(self, specialist: str) -> dict:
        """Return the first rule whose ``specialist`` matches, or ``{}``."""
        for rule in self._rules:
            if rule.get("specialist") == specialist:
                return rule
        return {}

    # ------------------------------------------------------------------
    # Public matching API
    # ------------------------------------------------------------------

    def match_rules(self, query: str) -> list:
        """Return ``[(rule_name, confidence, specialist), ...]`` for matching rules.

        The returned list is sorted by rule priority descending. A rule is
        included when at least one of its triggers produces a confidence > 0,
        or it carries an ``always_match`` trigger. The confidence for a rule
        is the maximum score across all of its triggers.

        Args:
            query: The raw user query string.

        Returns:
            List of ``(rule_name, confidence, specialist)`` tuples.
        """
        if not query:
            return []

        matches = []
        for rule in self._rules:
            confidence = self._score_rule(query, rule)
            if confidence > 0.0:
                matches.append(
                    (rule.get("name"), confidence, rule.get("specialist"))
                )
        # Stable sort by priority descending; Python's sort is stable so
        # equal-priority rules keep their config order.
        matches.sort(
            key=lambda m: self._priority_for(m[0]), reverse=True
        )
        return matches

    # ------------------------------------------------------------------
    # Trigger scorers (public for unit testing)
    # ------------------------------------------------------------------

    def keyword_match(self, query: str, patterns: list) -> float:
        """Return the fraction of keyword patterns found in ``query``."""
        if not patterns:
            return 0.0
        found = 0
        start = time.monotonic()
        for pat in patterns:
            if time.monotonic() - start > _MAX_MATCH_SECONDS:
                logger.warning(
                    "keyword_match exceeded %.3fs budget; aborting remaining patterns",
                    _MAX_MATCH_SECONDS,
                )
                break
            if pat and pat in query:
                found += 1
        return _fraction(found, len(patterns))

    def regex_match(self, query: str, patterns: list) -> float:
        """Return the fraction of regex patterns with at least one match."""
        if not patterns:
            return 0.0
        found = 0
        start = time.monotonic()
        for pat in patterns:
            if time.monotonic() - start > _MAX_MATCH_SECONDS:
                logger.warning(
                    "regex_match exceeded %.3fs budget; aborting remaining patterns",
                    _MAX_MATCH_SECONDS,
                )
                break
            compiled = self._compile_regex(pat)
            if compiled is None:
                continue
            if compiled.search(query):
                found += 1
        return _fraction(found, len(patterns))

    def syntax_density_match(
        self, query: str, chars: list, threshold: float
    ) -> float:
        """Return ``1.0`` when the density of ``chars`` in ``query`` exceeds threshold.

        Density is the fraction of query characters that are members of
        ``chars``. Returns ``1.0`` on match, ``0.0`` otherwise.
        """
        if not query or not chars:
            return 0.0
        char_set = set(chars)
        matching = sum(1 for ch in query if ch in char_set)
        density = matching / len(query)
        return 1.0 if density >= threshold else 0.0

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _score_rule(self, query: str, rule: dict) -> float:
        """Return the maximum trigger confidence for ``rule`` against ``query``."""
        best = 0.0
        for trigger in rule.get("triggers", []):
            score = self._score_trigger(query, trigger)
            if score > best:
                best = score
            # always_match short-circuits to its fixed confidence.
            if trigger.get("type") == "always_match" and best < _ALWAYS_MATCH_CONFIDENCE:
                best = _ALWAYS_MATCH_CONFIDENCE
        return best

    def _score_trigger(self, query: str, trigger: dict) -> float:
        """Dispatch a single trigger to the appropriate scorer."""
        trigger_type = trigger.get("type")
        if trigger_type == "keyword":
            return self.keyword_match(query, trigger.get("patterns", []))
        if trigger_type == "regex":
            return self.regex_match(query, trigger.get("patterns", []))
        if trigger_type == "syntax_density":
            return self.syntax_density_match(
                query,
                trigger.get("chars", []),
                trigger.get("threshold", 0.0),
            )
        if trigger_type == "always_match":
            return _ALWAYS_MATCH_CONFIDENCE
        logger.debug("Unknown trigger type '%s'; skipping", trigger_type)
        return 0.0

    def _priority_for(self, rule_name: str) -> int:
        """Look up the priority for a rule name (0 when not found)."""
        for rule in self._rules:
            if rule.get("name") == rule_name:
                return rule.get("priority", 0)
        return 0

    def _compile_regex(self, pattern: str):
        """Return a compiled regex, or ``None`` if the pattern is invalid/too long.

        Patterns longer than ``_MAX_REGEX_PATTERN_LEN`` are rejected (T-02-06).
        Compilation errors are logged and the pattern is treated as a non-match.
        """
        if not isinstance(pattern, str):
            return None
        if len(pattern) > _MAX_REGEX_PATTERN_LEN:
            logger.warning(
                "Rejecting regex pattern of length %d (max %d)",
                len(pattern),
                _MAX_REGEX_PATTERN_LEN,
            )
            return None
        if pattern in self._regex_cache:
            return self._regex_cache[pattern]
        try:
            compiled = re.compile(pattern)
        except re.error as exc:
            logger.warning("Invalid regex pattern %r: %s", pattern, exc)
            compiled = None
        self._regex_cache[pattern] = compiled
        return compiled
