#!/usr/bin/env python3
"""Validate pinned UOR artifacts (JSON Schema + SHACL)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from jsonschema import Draft202012Validator
from pyshacl import validate as shacl_validate
from rdflib import Graph, OWL, RDF, RDFS, URIRef
from rdflib.namespace import SH

ROOT = Path(__file__).resolve().parents[1]
UOR_DIR = ROOT / "third_party" / "uor"
DEFAULT_TAG = (UOR_DIR / "VERSION").read_text().strip()

REQUIRED_ARTIFACTS = {
    "json_schema": "uor.foundation.schema.json",
    "ontology": "uor.foundation.ttl",
    "shapes": "uor.shapes.ttl",
}


def _ensure_cache_dir(tag: str) -> Path:
    cache_dir = UOR_DIR / "cache" / tag
    if not cache_dir.exists():
        raise SystemExit(
            f"UOR artifact cache missing for tag {tag}. "
            "Run scripts/fetch_uor_artifacts.py first."
        )
    missing = [
        name
        for name in REQUIRED_ARTIFACTS.values()
        if not (cache_dir / name).exists()
    ]
    if missing:
        raise SystemExit("Missing artifacts in cache: " + ", ".join(missing))
    return cache_dir


def _sample_event() -> dict:
    return {
        "event_type": "sample",
        "run_id": "run-uor-validate",
        "goal_id": "goal-uor-validate",
        "skill": "diagnostic",
        "payload": {
            "demo": True,
            "note": "SHACL/JSON schema validation",
        },
    }


def validate_json_schema(cache_dir: Path) -> None:
    schema_path = cache_dir / REQUIRED_ARTIFACTS["json_schema"]
    schema = json.loads(schema_path.read_text())
    validator = Draft202012Validator(schema)
    sample = _sample_event()
    validator.validate(sample)
    print(
        f"JSON Schema validation passed for {schema_path.name} "
        f"against sample event"
    )


def validate_shacl(cache_dir: Path) -> None:
    """Validate the shapes schema and its ontology references.

    The ontology is a vocabulary graph, not an instance graph. Applying every
    target class shape to the vocabulary itself incorrectly treats class and
    property declarations as runtime instances and produces thousands of
    false violations. Meta-SHACL validates the shapes graph, while the explicit
    reference checks keep it aligned with the pinned ontology.
    """
    data_path = cache_dir / REQUIRED_ARTIFACTS["ontology"]
    shapes_path = cache_dir / REQUIRED_ARTIFACTS["shapes"]
    ontology_graph = Graph().parse(str(data_path), format="turtle")
    shapes_graph = Graph().parse(str(shapes_path), format="turtle")
    conforms, _, report = shacl_validate(
        Graph(),
        shacl_graph=shapes_graph,
        advanced=True,
        js=False,
        meta_shacl=True,
    )
    if not conforms:
        raise SystemExit(f"SHACL shapes validation failed:\n{report}")

    class_types = (OWL.Class, RDFS.Class)
    property_types = (
        RDF.Property,
        OWL.ObjectProperty,
        OWL.DatatypeProperty,
        OWL.AnnotationProperty,
    )
    target_classes = set(shapes_graph.objects(None, SH.targetClass))
    property_paths = {
        path
        for path in shapes_graph.objects(None, SH.path)
        if isinstance(path, URIRef)
    }
    missing_classes = sorted(
        str(target)
        for target in target_classes
        if not any(
            (target, RDF.type, class_type) in ontology_graph
            for class_type in class_types
        )
    )
    missing_properties = sorted(
        str(path)
        for path in property_paths
        if not any(
            (path, RDF.type, property_type) in ontology_graph
            for property_type in property_types
        )
    )
    if missing_classes or missing_properties:
        details = []
        if missing_classes:
            details.append(
                "missing target classes: " + ", ".join(missing_classes)
            )
        if missing_properties:
            details.append(
                "missing property paths: " + ", ".join(missing_properties)
            )
        raise SystemExit(
            "SHACL/ontology alignment failed: " + "; ".join(details)
        )

    print(
        "SHACL shapes are well-formed and ontology-aligned "
        f"({len(target_classes)} target classes, "
        f"{len(property_paths)} property paths)"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", default=DEFAULT_TAG)
    args = parser.parse_args(argv)

    cache_dir = _ensure_cache_dir(args.tag)
    validate_json_schema(cache_dir)
    validate_shacl(cache_dir)
    print(f"UOR alignment validation succeeded for release {args.tag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
