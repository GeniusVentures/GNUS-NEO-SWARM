"""Tests for SyntheticDataGenerator — quality filtering, cascade, and direct generation."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from distill.synthetic import SyntheticDataGenerator, _refusal_re


def make_mock_response(content):
    """Create a mock response compatible with _ResponseWrapper shape.

    Produces a MagicMock with ``.choices[0].message.content``,
    ``.usage.prompt_tokens``, and ``.usage.completion_tokens``.
    Logprobs data is attached via ``.choices[0].logprobs.content``
    for cascade confidence computation compatibility.
    """
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

    def test_rejects_empty_or_whitespace_only(self):
        """Empty string and whitespace-only content are rejected before min_length check."""
        gen = SyntheticDataGenerator(MagicMock())
        assert not gen._passes_quality("", None)
        assert not gen._passes_quality("   ", None)
        assert not gen._passes_quality("\n\t  \n", None)

    def test_refusal_patterns_reject_correctly(self):
        for phrase in ["I cannot assist", "I'm unable to help", "as an AI assistant",
                       "I don't have that", "sorry, I cannot", "can't generate that"]:
            assert _refusal_re.search(phrase), f"Should reject: {phrase}"


class TestSyntheticDataGenerator:
    def test_generates_for_niche(self):
        """Default (use_cascade=True) uses generate_with_cascade for generation."""
        mock_client = MagicMock()
        mock_client.generate_with_cascade = MagicMock()
        mock_client.generate_with_cascade.side_effect = [
            make_mock_response(f"Python is a high-level programming language known for its readability. Call {i}. " * 10)
            for i in range(5)
        ]

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
        # Verify cascade was used with the correct domain mapping
        assert mock_client.generate_with_cascade.call_count == 3

    def test_cascade_generation_for_niche(self):
        """Explicit cascade mode routes niche to correct benchmark domain."""
        mock_client = MagicMock()
        mock_client.generate_with_cascade = MagicMock()
        mock_client.generate_with_cascade.side_effect = [
            make_mock_response(f"Python is a high-level programming language known for its readability. Call {i}. " * 10)
            for i in range(5)
        ]

        gen = SyntheticDataGenerator(mock_client, use_cascade=True)
        samples = gen.generate_for_niche(
            niche_name="code",
            system_prompt="You are a code specialist.",
            user_prompts=["Explain Python."],
            num_samples=3,
        )

        assert len(samples) == 3
        # Verify generate_with_cascade was called with domain="coding"
        assert mock_client.generate_with_cascade.call_count == 3
        for call_args in mock_client.generate_with_cascade.call_args_list:
            called_messages = call_args[0][0]
            called_domain = call_args[1]["domain"]
            assert len(called_messages) == 2
            assert called_domain == "coding"

    def test_direct_generation_for_niche(self):
        """Direct mode (use_cascade=False) uses generate() with model_name."""
        mock_client = MagicMock()
        mock_client.generate = MagicMock()
        mock_client.generate.side_effect = [
            make_mock_response(f"Python is a high-level programming language known for its readability. Call {i}. " * 10)
            for i in range(5)
        ]

        gen = SyntheticDataGenerator(mock_client, use_cascade=False)
        samples = gen.generate_for_niche(
            niche_name="code",
            system_prompt="You are a code specialist.",
            user_prompts=["Explain Python."],
            num_samples=3,
        )

        assert len(samples) == 3
        # Verify generate was called with messages keyword arg
        assert mock_client.generate.call_count == 3
        for call_args in mock_client.generate.call_args_list:
            called_messages = call_args.kwargs["messages"]
            assert len(called_messages) == 2

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

    def test_dedup_rejects_duplicate_normalized_content(self):
        """When the same content (after normalization) is generated twice, only the first is kept."""
        mock_client = MagicMock()
        mock_client.generate_with_cascade = MagicMock()
        # First two responses are same after normalization (different whitespace collapses)
        content_a = "Python is a high-level programming language. Extra spaces. " * 8
        content_b = "Python is a high-level programming language.  Extra   spaces. " * 8  # same after normalize
        content_c = "Java is a different programming language entirely, with distinct syntax. " * 8
        mock_client.generate_with_cascade.side_effect = [
            make_mock_response(content_a),
            make_mock_response(content_b),
            make_mock_response(content_c),
            make_mock_response(content_b),  # dup of a again
            make_mock_response(content_c),  # dup of c
            make_mock_response(content_a),  # dup of a
        ]

        gen = SyntheticDataGenerator(mock_client, use_cascade=True)
        samples = gen.generate_for_niche(
            niche_name="encyclopedic",
            system_prompt="You are a helpful assistant.",
            user_prompts=["Explain programming languages."] * 3,
            num_samples=3,
        )

        # Only 2 unique samples after dedup (a and c; b is a dup of a)
        assert len(samples) == 2
        assert samples[0]["text"] == content_a
        assert samples[1]["text"] == content_c

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
