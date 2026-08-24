#!/usr/bin/env python3
"""Compare repeated baseline/candidate semantic replay runs distributionally.

Input JSON shape:

{
  "baseline_runs": [{"events": [...], "latency": 0.123}, ...],
  "candidate_runs": [{"events": [...], "latency": 0.125}, ...]
}

Callers should pre-stratify by task class and, when useful, final result. This
script reports validation statistics only; it does not modify Trust Spine
scores.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from uar.core.semantic_statistics import compare_semantic_distributions
from uar.core.semantic_trace import semantic_trace_from_events


def _load_runs(payload: dict, key: str):
    traces = []
    latencies = []
    for item in payload.get(key, []):
        events = item.get("events") or []
        traces.append(semantic_trace_from_events(events))
        if item.get("latency") is not None:
            latencies.append(float(item["latency"]))
    return traces, latencies


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    args = parser.parse_args()

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    baseline, baseline_latencies = _load_runs(payload, "baseline_runs")
    candidate, candidate_latencies = _load_runs(payload, "candidate_runs")

    report = compare_semantic_distributions(
        baseline,
        candidate,
        baseline_latencies=baseline_latencies,
        candidate_latencies=candidate_latencies,
    )

    print(
        json.dumps(
            {
                "baseline_samples": report.baseline_samples,
                "candidate_samples": report.candidate_samples,
                "js_divergence_bits": report.js_divergence_bits,
                "total_variation": report.total_variation,
                "baseline_entropy_bits": report.baseline_entropy_bits,
                "candidate_entropy_bits": report.candidate_entropy_bits,
                "mean_latency_delta": report.mean_latency_delta,
                "p95_latency_delta": report.p95_latency_delta,
                "distribution_equivalent": report.distribution_equivalent,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
