"""Teacher API backends — OpenAI and Anthropic SDK integrations."""

from distill.backends.base import TeacherBackend
from distill.backends.openai_backend import OpenAIBackend
from distill.backends.anthropic_backend import AnthropicBackend

__all__ = [
    "TeacherBackend",
    "OpenAIBackend",
    "AnthropicBackend",
]
