import concurrent.futures
import time
import uuid
from typing import Iterator

from .contracts import PipelineContext, RunRecord, StrategySpec
from .exceptions import SkillExecutionError, SkillNotFoundError, TimeoutError, ValidationError
from .registry import registry
from .validation import validate_timeout


def _run_with_timeout(fn, ctx, timeout_seconds):
    """Run a function with timeout using thread pool with proper cleanup."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(fn, ctx)
        try:
            return future.result(timeout=timeout_seconds)
        except concurrent.futures.TimeoutError as exc:
            # Cancel the future if possible
            future.cancel()
            raise TimeoutError(timeout_seconds) from exc
        except Exception:
            # Ensure future is cancelled on any exception
            future.cancel()
            raise


def _event(event_type: str, run_id: str, goal_id: str, skill=None, payload=None, error=None):
    return {
        "schema_version": "uar.event.v1",
        "type": event_type,
        "run_id": run_id,
        "goal_id": goal_id,
        "skill": skill,
        "timestamp": time.time(),
        "payload": payload or {},
        "error": error,
    }


class Executor:
    def iter_events(self, strategy: StrategySpec, goal, timeout_seconds=5) -> Iterator[dict]:
        """Execute strategy and yield events with proper error handling"""
        # Validate inputs
        timeout_seconds = validate_timeout(timeout_seconds)
        
        if not strategy.ordered_skills:
            raise ValidationError("At least one skill must be specified", field="skills")
        
        run_id = str(uuid.uuid4())
        ctx = PipelineContext(goal=goal)
        outputs = []
        errors = []

        # Validate all skills exist before execution
        missing_skills = []
        for skill_name in strategy.ordered_skills:
            if not registry.is_registered(skill_name):
                missing_skills.append(skill_name)
        
        if missing_skills:
            # Return failed run instead of raising
            error_msg = f"Skill(s) not found: {', '.join(missing_skills)}"
            yield _event(
                "start",
                run_id,
                strategy.goal_id,
                payload={"goal": goal.objective, "skills": strategy.ordered_skills},
            )
            yield _event(
                "complete",
                run_id,
                strategy.goal_id,
                payload={
                    "status": "failed",
                    "outputs": [],
                    "errors": [error_msg],
                    "final_context": {},
                },
            )
            return

        yield _event(
            "start",
            run_id,
            strategy.goal_id,
            payload={"goal": goal.objective, "skills": strategy.ordered_skills},
        )

        for skill_name in strategy.ordered_skills:
            yield _event("skill_start", run_id, strategy.goal_id, skill=skill_name)
            try:
                fn = registry.get(skill_name)
                result = _run_with_timeout(fn, ctx, timeout_seconds)
                ctx.data[skill_name] = result
                outputs.append({skill_name: result})
                yield _event(
                    "skill_complete",
                    run_id,
                    strategy.goal_id,
                    skill=skill_name,
                    payload={"result": result},
                )
            except TimeoutError as e:
                message = str(e)
                errors.append(message)
                yield _event("skill_failed", run_id, strategy.goal_id, skill=skill_name, error=message)
                yield _event(
                    "complete",
                    run_id,
                    strategy.goal_id,
                    payload={
                        "status": "failed",
                        "outputs": outputs,
                        "errors": errors,
                        "final_context": ctx.data,
                    },
                )
                return
            except SkillExecutionError as e:
                message = str(e)
                errors.append(message)
                yield _event("skill_failed", run_id, strategy.goal_id, skill=skill_name, error=message)
                yield _event(
                    "complete",
                    run_id,
                    strategy.goal_id,
                    payload={
                        "status": "failed",
                        "outputs": outputs,
                        "errors": errors,
                        "final_context": ctx.data,
                    },
                )
                return
            except Exception as e:
                message = str(e)
                errors.append(message)
                yield _event("skill_failed", run_id, strategy.goal_id, skill=skill_name, error=message)
                yield _event(
                    "complete",
                    run_id,
                    strategy.goal_id,
                    payload={
                        "status": "failed",
                        "outputs": outputs,
                        "errors": errors,
                        "final_context": ctx.data,
                    },
                )
                return

        # Optional sum_review skill - only run when explicitly opted in via
        # goal metadata, so implicit execution does not diverge from the
        # requested skill list.
        opt_in_review = bool(getattr(goal, "metadata", {}).get("auto_sum_review"))
        if (
            opt_in_review
            and registry.is_registered("sum_review")
            and "sum_review" not in strategy.ordered_skills
        ):
            skill_name = "sum_review"
            yield _event("skill_start", run_id, strategy.goal_id, skill=skill_name)
            try:
                summary = _run_with_timeout(registry.get(skill_name), ctx, timeout_seconds)
                outputs.append({skill_name: summary})
                yield _event(
                    "skill_complete",
                    run_id,
                    strategy.goal_id,
                    skill=skill_name,
                    payload={"result": summary},
                )
            except Exception as e:
                # Review failures don't fail the entire execution
                errors.append(f"Review failed: {str(e)}")

        yield _event(
            "complete",
            run_id,
            strategy.goal_id,
            payload={
                "status": "completed" if not errors else "failed",
                "outputs": outputs,
                "errors": errors,
                "final_context": ctx.data,
            },
        )

    def run(self, strategy: StrategySpec, goal, timeout_seconds=5) -> RunRecord:
        """Execute strategy and return RunRecord"""
        timeout_seconds = validate_timeout(timeout_seconds)
        events = list(self.iter_events(strategy, goal, timeout_seconds=timeout_seconds))
        
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
