from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from uar.core.executor import Executor
from uar.core.llm_planner import LLMPlanner
from uar.core.planner import SimplePlanner

MAX_ITER = int(os.getenv("UAR_AGENT_MAX_ITERATIONS", "3"))
MIN_EVALUATION_SCORE = float(os.getenv("UAR_MIN_EVALUATION_SCORE", "0.70"))


@dataclass
class EvaluationResult:
    passed: bool
    score: float
    reasons: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "score": self.score,
            "reasons": self.reasons,
            "metrics": self.metrics,
        }


def _flatten_outputs(outputs: list[Any]) -> str:
    parts: list[str] = []
    for output in outputs or []:
        parts.append(str(output))
    return "\n".join(parts)


def evaluate_result(result, goal=None) -> EvaluationResult:
    reasons: list[str] = []
    metrics: dict[str, Any] = {}
    score = 0.0

    if not result:
        return EvaluationResult(False, 0.0, ["missing_result"], {})

    status = getattr(result, "status", None)
    outputs = getattr(result, "outputs", []) or []
    errors = getattr(result, "errors", []) or []
    output_text = _flatten_outputs(outputs)

    metrics["status"] = status
    metrics["output_count"] = len(outputs)
    metrics["error_count"] = len(errors)
    metrics["output_chars"] = len(output_text)

    if status == "completed":
        score += 0.35
        reasons.append("status_completed")
    else:
        reasons.append("status_not_completed")

    if outputs:
        score += 0.25
        reasons.append("outputs_present")
    else:
        reasons.append("outputs_missing")

    if not errors:
        score += 0.20
        reasons.append("no_errors")
    else:
        reasons.append("errors_present")

    if len(output_text.strip()) >= 20:
        score += 0.10
        reasons.append("output_substantive")
    else:
        reasons.append("output_thin")

    if goal is not None:
        objective = getattr(goal, "objective", "") or ""
        goal_terms = [term.lower() for term in objective.split() if len(term) > 3]
        matched_terms = [term for term in goal_terms if term in output_text.lower()]
        metrics["goal_terms"] = goal_terms
        metrics["matched_goal_terms"] = matched_terms
        if goal_terms and matched_terms:
            score += 0.10
            reasons.append("goal_terms_reflected")
        elif goal_terms:
            reasons.append("goal_terms_not_reflected")

    score = min(score, 1.0)
    return EvaluationResult(score >= MIN_EVALUATION_SCORE, score, reasons, metrics)


# Backward-compatible boolean evaluator.
def evaluate(result):
    if isinstance(result, dict):
        class Obj:
            pass
        obj = Obj()
        obj.status = result.get("status")
        obj.outputs = result.get("outputs", [])
        obj.errors = result.get("errors", [])
        return evaluate_result(obj).passed
    return evaluate_result(result).passed


class AgentLoop:
    def run(self, goal):
        planner = LLMPlanner()
        executor = Executor()
        last_result = None
        last_evaluation = None

        for _ in range(MAX_ITER):
            strategy = planner.plan(goal)
            result = executor.run(strategy, goal)
            evaluation = evaluate_result(result, goal)
            result.final_context["evaluation"] = evaluation.to_dict()
            last_result = result
            last_evaluation = evaluation

            if evaluation.passed:
                return result

        strategy = SimplePlanner().plan(goal)
        result = executor.run(strategy, goal)
        fallback_evaluation = evaluate_result(result, goal)
        result.final_context["evaluation"] = fallback_evaluation.to_dict()
        result.final_context["previous_agent_evaluation"] = (
            last_evaluation.to_dict() if last_evaluation else None
        )
        result.final_context["previous_agent_status"] = getattr(last_result, "status", None)
        return result
