from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ProductTemplate:
    id: str
    name: str
    description: str
    goal_template: str
    skills: list[str]
    required_inputs: list[str] = field(default_factory=list)
    planner: str = "simple"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "goal_template": self.goal_template,
            "skills": self.skills,
            "required_inputs": self.required_inputs,
            "planner": self.planner,
        }


TEMPLATES: dict[str, ProductTemplate] = {
    "repo_analyzer": ProductTemplate(
        id="repo_analyzer",
        name="Analyze Repository",
        description="Analyze a local repository or folder and summarize structure, dependencies, and notable findings.",
        goal_template="Analyze repository at {input_path} and extract structure, dependencies, and summary.",
        skills=["doc_ingest", "dependency_map", "sum_review"],
        required_inputs=["input_path"],
        planner="simple",
    ),
    "document_summarizer": ProductTemplate(
        id="document_summarizer",
        name="Summarize Document",
        description="Summarize a local document or folder into a structured, readable result.",
        goal_template="Summarize document or folder at {input_path} with key points and important sections.",
        skills=["doc_ingest", "sum_review"],
        required_inputs=["input_path"],
        planner="simple",
    ),
    "smart_qa": ProductTemplate(
        id="smart_qa",
        name="Smart Q&A",
        description="Ask a question using the local Ollama-backed generation skill.",
        goal_template="Answer this question clearly: {question}",
        skills=["ollama_generate"],
        required_inputs=["question"],
        planner="simple",
    ),
    "agent_assist": ProductTemplate(
        id="agent_assist",
        name="Agent Assist",
        description="Use safe LLM-assisted planning over registered skills only.",
        goal_template="{goal}",
        skills=[],
        required_inputs=["goal"],
        planner="llm",
    ),
}


def list_templates() -> list[dict[str, Any]]:
    return [template.to_dict() for template in TEMPLATES.values()]


def get_template(template_id: str) -> ProductTemplate:
    if template_id not in TEMPLATES:
        raise ValueError(f"Unknown template: {template_id}")
    return TEMPLATES[template_id]


def validate_inputs(template: ProductTemplate, inputs: dict[str, Any]) -> list[str]:
    errors = []
    for key in template.required_inputs:
        value = inputs.get(key)
        if value is None or str(value).strip() == "":
            errors.append(f"Missing required input: {key}")
    return errors


def build_goal(template: ProductTemplate, inputs: dict[str, Any]) -> str:
    safe_inputs = {key: str(value) for key, value in inputs.items()}
    return template.goal_template.format(**safe_inputs)


def user_message(status: str, failure: dict[str, Any] | None = None) -> str:
    category = (failure or {}).get("category")
    if status == "completed" and category in (None, "none"):
        return "Completed successfully."
    if category == "goal_mismatch":
        return "The result may not fully match the selected task. Try refining the input."
    if category == "low_quality_output":
        return "The result may be incomplete or too thin. Try adding more detail."
    if category == "timeout":
        return "The run timed out. Try a smaller input or fewer steps."
    if category == "runtime_error":
        return "The system ran into an execution issue while processing the request."
    return "The request finished, but may need review."
