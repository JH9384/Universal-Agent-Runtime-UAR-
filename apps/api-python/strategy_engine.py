from __future__ import annotations

from typing import Any

STRATEGIES = {
    "maximize": ["sum_contents", "max_contents"],
    "minimize": ["min_contents"],
    "count": ["count_inputs"],
}


def choose_strategies(goal: str, values: list[Any]) -> list[str]:
    if goal not in STRATEGIES:
        return []
    return STRATEGIES[goal]


def score_results(results: list[tuple[str, Any]], goal: str) -> tuple[str, Any]:
    if not results:
        return None, None

    if goal == "maximize":
        return max(results, key=lambda x: x[1])
    if goal == "minimize":
        return min(results, key=lambda x: x[1])

    return results[0]
