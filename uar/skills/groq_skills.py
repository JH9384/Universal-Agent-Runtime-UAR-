"""Groq integration skills.

Provides skills for interacting with Groq's fast inference API:
  - groq_chat       : Chat with Groq-hosted models (Llama, Mixtral, etc.)
  - groq_completion : Text completion with Groq models
  - groq_embedding : Generate embeddings with Groq

Groq provides ultra-fast inference using LPU technology and
an OpenAI-compatible API.

Configure via env:
  GROQ_API_KEY       — Groq API key (required)
  GROQ_MODEL         — Default model (default: llama-3.3-70b-versatile)
  GROQ_TIMEOUT_SEC  — Request timeout in seconds (default: 30)

Goal metadata overrides:
  groq_model        — per-run model override
  groq_temperature  — per-run temperature override (0-2)
  groq_max_tokens   — per-run max tokens override
"""

from __future__ import annotations

import logging
import os
from typing import Dict, Any

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    openai = None  # type: ignore

from uar.core.registry import register_skill
from uar.core.contracts import PipelineContext
from uar.core.circuit_breaker_decorator import with_circuit_breaker

logger = logging.getLogger(__name__)


def _get_client() -> Any:
    """Get or create OpenAI client configured for Groq."""
    if not OPENAI_AVAILABLE:
        return None

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        logger.warning("GROQ_API_KEY not set")
        return None

    timeout = int(os.getenv("GROQ_TIMEOUT_SEC", "30"))
    return openai.OpenAI(
        base_url="https://api.groq.com/openai/v1",
        api_key=api_key,
        timeout=timeout,
    )


def _get_model(ctx: PipelineContext | None = None) -> str:
    """Get model from goal metadata override or environment."""
    if ctx and ctx.goal.metadata:
        override_model = ctx.goal.metadata.get("groq_model")
        if override_model:
            return override_model
    return os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")


def _get_temperature(ctx: PipelineContext | None = None) -> float:
    """Get temperature from goal metadata override or default."""
    if ctx and ctx.goal.metadata:
        temp = ctx.goal.metadata.get("groq_temperature")
        if temp is not None:
            try:
                value = float(temp)
                return max(0.0, min(2.0, value))
            except (ValueError, TypeError):
                logger.warning(
                    "Invalid groq_temperature value, using default"
                )
    return 0.7


def _get_max_tokens(ctx: PipelineContext | None = None) -> int:
    """Get max tokens from goal metadata override or default."""
    if ctx and ctx.goal.metadata:
        tokens = ctx.goal.metadata.get("groq_max_tokens")
        if tokens is not None:
            try:
                value = int(tokens)
                return max(1, min(100000, value))
            except (ValueError, TypeError):
                logger.warning(
                    "Invalid groq_max_tokens value, using default"
                )
    return 1000


@register_skill("groq_chat")
@with_circuit_breaker("groq", failure_threshold=5, recovery_timeout=60.0)
def groq_chat(ctx: PipelineContext) -> Dict[str, Any]:
    """Chat with Groq-hosted models.

    Sends a chat completion request to Groq's OpenAI-compatible API.
    Supports conversation history and various model parameters.

    Args:
        ctx: Pipeline context containing goal with messages

    Returns:
        Dictionary with chat response and metadata
    """
    client = _get_client()

    if client is None:
        return {
            "status": "failed",
            "error": "Groq client not available (install openai package and set GROQ_API_KEY)"  # noqa
        }

    meta = ctx.goal.metadata or {}
    messages = meta.get("messages", [])

    if not messages:
        messages = [{"role": "user", "content": ctx.goal.objective}]

    try:
        model = _get_model(ctx)
        temperature = _get_temperature(ctx)
        max_tokens = _get_max_tokens(ctx)

        logger.info("Calling Groq chat with model %s", model)

        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        if not response.choices:
            return {
                "status": "failed",
                "error": "API returned empty choices array",
                "model": model,
            }

        return {
            "status": "completed",
            "model": model,
            "message": response.choices[0].message.content,
            "finish_reason": response.choices[0].finish_reason,
            "usage": {  # noqa
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,  # noqa
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,  # noqa
                "total_tokens": response.usage.total_tokens if response.usage else 0,  # noqa
            },
        }
    except Exception as e:
        logger.exception("groq_chat failed")
        return {
            "status": "failed",
            "error": str(e),
            "model": _get_model(ctx),
        }


