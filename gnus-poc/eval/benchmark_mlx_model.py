"""MLX model wrapper for lm-eval-harness LM interface.

Subclasses ``lm_eval.api.model.LM`` to enable in-process inference with
MLX quantized specialist models through lm-eval's standard evaluation protocol.

Per RESEARCH.md: model is loaded once in ``__init__`` and reused for all
benchmark tasks in a ``simple_evaluate()`` call (Pitfall 3 avoidance).

Threat mitigations:
- T-04-01: Paths validated with FileNotFoundError before any MLX import.
- T-04-04: max_gen_toks capped at model context window in generate_until().
"""

import math
from pathlib import Path
from typing import List, Optional, Sequence, Tuple, Union

from lm_eval.api.model import LM

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
kDefaultMaxLength: int = 2048
kDefaultMaxGenToks: int = 256


class MLXBenchmarkModel(LM):
    """lm-eval LM wrapper that delegates inference to a local MLX model.

    Implements ``loglikelihood()``, ``generate_until()``, and
    ``loglikelihood_rolling()`` as required by the LM abstract base class.

    MLX imports are done defensively inside methods so the module
    is importable even in non-MLX test environments.
    """

    def __init__(
        self,
        model_path: Path,
        adapter_path: Optional[Path] = None,
        max_length: int = kDefaultMaxLength,
        **kwargs,
    ):
        """Initialize the MLX model wrapper and load the model.

        Args:
            model_path: Path to the MLX model directory (must exist).
            adapter_path: Optional path to LoRA adapter weights.
            max_length: Maximum sequence length for the model context window.
            **kwargs: Additional arguments passed to ``LM.__init__()``.

        Raises:
            FileNotFoundError: If ``model_path`` or ``adapter_path`` do not exist.
            RuntimeError: If MLX model loading fails.
        """
        # Validate paths before any MLX import (T-04-01 mitigation)
        if not model_path.exists():
            raise FileNotFoundError(f"model_path does not exist: {model_path}")

        if adapter_path is not None and not adapter_path.exists():
            raise FileNotFoundError(f"adapter_path does not exist: {adapter_path}")

        # Delegate to LM base
        super().__init__()

        self._model_path = model_path
        self._adapter_path = adapter_path
        self._batch_size = 1
        self._max_length = max_length

        # Load model and tokenizer via MLX
        self._model = None
        self._tokenizer = None
        self._load_model()

    # ------------------------------------------------------------------
    # Model loading
    # ------------------------------------------------------------------

    def _load_model(self) -> None:
        """Load the MLX model and tokenizer.

        Uses ``mlx_lm.load()`` to load the model from ``model_path``.
        If ``adapter_path`` is provided, loads the LoRA adapter.

        Raises:
            RuntimeError: If MLX model loading fails.
        """
        try:
            import mlx_lm
        except ImportError as exc:
            raise RuntimeError(
                f"mlx_lm is not installed — cannot load model from {self._model_path}"
            ) from exc

        try:
            result = mlx_lm.load(str(self._model_path))
        except Exception as exc:
            raise RuntimeError(
                f"Failed to load MLX model from {self._model_path}: {exc}"
            ) from exc

        if isinstance(result, tuple) and len(result) >= 2:
            self._model, self._tokenizer = result[0], result[1]
        else:
            self._model = result
            # Attempt to load tokenizer separately
            try:
                from transformers import AutoTokenizer
                self._tokenizer = AutoTokenizer.from_pretrained(
                    str(self._model_path), trust_remote_code=True,
                )
            except Exception:
                self._tokenizer = None

        # Load adapter if provided
        if self._adapter_path is not None:
            try:
                # mlx_lm.load_adapter is used for LoRA adapters
                mlx_lm.load_adapter(self._model, str(self._adapter_path))
            except Exception as exc:
                raise RuntimeError(
                    f"Failed to load LoRA adapter from {self._adapter_path}: {exc}"
                ) from exc

    # ------------------------------------------------------------------
    # Tokenizer helpers
    # ------------------------------------------------------------------

    def _encode(self, text: str) -> List[int]:
        """Encode text to token IDs using the loaded tokenizer.

        Handles multiple tokenizer APIs: HuggingFace (encode returns list
        or BatchEncoding), and callable tokenizers.

        Raises:
            RuntimeError: If no tokenizer is loaded.
        """
        if self._tokenizer is None:
            raise RuntimeError("Tokenizer is not loaded")
        if hasattr(self._tokenizer, "encode"):
            encoded = self._tokenizer.encode(text)
            if isinstance(encoded, list):
                return encoded
            if hasattr(encoded, "ids"):
                return encoded.ids
            return list(encoded)
        # Fallback: tokenizer is callable
        return self._tokenizer(text)

    def _decode(self, token_ids: Sequence[int]) -> str:
        """Decode token IDs to text using the loaded tokenizer."""
        if self._tokenizer is None:
            return " ".join(str(t) for t in token_ids)
        if hasattr(self._tokenizer, "decode"):
            return self._tokenizer.decode(list(token_ids))
        # Fallback
        return " ".join(str(t) for t in token_ids)

    def _tok_logprob(self, logits, position: int, token_id: int) -> float:
        """Extract the log-probability of a specific token at a position.

        Computes ``log(softmax(logits[0, position]))[token_id]``.

        Args:
            logits: Model output tensor of shape (1, seq_len, vocab_size).
            position: Sequence position to extract from.
            token_id: Target token ID to compute logprob for.

        Returns:
            Log-probability as a Python float.
        """
        import mlx.core as mx
        log_probs = mx.log_softmax(logits[0, position, :], axis=-1)
        return float(mx.take(log_probs, mx.array([token_id])))

    def _is_greedy(self, logits, position: int, token_id: int) -> bool:
        """Check whether *token_id* is the argmax at *position*.

        Args:
            logits: Model output tensor of shape (1, seq_len, vocab_size).
            position: Sequence position to check.
            token_id: Token ID to compare against argmax.

        Returns:
            True if *token_id* matches the argmax prediction at *position*.
        """
        import mlx.core as mx
        predicted = int(mx.argmax(logits[0, position, :], axis=-1))
        return predicted == token_id

    # ------------------------------------------------------------------
    # lm-eval LM interface
    # ------------------------------------------------------------------

    def loglikelihood(self, requests) -> List[Tuple[float, bool]]:
        """Compute log-probability of continuation given context.

        For each request, encodes ``context + continuation``, forwards
        through the model, extracts logprobs at continuation positions,
        sums them, and checks whether each continuation token is the
        greedy argmax.

        Args:
            requests: List of ``Instance`` objects with ``arguments`` set to
                ``(context: str, continuation: str)``.

        Returns:
            List of ``(logprob, is_greedy)`` tuples, one per request.

        Raises:
            ValueError: If ``requests`` is empty.
            RuntimeError: If MLX inference fails.
        """
        if not requests:
            raise ValueError("requests must not be empty")

        import mlx.core as mx
        results: List[Tuple[float, bool]] = []

        for req in requests:
            context, continuation = req.arguments
            full_text = context + continuation

            full_ids = self._encode(full_text)
            context_ids = self._encode(context)

            # CR-03: long-context truncation. Keep the TAIL of full_ids so the
            # continuation is never dropped, then recompute context_len against
            # the (possibly truncated) full sequence. The earlier head-truncation
            # used the untruncated context_len, producing cont_len < 0 and
            # returning -inf for every long multiple-choice request.
            if len(full_ids) > self._max_length:
                token_ids = full_ids[-self._max_length:]
            else:
                token_ids = full_ids
            # context_len is the number of leading tokens that belong to the
            # context. After tail-truncation it cannot exceed len(token_ids);
            # clamp it so the continuation always retains >= 1 token whenever
            # the continuation itself is non-empty.
            cont_len_total = max(0, len(full_ids) - len(context_ids))
            context_len = min(len(context_ids), len(token_ids) - max(1, cont_len_total))
            if context_len < 0:
                context_len = 0
            cont_len = len(token_ids) - context_len

            if cont_len <= 0:
                # Continuation itself is empty -- no tokens to score.
                results.append((float("-inf"), False))
                continue

            try:
                x = mx.array([token_ids])
                logits = self._model(x)
            except Exception as exc:
                raise RuntimeError(
                    f"MLX forward pass failed during loglikelihood: {exc}"
                ) from exc

            total_logprob = 0.0
            all_greedy = True

            for i in range(cont_len):
                pos = context_len + i
                target = token_ids[pos]
                # logits[pos-1] predicts the token at pos (causal next-token
                # convention). CR-02: reading logits[pos] would give the
                # distribution conditioned on tokens[0..pos] -- i.e. it
                # predicts token_ids[pos+1], not token_ids[pos].
                pred_pos = pos - 1
                assert pred_pos >= 0, (
                    "loglikelihood position invariant violated: pos-1 < 0"
                )
                total_logprob += self._tok_logprob(logits, pred_pos, target)
                if not self._is_greedy(logits, pred_pos, target):
                    all_greedy = False

            results.append((total_logprob, all_greedy))

        return results

    def generate_until(self, requests) -> List[str]:
        """Generate text autoregressively until stop conditions are met.

        Autoregressive greedy decode for each request. Generation stops
        when any stop sequence appears in the decoded text or the maximum
        generation token count is reached.

        Per T-04-04 mitigation: ``max_gen_toks`` is capped at
        ``min(requested_max, model_context_window)``.

        Args:
            requests: List of ``Instance`` objects with ``arguments`` set to
                ``(context: str, gen_kwargs: dict)`` where ``gen_kwargs["until"]``
                is a string or list of stop sequences and ``gen_kwargs["max_gen_toks"]``
                optionally caps generation length.

        Returns:
            List of generated strings (excluding the context), one per request.

        Raises:
            ValueError: If ``requests`` is empty.
            RuntimeError: If MLX generation fails.
        """
        if not requests:
            raise ValueError("requests must not be empty")

        import mlx.core as mx
        results: List[str] = []

        for req in requests:
            context, gen_kwargs = req.arguments

            # Extract generation parameters
            stop_sequences = gen_kwargs.get("until", [])
            if isinstance(stop_sequences, str):
                stop_sequences = [stop_sequences]

            requested_max = gen_kwargs.get("max_gen_toks", kDefaultMaxGenToks)
            # T-04-04: cap at model context window.

            prompt_ids = self._encode(context)
            if len(prompt_ids) > self._max_length:
                prompt_ids = prompt_ids[-self._max_length:]

            # WR-11: cap generation so prompt + generation fits in the context
            # window. The earlier ``min(requested_max, self._max_length)`` did
            # NOT account for the prompt length, so once the cumulative window
            # exceeded ``_max_length`` the sliding view dropped the oldest
            # tokens out of attention -- generation at later steps was then
            # conditioned on a DIFFERENT context than at earlier steps, making
            # greedy decode inconsistent and stop sequences that depend on
            # early context unreliable. Reserve room for the prompt explicitly.
            available = max(0, self._max_length - len(prompt_ids))
            max_gen_toks = max(0, min(requested_max, available))

            generated_ids: List[int] = []
            current_ids = list(prompt_ids)

            for _ in range(max_gen_toks):
                try:
                    x = mx.array([current_ids[-self._max_length:]])
                    logits = self._model(x)
                except Exception as exc:
                    raise RuntimeError(
                        f"MLX forward pass failed during generate_until: {exc}"
                    ) from exc

                # Greedy: take argmax of last position
                next_token = int(mx.argmax(logits[0, -1, :], axis=-1))
                generated_ids.append(next_token)
                current_ids.append(next_token)

                # Check stop sequences
                if stop_sequences:
                    generated_text = self._decode(generated_ids)
                    for stop_seq in stop_sequences:
                        if stop_seq and stop_seq in generated_text:
                            # Truncate at stop sequence position
                            stop_idx = generated_text.find(stop_seq)
                            generated_text = generated_text[:stop_idx]
                            results.append(generated_text)
                            break
                    else:
                        continue
                    break
            else:
                # Max tokens reached without stop
                generated_text = self._decode(generated_ids)
                results.append(generated_text)

        return results

    def loglikelihood_rolling(self, requests) -> List[Tuple[float, bool]]:
        """Compute rolling log-likelihood over full strings.

        For each request, encodes the full string and computes the
        log-probability of each token given all preceding tokens (sliding
        window). Sums the per-token logprobs and checks whether each
        token was the greedy argmax.

        Args:
            requests: List of ``Instance`` objects with ``arguments`` set to
                ``(text: str,)``.

        Returns:
            List of ``(logprob, is_greedy)`` tuples, one per request.

        Raises:
            ValueError: If ``requests`` is empty.
            RuntimeError: If MLX inference fails.
        """
        if not requests:
            raise ValueError("requests must not be empty")

        import mlx.core as mx
        results: List[Tuple[float, bool]] = []

        for req in requests:
            text = req.arguments[0]
            token_ids = self._encode(text)

            if len(token_ids) > self._max_length:
                token_ids = token_ids[:self._max_length]

            if len(token_ids) < 2:
                # Not enough tokens for rolling loglikelihood
                results.append((0.0, True))
                continue

            try:
                x = mx.array([token_ids])
                logits = self._model(x)
            except Exception as exc:
                raise RuntimeError(
                    f"MLX forward pass failed during loglikelihood_rolling: {exc}"
                ) from exc

            total_logprob = 0.0
            all_greedy = True

            # For each position i >= 1, compute logprob of token i given
            # tokens[0:i] (causal next-token convention, CR-02). logits[i-1]
            # is the distribution conditioned on tokens[0..i-1] and predicts
            # the token at position i.
            for i in range(1, len(token_ids)):
                target = token_ids[i]
                pred_pos = i - 1
                assert pred_pos >= 0, (
                    "loglikelihood_rolling position invariant violated: i-1 < 0"
                )
                total_logprob += self._tok_logprob(logits, pred_pos, target)
                if not self._is_greedy(logits, pred_pos, target):
                    all_greedy = False

            results.append((total_logprob, all_greedy))

        return results
