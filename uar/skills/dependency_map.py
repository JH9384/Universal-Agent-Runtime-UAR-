from typing import Dict, Any

from uar.core.registry import register_skill


@register_skill("dependency_map")
def dependency_map(ctx):
    ingest = ctx.data.get("doc_ingest") or {}
    documents = ingest.get("documents", [])

    nodes = []
    edges = []

    for doc in documents:
        path = doc.get("path")
        text = doc.get("text", "")
        nodes.append({"id": path, "type": "file"})

        for line in text.splitlines():
            line = line.strip()
            if line.startswith("import ") or line.startswith("from "):
                import_id = f"import:{line}"
                nodes.append({"id": import_id, "type": "import"})
                edges.append({"from": path, "to": import_id, "type": "import"})

    return {
        "node_count": len(nodes),
        "edge_count": len(edges),
        "nodes": nodes,
        "edges": edges,
    }
