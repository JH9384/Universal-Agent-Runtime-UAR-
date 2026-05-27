from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict


@dataclass(slots=True)
class RuntimePersistenceRecord:
    record_id: str
    category: str
    payload: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "category": self.category,
            "payload": self.payload,
        }


class RuntimePersistenceStore:
    def __init__(self, database_path: str = "uar_runtime_ops.db") -> None:
        self.database_path = Path(database_path)

    def initialize(self) -> None:
        connection = sqlite3.connect(self.database_path)
        try:
            cursor = connection.cursor()
            cursor.execute(
                "CREATE TABLE IF NOT EXISTS runtime_records ("
                "record_id TEXT PRIMARY KEY,"
                "category TEXT NOT NULL,"
                "payload TEXT NOT NULL"
                ")"
            )
            connection.commit()
        finally:
            connection.close()

    def put(self, record: RuntimePersistenceRecord) -> None:
        connection = sqlite3.connect(self.database_path)
        try:
            cursor = connection.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO runtime_records "
                "(record_id, category, payload) VALUES (?, ?, ?)",
                (record.record_id, record.category, record.payload),
            )
            connection.commit()
        finally:
            connection.close()

    def get(self, record_id: str) -> RuntimePersistenceRecord | None:
        connection = sqlite3.connect(self.database_path)
        try:
            cursor = connection.cursor()
            row = cursor.execute(
                "SELECT record_id, category, payload FROM runtime_records WHERE record_id = ?",
                (record_id,),
            ).fetchone()
        finally:
            connection.close()

        if row is None:
            return None

        return RuntimePersistenceRecord(
            record_id=row[0],
            category=row[1],
            payload=row[2],
        )
