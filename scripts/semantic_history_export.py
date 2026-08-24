#!/usr/bin/env python3
"""Export a sanitized corpus from read-only operational run stores."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from uar.core.semantic_history_export import export_history_corpus


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--baseline-store", required=True, type=Path)
    parser.add_argument("--candidate-store", required=True, type=Path)
    parser.add_argument("--sanitization-key", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    payload = export_history_corpus(
        json.loads(args.manifest.read_text(encoding="utf-8")),
        baseline_store=args.baseline_store,
        candidate_store=args.candidate_store,
        sanitization_key=args.sanitization_key.read_bytes(),
    )
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
