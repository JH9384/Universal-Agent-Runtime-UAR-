"""Together AI integration skills.

Provides skills for interacting with Together AI's serverless GPU API:
  - together_chat       : Chat with Together-hosted models
  - together_completion : Text completion with Together models
  - together_embedding : Generate embeddings with Together

Configure via env:
  TOGETHER_API_KEY     — Together API key (required)
  TOGETHER_MODEL       — Default model
  TOGETHER_TIMEOUT_SEC — Request timeout in seconds (default: 30)
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
    name="together",
    module=openai,
    api_key_env="TOGETHER_API_KEY",
    default_model="meta-llama/Llama-3.3-70B-Instruct-Turbo",
    base_url="https://api.together.xyz/v1",
)
