"""Hugging Face integration skills.

Provides skills for interacting with Hugging Face Inference API:
  - huggingface_chat       : Chat with HF models
  - huggingface_completion : Text completion with HF models
  - huggingface_embedding : Generate embeddings with HF

Configure via env:
  HF_API_KEY          — Hugging Face API token (optional for some models)
  HF_MODEL            — Default model
                        (default: meta-llama/Llama-3.3-70B-Instruct)
  HF_TIMEOUT_SEC      — Request timeout in seconds (default: 30)
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
    name="huggingface",
    module=openai,
    api_key_env="HF_API_KEY",
    default_model="meta-llama/Llama-3.3-70B-Instruct",
    base_url="https://api-inference.huggingface.co/v1",
    api_key_required=False,
    temperature_max=1.0,
)
