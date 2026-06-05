---
description: FastAPI file upload endpoints must use UploadFile type annotations
tags: [fastapi, api, uploads, types]
---

# FastAPI UploadFile Type Annotation Rule

## Problem
When a FastAPI endpoint accepts file uploads via multipart/form-data, the parameter must be typed as `UploadFile` (or `list[UploadFile]`). Using `list` or `list[Any]` prevents FastAPI from properly binding the multipart parser, causing the endpoint to receive unusable data or fail silently.

## Forbidden Pattern
```python
@router.post("/upload")
async def upload(files: list):  # WRONG — no UploadFile type hint
    ...
```

## Required Pattern
```python
from fastapi import UploadFile

@router.post("/upload")
async def upload(files: list[UploadFile]):  # CORRECT
    ...
```

## Enforcement
- Any router parameter named `files`, `upload`, or `file` with a `list` type must include `UploadFile` in the type annotation.
- Single-file parameters must be typed `UploadFile`.

## Rationale
Without the `UploadFile` type hint, FastAPI treats the parameter as a generic request field and does not invoke the multipart parser. The endpoint receives raw bytes or `None` instead of a file-like object with `.filename`, `.content_type`, and `.read()`.
