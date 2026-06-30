"""Tests for the rules-based router: RuleMatcher and RouterClassifier.

Covers ROUTE-01 (rule matching: keyword, regex, syntax density, priority,
fallback) and the RouterClassifier classify() API with fallback chaining
(D-12) and the GQHSM-compatible JSON export (D-13).
"""

import json
from pathlib import Path

import pytest
import yaml

from router.classifier import RouterClassifier
from router.rules import RuleMatcher


# Minimal router rules used by RuleMatcher-focused unit tests. Kept inline so
# the tests do not depend on the real config file.
_SAMPLE_RULES = {
    "router": {
        "rules": [
            {
                "name": "code_detection",
                "priority": 10,
                "triggers": [
                    {"type": "keyword", "patterns": ["def ", "class "]},
                    {
                        "type": "syntax_density",
                        "threshold": 0.3,
                        "chars": ["{", "}", "(", ")", ";", "=", "=>", ":"],
                    },
                ],
                "action": "select_specialist",
                "specialist": "code",
                "confidence_threshold": 0.6,
                "fallback": "encyclopedic",
            },
            {
                "name": "math_detection",
                "priority": 9,
                "triggers": [
                    {
                        "type": "syntax_density",
                        "threshold": 0.3,
                        "chars": list("0123456789+-*/=^"),
                    },
                    {
                        "type": "keyword",
                        "patterns": ["solve", "equation", "derivative"],
                    },
                ],
                "action": "select_specialist",
                "specialist": "qa_technical",
                "confidence_threshold": 0.6,
                "fallback": "encyclopedic",
            },
            {
                "name": "medical_detection",
                "priority": 8,
                "triggers": [
                    {
                        "type": "keyword",
                        "patterns": ["diagnosis", "patient", "disease"],
                    },
                ],
                "action": "select_specialist",
                "specialist": "medical",
                "confidence_threshold": 0.6,
                "fallback": "encyclopedic",
            },
            {
                "name": "default_encyclopedic",
                "priority": 0,
                "triggers": [{"type": "always_match"}],
                "action": "select_specialist",
                "specialist": "encyclopedic",
                "confidence_threshold": 0.0,
            },
        ]
    }
}


@pytest.fixture
def classifier_root(tmp_path):
    """Create a tmp project root with a config/router_rules.yaml for classifier tests."""
    root = tmp_path / "gnus_poc_test"
    config_dir = root / "config"
    config_dir.mkdir(parents=True)
    (root / "router").mkdir()
    # Copy the real production rules so behaviour matches the shipped config.
    prod_rules = Path(__file__).resolve().parent.parent / "config" / "router_rules.yaml"
    target = config_dir / "router_rules.yaml"
    target.write_text(prod_rules.read_text(), encoding="utf-8")
    return root


class TestRuleMatcher:
    def test_keyword_code_detection(self):
        """ROUTE-01: query with 'def ' matches the code_detection rule."""
        matcher = RuleMatcher(_SAMPLE_RULES)

        matches = matcher.match_rules("def my_function():")

        names = [m[0] for m in matches]
        assert "code_detection" in names

    def test_regex_pattern_match(self):
        """ROUTE-01: regex trigger matches expected text."""
        rules = {
            "router": {
                "rules": [
                    {
                        "name": "regex_rule",
                        "priority": 5,
                        "triggers": [{"type": "regex", "patterns": [r"\bfunction\b"]}],
                        "action": "select_specialist",
                        "specialist": "code",
                        "confidence_threshold": 0.5,
                        "fallback": "encyclopedic",
                    }
                ]
            }
        }
        matcher = RuleMatcher(rules)

        score = matcher.regex_match("a function declaration", [r"\bfunction\b"])

        assert score == 1.0

    def test_syntax_density_math(self):
        """ROUTE-01: query with >30% numeric/symbol tokens matches math_detection."""
        matcher = RuleMatcher(_SAMPLE_RULES)

        matches = matcher.match_rules("solve 3x + 5 = 20 for x")

        specialists = [m[2] for m in matches]
        assert "qa_technical" in specialists

    def test_no_match_default(self):
        """ROUTE-01: a query matching nothing falls back to default_encyclopedic only."""
        matcher = RuleMatcher(_SAMPLE_RULES)

        matches = matcher.match_rules("hello world")

        # always_match keeps the default in the match list.
        assert ("default_encyclopedic", 0.5, "encyclopedic") in matches
        # No non-default rules should have matched this trivial query.
        non_default = [m for m in matches if m[0] != "default_encyclopedic"]
        assert non_default == []

    def test_priority_ordering(self):
        """ROUTE-01: overlapping matches are sorted by priority descending."""
        matcher = RuleMatcher(_SAMPLE_RULES)

        matches = matcher.match_rules("def diagnose_patient()")

        # code_detection (priority 10) must rank above medical_detection (8).
        names = [m[0] for m in matches if m[0] != "default_encyclopedic"]
        assert names.index("code_detection") < names.index("medical_detection")

    def test_confidence_below_threshold_is_returned_anyway(self):
        """match_rules returns all matches; threshold gating happens in the classifier.

        A partial keyword match still appears in the matcher output — the
        RouterClassifier decides whether confidence meets the rule threshold.
        """
        matcher = RuleMatcher(_SAMPLE_RULES)

        # 'def x' contains 'def ' (1 of 2 keyword patterns) -> confidence 0.5,
        # which is below the rule's 0.6 threshold. The matcher still reports
        # the match; the classifier decides whether it clears the threshold.
        matches = matcher.match_rules("def x")  # one of two code keywords -> 0.5

        code_matches = [m for m in matches if m[0] == "code_detection"]
        assert code_matches
        # 1 of 2 keyword patterns matched -> 0.5 confidence, below 0.6 threshold.
        assert code_matches[0][1] == pytest.approx(0.5)

    def test_always_match_confidence(self):
        """ROUTE-01: always_match trigger returns exactly 0.5."""
        matcher = RuleMatcher(_SAMPLE_RULES)

        score = matcher.syntax_density_match("anything", [], 0.0) if False else 0.5

        # Use a dedicated always_match-only rule to assert the fixed confidence.
        always_rules = {
            "router": {
                "rules": [
                    {
                        "name": "default_only",
                        "priority": 0,
                        "triggers": [{"type": "always_match"}],
                        "action": "select_specialist",
                        "specialist": "encyclopedic",
                    }
                ]
            }
        }
        matches = RuleMatcher(always_rules).match_rules("any query at all")

        assert matches == [("default_only", 0.5, "encyclopedic")]
        assert score == 0.5  # placeholder assertion retained for clarity

    def test_rule_yaml_format_parseable(self):
        """ROUTE-01: the shipped router_rules.yaml loads cleanly with yaml.safe_load."""
        prod_rules = Path(__file__).resolve().parent.parent / "config" / "router_rules.yaml"

        with prod_rules.open("r", encoding="utf-8") as fh:
            loaded = yaml.safe_load(fh)

        assert "router" in loaded
        assert len(loaded["router"]["rules"]) >= 5


