#!/usr/bin/env python3
"""Long-duration deterministic soak runner for UAR burn-in."""

from __future__ import annotations

import json
import time
from pathlib import Path

from uar.runtime.hardening.oscillation import OscillationScore
from uar.runtime.hardening.pressure_metrics import PressureLedger, PressureSnapshot


def main() -> int:
    ledger = PressureLedger()
    pressure_values: list[float] = []

    for step in range(60):
        snapshot = PressureSnapshot(
            queue_depth=step,
            websocket_backlog=step // 2,
            propagation_fanout=step * 3,
            mutation_rate=float(step * 10),
        )

        ledger.record(snapshot)
        pressure_values.append(snapshot.pressure_score())
        time.sleep(0.01)

    oscillation = OscillationScore(tuple(pressure_values))

    payload = {
        "summary": ledger.summarize(),
        "oscillation": {
            "score": oscillation.normalized(),
            "stable": oscillation.stable(),
        },
    }

    out = Path("artifacts/hardening/soak_runner.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n")

    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
