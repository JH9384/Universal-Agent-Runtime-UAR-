from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "apps" / "api-python" / "main.py"

IMPORT_LINE = "from agent_loop import run_document_strategy\n"
MODEL_BLOCK = '''

class AgentStrategySection(BaseModel):
    label: str = "section"
    goal: str | None = None
    input_ids: list[str] = Field(default_factory=list)
    values: list[Any] = Field(default_factory=list)
    runtime_markers: list[str] = Field(default_factory=list)
'''

MODE_FIELD = '    mode: str = "workflow"\n    sections: list[AgentStrategySection] = Field(default_factory=list)\n'

AGENT_MODE_BLOCK = '''
    if req.mode == "agent_strategy":
        if not req.sections:
            raise HTTPException(status_code=400, detail="Agent strategy mode requires sections")

        def executor(runtime_name: str, inputs: list[str]) -> dict[str, Any]:
            return execute_runtime(
                runtime_name=runtime_name,
                runtime_object=None,
                inputs=inputs,
                parameters={"workflow_id": req.name, "mode": "agent_strategy"},
            )

        result = run_document_strategy(
            sections=[section.model_dump() for section in req.sections],
            execute_runtime=executor,
        )
        record = create_record(
            mediaType="application/vnd.uar.agent-strategy-record+json",
            mode="immutable",
            attributes={"agent": "workflow", "kind": "agent-strategy-record", "workflowName": req.name},
            links=[{"rel": "section_output", "target": run["chosen"]["output"]} for run in result["sections"] if run.get("chosen") and run["chosen"].get("output")],
            content={"name": req.name, **result, "timestamp": timestamp()},
        )
        return {"status": "completed", "agentStrategyRecord": record["digest"], **result}

'''


def replace_once(text: str, old: str, new: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"Expected exactly one occurrence of {old!r}, found {count}")
    return text.replace(old, new, 1)


def main() -> None:
    original = MAIN.read_text(encoding="utf-8")
    text = original

    if IMPORT_LINE not in text:
        text = replace_once(text, "import uuid\n", "import uuid\n" + IMPORT_LINE)

    if "class AgentStrategySection" not in text:
        text = replace_once(text, "class WorkflowStep(BaseModel):\n", MODEL_BLOCK + "\nclass WorkflowStep(BaseModel):\n")

    if "mode: str = \"workflow\"" not in text:
        text = replace_once(
            text,
            "class WorkflowRunReq(BaseModel):\n    name: str = \"adhoc-workflow\"\n    inputs: list[str] = Field(default_factory=list)\n    steps: list[WorkflowStep]\n",
            "class WorkflowRunReq(BaseModel):\n    name: str = \"adhoc-workflow\"\n    mode: str = \"workflow\"\n    inputs: list[str] = Field(default_factory=list)\n    sections: list[AgentStrategySection] = Field(default_factory=list)\n    steps: list[WorkflowStep] = Field(default_factory=list)\n",
        )

    if "if req.mode == \"agent_strategy\":" not in text:
        text = replace_once(text, "def workflow_run(req: WorkflowRunReq):\n", "def workflow_run(req: WorkflowRunReq):\n" + AGENT_MODE_BLOCK)

    changed_lines = sum(1 for a, b in zip(original.splitlines(), text.splitlines()) if a != b) + abs(len(original.splitlines()) - len(text.splitlines()))
    if changed_lines > 80:
        raise SystemExit(f"Refusing unexpectedly large main.py change: {changed_lines} changed lines")

    MAIN.write_text(text, encoding="utf-8")
    print(f"Wired agent_strategy workflow mode into {MAIN}; changed_lines={changed_lines}")


if __name__ == "__main__":
    main()
