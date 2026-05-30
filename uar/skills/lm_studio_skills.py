"""LM Studio integration skills.

Provides skills for interacting with LM Studio's local LLM server:
  - lm_studio_chat       : Chat with local LLM models via LM Studio
  - lm_studio_completion : Text completion with LM Studio models
  - lm_studio_embedding : Generate embeddings (if supported by model)

Configure via env:
  LM_STUDIO_HOST       — LM Studio host (default: localhost)
  LM_STUDIO_PORT       — LM Studio port (default: 1234)
  LM_STUDIO_MODEL      — Default model name
  LM_STUDIO_TIMEOUT_SEC — Request timeout in seconds (default: 30)
"""

from __future__ import annotations
import os

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:  # pragma: no cover
    OPENAI_AVAILABLE = False  # pragma: no cover
    openai = None  # type: ignore  # pragma: no cover

from uar.skills.llm_base import register_openai_provider

_host = os.getenv("LM_STUDIO_HOST", "localhost")
_port = os.getenv("LM_STUDIO_PORT", "1234")
register_openai_provider(
    name="lm_studio",
    module=openai,
    api_key_env="LM_STUDIO_API_KEY",
    default_model="local-model",
    base_url=f"http://{_host}:{_port}/v1",
    extra_client_kwargs={"api_key": "not-needed"},
)
