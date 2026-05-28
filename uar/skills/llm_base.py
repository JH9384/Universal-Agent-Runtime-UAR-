"""Shared helpers for OpenAI-compatible LLM provider skills.

Eliminates the duplicated ``_get_client``, ``_get_model``,
``_get_temperature``, and ``_get_max_tokens`` boilerplate that existed
across every LLM skill module. Also provides a factory for registering
the standard ``*_chat``, ``*_completion``, and ``*_embedding`` skills
for providers that use the OpenAI Python client library.

Usage for an OpenAI-compatible provider::

    from uar.skills.llm_base import register_openai_provider
    import openai

    register_openai_provider(
        name="groq",
        module=openai,               # the Python module providing the client
        api_key_env="GROQ_API_KEY",
        default_model="llama-3.3-70b-versatile",
        base_url="https://api.groq.com/openai/v1",
        temperature_max=2.0,
    )
"""

from __future__ import annotations

import logging
import os
from typing import Any, Callable, Dict, Optional, TypeVar

from uar.core.registry import register_skill
from uar.core.contracts import PipelineContext
from uar.core.circuit_breaker_decorator import with_circuit_breaker

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def _clamp_timeout(raw: str | None, default: str = "30") -> int:
    """Parse and clamp a timeout value to 1..300 seconds."""
    try:
        value = int((raw or default).strip() or default)
    except (ValueError, TypeError):
        value = int(default)
    return max(1, min(300, value))


def make_client_getter(
    *,
    module: Any,
    api_key_env: str,
    timeout_env: str,
    module_attr: str = "OpenAI",
    base_url: Optional[str] = None,
    extra_client_kwargs: Optional[Dict[str, Any]] = None,
    api_key_required: bool = True,
) -> Callable[[], Any]:
    """Return a ``_get_client`` function for the given provider config.

    The returned function checks that *module* is not ``None``, that the
    API key env var is set, and returns an instantiated client object.
    """

    def _get_client() -> Any:
        if module is None:
            return None
        kwargs: Dict[str, Any] = {}
        if extra_client_kwargs:
            kwargs.update(extra_client_kwargs)
        if "api_key" not in kwargs:
            api_key = os.getenv(api_key_env)
            if not api_key and api_key_required:
                logger.warning("%s not set", api_key_env)
                return None
            kwargs["api_key"] = api_key or ""
        timeout = _clamp_timeout(os.getenv(timeout_env))
        kwargs["timeout"] = timeout
        if base_url:
            kwargs["base_url"] = base_url
        client_cls = getattr(module, module_attr, None)
        if client_cls is None:
            return None
        return client_cls(**kwargs)

    return _get_client


def make_model_getter(
    *,
    prefix: str,
    default_model: str,
) -> Callable[[PipelineContext | None], str]:
    """Return a ``_get_model`` reading ``{prefix}_model`` from metadata."""

    def _get_model(ctx: PipelineContext | None = None) -> str:
        if ctx and ctx.goal.metadata:
            override = ctx.goal.metadata.get(f"{prefix}_model")
            if override:
                return override
        return os.getenv(f"{prefix.upper()}_MODEL", default_model)

    return _get_model


def make_temperature_getter(
    *,
    prefix: str,
    default: float = 0.7,
    temp_min: float = 0.0,
    temp_max: float = 2.0,
) -> Callable[[PipelineContext | None], float]:
    """Return a ``_get_temperature`` function clamped to temp_min..temp_max."""

    def _get_temperature(ctx: PipelineContext | None = None) -> float:
        if ctx and ctx.goal.metadata:
            raw = ctx.goal.metadata.get(f"{prefix}_temperature")
            if raw is not None:
                try:
                    return max(temp_min, min(temp_max, float(raw)))
                except (ValueError, TypeError):
                    logger.warning("Invalid %s_temperature value", prefix)
        return default

    return _get_temperature


def make_max_tokens_getter(
    *,
    prefix: str,
    default: int = 1000,
    token_max: int = 100_000,
) -> Callable[[PipelineContext | None], int]:
    """Return a ``_get_max_tokens`` function clamped to 1..token_max."""

    def _get_max_tokens(ctx: PipelineContext | None = None) -> int:
        if ctx and ctx.goal.metadata:
            raw = ctx.goal.metadata.get(f"{prefix}_max_tokens")
            if raw is not None:
                try:
                    return max(1, min(token_max, int(raw)))
                except (ValueError, TypeError):
                    logger.warning("Invalid %s_max_tokens value", prefix)
        return default

    return _get_max_tokens


