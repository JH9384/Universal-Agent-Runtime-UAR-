#!/usr/bin/env python3
"""UOR Provenance CLI - Verify and export cryptographic attestations.

This tool provides command-line access to UOR address verification,
witness validation, and attestation export for downstream audit.

Usage:
    python scripts/uor_provenance.py verify <run_id> [--store sqlite|jsonl]
    python scripts/uor_provenance.py export <run_id> --format json|in-toto
    python scripts/uor_provenance.py attest <run_id> --output <path>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from uar.compat.uor_address import (  # noqa: E402
    address_for_json,
    address_with_witness,
)
from uar.memory.json_store import JsonRunStore  # noqa: E402
from uar.memory.sqlite_store import SqliteRunStore  # noqa: E402


def load_run_record(
    run_id: str, store_type: str = "sqlite"
) -> Optional[Dict[str, Any]]:
    """Load a RunRecord from the specified store type."""
    root = Path(__file__).resolve().parents[1]

    if store_type == "sqlite":
        store_path = root / "data" / "runs.db"
        if not store_path.exists():
            return None
        store = SqliteRunStore(str(store_path))
        return store.get_by_run_id(run_id)
    elif store_type == "jsonl":
        store_path = root / "data" / "runs.jsonl"
        if not store_path.exists():
            return None
        store = JsonRunStore(str(store_path))
        records = store.list_records()
        for r in records:
            if r.get("run_id") == run_id:
                return r
        return None
    else:
        raise ValueError(f"Unknown store type: {store_type}")


def verify_uor_address(run_record: Dict[str, Any]) -> Dict[str, Any]:
    """Verify the UOR address in a run record against recomputed value.

    Returns verification result with match status and any discrepancies.
    """
    stored_address = run_record.get("uor_address")
    stored_witness = run_record.get("uor_witness")

    if not stored_address:
        return {
            "valid": False,
            "error": "No uor_address found in run record",
            "stored": None,
            "recomputed": None,
        }

    # Recompute address from run data
    verification_input = {
        "run_id": run_record.get("run_id"),
        "goal": run_record.get("goal"),
        "skills": run_record.get("skills", []),
        "timestamp": run_record.get("timestamp"),
    }

    try:
        recomputed, witness = address_with_witness(verification_input)
    except Exception:  # noqa: BLE001
        # Fallback to basic address
        try:
            recomputed = address_for_json(verification_input)
            witness = None
        except Exception as e2:
            return {
                "valid": False,
                "error": f"Failed to recompute address: {e2}",
                "stored": stored_address,
                "recomputed": None,
            }

    return {
        "valid": stored_address == recomputed,
        "stored": stored_address,
        "recomputed": recomputed,
        "witness_match": (
            stored_witness == witness
            if stored_witness and witness
            else None
        ),
        "witness_present": bool(stored_witness),
    }


def export_attestation(
    run_record: Dict[str, Any],
    format_type: str = "json"
) -> str:
    """Export run attestation in specified format.

    Formats:
        - json: UAR native format with full provenance
        - in-toto: In-Toto attestation predicate format
    """
    if format_type == "json":
        attestation = {
            "type": "https://uor.foundation/attestation/v1",
            "subject": {
                "run_id": run_record.get("run_id"),
                "uor_address": run_record.get("uor_address"),
            },
            "predicate": {
                "buildType": "https://uor.foundation/run/v1",
                "invocation": {
                    "configSource": {
                        "goal": run_record.get("goal"),
                        "skills": run_record.get("skills", []),
                    },
                    "timestamp": run_record.get("timestamp"),
                },
                "metadata": {
                    "witness": run_record.get("uor_witness"),
                    "artifacts": run_record.get("artifacts", []),
                },
            },
        }
        return json.dumps(attestation, indent=2)

    elif format_type == "in-toto":
        # In-Toto SLSA Provenance v1.0 format
        addr = run_record.get("uor_address", "").replace("sha256:", "")
        attestation = {
            "_type": "https://in-toto.io/Statement/v1",
            "subject": [
                {
                    "name": run_record.get("run_id"),
                    "digest": {"sha256": addr},
                }
            ],
            "predicateType": "https://slsa.dev/provenance/v1",
            "predicate": {
                "buildDefinition": {
                    "buildType": "https://uor.foundation/run/v1",
                    "externalParameters": {
                        "goal": run_record.get("goal"),
                        "skills": run_record.get("skills", []),
                    },
                },
                "runDetails": {
                    "builder": {
                        "id": "https://github.com/JH9384/UAR",
                    },
                    "metadata": {
                        "invocationId": run_record.get("run_id"),
                        "startedOn": run_record.get("timestamp"),
                    },
                },
            },
        }
        return json.dumps(attestation, indent=2)

    else:
        raise ValueError(f"Unknown format: {format_type}")


def cmd_verify(args: argparse.Namespace) -> int:
    """Verify command handler."""
    run_record = load_run_record(args.run_id, args.store)

    if not run_record:
        print(
            f"Error: Run {args.run_id} not found in {args.store} store",
            file=sys.stderr
        )
        return 1

    result = verify_uor_address(run_record)

    print(json.dumps(result, indent=2))

    if result["valid"]:
        print("\n✓ UOR address verification PASSED", file=sys.stderr)
        if result.get("witness_present"):
            witness_status = (
                "MATCH" if result.get("witness_match") else "MISMATCH"
            )
            print(f"✓ Witness verification: {witness_status}", file=sys.stderr)
        return 0
    else:
        print("\n✗ UOR address verification FAILED", file=sys.stderr)
        return 1


def cmd_export(args: argparse.Namespace) -> int:
    """Export command handler."""
    run_record = load_run_record(args.run_id, args.store)

    if not run_record:
        print(
            f"Error: Run {args.run_id} not found in {args.store} store",
            file=sys.stderr
        )
        return 1

    try:
        output = export_attestation(run_record, args.format)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if args.output:
        Path(args.output).write_text(output)
        print(f"Attestation exported to {args.output}", file=sys.stderr)
    else:
        print(output)

    return 0


def cmd_attest(args: argparse.Namespace) -> int:
    """Attest command - create signed attestation."""
    run_record = load_run_record(args.run_id, args.store)

    if not run_record:
        print(
            f"Error: Run {args.run_id} not found in {args.store} store",
            file=sys.stderr
        )
        return 1

    # Create attestation bundle
    attestation = export_attestation(run_record, "in-toto")

    # In future: Sign with Sigstore/cosign here
    # For now, just include verification data
    bundle = {
        "attestation": json.loads(attestation),
        "verification": verify_uor_address(run_record),
        "signatures": [],  # Placeholder for future signatures
    }

    output = json.dumps(bundle, indent=2)

    if args.output:
        Path(args.output).write_text(output)
        print(
            f"Attestation bundle exported to {args.output}",
            file=sys.stderr
        )
    else:
        print(output)

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="UOR Provenance CLI - Verify and export attestations"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Verify command
    verify_parser = subparsers.add_parser(
        "verify", help="Verify UOR address for a run"
    )
    verify_parser.add_argument("run_id", help="Run ID to verify")
    verify_parser.add_argument(
        "--store",
        choices=["sqlite", "jsonl"],
        default="sqlite",
        help="Store type to query (default: sqlite)"
    )
    verify_parser.set_defaults(func=cmd_verify)

    # Export command
    export_parser = subparsers.add_parser(
        "export", help="Export attestation for a run"
    )
    export_parser.add_argument("run_id", help="Run ID to export")
    export_parser.add_argument(
        "--format",
        choices=["json", "in-toto"],
        default="json",
        help="Export format (default: json)"
    )
    export_parser.add_argument(
        "--store",
        choices=["sqlite", "jsonl"],
        default="sqlite",
        help="Store type to query (default: sqlite)"
    )
    export_parser.add_argument("-o", "--output", help="Output file path")
    export_parser.set_defaults(func=cmd_export)

    # Attest command
    attest_parser = subparsers.add_parser(
        "attest",
        help="Create attestation bundle (placeholder for future signing)"
    )
    attest_parser.add_argument("run_id", help="Run ID to attest")
    attest_parser.add_argument(
        "--store",
        choices=["sqlite", "jsonl"],
        default="sqlite",
        help="Store type to query (default: sqlite)"
    )
    attest_parser.add_argument(
        "-o", "--output", required=True, help="Output file path"
    )
    attest_parser.set_defaults(func=cmd_attest)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
