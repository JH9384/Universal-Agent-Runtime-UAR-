import concurrent.futures
import copy
import functools
import gc
import json
import logging
import os
import pickle
import random
import sys
import threading
import time
import uuid
from typing import Iterator, Dict, Any, List, Tuple

from .cache import get_cache
from .contracts import PipelineContext, RunRecord, StrategySpec
from .exceptions import SkillExecutionError, TimeoutError, ValidationError
from .registry import registry
from .validation import validate_timeout
from .recipes import DEFAULT_RECIPES
from .schema import validate_event
from ..api.metrics import get_metrics_collector

# GC hint threshold: trigger gc.collect() after runs with many events
# to reduce memory pressure from accumulated intermediate objects.
GC_EVENT_THRESHOLD = int(os.getenv("UAR_GC_THRESHOLD", "50"))


@functools.lru_cache(maxsize=100)
def _cached_expand_execution_order(
    execution_order_tuple: tuple,
    recipe_map_tuple: tuple,
) -> Tuple[List[str], List[Dict[str, Any]]]:
    """LRU-cached wrapper for recipe expansion with hashable keys."""
    execution_order = [
        json.loads(item) for item in execution_order_tuple
    ]
    if recipe_map_tuple:
        recipe_map = {
            k: {"skills": list(v)}
            for k, v in recipe_map_tuple
        }
    else:
        recipe_map = None
    return _expand_execution_order_with_markers(
        execution_order, _recipe_map=recipe_map
    )


# Recipe-level context-mutation cache limits.
_MAX_RECIPE_CACHE_SIZE = 50

# Shared thread pool for _run_with_timeout to avoid per-skill churn.
# Adaptive sizing: UAR_TIMEOUT_POOL_MAX controls max workers.
_TIMEOUT_POOL_MAX = int(os.getenv("UAR_TIMEOUT_POOL_MAX", "16"))
_TIMEOUT_POOL = concurrent.futures.ThreadPoolExecutor(
    max_workers=_TIMEOUT_POOL_MAX
)
_TIMEOUT_POOL_LOCK = threading.Lock()

# Request coalescing: dedup concurrent identical skill executions
# Keyed by "skill_name:input_hash" — first caller executes,
# subsequent callers wait and receive the same result.
_COALESCE_ENABLED = (
    os.getenv("UAR_COALESCE", "true").lower() == "true"
)
_coalesce_locks: Dict[str, threading.Lock] = {}
_coalesce_results: Dict[str, Any] = {}
_coalesce_meta_lock = threading.Lock()

# Pickle-based snapshot is 3-10x faster than copy.deepcopy for large dicts
_USE_PICKLE_SNAPSHOT = (
    os.getenv("UAR_PICKLE_SNAPSHOT", "true").lower() == "true"
)

# Zero-copy: pickle protocol 5 supports out-of-band buffers (Python 3.8+)
_PICKLE_PROTOCOL = (
    5 if hasattr(pickle, "Protocol") else pickle.HIGHEST_PROTOCOL
)

# Early result streaming: emit partial outputs as waves complete
_EARLY_STREAMING = (
    os.getenv("UAR_EARLY_STREAMING", "false").lower() == "true"
)


class RestrictedUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        # Permit basic data structures and some builtins
        if module == "builtins" and name in {
            "dict",
            "list",
            "set",
            "tuple",
            "str",
            "int",
            "float",
            "bool",
            "bytes",
            "bytearray",
            "NoneType",
        }:
            return getattr(sys.modules[module], name)
        raise pickle.UnpicklingError(
            f"Forbidden unpickling class: {module}.{name}"
        )


def validate_parameters(params: Dict[str, Any]) -> None:
    """Validate item parameters to prevent restricted key injection."""
    if not isinstance(params, dict):
        return
    for key in params:
        if key.startswith("_") or key in {
            "metadata",
            "objective",
            "id",
            "goal_id",
            "user_id",
        }:
            raise ValidationError(
                f"Invalid parameter key: '{key}' is restricted."
            )


def _snapshot_context(data: Dict[str, Any]) -> Dict[str, Any]:
    """Fast snapshot of context data for retry / parallel isolation.

    Uses ``pickle`` (3-10x faster than ``copy.deepcopy`` for large dicts)
    and falls back to ``copy.deepcopy`` if pickle fails.
    """
    if not _USE_PICKLE_SNAPSHOT:
        return copy.deepcopy(data)
    try:
        import io
        serialized = pickle.dumps(data, protocol=_PICKLE_PROTOCOL)
        return RestrictedUnpickler(io.BytesIO(serialized)).load()
    except Exception:
        return copy.deepcopy(data)


def _zero_copy_serialize(data: Dict[str, Any]) -> bytes:
    """Serialize data with pickle protocol 5 for zero-copy deserialization.

    Uses out-of-band buffers to avoid extra copies during deserialization
    when the consumer also supports protocol 5.
    """
    try:
        import pickle
        if hasattr(pickle, "Protocol") and _PICKLE_PROTOCOL >= 5:
            buffers: List[Any] = []
            return pickle.dumps(
                data, protocol=_PICKLE_PROTOCOL, buffer_callback=buffers.append
            )
        return pickle.dumps(data, protocol=_PICKLE_PROTOCOL)
    except Exception:
        return pickle.dumps(data)


def _estimate_size(obj, max_depth=3, current_depth=0):
    """Recursively estimate the size of an object.

    Args:
        obj: Object to estimate size for
        max_depth: Maximum recursion depth to prevent infinite loops
        current_depth: Current recursion depth

    Returns:
        Estimated size in bytes
    """
    import sys

    if current_depth >= max_depth:
        return sys.getsizeof(obj)

    size = sys.getsizeof(obj)

    if isinstance(obj, dict):
        for key, value in obj.items():
            size += sys.getsizeof(key)
            size += _estimate_size(value, max_depth, current_depth + 1)
    elif isinstance(obj, (list, tuple, set)):
        for item in obj:
            size += _estimate_size(item, max_depth, current_depth + 1)

    return size


def _validate_input_guardrails(
    ctx: PipelineContext, skill_name: str
) -> List[str]:
    """Basic input validation guardrails.

    Args:
        ctx: Pipeline context
        skill_name: Name of the skill being executed

    Returns:
        List of violation messages (empty if no violations)
    """
    # Per-context cache: all skills in a parallel wave share ctx.data
    cache_key = "_guardrail_cache"
    cached = ctx.data.get(cache_key)
    if cached is not None:
        return cached
    violations = _validate_input_guardrails_core(ctx)
    ctx.data[cache_key] = violations
    return violations


