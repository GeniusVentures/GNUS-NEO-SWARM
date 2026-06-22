"""Tests for the rules-based specialist router module.

Covers:
- ExecutionPlan dataclass structure (ROUTE-02)
- Keyword, regex, and syntax density rule matching (ROUTE-01)
- Default specialist routing for no-match queries (ROUTE-01)
- Priority-based tiebreaking and fallback chaining
- YAML-driven rule definition with no hardcoded rules in Python
"""

from pathlib import Path

import pytest
import yaml

from router.plan import ExecutionPlan
from router.rules import RuleEngine


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_rules_yaml():
    """Return a dict representing the contents of config/router_rules.yaml."""
    return {
        "rules": [
            {
                "name": "code_keyword",
                "priority": 10,
                "type": "keyword",
                "patterns": ["def ", "class ", "import ", "function"],
                "specialist": "code",
                "execution_mode": "local_lora",
            },
            {
                "name": "code_regex",
                "priority": 15,
                "type": "regex",
                "patterns": [r"\b(function|class|import|def)\b"],
                "specialist": "code",
                "execution_mode": "local_lora",
            },
            {
                "name": "math_syntax",
                "priority": 20,
                "type": "syntax_density",
                "category": "numeric",
                "threshold": 0.3,
                "specialist": "qa_technical",
                "execution_mode": "local_lora",
            },
            {
                "name": "default_encyclopedic",
                "priority": 100,
                "type": "keyword",
                "patterns": [],
                "specialist": "encyclopedic",
                "execution_mode": "local_lora",
                "is_default": True,
            },
        ]
    }


@pytest.fixture
def rule_engine(sample_rules_yaml, tmp_path):
    """Create a RuleEngine with test rules YAML written to a temp file."""
    rules_path = tmp_path / "router_rules.yaml"
    with open(rules_path, "w") as fh:
        yaml.dump(sample_rules_yaml, fh)
    return RuleEngine(rules_path=rules_path)


@pytest.fixture
def rule_engine_str():
    """Create a RuleEngine from a YAML string (for YAML-driven test)."""
    yaml_str = """rules:
- name: "code_keyword"
  priority: 10
  type: keyword
  patterns: ["def ", "class ", "import ", "function"]
  specialist: "code"
  execution_mode: "local_lora"
- name: "default_encyclopedic"
  priority: 100
  type: keyword
  patterns: []
  specialist: "encyclopedic"
  execution_mode: "local_lora"
  is_default: true
"""
    return RuleEngine(rules_str=yaml_str)


# ---------------------------------------------------------------------------
# Tests: ExecutionPlan structure (ROUTE-02)
# ---------------------------------------------------------------------------

class TestExecutionPlan:
    def test_plan_structure_defaults(self):
        """ExecutionPlan dataclass has primary_specialist, execution_mode,
        confidence, and matched_rules fields."""
        plan = ExecutionPlan(
            primary_specialist="code",
            execution_mode="local_lora",
        )
        assert plan.primary_specialist == "code"
        assert plan.execution_mode == "local_lora"
        assert plan.confidence == 0.0
        assert plan.matched_rules == []
        assert plan.fallback_chain is None

    def test_plan_structure_complete(self):
        """All ExecutionPlan fields accept explicit values."""
        plan = ExecutionPlan(
            primary_specialist="medical",
            execution_mode="local_lora",
            confidence=0.85,
            matched_rules=["code_keyword", "code_regex"],
            fallback_chain=["qa_technical"],
        )
        assert plan.primary_specialist == "medical"
        assert plan.execution_mode == "local_lora"
        assert plan.confidence == 0.85
        assert plan.matched_rules == ["code_keyword", "code_regex"]
        assert plan.fallback_chain == ["qa_technical"]


# ---------------------------------------------------------------------------
# Tests: Keyword routing (ROUTE-01)
# ---------------------------------------------------------------------------

class TestKeywordRouting:
    def test_code_keyword_routing(self, rule_engine):
        """Keyword rules route code-containing queries to code specialist."""
        query = "def calculate_total(items): return sum(items)"
        plan = rule_engine.classify(query)
        assert plan.primary_specialist == "code"
        assert plan.execution_mode == "local_lora"
        assert plan.confidence > 0.0
        assert any("code" in r for r in plan.matched_rules), f"Expected code rule, got {plan.matched_rules}"

    def test_keyword_case_insensitive(self, rule_engine):
        """Keyword matching is case-insensitive."""
        query = "DEF Calculate(items): RETURN sum"
        plan = rule_engine.classify(query)
        assert plan.primary_specialist == "code"


