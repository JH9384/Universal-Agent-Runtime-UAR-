"""Tests for T11 — SBOM + Supply Chain.

Covers:
- generate_sbom produces CycloneDX-like structure
- validate_sbom catches malformed documents
- CLI command generates file on disk
"""

from __future__ import annotations

import json
import os
import tempfile

from uar.observability.sbom import generate_sbom, validate_sbom


def test_generate_sbom_structure():
    """SBOM has required CycloneDX top-level keys."""
    sbom = generate_sbom()
    assert sbom["bomFormat"] == "CycloneDX"
    assert sbom["specVersion"] == "1.5"
    assert "serialNumber" in sbom
    assert "metadata" in sbom
    assert "components" in sbom
    assert len(sbom["components"]) > 0


def test_generate_sbom_metadata():
    """Metadata section includes tool and primary component."""
    sbom = generate_sbom()
    meta = sbom["metadata"]
    assert "timestamp" in meta
    assert meta["tools"][0]["name"] == "uar-sbom-generator"
    assert meta["component"]["name"] == "universal-agent-runtime"


def test_generate_sbom_components_have_purl():
    """Every component has a pURL."""
    sbom = generate_sbom()
    for comp in sbom["components"]:
        assert comp["purl"].startswith("pkg:pypi/")
        assert comp["version"]
        assert comp["name"]


def test_generate_sbom_writes_file():
    """output_path writes JSON to disk."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False
    ) as f:
        path = f.name
    try:
        generate_sbom(output_path=path)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["bomFormat"] == "CycloneDX"
    finally:
        os.unlink(path)


def test_validate_sbom_clean_document():
    """A freshly generated SBOM has no validation warnings."""
    sbom = generate_sbom()
    warnings = validate_sbom(sbom)
    assert warnings == []


def test_validate_sbom_missing_key():
    """Missing top-level key produces a warning."""
    sbom = generate_sbom()
    del sbom["components"]
    warnings = validate_sbom(sbom)
    assert any("missing top-level key" in w for w in warnings)


def test_validate_sbom_bad_component():
    """Component missing name/version/purl triggers warning."""
    sbom = generate_sbom()
    sbom["components"].append({"name": "", "version": "1.0"})
    warnings = validate_sbom(sbom)
    assert any("missing field" in w for w in warnings)


def test_validate_sbom_duplicate_purl():
    """Duplicate purl triggers warning."""
    sbom = generate_sbom()
    dup = sbom["components"][0].copy()
    sbom["components"].append(dup)
    warnings = validate_sbom(sbom)
    assert any("duplicate purl" in w for w in warnings)