def _validate_input_guardrails_core(
    ctx: PipelineContext,
) -> List[str]:
    """Core guardrail logic (context-scoped, not skill-scoped)."""
    violations = []

    # Check for suspiciously large inputs
    # Use sys.getsizeof for more accurate size estimation
    # Fall back to string length for complex objects
    if ctx.data:
        import sys

        try:
            # Get size of the data object
            size = sys.getsizeof(ctx.data)
            # For containers, recursively estimate size (limited depth)
            if isinstance(ctx.data, (dict, list, set, tuple)):
                size = _estimate_size(ctx.data, max_depth=2)
            if size > 10_000_000:  # 10MB
                violations.append(
                    f"Input size exceeds 10MB limit: {size} bytes"
                )
        except Exception:
            # Fallback to string length if size estimation fails
            data_str = str(ctx.data)
            if len(data_str) > 10_000_000:  # 10MB
                violations.append(
                    f"Input size exceeds 10MB limit: {len(data_str)} bytes"
                )

    # Check for potentially dangerous patterns in context
    # Only flag if password appears to be an actual credential value
    # (not field names, documentation, or configuration keys)
    # This is opt-in via metadata to avoid false positives
    enable_password_check = bool(
        getattr(ctx, "metadata", {}).get("enable_password_guardrail", False)
    )
    if enable_password_check:
        data_str = str(ctx.data).lower()
        if "password" in data_str:
            # Check if it's likely a real password value vs
            # documentation/field names
            # Exclude common documentation, configuration, and code patterns
            exclusion_patterns = [
                # Documentation/instructional patterns
                "password:",
                "your password",
                "enter password",
                "set password",
                "change password",
                "reset password",
                "confirm password",
                "password policy",
                "password requirements",
                # Configuration patterns (keys/field names)
                "password=",
                "db_password",
                "api_password",
                "admin_password",
                "user_password",
                "app_password",
                "login_password",
                # Code patterns (functions/properties)
                ".password",
                "_password",
                "get_password",
                "set_password",
                "check_password",
                "verify_password",
                "hash_password",
                # File/variable patterns
                "env_password",
                "config_password",
                "secret_password",
                "password_file",
                "password_path",
                # Common field names in APIs/configs
                "password_field",
                "password_key",
                "password_value",
                "password_input",
                "password_output",
                "password_param",
                # UI/form patterns
                "password_field",
                "password_label",
                "password_placeholder",
                # Security policy patterns
                "password_length",
                "password_complexity",
                "password_expiration",
                "password_history",
            ]
            if not any(pattern in data_str for pattern in exclusion_patterns):
                # Also exclude if it's in a file path or documentation context
                if not (
                    "/doc" in data_str
                    or "/docs" in data_str
                    or "documentation" in data_str
                    or "readme" in data_str
                    or ".md" in data_str
                    or ".txt" in data_str
                    or ".rst" in data_str
                    or "example" in data_str
                    or "sample" in data_str
                    or "template" in data_str
                    or "tutorial" in data_str
                    or "guide" in data_str
                    or "spec" in data_str
                ):
                    violations.append(
                        "Potential password in context data. "
                        "Disable with enable_password_guardrail=false"
                    )

    return violations


def _validate_output_guardrails(result: Any, skill_name: str) -> List[str]:
    """Basic output validation guardrails.

    Args:
        result: Skill execution result
        skill_name: Name of the skill that was executed

    Returns:
        List of violation messages (empty if no violations)
    """
    violations = []

    # Check for suspiciously large outputs
    if result:
        result_str = str(result)
        if len(result_str) > 10_000_000:  # 10MB
            violations.append(
                f"Output size exceeds 10MB limit: {len(result_str)} bytes"
            )

    return violations


logger = logging.getLogger(__name__)

# Sampled logging: log only 1/N debug messages on hot paths
# to reduce I/O overhead.  UAR_LOG_SAMPLE_RATE=0 disables sampling.
_LOG_SAMPLE_RATE = int(os.getenv("UAR_LOG_SAMPLE_RATE", "1"))
_log_counter = 0
_log_counter_lock = threading.Lock()


def _sampled_log(level: str, msg: str, *args: Any, **kwargs: Any) -> None:
    """Log only 1/N messages to reduce hot-path I/O."""
    global _log_counter
    if _LOG_SAMPLE_RATE <= 1:
        getattr(logger, level)(msg, *args, **kwargs)
        return
    with _log_counter_lock:
        _log_counter += 1
        if _log_counter % _LOG_SAMPLE_RATE == 0:
            getattr(logger, level)(msg, *args, **kwargs)


# Retry configuration per skill (max retries)
DEFAULT_MAX_RETRIES = int(os.getenv("UAR_MAX_RETRIES", "2"))
SKILL_RETRY_POLICIES = {
    "default": DEFAULT_MAX_RETRIES,
    "ollama_generate": 3,  # More retries for external service
    "graphrag_query": 2,
    "autonomi_upload": 3,
    "autonomi_download": 3,
}


def get_max_retries(skill_name: str) -> int:
    """Get max retries for a skill, with default fallback."""
    return SKILL_RETRY_POLICIES.get(
        skill_name, SKILL_RETRY_POLICIES["default"]
    )


def _expand_execution_order(
    execution_order: List[Dict[str, Any]],
) -> List[str]:
    """Expand execution_order with recipes into a flat skill list.

    See :func:`_expand_execution_order_with_markers` for the variant
    that also returns recipe boundary metadata for event emission.
    """
    skills, _ = _expand_execution_order_with_markers(execution_order)
    return skills


MAX_RECIPE_DEPTH = 10


def _expand_execution_order_with_markers(
    execution_order: List[Dict[str, Any]],
    _visited: set[str] | None = None,
    _depth: int = 0,
    _recipe_map: Dict[str, Dict[str, Any]] | None = None,
) -> tuple[List[str], List[Dict[str, Any]]]:
    """Expand execution_order, returning ``(skills, recipe_markers)``.

    Supports **nested recipes** (a recipe may reference another recipe
    in its ``skills`` list).  Circular recipe references are detected
    and raise :class:`ValidationError`.

    ``recipe_markers`` is a list of
    ``{"index": <int>, "kind": "start"|"end", "recipe_id": <str>,
    "instance_id": <str>}`` records describing where in ``skills``
    each recipe block begins (inclusive) and ends (exclusive). The
    executor consumes this to emit ``recipe_start``/``recipe_end``
    events while preserving the existing flattened execution path.

    Args:
        execution_order: List of typed items to expand.
        _visited: Internal set tracking visited recipe IDs for
            circular dependency detection.
        _depth: Internal recursion depth counter.
        _recipe_map: Optional recipe map overriding ``DEFAULT_RECIPES``.
            Used when the request includes user-created recipes in
            metadata.

    Raises:
        ValidationError: If an unknown recipe is referenced, a
        circular dependency is detected, or max nesting depth is
        exceeded.
    """
    from .exceptions import ValidationError

    recipe_map = _recipe_map if _recipe_map is not None else DEFAULT_RECIPES
    visited = _visited if _visited is not None else set()
    skills: List[str] = []
    markers: List[Dict[str, Any]] = []

    if _depth > MAX_RECIPE_DEPTH:
        raise ValidationError(
            f"Recipe nesting exceeds maximum depth ({MAX_RECIPE_DEPTH}). "
            f"This may indicate a circular dependency or excessively "
            f"deep recipe hierarchy."
        )

    for i, item in enumerate(execution_order):
        item_type = item.get("type")
        content = item.get("content")
        instance_id = item.get("id", "") if isinstance(item, dict) else ""

        if item_type == "recipe":
            if content is None:
                raise ValidationError(
                    f"execution_order[{i}] has recipe type but "
                    f"missing content field"
                )
            if content in visited:
                raise ValidationError(
                    f"Circular recipe dependency detected: "
                    f"recipe '{content}' references itself (directly or "
                    f"indirectly)"
                )
            recipe = recipe_map.get(content)
            if recipe is None:
                available = list(recipe_map.keys())
                raise ValidationError(
                    f"execution_order[{i}] references unknown recipe: "
                    f"{content}. Available recipes: {available}"
                )

            recipe_items = recipe.get("skills", [])
            if not isinstance(recipe_items, list):
                logger.warning(
                    "Recipe %s has invalid skills type: %s. Expected list.",
                    content,
                    type(recipe_items),
                )
                recipe_items = []

            # Convert recipe skills into typed items for recursion.
            # Supports flat strings or nested lists for parallel groups.
            typed_items: List[Dict[str, Any]] = []
            for s in recipe_items:
                if isinstance(s, list):
                    for sub in s:
                        if not isinstance(sub, str) or not sub:
                            logger.warning(
                                "Recipe %s has invalid skill in group: "
                                "%s. Skipping.",
                                content,
                                sub,
                            )
                            continue
                        nested_id = (
                            f"{instance_id}:{sub}" if instance_id else sub
                        )
                        if sub in recipe_map:
                            typed_items.append(
                                {
                                    "type": "recipe",
                                    "content": sub,
                                    "id": nested_id,
                                }
                            )
                        else:
                            typed_items.append(
                                {
                                    "type": "skill",
                                    "content": sub,
                                    "id": nested_id,
                                }
                            )
                elif isinstance(s, str) and s:
                    nested_id = f"{instance_id}:{s}" if instance_id else s
                    if s in recipe_map:
                        typed_items.append(
                            {
                                "type": "recipe",
                                "content": s,
                                "id": nested_id,
                            }
                        )
                    else:
                        typed_items.append(
                            {
                                "type": "skill",
                                "content": s,
                                "id": nested_id,
                            }
                        )
                else:
                    logger.warning(
                        "Recipe %s has invalid skill: %s. Skipping.",
                        content,
                        s,
                    )

            start_index = len(skills)
            markers.append(
                {
                    "index": start_index,
                    "kind": "start",
                    "recipe_id": content,
                    "instance_id": instance_id,
                    "max_retries": item.get("max_retries", 0),
                    "parameters": recipe.get("parameters", {}),
                    "condition": recipe.get("condition"),
                }
            )
            # Recursively expand, tracking visited recipes
            visited.add(content)
            try:
                nested_skills, nested_markers = (
                    _expand_execution_order_with_markers(
                        typed_items,
                        _visited=visited,
                        _depth=_depth + 1,
                        _recipe_map=recipe_map,
                    )
                )
            finally:
                visited.discard(content)
            skills.extend(nested_skills)
            # Adjust nested marker indices to account for the current offset
            offset = start_index
            for m in nested_markers:
                m["index"] = m.get("index", 0) + offset
            markers.extend(nested_markers)
            markers.append(
                {
                    "index": len(skills),
                    "kind": "end",
                    "recipe_id": content,
                    "instance_id": instance_id,
                }
            )
        elif item_type == "skill":
            if content is not None:
                skills.append(content)
        else:
            logger.warning(
                "execution_order[%d] has invalid type: %s",
                i,
                item_type,
            )

    return skills, markers


