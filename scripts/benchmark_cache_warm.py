"""Verify D4A-1: aggregate endpoints < 10 ms with cache warm at 10k runs."""

from __future__ import annotations

import json
import os
import random
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient

from uar.api.state import set_service_container
from uar.container import ServiceContainer
from uar.memory.sqlite_store import SqliteRunStore

SKILLS = [
    "math",
    "graph",
    "verilog",
    "riscv",
    "autonomi",
    "molecule",
    "quantum",
    "physics",
]
RECIPES = ["math_graph", "hardware_suite", "science_bundle"]
STATUSES = ["success", "failed", "partial"]


def _synthetic_run(run_id: str, idx: int, now: float) -> dict:
    num_events = random.randint(5, 50)
    events = []
    has_fail = random.random() < 0.15
    for i in range(num_events):
        ev = {
            "type": random.choice(
                ["skill_start", "skill_end", "heartbeat", "error"]
            ),
            "skill": random.choice(SKILLS),
            "timestamp": now - (num_events - i) * 60,
        }
        if has_fail and random.random() < 0.3:
            ev["error"] = random.choice(
                [
                    "timeout",
                    "connection refused",
                    "assertion failed",
                    "index out of range",
                    "schema mismatch",
                ]
            )
            ev["type"] = "error"
        events.append(ev)

    skills_used = list({e["skill"] for e in events if e.get("skill")})
    status = (
        "failed"
        if has_fail
        else random.choice(["success", "success", "partial"])
    )

    exec_order = []
    if random.random() < 0.4:
        exec_order.append(
            {"type": "recipe", "content": random.choice(RECIPES)}
        )
    for s in skills_used:
        exec_order.append({"type": "skill", "content": s})

    return {
        "run_id": run_id,
        "goal_id": f"goal_{idx}",
        "user_id": "benchmark_user",
        "status": status,
        "skills": json.dumps(skills_used),
        "events": json.dumps(events),
        "outputs": json.dumps({}),
        "metadata": json.dumps({"execution_order": exec_order}),
        "uor_address": None,
        "uor_witness": None,
        "created_at": now - random.randint(0, 3600 * 24 * 7),
    }


def _seed_store(store: SqliteRunStore, n: int) -> None:
    now = time.time()
    conn = sqlite3.connect(str(store._path))
    try:
        for i in range(n):
            run = _synthetic_run(f"run_{n}_{i:06d}", i, now)
            conn.execute(
                """
                INSERT INTO uar_runs
                (run_id, goal_id, user_id, status, skills, events,
                 outputs, metadata, uor_address, uor_witness, created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    run["run_id"],
                    run["goal_id"],
                    run["user_id"],
                    run["status"],
                    run["skills"],
                    run["events"],
                    run["outputs"],
                    run["metadata"],
                    run["uor_address"],
                    run["uor_witness"],
                    run["created_at"],
                ),
            )
        conn.commit()
    finally:
        conn.close()
    store.list_records(limit=n)


def main():
    n = 10000
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "bench.db")
        store = SqliteRunStore(path=db_path)
        _seed_store(store, n)

        container = ServiceContainer()
        container._store = store
        set_service_container(container)

        from uar.api.server import app

        client = TestClient(app)

        # Inject auth key
        import uar.api.middleware as _mw

        _mw.API_KEYS["bench-key"] = {"user": "benchmark_user", "tier": "admin"}
        headers = {"Authorization": "Bearer bench-key"}

        endpoints = [
            ("/api/uar/confidence-drift", "ConfidenceDrift"),
            ("/api/uar/alerts/summary", "AlertsSummary"),
            ("/api/uar/recommendations", "Recommendations"),
            ("/api/uar/runs/failure-clusters", "FailureClusters"),
            (
                "/api/uar/topology/analytics?mode=success",
                "TopologyAnalyticsSuccess",
            ),
            (
                "/api/uar/topology/analytics?mode=failure",
                "TopologyAnalyticsFailure",
            ),
            ("/api/uar/recipes/intelligence", "RecipeIntelligence"),
        ]

        print(f"=== D4A-1 Cache-Warm Benchmark ({n} runs) ===\n")

        for path, label in endpoints:
            # Warm cache (first call)
            resp = client.get(path, headers=headers)
            assert resp.status_code == 200, f"{label} failed: {resp.text}"

            # Measure cache-warm calls
            times = []
            for _ in range(5):
                t0 = time.perf_counter()
                resp = client.get(path, headers=headers)
                t1 = time.perf_counter()
                assert resp.status_code == 200
                times.append((t1 - t0) * 1000)

            times.sort()
            median = times[len(times) // 2]
            status = "PASS" if median < 10 else "FAIL"
            all_times = ", ".join(f"{duration:.1f}" for duration in times)
            print(
                f"  {label:20s}  median={median:8.2f}ms  {status}  "
                f"(all: {all_times})ms"
            )

        print("\nD4A-1 target: median < 10 ms at 10,000 runs (cache warm)")


if __name__ == "__main__":
    main()
