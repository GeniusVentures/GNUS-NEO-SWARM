"""Tests for SyntheticDataGenerator — quality filtering and output validation."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from distill.synthetic import SyntheticDataGenerator, _refusal_re


def make_mock_response(content):
    resp = MagicMock()
    resp.choices = [MagicMock()]
    resp.choices[0].message.content = content
    resp.usage = MagicMock()
    resp.usage.prompt_tokens = 10
    resp.usage.completion_tokens = 5
    return resp


class TestQualityFiltering:
    def test_rejects_short_content(self):
        gen = SyntheticDataGenerator(MagicMock())
        assert not gen._passes_quality("short", None)
        assert not gen._passes_quality("a" * 199, None)
        assert gen._passes_quality("a" * 200, None)

    def test_rejects_refusal_content(self):
        gen = SyntheticDataGenerator(MagicMock())
        assert not gen._passes_quality("I cannot help with that request. Please ask something else. " + "x" * 200, None)
        assert not gen._passes_quality("As an AI, I'm unable to provide that information. " + "x" * 200, None)
        assert not gen._passes_quality("I'm not able to generate that content. " + "x" * 200, None)

    def test_rejects_missing_keywords(self):
        gen = SyntheticDataGenerator(MagicMock())
        content = "Python is a programming language. It is used for web development. " * 10
        assert not gen._passes_quality(content, ["quantum", "reactor"])

    def test_accepts_keyword_match(self):
        gen = SyntheticDataGenerator(MagicMock())
        content = "Python is a programming language. " * 20
        assert gen._passes_quality(content, ["python"])

    def test_refusal_patterns_reject_correctly(self):
        for phrase in ["I cannot assist", "I'm unable to help", "as an AI assistant",
                       "I don't have that", "sorry, I cannot", "can't generate that"]:
            assert _refusal_re.search(phrase), f"Should reject: {phrase}"


class TestSyntheticDataGenerator:
    def test_generates_for_niche(self):
        mock_client = MagicMock()
        mock_client.generate = MagicMock()
        mock_client.generate.return_value = make_mock_response(
            "Python is a high-level programming language known for its readability. " * 10
        )

        gen = SyntheticDataGenerator(mock_client)
        samples = gen.generate_for_niche(
            niche_name="code",
            system_prompt="You are a code specialist.",
            user_prompts=["Explain Python."],
            num_samples=3,
        )

        assert len(samples) == 3
        for s in samples:
            assert s["niche"] == "code"
            assert s["source"] == "synthetic_deepseek_v4_pro"
            assert len(s["text"]) >= 200

    def test_save_to_jsonl(self, tmp_path):
        gen = SyntheticDataGenerator(MagicMock())
        samples = [
            {"text": "Hello world " * 50, "source": "synthetic", "niche": "test", "prompt": "Say hello"},
        ]
        out = tmp_path / "synthetic" / "test.jsonl"
        gen.save_to_jsonl(samples, out)
        assert out.exists()
        lines = out.read_text().strip().split("\n")
        assert len(lines) == 1

    def test_empty_niche_yields_no_samples(self):
        mock_client = MagicMock()
        gen = SyntheticDataGenerator(mock_client)
        samples = gen.generate_for_niche(
            niche_name="empty",
            system_prompt="You are a specialist.",
            user_prompts=[],
            num_samples=10,
        )
        assert len(samples) == 0
