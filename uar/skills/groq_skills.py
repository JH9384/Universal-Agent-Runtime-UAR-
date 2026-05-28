"""Groq integration skills.

Provides skills for interacting with Groq's fast inference API:
  - groq_chat       : Chat with Groq-hosted models
  - groq_completion : Text completion with Groq models
  - groq_embedding : Generate embeddings with Groq

Configure via env:
  GROQ_API_KEY       — Groq API key (required)
  GROQ_MODEL         — Default model (default: llama-3.3-70b-versatile)
  GROQ_TIMEOUT_SEC  — Request timeout in seconds (default: 30)
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
    name="groq",
    module=openai,
    api_key_env="GROQ_API_KEY",
    default_model="llama-3.3-70b-versatile",
    base_url="https://api.groq.com/openai/v1",
)
