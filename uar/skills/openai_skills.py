"""OpenAI integration skills.

Provides skills for interacting with OpenAI's API:
  - openai_chat       : Chat with GPT models (gpt-4, gpt-3.5-turbo, etc.)
  - openai_completion : Text completion with OpenAI models
  - openai_embedding : Generate embeddings for text

Configure via env:
  OPENAI_API_KEY      — OpenAI API key (required)
  OPENAI_MODEL        — Default model (default: gpt-3.5-turbo)
  OPENAI_TIMEOUT_SEC  — Request timeout in seconds (default: 30)

Goal metadata overrides:
  openai_model        — per-run model override
  openai_temperature  — per-run temperature override (0-2)
  openai_max_tokens   — per-run max tokens override
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

logger = logging.getLogger(__name__)


def _get_client() -> Any:
    """Get or create OpenAI client."""
    if not OPENAI_AVAILABLE:
        return None

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.warning("OPENAI_API_KEY not set")
        return None

    timeout = int(os.getenv("OPENAI_TIMEOUT_SEC", "30"))
    return openai.OpenAI(api_key=api_key, timeout=timeout)


def _get_model(ctx: PipelineContext | None = None) -> str:
    """Get model from goal metadata override or environment."""
    if ctx and ctx.goal.metadata:
        override_model = ctx.goal.metadata.get("openai_model")
        if override_model:
            return override_model
    return os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")


def _get_temperature(ctx: PipelineContext | None = None) -> float:
    """Get temperature from goal metadata override or default."""
    if ctx and ctx.goal.metadata:
        temp = ctx.goal.metadata.get("openai_temperature")
        if temp is not None:
            try:
                value = float(temp)
                # Clamp temperature to valid range (0-2 for most models)
                return max(0.0, min(2.0, value))
            except (ValueError, TypeError):
                logger.warning(
                    "Invalid openai_temperature value, using default"
                )
    return 0.7


def _get_max_tokens(ctx: PipelineContext | None = None) -> int:
    """Get max tokens from goal metadata override or default."""
    if ctx and ctx.goal.metadata:
        tokens = ctx.goal.metadata.get("openai_max_tokens")
        if tokens is not None:
            try:
                value = int(tokens)
                # Ensure max_tokens is positive and reasonable
                return max(1, min(100000, value))
            except (ValueError, TypeError):
                logger.warning(
                    "Invalid openai_max_tokens value, using default"
                )
    return 1000


@register_skill("openai_chat")
def openai_chat(ctx: PipelineContext) -> Dict[str, Any]:
    """Chat with OpenAI GPT models.

    Sends a chat completion request to OpenAI's API. Supports system
    messages, conversation history, and various model parameters.

    Args:
        ctx: Pipeline context containing goal with messages

    Returns:
        Dictionary with chat response and metadata
    """
    client = _get_client()

    if client is None:
        return {
            "status": "failed",
            "error": "OpenAI client not available (install openai package and set OPENAI_API_KEY)"  # noqa
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

        logger.info("Calling OpenAI chat with model %s", model)

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
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
        }
    except Exception as e:
        logger.exception("openai_chat failed")
        return {
            "status": "failed",
            "error": str(e),
            "model": _get_model(ctx),
        }


@register_skill("openai_completion")
def openai_completion(ctx: PipelineContext) -> Dict[str, Any]:
    """Text completion with OpenAI models.

    Sends a text completion request to OpenAI's API using legacy
    completion endpoint (useful for non-chat models).

    Args:
        ctx: Pipeline context containing goal with prompt

    Returns:
        Dictionary with completion text and metadata
    """
    client = _get_client()

    if client is None:
        return {
            "status": "failed",
            "error": "OpenAI client not available (install openai package and set OPENAI_API_KEY)"  # noqa
        }

    meta = ctx.goal.metadata or {}
    prompt = meta.get("prompt", ctx.goal.objective)

    try:
        model = _get_model(ctx)
        temperature = _get_temperature(ctx)
        max_tokens = _get_max_tokens(ctx)

        logger.info("Calling OpenAI completion with model %s", model)

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
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
        }
    except Exception as e:
        logger.exception("openai_completion failed")
        return {
            "status": "failed",
            "error": str(e),
            "model": _get_model(ctx),
        }


@register_skill("openai_embedding")
def openai_embedding(ctx: PipelineContext) -> Dict[str, Any]:
    """Generate embeddings for text using OpenAI.

    Generates vector embeddings for the given text using OpenAI's
    embedding models (text-embedding-ada-002, text-embedding-3-small, etc.).

    Args:
        ctx: Pipeline context containing goal with text to embed

    Returns:
        Dictionary with embedding vector and metadata
    """
    client = _get_client()

    if client is None:
        return {
            "status": "failed",
            "error": "OpenAI client not available (install openai package and set OPENAI_API_KEY)"  # noqa
        }

    meta = ctx.goal.metadata or {}
    text = meta.get("text", ctx.goal.objective)
    embedding_model = meta.get("embedding_model", "text-embedding-3-small")

    try:
        logger.info("Calling OpenAI embedding with model %s", embedding_model)

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
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "total_tokens": response.usage.total_tokens,
            },
        }
    except Exception as e:
        logger.exception("openai_embedding failed")
        return {
            "status": "failed",
            "error": str(e),
            "model": embedding_model,
        }
