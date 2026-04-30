from __future__ import annotations

import json
import sqlite3
import time
from typing import Any


class LineageStore:
    """Lineage tracking extracted from main.py.

    Phase 3 status: add-only. Not yet wired into main execution.
    """

    def __init__(self, db_path: str = "uar.sqlite3") -> None:
        self.db_path = db_path
        self.lineage: dict[str, list[dict[str, Any]]] = {}

    def db(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        with self.db() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS lineage (digest TEXT NOT NULL, event_json TEXT NOT NULL)")
            conn.commit()

    def load(self) -> None:
        self.lineage.clear()
        with self.db() as conn:
            for row in conn.execute("SELECT digest, event_json FROM lineage"):
                self.lineage.setdefault(row["digest"], []).append(json.loads(row["event_json"]))

    def persist_lineage(self, digest: str, event: dict[str, Any]) -> None:
        with self.db() as conn:
            conn.execute(
                "INSERT INTO lineage (digest, event_json) VALUES (?, ?)",
                (digest, json.dumps(event, sort_keys=True)),
            )
            conn.commit()

    def add_event(self, digest: str, event: dict[str, Any]) -> None:
        event = {**event, "timestamp": time.time()}
        self.lineage.setdefault(digest, []).append(event)
        self.persist_lineage(digest, event)

    def trace(self, digest: str) -> list[dict[str, Any]]:
        return self.lineage.get(digest, [])
