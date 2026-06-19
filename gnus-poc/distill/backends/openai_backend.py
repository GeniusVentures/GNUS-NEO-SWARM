"""OpenAI-compatible API backend using the ``openai`` Python SDK."""

from openai import OpenAI

from distill.backends.base import TeacherBackend


class OpenAIBackend(TeacherBackend):
    """Teacher backend that talks to any OpenAI-compatible endpoint.

    This wraps the official ``openai`` SDK and is used for endpoints whose
    ``apiType`` is ``"openai"`` — including the local LiteLLM proxy and
    direct OpenAI/DeepSeek API calls.
    """

    def __init__(self, endpoint_config: dict, model_id: str, api_key: str):
        super().__init__(endpoint_config, model_id, api_key)
        self._client = OpenAI(
            api_key=api_key,
            base_url=endpoint_config["url"],
        )

    @property
    def backend_type(self) -> str:
        return "openai"

    def generate(
        self,
        messages: list,
        max_tokens: int,
        temperature: float,
        **kwargs,
    ) -> dict:
        """Call the OpenAI Chat Completions endpoint and normalise the response.

        Returns:
            Uniform dict with ``content``, ``prompt_tokens``,
            ``completion_tokens``, and ``raw_response``.
        """
        response = self._client.chat.completions.create(
            model=self._model_id,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            **kwargs,
        )

        choice = response.choices[0]
        usage = response.usage

        return {
            "content": choice.message.content,
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "raw_response": response,
        }
