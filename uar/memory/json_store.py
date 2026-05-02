import json
from dataclasses import asdict
from pathlib import Path
from typing import List

from uar.core.contracts import RunRecord


class JsonRunStore:
    """Append-only JSONL storage for UAR run records.

    This keeps persistence simple, portable, and easy to inspect before
    introducing SQLite or a distributed event ledger.
    """

    def __init__(self, path: str = "runs/uar_runs.jsonl"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, record: RunRecord) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(record), sort_keys=True) + "\n")

    def list_records(self) -> List[dict]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        return records
