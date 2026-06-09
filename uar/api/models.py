"""Pydantic models shared across UAR API endpoints."""

from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, field_validator

from uar.core.validation import (
    validate_goal,
    validate_input_path,
    validate_skills,
)


class RunRequest(BaseModel):
    goal: str
    skills: Optional[List[str]] = None
    input_path: Optional[str] = None
    timeout_seconds: Optional[float] = None
    metadata: Optional[dict] = None
    execution_order: Optional[List[dict]] = None
    use_hierarchical: Optional[bool] = None
    idempotency_key: Optional[str] = None

    @field_validator("goal")
    @classmethod
    def validate_goal_field(cls, v):
        return validate_goal(v)

    @field_validator("skills")
    @classmethod
    def validate_skills_field(cls, v):
        return validate_skills(v)

    @field_validator("input_path")
    @classmethod
    def validate_input_path_field(cls, v):
        import os

        root = Path(os.getenv("PROJECT_ROOT", Path.cwd())).resolve()
        return validate_input_path(v, allowed_root=root)

    @field_validator("timeout_seconds")
    @classmethod
    def validate_timeout_field(cls, v):
        if v is not None:
            from uar.core.validation import validate_timeout

            return validate_timeout(v)
        return v

    @field_validator("execution_order")
    @classmethod
    def validate_execution_order_field(cls, v):
        if v is None:
            return v
        if not isinstance(v, list):
            raise ValueError("execution_order must be an array")
        seen_ids = set()
        for i, item in enumerate(v):
            if not isinstance(item, dict):
                raise ValueError(f"execution_order[{i}] must be an object")
            for field in ("type", "content", "id"):
                if field not in item:
                    raise ValueError(f"execution_order[{i}] missing required field: {field}")
            if item["type"] not in ["skill", "recipe"]:
                raise ValueError(f"execution_order[{i}] has invalid type: {item['type']}")
            if item["id"] in seen_ids:
                raise ValueError(f"execution_order[{i}] has duplicate ID: {item['id']}")
            seen_ids.add(item["id"])
            if item["type"] == "recipe":
                if not isinstance(item["content"], str) or not item["content"]:
                    raise ValueError(f"execution_order[{i}] recipe content must be non-empty")
            elif item["type"] == "skill":
                from uar.core.registry import registry

                if not registry.is_registered(item["content"]):
                    raise ValueError(f"execution_order[{i}] references unknown skill")
        return v


class RunResponse(BaseModel):
    run_id: str
    goal_id: str
    skills: List[str]
    outputs: List
    status: str
    errors: List[str]
    events: List[dict]
    final_context: dict


class ErrorResponse(BaseModel):
    error: str
    message: str
    code: Optional[str] = None
    request_id: Optional[str] = None
    field: Optional[str] = None
