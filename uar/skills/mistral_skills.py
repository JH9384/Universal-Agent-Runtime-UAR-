"""Mistral AI integration skills.

Provides skills for interacting with Mistral AI's API:
  - mistral_chat       : Chat with Mistral models
  - mistral_completion : Text completion with Mistral models
  - mistral_embedding : Generate embeddings with Mistral

Configure via env:
  MISTRAL_API_KEY      — Mistral API key (required)
  MISTRAL_MODEL        — Default model (default: mistral-large-latest)
  MISTRAL_TIMEOUT_SEC  — Request timeout in seconds (default: 30)
"""

from __future__ import annotations

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    openai = None  # type: ignore

from uar.skills.llm_base import register_openai_provider

register_openai_provider(
    name="mistral",
    module=openai,
    api_key_env="MISTRAL_API_KEY",
    default_model="mistral-large-latest",
    base_url="https://api.mistral.ai/v1",
    temperature_max=1.0,
)