# Skills that modify context and must run sequentially
CONTEXT_MODIFYING_SKILLS = {"doc_ingest", "graphrag_index"}


def _eval_condition(condition: Any, data: Dict[str, Any]) -> bool:
    """Evaluate a recipe condition against context data."""
    if not condition or not isinstance(condition, dict):
        return True
    key = condition.get("key", "")
    if not key:
        return True
    if "exists" in condition:
        return key in data
    if "equals" in condition:
        return data.get(key) == condition["equals"]
    if "not_equals" in condition:
        return data.get(key) != condition["not_equals"]
    return True


def _get_parallel_groups(skills: List[str]) -> List[List[str]]:
    """Group skills that can run in parallel.

    Args:
        skills: List of skill names in execution order

    Returns:
        List of skill groups where each group can run in parallel
    """
    groups: List[List[str]] = []
    current_group: List[str] = []

    for skill in skills:
        # Skills that modify context should run sequentially
        # Never group them with other skills to prevent race conditions
        if skill in CONTEXT_MODIFYING_SKILLS:
            if current_group:
                groups.append(current_group)
                current_group = []
            # Context-modifying skills always run in their own group
            groups.append([skill])
        else:
            current_group.append(skill)

    if current_group:
        groups.append(current_group)

    return groups


def _run_with_timeout(fn, ctx, timeout_seconds):
    """Run a function with timeout using thread pool with proper cleanup.

    Automatically detects async (coroutine) skills and runs them in an
    event loop instead of blocking a thread. This eliminates thread
    overhead for I/O-bound async skills.

    Note: Thread cancellation in Python is cooperative - future.cancel()
    signals the thread to cancel but doesn't guarantee immediate
    termination. Skills should periodically check for cancellation if
    they support it.
    """
    import asyncio
    import inspect

    # Validate timeout to prevent negative or zero values
    timeout_seconds = max(0.1, timeout_seconds)

    # Async skill: run in event loop, not a thread pool
    if inspect.iscoroutinefunction(fn):
        try:
            return asyncio.run(
                asyncio.wait_for(fn(ctx), timeout=timeout_seconds)
            )
        except asyncio.TimeoutError as exc:
            raise TimeoutError(timeout_seconds) from exc

    # Shared pool avoids per-skill churn.
    with _TIMEOUT_POOL_LOCK:
        pool = _TIMEOUT_POOL
    future = pool.submit(fn, ctx)
    try:
        return future.result(timeout=timeout_seconds)
    except concurrent.futures.TimeoutError as exc:
        future.cancel()
        raise TimeoutError(timeout_seconds) from exc
    except Exception:
        future.cancel()
        raise


def make_executor_event(
    event_type: str,
    run_id: str,
    goal_id: str,
    skill=None,
    payload=None,
    error=None,
    correlation_id: str = "",
    timestamp: float | None = None,
):
    """Construct a canonical RuntimeEvent dict.

    This is the single source of truth for event construction in the
    executor.  All event emission flows through here.
    Interns frequently repeated strings to reduce memory overhead.
    """
    event = {
        "schema_version": "uar.event.v1",
        "type": sys.intern(event_type),
        "run_id": sys.intern(run_id),
        "goal_id": goal_id,
        "skill": skill,
        "timestamp": timestamp if timestamp is not None else time.time(),
        "correlation_id": correlation_id,
        "payload": payload or {},
        "error": error,
    }
    # Validate against schema and log a warning if non-compliant
    validation_errors = validate_event(event)
    if validation_errors:
        logger.warning(
            f"Event schema validation failed: {validation_errors} "
            f"for event: {event}"
        )
    return event


def _event(
    event_type: str,
    run_id: str,
    goal_id: str,
    skill=None,
    payload=None,
    error=None,
    correlation_id: str = "",
    timestamp: float | None = None,
):
    """Legacy alias for :func:`make_executor_event`.

    Preserved for backward compatibility; new code should call
    ``make_executor_event`` directly.
    """
    return make_executor_event(
        event_type,
        run_id,
        goal_id,
        skill=skill,
        payload=payload,
        error=error,
        correlation_id=correlation_id,
        timestamp=timestamp,
    )


