"""Tests for the GQHSM-compatible router state machine runtime.

Covers ROUTE-02: the ``RouterStateMachine`` built from a GQHSM-compatible JSON
document. Verifies transitions, guards, state progression, the execution plan
shape, and the fallback-chain path.
"""

import pytest

from router.engine import RouterStateMachine, _DEFAULT_STATES


@pytest.fixture
def gqhsm_config():
    """Return a minimal valid GQHSM JSON config for the state machine."""
    return {
        "states": [{"name": s} for s in _DEFAULT_STATES],
        "transitions": [
            {
                "trigger": "begin_keyword",
                "source": "pre_classify",
                "dest": "keyword_match",
            },
            {
                "trigger": "matched_keywords",
                "source": "keyword_match",
                "dest": "select_specialist",
                "conditions": ["confidence_above_threshold"],
                "actions": ["set_specialist_from_match"],
            },
            {
                "trigger": "no_match",
                "source": "keyword_match",
                "dest": "fallback_chain",
            },
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
        ],
        "initial": "pre_classify",
    }


class TestRouterEngine:
    def test_transitions_from_json(self, gqhsm_config):
        """The machine builds its transitions from the GQHSM JSON config."""
        sm = RouterStateMachine(gqhsm_config)

        # The configured triggers must be registered as callable methods on
        # the model. Each trigger name from the JSON should be present.
        for expected_trigger in (
            "begin_keyword",
            "matched_keywords",
            "no_match",
            "fallback_selected",
            "finalise",
        ):
            assert hasattr(sm, expected_trigger), (
                f"trigger '{expected_trigger}' not registered on machine"
            )

    def test_state_progression(self, gqhsm_config):
        """A high-confidence match walks pre_classify -> ... -> classified."""
        sm = RouterStateMachine(gqhsm_config)

        # Seed a high-confidence match so the confidence guard passes.
        matches = [("code_detection", 0.9, "code")]
        sm.run("def foo(): pass", matches)

        assert sm.current_state == "classified"
        assert sm.primary_specialist == "code"

    def test_initial_state_is_pre_classify(self, gqhsm_config):
        """The machine starts at the configured initial state."""
        sm = RouterStateMachine(gqhsm_config)

        assert sm.current_state == "pre_classify"

    def test_guard_blocks_transition(self, gqhsm_config):
        """confidence_above_threshold guard blocks when confidence is low.

        With no matches, confidence stays at 0.0 which is below the default
        threshold (0.6), so the guarded transition into select_specialist is
        not taken and the machine relies on the fallback path instead.
        """
        sm = RouterStateMachine(gqhsm_config)

        # No matches -> confidence remains 0.0 -> guard returns False.
        assert sm.confidence_above_threshold() is False

        sm.run("hello world", [])
        # The machine should still reach a terminal state via fallback.
        assert sm.current_state == "classified"

    def test_fallback_chain_activated(self, gqhsm_config):
        """A no_match transition drives the machine into the fallback_chain state.

        We step the machine manually to assert the fallback state is reachable
        via the no_match trigger before finalisation.
        """
        sm = RouterStateMachine(gqhsm_config)

        # Advance manually: pre_classify -> keyword_match -> fallback_chain.
        sm.begin_keyword()
        assert sm.current_state == "keyword_match"

        # confidence is 0.0 so matched_keywords is blocked; no_match advances.
        sm.no_match()
        assert sm.current_state == "fallback_chain"

    def test_execution_plan_structure(self, gqhsm_config):
        """The final state produces a dict with the required ROUTE-02 keys."""
        sm = RouterStateMachine(gqhsm_config)

        matches = [("code_detection", 0.9, "code")]
        plan = sm.run("def foo(): pass", matches)

        required_keys = {
            "primary_specialist",
            "execution_mode",
            "confidence",
            "matched_rule",
            "fallback_chain",
        }
        assert required_keys.issubset(plan.keys())
        assert plan["primary_specialist"] == "code"
        assert plan["confidence"] == pytest.approx(0.9)
        assert plan["matched_rule"] == "code_detection"

    def test_default_machine_when_no_config(self):
        """A None/empty config yields the default GQHSM model."""
        sm = RouterStateMachine(None)

        assert sm.current_state == "pre_classify"
        # The default model includes all canonical states.
        plan = sm.run("def foo(): pass", [("code_detection", 0.9, "code")])
        assert plan["primary_specialist"] == "code"

    def test_classification_result_reflects_fallback_chain(self, gqhsm_config):
        """Lower-priority matches are recorded in the fallback_chain list."""
        sm = RouterStateMachine(gqhsm_config)

        matches = [
            ("code_detection", 0.9, "code"),
            ("medical_detection", 0.5, "medical"),
        ]
        plan = sm.run("def diagnose()", matches)

        assert plan["fallback_chain"] == ["medical"]
