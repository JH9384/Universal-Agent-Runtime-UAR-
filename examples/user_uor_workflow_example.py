"""User example: create UOR objects and run a simple UOR workflow.

Run with:
    python examples/user_uor_workflow_example.py

Start the API first:
    uvicorn uar.api.server:app --reload
"""

from __future__ import annotations

import json
from typing import Any, Dict

import requests

BASE_URL = "http://localhost:8000/api/uor"


def post(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    response = requests.post(f"{BASE_URL}{path}", json=payload, timeout=30)
    response.raise_for_status()
    return response.json()


def main() -> None:
    source = post(
        "/objects",
        {
            "mediaType": "text/plain",
            "mode": "immutable",
            "content": (
                "UAR helps users run skills, recipes, and UOR workflows."
            ),
            "attributes": {
                "title": "UAR user example",
                "kind": "example-input",
            },
        },
    )
    print("Created source object:")
    print(json.dumps(source, indent=2))

    runtime = post(
        "/runtimes/register",
        {
            "name": "uppercase-demo",
            "runtimeObject": {
                "kind": "python_function",
                "entrypoint": "transform",
                "source": (
                    "def transform(value, **kwargs):\n"
                    "    return str(value).upper()\n"
                ),
            },
        },
    )
    print("\nRegistered runtime:")
    print(json.dumps(runtime, indent=2))

    workflow = post(
        "/workflows/run",
        {
            "name": "uppercase-workflow",
            "inputs": [source["digest"]],
            "steps": [
                {
                    "runtimeName": "uppercase-demo",
                    "inputs": [source["digest"]],
                    "parameters": {"purpose": "user-example"},
                }
            ],
        },
    )
    print("\nWorkflow result:")
    print(json.dumps(workflow, indent=2))

    lineage = post(
        "/agents/lineage/trace",
        {"digest": workflow["workflowRecord"]},
    )
    print("\nWorkflow lineage:")
    print(json.dumps(lineage, indent=2))


if __name__ == "__main__":
    main()
