#!/usr/bin/env python3
"""Build Evidence Pack v2 artifacts from supplied read-only inputs.

D5G keeps pack generation local/script-based before adding any API surface.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from uar.core.evidence_pack import (
    build_evidence_pack,
    render_evidence_pack_markdown,
)


def _load_json(path: str | None) -> dict[str, Any] | None:
    if not path:
        return None

    json_path = Path(path)
    if not json_path.exists():
        raise FileNotFoundError(f"input JSON not found: {json_path}")

    data = json.loads(json_path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"input JSON must contain an object: {json_path}")

    return data


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build Evidence Pack v2 artifacts"
    )
    parser.add_argument(
        "--run-id", required=True, help="Run ID for the evidence pack"
    )
    parser.add_argument("--output-dir", default="reports/evidence_pack")
    parser.add_argument(
        "--authority-tag", default="v1.2.19-d5e-evidence-pack-builder"
    )

    parser.add_argument("--signal-json")
    parser.add_argument("--mission-control-json")
    parser.add_argument("--replay-json")
    parser.add_argument("--burnin-json")
    parser.add_argument("--certification-json")
    parser.add_argument("--trust-json")
    parser.add_argument("--outcome-json")
    parser.add_argument("--closure-json")

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    pack = build_evidence_pack(
        run_id=args.run_id,
        authority_tag=args.authority_tag,
        signal=_load_json(args.signal_json),
        mission_control=_load_json(args.mission_control_json),
        replay=_load_json(args.replay_json),
        burnin=_load_json(args.burnin_json),
        certification=_load_json(args.certification_json),
        trust=_load_json(args.trust_json),
        outcome=_load_json(args.outcome_json),
        closure=_load_json(args.closure_json),
    )

    json_path = output_dir / f"{args.run_id}_evidence_pack.json"
    markdown_path = output_dir / f"{args.run_id}_evidence_pack.md"

    json_path.write_text(
        json.dumps(pack.to_dict(), indent=2, sort_keys=True) + "\n"
    )
    markdown_path.write_text(render_evidence_pack_markdown(pack) + "\n")

    print(
        json.dumps(
            {
                "status": "PASS",
                "run_id": args.run_id,
                "json": str(json_path),
                "markdown": str(markdown_path),
            },
            indent=2,
            sort_keys=True,
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
