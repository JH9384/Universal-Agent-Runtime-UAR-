#!/usr/bin/env python3
"""Review sanitized operational history without exposing raw events."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from uar.core.semantic_history import (
    HistoryGateThresholds,
    review_semantic_history,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--trusted-key-id", required=True)
    parser.add_argument("--trusted-public-key", required=True, type=Path)
    parser.add_argument("--min-samples-per-cohort", type=int, default=20)
    parser.add_argument("--max-js", type=float, default=0.02)
    parser.add_argument("--max-tv", type=float, default=0.05)
    parser.add_argument("--max-telemetry-loss", type=float, default=0.01)
    parser.add_argument(
        "--max-telemetry-loss-delta", type=float, default=0.005
    )
    parser.add_argument("--max-paired-different", type=float, default=0.0)
    parser.add_argument("--max-paired-indeterminate", type=float, default=0.0)
    args = parser.parse_args()

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    report = review_semantic_history(
        payload,
        thresholds=HistoryGateThresholds(
            min_samples_per_cohort=args.min_samples_per_cohort,
            max_js_divergence_bits=args.max_js,
            max_total_variation=args.max_tv,
            max_telemetry_loss_rate=args.max_telemetry_loss,
            max_telemetry_loss_delta=args.max_telemetry_loss_delta,
            max_paired_different_rate=args.max_paired_different,
            max_paired_indeterminate_rate=args.max_paired_indeterminate,
        ),
        trusted_attestor_public_keys={
            args.trusted_key_id: args.trusted_public_key.read_bytes()
        },
    )
    rendered = json.dumps(report, indent=2, sort_keys=True)
    print(rendered)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    return 0 if report["gate_passes"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
