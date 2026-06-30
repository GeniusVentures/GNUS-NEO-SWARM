"""GQHSM-compatible JSON schema and validation for router rules.

Defines the JSON shape that the Python ``transitions`` state machine and the
future C++ GQHSM integration both consume (D-10: GQHSM conceptual model;
D-13: JSON is the compatibility contract).

T-02-07 mitigation: ``validate_router_rules()`` performs structural validation
at load time so malformed configuration produces a clear, structured error
instead of silent misclassification. It returns a result dict (never raises
on invalid input) to keep the validation hot path exception-free.
"""

import logging

logger = logging.getLogger(__name__)

# Required top-level keys of a GQHSM-compatible router rules document.
_REQUIRED_TOP_KEYS = ("states", "transitions", "initial")

# Required keys inside each element of the ``states`` array.
_REQUIRED_STATE_KEYS = ("name",)

# Required keys inside each element of the ``transitions`` array.
_REQUIRED_TRANSITION_KEYS = ("trigger", "source", "dest")

# Optional keys on a transition entry that, if present, must be lists of str.
_OPTIONAL_TRANSITION_LIST_KEYS = ("conditions", "unless", "actions")

# GQHSM-compatible JSON schema descriptor. Kept as a plain dict so the
# validation logic can be reused without a hard dependency on ``jsonschema``.
GQHSM_ROUTER_SCHEMA = {
    "type": "object",
    "required": list(_REQUIRED_TOP_KEYS),
    "properties": {
        "states": {
            "type": "array",
            "items": {
                "type": "object",
                "required": list(_REQUIRED_STATE_KEYS),
                "properties": {
                    "name": {"type": "string"},
                },
            },
        },
        "transitions": {
            "type": "array",
            "items": {
                "type": "object",
                "required": list(_REQUIRED_TRANSITION_KEYS),
                "properties": {
                    "trigger": {"type": "string"},
                    "source": {"type": "string"},
                    "dest": {"type": "string"},
                    "conditions": {"type": "array", "items": {"type": "string"}},
                    "unless": {"type": "array", "items": {"type": "string"}},
                    "actions": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
        "initial": {"type": "string"},
    },
}


def validate_router_rules(rules_config: dict) -> dict:
    """Validate a GQHSM-compatible router rules document.

    Performs manual structural validation following the
    ``MetricStore._validate_stats_dict`` pattern. Validation is exception-free
    on bad input: a structured ``{"valid": bool, "errors": [str]}`` result is
    always returned.

    Args:
        rules_config: Parsed router rules document expected to conform to
            ``GQHSM_ROUTER_SCHEMA``.

    Returns:
        Dict with keys ``valid`` (bool) and ``errors`` (list[str]). When
        ``valid`` is ``True``, ``errors`` is an empty list.
    """
    errors = []

    if not isinstance(rules_config, dict):
        return {"valid": False, "errors": ["router rules must be a JSON object"]}

    # Top-level required keys.
    for key in _REQUIRED_TOP_KEYS:
        if key not in rules_config:
            errors.append(f"Missing required top-level key '{key}'")

    if errors:
        return {"valid": False, "errors": errors}

    # states: list of {"name": str}.
    states = rules_config.get("states")
    state_names = set()
    if not isinstance(states, list):
        errors.append("'states' must be an array")
    else:
        for idx, state in enumerate(states):
            if not isinstance(state, dict):
                errors.append(f"states[{idx}] must be an object")
                continue
            for key in _REQUIRED_STATE_KEYS:
                if key not in state:
                    errors.append(f"states[{idx}] missing required key '{key}'")
            name = state.get("name")
            if not isinstance(name, str):
                errors.append(f"states[{idx}].name must be a string")
            else:
                state_names.add(name)

    # transitions: list of {trigger, source, dest, [conditions], [unless], [actions]}.
    transitions = rules_config.get("transitions")
    if not isinstance(transitions, list):
        errors.append("'transitions' must be an array")
    else:
        for idx, trans in enumerate(transitions):
            if not isinstance(trans, dict):
                errors.append(f"transitions[{idx}] must be an object")
                continue
            for key in _REQUIRED_TRANSITION_KEYS:
                if key not in trans:
                    errors.append(
                        f"transitions[{idx}] missing required key '{key}'"
                    )
            for key in _REQUIRED_TRANSITION_KEYS:
                if key in trans and not isinstance(trans[key], str):
                    errors.append(f"transitions[{idx}].{key} must be a string")
            for key in _OPTIONAL_TRANSITION_LIST_KEYS:
                if key in trans and not isinstance(trans[key], list):
                    errors.append(f"transitions[{idx}].{key} must be an array")
                elif key in trans:
                    for item in trans[key]:
                        if not isinstance(item, str):
                            errors.append(
                                f"transitions[{idx}].{key} entries must be strings"
                            )
                            break

    # initial: must be a known state name.
    initial = rules_config.get("initial")
    if not isinstance(initial, str):
        errors.append("'initial' must be a string")
    elif isinstance(states, list) and initial not in state_names:
        errors.append(
            f"'initial' ('{initial}') must match a declared state name"
        )

    return {"valid": not errors, "errors": errors}