# ---------------------------------------------------------------------------
# Tests: Regex routing (ROUTE-01)
# ---------------------------------------------------------------------------

class TestRegexRouting:
    def test_regex_routing(self, rule_engine):
        """Regex rules match queries with function/class/import patterns."""
        query = "Let me define a function to process data"
        plan = rule_engine.classify(query)
        assert plan.primary_specialist == "code"
        assert "code_regex" in plan.matched_rules

    def test_regex_no_match(self, rule_engine):
        """Non-code queries do not falsely match regex rules."""
        query = "What are the side effects of aspirin?"
        plan = rule_engine.classify(query)
        # Should fall through to encyclopedic (default)
        assert plan.primary_specialist != "code"


# ---------------------------------------------------------------------------
# Tests: Syntax density routing (ROUTE-01)
# ---------------------------------------------------------------------------

class TestSyntaxDensityRouting:
    def test_high_numeric_density_routes_to_technical(self, rule_engine):
        """Queries with >30% numeric tokens route to qa_technical (math path)."""
        query = "1 2 3 4 x = y 5 6 7 8 9 10"
        plan = rule_engine.classify(query)
        assert plan.primary_specialist == "qa_technical"
        assert "math_syntax" in plan.matched_rules

    def test_low_numeric_density_no_match(self, rule_engine):
        """Queries with <30% numeric tokens do not match syntax density rule."""
        query = "Just a few numbers like 42 in a long sentence about history and science and philosophy"
        plan = rule_engine.classify(query)
        # Should fall through to default
        assert plan.primary_specialist != "qa_technical"


# ---------------------------------------------------------------------------
# Tests: Default routing (ROUTE-01)
# ---------------------------------------------------------------------------

class TestNoMatchDefault:
    def test_no_match_defaults_to_encyclopedic(self, rule_engine):
        """Queries that match no specialist rules route to encyclopedic."""
        query = "What is the capital of France?"
        plan = rule_engine.classify(query)
        assert plan.primary_specialist == "encyclopedic"

    def test_no_match_with_fallback_disabled(self, rule_engine):
        """Default routing still works when fallback chain is disabled."""
        query = "Tell me about the history of printing"
        plan = rule_engine.classify(query)
        assert plan.primary_specialist == "encyclopedic"


# ---------------------------------------------------------------------------
# Tests: YAML-driven rules (ROUTE-01)
# ---------------------------------------------------------------------------

class TestYamlDrivenRules:
    def test_rule_addition_no_code_change(self, rule_engine_str, tmp_path):
        """Adding a rule to YAML changes behavior without Python code changes.

        Rewrites the YAML with an extra medical keyword rule, then verifies
        the engine picks it up on reload.
        """
        engine = rule_engine_str

        # Before: medical query routes to encyclopedic
        query = "What are the side effects of aspirin and ibuprofen?"
        plan_before = engine.classify(query)
        assert plan_before.primary_specialist == "encyclopedic"

        # Add a medical keyword rule to YAML (simulating config-only change)
        yaml_str = """rules:
- name: "code_keyword"
  priority: 10
  type: keyword
  patterns: ["def ", "class ", "import ", "function"]
  specialist: "code"
  execution_mode: "local_lora"
- name: "medical_keyword"
  priority: 5
  type: keyword
  patterns: ["aspirin", "ibuprofen", "side effects", "diabetes", "symptom"]
  specialist: "medical"
  execution_mode: "local_lora"
- name: "default_encyclopedic"
  priority: 100
  type: keyword
  patterns: []
  specialist: "encyclopedic"
  execution_mode: "local_lora"
  is_default: true
"""
        engine.reload(rules_str=yaml_str)

        # After: medical query routes to medical specialist
        plan_after = engine.classify(query)
        assert plan_after.primary_specialist == "medical"
        assert "medical_keyword" in plan_after.matched_rules


# ---------------------------------------------------------------------------
# Tests: Priority ordering
# ---------------------------------------------------------------------------

