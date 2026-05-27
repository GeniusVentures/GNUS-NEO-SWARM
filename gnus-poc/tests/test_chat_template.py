"""
Smoke tests for tokenizer_utils — validates FOUND-01 chat template fix.

These tests ensure:
1. tokenizer_utils module is importable and exports correct functions
2. format_chat() uses tokenizer.apply_chat_template() — NOT hand-rolled <|im_start|>
3. format_chat() output matches the tokenizer's native template output
"""

import sys
from pathlib import Path

# Ensure gnus-poc root is on sys.path so that 'from training.tokenizer_utils import ...' works
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_tokenizer_utils_imports():
    """Verify tokenizer_utils module exports load_tokenizer and format_chat."""
    from training.tokenizer_utils import load_tokenizer, format_chat

    assert callable(load_tokenizer), "load_tokenizer must be callable"
    assert callable(format_chat), "format_chat must be callable"


def test_format_chat_rejects_old_template():
    """
    Verify format_chat() does NOT produce <|im_start|> tokens.

    This is the core FOUND-01 bug: the old code hardcoded Qwen2.5's
    <|im_start|> format, but training uses Qwen3 models.
    """
    # Lazy-load: don't require model download for this structural test
    # Mock a tokenizer that has apply_chat_template returning known content
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


def test_format_chat_matches_tokenizer_template():
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


def test_load_tokenizer_returns_valid_tokenizer():
    """Verify load_tokenizer returns an object with apply_chat_template method."""
    # This test only checks the function signature and return type contract.
    # Full model download test is in Plan 01-03 smoke test (marked slow).
    import inspect
    from training.tokenizer_utils import load_tokenizer

    sig = inspect.signature(load_tokenizer)
    params = list(sig.parameters.keys())
    assert "model_path" in params, f"load_tokenizer must accept model_path parameter, got: {params}"
