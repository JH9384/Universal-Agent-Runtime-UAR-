from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

DB_FILE = Path("uar_run_memory.sqlite3")


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_memory() -> None:
    with _conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS run_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT NOT NULL,
                section TEXT,
                goal TEXT,
                chosen_runtime TEXT,
                result_json TEXT,
                entry_json TEXT NOT NULL,
                created_at REAL NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_run_memory_kind ON run_memory(kind)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_run_memory_goal ON run_memory(goal)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_run_memory_runtime ON run_memory(chosen_runtime)")
        conn.commit()


def record_run(entry: dict[str, Any]) -> None:
    init_memory()
    created_at = time.time()
    normalized = {
        **entry,
        "timestamp": created_at,
    }
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO run_memory
                (kind, section, goal, chosen_runtime, result_json, entry_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(normalized.get("kind", "run")),
                normalized.get("section"),
                normalized.get("goal"),
                normalized.get("chosen_runtime"),
                json.dumps(normalized.get("result"), sort_keys=True),
                json.dumps(normalized, sort_keys=True),
                created_at,
            ),
        )
        conn.commit()


def query_runs(
    *,
    kind: str | None = None,
    goal: str | None = None,
    chosen_runtime: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    init_memory()
    clauses: list[str] = []
    params: list[Any] = []

    if kind:
        clauses.append("kind = ?")
        params.append(kind)
    if goal:
        clauses.append("goal = ?")
        params.append(goal)
    if chosen_runtime:
        clauses.append("chosen_runtime = ?")
        params.append(chosen_runtime)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    safe_limit = max(1, min(int(limit), 500))

    with _conn() as conn:
        rows = conn.execute(
            f"SELECT entry_json FROM run_memory {where} ORDER BY created_at DESC LIMIT ?",
            [*params, safe_limit],
        ).fetchall()

    return [json.loads(row["entry_json"]) for row in rows]


def summarize_runtime_success(goal: str | None = None) -> dict[str, Any]:
    runs = query_runs(kind="agent_strategy_run", goal=goal, limit=500)
    summary: dict[str, dict[str, Any]] = {}
    for run in runs:
        runtime = run.get("chosen_runtime") or "unknown"
        bucket = summary.setdefault(runtime, {"count": 0, "last_result": None})
        bucket["count"] += 1
        bucket["last_result"] = run.get("result")
    return {"goal": goal, "runtimes": summary}
