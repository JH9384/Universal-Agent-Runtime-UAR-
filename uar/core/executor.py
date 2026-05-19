import concurrent.futures
import copy
import logging
import os
import random
import time
import uuid
from typing import Iterator, Dict, Any, List

from .cache import get_cache
from .contracts import PipelineContext, RunRecord, StrategySpec
from .exceptions import SkillExecutionError, TimeoutError, ValidationError
from .registry import registry
from .validation import validate_timeout
from .recipes import DEFAULT_RECIPES


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
    ctx: PipelineContext,
    skill_name: str
) -> List[str]:
    """Basic input validation guardrails.

    Args:
        ctx: Pipeline context
        skill_name: Name of the skill being executed

    Returns:
        List of violation messages (empty if no violations)
    """
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


def _validate_output_guardrails(
    result: Any,
    skill_name: str
) -> List[str]:
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
    execution_order: List[Dict[str, Any]]
) -> List[str]:
    """Expand execution_order with recipes into skill list.

    Args:
        execution_order: List of items with type ('skill'|'recipe')
            and content

    Returns:
        Flattened list of skill names in execution order

    Raises:
        ValidationError: If an unknown recipe is referenced
    """
    from .exceptions import ValidationError

    skills = []
    for i, item in enumerate(execution_order):
        item_type = item.get('type')
        content = item.get('content')

        if item_type == 'recipe':
            if content is None:
                raise ValidationError(
                    f"execution_order[{i}] has recipe type but "
                    f"missing content field"
                )
            recipe = DEFAULT_RECIPES.get(content)
            if recipe:
                recipe_skills = recipe.get('skills', [])
                # Validate that recipe_skills is a list
                if not isinstance(recipe_skills, list):
                    logger.warning(
                        f"Recipe {content} has invalid skills type: "
                        f"{type(recipe_skills)}. Expected list."
                    )
                    recipe_skills = []
                # Filter out None values and ensure all items are strings
                valid_skills = []
                for s in recipe_skills:
                    if s is not None and isinstance(s, str):
                        valid_skills.append(s)
                    else:
                        logger.warning(
                            f"Recipe {content} has invalid skill: "
                            f"{s} (type: {type(s)}). Skipping."
                        )
                skills.extend(valid_skills)
            else:
                raise ValidationError(
                    f"execution_order[{i}] references unknown recipe: "
                    f"{content}. Available recipes: "
                    f"{list(DEFAULT_RECIPES.keys())}"
                )
        elif item_type == 'skill':
            if content is not None:
                skills.append(content)
        else:
            logger.warning(
                f"execution_order[{i}] has invalid type: {item_type}"
            )
    return skills


