"""Router execution plan dataclass.

Defines the structured output of the rules-based specialist router:
which specialist to invoke, how to invoke it, and the confidence/evidence
behind the classification decision.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ExecutionPlan:
    """Result of query classification by the RuleEngine.

    Attributes:
        primary_specialist: The selected specialist name (e.g. ``"code"``,
            ``"medical"``, ``"encyclopedic"``).
        execution_mode: How the specialist should be executed
            (e.g. ``"local_lora"``).
        confidence: Classification confidence score, 0.0--1.0.
        matched_rules: Names of rules that matched the query, in match order.
        fallback_chain: Specialists tried in fallback order when primary
            confidence fell below the configured threshold, or ``None`` if
            no fallback was needed.
    """

    primary_specialist: str
    execution_mode: str
    confidence: float = 0.0
    matched_rules: List[str] = field(default_factory=list)
    fallback_chain: Optional[List[str]] = None
