from __future__ import annotations

import json
import os
import re
from typing import Any

MEMORY_FILE = os.getenv("UAR_STRATEGY_MEMORY_FILE", "./.uar_strategy_memory.jsonl")


def _ensure_file():
    os.makedirs(os.path.dirname(MEMORY_FILE) or ".", exist_ok=True)
    if not os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "w", encoding="utf-8"):
            pass


def _tokens(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9_]+", text.lower()) if len(token) > 2}


def _similarity(a: str, b: str) -> float:
    left = _tokens(a)
    right = _tokens(b)
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def record_strategy(goal_text: str, strategy, evaluation: dict[str, Any]):
    _ensure_file()
    entry = {
        "goal": goal_text,
        "goal_tokens": sorted(_tokens(goal_text)),
        "skills": getattr(strategy, "ordered_skills", []),
        "score": evaluation.get("score"),
        "passed": evaluation.get("passed"),
        "reasons": evaluation.get("reasons", []),
    }
    with open(MEMORY_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def get_best_strategies(goal_text: str, limit: int = 3, min_similarity: float = 0.05):
    if not os.path.exists(MEMORY_FILE):
        return []

    matches = []
    with open(MEMORY_FILE, "r", encoding="utf-8") as f:
        for line in f:
            try:
                entry = json.loads(line)
            except Exception:
                continue

            similarity = _similarity(goal_text, entry.get("goal", ""))
            if goal_text.lower() in entry.get("goal", "").lower():
                similarity = max(similarity, 1.0)

            if similarity < min_similarity:
                continue

            score = float(entry.get("score") or 0.0)
            passed_bonus = 0.10 if entry.get("passed") else 0.0
            entry = dict(entry)
            entry["memory_similarity"] = similarity
            entry["memory_rank_score"] = score + passed_bonus + similarity
            matches.append(entry)

    matches.sort(key=lambda x: x.get("memory_rank_score", 0), reverse=True)
    return matches[:limit]
