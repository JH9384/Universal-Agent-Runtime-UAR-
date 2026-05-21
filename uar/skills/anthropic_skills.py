"""Anthropic Claude integration skills.

Provides skills for interacting with Anthropic's Claude API:
  - anthropic_chat       : Chat with Claude models (Opus, Sonnet, Haiku)
  - anthropic_completion : Text completion with Claude models
  - anthropic_embedding : Generate embeddings (if supported)

Configure via env:
  ANTHROPIC_API_KEY     — Anthropic API key (required)
  ANTHROPIC_MODEL       — Default model (default: claude-3-5-sonnet-20241022)
  ANTHROPIC_TIMEOUT_SEC — Request timeout in seconds (default: 30)

Goal metadata overrides:
  anthropic_model       — per-run model override
  anthropic_temperature — per-run temperature override (0-1)
  anthropic_max_tokens  — per-run max tokens override
"""

from __future__ import annotations

import logging
import os
from typing import Dict, Any

try:
    import anthropic

    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    anthropic = None  # type: ignore

from uar.core.registry import register_skill
from uar.core.contracts import PipelineContext
from uar.core.circuit_breaker_decorator import with_circuit_breaker

logger = logging.getLogger(__name__)


def _get_client() -> Any:
    """Get or create Anthropic client."""
    if not ANTHROPIC_AVAILABLE:
        return None

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY not set")
        return None

    timeout = int(os.getenv("ANTHROPIC_TIMEOUT_SEC", "30"))
    return anthropic.Anthropic(api_key=api_key, timeout=timeout)


def _get_model(ctx: PipelineContext | None = None) -> str:
    """Get model from goal metadata override or environment."""
    if ctx and ctx.goal.metadata:
        override_model = ctx.goal.metadata.get("anthropic_model")
        if override_model:
            return override_model
    return os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")


def _get_temperature(ctx: PipelineContext | None = None) -> float:
    """Get temperature from goal metadata override or default."""
    if ctx and ctx.goal.metadata:
        temp = ctx.goal.metadata.get("anthropic_temperature")
        if temp is not None:
            try:
                value = float(temp)
                return max(0.0, min(1.0, value))
            except (ValueError, TypeError):
                logger.warning(
                    "Invalid anthropic_temperature value, using default"
                )
    return 0.7


def _get_max_tokens(ctx: PipelineContext | None = None) -> int:
    """Get max tokens from goal metadata override or default."""
    if ctx and ctx.goal.metadata:
        tokens = ctx.goal.metadata.get("anthropic_max_tokens")
        if tokens is not None:
            try:
                value = int(tokens)
                return max(1, min(100000, value))
            except (ValueError, TypeError):
                logger.warning(
                    "Invalid anthropic_max_tokens value, using default"
                )
    return 1000


@register_skill("anthropic_chat")
@with_circuit_breaker("anthropic", failure_threshold=5, recovery_timeout=60.0)
def anthropic_chat(ctx: PipelineContext) -> Dict[str, Any]:
    """Chat with Anthropic Claude models.

    Sends a message to Claude models (Opus, Sonnet, Haiku) for chat.
    Supports system messages and conversation history.

    Args:
        ctx: Pipeline context containing goal with messages

    Returns:
        Dictionary with chat response and metadata
    """
    client = _get_client()

    if client is None:
        return {
            "status": "failed",
            "error": (  # noqa
                "Anthropic client not available (install anthropic package and set ANTHROPIC_API_KEY)"  # noqa
            ),
        }

    meta = ctx.goal.metadata or {}
    messages = meta.get("messages", [])
    system = meta.get("system", "")

    if not messages:
        # If no messages provided, use the goal as a user message
        messages = [{"role": "user", "content": ctx.goal.objective}]

    try:
        model = _get_model(ctx)
        temperature = _get_temperature(ctx)
        max_tokens = _get_max_tokens(ctx)

        logger.info("Calling Anthropic Claude with model %s", model)

        response = client.messages.create(
            model=model,
            system=system,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        if not response.content:
            return {
                "status": "failed",
                "error": "API returned empty content array",
                "model": model,
            }

        return {
            "status": "completed",
            "model": model,
            "message": response.content[0].text,
            "stop_reason": response.stop_reason,
            "usage": {  # noqa
                "input_tokens": response.usage.input_tokens,  # noqa
                "output_tokens": response.usage.output_tokens,  # noqa
                "total_tokens": response.usage.input_tokens
                + response.usage.output_tokens,  # noqa
            },
        }
    except Exception as e:
        logger.exception("anthropic_chat failed")
        return {
            "status": "failed",
            "error": str(e),
            "model": _get_model(ctx),
        }


@register_skill("anthropic_completion")
@with_circuit_breaker("anthropic", failure_threshold=5, recovery_timeout=60.0)
def anthropic_completion(ctx: PipelineContext) -> Dict[str, Any]:
    """Text completion with Anthropic Claude models.

    Sends a completion request to Claude models for text generation.

    Args:
        ctx: Pipeline context containing goal with prompt

    Returns:
        Dictionary with completion text and metadata
    """
    client = _get_client()

    if client is None:
        return {
            "status": "failed",
            "error": (  # noqa
                "Anthropic client not available (install anthropic package and set ANTHROPIC_API_KEY)"  # noqa
            ),
        }

    meta = ctx.goal.metadata or {}
    prompt = meta.get("prompt", ctx.goal.objective)

    try:
        model = _get_model(ctx)
        temperature = _get_temperature(ctx)
        max_tokens = _get_max_tokens(ctx)

        logger.info("Calling Anthropic completion with model %s", model)

        response = client.messages.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
        )

        if not response.content:
            return {
                "status": "failed",
                "error": "API returned empty content array",
                "model": model,
            }

        return {
            "status": "completed",
            "model": model,
            "text": response.content[0].text,
            "stop_reason": response.stop_reason,
            "usage": {  # noqa
                "input_tokens": response.usage.input_tokens,  # noqa
                "output_tokens": response.usage.output_tokens,  # noqa
                "total_tokens": response.usage.input_tokens
                + response.usage.output_tokens,  # noqa
            },
        }
    except Exception as e:
        logger.exception("anthropic_completion failed")
        return {
            "status": "failed",
            "error": str(e),
            "model": _get_model(ctx),
        }


@register_skill("anthropic_embedding")
@with_circuit_breaker("anthropic", failure_threshold=5, recovery_timeout=60.0)
def anthropic_embedding(ctx: PipelineContext) -> Dict[str, Any]:
    """Generate embeddings using Anthropic (if supported).

    Note: Anthropic does not currently provide a public embeddings API.
    This skill is included for future compatibility and will return
    an appropriate error message.

    Args:
        ctx: Pipeline context containing goal with text to embed

    Returns:
        Dictionary with error indicating embeddings not available
    """
    return {
        "status": "failed",
        "error": "Anthropic does not currently provide a public embeddings API",  # noqa
        "note": "Use OpenAI or Hugging Face for embeddings instead",
    }
