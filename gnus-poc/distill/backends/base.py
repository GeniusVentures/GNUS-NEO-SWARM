"""Abstract base class for teacher API backends.

All backends (OpenAI, Anthropic) implement this interface so that
TeacherClient can dispatch calls uniformly regardless of backend.
"""

from abc import ABC, abstractmethod


class TeacherBackend(ABC):
    """Abstract interface that every teacher API backend must implement.

    Concrete backends wrap their respective SDKs (openai, anthropic),
    converting native responses into a uniform response dict with keys:
        content:           str   — the completion text
        prompt_tokens:     int   — tokens consumed by the prompt
        completion_tokens: int   — tokens produced by the completion
        raw_response:      object — the original SDK response object
    """

    def __init__(self, endpoint_config: dict, model_id: str, api_key: str):
        """Initialise the backend with connection details.

        Args:
            endpoint_config: The resolved ``endpoints[name]`` dict from
                pipeline.yaml (contains ``url``, ``apiType``, etc.).
            model_id: The literal model identifier from the ``models``
                config block (e.g. ``"deepseek-v4-pro[1m]"``).
            api_key: The API key to authenticate requests.
        """
        self._endpoint_config = endpoint_config
        self._model_id = model_id
        self._api_key = api_key

    # ------------------------------------------------------------------
    # Abstract — subclasses MUST implement
    # ------------------------------------------------------------------

    @abstractmethod
    def generate(
        self,
        messages: list,
        max_tokens: int,
        temperature: float,
        **kwargs,
    ) -> dict:
        """Send a completion request and return a uniform response dict.

        Returns:
            dict with keys ``content``, ``prompt_tokens``,
            ``completion_tokens``, ``raw_response``.
        """

    @property
    @abstractmethod
    def backend_type(self) -> str:
        """Return a short identifier for this backend (e.g. ``"openai"``)."""

    # ------------------------------------------------------------------
    # Concrete — subclasses MAY override
    # ------------------------------------------------------------------

    @staticmethod
    def estimate_cost(prompt_tokens: int, completion_tokens: int) -> float:
        """Estimate the USD cost of a completion.

        Default formula: (prompt_tokens * 0.27 + completion_tokens * 1.10) / 1_000_000.
        Subclasses that use different pricing SHOULD override this.
        """
        return (prompt_tokens * 0.27 + completion_tokens * 1.10) / 1_000_000
