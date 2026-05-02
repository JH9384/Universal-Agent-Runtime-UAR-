from __future__ import annotations

import json
import time
from typing import Any

DB_FILE = "uar_run_memory.jsonl"


def record_run(entry: dict[str, Any]) -> None:
    entry = {
        **entry,
        "timestamp": time.time(),
    }
    with open(DB_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
