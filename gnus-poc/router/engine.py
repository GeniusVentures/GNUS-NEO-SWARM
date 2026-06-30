"""GQHSM-compatible state machine runtime for the rules-based router.

Implements D-09 (Python-native state machine via the ``transitions`` library)
and D-10 (GQHSM conceptual model: states, transitions, triggers, guards,
actions). The machine consumes a GQHSM-compatible JSON document and walks
through classification stages::

    pre_classify -> keyword_match -> regex_match -> syntax_density
        -> select_specialist -> classified (final)
        -> fallback_chain -> classified (final)

Guard callbacks (conditions/unless) and action callbacks are methods on the
class, referenced by name from the JSON transition definitions. The runtime
exposes a ``run()`` method that drives the machine from the initial state to
``classified`` and returns the execution plan produced along the way.
"""

import logging

from transitions import Machine
from transitions.core import MachineError

logger = logging.getLogger(__name__)

# Final (terminal) state of the classification flow.
_FINAL_STATE = "classified"

# States used when no JSON config is supplied (the default GQHSM model).
_DEFAULT_STATES = [
    "pre_classify",
    "keyword_match",
    "regex_match",
    "syntax_density",
    "select_specialist",
    "fallback_chain",
    "classified",
]

# Confidence value below which a primary match is considered too weak and
# fallback chaining is attempted.
_DEFAULT_CONFIDENCE_THRESHOLD = 0.6


