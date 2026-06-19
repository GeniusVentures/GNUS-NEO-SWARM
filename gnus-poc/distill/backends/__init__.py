"""Teacher API backends — OpenAI and Anthropic SDK integrations."""

from distill.backends.base import TeacherBackend
from distill.backends.openai_backend import OpenAIBackend

# AnthropicBackend imported after creation in Task 2
__all__ = [
    "TeacherBackend",
    "OpenAIBackend",
]
