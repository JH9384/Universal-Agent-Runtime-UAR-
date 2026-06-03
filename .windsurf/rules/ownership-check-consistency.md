---
description: All ownership checks must use the same field fallback pattern
tags: [security, auth, consistency, api]
---

# Ownership Check Consistency Rule

## Problem
Run records may store the owning user under either `"user_id"` or `"user"` depending on the record version or store type. Endpoints that only check one field will incorrectly deny access to legitimate owners or allow access to non-owners.

## Forbidden Pattern
```python
# Inconsistent — only checks user_id
if record.get("user_id") != user and not is_admin:
    raise HTTPException(status_code=403)
```

## Required Pattern
```python
# Consistent — checks both fields with fallback
owner = record.get("user_id") or record.get("user", "")
if owner and owner != user and not is_admin:
    raise HTTPException(status_code=403, detail="Access denied")
```

## Enforcement
- Every endpoint that performs ownership authorization on a run record MUST use:
  ```python
  owner = record.get("user_id") or record.get("user", "")
  if owner and owner != user and not is_admin:
      raise HTTPException(status_code=403, detail="Access denied")
  ```
- Do NOT use `record.get("user_id") != user` without the fallback.
- Do NOT use `record["user_id"]` which raises KeyError if the field is absent.

## Rationale
The codebase has evolved through multiple storage backends and schema versions. Using a consistent fallback pattern ensures backward compatibility and prevents authorization bypasses or false denials across all endpoints.
