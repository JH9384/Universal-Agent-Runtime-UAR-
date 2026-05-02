from pathlib import Path
from typing import Dict, List

from uar.core.registry import register_skill

ALLOWED_ROOT = Path('.').resolve()


@register_skill("doc_ingest")
def doc_ingest(ctx):
    input_path = ctx.goal.metadata.get("input_path")
    if not input_path:
        return {"documents": [], "warning": "No input_path provided"}

    path = Path(input_path).resolve()

    try:
        path.relative_to(ALLOWED_ROOT)
    except Exception:
        return {"documents": [], "error": "Path outside allowed root"}

    documents: List[Dict[str, str]] = []

    if path.is_file():
        documents.append({"path": str(path), "text": path.read_text(encoding="utf-8")})
    elif path.is_dir():
        for item in sorted(path.rglob("*")):
            if item.suffix.lower() in {".txt", ".md", ".py", ".ts", ".tsx", ".json"}:
                documents.append({"path": str(item), "text": item.read_text(encoding="utf-8")})
    else:
        return {"documents": [], "warning": f"Input path not found: {input_path}"}

    return {
        "documents": documents,
        "document_count": len(documents),
        "paths": [doc["path"] for doc in documents],
    }
