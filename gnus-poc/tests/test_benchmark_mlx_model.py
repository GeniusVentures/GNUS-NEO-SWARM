"""Tests for MLXBenchmarkModel — lm-eval LM wrapper for MLX models."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from eval.benchmark_mlx_model import MLXBenchmarkModel


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_minimal_model_dir(base_dir: Path, niche: str = "test_niche") -> Path:
    """Create a minimal model directory with config.json."""
    model_dir = base_dir / niche
    model_dir.mkdir(parents=True, exist_ok=True)
    (model_dir / "config.json").write_text('{"model_type": "qwen2"}')
    return model_dir


def _create_minimal_adapter(base_dir: Path, niche: str = "test_niche") -> Path:
    """Create a minimal adapter file (empty safetensors placeholder)."""
    adapter_dir = base_dir / niche
    adapter_dir.mkdir(parents=True, exist_ok=True)
    adapter_path = adapter_dir / "adapters.safetensors"
    adapter_path.write_bytes(b"\x00" * 64)
    return adapter_path


def _make_mock_loglikelihood_requests():
    """Create mock Instance objects for loglikelihood requests."""
    req1 = MagicMock()
    req1.arguments = ("The capital of France is", " Paris")
    req2 = MagicMock()
    req2.arguments = ("The largest planet is", " Jupiter")
    return [req1, req2]


def _make_mock_generate_until_requests():
    """Create mock Instance objects for generate_until requests."""
    req1 = MagicMock()
    req1.arguments = ("Explain gravity:", {"until": ["\n\n"], "max_gen_toks": 50})
    req2 = MagicMock()
    req2.arguments = ("Write a haiku:", {"until": ["\n\n"], "max_gen_toks": 30})
    return [req1, req2]


def _make_mock_loglikelihood_rolling_requests():
    """Create mock Instance objects for loglikelihood_rolling requests."""
    req1 = MagicMock()
    req1.arguments = ("The quick brown fox jumps over the lazy dog",)
    req2 = MagicMock()
    req2.arguments = ("Machine learning is a field of artificial intelligence",)
    return [req1, req2]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestMLXBenchmarkModel:
    """Tests for the MLXBenchmarkModel lm-eval LM wrapper."""

    def test_constructor_loads_model_and_tokenizer(self, tmp_path):
        """Constructor loads model from model_path, stores tokenizer, batch_size=1.

        Verifies that model_path and optional adapter_path are stored,
        a tokenizer is loaded, and batch_size is set to 1.
        """
        model_dir = _create_minimal_model_dir(tmp_path, "test_model")

        # Mock mlx_lm.load and tokenizer
        with patch.dict(sys.modules, {"mlx_lm": MagicMock(), "mlx.core": MagicMock()}):
            import mlx_lm as mock_mlx_lm
            mock_model = MagicMock()
            mock_tokenizer = MagicMock()
            mock_mlx_lm.load.return_value = (mock_model, mock_tokenizer)

            model = MLXBenchmarkModel(model_path=model_dir)

            assert model._model_path == model_dir
            assert model._adapter_path is None
            assert model._tokenizer is mock_tokenizer
            assert model._batch_size == 1

    def test_constructor_with_adapter(self, tmp_path):
        """Constructor with adapter_path stores adapter, validates path exists."""
        model_dir = _create_minimal_model_dir(tmp_path, "test_model")
        adapter_path = _create_minimal_adapter(tmp_path, "adapter")

        with patch.dict(sys.modules, {"mlx_lm": MagicMock(), "mlx.core": MagicMock()}):
            import mlx_lm as mock_mlx_lm
            mock_mlx_lm.load.return_value = (MagicMock(), MagicMock())

            model = MLXBenchmarkModel(model_path=model_dir, adapter_path=adapter_path)

            assert model._model_path == model_dir
            assert model._adapter_path == adapter_path
            assert model._batch_size == 1

    def test_loglikelihood_returns_tuples(self, tmp_path):
        """loglikelihood() returns list of (float, bool) tuples matching request count."""
        model_dir = _create_minimal_model_dir(tmp_path, "test_model")

        with patch.dict(sys.modules, {"mlx_lm": MagicMock(), "mlx.core": MagicMock()}):
            import mlx_lm as mock_mlx_lm
            mock_model = MagicMock()
            mock_tokenizer = MagicMock()
            # Tokenizer: encode returns a list of token IDs
            mock_tokenizer.encode.side_effect = lambda text: [101] + [202] * 5
            mock_mlx_lm.load.return_value = (mock_model, mock_tokenizer)

            # Mock model forward pass to return logits
            import mlx.core as mock_mx
            # Logits shape: (batch=1, seq_len, vocab_size)
            mock_logits = MagicMock()
            mock_model.return_value = mock_logits

            # Mock log_softmax to return log probabilities
            mock_log_probs = MagicMock()
            mock_mx.log_softmax.return_value = mock_log_probs

            model = MLXBenchmarkModel(model_path=model_dir)
            requests = _make_mock_loglikelihood_requests()
            results = model.loglikelihood(requests)

            assert len(results) == 2
            for logprob, is_greedy in results:
                assert isinstance(logprob, float)
                assert isinstance(is_greedy, bool)

    def test_loglikelihood_raises_value_error_on_empty(self, tmp_path):
        """loglikelihood() raises ValueError on empty requests list."""
        model_dir = _create_minimal_model_dir(tmp_path, "test_model")

        with patch.dict(sys.modules, {"mlx_lm": MagicMock(), "mlx.core": MagicMock()}):
            import mlx_lm as mock_mlx_lm
            mock_mlx_lm.load.return_value = (MagicMock(), MagicMock())

            model = MLXBenchmarkModel(model_path=model_dir)

            with pytest.raises(ValueError, match="empty"):
                model.loglikelihood([])

    def test_generate_until_returns_strings(self, tmp_path):
        """generate_until() returns list of strings matching request count."""
        model_dir = _create_minimal_model_dir(tmp_path, "test_model")

        with patch.dict(sys.modules, {"mlx_lm": MagicMock(), "mlx.core": MagicMock()}):
            import mlx_lm as mock_mlx_lm
            mock_model = MagicMock()
            mock_tokenizer = MagicMock()
            mock_tokenizer.encode.return_value = [101] + [202] * 3
            mock_tokenizer.decode.return_value = " generated text"
            mock_mlx_lm.load.return_value = (mock_model, mock_tokenizer)

            import mlx.core as mock_mx
            mock_logits = MagicMock()
            mock_model.return_value = mock_logits
            mock_mx.argmax.return_value = MagicMock()
            # Convert to int when indexing
            mock_mx.argmax.return_value.__getitem__.return_value = MagicMock()
            mock_mx.argmax.return_value.__getitem__.return_value.__int__ = lambda: 42

            model = MLXBenchmarkModel(model_path=model_dir)
            requests = _make_mock_generate_until_requests()
            results = model.generate_until(requests)

            assert len(results) == 2
            for result in results:
                assert isinstance(result, str)

    def test_generate_until_raises_value_error_on_empty(self, tmp_path):
        """generate_until() raises ValueError on empty requests list."""
        model_dir = _create_minimal_model_dir(tmp_path, "test_model")

        with patch.dict(sys.modules, {"mlx_lm": MagicMock(), "mlx.core": MagicMock()}):
            import mlx_lm as mock_mlx_lm
            mock_mlx_lm.load.return_value = (MagicMock(), MagicMock())

            model = MLXBenchmarkModel(model_path=model_dir)

            with pytest.raises(ValueError, match="empty"):
                model.generate_until([])

    def test_loglikelihood_rolling_returns_tuples(self, tmp_path):
        """loglikelihood_rolling() returns list of (float, bool) tuples matching request count."""
        model_dir = _create_minimal_model_dir(tmp_path, "test_model")

        with patch.dict(sys.modules, {"mlx_lm": MagicMock(), "mlx.core": MagicMock()}):
            import mlx_lm as mock_mlx_lm
            mock_model = MagicMock()
            mock_tokenizer = MagicMock()
            mock_tokenizer.encode.return_value = [101] + [202] * 10
            mock_mlx_lm.load.return_value = (mock_model, mock_tokenizer)

            import mlx.core as mock_mx
            mock_logits = MagicMock()
            mock_model.return_value = mock_logits
            mock_mx.log_softmax.return_value = MagicMock()

            model = MLXBenchmarkModel(model_path=model_dir)
            requests = _make_mock_loglikelihood_rolling_requests()
            results = model.loglikelihood_rolling(requests)

            assert len(results) == 2
            for logprob, is_greedy in results:
                assert isinstance(logprob, float)
                assert isinstance(is_greedy, bool)

    def test_loglikelihood_rolling_raises_value_error_on_empty(self, tmp_path):
        """loglikelihood_rolling() raises ValueError on empty requests list."""
        model_dir = _create_minimal_model_dir(tmp_path, "test_model")

        with patch.dict(sys.modules, {"mlx_lm": MagicMock(), "mlx.core": MagicMock()}):
            import mlx_lm as mock_mlx_lm
            mock_mlx_lm.load.return_value = (MagicMock(), MagicMock())

            model = MLXBenchmarkModel(model_path=model_dir)

            with pytest.raises(ValueError, match="empty"):
                model.loglikelihood_rolling([])

    def test_constructor_raises_file_not_found_for_model_path(self):
        """Constructor raises FileNotFoundError when model_path does not exist."""
        nonexistent_path = Path("/nonexistent/model/path/42a7b")

        with pytest.raises(FileNotFoundError, match="model_path"):
            MLXBenchmarkModel(model_path=nonexistent_path)

    def test_constructor_raises_file_not_found_for_adapter_path(self, tmp_path):
        """Constructor raises FileNotFoundError when adapter_path does not exist."""
        model_dir = _create_minimal_model_dir(tmp_path, "test_model")
        nonexistent_adapter = tmp_path / "nonexistent" / "adapters.safetensors"

        with pytest.raises(FileNotFoundError, match="adapter_path"):
            MLXBenchmarkModel(model_path=model_dir, adapter_path=nonexistent_adapter)
