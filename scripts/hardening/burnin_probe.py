#!/usr/bin/env python3
"""Deterministic runtime hardening probe for UAR."""

from __future__ import annotations

import json
from pathlib import Path

from uar.runtime.hardening.pressure_metrics import PressureLedger, PressureSnapshot
from uar.runtime.hardening.replay_score import ReplayScore


SCENARIOS = {
    "steady": PressureSnapshot(),
    "observer_pressure": PressureSnapshot(
        websocket_backlog=800,
        observer_lag_ms=300,
    ),
    "topology_pressure": PressureSnapshot(
        propagation_fanout=25_000,
        mutation_rate=50_000,
    ),
}


def main() -> int:
    ledger = PressureLedger()
    rows = []

    for name, snapshot in SCENARIOS.items():
        ledger.record(snapshot)

        replay = ReplayScore(
            total_events=1000,
            missing_events=0,
            duplicate_events=0,
            out_of_order_events=0,
            invalid_events=0,
        )

        rows.append(
            {
                "scenario": name,
                "pressure": snapshot.pressure_score(),
                "replay_confidence": replay.confidence(),
                "replay_divergence": replay.divergence(),
            }
        )

    payload = {
        "summary": ledger.summarize(),
        "results": rows,
    }

    out = Path("artifacts/hardening/burnin_probe.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n")

    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
