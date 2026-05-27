"""Runtime lineage persistence scaffolding."""

from __future__ import annotations

import sqlite3
from pathlib import Path


class RuntimeLineageStore:
    def __init__(self, database_path: str = "uar_runtime.db") -> None:
        self.database_path = Path(database_path)

    def initialize(self) -> None:
        connection = sqlite3.connect(self.database_path)
        cursor = connection.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS replay_lineage (
                replay_id TEXT PRIMARY KEY,
                topology_hash TEXT NOT NULL,
                semantic_hash TEXT NOT NULL,
                governance_hash TEXT NOT NULL,
                certificate_hash TEXT NOT NULL
            )
            """
        )

        connection.commit()
        connection.close()
