from uar.skills.dependency_map import dependency_map
from uar.core.contracts import PipelineContext, GoalSpec


def test_graph_has_no_dangling_edges():
    ctx = PipelineContext(goal=GoalSpec(id="g", user_intent="", objective=""))

    # minimal fake ingest
    ctx.data["doc_ingest"] = {
        "documents": [
            {"path": "a.py", "text": "import os"},
            {"path": "b.py", "text": "from sys import path"},
        ]
    }

    graph = dependency_map(ctx)

    node_ids = {n["id"] for n in graph["nodes"]}

    for edge in graph["edges"]:
        assert edge["from"] in node_ids
        assert edge["to"] in node_ids