# Skills that modify context and must run sequentially
CONTEXT_MODIFYING_SKILLS = {'doc_ingest', 'graphrag_index'}


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

    Note: Thread cancellation in Python is cooperative - future.cancel()
    signals the thread to cancel but doesn't guarantee immediate
    termination. Skills should periodically check for cancellation if
    they support it.

    IMPORTANT: Due to Python's threading model, cancelled threads may
    continue running in the background for a short time. The brief
    wait after cancel() allows the thread to clean up, but doesn't
    guarantee immediate termination. For true isolation, consider
    using multiprocessing instead of threading for long-running skills.
    """
    # Validate timeout to prevent negative or zero values
    timeout_seconds = max(0.1, timeout_seconds)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(fn, ctx)
        try:
            return future.result(timeout=timeout_seconds)
        except concurrent.futures.TimeoutError as exc:
            # Cancel the future - this signals cancellation but doesn't
            # guarantee the thread stops immediately (Python limitation)
            future.cancel()
            # Wait briefly for the thread to clean up
            try:
                future.result(timeout=0.1)
            except (
                concurrent.futures.TimeoutError,
                concurrent.futures.CancelledError,
            ):
                pass
            raise TimeoutError(timeout_seconds) from exc
        except Exception:
            # Ensure future is cancelled on any exception
            future.cancel()
            try:
                future.result(timeout=0.1)
            except (
                concurrent.futures.TimeoutError,
                concurrent.futures.CancelledError,
            ):
                pass
            raise


def _event(
    event_type: str,
    run_id: str,
    goal_id: str,
    skill=None,
    payload=None,
    error=None,
    correlation_id: str = "",
):
    return {
        "schema_version": "uar.event.v1",
        "type": event_type,
        "run_id": run_id,
        "goal_id": goal_id,
        "skill": skill,
        "timestamp": time.time(),
        "correlation_id": correlation_id,
        "payload": payload or {},
        "error": error,
    }


class Executor:
    def iter_events(
        self,
        strategy: StrategySpec,
        goal,
        timeout_seconds: float = 5.0,
        correlation_id: str = "",
    ) -> Iterator[dict]:
        """Execute strategy and yield events with proper error handling"""
        # Validate inputs
        timeout_seconds = validate_timeout(timeout_seconds)

        # Check for execution_order in goal metadata
        execution_order = getattr(goal, "metadata", {}).get("execution_order")
        if execution_order and isinstance(execution_order, list):
            # Expand execution_order to skill list
            ordered_skills = _expand_execution_order(execution_order)
            if ordered_skills:
                strategy = StrategySpec(
                    goal_id=strategy.goal_id,
                    ordered_skills=ordered_skills
                )
                yield _event(
                    "orchestration_plan",
                    run_id=str(uuid.uuid4()),
                    goal_id=strategy.goal_id,
                    payload={
                        "execution_order": execution_order,
                        "expanded_skills": ordered_skills
                    },
                    correlation_id=correlation_id
                )

        if not strategy.ordered_skills:
            raise ValidationError(
                "At least one skill must be specified", field="skills"
            )

        run_id = str(uuid.uuid4())
        ctx = PipelineContext(goal=goal)
        outputs = []
        errors = []

        # Get cache instance
        cache = get_cache()
        enable_cache = getattr(goal, "metadata", {}).get("enable_cache", True)

        # Thread-safe context for parallel execution
        import threading
        ctx_lock = threading.Lock()

        # Local helper so every event carries the correlation ID
        def _ev(event_type: str, skill=None, payload=None, error=None):
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

        yield _ev(
            "start",
            payload={
                "goal": goal.objective,
                "skills": strategy.ordered_skills,
            },
        )

        # Group skills for parallel execution
        enable_parallel = getattr(
            goal, "metadata", {}
        ).get("enable_parallel", True)
        skill_groups = (
            _get_parallel_groups(strategy.ordered_skills)
            if enable_parallel
            else [[s] for s in strategy.ordered_skills]
        )

        for skill_group in skill_groups:
            if len(skill_group) == 1:
                # Sequential execution for single skill
                skill_name = skill_group[0]
                yield _ev("skill_start", skill=skill_name)

                # Input guardrails check
                input_violations = _validate_input_guardrails(ctx, skill_name)
                if input_violations:
                    error_msg = (
                        "Input guardrail violations: " +
                        ", ".join(input_violations)
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
                    errors.append(f"{skill_name}: {error_msg}")
                    break

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
                    # Validate cached result against output guardrails
                    output_violations = _validate_output_guardrails(
                        cached_result, skill_name
                    )
                    if output_violations:
                        error_msg = (
                            "Cached result failed guardrails: " +
                            ", ".join(output_violations)
                        )
                        logger.warning(
                            f"Cached result guardrails failed for "
                            f"{skill_name}: {error_msg}"
                        )
                        # Treat cache miss and execute normally
                        cached_result = None
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
                    # No cache hit, execute with retry logic
                    max_retries = get_max_retries(skill_name)
                    last_error = None

                    for attempt in range(max_retries + 1):
                        try:
                            fn = registry.get(skill_name)
                            result = _run_with_timeout(
                                fn, ctx, timeout_seconds
                            )

                            # Output guardrails check
                            output_violations = _validate_output_guardrails(
                                result, skill_name
                            )
                            if output_violations:
                                error_msg = (
                                    "Output guardrail violations: " +
                                    ", ".join(output_violations)
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
                                    skill_name, ctx.data, goal.objective,
                                    result,
                                )

                            yield _ev(
                                "skill_complete",
                                skill=skill_name,
                                payload={
                                    "result": result,
                                    "attempt": attempt + 1
                                },
                            )
                            break
                        except (TimeoutError, SkillExecutionError) as exc:
                            last_error = exc
                            if attempt < max_retries:
                                # Add jitter to prevent thundering herd
                                base_backoff = min(2**attempt, 5)
                                backoff = (
                                    base_backoff * random.uniform(0.8, 1.2)
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
                                errors.append(
                                    f"{skill_name}: {str(last_error)}"
                                )
                                break
                        except Exception as exc:
                            yield _ev(
                                "skill_failed",
                                skill=skill_name,
                                error=str(exc),
                            )
                            errors.append(f"{skill_name}: {str(exc)}")
                            break
            else:
                # Parallel execution for group of skills
                yield _ev(
                    "parallel_start",
                    payload={"skills": skill_group}
                )

                # Check for fail_fast option in goal metadata
                fail_fast = getattr(
                    goal, "metadata", {}
                ).get("fail_fast", False)

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
                                "Cached result failed guardrails: " +
                                ", ".join(output_violations)
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

                # Execute non-cached skills in parallel
                # Limit max workers to prevent resource exhaustion
                max_workers = min(8, len(skills_to_execute))
                with concurrent.futures.ThreadPoolExecutor(
                    max_workers=max_workers
                ) as pool:
                    future_to_skill = {}
                    for skill_name in skills_to_execute:
                        # Input guardrails check before parallel execution
                        input_violations = _validate_input_guardrails(
                            ctx, skill_name
                        )
                        if input_violations:
                            error_msg = (
                                "Guardrail violations: " +
                                ", ".join(input_violations)
                            )
                            logger.warning(
                                f"Input guardrails failed for "
                                f"{skill_name}: {error_msg}"
                            )
                            yield _ev(
                                "skill_failed",
                                skill=skill_name,
                                error=error_msg,
                            )
                            errors.append(f"{skill_name}: {error_msg}")
                            # If fail_fast is enabled, cancel all futures
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
                        ctx_copy.data = copy.deepcopy(ctx.data)
                        future = pool.submit(
                            _run_with_timeout, fn, ctx_copy,
                            timeout_seconds
                        )
                        future_to_skill[future] = skill_name

                    # Track if any skill failed for fail_fast logic
                    any_failed = False

                    for future in concurrent.futures.as_completed(
                        future_to_skill
                    ):
                        skill_name = future_to_skill[future]
                        try:
                            result = future.result()

                            # Output guardrails check after execution
                            output_violations = (
                                _validate_output_guardrails(
                                    result, skill_name
                                )
                            )
                            if output_violations:
                                error_msg = (
                                    "Output guardrail violations: " +
                                    ", ".join(output_violations)
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
                                errors.append(f"{skill_name}: {error_msg}")
                                any_failed = True
                                if fail_fast:
                                    break
                                continue

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
                            errors.append(f"{skill_name}: {str(exc)}")
                            any_failed = True
                            if fail_fast:
                                break
                        except Exception as exc:
                            yield _ev(
                                "skill_failed",
                                skill=skill_name,
                                error=str(exc),
                            )
                            errors.append(f"{skill_name}: {str(exc)}")
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
                            output_violations = (
                                _validate_output_guardrails(
                                    result, skill_name
                                )
                            )
                            if not output_violations:
                                cache.set(
                                    skill_name, ctx.data,
                                    goal.objective, result
                                )

                yield _ev(
                    "parallel_complete",
                    payload={"skills": skill_group}
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
                summary = _run_with_timeout(
                    registry.get(skill_name), ctx, timeout_seconds
                )
                outputs.append({skill_name: summary})
                yield _ev(
                    "skill_complete",
                    skill=skill_name,
                    payload={"result": summary},
                )
            except Exception as e:
                # Review failures don't fail the entire execution
                errors.append(f"Review failed: {str(e)}")

        yield _ev(
            "complete",
            payload={
                "status": "completed" if not errors else "failed",
                "outputs": outputs,
                "errors": errors,
                "final_context": ctx.data,
            },
        )

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