@register_skill("groq_completion")
@with_circuit_breaker("groq", failure_threshold=5, recovery_timeout=60.0)
def groq_completion(ctx: PipelineContext) -> Dict[str, Any]:
    """Text completion with Groq-hosted models.

    Sends a text completion request to Groq's OpenAI-compatible API.

    Args:
        ctx: Pipeline context containing goal with prompt

    Returns:
        Dictionary with completion text and metadata
    """
    client = _get_client()

    if client is None:
        return {
            "status": "failed",
            "error": "Groq client not available (install openai package and set GROQ_API_KEY)"  # noqa
        }

    meta = ctx.goal.metadata or {}
    prompt = meta.get("prompt", ctx.goal.objective)

    try:
        model = _get_model(ctx)
        temperature = _get_temperature(ctx)
        max_tokens = _get_max_tokens(ctx)

        logger.info("Calling Groq completion with model %s", model)

        response = client.completions.create(
            model=model,
            prompt=prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        if not response.choices:
            return {
                "status": "failed",
                "error": "API returned empty choices array",
                "model": model,
            }

        return {
            "status": "completed",
            "model": model,
            "text": response.choices[0].text,
            "finish_reason": response.choices[0].finish_reason,
            "usage": {  # noqa
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,  # noqa
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,  # noqa
                "total_tokens": response.usage.total_tokens if response.usage else 0,  # noqa
            },
        }
    except Exception as e:
        logger.exception("groq_completion failed")
        return {
            "status": "failed",
            "error": str(e),
            "model": _get_model(ctx),
        }


@register_skill("groq_embedding")
@with_circuit_breaker("groq", failure_threshold=5, recovery_timeout=60.0)
def groq_embedding(ctx: PipelineContext) -> Dict[str, Any]:
    """Generate embeddings using Groq.

    Generates vector embeddings for the given text using Groq's
    embedding models (if supported).

    Args:
        ctx: Pipeline context containing goal with text to embed

    Returns:
        Dictionary with embedding vector and metadata
    """
    client = _get_client()

    if client is None:
        return {
            "status": "failed",
            "error": "Groq client not available (install openai package and set GROQ_API_KEY)"  # noqa
        }

    meta = ctx.goal.metadata or {}
    text = meta.get("text", ctx.goal.objective)
    embedding_model = meta.get("embedding_model", "")

    # Use a sensible default if no embedding model specified
    if not embedding_model:
        return {
            "status": "failed",
            "error": (
                "No embedding model specified. "
                "Groq does not currently provide a dedicated embedding API. "
                "Please use a different provider for embeddings."
            ),
        }

    try:
        logger.info("Calling Groq embedding with model %s", embedding_model)

        response = client.embeddings.create(
            model=embedding_model,
            input=text,
        )

        if not response.data:
            return {
                "status": "failed",
                "error": "API returned empty data array",
                "model": embedding_model,
            }

        return {
            "status": "completed",
            "model": embedding_model,
            "embedding": response.data[0].embedding,
            "dimensions": len(response.data[0].embedding),
            "usage": {  # noqa
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,  # noqa
                "total_tokens": response.usage.total_tokens if response.usage else 0,  # noqa
            },
        }
    except Exception as e:
        logger.exception("groq_embedding failed")
        return {
            "status": "failed",
            "error": str(e),
            "model": embedding_model,
            "note": "Ensure the selected Groq model supports embeddings",
        }
