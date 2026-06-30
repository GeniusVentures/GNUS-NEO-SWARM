"""GQHSM-compatible rules-based specialist router.

This package classifies incoming queries into specialist domains using a
rules-based state machine. The state machine consumes GQHSM-compatible JSON
rule definitions (D-09: Python-native via the ``transitions`` library;
D-10: GQHSM conceptual model; D-13: JSON is the compatibility contract for
the future C++ GQHSM integration).

Public API:
    RouterStateMachine: State machine runtime backed by ``transitions``.
    RuleMatcher: Keyword / regex / syntax-density rule matching engine.
    RouterClassifier: High-level ``classify()`` API with fallback chaining.
"""

import logging

from router.classifier import RouterClassifier
from router.engine import RouterStateMachine
from router.rules import RuleMatcher

logger = logging.getLogger(__name__)

__all__ = ["RouterClassifier", "RouterStateMachine", "RuleMatcher"]
