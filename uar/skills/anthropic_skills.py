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
from typing import Dict, Any

try:
    import anthropic
except ImportError:
    anthropic = None  # type: ignore

from uar.core.registry import register_skill
from uar.core.contracts import PipelineContext
from uar.core.circuit_breaker_decorator import with_circuit_breaker
from uar.core.skill_utils import require_package, skill_guard
from uar.skills.llm_base import (
    make_client_getter,
    make_model_getter,
    make_temperature_getter,
    make_max_tokens_getter,
)

logger = logging.getLogger(__name__)

_get_client = make_client_getter(
    module=anthropic,
    api_key_env="ANTHROPIC_API_KEY",
    timeout_env="ANTHROPIC_TIMEOUT_SEC",
    module_attr="Anthropic",
)
_get_model = make_model_getter(
    prefix="anthropic",
    default_model="claude-3-5-sonnet-20241022",
)
_get_temperature = make_temperature_getter(
    prefix="anthropic",
    default=0.7,
    temp_max=1.0,
)
_get_max_tokens = make_max_tokens_getter(prefix="anthropic")


@register_skill("anthropic_chat")
@skill_guard("Anthropic chat", status="failed")
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
    err = require_package("anthropic")
    if err:
        return err

    client = _get_client()
    if client is None:
        return {"status": "failed", "error": "ANTHROPIC_API_KEY not set"}

    meta = ctx.goal.metadata or {}
    messages = meta.get("messages", [])
    system = meta.get("system", "")

    if not messages:
        # If no messages provided, use the goal as a user message
        messages = [{"role": "user", "content": ctx.goal.objective}]

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


@register_skill("anthropic_completion")
@skill_guard("Anthropic completion", status="failed")
@with_circuit_breaker("anthropic", failure_threshold=5, recovery_timeout=60.0)
def anthropic_completion(ctx: PipelineContext) -> Dict[str, Any]:
    """Text completion with Anthropic Claude models.

    Sends a completion request to Claude models for text generation.

    Args:
        ctx: Pipeline context containing goal with prompt

    Returns:
        Dictionary with completion text and metadata
    """
    err = require_package("anthropic")
    if err:
        return err

    client = _get_client()
    if client is None:
        return {"status": "failed", "error": "ANTHROPIC_API_KEY not set"}

    meta = ctx.goal.metadata or {}
    prompt = meta.get("prompt", ctx.goal.objective)

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


@register_skill("anthropic_embedding")
@skill_guard("Anthropic embedding", status="failed")
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
