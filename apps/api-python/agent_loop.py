from __future__ import annotations

from typing import Any, Callable

from run_memory import record_run
from strategy_engine import choose_strategies, score_results

RuntimeExecutor = Callable[[str, list[str]], dict[str, Any]]


def infer_goal(section: dict[str, Any], default: str = "maximize") -> str:
    explicit = str(section.get("goal", "")).strip().lower()
    if explicit:
        return explicit

    runtime_markers = {str(marker).strip().lower() for marker in section.get("runtime_markers", [])}
    if "count" in runtime_markers or "count_inputs" in runtime_markers:
        return "count"
    if "min" in runtime_markers or "min_contents" in runtime_markers:
        return "minimize"
    return default


def run_section_strategy(
    *,
    section: dict[str, Any],
    execute_runtime: RuntimeExecutor,
    record_memory: bool = True,
) -> dict[str, Any]:
    """Execute a goal-aware strategy loop for one parsed section.

    The section payload is intentionally simple and UI-friendly:
    {
      "label": "Finance",
      "goal": "maximize",
      "input_ids": ["sha256:...", "sha256:..."],
      "values": [5, 10],
      "runtime_markers": ["sum"]
    }
    """
    label = str(section.get("label", "section"))
    input_ids = [str(item) for item in section.get("input_ids", [])]
    values = list(section.get("values", []))
    goal = infer_goal(section)
    strategies = choose_strategies(goal, values)

    attempts: list[dict[str, Any]] = []
    scored: list[tuple[str, Any]] = []

    for runtime_name in strategies:
        result = execute_runtime(runtime_name, input_ids)
        value = result.get("result")
        attempts.append(
            {
                "runtime": runtime_name,
                "result": value,
                "output": result.get("output"),
                "executionRecord": result.get("executionRecord"),
            }
        )
        scored.append((runtime_name, value))

    winning_runtime, winning_value = score_results(scored, goal)
    chosen = next((attempt for attempt in attempts if attempt["runtime"] == winning_runtime), None)

    summary = {
        "section": label,
        "goal": goal,
        "strategies": strategies,
        "attempts": attempts,
        "chosen": chosen,
        "result": winning_value,
    }

    if record_memory:
        record_run(
            {
                "kind": "agent_strategy_run",
                "section": label,
                "goal": goal,
                "strategies": strategies,
                "chosen_runtime": winning_runtime,
                "result": winning_value,
            }
        )

    return summary


def run_document_strategy(
    *,
    sections: list[dict[str, Any]],
    execute_runtime: RuntimeExecutor,
) -> dict[str, Any]:
    runs = [
        run_section_strategy(section=section, execute_runtime=execute_runtime)
        for section in sections
    ]
    return {"status": "completed", "sections": runs}
