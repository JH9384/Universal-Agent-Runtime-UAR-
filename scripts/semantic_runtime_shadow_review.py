"""Exercise real Executor paths under the Ω-7B.S shadow observer."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from typing import Any

import uar.core.executor as executor_module
from uar.core.contracts import GoalSpec, StrategySpec
from uar.core.exceptions import SkillExecutionError, TimeoutError
from uar.core.executor import Executor
from uar.core.registry import registry
from uar.core.semantic_shadow import (
    measure_shadow_observer_overhead,
    pair_runtime_with_shadow,
)
from uar.core.semantic_trace import validate_semantic_trace


def _register(name: str, function) -> None:
    if not registry.is_registered(name):
        registry.register(name, function)


def _goal(name: str, *, parallel: bool = False) -> GoalSpec:
    return GoalSpec(
        id=f"semantic-shadow-{name}",
        user_intent=f"validate {name} shadow path",
        objective=f"execute {name} deterministically",
        metadata={"enable_cache": False, "enable_parallel": parallel},
    )


def _pair(name: str, strategy: StrategySpec, goal: GoalSpec):
    return pair_runtime_with_shadow(
        lambda: Executor().iter_events(
            strategy,
            goal,
            timeout_seconds=1.0,
            _run_id=f"semantic-shadow-{name}",
        )
    )


def _scenario_report(name: str, pair, iterations: int) -> dict[str, Any]:
    issues = validate_semantic_trace(pair.semantic_trace)
    overhead = measure_shadow_observer_overhead(
        pair.baseline_events, iterations=iterations
    )
    return {
        "name": name,
        "baseline_events": len(pair.baseline_events),
        "shadow_events": len(pair.shadow_events),
        "semantic_stages": len(pair.semantic_trace.stages),
        "projected_events_equal": pair.projected_events_equal,
        "integrity_issues": [asdict(issue) for issue in issues],
        "overhead": asdict(overhead),
        "within_overhead_envelope": overhead.within_envelope,
    }


def build_report(iterations: int) -> dict[str, Any]:
    _register("omega_shadow_identity", lambda _: {"value": 1})
    _register("omega_shadow_double", lambda _: {"value": 2})
    _register("omega_shadow_left", lambda _: {"branch": "left"})
    _register("omega_shadow_right", lambda _: {"branch": "right"})
    _register("omega_shadow_join", lambda _: {"joined": True})

    def reject(_):
        raise RuntimeError("rejected by validation corpus")

    def timeout(_):
        raise TimeoutError(0.01)

    retry_attempt = {"value": 0}

    def retry(_):
        retry_attempt["value"] += 1
        if retry_attempt["value"] == 1:
            raise SkillExecutionError(
                "omega_shadow_retry", RuntimeError("transient")
            )
        return {"recovered": True}

    _register("omega_shadow_reject", reject)
    _register("omega_shadow_timeout", timeout)
    _register("omega_shadow_retry", retry)

    scenarios = []
    sequential_goal = _goal("sequential")
    scenarios.append(
        (
            "sequential",
            _pair(
                "sequential",
                StrategySpec(
                    goal_id=sequential_goal.id,
                    ordered_skills=[
                        "omega_shadow_identity",
                        "omega_shadow_double",
                    ],
                ),
                sequential_goal,
            ),
        )
    )

    dag_goal = _goal("dag", parallel=True)
    scenarios.append(
        (
            "dag_parallel",
            _pair(
                "dag",
                StrategySpec(
                    goal_id=dag_goal.id,
                    ordered_skills=[
                        "omega_shadow_left",
                        "omega_shadow_right",
                        "omega_shadow_join",
                    ],
                    waves=[
                        ["omega_shadow_left", "omega_shadow_right"],
                        ["omega_shadow_join"],
                    ],
                ),
                dag_goal,
            ),
        )
    )

    old_policies = dict(executor_module.SKILL_RETRY_POLICIES)
    executor_module.SKILL_RETRY_POLICIES.update(
        {
            "omega_shadow_retry": 1,
            "omega_shadow_timeout": 0,
        }
    )
    try:
        for name in ("reject", "timeout", "retry"):
            goal = _goal(name)
            scenarios.append(
                (
                    name,
                    _pair(
                        name,
                        StrategySpec(
                            goal_id=goal.id,
                            ordered_skills=[f"omega_shadow_{name}"],
                        ),
                        goal,
                    ),
                )
            )
    finally:
        executor_module.SKILL_RETRY_POLICIES.clear()
        executor_module.SKILL_RETRY_POLICIES.update(old_policies)

    reports = [
        _scenario_report(name, pair, iterations) for name, pair in scenarios
    ]
    passed = all(
        item["projected_events_equal"]
        and not item["integrity_issues"]
        and item["within_overhead_envelope"]
        for item in reports
    )
    return {
        "schema": "uar.semantic-shadow-runtime-review.v1",
        "iterations_per_scenario": iterations,
        "passed": passed,
        "scenarios": reports,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=250)
    args = parser.parse_args()
    report = build_report(args.iterations)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
