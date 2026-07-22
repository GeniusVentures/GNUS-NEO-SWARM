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


# ---------------------------------------------------------------------------
# Real-MLX correctness tests (CR-02 / CR-03) — verify loglikelihood indexing
#
# These do NOT mock mlx.core: they inject a controlled logits tensor where the
# position-read determines the result, so an off-by-one (reading logits[pos]
# instead of logits[pos-1]) would change the score. This is the test that was
# missing and let CR-02 ship undetected.
# ---------------------------------------------------------------------------


class _FakeTokenizer:
    """Deterministic tokenizer mapping known strings to controlled token IDs."""

    def __init__(self, table):
        self._table = table

    def encode(self, text):
        return list(self._table[text])


def _build_model_without_load(model_fn, tokenizer, max_length):
    """Construct an MLXBenchmarkModel bypassing mlx_lm.load.

    Sets only the attributes loglikelihood touches: ``_tokenizer`` (drives
    ``_encode``), ``_model`` (the forward callable), and ``_max_length``.
    """
    model = MLXBenchmarkModel.__new__(MLXBenchmarkModel)
    model._tokenizer = tokenizer
    model._model = model_fn
    model._max_length = max_length
    return model


def _logits_favoring(positions_favor_token, seq_len, vocab_size=4):
    """Build an mlx logits tensor (1, seq_len, vocab_size).

    ``positions_favor_token`` maps sequence position -> the token id that
    position's distribution strongly favors (all other positions favor token 0).
    A favored position peaks on its token so log_softmax ~ 0 and argmax matches.
    """
    import mlx.core as mx

    base = [-30.0] * vocab_size
    base[0] = 30.0  # default: every position favors token 0
    rows = []
    for pos in range(seq_len):
        row = list(base)
        favored = positions_favor_token.get(pos, 0)
        row[0] = -30.0
        row[favored] = 30.0
        rows.append(row)
    return mx.array([rows])


def test_loglikelihood_reads_logits_at_pos_minus_one():
    """CR-02: logprob of continuation token at pos comes from logits[pos-1].

    Setup: context "C" -> [0], full "CX" -> [0, 1]. The continuation token (id 1)
    is at position 1, so its logprob must come from logits[0]. We make logits[0]
    favor token 1 (high logprob, greedy) and logits[1] favor token 0.

    Only the FIXED indexing (pred_pos = pos - 1) yields a high logprob and
    is_greedy=True. The buggy logits[pos] read would score against logits[1]
    (favoring token 0), producing a very negative logprob and is_greedy=False.
    """
    tokenizer = _FakeTokenizer({"C": [0], "CX": [0, 1]})

    def model_fn(_x):
        # seq_len 2: pos 0 favors token 1, pos 1 favors token 0
        return _logits_favoring({0: 1, 1: 0}, seq_len=2)

    model = _build_model_without_load(model_fn, tokenizer, max_length=32)

    req = MagicMock()
    req.arguments = ("C", "X")

    logprob, is_greedy = model.loglikelihood([req])[0]

    assert is_greedy is True, (
        "continuation token must be the argmax at the position that predicts it "
        "(logits[pos-1]); is_greedy=False indicates the wrong position was read"
    )
    assert logprob > -1e-4, (
        f"logprob should be ~0 (continuation token strongly predicted); got {logprob}"
    )


def test_loglikelihood_long_context_does_not_return_neg_inf():
    """CR-03: long context (len > max_length) must not collapse to -inf.

    Setup: context -> 6 tokens [0]*6, full -> 7 tokens [0]*6 + [1]. With
    max_length=4 the sequence is tail-truncated to [0,0,0,1]; the continuation
    token (id 1) sits at position 3, predicted by logits[2]. We make logits[2]
    favor token 1.

    The pre-fix code used the untruncated context_len (6), yielding cont_len < 0
    and returning (-inf, False) for every long request. The fix must preserve the
    continuation and return a real, high logprob.
    """
    tokenizer = _FakeTokenizer({"L": [0, 0, 0, 0, 0, 0], "LX": [0, 0, 0, 0, 0, 0, 1]})

    def model_fn(_x):
        # after tail-truncation token_ids = [0,0,0,1]; token 1 at pos 3, predicted by logits[2]
        return _logits_favoring({2: 1}, seq_len=4)

    model = _build_model_without_load(model_fn, tokenizer, max_length=4)

    req = MagicMock()
    req.arguments = ("L", "X")

    logprob, is_greedy = model.loglikelihood([req])[0]

    assert logprob != float("-inf"), "long-context request returned -inf (CR-03 regressed)"
    assert is_greedy is True, (
        "continuation token must be scored from logits[pos-1] after truncation"
    )
    assert logprob > -1e-4, f"logprob should be ~0; got {logprob}"
