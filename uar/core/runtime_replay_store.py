from __future__ import annotations

import sqlite3
from pathlib import Path

from .replay_certificate import ReplayCertificate


class RuntimeReplayStore:
    """Persistence layer for replay certificates."""

    def __init__(self, database_path: str = "uar_runtime.db") -> None:
        self.database_path = Path(database_path)

    def initialize(self) -> None:
        connection = sqlite3.connect(self.database_path)
        try:
            cursor = connection.cursor()
            cursor.execute(
                "CREATE TABLE IF NOT EXISTS replay_certificates ("
                "replay_id TEXT PRIMARY KEY,"
                "topology_hash TEXT NOT NULL,"
                "semantic_hash TEXT NOT NULL,"
                "governance_hash TEXT NOT NULL,"
                "certificate_hash TEXT NOT NULL"
                ")"
            )
            connection.commit()
        finally:
            connection.close()

    def insert_certificate(self, certificate: ReplayCertificate) -> None:
        connection = sqlite3.connect(self.database_path)
        try:
            cursor = connection.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO replay_certificates ("
                "replay_id, topology_hash, semantic_hash, governance_hash, certificate_hash"
                ") VALUES (?, ?, ?, ?, ?)",
                (
                    certificate.replay_id,
                    certificate.topology_hash,
                    certificate.semantic_hash,
                    certificate.governance_hash,
                    certificate.certificate_hash,
                ),
            )
            connection.commit()
        finally:
            connection.close()