class RouterStateMachine:
    """GQHSM-compatible classification state machine.

    The machine is built from a JSON document with ``states`` and
    ``transitions`` arrays. Guard methods (referenced by ``conditions`` /
    ``unless`` in the JSON) and action methods (referenced by ``after`` /
    ``actions``) are implemented on this class.

    Attributes:
        confidence: Latest confidence score observed during a ``run()``.
        matched_rule: Name of the rule that produced the current selection.
        primary_specialist: Specialist selected by the latest classification.
        fallback_chain: Ordered list of specialists tried as fallbacks.
    """

    def __init__(self, rules_config: dict):
        """Build the state machine from a GQHSM-compatible JSON document.

        Args:
            rules_config: Dict with ``states``, ``transitions`` and
                ``initial`` keys. When ``None`` or empty, a default
                GQHSM-compatible model is used.
        """
        self._reset_run_state()

        states, transitions, initial = self._parse_config(rules_config)

        # Build the machine with auto_transitions disabled so only the
        # JSON-declared transitions exist (matches GQHSM semantics).
        self._machine = Machine(
            model=self,
            states=states,
            initial=initial,
            auto_transitions=False,
            send_event=False,
        )
        for trans in transitions:
            self._machine.add_transition(
                trigger=trans["trigger"],
                source=trans["source"],
                dest=trans["dest"],
                conditions=trans.get("conditions", []),
                unless=trans.get("unless", []),
                after=trans.get("actions", []),
            )

        logger.debug(
            "RouterStateMachine built with %d states, %d transitions, initial=%s",
            len(states),
            len(transitions),
            initial,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def current_state(self) -> str:
        """Return the current state name."""
        return self.state

    @property
    def classification_result(self) -> dict:
        """Return the execution plan assembled during the latest ``run()``."""
        return {
            "primary_specialist": self.primary_specialist,
            "execution_mode": self._execution_mode,
            "confidence": self.confidence,
            "matched_rule": self.matched_rule,
            "fallback_chain": list(self.fallback_chain),
        }

    def run(self, query: str, rule_matches: list) -> dict:
        """Walk the machine from its initial state to ``classified``.

        The ``transitions`` library fires triggers by name. This method
        simulates the GQHSM walk by attempting each declared trigger in order
        until the machine reaches the final state, accumulating the
        classification result as it goes.

        Args:
            query: The original query string (unused by the default guards
                but available for subclasses / custom actions).
            rule_matches: Output of ``RuleMatcher.match_rules`` — a list of
                ``(rule_name, confidence, specialist)`` tuples sorted by
                priority descending.

        Returns:
            The execution plan dict (see ``classification_result``).
        """
        self._reset_run_state()
        # Seed the run with the best match so guard callbacks have data.
        self._apply_matches(rule_matches)

        # Drive the machine forward. The GQHSM model declares named triggers;
        # we fire them in declaration order, relying on guards to gate which
        # transitions actually occur.
        triggers_to_fire = self._introspect_triggers()
        for trigger in triggers_to_fire:
            if self.state == _FINAL_STATE:
                break
            self._safe_trigger(trigger)

        # Guarantee a populated result even if the machine stalled.
        if self.primary_specialist is None and rule_matches:
            _, _, specialist = rule_matches[0]
            self.primary_specialist = specialist
            if self._execution_mode is None:
                self._execution_mode = "single"

        return self.classification_result

    # ------------------------------------------------------------------
    # Guard callbacks (referenced by transition "conditions" / "unless")
    # ------------------------------------------------------------------

    def confidence_above_threshold(self) -> bool:
        """Guard: True when the current best confidence meets the threshold."""
        return self.confidence >= self._confidence_threshold

    def has_fallback(self) -> bool:
        """Guard: True when a fallback specialist is configured."""
        return self._fallback_specialist is not None

    # ------------------------------------------------------------------
    # Action callbacks (referenced by transition "after" / "actions")
    # ------------------------------------------------------------------

    def set_specialist_from_match(self) -> None:
        """Action: record the primary specialist from the best match."""
        if self._best_match is not None:
            _, confidence, specialist = self._best_match
            self.primary_specialist = specialist
            self.confidence = confidence
            if self._execution_mode is None:
                self._execution_mode = "single"

    def log_classification(self) -> None:
        """Action: emit a debug log line for the current classification."""
        logger.debug(
            "RouterStateMachine classification: specialist=%s confidence=%.3f rule=%s",
            self.primary_specialist,
            self.confidence,
            self.matched_rule,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _parse_config(self, rules_config: dict):
        """Extract (states, transitions, initial) from a JSON config with defaults."""
        if not rules_config:
            return (
                list(_DEFAULT_STATES),
                self._default_transitions(),
                _DEFAULT_STATES[0],
            )

        raw_states = rules_config.get("states", [])
        states = [
            s["name"] if isinstance(s, dict) and "name" in s else s
            for s in raw_states
        ] or list(_DEFAULT_STATES)

        transitions = rules_config.get("transitions") or self._default_transitions()
        initial = rules_config.get("initial") or states[0]
        return states, transitions, initial

    @staticmethod
    def _default_transitions() -> list:
        """Return a minimal default transition set matching the GQHSM model."""
        return [
            {"trigger": "begin_keyword", "source": "pre_classify", "dest": "keyword_match"},
            {
                "trigger": "matched_keywords",
                "source": "keyword_match",
                "dest": "select_specialist",
                "conditions": ["confidence_above_threshold"],
                "actions": ["set_specialist_from_match"],
            },
            {"trigger": "no_match", "source": "keyword_match", "dest": "regex_match"},
            {
                "trigger": "matched_regex",
                "source": "regex_match",
                "dest": "select_specialist",
                "conditions": ["confidence_above_threshold"],
                "actions": ["set_specialist_from_match"],
            },
            {"trigger": "no_match", "source": "regex_match", "dest": "syntax_density"},
            {
                "trigger": "matched_density",
                "source": "syntax_density",
                "dest": "select_specialist",
                "conditions": ["confidence_above_threshold"],
                "actions": ["set_specialist_from_match"],
            },
            {"trigger": "no_match", "source": "syntax_density", "dest": "fallback_chain"},
            {
                "trigger": "fallback_selected",
                "source": "fallback_chain",
                "dest": "select_specialist",
                "actions": ["set_specialist_from_match"],
            },
            {
                "trigger": "finalise",
                "source": "select_specialist",
                "dest": "classified",
                "actions": ["log_classification"],
            },
            {
                "trigger": "finalise",
                "source": "fallback_chain",
                "dest": "classified",
                "actions": ["log_classification"],
            },
        ]

    def _ordered_triggers(self) -> list:
        """Return the configured triggers in declaration order (deprecated alias)."""
        return self._introspect_triggers()

    def _introspect_triggers(self) -> list:
        """Pull trigger names in declaration order from the machine's internal map."""
        events = getattr(self._machine, "events", {})
        names = list(events.keys())
        # Preserve declaration order as far as possible; drop internal triggers.
        return [n for n in names if not n.startswith("to_")]

    def _safe_trigger(self, trigger: str) -> None:
        """Fire ``trigger`` if a matching transition is valid in the current state."""
        if trigger is None:
            return
        method = getattr(self, trigger, None)
        if method is None:
            return
        try:
            method()
        except MachineError as exc:
            # Guards may reject the transition; that is expected flow.
            logger.debug("Trigger '%s' not taken from state '%s': %s", trigger, self.state, exc)

    def _apply_matches(self, rule_matches: list) -> None:
        """Seed run-time state from the matcher output."""
        if not rule_matches:
            return
        best = rule_matches[0]
        self._best_match = best
        self.matched_rule = best[0]
        self.confidence = best[1]
        self.primary_specialist = best[2]
        self._execution_mode = "single"
        # Record fallback candidates (lower-priority matches).
        for _, _, specialist in rule_matches[1:]:
            if specialist and specialist not in self.fallback_chain:
                self.fallback_chain.append(specialist)
        if self.fallback_chain:
            self._fallback_specialist = self.fallback_chain[0]

    def _reset_run_state(self) -> None:
        """Zero out all per-run mutable state."""
        self.confidence = 0.0
        self.matched_rule = None
        self.primary_specialist = None
        self.fallback_chain = []
        self._best_match = None
        self._fallback_specialist = None
        self._execution_mode = None
        self._confidence_threshold = _DEFAULT_CONFIDENCE_THRESHOLD
