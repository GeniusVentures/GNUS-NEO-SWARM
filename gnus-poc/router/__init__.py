"""GNUS-POC router — rules-based specialist classification and execution planning.

The router module classifies input queries using YAML-driven rules
(keyword, regex, syntax density) and produces ``ExecutionPlan`` objects
consumed by the pipeline runner.  A GQHSM-compatible state machine
wraps the classification pipeline for future C++ portability.
"""

from router.plan import ExecutionPlan
from router.rules import RuleEngine, RouterConfigError

__all__ = [
    "ExecutionPlan",
    "RuleEngine",
    "RouterConfigError",
]
