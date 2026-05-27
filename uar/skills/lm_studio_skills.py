"""LM Studio integration skills.

Provides skills for interacting with LM Studio's local LLM server:
  - lm_studio_chat       : Chat with local LLM models via LM Studio
  - lm_studio_completion : Text completion with LM Studio models
  - lm_studio_embedding : Generate embeddings (if supported by model)

LM Studio provides an OpenAI-compatible API running locally.

Configure via env:
  LM_STUDIO_HOST       — LM Studio host (default: localhost)
  LM_STUDIO_PORT       — LM Studio port (default: 1234)
  LM_STUDIO_MODEL      — Default model name
  LM_STUDIO_TIMEOUT_SEC — Request timeout in seconds (default: 30)

Goal metadata overrides:
  lm_studio_model      — per-run model override
  lm_studio_temperature — per-run temperature override (0-2)
  lm_studio_max_tokens  — per-run max tokens override
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
    """Get or create OpenAI client configured for LM Studio."""
    if not OPENAI_AVAILABLE:
        return None

    host = os.getenv("LM_STUDIO_HOST", "localhost")
    port = os.getenv("LM_STUDIO_PORT", "1234")
    base_url = f"http://{host}:{port}/v1"

    timeout = max(
        1, int(os.getenv("LM_STUDIO_TIMEOUT_SEC", "30").strip() or "30")
    )
    return openai.OpenAI(
        base_url=base_url,
        api_key="not-needed",  # LM Studio doesn't require API key
        timeout=timeout,
    )


def _get_model(ctx: PipelineContext | None = None) -> str:
    """Get model from goal metadata override or environment."""
    if ctx and ctx.goal.metadata:
        override_model = ctx.goal.metadata.get("lm_studio_model")
        if override_model:
            return override_model
    return os.getenv("LM_STUDIO_MODEL", "local-model")


def _get_temperature(ctx: PipelineContext | None = None) -> float:
    """Get temperature from goal metadata override or default."""
    if ctx and ctx.goal.metadata:
        temp = ctx.goal.metadata.get("lm_studio_temperature")
        if temp is not None:
            try:
                value = float(temp)
                return max(0.0, min(2.0, value))
            except (ValueError, TypeError):
                logger.warning(
                    "Invalid lm_studio_temperature value, using default"
                )
    return 0.7


def _get_max_tokens(ctx: PipelineContext | None = None) -> int:
    """Get max tokens from goal metadata override or default."""
    if ctx and ctx.goal.metadata:
        tokens = ctx.goal.metadata.get("lm_studio_max_tokens")
        if tokens is not None:
            try:
                value = int(tokens)
                return max(1, min(100000, value))
            except (ValueError, TypeError):
                logger.warning(
                    "Invalid lm_studio_max_tokens value, using default"
                )
    return 1000


@register_skill("lm_studio_chat")
@with_circuit_breaker("lm_studio", failure_threshold=5, recovery_timeout=60.0)
def lm_studio_chat(ctx: PipelineContext) -> Dict[str, Any]:
    """Chat with local LLM models via LM Studio.

    Sends a chat completion request to LM Studio's OpenAI-compatible API.
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
            "error": "OpenAI client not available (install openai package)",
        }

    meta = ctx.goal.metadata or {}
    messages = meta.get("messages", [])

    if not messages:
        # If no messages provided, use the goal as a user message
        messages = [{"role": "user", "content": ctx.goal.objective}]

    try:
        model = _get_model(ctx)
        temperature = _get_temperature(ctx)
        max_tokens = _get_max_tokens(ctx)

        host = os.getenv("LM_STUDIO_HOST", "localhost")
        port = os.getenv("LM_STUDIO_PORT", "1234")
        logger.info(  # noqa
            "Calling LM Studio chat at %s:%s with model %s", host, port, model
        )

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
                "prompt_tokens": response.usage.prompt_tokens
                if response.usage
                else 0,  # noqa
                "completion_tokens": response.usage.completion_tokens
                if response.usage
                else 0,  # noqa
                "total_tokens": response.usage.total_tokens
                if response.usage
                else 0,  # noqa
            },
        }
    except Exception:
        logger.exception("lm_studio_chat failed")
        return {
            "status": "failed",
            "error": "Chat request failed",
            "model": _get_model(ctx),
        }


@register_skill("lm_studio_completion")
@with_circuit_breaker("lm_studio", failure_threshold=5, recovery_timeout=60.0)
def lm_studio_completion(ctx: PipelineContext) -> Dict[str, Any]:
    """Text completion with LM Studio models.

    Sends a text completion request to LM Studio's OpenAI-compatible API.

    Args:
        ctx: Pipeline context containing goal with prompt

    Returns:
        Dictionary with completion text and metadata
    """
    client = _get_client()

    if client is None:
        return {
            "status": "failed",
            "error": "OpenAI client not available (install openai package)",
        }

    meta = ctx.goal.metadata or {}
    prompt = meta.get("prompt", ctx.goal.objective)

    try:
        model = _get_model(ctx)
        temperature = _get_temperature(ctx)
        max_tokens = _get_max_tokens(ctx)

        host = os.getenv("LM_STUDIO_HOST", "localhost")
        port = os.getenv("LM_STUDIO_PORT", "1234")
        logger.info(  # noqa
            "Calling LM Studio completion at %s:%s with model %s",
            host,
            port,
            model,
        )

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
                "prompt_tokens": response.usage.prompt_tokens
                if response.usage
                else 0,  # noqa
                "completion_tokens": response.usage.completion_tokens
                if response.usage
                else 0,  # noqa
                "total_tokens": response.usage.total_tokens
                if response.usage
                else 0,  # noqa
            },
        }
    except Exception:
        logger.exception("lm_studio_completion failed")
        return {
            "status": "failed",
            "error": "Completion request failed",
            "model": _get_model(ctx),
        }


@register_skill("lm_studio_embedding")
@with_circuit_breaker("lm_studio", failure_threshold=5, recovery_timeout=60.0)
def lm_studio_embedding(ctx: PipelineContext) -> Dict[str, Any]:
    """Generate embeddings for text using LM Studio.

    Generates vector embeddings for the given text using LM Studio's
    embedding endpoint (if the loaded model supports embeddings).

    Args:
        ctx: Pipeline context containing goal with text to embed

    Returns:
        Dictionary with embedding vector and metadata
    """
    client = _get_client()

    if client is None:
        return {
            "status": "failed",
            "error": "OpenAI client not available (install openai package)",
        }

    meta = ctx.goal.metadata or {}
    text = meta.get("text", ctx.goal.objective)

    try:
        host = os.getenv("LM_STUDIO_HOST", "localhost")
        port = os.getenv("LM_STUDIO_PORT", "1234")
        logger.info(  # noqa
            "Calling LM Studio embedding at %s:%s", host, port
        )

        response = client.embeddings.create(
            model=_get_model(ctx),
            input=text,
        )

        if not response.data:
            return {
                "status": "failed",
                "error": "API returned empty data array",
                "model": _get_model(ctx),
            }

        return {
            "status": "completed",
            "model": response.model,
            "embedding": response.data[0].embedding,
            "dimensions": len(response.data[0].embedding),
            "usage": {  # noqa
                "prompt_tokens": response.usage.prompt_tokens
                if response.usage
                else 0,  # noqa
                "total_tokens": response.usage.total_tokens
                if response.usage
                else 0,  # noqa
            },
        }
    except Exception:
        logger.exception("lm_studio_embedding failed")
        return {
            "status": "failed",
            "error": "Embedding request failed",
            "note": "Ensure the loaded LM Studio model supports embeddings",
        }
