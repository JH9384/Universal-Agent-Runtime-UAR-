# Store list_records Must Filter by user_id

## Applies to
- `uar/api/routers/*.py`
- `uar/api/routers/operator/*.py`

## Rule
All endpoints that call `store.list_records()` to retrieve runs MUST pass a `user_id` filter, except for admin-only endpoints.

## Why
Without `user_id` filtering, `store.list_records()` returns **all users' data**, causing cross-user data leaks.

## Correct pattern
```python
user = user_info.get("user") if user_info else None
is_admin = user_info.get("tier") == "admin" if user_info else False

runs = store.list_records(
    user_id=None if is_admin else user, limit=...
)
```

## Incorrect pattern
```python
runs = store.list_records(limit=50000)  # Leaks all users' data
```

## Enforcement
- Check every `store.list_records()` call in router files.
- If the endpoint is not explicitly admin-only (tier check), it MUST pass `user_id`.
- For admin endpoints that intentionally return all data, add a code comment justifying it.
