import concurrent.futures
import os
import time
import uuid
from typing import Iterator

from .contracts import PipelineContext, RunRecord, StrategySpec
from .exceptions import SkillExecutionError, TimeoutError, ValidationError
from .registry import registry
from .validation import validate_timeout


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

        if not strategy.ordered_skills:
            raise ValidationError(
                "At least one skill must be specified", field="skills"
            )

        run_id = str(uuid.uuid4())
        ctx = PipelineContext(goal=goal)
        outputs = []
        errors = []

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

        for skill_name in strategy.ordered_skills:
            yield _ev("skill_start", skill=skill_name)

            # Retry logic for skill execution
            max_retries = get_max_retries(skill_name)
            last_error = None

            for attempt in range(max_retries + 1):
                try:
                    fn = registry.get(skill_name)
                    result = _run_with_timeout(fn, ctx, timeout_seconds)
                    ctx.data[skill_name] = result
                    outputs.append({skill_name: result})
                    yield _ev(
                        "skill_complete",
                        skill=skill_name,
                        payload={"result": result, "attempt": attempt + 1},
                    )
                    break  # Success, exit retry loop
                except (TimeoutError, SkillExecutionError) as exc:
                    last_error = exc
                    if attempt < max_retries:
                        # Retry with exponential backoff
                        backoff = min(2**attempt, 5)  # Max 5 seconds
                        yield _ev(
                            "skill_retry",
                            skill=skill_name,
                            payload={
                                "attempt": attempt + 1,
                                "backoff": backoff,
                                "error": str(exc),
                            },
                        )
                        time.sleep(backoff)
                    else:
                        # Max retries exceeded
                        yield _ev(
                            "skill_failed",
                            skill=skill_name,
                            error=str(last_error),
                            payload={"attempts": attempt + 1},
                        )
                        errors.append(f"{skill_name}: {str(last_error)}")
                        break
                except Exception as exc:
                    # Non-retryable error
                    yield _ev(
                        "skill_failed",
                        skill=skill_name,
                        error=str(exc),
                    )
                    errors.append(f"{skill_name}: {str(exc)}")
                    break

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
