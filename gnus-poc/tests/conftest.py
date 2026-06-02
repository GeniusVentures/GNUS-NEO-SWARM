"""
Shared pytest fixtures for GNUS-POC test suite.

Provides reusable fixtures for:
- Temporary directory scaffolding
- Lightweight model paths for testing
- Sample chat messages
- Real tokenizer loading (session-scoped for efficiency)
"""

import sys
from pathlib import Path

import pytest

# Ensure gnus-poc root is on sys.path for all tests
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture
def tmp_project_root(tmp_path):
    """Create a temporary directory mimicking the gnus-poc structure."""
    root = tmp_path / "gnus_poc_test"
    root.mkdir()

    # Create essential subdirectories
    (root / "data").mkdir()
    (root / "data" / "analysis").mkdir()
    (root / "data" / "specialists").mkdir()
    (root / "models").mkdir()
    (root / "models" / "specialists_mlx").mkdir()
    (root / "training").mkdir()
    (root / "config").mkdir()
    (root / "artifacts").mkdir()

    return root


@pytest.fixture(scope="session")
def mock_model_path():
    """Return a lightweight HuggingFace model path suitable for testing.

    Uses Qwen2.5-0.5B-Instruct — a small model (~1GB) with a valid chat template.
    First download is cached by HuggingFace for subsequent test runs.
    """
    return "Qwen/Qwen2.5-0.5B-Instruct"


@pytest.fixture
def sample_messages():
    """Return standard chat messages for template testing."""
    return [
        {"role": "system", "content": "You are a test assistant."},
        {"role": "user", "content": "Hello, world!"},
    ]


@pytest.fixture(scope="session")
def real_tokenizer(mock_model_path):
    """Load the actual HuggingFace tokenizer for template validation.

    Session-scoped: loaded once per test session (model download on first use).
    Skips automatically if pytest is run with '-m \"not slow\"'.
    """
    try:
        from transformers import AutoTokenizer
    except ImportError:
        pytest.skip("transformers library not installed")

    try:
        tokenizer = AutoTokenizer.from_pretrained(
            mock_model_path,
            trust_remote_code=True,
        )
    except Exception as e:
        pytest.skip(f"Could not load tokenizer from {mock_model_path}: {e}")

    return tokenizer
