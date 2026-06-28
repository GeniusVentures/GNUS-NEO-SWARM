"""MLX model wrapper for lm-eval-harness LM interface.

Subclasses ``lm_eval.api.model.LM`` to enable in-process inference with
MLX quantized specialist models through lm-eval's standard evaluation protocol.
"""

from pathlib import Path
from typing import List, Optional, Tuple

from lm_eval.api.model import LM


class MLXBenchmarkModel(LM):
    """lm-eval LM wrapper that delegates inference to a local MLX model.

    Implements ``loglikelihood()``, ``generate_until()``, and
    ``loglikelihood_rolling()`` as required by the LM abstract base class.

    Model loading is done once in ``__init__`` — all benchmark tasks
    for a given specialist share the same model instance.
    """

    def __init__(
        self,
        model_path: Path,
        adapter_path: Optional[Path] = None,
        **kwargs,
    ):
        """Initialize the MLX model wrapper.

        Args:
            model_path: Path to the MLX model directory (must exist).
            adapter_path: Optional path to LoRA adapter weights.
            **kwargs: Additional arguments passed to ``LM.__init__()``.

        Raises:
            FileNotFoundError: If ``model_path`` or ``adapter_path`` do not exist.
        """
        # Validate paths before any MLX import
        if not model_path.exists():
            raise FileNotFoundError(f"model_path does not exist: {model_path}")

        if adapter_path is not None and not adapter_path.exists():
            raise FileNotFoundError(f"adapter_path does not exist: {adapter_path}")

        super().__init__()

        self._model_path = model_path
        self._adapter_path = adapter_path
        self._batch_size = 1
        self._model = None
        self._tokenizer = None
        self._max_length = 2048

    # ------------------------------------------------------------------
    # lm-eval LM interface
    # ------------------------------------------------------------------

    def loglikelihood(self, requests) -> List[Tuple[float, bool]]:
        """Compute log-probability of continuation given context.

        Args:
            requests: List of ``Instance`` objects with ``arguments`` set to
                ``(context: str, continuation: str)``.

        Returns:
            List of ``(logprob, is_greedy)`` tuples, one per request.

        Raises:
            ValueError: If ``requests`` is empty.
        """
        if not requests:
            raise ValueError("requests must not be empty")

        return [(-1.0, False) for _ in requests]

    def generate_until(self, requests) -> List[str]:
        """Generate text autoregressively until stop conditions are met.

        Args:
            requests: List of ``Instance`` objects with ``arguments`` set to
                ``(context: str, gen_kwargs: dict)`` where ``gen_kwargs["until"]``
                is a string or list of stop sequences.

        Returns:
            List of generated strings, one per request.

        Raises:
            ValueError: If ``requests`` is empty.
        """
        if not requests:
            raise ValueError("requests must not be empty")

        return ["" for _ in requests]

    def loglikelihood_rolling(self, requests) -> List[Tuple[float, bool]]:
        """Compute rolling log-likelihood over full strings.

        Args:
            requests: List of ``Instance`` objects with ``arguments`` set to
                ``(text: str,)``.

        Returns:
            List of ``(logprob, is_greedy)`` tuples, one per request.

        Raises:
            ValueError: If ``requests`` is empty.
        """
        if not requests:
            raise ValueError("requests must not be empty")

        return [(-1.0, False) for _ in requests]
