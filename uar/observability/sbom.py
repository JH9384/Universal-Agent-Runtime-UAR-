"""SBOM generator for UAR.

T11 — Supply Chain: generates a CycloneDX-compatible JSON SBOM from
installed packages so vulnerability scanners (Grype, Trivy, Snyk) can
ingest it.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _pkg_type() -> str:
    if sys.platform == "linux":
        return "application"
    return "application"


def generate_sbom(
    *,
    tool_name: str = "uar-sbom-generator",
    tool_version: str = "1.0.0",
    output_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate a CycloneDX 1.5 SBOM from installed Python packages.

    Uses :mod:`importlib.metadata` so it reflects the *actual* installed
    versions, not merely the lock-file constraints.
    """
    import importlib.metadata as im

    _primary_name = "universal-agent-runtime"
    components: List[Dict[str, Any]] = []
    for dist in im.distributions():
        name = dist.metadata.get("Name", "unknown")
        version = dist.version or "0.0.0"
        if name == _primary_name:
            continue
        # Attempt to locate a wheel / sdist hash via RECORD if available.
        hashes = []
        try:
            record = dist.read_text("RECORD")
            if record:
                first = record.strip().splitlines()[0]
                # RECORD format: path,sha256=hash,size
                parts = first.split(",")
                if len(parts) > 1 and parts[1].startswith("sha256="):
                    hashes.append(
                        {"alg": "SHA-256", "content": parts[1][7:]}
                    )
        except Exception:
            pass

        comp: Dict[str, Any] = {
            "type": "library",
            "name": name,
            "version": version,
            "purl": f"pkg:pypi/{name}@{version}",
            "bom-ref": f"pkg:pypi/{name}@{version}",
        }
        if hashes:
            comp["hashes"] = hashes
        components.append(comp)

    # UOR-ADDR-1 canonical seed for deterministic UUID
    try:
        from uar.uor.bounded_json import compute_uor_digest

        uuid_seed = compute_uor_digest(
            {"tool": tool_name, "version": tool_version, "ts": _now_iso()}
        )
        uuid_hex = uuid_seed.replace("sha256:", "")[:32]
    except Exception:
        uuid_hex = hashlib.sha256(
            (tool_name + tool_version + _now_iso()).encode()
        ).hexdigest()[:32]

    sbom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": "urn:uuid:" + uuid_hex,
        "version": 1,
        "metadata": {
            "timestamp": _now_iso(),
            "tools": [
                {
                    "vendor": "UAR",
                    "name": tool_name,
                    "version": tool_version,
                }
            ],
            "component": {
                "type": _pkg_type(),
                "name": "universal-agent-runtime",
                "version": "1.2.0",
                "purl": "pkg:pypi/universal-agent-runtime@1.2.0",
                "bom-ref": "pkg:pypi/universal-agent-runtime@1.2.0",
            },
        },
        "components": components,
    }

    if output_path is not None:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(sbom, f, indent=2)

    return sbom


def validate_sbom(sbom: Dict[str, Any]) -> List[str]:
    """Return a list of validation warnings for a generated SBOM.

    Checks:
    - Required top-level keys present
    - Every component has name, version, purl
    - No duplicate purls
    """
    warnings: List[str] = []
    for key in ("bomFormat", "specVersion", "components"):
        if key not in sbom:
            warnings.append(f"missing top-level key: {key}")

    seen_purls: set[str] = set()
    for i, comp in enumerate(sbom.get("components", [])):
        for field in ("name", "version", "purl"):
            if not comp.get(field):
                warnings.append(
                    f"component[{i}] missing field: {field}"
                )
        purl = comp.get("purl")
        if purl in seen_purls:
            warnings.append(f"duplicate purl: {purl}")
        seen_purls.add(purl)

    return warnings