def _chat_skill(
    provider_name: str,
    get_client: Callable[[], Any],
    get_model: Callable[[PipelineContext | None], str],
    get_temperature: Callable[[PipelineContext | None], float],
    get_max_tokens: Callable[[PipelineContext | None], int],
) -> Callable[[PipelineContext], Dict[str, Any]]:
    """Build a ``*_chat`` skill for an OpenAI-compatible provider."""

    def skill(ctx: PipelineContext) -> Dict[str, Any]:
        client = get_client()
        if client is None:
            return {
                "status": "failed",
                "error": (
                    f"{provider_name.title()} client not available "
                    f"(install package and set API key)"
                ),
            }

        meta = ctx.goal.metadata or {}
        messages = meta.get("messages", [])
        if not messages:
            messages = [{"role": "user", "content": ctx.goal.objective}]

        try:
            model = get_model(ctx)
            temperature = get_temperature(ctx)
            max_tokens = get_max_tokens(ctx)

            logger.info("Calling %s chat with model %s", provider_name, model)

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

            usage = response.usage or {}
            return {
                "status": "completed",
                "model": model,
                "message": response.choices[0].message.content,
                "finish_reason": response.choices[0].finish_reason,
                "usage": {
                    "prompt_tokens": getattr(usage, "prompt_tokens", 0),
                    "completion_tokens": getattr(
                        usage, "completion_tokens", 0
                    ),
                    "total_tokens": getattr(usage, "total_tokens", 0),
                },
            }
        except Exception:
            logger.exception("%s_chat failed", provider_name)
            return {
                "status": "failed",
                "error": "Chat request failed",
                "model": get_model(ctx),
            }

    skill.__name__ = f"{provider_name}_chat"
    skill.__doc__ = (
        f"Chat with {provider_name.title()} models via "
        f"OpenAI-compatible API."
    )
    return skill


