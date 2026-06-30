"""
Smoke tests for tokenizer_utils — validates FOUND-01 chat template fix.

These tests ensure:
1. tokenizer_utils module is importable and exports correct functions
2. format_chat() uses tokenizer.apply_chat_template() — NOT hand-rolled <|im_start|>
3. format_chat() output matches the tokenizer's native template output

Fast structural tests (no model download) run by default.
Slow integration tests require a real tokenizer — use 'pytest -m slow' to run.
"""

import sys
from pathlib import Path

import pytest

# Ensure gnus-poc root is on sys.path so that 'from training.tokenizer_utils import ...' works
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ---------------------------------------------------------------------------
# Fast structural tests (no model download — always run)
# ---------------------------------------------------------------------------

def test_tokenizer_utils_imports():
    """Verify tokenizer_utils module exports load_tokenizer and format_chat."""
    from training.tokenizer_utils import load_tokenizer, format_chat

    assert callable(load_tokenizer), "load_tokenizer must be callable"
    assert callable(format_chat), "format_chat must be callable"


def test_format_chat_with_mock_rejects_old_template():
    """
    Verify format_chat() does NOT produce <|im_start|> tokens (mock tokenizer).

    This is the core FOUND-01 bug: the old code hardcoded Qwen2.5's
    <|im_start|> format, but training uses Qwen3 models.
    """
    class MockTokenizer:
        def apply_chat_template(self, messages, tokenize=False, add_generation_prompt=False):
            return "<|qwen3_start|>system\nYou are helpful.\n<|qwen3_end|>\n<|qwen3_start|>user\nHello\n<|qwen3_end|>"

    from training.tokenizer_utils import format_chat

    messages = [
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "Hello"},
    ]
    result = format_chat(messages, MockTokenizer())
    assert "<|im_start|>" not in result, (
        "format_chat() must NOT produce <|im_start|> tokens — "
        "this is the Qwen2.5 format that causes the chat template mismatch bug"
    )


def test_format_chat_with_mock_matches_template():
    """
    Verify format_chat() delegates to tokenizer.apply_chat_template()
    and returns its output unchanged (thin wrapper).
    """
    expected = "<template>user: test</template>"

    class MockTokenizer:
        def apply_chat_template(self, messages, tokenize=False, add_generation_prompt=False):
            return expected

    from training.tokenizer_utils import format_chat

    messages = [{"role": "user", "content": "test"}]
    result = format_chat(messages, MockTokenizer())
    assert result == expected, f"Expected '{expected}', got '{result}'"


def test_load_tokenizer_signature():
    """Verify load_tokenizer function signature accepts model_path parameter."""
    import inspect
    from training.tokenizer_utils import load_tokenizer

    sig = inspect.signature(load_tokenizer)
    params = list(sig.parameters.keys())
    assert "model_path" in params, f"load_tokenizer must accept model_path parameter, got: {params}"


# ---------------------------------------------------------------------------
# Slow integration tests (require model download — run with 'pytest -m slow')
# These use the real Qwen2.5-0.5B-Instruct tokenizer for full validation.
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_format_chat_produces_chat_template(real_tokenizer, sample_messages):
    """
    Verify format_chat produces valid chat template output using a real tokenizer.

    Checks:
    - Result is a non-empty string
    - Uses the tokenizer's native template (delegation verified by
      test_format_chat_matches_tokenizer_template). Note: Qwen2.5's native
      ChatML template legitimately uses <|im_start|>/<|im_end|> tokens, so
      their presence is expected and correct.
    - Contains the user message text
    """
    from training.tokenizer_utils import format_chat

    result = format_chat(sample_messages, real_tokenizer)

    assert result and len(result) > 0, "format_chat returned empty string"
    assert "Hello, world!" in result, (
        "format_chat output must contain the user message text"
    )


@pytest.mark.slow
def test_format_chat_matches_tokenizer_template(real_tokenizer, sample_messages):
    """
    Verify format_chat output matches tokenizer.apply_chat_template natively.

    format_chat() should be a thin wrapper — the output must be identical
    to calling tokenizer.apply_chat_template() directly with the same args.
    """
    from training.tokenizer_utils import format_chat

    result_a = format_chat(sample_messages, real_tokenizer)
    result_b = real_tokenizer.apply_chat_template(
        sample_messages, tokenize=False, add_generation_prompt=False
    )

    assert result_a == result_b, (
        f"format_chat output differs from tokenizer.apply_chat_template:\n"
        f"  format_chat: {result_a[:100]}...\n"
        f"  tokenizer:   {result_b[:100]}..."
    )


@pytest.mark.slow
def test_load_tokenizer_returns_valid_tokenizer(mock_model_path):
    """
    Verify load_tokenizer returns a valid tokenizer with apply_chat_template.

    Calls load_tokenizer with the real model path and validates:
    - Returned object has apply_chat_template method
    - apply_chat_template returns a string when called
    """
    from training.tokenizer_utils import load_tokenizer

    tokenizer = load_tokenizer(mock_model_path)

    assert hasattr(tokenizer, "apply_chat_template"), (
        "load_tokenizer must return an object with apply_chat_template method"
    )

    result = tokenizer.apply_chat_template(
        [{"role": "user", "content": "test"}],
        tokenize=False,
        add_generation_prompt=False,
    )
    assert isinstance(result, str) and len(result) > 0, (
        "tokenizer.apply_chat_template must return a non-empty string"
    )