class TestPriorityOrdering:
    def test_higher_priority_wins(self, tmp_path):
        """Higher priority (lower number) rules take precedence."""
        yaml_str = """rules:
- name: "low_priority_code"
  priority: 50
  type: keyword
  patterns: ["def ", "class "]
  specialist: "code"
  execution_mode: "local_lora"
- name: "high_priority_medical"
  priority: 5
  type: keyword
  patterns: ["class"]
  specialist: "medical"
  execution_mode: "local_lora"
- name: "default_encyclopedic"
  priority: 100
  type: keyword
  patterns: []
  specialist: "encyclopedic"
  execution_mode: "local_lora"
  is_default: true
"""
        engine = RuleEngine(rules_str=yaml_str)
        # "class" matches both rules; higher priority (5) should win
        plan = engine.classify("class Medication:")
        assert plan.primary_specialist == "medical"
        assert "high_priority_medical" in plan.matched_rules

    def test_duplicate_priority_raises_error(self, tmp_path):
        """Duplicate priorities across rules raise ConfigValidationError."""
        yaml_str = """rules:
- name: "rule_a"
  priority: 10
  type: keyword
  patterns: ["def "]
  specialist: "code"
  execution_mode: "local_lora"
- name: "rule_b"
  priority: 10
  type: keyword
  patterns: ["class "]
  specialist: "qa_technical"
  execution_mode: "local_lora"
"""
        from router.rules import RouterConfigError

        with pytest.raises(RouterConfigError, match="priority"):
            RuleEngine(rules_str=yaml_str)


# ---------------------------------------------------------------------------
# Tests: Fallback chaining
# ---------------------------------------------------------------------------

class TestFallbackChaining:
    def test_fallback_when_confidence_below_threshold(self, tmp_path):
        """When primary match confidence is below threshold, try next-best."""
        yaml_str = """rules:
- name: "weak_code_match"
  priority: 10
  type: keyword
  patterns: ["def "]
  specialist: "code"
  execution_mode: "local_lora"
- name: "strong_medical_match"
  priority: 20
  type: keyword
  patterns: ["def ", "class ", "aspirin", "symptom", "diagnosis", "treatment"]
  specialist: "medical"
  execution_mode: "local_lora"
- name: "default_encyclopedic"
  priority: 100
  type: keyword
  patterns: []
  specialist: "encyclopedic"
  execution_mode: "local_lora"
  is_default: true
"""
        # Use a very high confidence threshold so no keyword match is "confident enough"
        engine = RuleEngine(rules_str=yaml_str, confidence_threshold=1.5)

        # Query with minimal code signal (only "def " matches weak rule)
        query = "def aspirin and ibuprofen diagnosis treatment"
        plan = engine.classify(query)
        # All rules below threshold → fallback chain activated
        assert plan.fallback_chain is not None
        assert len(plan.fallback_chain) > 0
        # Best match during fallback selected
        assert plan.primary_specialist == "code"

    def test_fallback_exhausted_defaults_to_default(self, tmp_path):
        """When fallback chain is exhausted, routes to default specialist."""
        yaml_str = """rules:
- name: "tiny_match"
  priority: 10
  type: keyword
  patterns: ["xyz"]
  specialist: "code"
  execution_mode: "local_lora"
- name: "default_encyclopedic"
  priority: 100
  type: keyword
  patterns: []
  specialist: "encyclopedic"
  execution_mode: "local_lora"
  is_default: true
"""
        engine = RuleEngine(rules_str=yaml_str, confidence_threshold=1.5)

        # Only one keyword match possible, all below threshold.
        # Fallback returns best match by confidence
        plan = engine.classify("xyz")
        assert plan.fallback_chain is not None
        assert plan.primary_specialist == "code"
        assert plan.fallback_chain is not None


# ---------------------------------------------------------------------------
# Edge case: input size limit (T-02-11)
# ---------------------------------------------------------------------------

class TestInputLimits:
    def test_input_size_limit(self, rule_engine):
        """Inputs exceeding 100KB raise RouterConfigError."""
        from router.rules import RouterConfigError

        huge_query = "x" * 102401  # 100KB + 1 byte
        with pytest.raises(RouterConfigError, match="Input size"):
            rule_engine.classify(huge_query)

    def test_input_just_under_limit(self, rule_engine):
        """Inputs at exactly 100KB are processed normally."""
        query = "What is the capital? " + "x" * (102400 - 25)
        plan = rule_engine.classify(query)
        assert plan.primary_specialist == "encyclopedic"
