"""OpenAI integration skills.

Provides skills for interacting with OpenAI's API:
  - openai_chat       : Chat with GPT models
  - openai_completion : Text completion with OpenAI models
  - openai_embedding : Generate embeddings for text

Configure via env:
  OPENAI_API_KEY      — OpenAI API key (required)
  OPENAI_MODEL        — Default model (default: gpt-3.5-turbo)
  OPENAI_TIMEOUT_SEC  — Request timeout in seconds (default: 30)
"""

from __future__ import annotations

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:  # pragma: no cover
    OPENAI_AVAILABLE = False  # pragma: no cover
    openai = None  # type: ignore  # pragma: no cover

from uar.skills.llm_base import register_openai_provider

register_openai_provider(
    name="openai",
    module=openai,
    api_key_env="OPENAI_API_KEY",
    default_model="gpt-3.5-turbo",
)