def _completion_skill(
    provider_name: str,
    get_client: Callable[[], Any],
    get_model: Callable[[PipelineContext | None], str],
    get_temperature: Callable[[PipelineContext | None], float],
    get_max_tokens: Callable[[PipelineContext | None], int],
) -> Callable[[PipelineContext], Dict[str, Any]]:
    """Build a ``*_completion`` skill for an OpenAI-compatible provider."""

    def skill(ctx: PipelineContext) -> Dict[str, Any]:
        client = get_client()
        if client is None:
            return {
                "status": "failed",
                "error": (
                    f"{provider_name.title()} client not available "
                    f"(install package and set API key)"
                ),
            }

        meta = ctx.goal.metadata or {}
        prompt = meta.get("prompt", ctx.goal.objective)

        try:
            model = get_model(ctx)
            temperature = get_temperature(ctx)
            max_tokens = get_max_tokens(ctx)

            logger.info(
                "Calling %s completion with model %s", provider_name, model
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

            usage = response.usage or {}
            return {
                "status": "completed",
                "model": model,
                "text": response.choices[0].text,
                "finish_reason": response.choices[0].finish_reason,
                "usage": {
                    "prompt_tokens": getattr(usage, "prompt_tokens", 0),
                    "completion_tokens": getattr(
                        usage, "completion_tokens", 0
                    ),
                    "total_tokens": getattr(usage, "total_tokens", 0),
                },
            }
        except Exception:
            logger.exception("%s_completion failed", provider_name)
            return {
                "status": "failed",
                "error": "Completion request failed",
                "model": get_model(ctx),
            }

    skill.__name__ = f"{provider_name}_completion"
    skill.__doc__ = (
        f"Text completion with {provider_name.title()} models via "
        f"OpenAI-compatible API."
    )
    return skill


def _embedding_skill(
    provider_name: str,
    get_client: Callable[[], Any],
    default_embedding_model: str,
) -> Callable[[PipelineContext], Dict[str, Any]]:
    """Build a ``*_embedding`` skill for an OpenAI-compatible provider."""

    def skill(ctx: PipelineContext) -> Dict[str, Any]:
        client = get_client()
        if client is None:
            return {
                "status": "failed",
                "error": (
                    f"{provider_name.title()} client not available "
                    f"(install package and set API key)"
                ),
            }

        meta = ctx.goal.metadata or {}
        text = meta.get("text", ctx.goal.objective)
        model = meta.get("embedding_model", default_embedding_model)

        try:
            logger.info(
                "Calling %s embedding with model %s", provider_name, model
            )

            response = client.embeddings.create(model=model, input=text)

            if not response.data:
                return {
                    "status": "failed",
                    "error": "API returned empty data array",
                    "model": model,
                }

            usage = response.usage or {}
            return {
                "status": "completed",
                "model": model,
                "embedding": response.data[0].embedding,
                "dimensions": len(response.data[0].embedding),
                "usage": {
                    "prompt_tokens": getattr(usage, "prompt_tokens", 0),
                    "total_tokens": getattr(usage, "total_tokens", 0),
                },
            }
        except Exception:
            logger.exception("%s_embedding failed", provider_name)
            return {
                "status": "failed",
                "error": "Embedding request failed",
                "model": model,
            }

    skill.__name__ = f"{provider_name}_embedding"
    skill.__doc__ = (
        f"Generate embeddings with {provider_name.title()} models via "
        f"OpenAI-compatible API."
    )
    return skill


def register_openai_provider(
    *,
    name: str,
    module: Any,
    api_key_env: str,
    default_model: str,
    base_url: Optional[str] = None,
    default_embedding_model: str = "text-embedding-3-small",
    temperature_max: float = 2.0,
    temperature_default: float = 0.7,
    max_tokens_default: int = 1000,
    timeout_env: Optional[str] = None,
    extra_client_kwargs: Optional[Dict[str, Any]] = None,
    api_key_required: bool = True,
) -> None:
    """Register ``{name}_chat``, ``{name}_completion``,
    and ``{name}_embedding`` skills.

    This factory replaces ~250 lines of boilerplate per OpenAI-compatible
    provider with a single configuration call.

    Args:
        name: Provider identifier used for skill names and
            circuit-breaker keys.
        module: The Python module that exposes the client class
            (e.g. ``openai``).
        api_key_env: Environment variable name for the API key.
        default_model: Fallback model when none is specified in goal metadata.
        base_url: Optional ``base_url`` passed to the client constructor.
        default_embedding_model: Default model for the embedding skill.
        temperature_max: Upper clamp for temperature (default 2.0).
        temperature_default: Default temperature (default 0.7).
        max_tokens_default: Default max_tokens (default 1000).
        timeout_env: Override the default
            ``{name.upper()}_TIMEOUT_SEC`` env var.
        extra_client_kwargs: Extra kwargs forwarded to the client constructor.
        api_key_required: When ``False``, allow missing API key
            (e.g. LM Studio).
    """
    prefix = name.lower()
    timeout_var = timeout_env or f"{name.upper()}_TIMEOUT_SEC"

    get_client = make_client_getter(
        module=module,
        api_key_env=api_key_env,
        timeout_env=timeout_var,
        base_url=base_url,
        extra_client_kwargs=extra_client_kwargs,
        api_key_required=api_key_required,
    )
    get_model = make_model_getter(prefix=prefix, default_model=default_model)
    get_temperature = make_temperature_getter(
        prefix=prefix,
        default=temperature_default,
        temp_max=temperature_max,
    )
    get_max_tokens = make_max_tokens_getter(
        prefix=prefix,
        default=max_tokens_default,
    )

    # Register the three standard skills with circuit breaker protection
    register_skill(f"{prefix}_chat")(
        with_circuit_breaker(name, failure_threshold=5, recovery_timeout=60.0)(
            _chat_skill(
                name, get_client, get_model, get_temperature, get_max_tokens
            )
        )
    )
    register_skill(f"{prefix}_completion")(
        with_circuit_breaker(name, failure_threshold=5, recovery_timeout=60.0)(
            _completion_skill(
                name, get_client, get_model, get_temperature, get_max_tokens
            )
        )
    )
    register_skill(f"{prefix}_embedding")(
        with_circuit_breaker(name, failure_threshold=5, recovery_timeout=60.0)(
            _embedding_skill(name, get_client, default_embedding_model)
        )
    )
