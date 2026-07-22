"""Tests for RouterStateMachine — GQHSM-compatible state machine runtime."""

import pytest

from router.state_machine import (
    RouterStateMachine,
    _ROUTER_CLASSIFIER_DEFINITION,
    create_router_state_machine,
)

transitions = pytest.importorskip("transitions")


class TestRouterStateMachine:
    """Guard enforcement and start-state reachability."""

    def test_start_state_is_pre_classify(self):
        """The built-in machine starts in pre_classify."""
        sm = create_router_state_machine()
        assert sm.state == "pre_classify"

    def test_begin_classification_reaches_keyword_match(self):
        """The t_begin transition moves pre_classify -> keyword_match."""
        sm = create_router_state_machine()
        sm.trigger("begin_classification")
        assert sm.state == "keyword_match"

    def test_missing_guard_handler_blocks_transition(self):
        """A declared guardCondition with no registered handler must fail
        closed (block the transition), not silently become unconditional.

        Regression: previously _build() dropped missing guards, so
        `keyword_hit` (guarded by confidence_above_threshold) would fire
        unconditionally and route low-confidence matches to select_specialist.
        """
        sm = create_router_state_machine()  # no handlers registered
        sm.trigger("begin_classification")
        assert sm.state == "keyword_match"

        # keyword_hit has guardCondition "confidence_above_threshold" with no
        # handler — transition must be blocked.
        from transitions.core import MachineError
        try:
            sm.trigger("keyword_hit")
            # If no exception, state must NOT have moved to select_specialist
            assert sm.state != "select_specialist"
        except MachineError:
            pass  # blocked transition raising is also acceptable fail-closed
        assert sm.state == "keyword_match"

    def test_registered_guard_allows_transition(self):
        """Supplying a guard handler that returns True allows the transition."""
        sm = create_router_state_machine(
            rule_handlers={"confidence_above_threshold": lambda *a, **k: True}
        )
        sm.trigger("begin_classification")
        sm.trigger("keyword_hit")
        assert sm.state == "select_specialist"

    def test_registered_guard_rejecting_blocks_transition(self):
        """A guard handler returning False blocks the transition."""
        sm = create_router_state_machine(
            rule_handlers={"confidence_above_threshold": lambda *a, **k: False}
        )
        sm.trigger("begin_classification")
        try:
            sm.trigger("keyword_hit")
        except Exception:
            pass
        assert sm.state == "keyword_match"
