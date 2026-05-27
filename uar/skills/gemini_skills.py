"""Google Gemini integration skills.

Provides skills for interacting with Google's Gemini API:
  - gemini_chat       : Chat with Gemini models (Pro, Flash, Flash-Lite)
  - gemini_completion : Text completion with Gemini models
  - gemini_embedding : Generate embeddings with Gemini

Configure via env:
  GEMINI_API_KEY      — Google API key (required)
  GEMINI_MODEL        — Default model (default: gemini-2.0-flash-exp)
  GEMINI_TIMEOUT_SEC — Request timeout in seconds (default: 30)

Goal metadata overrides:
  gemini_model        — per-run model override
  gemini_temperature  — per-run temperature override (0-2)
  gemini_max_tokens   — per-run max tokens override
"""

from __future__ import annotations

import logging
import os
from typing import Dict, Any

try:
    import google.generativeai as genai

    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    genai = None  # type: ignore

from uar.core.registry import register_skill
from uar.core.contracts import PipelineContext
from uar.core.circuit_breaker_decorator import with_circuit_breaker

logger = logging.getLogger(__name__)

# Cache for the configured API key to avoid repeated global state mutations
_gemini_configured_key: str | None = None


def _get_client() -> Any:
    """Get or create Gemini client."""
    if not GEMINI_AVAILABLE:
        return None

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.warning("GEMINI_API_KEY not set")
        return None

    global _gemini_configured_key
    # Only configure if the API key has changed
    if _gemini_configured_key != api_key:
        genai.configure(api_key=api_key)
        _gemini_configured_key = api_key

    return genai


def _get_model(ctx: PipelineContext | None = None) -> str:
    """Get model from goal metadata override or environment."""
    if ctx and ctx.goal.metadata:
        override_model = ctx.goal.metadata.get("gemini_model")
        if override_model:
            return override_model
    return os.getenv("GEMINI_MODEL", "gemini-2.0-flash-exp")


def _get_temperature(ctx: PipelineContext | None = None) -> float:
    """Get temperature from goal metadata override or default."""
    if ctx and ctx.goal.metadata:
        temp = ctx.goal.metadata.get("gemini_temperature")
        if temp is not None:
            try:
                value = float(temp)
                return max(0.0, min(2.0, value))
            except (ValueError, TypeError):
                logger.warning(
                    "Invalid gemini_temperature value, using default"
                )
    return 0.7


def _get_max_tokens(ctx: PipelineContext | None = None) -> int:
    """Get max tokens from goal metadata override or default."""
    if ctx and ctx.goal.metadata:
        tokens = ctx.goal.metadata.get("gemini_max_tokens")
        if tokens is not None:
            try:
                value = int(tokens)
                return max(1, min(100000, value))
            except (ValueError, TypeError):
                logger.warning(
                    "Invalid gemini_max_tokens value, using default"
                )
    return 1000


@register_skill("gemini_chat")
@with_circuit_breaker("gemini", failure_threshold=5, recovery_timeout=60.0)
def gemini_chat(ctx: PipelineContext) -> Dict[str, Any]:
    """Chat with Google Gemini models.

    Sends a message to Gemini models for chat. Supports conversation
    history and system instructions.

    Args:
        ctx: Pipeline context containing goal with messages

    Returns:
        Dictionary with chat response and metadata
    """
    if not GEMINI_AVAILABLE:
        return {
            "status": "failed",
            "error": (  # noqa
                "Gemini client not available (install google-generativeai package and set GEMINI_API_KEY)"  # noqa
            ),
        }

    if not os.getenv("GEMINI_API_KEY"):
        return {"status": "failed", "error": "GEMINI_API_KEY not set"}

    meta = ctx.goal.metadata or {}
    messages = meta.get("messages", [])
    system_instruction = meta.get("system_instruction", "")

    if not messages:
        messages = [ctx.goal.objective]

    try:
        model_name = _get_model(ctx)
        temperature = _get_temperature(ctx)
        max_tokens = _get_max_tokens(ctx)

        logger.info("Calling Gemini with model %s", model_name)

        model = genai.GenerativeModel(  # noqa
            model_name=model_name,
            system_instruction=system_instruction
            if system_instruction
            else None,  # noqa
            generation_config=genai.GenerationConfig(  # noqa
                temperature=temperature,
                max_output_tokens=max_tokens,
            ),
        )

        # Convert messages to Gemini format
        gemini_messages = []  # noqa
        for msg in messages:
            if isinstance(msg, str):
                gemini_messages.append({"role": "user", "parts": [msg]})
            elif isinstance(msg, dict):
                gemini_messages.append(msg)

        # Validate message format before accessing
        if (
            not gemini_messages
            or not gemini_messages[-1].get("parts")
            or not gemini_messages[-1]["parts"]
        ):
            return {
                "status": "failed",
                "error": (
                    "Invalid message format: missing or empty parts array"
                ),
                "model": model_name,
            }

        chat = model.start_chat(history=gemini_messages[:-1])  # noqa
        response = chat.send_message(gemini_messages[-1]["parts"][0])

        if not response.text:
            return {
                "status": "failed",
                "error": "API returned empty response text",
                "model": model_name,
            }

        return {
            "status": "completed",
            "model": model_name,
            "message": response.text,
            "usage": {
                "prompt_tokens": response.usage_metadata.prompt_token_count
                if response.usage_metadata
                else 0,  # noqa
                "output_tokens": response.usage_metadata.candidates_token_count
                if response.usage_metadata
                else 0,  # noqa
                "total_tokens": response.usage_metadata.total_token_count
                if response.usage_metadata
                else 0,  # noqa
            },
        }
    except Exception:
        logger.exception("gemini_chat failed")
        return {
            "status": "failed",
            "error": "Chat request failed",
            "model": _get_model(ctx),
        }


