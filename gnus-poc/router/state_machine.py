"""GQHSM-compatible JSON state machine runtime for the router classification pipeline.

Consumes a GQHSM-compatible JSON state machine definition (derived from the
GQHSM XML format used in ``Valve.xml`` and ``Air.xml``) and builds a
``transitions``-based runtime.  The JSON format is the compatibility
contract — when the C++ parent integrates GQHSM directly, the same JSON
feeds into it.

Usage::

    sm = RouterStateMachine.load_definition("config/router_state_machine.json")
    sm.trigger("keyword_hit", specialist="code", confidence=0.85)
    print(sm.state)  # 'select_specialist'

Dependency on ``transitions`` is deferred — the module loads and works
without it, but ``RouterStateMachine`` raises ``ImportError`` with a
helpful message when ``transitions`` is not installed.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# GQHSM JSON Schema (derived from GQHSM XML: Valve.xml, Air.xml)
# ---------------------------------------------------------------------------

GQHSM_JSON_SCHEMA: Dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "GQHSM State Machine Definition",
    "type": "object",
    "required": ["stateMachineInfo", "states", "transitions"],
    "properties": {
        "stateMachineInfo": {
            "type": "object",
            "required": ["name"],
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Machine identifier (e.g., 'router_classifier')",
                },
                "version": {"type": "integer", "default": 1},
                "description": {"type": "string"},
                "namespace": {"type": "string", "default": "gnus.router"},
            },
        },
        "states": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name"],
                "properties": {
                    "name": {"type": "string"},
                    "isStartState": {"type": "boolean", "default": False},
                    "entryAction": {
                        "type": "string",
                        "description": "Callback name executed on state entry",
                    },
                    "exitAction": {
                        "type": "string",
                        "description": "Callback name executed on state exit",
                    },
                    "children": {
                        "type": "array",
                        "items": {"$ref": "#/properties/states/items"},
                        "description": "Hierarchical child states (mirrors GQHSM nested StateGlyph)",
                    },
                    "metadata": {
                        "type": "object",
                        "description": "Arbitrary key-value annotations",
                    },
                },
            },
        },
        "transitions": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["eventSignal", "source", "target"],
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Optional label for debugging",
                    },
                    "eventSignal": {
                        "type": "string",
                        "description": "Trigger name (e.g., 'keyword_match', 'no_match')",
                    },
                    "eventSource": {
                        "type": "string",
                        "description": "Port/source identifier (mirrors GQHSM EventSource)",
                    },
                    "guardCondition": {
                        "type": "string",
                        "description": "Guard callback name or inline expression",
                    },
                    "action": {
                        "type": "string",
                        "description": "Action callback name executed on transition",
                    },
                    "evaluationOrderPriority": {
                        "type": "integer",
                        "default": 0,
                        "description": "Lower values evaluated first",
                    },
                    "transitionType": {
                        "type": "string",
                        "enum": ["Normal", "Internal"],
                        "default": "Normal",
                    },
                    "source": {"type": "string", "description": "Source state name"},
                    "target": {"type": "string", "description": "Target state name"},
                },
            },
        },
    },
}


def _deferred_import_transitions():
    """Deferred import of the ``transitions`` library.

    Returns the ``Machine`` and ``State`` classes if installed, or raises
    ``ImportError`` with installation instructions.
    """
    try:
        from transitions import Machine, State  # type: ignore[import-untyped]

        return Machine, State
    except ImportError:
        raise ImportError(
            "The 'transitions' library is required for the GQHSM-compatible "
            "state machine runtime. Install it with:\n"
            "    pip install transitions\n"
            "See: https://github.com/pytransitions/transitions"
        )


# ---------------------------------------------------------------------------
# RouterStateMachine
# ---------------------------------------------------------------------------


class RouterStateMachine:
    """GQHSM-compatible state machine runtime wrapping ``transitions``.

    Consumes a JSON state machine definition (matching
    ``GQHSM_JSON_SCHEMA``) and builds a ``transitions.Machine`` from it.
    Rule handler callbacks are registered via *rule_handlers*, mapping
    callback name strings from the JSON definition to Python callables.

    The machine is built lazily — the constructor validates the JSON
    structure but defers ``transitions`` instantiation until
    :meth:`trigger` is first called.  This allows the module to be
    imported even when ``transitions`` is not yet installed.

    Args:
        sm_definition: GQHSM-compatible state machine JSON as a dict.
        rule_handlers: Optional dict mapping callback names (e.g.,
            ``"run_keyword_triggers"``) to Python callables.  Only needed
            if the JSON definition references entry/exit/guard/action
            callbacks.

    Raises:
        ValueError: If *sm_definition* does not contain the required
            ``stateMachineInfo``, ``states``, and ``transitions`` keys.
    """

    def __init__(
        self,
        sm_definition: Dict[str, Any],
        rule_handlers: Optional[Dict[str, Callable[..., Any]]] = None,
    ) -> None:
        self._definition: Dict[str, Any] = sm_definition
        self._handlers: Dict[str, Callable[..., Any]] = rule_handlers or {}
        self._machine: Any = None  # transitions.Machine, built lazily

        self._validate_definition()

    # -- public API ----------------------------------------------------------

    @classmethod
    def load_definition(
        cls,
        json_path: Path,
        rule_handlers: Optional[Dict[str, Callable[..., Any]]] = None,
    ) -> RouterStateMachine:
        """Load a GQHSM-compatible JSON definition from *json_path*.

        Args:
            json_path: Path to a JSON state machine definition file.
            rule_handlers: Optional callback name → callable mapping.

        Returns:
            A ``RouterStateMachine`` ready to trigger events.

        Raises:
            FileNotFoundError: If *json_path* does not exist.
            json.JSONDecodeError: If the file is not valid JSON.
        """
        if not json_path.exists():
            raise FileNotFoundError(f"State machine definition not found: {json_path}")

        raw = json_path.read_text(encoding="utf-8")
        definition = json.loads(raw)
        logger.info(
            "Loaded GQHSM state machine '%s' from %s",
            definition.get("stateMachineInfo", {}).get("name", "unnamed"),
            json_path,
        )
        return cls(definition, rule_handlers)

    def trigger(self, event_name: str, *args: Any, **kwargs: Any) -> None:
        """Dispatch an event signal to the state machine.

        Building the ``transitions.Machine`` is deferred until the first
        trigger call (lazy initialization).

        Args:
            event_name: The event signal name matching a transition's
                ``eventSignal`` in the JSON definition.
            *args: Positional arguments passed to guard/action callbacks.
            **kwargs: Keyword arguments passed to guard/action callbacks.

        Raises:
            ImportError: If ``transitions`` is not installed.
            AttributeError: If *event_name* does not match any trigger.
        """
        if self._machine is None:
            self._build()
        # The transitions library appends _ to reserved names like 'trigger'
        # so we use the model attribute directly.
        machine_model = self._machine.model
        trigger_func = getattr(machine_model, event_name, None)
        if trigger_func is None:
            raise AttributeError(
                f"No trigger '{event_name}' on state machine "
                f"'{self._definition.get('stateMachineInfo', {}).get('name', 'unnamed')}'"
            )
        trigger_func(*args, **kwargs)

    @property
    def state(self) -> str:
        """Return the current state name (from the initial state if not yet built)."""
        if self._machine is not None:
            return str(self._machine.model.state)
        return self._find_start_state()

    @property
    def is_built(self) -> bool:
        """True if the ``transitions`` machine has been constructed."""
        return self._machine is not None

    # -- private: lazy build -------------------------------------------------

    def _build(self) -> None:
        """Build the ``transitions.Machine`` from the JSON definition."""
        Machine, State = _deferred_import_transitions()

        states: List[Any] = []
        transitions_list: List[Dict[str, Any]] = []

        # Build states from JSON definition
        for state_def in self._definition["states"]:
            callbacks: Dict[str, Optional[Callable[..., Any]]] = {}
            if state_def.get("entryAction"):
                callbacks["on_enter"] = self._handlers.get(state_def["entryAction"])
            if state_def.get("exitAction"):
                callbacks["on_exit"] = self._handlers.get(state_def["exitAction"])

            # Handle hierarchical (nested) states
            if state_def.get("children"):
                sub_states = [
                    State(
                        name=child["name"],
                        on_enter=self._handlers.get(child.get("entryAction")),
                        on_exit=self._handlers.get(child.get("exitAction")),
                    )
                    for child in state_def["children"]
                ]
                states.append(State(name=state_def["name"], children=sub_states, **callbacks))
            else:
                states.append(State(name=state_def["name"], **callbacks))

        # Build transitions from JSON definition
        for trans in self._definition["transitions"]:
            conditions: List[Callable[..., bool]] = []
            if trans.get("guardCondition"):
                guard = self._handlers.get(trans["guardCondition"])
                if guard is not None:
                    conditions.append(guard)

            transitions_list.append(
                {
                    "trigger": trans["eventSignal"],
                    "source": trans["source"],
                    "dest": trans["target"],
                    "conditions": conditions,
                    "after": self._handlers.get(trans.get("action")),
                }
            )

        class _Model:
            """Minimal model for transitions library (stateless machine)."""
            pass

        self._machine = Machine(
            model=_Model(),
            states=states,
            transitions=transitions_list,
            initial=self._find_start_state(),
            auto_transitions=False,
        )
        logger.debug(
            "Built RouterStateMachine with %d states and %d transitions",
            len(states), len(transitions_list),
        )

    # -- private: helpers ----------------------------------------------------

    def _validate_definition(self) -> None:
        if not isinstance(self._definition, dict):
            raise ValueError("State machine definition must be a dict")

        required = ["stateMachineInfo", "states", "transitions"]
        for key in required:
            if key not in self._definition:
                raise ValueError(f"Missing required key '{key}' in state machine definition")

        info = self._definition["stateMachineInfo"]
        if not isinstance(info, dict) or "name" not in info:
            raise ValueError("stateMachineInfo must contain 'name'")

        if not isinstance(self._definition["states"], list):
            raise ValueError("'states' must be a list")
        if not isinstance(self._definition["transitions"], list):
            raise ValueError("'transitions' must be a list")

        # Verify all transition sources/targets reference defined states
        state_names = {s["name"] for s in self._definition["states"]}
        for t_idx, trans in enumerate(self._definition["transitions"]):
            src = trans.get("source")
            tgt = trans.get("target")
            if src not in state_names:
                raise ValueError(
                    f"transition[{t_idx}] source '{src}' is not a defined state"
                )
            if tgt not in state_names:
                raise ValueError(
                    f"transition[{t_idx}] target '{tgt}' is not a defined state"
                )

    def _find_start_state(self) -> str:
        """Return the name of the start state from the JSON definition."""
        for state_def in self._definition["states"]:
            if state_def.get("isStartState"):
                return state_def["name"]
        # Fallback: first state
        if self._definition["states"]:
            return self._definition["states"][0]["name"]
        raise ValueError("No states defined in state machine definition")


# ---------------------------------------------------------------------------
# Default router classification state machine (GQHSM-compatible)
# ---------------------------------------------------------------------------

_ROUTER_CLASSIFIER_DEFINITION: Dict[str, Any] = {
    "stateMachineInfo": {
        "name": "router_classifier",
        "version": 1,
        "description": "Rules-based query classification for specialist routing",
        "namespace": "gnus.router",
    },
    "states": [
        {
            "name": "pre_classify",
            "isStartState": True,
            "entryAction": "log_entry",
            "metadata": {"description": "Initial classification entry point"},
        },
        {
            "name": "keyword_match",
            "entryAction": "run_keyword_triggers",
            "metadata": {"description": "Evaluate keyword-based rules"},
        },
        {
            "name": "regex_match",
            "entryAction": "run_regex_triggers",
            "metadata": {"description": "Evaluate regex pattern rules"},
        },
        {
            "name": "syntax_density",
            "entryAction": "run_syntax_density_triggers",
            "metadata": {"description": "Evaluate syntax density heuristics"},
        },
        {
            "name": "select_specialist",
            "entryAction": "emit_specialist_selection",
            "metadata": {"description": "Terminal: specialist selected"},
        },
        {
            "name": "fallback_chain",
            "entryAction": "run_fallback_chain",
            "metadata": {
                "description": "Try next-best match when confidence below threshold"
            },
        },
        {
            "name": "no_match",
            "entryAction": "emit_default_specialist",
            "metadata": {"description": "Terminal: no match, route to default"},
        },
    ],
    "transitions": [
        {
            "name": "t_begin",
            "eventSignal": "begin_classification",
            "source": "pre_classify",
            "target": "keyword_match",
            "evaluationOrderPriority": 0,
        },
        {
            "name": "t_kw_hit",
            "eventSignal": "keyword_hit",
            "source": "keyword_match",
            "target": "select_specialist",
            "guardCondition": "confidence_above_threshold",
            "action": "set_selected_specialist",
            "evaluationOrderPriority": 10,
        },
        {
            "name": "t_kw_miss",
            "eventSignal": "keyword_miss",
            "source": "keyword_match",
            "target": "regex_match",
            "evaluationOrderPriority": 20,
        },
        {
            "name": "t_regex_hit",
            "eventSignal": "regex_hit",
            "source": "regex_match",
            "target": "select_specialist",
            "guardCondition": "confidence_above_threshold",
            "action": "set_selected_specialist",
            "evaluationOrderPriority": 10,
        },
        {
            "name": "t_regex_miss",
            "eventSignal": "regex_miss",
            "source": "regex_match",
            "target": "syntax_density",
            "evaluationOrderPriority": 20,
        },
        {
            "name": "t_syntax_hit",
            "eventSignal": "syntax_hit",
            "source": "syntax_density",
            "target": "select_specialist",
            "guardCondition": "confidence_above_threshold",
            "action": "set_selected_specialist",
            "evaluationOrderPriority": 10,
        },
        {
            "name": "t_syntax_miss",
            "eventSignal": "syntax_miss",
            "source": "syntax_density",
            "target": "no_match",
            "evaluationOrderPriority": 20,
        },
        {
            "name": "t_low_confidence",
            "eventSignal": "confidence_below_threshold",
            "source": "select_specialist",
            "target": "fallback_chain",
            "guardCondition": "has_fallback",
            "action": "try_next_best_match",
        },
        {
            "name": "t_fallback_resolved",
            "eventSignal": "fallback_hit",
            "source": "fallback_chain",
            "target": "select_specialist",
            "action": "set_selected_specialist",
        },
        {
            "name": "t_fallback_exhausted",
            "eventSignal": "fallback_miss",
            "source": "fallback_chain",
            "target": "no_match",
        },
    ],
}


def create_router_state_machine(
    rule_handlers: Optional[Dict[str, Callable[..., Any]]] = None,
) -> RouterStateMachine:
    """Create a pre-configured router classification state machine.

    Uses the built-in ``_ROUTER_CLASSIFIER_DEFINITION`` (7 states,
    10 transitions) matching the GQHSM-compatible JSON schema.

    Args:
        rule_handlers: Optional dict mapping callback names to callables.

    Returns:
        A ``RouterStateMachine`` configured for query classification.
    """
    return RouterStateMachine(_ROUTER_CLASSIFIER_DEFINITION, rule_handlers)
