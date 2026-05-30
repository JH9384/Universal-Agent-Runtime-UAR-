"""Tests for uar.skills.dependency_map."""

from uar.core.contracts import GoalSpec, PipelineContext
from uar.skills.dependency_map import dependency_map


def test_dependency_map_with_documents():
    """Must extract imports from document text."""
    goal = GoalSpec(id="g", user_intent="test", objective="test")
    ctx = PipelineContext(goal=goal)
    ctx.data["doc_ingest"] = {
        "documents": [
            {
                "path": "/tmp/main.py",
                "text": "import os\nfrom sys import argv\n",
            }
        ]
    }
    result = dependency_map(ctx)
    assert result["node_count"] == 3  # file + 2 imports
    assert result["edge_count"] == 2


def test_dependency_map_skips_non_dict_document():
    """Must skip documents that are not dicts."""
    goal = GoalSpec(id="g", user_intent="test", objective="test")
    ctx = PipelineContext(goal=goal)
    ctx.data["doc_ingest"] = {
        "documents": ["not a dict", {"path": "/tmp/a.py", "text": ""}]
    }
    result = dependency_map(ctx)
    assert result["node_count"] == 1


def test_dependency_map_skips_invalid_path():
    """Must skip documents without valid path."""
    goal = GoalSpec(id="g", user_intent="test", objective="test")
    ctx = PipelineContext(goal=goal)
    ctx.data["doc_ingest"] = {
        "documents": [
            {"path": None, "text": "import os"},
            {"text": "import sys"},
        ]
    }
    result = dependency_map(ctx)
    assert result["node_count"] == 0
    assert result["edge_count"] == 0


def test_dependency_map_skips_non_import_lines():
    """Must skip lines that don't start with import or from."""
    goal = GoalSpec(id="g", user_intent="test", objective="test")
    ctx = PipelineContext(goal=goal)
    ctx.data["doc_ingest"] = {
        "documents": [
            {"path": "/tmp/a.py", "text": "x = 1\n# import os\n"},
        ]
    }
    result = dependency_map(ctx)
    assert result["node_count"] == 1  # just the file
    assert result["edge_count"] == 0
