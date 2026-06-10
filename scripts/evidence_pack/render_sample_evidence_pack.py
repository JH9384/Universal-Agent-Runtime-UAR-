#!/usr/bin/env python3
"""Render a sample Evidence Pack v2 artifact.

D5F is intentionally local/script-only. It exercises the read-only core builder
without adding an API surface or mutating runtime state.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from uar.core.evidence_pack import build_evidence_pack, render_evidence_pack_markdown


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render sample Evidence Pack v2 artifacts")
    parser.add_argument("--run-id", default="sample-run", help="Run ID for the evidence pack")
    parser.add_argument(
        "--output-dir",
        default="reports/evidence_pack",
        help="Directory for generated evidence pack artifacts",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    pack = build_evidence_pack(
        run_id=args.run_id,
        signal={"signal_type": "sample", "severity": "info"},
        mission_control={"runtime_health": {"status": "sample"}},
        replay={"replay_available": True, "replay_confidence_score": 96},
        burnin={"passed": True, "score": 99},
        certification={"level": "sample", "score": 95},
        trust={"trust_score": 0.9},
        outcome={"outcome_type": "sample"},
        closure={"status": "open"},
    )

    json_path = output_dir / f"{args.run_id}_evidence_pack.json"
    markdown_path = output_dir / f"{args.run_id}_evidence_pack.md"

    json_path.write_text(json.dumps(pack.to_dict(), indent=2, sort_keys=True) + "\n")
    markdown_path.write_text(render_evidence_pack_markdown(pack) + "\n")

    print(json.dumps({
        "status": "PASS",
        "run_id": args.run_id,
        "json": str(json_path),
        "markdown": str(markdown_path),
    }, indent=2, sort_keys=True))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
