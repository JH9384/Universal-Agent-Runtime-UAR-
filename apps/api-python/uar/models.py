from pydantic import BaseModel, Field
from typing import Any

class UORObjectIn(BaseModel):
    mediaType: str = "application/json"
    mode: str = "immutable"
    attributes: dict[str, Any] = Field(default_factory=dict)
    links: list[dict[str, Any]] = Field(default_factory=list)
    content: Any
