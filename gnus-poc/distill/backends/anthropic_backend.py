"""Anthropic API backend using the ``anthropic`` Python SDK.

Handles message-format conversion between the OpenAI-style message list
that TeacherClient uses internally and the Anthropic Messages API format
(system as top-level parameter, role restrictions).
"""

from anthropic import Anthropic

from distill.backends.base import TeacherBackend


class AnthropicBackend(TeacherBackend):
    """Teacher backend that talks to the Anthropic Messages API.

    Used for endpoints whose ``apiType`` is ``"anthropic"`` — either a
    direct Anthropic API connection or an Anthropic-compatible proxy.
    """

    def __init__(self, endpoint_config: dict, model_id: str, api_key: str):
        super().__init__(endpoint_config, model_id, api_key)
        kwargs = {"api_key": api_key}
        url = endpoint_config.get("url")
        if url:
            kwargs["base_url"] = url
        self._client = Anthropic(**kwargs)

    @property
    def backend_type(self) -> str:
        return "anthropic"

    # ------------------------------------------------------------------
    # Message conversion — OpenAI list → Anthropic params
    # ------------------------------------------------------------------

    @staticmethod
    def _convert_messages(messages: list) -> dict:
        """Convert an OpenAI-format message list to Anthropic API parameters.

        Args:
            messages: List of dicts with ``role`` and ``content`` keys.
                Roles may be ``"system"``, ``"user"``, or ``"assistant"``.

        Returns:
            dict with keys ``system`` (str or None) and ``messages`` (list
            of ``{"role": ..., "content": ...}`` dicts containing only
            ``"user"`` and ``"assistant"`` roles).
        """
        system_parts = []
        converted = []

        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            if role == "system":
                system_parts.append(content)
            else:
                converted.append({"role": role, "content": content})

        system_prompt = "\n".join(system_parts) if system_parts else None
        return {"system": system_prompt, "messages": converted}

    # ------------------------------------------------------------------
    # Generate
    # ------------------------------------------------------------------

    def generate(
        self,
        messages: list,
        max_tokens: int,
        temperature: float,
        **kwargs,
    ) -> dict:
        """Send a completion via the Anthropic Messages API.

        Converts OpenAI-format messages to Anthropic format, extracts
        the first system message as the top-level ``system`` parameter,
        and normalises the response into the uniform dict.

        Extended thinking (``thinking={"type": "enabled", ...}``) is
        passed through in ``**kwargs`` if supplied.

        Returns:
            Uniform dict with ``content``, ``prompt_tokens``,
            ``completion_tokens``, ``raw_response``.
        """
        converted = self._convert_messages(messages)

        response = self._client.messages.create(
            model=self._model_id,
            system=converted["system"],
            messages=converted["messages"],
            max_tokens=max_tokens,
            temperature=temperature,
            **kwargs,
        )

        # Anthropic returns content as a list of blocks; the first block
        # is typically a text block.  For now we extract the first text.
        content_text = ""
        for block in response.content:
            if hasattr(block, "text"):
                content_text = block.text
                break
            elif isinstance(block, dict) and "text" in block:
                content_text = block["text"]
                break

        usage = response.usage

        return {
            "content": str(content_text),
            "prompt_tokens": int(usage.input_tokens),
            "completion_tokens": int(usage.output_tokens),
            "raw_response": response,
        }
