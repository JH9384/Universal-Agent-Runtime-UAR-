"""Read-only projections over immutable PSERA/UAR evidence objects.

The graph is derived from canonical objects and links already stored by UAR.
It is not a second source of truth and it never changes authorization state.
"""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Any, Dict, Iterable, List, Set

from .evidence import EVIDENCE_SCHEMA
from .store import ObjectStore


def is_evidence_record(record: Dict[str, Any]) -> bool:
    """Return True when ``record`` is a PSERA evidence-contract object."""
    attrs = record.get("attributes", {})
    return (
        record.get("mode") == "immutable"
        and attrs.get("schema") == EVIDENCE_SCHEMA
        and attrs.get("kind") == "control-evidence"
    )


def iter_evidence(store: ObjectStore) -> Iterable[Dict[str, Any]]:
    """Yield evidence records from the store without mutating source state."""
    for _digest, record in store.iter_objects():
        if is_evidence_record(record):
            yield record


def project_evidence_graph(
    store: ObjectStore,
    evidence_digests: Iterable[str] | None = None,
    *,
    max_depth: int = 4,
) -> Dict[str, Any]:
    """Build a deterministic evidence/witness graph projection.

    Only explicit UAR object links are followed. Missing linked objects are
    represented as unresolved nodes rather than silently ignored. The graph
    is an operational projection; canonical objects remain the source of truth.
    """
    if max_depth < 0:
        raise ValueError("max_depth must be non-negative")

    roots = (
        list(evidence_digests)
        if evidence_digests is not None
        else [record["digest"] for record in iter_evidence(store)]
    )
    queue = deque((digest, 0) for digest in sorted(set(roots)))
    visited: Set[str] = set()
    nodes: Dict[str, Dict[str, Any]] = {}
    edges: List[Dict[str, str]] = []

    while queue:
        digest, depth = queue.popleft()
        if digest in visited:
            continue
        visited.add(digest)
        try:
            record = store.get_object(digest)
        except KeyError:
            nodes[digest] = {"digest": digest, "status": "unresolved"}
            continue

        attrs = record.get("attributes", {})
        nodes[digest] = {
            "digest": digest,
            "status": "resolved",
            "mediaType": record.get("mediaType"),
            "kind": attrs.get("kind"),
            "schema": attrs.get("schema"),
            "control_id": attrs.get("control_id"),
        }
        if depth >= max_depth:
            continue

        for link in record.get("links", []):
            target = link.get("target")
            rel = link.get("rel")
            if not isinstance(target, str) or not target:
                continue
            edges.append({"source": digest, "rel": str(rel or "related"), "target": target})
            if target not in visited:
                queue.append((target, depth + 1))

    edges.sort(key=lambda item: (item["source"], item["rel"], item["target"]))
    return {
        "roots": sorted(set(roots)),
        "nodes": [nodes[digest] for digest in sorted(nodes)],
        "edges": edges,
        "unresolved": sorted(
            digest for digest, node in nodes.items() if node["status"] == "unresolved"
        ),
    }


def mission_control_evidence_projection(store: ObjectStore) -> Dict[str, Any]:
    """Return an evidence-only operator projection for Mission Control.

    This projection reports observations; it deliberately does not compute
    compliance/pass status. Assessment remains a separate authority.
    """
    by_control: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {"evidence_count": 0, "subjects": set(), "results": defaultdict(int)}
    )
    total = 0
    for record in iter_evidence(store):
        total += 1
        content = record.get("content", {})
        control_id = str(content.get("control_id") or "UNMAPPED")
        bucket = by_control[control_id]
        bucket["evidence_count"] += 1
        subject = content.get("subject")
        if subject:
            bucket["subjects"].add(str(subject))
        bucket["results"][str(content.get("result", "unknown"))] += 1

    controls = []
    for control_id in sorted(by_control):
        bucket = by_control[control_id]
        controls.append(
            {
                "control_id": control_id,
                "evidence_count": bucket["evidence_count"],
                "subjects": sorted(bucket["subjects"]),
                "observed_results": dict(sorted(bucket["results"].items())),
            }
        )
    return {
        "evidence_count": total,
        "controls": controls,
        "assessment_status": "not-assessed",
    }


__all__ = [
    "is_evidence_record",
    "iter_evidence",
    "mission_control_evidence_projection",
    "project_evidence_graph",
]