class Executor:
    """Execute strategies and yield events.

    Supports recipe-level caching via the ``_recipe_cache`` instance
    attribute. Each executor instance maintains its own cache; create
    a new instance if you need a fresh cache.
    """

    def __init__(self) -> None:
        # Simple in-memory cache keyed by (recipe_id, params_hash).
        # Value stores the context mutations produced by the recipe.
        self._recipe_cache: Dict[str, Dict[str, Any]] = {}
        self._recipe_cache_hits = 0
        self._recipe_cache_misses = 0
        self._recipe_cache_lock = threading.Lock()

    def iter_events(
        self,
        strategy: StrategySpec,
        goal,
        timeout_seconds: float = 5.0,
        correlation_id: str = "",
        _existing_ctx: Any | None = None,
        _suppress_start_complete: bool = False,
        _run_id: str = "",
        _use_hierarchical: bool = True,
    ) -> Iterator[dict]:
        """Execute strategy and yield events with proper error handling"""
        # Validate inputs
        timeout_seconds = validate_timeout(timeout_seconds)

        # Check for execution_order in goal metadata
        goal_metadata = getattr(goal, "metadata", {}) or {}
        execution_order = goal_metadata.get("execution_order")
        recipe_markers: List[Dict[str, Any]] = []
        recipe_map: Dict[str, Dict[str, Any]] | None = None
        if execution_order and isinstance(execution_order, list):
            # Build optional recipe map from metadata-provided definitions
            # so user-created recipes sent by the frontend are expanded.
            raw_defs = goal_metadata.get("recipe_definitions")
            if raw_defs and isinstance(raw_defs, list):
                recipe_map = dict(DEFAULT_RECIPES)
                for r in raw_defs:
                    if isinstance(r, dict) and "id" in r:
                        recipe_map[r["id"]] = r

            # Expand execution_order to a flat skill list AND collect
            # recipe-boundary markers so the runtime can emit
            # ``recipe_start``/``recipe_end`` events while still
            # executing the flattened sequence.
            if recipe_map is not None:
                eo_tuple = tuple(
                    json.dumps(item, sort_keys=True, default=str)
                    for item in execution_order
                )
                rm_tuple = tuple(
                    sorted(
                        (k, tuple(v.get("skills", [])))
                        for k, v in recipe_map.items()
                    )
                )
                ordered_skills, recipe_markers = (
                    _cached_expand_execution_order(eo_tuple, rm_tuple)
                )
            else:
                ordered_skills, recipe_markers = (
                    _expand_execution_order_with_markers(
                        execution_order, _recipe_map=recipe_map
                    )
                )
            if ordered_skills:
                strategy = StrategySpec(
                    goal_id=strategy.goal_id, ordered_skills=ordered_skills
                )

        if not strategy.ordered_skills:
            raise ValidationError(
                "At least one skill must be specified", field="skills"
            )

        run_id = _run_id or str(uuid.uuid4())
        ctx = _existing_ctx or PipelineContext(goal=goal)
        outputs: List[Dict[str, Any]] = []
        errors: List[str] = []

        # Execution metrics
        _metrics_start = time.time()
        _metrics_event_count = 0
        _metrics_skill_times: Dict[str, float] = {}
        _metrics_cache_hits = 0
        _metrics_cache_misses = 0

        # Get cache instance
        cache = get_cache()
        enable_cache = getattr(goal, "metadata", {}).get("enable_cache", True)

        # Thread-safe context for parallel execution
        ctx_lock = threading.Lock()

        # Local helper so every event carries the correlation ID
        def _ev(event_type: str, skill=None, payload=None, error=None):
            nonlocal _metrics_event_count
            _metrics_event_count += 1
            return _event(
                event_type,
                run_id,
                strategy.goal_id,
                skill=skill,
                payload=payload,
                error=error,
                correlation_id=correlation_id,
            )

        # Validate all skills exist before execution
        missing_skills = []
        for skill_name in strategy.ordered_skills:
            if not registry.is_registered(skill_name):
                missing_skills.append(skill_name)

        if missing_skills:
            # Return failed run instead of raising
            error_msg = f"Skill(s) not found: {', '.join(missing_skills)}"
            if not _suppress_start_complete:
                yield _ev(
                    "start",
                    payload={
                        "goal": goal.objective,
                        "skills": strategy.ordered_skills,
                    },
                )
                yield _ev(
                    "complete",
                    payload={
                        "status": "failed",
                        "outputs": [],
                        "errors": [error_msg],
                        "final_context": {},
                    },
                )
            return

        if not _suppress_start_complete:
            yield _ev(
                "start",
                payload={
                    "goal": goal.objective,
                    "skills": strategy.ordered_skills,
                },
            )

        # Emit orchestration plan after start so event contract is preserved
        if execution_order and ordered_skills:
            yield _ev(
                "orchestration_plan",
                payload={
                    "execution_order": execution_order,
                    "expanded_skills": ordered_skills,
                    "recipe_markers": recipe_markers,
                },
            )

        # Hierarchical execution path (opt-in via env var or metadata)
        _executed_hierarchical = False
        _hierarchical_enabled = os.getenv(
            "UAR_HIERARCHICAL_EXECUTION", ""
        ) or goal_metadata.get("use_hierarchical")
        if (
            execution_order
            and _hierarchical_enabled
            and recipe_map is not None
            and _existing_ctx is None
            and _use_hierarchical
        ):
            yield from self._execute_items(
                execution_order,
                ctx,
                goal,
                timeout_seconds,
                recipe_map,
                correlation_id,
                depth=0,
            )
            # Emit top-level metrics and complete for hierarchical path
            total_time = time.time() - _metrics_start
            yield _ev(
                "metrics",
                payload={
                    "total_time_sec": round(total_time, 3),
                    "event_count": _metrics_event_count,
                    "cache_hits": _metrics_cache_hits,
                    "cache_misses": _metrics_cache_misses,
                    "recipe_cache_hits": self._recipe_cache_hits,
                    "recipe_cache_misses": self._recipe_cache_misses,
                    "skills_executed": len(_metrics_skill_times),
                    "skill_times_ms": {
                        k: round(v * 1000, 1)
                        for k, v in _metrics_skill_times.items()
                    },
                },
            )
            yield _ev(
                "complete",
                payload={
                    "status": "completed" if not errors else "failed",
                    "outputs": outputs,
                    "errors": errors,
                    "final_context": ctx.data,
                },
            )
            if _metrics_event_count > GC_EVENT_THRESHOLD:
                gc.collect()
            return

        if not _executed_hierarchical:
            # Legacy flat execution path
            # Group skills for parallel execution
            enable_parallel = getattr(goal, "metadata", {}).get(
                "enable_parallel", True
            )
            if enable_parallel and strategy.waves:
                # DAG-aware parallel waves from orchestration plan
                skill_groups: List[List[str]] = []
                for g in strategy.waves:
                    if len(g) == 1:
                        # Singleton groups always included
                        skill_groups.append(g)
                    else:
                        # Multi-skill wave: split out context-modifying
                        clean: List[str] = []
                        for skill in g:
                            if skill in CONTEXT_MODIFYING_SKILLS:
                                if clean:
                                    skill_groups.append(clean)
                                    clean = []
                                skill_groups.append([skill])
                            else:
                                clean.append(skill)
                        if clean:
                            skill_groups.append(clean)
            elif enable_parallel:
                skill_groups = _get_parallel_groups(
                    strategy.ordered_skills
                )
            else:
                skill_groups = [
                    [s] for s in strategy.ordered_skills
                ]
        else:
            skill_groups = []

        # Build O(1) marker lookup for recipe_start/recipe_end emission
        # keyed by index in the flat ordered_skills list
        marker_index: Dict[int, List[Dict[str, Any]]] = {}
        for m in recipe_markers:
            idx = m.get("index", 0)
            marker_index.setdefault(idx, []).append(m)

        current_idx = 0
        # Track recipe end markers that have been yielded so that
        # we can emit any missed ``recipe_end`` events when the
        # skill loop breaks early due to an error.
        yielded_end_markers: set[int] = set()
        # Track recipe start times for duration metrics
        recipe_start_times: Dict[str, float] = {}
        # Recipe retry tracking
        recipe_snapshots: Dict[str, Any] = {}
        recipe_retry_remaining: Dict[str, int] = {}
        recipe_start_skill_idx: Dict[str, int] = {}
        recipe_error_lists: Dict[str, List[str]] = {}
        active_recipe_stack: List[str] = []
        skip_to_recipe_end: str = ""

        def _add_error(error_str: str) -> None:
            if active_recipe_stack:
                recipe_error_lists[active_recipe_stack[-1]].append(error_str)
            else:
                errors.append(error_str)

        def _eval_condition(condition: Any, data: Dict[str, Any]) -> bool:
            if not condition or not isinstance(condition, dict):
                return True
            key = condition.get("key", "")
            if not key:
                return True
            if "exists" in condition:
                return key in data
            if "equals" in condition:
                return data.get(key) == condition["equals"]
            if "not_equals" in condition:
                return data.get(key) != condition["not_equals"]
            return True

        # Map flat skill index -> group index for rewinding on retry.
        # Every flat index that falls inside a group maps to that group.
        flat_idx_to_group: Dict[int, int] = {}
        temp_flat = 0
        for gi, sg in enumerate(skill_groups):
            for _ in range(len(sg)):
                flat_idx_to_group[temp_flat] = gi
                temp_flat += 1
        flat_idx_to_group[temp_flat] = len(skill_groups)

        group_idx = 0
        while group_idx < len(skill_groups):
            skill_group = skill_groups[group_idx]
            # Emit recipe_start events for markers at this group's start index
            for marker in marker_index.get(current_idx, []):
                if marker.get("kind") == "start":
                    instance_id = marker.get("instance_id", "")
                    condition = marker.get("condition")
                    if not _eval_condition(condition, ctx.data):
                        skip_to_recipe_end = instance_id
                        yield _ev(
                            "recipe_skipped",
                            payload={
                                "recipe_id": marker.get("recipe_id"),
                                "instance_id": instance_id,
                                "reason": "condition_false",
                            },
                        )
                        continue
                    recipe_start_times[instance_id] = time.time()
                    params = marker.get("parameters", {})
                    validate_parameters(params)
                    # Snapshot BEFORE pushing params so retry is clean.
                    if instance_id not in recipe_snapshots:
                        recipe_snapshots[instance_id] = (
                            _snapshot_context(ctx.data)
                        )
                        recipe_retry_remaining[instance_id] = marker.get(
                            "max_retries", 0
                        )
                        recipe_start_skill_idx[instance_id] = current_idx
                        recipe_error_lists[instance_id] = []
                    if params:
                        # Use stack so nested recipes don't overwrite
                        # parent params
                        stack = ctx.data.setdefault("_recipe_params", [])
                        stack.append(params)
                    yield _ev(
                        "recipe_start",
                        payload={
                            "recipe_id": marker.get("recipe_id"),
                            "instance_id": instance_id,
                            "parameters": params,
                        },
                    )
                    if instance_id not in active_recipe_stack:
                        active_recipe_stack.append(instance_id)
            execution_broken = False
            if skip_to_recipe_end:
                # Skip skill execution while fast-forwarding to recipe end
                pass
            elif len(skill_group) == 1:
                # Sequential execution for single skill
                skill_name = skill_group[0]
                yield _ev("skill_start", skill=skill_name)

                # Input guardrails check
                input_violations = _validate_input_guardrails(ctx, skill_name)
                if input_violations:
                    error_msg = "Input guardrail violations: " + ", ".join(
                        input_violations
                    )
                    logger.warning(
                        f"Input guardrails failed for {skill_name}: "
                        f"{error_msg}"
                    )
                    yield _ev(
                        "skill_failed",
                        skill=skill_name,
                        error=error_msg,
                    )
                    _add_error(f"{skill_name}: {error_msg}")
                    if (
                        active_recipe_stack
                        and recipe_retry_remaining.get(
                            active_recipe_stack[-1], 0
                        )
                        > 0
                    ):
                        skip_to_recipe_end = active_recipe_stack[-1]
                    else:
                        execution_broken = True

                # Check cache first if enabled (outside retry loop)
                # Note: cache.get() is thread-safe internally,
                # no need for ctx_lock
                cached_result = None
                if enable_cache:
                    cached_result = cache.get(
                        skill_name,
                        ctx.data,
                        goal.objective,
                    )
                if cached_result is not None:
                    _metrics_cache_hits += 1
                    # Validate cached result against output guardrails
                    output_violations = _validate_output_guardrails(
                        cached_result, skill_name
                    )
                    if output_violations:
                        error_msg = (
                            "Cached result failed guardrails: "
                            + ", ".join(output_violations)
                        )
                        logger.warning(
                            f"Cached result guardrails failed for "
                            f"{skill_name}: {error_msg}"
                        )
                        # Treat cache miss and execute normally
                        cached_result = None
                        _metrics_cache_misses += 1
                    else:
                        with ctx_lock:
                            ctx.data[skill_name] = cached_result
                        outputs.append({skill_name: cached_result})
                        yield _ev(
                            "skill_complete",
                            skill=skill_name,
                            payload={
                                "result": cached_result,
                                "cached": True,
                                "attempt": 1,
                            },
                        )
                else:
                    _metrics_cache_misses += 1
                    # No cache hit, execute with retry logic
                    max_retries = get_max_retries(skill_name)
                    last_error = None

                    for attempt in range(max_retries + 1):
                        _coalesce_lock_acquired = False

                        def _release_coalesce_lock() -> None:
                            nonlocal _coalesce_lock_acquired
                            if (
                                _COALESCE_ENABLED
                                and _coalesce_key
                                and _coalesce_lock_acquired
                            ):
                                _coalesce_locks[_coalesce_key].release()
                                _coalesce_lock_acquired = False

                        try:
                            # Request coalescing: dedup concurrent
                            # identical executions
                            _coalesce_key = ""
                            if _COALESCE_ENABLED:
                                import hashlib

                                coalesce_input = {
                                    "context": ctx.data,
                                    "goal": {
                                        "id": getattr(goal, "id", ""),
                                        "objective": getattr(
                                            goal, "objective", ""
                                        ),
                                        "metadata": getattr(
                                            goal, "metadata", {}
                                        ),
                                    },
                                }
                                _input_hash = hashlib.blake2b(
                                    json.dumps(
                                        coalesce_input,
                                        sort_keys=True,
                                        default=str,
                                    ).encode(),
                                    digest_size=8,
                                ).hexdigest()
                                _coalesce_key = (
                                    f"{skill_name}:{_input_hash}"
                                )
                                with _coalesce_meta_lock:
                                    if _coalesce_key not in _coalesce_locks:
                                        _coalesce_locks[_coalesce_key] = (
                                            threading.Lock()
                                        )
                                _coalesce_locks[_coalesce_key].acquire()
                                _coalesce_lock_acquired = True
                                if _coalesce_key in _coalesce_results:
                                    result = _coalesce_results[
                                        _coalesce_key
                                    ]
                                    _release_coalesce_lock()
                                    with ctx_lock:
                                        ctx.data[skill_name] = result
                                    outputs.append(
                                        {skill_name: result}
                                    )
                                    yield _ev(
                                        "skill_complete",
                                        skill=skill_name,
                                        payload={
                                            "result": result,
                                            "cached": True,
                                            "coalesced": True,
                                            "attempt": 1,
                                        },
                                    )
                                    break
                            fn = registry.get(skill_name)
                            _skill_t0 = time.time()
                            result = _run_with_timeout(
                                fn, ctx, timeout_seconds
                            )
                            _skill_dur = time.time() - _skill_t0
                            _metrics_skill_times[skill_name] = _skill_dur
                            get_metrics_collector().record_skill(
                                skill_name, _skill_dur, error=False
                            )

                            # Output guardrails check
                            output_violations = _validate_output_guardrails(
                                result, skill_name
                            )
                            if output_violations:
                                error_msg = (
                                    "Output guardrail violations: "
                                    + ", ".join(output_violations)
                                )
                                logger.warning(
                                    f"Output guardrails failed for "
                                    f"{skill_name}: {error_msg}"
                                )
                                raise SkillExecutionError(
                                    skill_name,
                                    original_error=Exception(error_msg),
                                )

                            with ctx_lock:
                                ctx.data[skill_name] = result
                            outputs.append({skill_name: result})

                            # Store result in cache if enabled
                            # Result already passed guardrails above
                            # Note: cache.set() is thread-safe
                            # internally, no need for ctx_lock
                            if enable_cache:
                                cache.set(
                                    skill_name,
                                    ctx.data,
                                    goal.objective,
                                    result,
                                )
                            # Publish coalesced result for waiters
                            if _COALESCE_ENABLED and _coalesce_key:
                                _coalesce_results[_coalesce_key] = result

                            _release_coalesce_lock()
                            yield _ev(
                                "skill_complete",
                                skill=skill_name,
                                payload={
                                    "result": result,
                                    "attempt": attempt + 1,
                                },
                            )
                            break
                        except (TimeoutError, SkillExecutionError) as exc:
                            last_error = exc
                            if attempt < max_retries:
                                _release_coalesce_lock()
                                # Add jitter to prevent thundering herd
                                base_backoff = min(2**attempt, 5)
                                backoff = base_backoff * random.uniform(
                                    0.8, 1.2
                                )
                                yield _ev(
                                    "skill_retry",
                                    skill=skill_name,
                                    payload={
                                        "attempt": attempt + 1,
                                        "max_retries": max_retries,
                                        "backoff_seconds": backoff,
                                    },
                                )
                                time.sleep(backoff)
                            else:
                                yield _ev(
                                    "skill_failed",
                                    skill=skill_name,
                                    error=str(last_error),
                                    payload={"attempts": attempt + 1},
                                )
                                get_metrics_collector().record_skill(
                                    skill_name,
                                    time.time() - _skill_t0,
                                    error=True,
                                )
                                _release_coalesce_lock()
                                _add_error(f"{skill_name}: {str(last_error)}")
                                if (
                                    active_recipe_stack
                                    and recipe_retry_remaining.get(
                                        active_recipe_stack[-1], 0
                                    )
                                    > 0
                                ):
                                    skip_to_recipe_end = active_recipe_stack[
                                        -1
                                    ]
                                else:
                                    execution_broken = True
                        except Exception as exc:
                            _release_coalesce_lock()
                            yield _ev(
                                "skill_failed",
                                skill=skill_name,
                                error=str(exc),
                            )
                            _add_error(f"{skill_name}: {str(exc)}")
                            if (
                                active_recipe_stack
                                and recipe_retry_remaining.get(
                                    active_recipe_stack[-1], 0
                                )
                                > 0
                            ):
                                skip_to_recipe_end = active_recipe_stack[-1]
                            else:
                                execution_broken = True
            else:
                # Parallel execution for group of skills
                yield _ev("parallel_start", payload={"skills": skill_group})

                # Check for fail_fast option in goal metadata
                fail_fast = getattr(goal, "metadata", {}).get(
                    "fail_fast", False
                )

                # Collect results locally to avoid concurrent ctx.data writes
                parallel_results = {}
                skills_to_execute = []

                # Check cache for each skill before parallel
                # execution. Note: cache.get() is thread-safe
                # internally, no need for ctx_lock
                for skill_name in skill_group:
                    cached_result = None
                    if enable_cache:
                        cached_result = cache.get(
                            skill_name,
                            ctx.data,
                            goal.objective,
                        )
                    if cached_result is not None:
                        # Validate cached result against output guardrails
                        output_violations = _validate_output_guardrails(
                            cached_result, skill_name
                        )
                        if output_violations:
                            error_msg = (
                                "Cached result failed guardrails: "
                                + ", ".join(output_violations)
                            )
                            logger.warning(
                                f"Cached result guardrails failed for "
                                f"{skill_name}: {error_msg}"
                            )
                            # Treat cache miss and execute normally
                            cached_result = None
                        else:
                            # Cache hit, add to results directly
                            parallel_results[skill_name] = cached_result
                            yield _ev(
                                "skill_complete",
                                skill=skill_name,
                                payload={
                                    "result": cached_result,
                                    "cached": True,
                                },
                            )
                    else:
                        # Cache miss, add to execution list
                        skills_to_execute.append(skill_name)
                        _metrics_cache_misses += 1

                # Execute non-cached skills in parallel
                # Limit max workers to prevent resource exhaustion
                max_workers = min(8, len(skills_to_execute))
                with concurrent.futures.ThreadPoolExecutor(
                    max_workers=max_workers
                ) as pool:
                    future_to_skill = {}
                    future_to_start_time: Dict[
                        concurrent.futures.Future, float
                    ] = {}
                    for skill_name in skills_to_execute:
                        # Input guardrails check before parallel execution
                        input_violations = _validate_input_guardrails(
                            ctx, skill_name
                        )
                        if input_violations:
                            error_msg = (
                                f"Input guardrails failed for "
                                f"{skill_name}: " + ", ".join(input_violations)
                            )
                            logger.warning(error_msg)
                            yield _ev(
                                "skill_failed",
                                skill=skill_name,
                                error=error_msg,
                            )
                            if fail_fast:
                                break
                            continue

                        yield _ev("skill_start", skill=skill_name)
                        fn = registry.get(skill_name)
                        # Create isolated context copy for parallel
                        # execution to prevent race conditions.
                        # IMPORTANT: Skills in a parallel group must be
                        # independent and should not rely on each other's
                        # context modifications. Each skill receives a copy
                        # of the context as it existed before the group
                        # started. Results are merged back after all
                        # parallel skills complete.
                        # WARNING: If a skill depends on another
                        # skill's output in the same parallel group,
                        # it will receive stale data from the context
                        # copy. Only group skills that are truly
                        # independent.
                        # CRITICAL: Use deep copy to ensure true isolation.
                        # Shallow copy would share nested objects, causing
                        # race conditions if skills modify nested structures.
                        # This is a performance trade-off for correctness.
                        ctx_copy = PipelineContext(goal=goal)
                        ctx_copy.data = _snapshot_context(ctx.data)
                        _skill_t0 = time.time()
                        future = pool.submit(
                            _run_with_timeout, fn, ctx_copy, timeout_seconds
                        )
                        future_to_skill[future] = skill_name
                        future_to_start_time[future] = _skill_t0

                    # Track if any skill failed for fail_fast logic
                    any_failed = False

                    for future in concurrent.futures.as_completed(
                        future_to_skill
                    ):
                        skill_name = future_to_skill[future]
                        _skill_t0 = future_to_start_time.get(future, 0)
                        try:
                            result = future.result()

                            # Output guardrails check after execution
                            output_violations = _validate_output_guardrails(
                                result, skill_name
                            )
                            if output_violations:
                                error_msg = (
                                    "Output guardrail violations: "
                                    + ", ".join(output_violations)
                                )
                                logger.warning(
                                    f"Output guardrails failed for "
                                    f"{skill_name}: {error_msg}"
                                )
                                yield _ev(
                                    "skill_failed",
                                    skill=skill_name,
                                    error=error_msg,
                                )
                                _add_error(f"{skill_name}: {error_msg}")
                                any_failed = True
                                if fail_fast:
                                    break
                                continue

                            if _skill_t0:
                                _metrics_skill_times[skill_name] = (
                                    time.time() - _skill_t0
                                )
                            parallel_results[skill_name] = result

                            yield _ev(
                                "skill_complete",
                                skill=skill_name,
                                payload={"result": result},
                            )
                        except (TimeoutError, SkillExecutionError) as exc:
                            yield _ev(
                                "skill_failed",
                                skill=skill_name,
                                error=str(exc),
                            )
                            _add_error(f"{skill_name}: {str(exc)}")
                            any_failed = True
                            if fail_fast:
                                break
                        except Exception as exc:
                            yield _ev(
                                "skill_failed",
                                skill=skill_name,
                                error=str(exc),
                            )
                            _add_error(f"{skill_name}: {str(exc)}")
                            any_failed = True
                            if fail_fast:
                                break

                    # Cancel remaining futures if fail_fast and any failed
                    if fail_fast and any_failed:
                        for future in future_to_skill:
                            if not future.done():
                                future.cancel()
                        logger.info(
                            "Cancelled remaining parallel skills due to "
                            "fail_fast=True and skill failure"
                        )

                # Merge parallel results into context with lock
                with ctx_lock:
                    for skill_name, result in parallel_results.items():
                        ctx.data[skill_name] = result
                        outputs.append({skill_name: result})

                        # Store result in cache if enabled
                        # (only for newly executed). Note:
                        # cache.set() is thread-safe internally,
                        # no need for ctx_lock
                        # Only cache if result passes guardrails
                        if enable_cache and skill_name in skills_to_execute:
                            output_violations = _validate_output_guardrails(
                                result, skill_name
                            )
                            if not output_violations:
                                cache.set(
                                    skill_name,
                                    ctx.data,
                                    goal.objective,
                                    result,
                                )

                # Early streaming: emit partial outputs as waves complete
                if _EARLY_STREAMING and parallel_results:
                    yield _ev(
                        "partial_result",
                        payload={
                            "wave": group_idx,
                            "outputs": parallel_results,
                        },
                    )

                yield _ev("parallel_complete", payload={"skills": skill_group})

            # Advance flat skill index and emit recipe_end events for
            # markers at this position (end markers use exclusive index)
            current_idx += len(skill_group)
            group_idx += 1
            retry_triggered = False
            for marker in marker_index.get(current_idx, []):
                if marker.get("kind") == "end":
                    marker_id = id(marker)
                    instance_id = marker.get("instance_id", "")
                    if (
                        active_recipe_stack
                        and active_recipe_stack[-1] == instance_id
                    ):
                        active_recipe_stack.pop()
                        # Pop recipe params when recipe leaves the stack
                        params_stack = ctx.data.get("_recipe_params")
                        if params_stack and isinstance(params_stack, list):
                            params_stack.pop()

                    if skip_to_recipe_end == instance_id:
                        skip_to_recipe_end = ""

                    if recipe_error_lists.get(instance_id):
                        if recipe_retry_remaining.get(instance_id, 0) > 0:
                            recipe_retry_remaining[instance_id] -= 1
                            attempt = (
                                marker.get("max_retries", 0)
                                - recipe_retry_remaining[instance_id]
                                + 1
                            )
                            yield _ev(
                                "recipe_retry",
                                payload={
                                    "recipe_id": marker.get("recipe_id"),
                                    "instance_id": instance_id,
                                    "attempt": attempt,
                                    "remaining": recipe_retry_remaining[
                                        instance_id
                                    ],
                                },
                            )
                            ctx.data = _snapshot_context(
                                recipe_snapshots[instance_id]
                            )
                            recipe_error_lists[instance_id] = []
                            current_idx = recipe_start_skill_idx[instance_id]
                            group_idx = flat_idx_to_group[current_idx]
                            skip_to_recipe_end = ""
                            retry_triggered = True
                            break

                        if active_recipe_stack:
                            parent = active_recipe_stack[-1]
                            recipe_error_lists[parent].extend(
                                recipe_error_lists[instance_id]
                            )
                        else:
                            errors.extend(recipe_error_lists[instance_id])

                    if retry_triggered:
                        break

                    yielded_end_markers.add(marker_id)
                    # Capture start time BEFORE cleaning up tracking dicts
                    started = recipe_start_times.get(instance_id)
                    # Clean up tracking dicts for completed recipes
                    recipe_start_times.pop(instance_id, None)
                    recipe_snapshots.pop(instance_id, None)
                    recipe_retry_remaining.pop(instance_id, None)
                    recipe_start_skill_idx.pop(instance_id, None)
                    recipe_error_lists.pop(instance_id, None)
                    duration_ms = (
                        round((time.time() - started) * 1000)
                        if started
                        else None
                    )
                    yield _ev(
                        "recipe_end",
                        payload={
                            "recipe_id": marker.get("recipe_id"),
                            "instance_id": instance_id,
                            "duration_ms": duration_ms,
                        },
                    )
            if retry_triggered:
                continue

            if execution_broken and not skip_to_recipe_end:
                break

        # Clean up internal state so it never leaks into downstream
        # handlers or the final context, even if the loop broke early.
        ctx.data.pop("_recipe_params", None)

        # Emit any recipe_end events for markers that were skipped
        # because the skill loop broke early due to a failure.
        for m in recipe_markers:
            if m.get("kind") == "end" and id(m) not in yielded_end_markers:
                instance_id = m.get("instance_id", "")
                started = recipe_start_times.get(instance_id)
                duration_ms = (
                    round((time.time() - started) * 1000) if started else None
                )
                yield _ev(
                    "recipe_end",
                    payload={
                        "recipe_id": m.get("recipe_id"),
                        "instance_id": instance_id,
                        "status": "aborted",
                        "duration_ms": duration_ms,
                    },
                )

        # Optional sum_review skill - only run when explicitly opted in via
        # goal metadata, so implicit execution does not diverge from the
        # requested skill list.
        opt_in_review = bool(
            getattr(goal, "metadata", {}).get("auto_sum_review")
        )
        if (
            opt_in_review
            and registry.is_registered("sum_review")
            and "sum_review" not in strategy.ordered_skills
        ):
            skill_name = "sum_review"
            yield _ev("skill_start", skill=skill_name)
            try:
                _s0 = time.time()
                summary = _run_with_timeout(
                    registry.get(skill_name), ctx, timeout_seconds
                )
                get_metrics_collector().record_skill(
                    skill_name, time.time() - _s0, error=False
                )
                outputs.append({skill_name: summary})
                yield _ev(
                    "skill_complete",
                    skill=skill_name,
                    payload={"result": summary},
                )
            except Exception as e:
                get_metrics_collector().record_skill(
                    skill_name, time.time() - _s0, error=True
                )
                # Review failures don't fail the entire execution
                errors.append(f"Review failed: {str(e)}")

        if not _suppress_start_complete:
            # Emit execution metrics before completion
            total_time = time.time() - _metrics_start
            yield _ev(
                "metrics",
                payload={
                    "total_time_sec": round(total_time, 3),
                    "event_count": _metrics_event_count,
                    "cache_hits": _metrics_cache_hits,
                    "cache_misses": _metrics_cache_misses,
                    "recipe_cache_hits": self._recipe_cache_hits,
                    "recipe_cache_misses": self._recipe_cache_misses,
                    "skills_executed": len(_metrics_skill_times),
                    "skill_times_ms": {
                        k: round(v * 1000, 1)
                        for k, v in _metrics_skill_times.items()
                    },
                },
            )

            yield _ev(
                "complete",
                payload={
                    "status": "completed" if not errors else "failed",
                    "outputs": outputs,
                    "errors": errors,
                    "final_context": ctx.data,
                },
            )

        # GC hint: clean up accumulated intermediate objects for
        # long-running executions to reduce memory pressure.
        if _metrics_event_count > GC_EVENT_THRESHOLD:
            gc.collect()

    def run(
        self, strategy: StrategySpec, goal, timeout_seconds: float = 5.0
    ) -> RunRecord:
        """Execute strategy and return RunRecord"""
        timeout_seconds = validate_timeout(timeout_seconds)
        events = list(
            self.iter_events(strategy, goal, timeout_seconds=timeout_seconds)
        )

        if not events:
            raise ValidationError("No events generated during execution")

        start_event = events[0]
        complete_event = events[-1]
        payload = complete_event.get("payload", {})

        return RunRecord(
            run_id=start_event["run_id"],
            goal_id=strategy.goal_id,
            skills=strategy.ordered_skills,
            outputs=payload.get("outputs", []),
            status=payload.get("status", "failed"),
            errors=payload.get("errors", []),
            events=events,
            final_context=payload.get("final_context", {}),
        )

    def run_batch(
        self,
        strategies: List[StrategySpec],
        goals: List[Any],
        timeout_seconds: float = 5.0,
    ) -> List[RunRecord]:
        """Execute multiple skill strategies in a single batch.

        Runs each strategy-goal pair sequentially, reusing the same
        registry and cache context for efficiency.
        """
        results: List[RunRecord] = []
        for strategy, goal in zip(strategies, goals):
            results.append(self.run(strategy, goal, timeout_seconds))
        return results

    @staticmethod
    def paginate_results(
        results: List[Any],
        page: int = 1,
        page_size: int = 100,
    ) -> Dict[str, Any]:
        """Paginate large result lists for API responses.

        Returns a dict with items, total, page, page_size, and pages.
        """
        total = len(results)
        pages = max(1, (total + page_size - 1) // page_size)
        start = (page - 1) * page_size
        end = start + page_size
        return {
            "items": results[start:end],
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": pages,
        }

    def _execute_items(
        self,
        items: List[Dict[str, Any]],
        ctx: PipelineContext,
        goal,
        timeout_seconds: float,
        recipe_map: Dict[str, Dict[str, Any]],
        correlation_id: str,
        depth: int = 0,
    ) -> Iterator[dict]:
        """Recursively execute execution_order items as discrete units.

        Walks the execution_order hierarchy: skills are delegated to the
        existing flat executor via sub-executor calls (preserving all
        cache/guardrail/parallel behaviour), while recipes become true
        execution blocks with their own snapshot, retry, and parameter
        scope.
        """
        if depth > MAX_RECIPE_DEPTH:
            raise ValidationError(
                f"Recipe nesting exceeds maximum depth of {MAX_RECIPE_DEPTH}"
            )

        i = 0
        while i < len(items):
            item = items[i]
            item_type = item.get("type")

            if item_type == "skill":
                # Collect consecutive skills for a block execution
                skill_names: List[str] = []
                while i < len(items) and items[i].get("type") == "skill":
                    skill_names.append(str(items[i].get("content", "")))
                    i += 1

                if skill_names:
                    sub_strategy = StrategySpec(
                        goal_id=getattr(goal, "id", "sub"),
                        ordered_skills=skill_names,
                    )
                    # Strip execution_order from goal metadata so the
                    # sub-executor runs the flat path without re-expanding
                    # recipes and emitting duplicate boundary events.
                    sub_goal = copy.copy(goal)
                    sub_goal.metadata = {
                        k: v
                        for k, v in goal.metadata.items()
                        if k != "execution_order"
                    }
                    sub = Executor()
                    for event in sub.iter_events(
                        sub_strategy,
                        sub_goal,
                        timeout_seconds=timeout_seconds,
                        correlation_id=correlation_id,
                        _existing_ctx=ctx,
                        _suppress_start_complete=True,
                        _run_id="",
                        _use_hierarchical=False,
                    ):
                        yield event

            elif item_type == "recipe":
                recipe_id = str(item.get("content", ""))
                instance_id = str(item.get("id", ""))
                recipe = recipe_map.get(recipe_id)

                if recipe is None:
                    yield _event(
                        "recipe_skipped",
                        "",
                        getattr(goal, "id", ""),
                        payload={
                            "recipe_id": recipe_id,
                            "instance_id": instance_id,
                            "reason": "unknown_recipe",
                        },
                        correlation_id=correlation_id,
                    )
                    i += 1
                    continue

                condition = item.get("condition") or recipe.get("condition")
                if not _eval_condition(condition, ctx.data):
                    yield _event(
                        "recipe_skipped",
                        "",
                        getattr(goal, "id", ""),
                        payload={
                            "recipe_id": recipe_id,
                            "instance_id": instance_id,
                            "reason": "condition_false",
                        },
                        correlation_id=correlation_id,
                    )
                    i += 1
                    continue

                params = item.get("parameters") or recipe.get("parameters", {})
                validate_parameters(params)
                self._recipe_pre_execute(recipe_id, instance_id, params)

                # Build cache key from recipe_id + deterministic params
                _cache_key: str | None = None
                if self._recipe_should_cache(recipe_id, recipe):
                    _cache_key = json.dumps(
                        [recipe_id, sorted(params.items())],
                        default=str,
                    )

                # Cache hit: replay cached context mutations
                has_hit = False
                cached_delta = None
                if _cache_key:
                    with self._recipe_cache_lock:
                        if _cache_key in self._recipe_cache:
                            self._recipe_cache_hits += 1
                            cached_delta = self._recipe_cache[_cache_key]
                            has_hit = True

                if has_hit:
                    yield _event(
                        "recipe_start",
                        "",
                        getattr(goal, "id", ""),
                        payload={
                            "recipe_id": recipe_id,
                            "instance_id": instance_id,
                            "parameters": params,
                            "cached": True,
                        },
                        correlation_id=correlation_id,
                    )
                    # Prevent cached deltas from overwriting internal keys
                    if cached_delta:
                        for key, value in cached_delta.items():
                            if not key.startswith("_"):
                                ctx.data[key] = value
                    yield _event(
                        "recipe_end",
                        "",
                        getattr(goal, "id", ""),
                        payload={
                            "recipe_id": recipe_id,
                            "instance_id": instance_id,
                            "status": "completed",
                            "cached": True,
                        },
                        correlation_id=correlation_id,
                    )
                    i += 1
                    continue

                yield _event(
                    "recipe_start",
                    "",
                    getattr(goal, "id", ""),
                    payload={
                        "recipe_id": recipe_id,
                        "instance_id": instance_id,
                        "parameters": params,
                    },
                    correlation_id=correlation_id,
                )

                if params:
                    stack = ctx.data.setdefault("_recipe_params", [])
                    stack.append(params)

                snapshot = _snapshot_context(ctx.data)
                max_retries = item.get(
                    "max_retries", recipe.get("max_retries", 0)
                )
                recipe_timeout = self._recipe_timeout(
                    recipe_id, timeout_seconds, recipe
                )
                recipe_errors: List[str] = []
                attempt = 0

                raw_nested = recipe.get("items", []) or recipe.get(
                    "skills", []
                )
                # Normalize string lists to typed item dicts so that
                # recipes defined with plain skill names work seamlessly.
                nested_items: List[Dict[str, Any]] = []
                for raw in raw_nested:
                    if isinstance(raw, str):
                        nested_items.append(
                            {"type": "skill", "content": raw, "id": ""}
                        )
                    elif isinstance(raw, dict):
                        nested_items.append(raw)

                while True:
                    if attempt > 0:
                        ctx.data = _snapshot_context(snapshot)
                        recipe_errors = []
                        yield _event(
                            "recipe_retry",
                            "",
                            getattr(goal, "id", ""),
                            payload={
                                "recipe_id": recipe_id,
                                "instance_id": instance_id,
                                "attempt": attempt,
                            },
                            correlation_id=correlation_id,
                        )

                    for event in self._execute_items(
                        nested_items,
                        ctx,
                        goal,
                        recipe_timeout,
                        recipe_map,
                        correlation_id,
                        depth + 1,
                    ):
                        if event.get("type") == "skill_failed" and event.get(
                            "error"
                        ):
                            recipe_errors.append(
                                f"{event.get('skill', 'unknown')}: "
                                f"{event['error']}"
                            )
                        yield event

                    if not recipe_errors or attempt >= max_retries:
                        break
                    attempt += 1

                params_stack = ctx.data.get("_recipe_params")
                if params_stack and isinstance(params_stack, list):
                    params_stack.pop()
                    # Only remove the key if the stack is empty;
                    # otherwise parent recipe params are preserved.
                    if not params_stack:
                        ctx.data.pop("_recipe_params", None)

                status = "completed" if not recipe_errors else "failed"
                self._recipe_post_execute(
                    recipe_id, instance_id, status, recipe_errors
                )

                self._recipe_cache_misses += 1

                # Cache the context delta on successful execution
                if _cache_key and not recipe_errors and status == "completed":
                    # Compute delta: keys that changed or were added
                    delta: Dict[str, Any] = {}
                    for key, value in ctx.data.items():
                        if key not in snapshot or snapshot[key] != value:
                            delta[key] = value
                    with self._recipe_cache_lock:
                        while (
                            len(self._recipe_cache) >= _MAX_RECIPE_CACHE_SIZE
                        ):
                            self._recipe_cache.pop(
                                next(iter(self._recipe_cache))
                            )
                        self._recipe_cache[_cache_key] = delta

                yield _event(
                    "recipe_end",
                    "",
                    getattr(goal, "id", ""),
                    payload={
                        "recipe_id": recipe_id,
                        "instance_id": instance_id,
                        "status": status,
                        "errors": recipe_errors if recipe_errors else None,
                    },
                    correlation_id=correlation_id,
                )

                if recipe_errors:
                    for error in recipe_errors:
                        yield _event(
                            "error",
                            "",
                            getattr(goal, "id", ""),
                            error=error,
                            correlation_id=correlation_id,
                        )

                i += 1

            else:
                logger.warning(
                    "execution_order[%d] has invalid type: %s",
                    i,
                    item_type,
                )
                i += 1

    # -----------------------------------------------------------------
    # Future hooks — subclasses may override to extend recipe behaviour
    # -----------------------------------------------------------------

    def _recipe_pre_execute(
        self,
        recipe_id: str,
        instance_id: str,
        params: Dict[str, Any],
    ) -> None:
        """Hook called before a recipe begins execution.

        Subclasses may override to inject pre-recipe logic such as
        validation, logging, or dynamic parameter adjustment.
        """
        pass

    def _recipe_post_execute(
        self,
        recipe_id: str,
        instance_id: str,
        status: str,
        errors: List[str],
    ) -> None:
        """Hook called after a recipe completes (success or failure).

        Subclasses may override to collect metrics, trigger side
        effects, or cache recipe results.
        """
        pass

    def _recipe_should_cache(
        self, recipe_id: str, recipe: Dict[str, Any] | None = None
    ) -> bool:
        """Whether results for this recipe should be cached.

        Checks the recipe definition for a ``cache`` flag; subclasses
        may override to add additional logic (e.g. whitelist/blacklist).
        """
        if recipe and recipe.get("cache"):
            return True
        return False

    def _recipe_timeout(
        self,
        recipe_id: str,
        default_timeout: float,
        recipe: Dict[str, Any] | None = None,
    ) -> float:
        """Recipe-specific timeout override.

        Checks the recipe definition for a ``timeout`` field first;
        subclasses may override to add additional logic.
        """
        if recipe and "timeout" in recipe:
            return float(recipe["timeout"])
        return default_timeout
