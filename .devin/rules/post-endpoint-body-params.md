---
description: POST endpoints must accept data via request body models, not query params
tags: [fastapi, api, rest, post, pydantic]
---

# POST Endpoint Body Parameter Rule

## Problem
POST endpoints that declare plain function parameters (e.g., `agent_id: str`, `query: str`) force FastAPI to treat them as query parameters. This violates REST conventions, causes URL length/encoding issues for special characters, and leaks sensitive data in server logs.

## Forbidden Pattern
```python
@router.post("/governance/budget")
async def create_budget(
    agent_id: str,           # WRONG — query param
    max_tokens: int = 100000, # WRONG — query param
):
    ...
```

## Required Pattern
```python
from pydantic import BaseModel, Field

class BudgetCreateReq(BaseModel):
    agent_id: str = Field(..., description="Agent identifier")
    max_tokens: int = Field(100000, ge=1)

@router.post("/governance/budget")
async def create_budget(req: BudgetCreateReq):  # CORRECT — body param
    ...
```

## Enforcement
- POST, PUT, and PATCH endpoints MUST use Pydantic `BaseModel` subclasses for request data.
- Plain scalar parameters are only allowed for GET and DELETE endpoints.
- Exception: path parameters (e.g., `/{id}`) are allowed in the path itself.

## Rationale
Query parameters in POST requests are visible in URL logs, have length limits, and cannot represent nested structures. Request bodies are the standard REST mechanism for creating or updating resources.