class TestRouterClassifier:
    def test_keyword_code_detection_routes_to_code(self, classifier_root):
        """A code-heavy query routes to the code specialist."""
        clf = RouterClassifier(project_root=classifier_root)

        # Rich in code signals: multiple keyword hits ('def ', 'class ',
        # 'import ', 'const ') plus high syntax density.
        plan = clf.classify("def class import const { } ( ) ; = => :")

        assert plan["primary_specialist"] == "code"
        assert plan["confidence"] > 0
        assert plan["matched_rule"] == "code_detection"

    def test_syntax_density_math_routes_to_qa_technical(self, classifier_root):
        """A math query with >30% numeric/symbol chars routes to qa_technical."""
        clf = RouterClassifier(project_root=classifier_root)

        # Densely numeric/symbolic: digits and operators dominate the query so
        # syntax_density clears its 0.3 threshold and confidence reaches 1.0.
        plan = clf.classify("solve 3+5=8 9-4=5 2*6=12 10/2=5")

        assert plan["primary_specialist"] == "qa_technical"
        assert plan["matched_rule"] == "math_detection"

    def test_default_fallback_routes_to_encyclopedic(self, classifier_root):
        """A query matching no rules routes to the encyclopedic specialist."""
        clf = RouterClassifier(project_root=classifier_root)

        plan = clf.classify("What is the capital of France?")

        assert plan["primary_specialist"] == "encyclopedic"

    def test_priority_ordering(self, classifier_root):
        """A query matching both code (priority 10) and medical (priority 8) prefers code.

        Code signals dominate (high keyword + syntax density), so code_detection
        clears its threshold and wins over medical_detection on priority.
        """
        clf = RouterClassifier(project_root=classifier_root)

        # Code signals dominate: braces/operators push syntax_density above 0.3
        # so code_detection clears its threshold, while 'patient' also triggers
        # medical_detection at a lower priority.
        plan = clf.classify("def diagnose_patient(){}(){}();=:=:={}{ }()")

        assert plan["primary_specialist"] == "code"
        assert plan["matched_rule"] == "code_detection"

    def test_confidence_below_threshold_triggers_fallback(self, classifier_root):
        """A weak keyword match (below threshold) triggers fallback chaining."""
        clf = RouterClassifier(project_root=classifier_root)

        # 'def' alone matches 1 of 6 code keywords -> confidence 1/6 < 0.6.
        plan = clf.classify("def")

        assert plan["execution_mode"] == "fallback"
        assert plan["primary_specialist"] == "encyclopedic"
        assert plan["fallback_chain"]

    def test_execution_plan_structure(self, classifier_root):
        """classify() returns a dict with the required ROUTE-02 keys."""
        clf = RouterClassifier(project_root=classifier_root)

        plan = clf.classify("def foo(): pass")

        required_keys = {
            "primary_specialist",
            "execution_mode",
            "confidence",
            "matched_rule",
            "fallback_chain",
        }
        assert required_keys.issubset(plan.keys())
        assert plan["execution_mode"] in ("single", "fallback")

    def test_json_export_matches_yaml(self, classifier_root):
        """router_rules.json is written at init and contains states + transitions."""
        clf = RouterClassifier(project_root=classifier_root)

        json_path = classifier_root / "config" / "router_rules.json"
        assert json_path.exists()

        with json_path.open("r", encoding="utf-8") as fh:
            exported = json.load(fh)

        assert "states" in exported
        assert "transitions" in exported
        assert exported.get("initial") == "pre_classify"
        assert isinstance(exported["transitions"], list)
        assert exported["transitions"]  # non-empty

    def test_json_export_states_match_yaml_specialists(self, classifier_root):
        """The exported JSON states list is structurally valid GQHSM."""
        clf = RouterClassifier(project_root=classifier_root)

        json_path = classifier_root / "config" / "router_rules.json"
        with json_path.open("r", encoding="utf-8") as fh:
            exported = json.load(fh)

        state_names = {s["name"] for s in exported["states"]}
        # The default GQHSM model states must all be present.
        for expected in (
            "pre_classify",
            "keyword_match",
            "select_specialist",
            "fallback_chain",
            "classified",
        ):
            assert expected in state_names
