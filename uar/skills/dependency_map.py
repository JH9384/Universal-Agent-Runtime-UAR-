from uar.core.registry import register_skill
from uar.core.contracts import PipelineContext
from typing import Dict, Any, List


@register_skill("dependency_map")
def dependency_map(ctx: PipelineContext) -> Dict[str, Any]:
    """Build a dependency graph from ingested Python documents.

    This skill analyzes Python files to extract import statements and construct
    a graph of file dependencies. It creates nodes for files and imports, and
    edges representing the relationships between them.

    Args:
        ctx: Pipeline context containing doc_ingest results with document data.

    Returns:
        Dictionary containing node count, edge count, and lists of nodes and edges.
    """  # noqa: E501
    ingest = ctx.data.get("doc_ingest") or {}
    documents = ingest.get("documents", [])

    nodes_by_id: Dict[str, Dict[str, str]] = {}
    edges_by_id: Dict[str, Dict[str, str]] = {}

    for doc in documents:
        # Validate document structure
        if not isinstance(doc, dict):
            continue
        path = doc.get("path")
        text = doc.get("text", "")
        if not path or not isinstance(path, str):
            continue

        nodes_by_id[path] = {"id": path, "type": "file"}

        for line in text.splitlines():
            line = line.strip()
            if line.startswith("import ") or line.startswith("from "):
                import_id = f"import:{line}"
                edge_id = f"{path}->{import_id}"
                nodes_by_id[import_id] = {"id": import_id, "type": "import"}
                edges_by_id[edge_id] = {
                    "id": edge_id,
                    "from": path,
                    "to": import_id,
                    "type": "import",
                }

    nodes: List[Dict[str, str]] = list(nodes_by_id.values())
    edges: List[Dict[str, str]] = list(edges_by_id.values())

    return {
        "node_count": len(nodes),
        "edge_count": len(edges),
        "nodes": nodes,
        "edges": edges,
    }
