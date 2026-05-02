from uar.core.registry import register_skill


@register_skill("dependency_map")
def dependency_map(ctx):
    ingest = ctx.data.get("doc_ingest") or {}
    documents = ingest.get("documents", [])

    nodes_by_id = {}
    edges_by_id = {}

    for doc in documents:
        path = doc.get("path")
        text = doc.get("text", "")
        if not path:
            continue

        nodes_by_id[path] = {"id": path, "type": "file"}

        for line in text.splitlines():
            line = line.strip()
            if line.startswith("import ") or line.startswith("from "):
                import_id = f"import:{line}"
                edge_id = f"{path}->{import_id}"
                nodes_by_id[import_id] = {"id": import_id, "type": "import"}
                edges_by_id[edge_id] = {"id": edge_id, "from": path, "to": import_id, "type": "import"}

    nodes = list(nodes_by_id.values())
    edges = list(edges_by_id.values())

    return {
        "node_count": len(nodes),
        "edge_count": len(edges),
        "nodes": nodes,
        "edges": edges,
    }
