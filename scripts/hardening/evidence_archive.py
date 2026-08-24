#!/usr/bin/env python3
"""Evidence Archive — Track 4.

Structured archival of all operational validation artifacts.
Scans report directories, builds an index, and packages
findings into a single browsable manifest.

Directories:
  reports/trust_validation/    — weekly trust reports
  reports/divergence/            — daily divergence investigations
  reports/burnin/                — long-duration burn-in logs
  reports/certification/         — system state snapshots

Usage:
    python scripts/hardening/evidence_archive.py [--scan]

With --scan: discovers existing reports and builds manifest.
Without:     prints current manifest summary.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


REPORT_DIRS = {
    "trust_validation": Path("reports/trust_validation"),
    "divergence": Path("reports/divergence"),
    "burnin": Path("reports/burnin"),
    "certification": Path("reports/certification"),
}


def _extract_timestamp(filename: str) -> str:
    """Pull YYYYMMDD or YYYYMMDD_HHMMSS from filename."""
    import re

    m = re.search(r"(\d{8})(?:_\d{6})?", filename)
    return m.group(1) if m else "unknown"


def scan_reports() -> Dict[str, List[Dict[str, Any]]]:
    """Scan all report directories and return categorized listings."""
    findings: Dict[str, List[Dict[str, Any]]] = {}

    for category, directory in REPORT_DIRS.items():
        entries: List[Dict[str, Any]] = []
        if directory.exists():
            for path in sorted(directory.iterdir()):
                if path.is_file() and path.suffix == ".json":
                    # Try to load a summary line
                    summary = {}
                    try:
                        data = json.loads(path.read_text())
                        # Extract key fields based on report type
                        if category == "trust_validation":
                            summary = {
                                "trust_ranking_enabled": data.get(
                                    "trust_ranking_enabled"
                                ),
                                "recommendation_count": len(
                                    data.get("recommendations", [])
                                ),
                                "top_confidence": (
                                    data.get("recommendations", [])[0].get(
                                        "confidence"
                                    )
                                    if data.get("recommendations")
                                    else None
                                ),
                            }
                        elif category == "divergence":
                            summary = {
                                "total_divergences": data.get(
                                    "total_divergences"
                                ),
                            }
                        elif category == "burnin":
                            summary = data.get("summary", {})
                        elif category == "certification":
                            sections = data.get("sections", {})
                            summary = {
                                "sections_present": list(sections.keys()),
                                "sections_with_error": [
                                    k
                                    for k, v in sections.items()
                                    if "error" in v
                                ],
                            }
                    except Exception:
                        pass

                    entries.append(
                        {
                            "file": str(path),
                            "size_bytes": path.stat().st_size,
                            "timestamp": _extract_timestamp(path.name),
                            "summary": summary,
                        }
                    )
        findings[category] = entries

    return findings


def build_manifest(
    findings: Dict[str, List[Dict[str, Any]]],
) -> Dict[str, Any]:
    """Build the top-level archive manifest."""
    total_files = sum(len(v) for v in findings.values())
    total_size = sum(
        e["size_bytes"] for entries in findings.values() for e in entries
    )

    return {
        "manifest_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_files": total_files,
        "total_size_bytes": total_size,
        "categories": {
            cat: {
                "file_count": len(entries),
                "size_bytes": sum(e["size_bytes"] for e in entries),
                "entries": entries,
            }
            for cat, entries in findings.items()
        },
    }


def print_summary(manifest: Dict[str, Any]) -> None:
    """Print human-readable summary of the archive."""
    print("Evidence Archive Summary")
    print(f"Generated: {manifest['generated_at']}")
    print(f"Total files: {manifest['total_files']}")
    print(f"Total size: {manifest['total_size_bytes'] / 1024:.1f} KB")
    print()

    for cat, data in manifest["categories"].items():
        print(f"  {cat}: {data['file_count']} file(s)")
        for entry in data["entries"][-3:]:  # Last 3
            ts = entry.get("timestamp", "—")
            size = entry.get("size_bytes", 0)
            print(f"    {ts} — {size / 1024:.1f} KB — {entry['file']}")
        if data["file_count"] > 3:
            print(f"    ... and {data['file_count'] - 3} more")
        print()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evidence archive manager",
    )
    parser.add_argument(
        "--scan",
        action="store_true",
        help="Scan report directories and rebuild manifest",
    )
    parser.add_argument(
        "--output",
        default="reports/archive_manifest.json",
        help="Manifest output path",
    )
    args = parser.parse_args()

    if args.scan:
        print("Scanning report directories…")
        findings = scan_reports()
        manifest = build_manifest(findings)
        Path(args.output).write_text(json.dumps(manifest, indent=2) + "\n")
        print(f"Manifest written to {args.output}")
        print()
        print_summary(manifest)
    else:
        if Path(args.output).exists():
            manifest = json.loads(Path(args.output).read_text())
            print_summary(manifest)
        else:
            print("No manifest found. Run with --scan to build.")
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
