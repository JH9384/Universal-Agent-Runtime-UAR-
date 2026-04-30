from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from typing import Any, Literal

from fastapi import HTTPException

ObjectMode = Literal["immutable", "mutable", "collection"]


def canonical_digest(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def timestamp() -> float:
    return time.time()


class ObjectStore:
    """Small persistence helper extracted from main.py.

    Phase 3 status: add-only module. Not wired into main.py yet.
    """

    def __init__(self, db_path: str = "uar.sqlite3") -> None:
        self.db_path = db_path
        self.store: dict[str, dict[str, Any]] = {}

    def db(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        with self.db() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS objects (digest TEXT PRIMARY KEY, record_json TEXT NOT NULL)")
            conn.commit()

    def load(self) -> None:
        self.store.clear()
        with self.db() as conn:
            for row in conn.execute("SELECT digest, record_json FROM objects"):
                self.store[row["digest"]] = json.loads(row["record_json"])

    def persist_object(self, record: dict[str, Any]) -> None:
        with self.db() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO objects (digest, record_json) VALUES (?, ?)",
                (record["digest"], json.dumps(record, sort_keys=True)),
            )
            conn.commit()

    def create_record(
        self,
        *,
        mediaType: str,
        mode: ObjectMode,
        attributes: dict[str, Any],
        links: list[dict[str, Any]],
        content: Any,
    ) -> dict[str, Any]:
        envelope = {
            "mediaType": mediaType,
            "mode": mode,
            "schema": attributes.get("schema", "uor.schema.object.v1"),
            "attributes": attributes,
            "links": links,
            "content": content,
        }
        digest = canonical_digest(envelope)
        record = {
            "digest": digest,
            "size": len(json.dumps(envelope, sort_keys=True)),
            "created_at": timestamp(),
            **envelope,
        }
        self.store[digest] = record
        self.persist_object(record)
        return record

    def get_obj(self, digest: str) -> dict[str, Any]:
        if digest not in self.store:
            raise HTTPException(status_code=404, detail=f"Object not found: {digest}")
        return self.store[digest]


def audit_object_integrity(record: dict[str, Any]) -> dict[str, Any]:
    envelope = {k: record[k] for k in ("mediaType", "mode", "schema", "attributes", "links", "content")}
    expected = canonical_digest(envelope)
    return {"object": record.get("digest"), "expected": expected, "valid": expected == record.get("digest")}
