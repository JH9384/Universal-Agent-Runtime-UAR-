from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

from uar.core.executor import Executor
from uar.core.llm_planner import LLMPlanner, call_ollama
from uar.core.planner import SimplePlanner
from uar.memory.strategy_memory import record_strategy
from uar.core.failure_taxonomy import classify_failure

MAX_ITER = int(os.getenv("UAR_AGENT_MAX_ITERATIONS", "3"))
MIN_EVALUATION_SCORE = float(os.getenv("UAR_MIN_EVALUATION_SCORE", "0.70"))
ENABLE_SEMANTIC_EVALUATOR = os.getenv("UAR_ENABLE_SEMANTIC_EVALUATOR", "false").lower() == "true"


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
    return "\n".join(str(output) for output in outputs or [])


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

    if status == "completed":
        score += 0.30
        reasons.append("status_completed")

    if outputs:
        score += 0.20
        reasons.append("outputs_present")

    if not errors:
        score += 0.15
        reasons.append("no_errors")

    if len(output_text.strip()) >= 20:
        score += 0.10
        reasons.append("output_substantive")

    score = min(score, 1.0)
    return EvaluationResult(score >= MIN_EVALUATION_SCORE, score, reasons, metrics)


class AgentLoop:
    def run(self, goal):
        planner = LLMPlanner()
        executor = Executor()
        feedback = None

        for iteration in range(MAX_ITER):
            strategy = planner.plan(goal, feedback=feedback)
            result = executor.run(strategy, goal)
            evaluation = evaluate_result(result, goal)
            failure = classify_failure(result, evaluation)

            result.final_context["evaluation"] = evaluation.to_dict()
            result.final_context["failure"] = failure.to_dict()
            result.final_context["agent_iteration"] = iteration + 1

            record_strategy(goal.objective, strategy, evaluation.to_dict())

            if evaluation.passed:
                return result

            feedback = evaluation.to_dict()

        strategy = SimplePlanner().plan(goal)
        result = executor.run(strategy, goal)
        evaluation = evaluate_result(result, goal)
        failure = classify_failure(result, evaluation)

        result.final_context["evaluation"] = evaluation.to_dict()
        result.final_context["failure"] = failure.to_dict()
        result.final_context["fallback_used"] = True

        record_strategy(goal.objective, strategy, evaluation.to_dict())

        return result
