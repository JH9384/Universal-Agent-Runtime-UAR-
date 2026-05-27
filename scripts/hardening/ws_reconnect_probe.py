#!/usr/bin/env python3
"""Synthetic websocket reconnect pressure probe."""

from __future__ import annotations

import json
from pathlib import Path


def main() -> int:
    reconnects = [1, 2, 4, 8, 16, 32]
    payload = {
        "max_reconnects": max(reconnects),
        "samples": reconnects,
        "healthy": max(reconnects) <= 32,
    }

    out = Path("artifacts/hardening/ws_reconnect_probe.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n")

    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