@register_skill("gemini_completion")
@with_circuit_breaker("gemini", failure_threshold=5, recovery_timeout=60.0)
def gemini_completion(ctx: PipelineContext) -> Dict[str, Any]:
    """Text completion with Google Gemini models.

    Sends a completion request to Gemini models for text generation.

    Args:
        ctx: Pipeline context containing goal with prompt

    Returns:
        Dictionary with completion text and metadata
    """
    if not GEMINI_AVAILABLE:
        return {
            "status": "failed",
            "error": (  # noqa
                "Gemini client not available (install google-generativeai package and set GEMINI_API_KEY)"  # noqa
            ),
        }

    if not os.getenv("GEMINI_API_KEY"):
        return {"status": "failed", "error": "GEMINI_API_KEY not set"}

    meta = ctx.goal.metadata or {}
    prompt = meta.get("prompt", ctx.goal.objective)

    try:
        model_name = _get_model(ctx)
        temperature = _get_temperature(ctx)
        max_tokens = _get_max_tokens(ctx)

        logger.info("Calling Gemini completion with model %s", model_name)

        model = genai.GenerativeModel(
            model_name=model_name,
            generation_config=genai.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            ),
        )

        response = model.generate_content(prompt)

        if not response.text:
            return {
                "status": "failed",
                "error": "API returned empty response text",
                "model": model_name,
            }

        return {
            "status": "completed",
            "model": model_name,
            "text": response.text,
            "usage": {
                "prompt_tokens": response.usage_metadata.prompt_token_count
                if response.usage_metadata
                else 0,  # noqa
                "output_tokens": response.usage_metadata.candidates_token_count
                if response.usage_metadata
                else 0,  # noqa
                "total_tokens": response.usage_metadata.total_token_count
                if response.usage_metadata
                else 0,  # noqa
            },
        }
    except Exception:
        logger.exception("gemini_completion failed")
        return {
            "status": "failed",
            "error": "Completion request failed",
            "model": _get_model(ctx),
        }


@register_skill("gemini_embedding")
@with_circuit_breaker("gemini", failure_threshold=5, recovery_timeout=60.0)
def gemini_embedding(ctx: PipelineContext) -> Dict[str, Any]:
    """Generate embeddings using Google Gemini.

    Generates vector embeddings for the given text using Gemini's
    embedding models (text-embedding-004, etc.).

    Args:
        ctx: Pipeline context containing goal with text to embed

    Returns:
        Dictionary with embedding vector and metadata
    """
    if not GEMINI_AVAILABLE:
        return {
            "status": "failed",
            "error": (  # noqa
                "Gemini client not available (install google-generativeai package and set GEMINI_API_KEY)"  # noqa
            ),
        }

    if not os.getenv("GEMINI_API_KEY"):
        return {"status": "failed", "error": "GEMINI_API_KEY not set"}

    meta = ctx.goal.metadata or {}
    text = meta.get("text", ctx.goal.objective)
    embedding_model = meta.get("embedding_model", "text-embedding-004")

    try:
        logger.info("Calling Gemini embedding with model %s", embedding_model)

        result = genai.embed_content(
            model=f"models/{embedding_model}",
            content=text,
            task_type="retrieval_document",
        )

        return {
            "status": "completed",
            "model": embedding_model,
            "embedding": result.embedding,
            "dimensions": len(result.embedding),
        }
    except Exception:
        logger.exception("gemini_embedding failed")
        return {
            "status": "failed",
            "error": "Embedding request failed",
            "model": embedding_model,
        }
