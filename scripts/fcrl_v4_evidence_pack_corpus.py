#!/usr/bin/env python3
"""Run the read-only FCRL v4 Evidence Pack corpus evaluator."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from uar.core.evidence_pack_validation_corpus import (
    evaluate_evidence_pack_corpus_document,
    render_evidence_pack_corpus_report,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate a JSON FCRL v4 evidence-pack corpus."
    )
    parser.add_argument("corpus", type=Path, help="Path to the corpus JSON document")
    parser.add_argument(
        "--json-out", type=Path, help="Optional path for structured result JSON"
    )
    parser.add_argument(
        "--markdown-out", type=Path, help="Optional path for the markdown report"
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    with args.corpus.open("r", encoding="utf-8") as handle:
        document = json.load(handle)

    result = evaluate_evidence_pack_corpus_document(document)
    structured = json.dumps(result.to_dict(), indent=2, sort_keys=True)
    markdown = render_evidence_pack_corpus_report(result)

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(structured + "\n", encoding="utf-8")
    else:
        print(structured)

    if args.markdown_out:
        args.markdown_out.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_out.write_text(markdown, encoding="utf-8")
    else:
        print()
        print(markdown)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
