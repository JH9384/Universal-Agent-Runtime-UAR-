"""Hugging Face integration skills.

Provides skills for interacting with Hugging Face Inference API:
  - huggingface_chat       : Chat with HF models
  - huggingface_completion : Text completion with HF models
  - huggingface_embedding : Generate embeddings with HF

Hugging Face provides access to 200+ open-source models via  # noqa
their Inference API and serverless GPU endpoints.

Configure via env:
  HF_API_KEY          — Hugging Face API token (required for some models)
  HF_MODEL            — Default model (default: meta-llama/Llama-3.3-70B-Instruct)
  HF_TIMEOUT_SEC      — Request timeout in seconds (default: 30)

Goal metadata overrides:
  huggingface_model   — per-run model override
  huggingface_temperature — per-run temperature override (0-1)
  huggingface_max_tokens  — per-run max tokens override
"""  # noqa: E501

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
    """Get or create OpenAI client configured for HF Inference."""
    if not OPENAI_AVAILABLE:
        return None

    api_key = os.getenv("HF_API_KEY")
    if not api_key:
        logger.warning("HF_API_KEY not set (may be required for some models)")

    base_url = "https://api-inference.huggingface.co/v1"
    timeout = int(os.getenv("HF_TIMEOUT_SEC", "30"))

    return openai.OpenAI(
        base_url=base_url,
        api_key=api_key,
        timeout=timeout,
    )


def _get_model(ctx: PipelineContext | None = None) -> str:
    """Get model from goal metadata override or environment."""
    if ctx and ctx.goal.metadata:
        override_model = ctx.goal.metadata.get("huggingface_model")
        if override_model:
            return override_model
    return os.getenv("HF_MODEL", "meta-llama/Llama-3.3-70B-Instruct")


def _get_temperature(ctx: PipelineContext | None = None) -> float:
    """Get temperature from goal metadata override or default."""
    if ctx and ctx.goal.metadata:
        temp = ctx.goal.metadata.get("huggingface_temperature")
        if temp is not None:
            try:
                value = float(temp)
                return max(0.0, min(1.0, value))
            except (ValueError, TypeError):
                logger.warning(
                    "Invalid huggingface_temperature value, using default"
                )
    return 0.7


def _get_max_tokens(ctx: PipelineContext | None = None) -> int:
    """Get max tokens from goal metadata override or default."""
    if ctx and ctx.goal.metadata:
        tokens = ctx.goal.metadata.get("huggingface_max_tokens")
        if tokens is not None:
            try:
                value = int(tokens)
                return max(1, min(100000, value))
            except (ValueError, TypeError):
                logger.warning(
                    "Invalid huggingface_max_tokens value, using default"
                )
    return 1000


@register_skill("huggingface_chat")
def huggingface_chat(ctx: PipelineContext) -> Dict[str, Any]:
    """Chat with Hugging Face models.

    Sends a chat completion request to HF's OpenAI-compatible API.
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
            "error": "HF client not available (install openai package)",  # noqa
        }

    meta = ctx.goal.metadata or {}
    messages = meta.get("messages", [])

    if not messages:
        messages = [{"role": "user", "content": ctx.goal.objective}]

    try:
        model = _get_model(ctx)
        temperature = _get_temperature(ctx)
        max_tokens = _get_max_tokens(ctx)

        logger.info("Calling HF chat with model %s", model)

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
    except Exception as e:
        logger.exception("huggingface_chat failed")
        return {
            "status": "failed",
            "error": str(e),
            "model": _get_model(ctx),
        }


@register_skill("huggingface_completion")
def huggingface_completion(ctx: PipelineContext) -> Dict[str, Any]:
    """Text completion with Hugging Face models.

    Sends a text completion request to HF's OpenAI-compatible API.

    Args:
        ctx: Pipeline context containing goal with prompt

    Returns:
        Dictionary with completion text and metadata
    """
    client = _get_client()

    if client is None:
        return {
            "status": "failed",
            "error": "HF client not available (install openai package)",  # noqa
        }

    meta = ctx.goal.metadata or {}
    prompt = meta.get("prompt", ctx.goal.objective)

    try:
        model = _get_model(ctx)
        temperature = _get_temperature(ctx)
        max_tokens = _get_max_tokens(ctx)

        logger.info("Calling HF completion with model %s", model)

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
    except Exception as e:
        logger.exception("huggingface_completion failed")
        return {
            "status": "failed",
            "error": str(e),
            "model": _get_model(ctx),
        }


@register_skill("huggingface_embedding")
def huggingface_embedding(ctx: PipelineContext) -> Dict[str, Any]:
    """Generate embeddings using Hugging Face.

    Generates vector embeddings for the given text using HF's
    feature extraction API.

    Args:
        ctx: Pipeline context containing goal with text to embed

    Returns:
        Dictionary with embedding vector and metadata
    """
    client = _get_client()

    if client is None:
        return {
            "status": "failed",
            "error": "HF client not available (install openai package)",
        }

    meta = ctx.goal.metadata or {}
    text = meta.get("text", ctx.goal.objective)
    embedding_model = meta.get(
        "embedding_model", "sentence-transformers/all-MiniLM-L6-v2"
    )

    try:
        logger.info("Calling HF embedding with model %s", embedding_model)

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
                "prompt_tokens": response.usage.prompt_tokens
                if response.usage
                else 0,  # noqa
                "total_tokens": response.usage.total_tokens
                if response.usage
                else 0,  # noqa
            },
        }
    except Exception as e:
        logger.exception("huggingface_embedding failed")
        return {
            "status": "failed",
            "error": str(e),
            "model": embedding_model,
        }
