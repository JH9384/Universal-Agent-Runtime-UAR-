"""Pydantic v2 request/response models for UOR object endpoints."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

ObjectMode = Literal["immutable", "mutable", "collection"]


class UORObjectIn(BaseModel):
    """Inbound payload for ``POST /objects``."""

    mediaType: str = "application/json"
    mode: ObjectMode = "immutable"
    attributes: Dict[str, Any] = Field(default_factory=dict)
    links: List[Dict[str, Any]] = Field(default_factory=list)
    content: Any = None


class RuntimeRegisterReq(BaseModel):
    """Inbound payload for ``POST /runtimes/register``."""

    name: str
    code: str
    description: str = ""
    tags: List[str] = Field(default_factory=list)
    attributes: Dict[str, Any] = Field(default_factory=dict)


class QueryReq(BaseModel):
    """Inbound payload for ``POST /agents/locator/query``."""

    where: Dict[str, Any] = Field(default_factory=dict)
    limit: int = Field(default=25, ge=1, le=10_000)


class VerifyReq(BaseModel):
    object: str
    expectedDigest: Optional[str] = None


class CompareReq(BaseModel):
    left: str
    right: str


class ComposeReq(BaseModel):
    inputs: List[str]
    compositionType: str = "dataset"
    attributes: Dict[str, Any] = Field(default_factory=dict)


class ExecuteReq(BaseModel):
    runtimeName: Optional[str] = None
    runtimeObject: Optional[str] = None
    inputs: List[str] = Field(default_factory=list)
    parameters: Dict[str, Any] = Field(default_factory=dict)


class WorkflowStep(BaseModel):
    runtimeName: Optional[str] = None
    runtimeObject: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    usePreviousOutput: bool = True


class WorkflowRunReq(BaseModel):
    name: str = "adhoc-workflow"
    inputs: List[str] = Field(default_factory=list)
    steps: List[WorkflowStep]


class ConstraintReq(BaseModel):
    action: str
    agent: str
    target: str
    policy: Optional[str] = None


class BridgeReq(BaseModel):
    source: Dict[str, Any]
    normalize: bool = True
    attributes: Dict[str, Any] = Field(default_factory=dict)


class InferenceReq(BaseModel):
    objects: List[str]
    task: str
    requireVerification: bool = True


class DelegationReq(BaseModel):
    goal: str
    inputs: List[str] = Field(default_factory=list)
    allowedAgents: List[str] = Field(default_factory=list)


class AtomicLangModelAnalyzeReq(BaseModel):
    grammar_spec: str = Field(
        ..., description="Formal grammar specification (e.g., BNF, EBNF)"
    )


class AtomicLangModelGenerateReq(BaseModel):
    prefix: str = Field(
        ..., description="Starting text sequence for generation"
    )
    count: int = Field(
        default=5, ge=1, le=50, description="Number of tokens to generate"
    )


class AtomicLangModelVerifyReq(BaseModel):
    text: str = Field(
        ..., description="Text to validate for syntax and semantics"
    )


__all__ = [
    "AtomicLangModelAnalyzeReq",
    "AtomicLangModelGenerateReq",
    "AtomicLangModelVerifyReq",
    "BridgeReq",
    "CompareReq",
    "ComposeReq",
    "ConstraintReq",
    "DelegationReq",
    "ExecuteReq",
    "InferenceReq",
    "ObjectMode",
    "QueryReq",
    "RuntimeRegisterReq",
    "UORObjectIn",
    "VerifyReq",
    "WorkflowRunReq",
    "WorkflowStep",
]
