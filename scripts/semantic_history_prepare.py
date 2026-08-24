#!/usr/bin/env python3
"""Freeze and sign a sanitized Semantic Replay history corpus."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from uar.core.semantic_history import CORPUS_SCHEMA, HistoryGateThresholds
from uar.core.semantic_history_attestation import sign_history_attestation


def _thresholds(args: argparse.Namespace) -> HistoryGateThresholds:
    return HistoryGateThresholds(
        min_samples_per_cohort=args.min_samples_per_cohort,
        max_js_divergence_bits=args.max_js,
        max_total_variation=args.max_tv,
        max_telemetry_loss_rate=args.max_telemetry_loss,
        max_telemetry_loss_delta=args.max_telemetry_loss_delta,
        max_paired_different_rate=args.max_paired_different,
        max_paired_indeterminate_rate=args.max_paired_indeterminate,
    )


def _validate_collectable(payload: object) -> dict:
    if not isinstance(payload, dict) or payload.get("schema") != CORPUS_SCHEMA:
        raise ValueError("invalid_history_corpus_schema")
    provenance = payload.get("provenance")
    if not isinstance(provenance, dict):
        raise ValueError("missing_provenance")
    for field in ("code_revision", "capture_window", "sanitization"):
        if not provenance.get(field):
            raise ValueError(f"missing_provenance_{field}")
    if not isinstance(payload.get("runs"), list) or not payload["runs"]:
        raise ValueError("missing_runs")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--key-id", required=True)
    parser.add_argument("--private-key", required=True, type=Path)
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

    payload = _validate_collectable(
        json.loads(args.input.read_text(encoding="utf-8"))
    )
    payload["attestation"] = sign_history_attestation(
        payload,
        key_id=args.key_id,
        review_policy=asdict(_thresholds(args)),
        private_key_pem=args.private_key.read_bytes(),
    )
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
