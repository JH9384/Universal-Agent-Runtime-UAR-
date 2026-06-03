---
description: Path validation must detect symlinks in the original path, not the resolved path
tags: [security, path-traversal, symlink, filesystem]
globs: ["uar/skills/doc_ingest*.py", "uar/core/validation.py", "uar/skills/autonomi_storage.py", "uar/skills/graphrag_skills.py"]
---

# Path Security Symlink Detection Rule

## Rule

When validating filesystem paths for security (e.g., `validate_path_security`), **NEVER** check for symlinks on a *resolved* path.  `Path.resolve()` silently follows symlinks, so any check on the resolved path misses intermediate symlinks entirely.

Always check symlinks on the **original path** using `os.lstat()` (which does not follow symlinks) on each path component.

## Why

`Path.resolve()` follows all symlinks in the path chain.  If `/safe/link` is a symlink to `/safe/subdir`, then `Path("/safe/link/file.txt").resolve()` returns `/safe/subdir/file.txt`.  A symlink check on the resolved path sees only normal directories — the symlink is invisible.

An attacker can exploit this by creating symlinks inside the allowed root that point to other locations inside the root, then using them to confuse path traversal logic, enable TOCTOU races, or bypass audit logging.

## Detect

Forbidden pattern — checking resolved path for symlinks:

```python
def validate_path_security(path, allowed_root):
    resolved = path.resolve()
    # ... relative_to check ...
    current = allowed_root.resolve()
    for part in resolved.parts[len(current.parts):]:  # ← resolved path!
        current = current / part
        if current.is_symlink():  # ← checks resolved components, misses originals
            raise PathSecurityError(...)
```

Correct pattern — check original path with lstat:

```python
def _has_symlink_in_path(path: Path) -> bool:
    abs_path = os.path.abspath(str(path))
    parts = Path(abs_path).parts
    if not parts:
        return False
    current = Path(parts[0]) if parts[0] != "/" else Path("/")
    for part in parts[1:]:
        current = current / part
        try:
            if stat.S_ISLNK(os.lstat(current).st_mode):
                return True
        except (OSError, FileNotFoundError):
            try:
                os.readlink(current)
                return True  # broken symlink is still a symlink
            except OSError:
                pass
    return False
```

## Additional Rule: O_NOFOLLOW on File Open

When opening files after validation, use `os.open(path, os.O_RDONLY | os.O_NOFOLLOW)` followed by `os.fdopen()` to prevent TOCTOU attacks where a file is replaced by a symlink between validation and open.

```python
if hasattr(os, "O_NOFOLLOW"):
    fd = os.open(file_path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "r", encoding="utf-8") as f:
        content = f.read()
else:
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
```

## Additional Rule: Validate Original Path Before resolve()

Entry points that accept user-provided paths must validate the **original** path before calling `resolve()`:

```python
raw_path = Path(input_path)
validate_path_security(raw_path, ALLOWED_ROOT)  # ← validate BEFORE resolve
path = raw_path.resolve()  # ← now safe to resolve for actual I/O
```

## Critical Locations

- `uar/core/validation.py::validate_path_security` — core path validator
- `uar/skills/doc_ingest.py` — document ingestion with directory traversal
- `uar/skills/doc_ingest_enhanced.py` — enhanced document ingestion
- `uar/skills/autonomi_storage.py` — file path validation
- `uar/skills/graphrag_skills.py` — source path validation

## Known Offenders (Fixed)

- `uar/core/validation.py::validate_path_security` — used `resolved_path.parts` loop
- `uar/skills/doc_ingest.py::doc_ingest` — resolved path before validation
- `uar/skills/doc_ingest.py::_read_file_safely` — plain `open()` without `O_NOFOLLOW`
- `uar/skills/doc_ingest_enhanced.py::_extract_with_fallback` — plain `open()`
