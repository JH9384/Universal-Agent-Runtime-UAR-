from __future__ import annotations

import json
import os
from typing import Any

MEMORY_FILE = os.getenv("UAR_STRATEGY_MEMORY_FILE", "./.uar_strategy_memory.jsonl")


def _ensure_file():
    os.makedirs(os.path.dirname(MEMORY_FILE) or ".", exist_ok=True)
    if not os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "w", encoding="utf-8"):
            pass


def record_strategy(goal_text: str, strategy, evaluation: dict[str, Any]):
    _ensure_file()
    entry = {
        "goal": goal_text,
        "skills": getattr(strategy, "ordered_skills", []),
        "score": evaluation.get("score"),
        "passed": evaluation.get("passed"),
        "reasons": evaluation.get("reasons", []),
    }
    with open(MEMORY_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def get_best_strategies(goal_text: str, limit: int = 3):
    if not os.path.exists(MEMORY_FILE):
        return []

    matches = []
    with open(MEMORY_FILE, "r", encoding="utf-8") as f:
        for line in f:
            try:
                entry = json.loads(line)
            except Exception:
                continue
            if goal_text.lower() in entry.get("goal", "").lower():
                matches.append(entry)

    matches.sort(key=lambda x: x.get("score", 0), reverse=True)
    return matches[:limit]
