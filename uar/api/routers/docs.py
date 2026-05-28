"""Document library endpoints.

Extracted from server.py to reduce monolith size.
"""

import logging
import os
import uuid
from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials

from uar.api.middleware import security, _is_dev_mode
from uar.api.responses import error_response
from uar.core.exceptions import ValidationError, PathSecurityError
from uar.services import AuthService

logger = logging.getLogger(__name__)
router = APIRouter()
_auth_svc = AuthService()


def _require_auth(credentials):
    """Require authenticated user or raise 401."""
    return _auth_svc.require_user(credentials)


def _require_auth_or_dev(
    credentials,
    module: str | None = None,
    endpoint: str | None = None,
    func: str | None = None,
):
    """Require auth in production; allow anonymous in dev mode.

    In dev mode an *invalid* API key is treated as anonymous rather
    than raising 401, so users with stale localStorage keys don't get
    locked out of local-first deployments.
    """
    from fastapi import HTTPException

    try:
        user = _auth_svc.authenticate(credentials)
    except HTTPException:
        if _is_dev_mode():
            user = None
        else:
            raise
    if user is None and not _is_dev_mode():
        msg = "Authentication required"
        if func:
            msg = f"{func}: {msg}. Provide a valid Bearer token."
        detail: dict[str, str] = {
            "error": "unauthorized",
            "message": msg,
        }
        if module:
            detail["module"] = module
        if endpoint:
            detail["endpoint"] = endpoint
        raise HTTPException(
            status_code=401,
            detail=detail,
        )
    return user


CHUNK_SIZE = 1024 * 64  # 64KB
DEFAULT_BROWSE_LIMIT = 200

# Upload limits
DEFAULT_MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50MB
MAX_UPLOAD_BYTES = max(
    1,
    int(
        os.getenv(
            "UAR_MAX_UPLOAD_BYTES", str(DEFAULT_MAX_UPLOAD_BYTES)
        ).strip()
        or str(DEFAULT_MAX_UPLOAD_BYTES)
    ),
)
ALLOWED_UPLOAD_EXTS = {
    ".pdf", ".docx", ".xlsx", ".xlsm", ".ipynb", ".parquet", ".feather",
    ".txt", ".md", ".rst", ".tex", ".bib", ".csv", ".tsv", ".json",
    ".jsonl", ".yaml", ".yml", ".toml", ".html", ".htm", ".xml",
    ".py", ".js", ".ts", ".tsx", ".r", ".jl", ".rmd", ".qmd",
}


def _docs_root():
    from pathlib import Path

    return Path(os.getenv("PROJECT_ROOT", Path.cwd())).resolve()


def _library_dir():
    """Default ingest library: <PROJECT_ROOT>/.uar_library (overridable)."""
    from pathlib import Path

    custom = os.getenv("UAR_LIBRARY_DIR")
    if custom:
        p = Path(custom).resolve()
    else:
        p = _docs_root() / ".uar_library"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _cleanup_orphaned_temp_files(library) -> int:
    """Clean up orphaned .tmp files in the library directory.

    Returns the number of files cleaned up.
    """
    import time

    cleaned = 0
    current_time = time.time()
    max_age_seconds = 3600

    for tmp_file in library.glob("*.tmp"):
        try:
            file_age = current_time - tmp_file.stat().st_mtime
            if file_age > max_age_seconds:
                tmp_file.unlink()
                cleaned += 1
                logger.info("Cleaned up orphaned temp file: %s", tmp_file.name)
        except (OSError, PermissionError):
            pass

    if cleaned > 0:
        logger.info("Cleaned up %s orphaned temp file(s)", cleaned)
    return cleaned


def _resolve_docs_path(raw: str):
    """Resolve a user-provided path (relative or absolute) and require it be
    contained within PROJECT_ROOT. Raises PathSecurityError otherwise."""
    from pathlib import Path

    root = _docs_root()
    raw = (raw or "").strip()
    if not raw:
        raise ValidationError("Empty path", field="path")
    if "\x00" in raw:
        raise PathSecurityError(raw, "Path contains null bytes")
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        raise PathSecurityError(
            str(resolved), f"Path is outside PROJECT_ROOT ({root})"
        ) from None
    return resolved


@router.get("/api/uar/docs/presets")
async def docs_presets(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """Return convenient preset document paths inside PROJECT_ROOT."""
    _require_auth_or_dev(credentials)
    project_root = _docs_root()
    library = _library_dir()
    candidates = ["docs", "specs", "tests", "apps/web/src", "uar"]
    presets = [{"name": "📚 library", "path": str(library)}]
    for name in candidates:
        p = project_root / name
        if p.exists() and p.is_dir():
            presets.append({"name": name, "path": str(p)})
    return {
        "project_root": str(project_root),
        "library": str(library),
        "presets": presets,
    }


@router.post("/api/uar/docs/upload")
async def docs_upload(
    files: list,
    overwrite: bool = False,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """Upload files to the document library."""
    from pathlib import Path

    _require_auth(credentials)
    request_id = str(uuid.uuid4())
    library = _library_dir()
    saved = []
    rejected = []

    for upload in files:
        original = upload.filename or "upload.bin"
        safe_name = Path(original).name.replace("\x00", "")
        if not safe_name or safe_name in (".", ".."):
            rejected.append({"name": safe_name, "reason": "Invalid filename"})
            continue
        ext = Path(safe_name).suffix.lower()
        if not ext or ext not in ALLOWED_UPLOAD_EXTS:
            rejected.append(
                {"name": safe_name, "reason": "Extension not allowed"}
            )
            continue

        dest = library / safe_name
        if not overwrite:
            max_attempts = 5
            for _ in range(max_attempts):
                if not dest.exists():
                    try:
                        import os as _os

                        fd = _os.open(
                            dest,
                            _os.O_CREAT | _os.O_EXCL | _os.O_WRONLY,
                            0o644,
                        )
                        try:
                            with _os.fdopen(fd, "wb") as _:
                                pass
                        except OSError:
                            try:
                                _os.close(fd)
                            except OSError:
                                pass
                            try:
                                dest.unlink()
                            except OSError:
                                pass
                            raise
                        break
                    except FileExistsError:
                        pass
                stem = Path(safe_name).stem
                unique_id = str(uuid.uuid4())[:8]
                dest = library / f"{stem}.{unique_id}{ext}"
            else:
                rejected.append(
                    {
                        "name": safe_name,
                        "reason": "Could not generate unique filename",
                    }
                )
                continue

        size = 0
        temp_dest = dest.with_suffix(dest.suffix + ".tmp")
        try:
            with open(temp_dest, "wb") as out:
                while True:
                    chunk = await upload.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > MAX_UPLOAD_BYTES:
                        rejected.append(
                            {
                                "name": safe_name,
                                "reason": (
                                    "file too large"
                                    f"(>{MAX_UPLOAD_BYTES} bytes)"
                                ),
                            }
                        )
                        size = -1
                        break
                    out.write(chunk)
        except Exception:
            logger.exception(
                "[%s] upload failed for %s", request_id, safe_name
            )
            for p in (temp_dest, dest):
                try:
                    p.unlink()
                except OSError:
                    pass
            rejected.append({"name": safe_name, "reason": "Upload failed"})
            continue
        finally:
            await upload.close()

        if size >= 0:
            try:
                if dest.exists():
                    dest.unlink()
                temp_dest.rename(dest)
                saved.append(
                    {
                        "name": dest.name,
                        "path": str(dest),
                        "size": size,
                        "ext": ext,
                    }
                )
            except OSError:
                logger.exception(
                    "[%s] rename failed for %s", request_id, safe_name
                )
                try:
                    temp_dest.unlink()
                except OSError:
                    pass
                rejected.append({"name": safe_name, "reason": "Rename failed"})
        else:
            for p in (temp_dest, dest):
                try:
                    p.unlink()
                except OSError:
                    pass

    return {
        "library": str(library),
        "saved": saved,
        "rejected": rejected,
        "request_id": request_id,
    }


@router.get("/api/uar/docs/library")
async def docs_library_list(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """List all files currently in the document library."""
    _require_auth_or_dev(credentials)
    library = _library_dir()
    entries = []
    total = 0
    for p in sorted(library.iterdir(), key=lambda x: x.name.lower()):
        if not p.is_file():
            continue
        st = p.stat()
        total += st.st_size
        entries.append(
            {
                "name": p.name,
                "path": str(p),
                "size": st.st_size,
                "ext": p.suffix.lower(),
                "mtime": st.st_mtime,
            }
        )
    return {
        "library": str(library),
        "count": len(entries),
        "total_bytes": total,
        "entries": entries,
    }


@router.delete("/api/uar/docs/library")
async def docs_library_delete(
    name: str,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """Delete a single file from the library by its basename."""
    _require_auth(credentials)
    from pathlib import Path

    library = _library_dir().resolve()
    safe_name = Path(name).name
    if not safe_name or safe_name in (".", ".."):
        return error_response(400, "Invalid name", "Invalid file name")
    target = (library / safe_name).resolve()
    try:
        target.relative_to(library)
    except ValueError:
        return error_response(400, "Invalid name", "Invalid file name")
    if not target.exists() or not target.is_file():
        return error_response(404, "Not found", "File not found")
    try:
        target.unlink()
    except OSError:
        return error_response(500, "Delete failed", "File deletion failed")
    return {"deleted": str(target)}


@router.get("/api/uar/docs/browse")
async def docs_browse(
    path: str,
    limit: int = DEFAULT_BROWSE_LIMIT,
    recursive: bool = False,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """Browse directories with optional recursion."""
    _require_auth_or_dev(
        credentials,
        module="uar.api.routers.docs",
        endpoint="GET /api/uar/docs/browse",
        func="docs_browse",
    )
    request_id = str(uuid.uuid4())
    try:
        p = _resolve_docs_path(path)
        if not p.exists():
            return JSONResponse(
                status_code=404,
                content={
                    "error": "Path not found",
                    "message": "Path not found",
                    "request_id": request_id,
                },
            )
        entries = []
        total_bytes = 0
        truncated = False
        parent = str(p.parent) if p.parent != p else None
        if p.is_file():
            st = p.stat()
            entries.append(
                {
                    "name": p.name,
                    "path": str(p),
                    "size": st.st_size,
                    "ext": p.suffix.lower(),
                    "is_dir": False,
                }
            )
            total_bytes += st.st_size
        else:
            iterator = p.rglob("*") if recursive else p.iterdir()
            count = 0
            for entry in iterator:
                if count >= limit:
                    truncated = True
                    break
                if entry.is_symlink():
                    continue
                try:
                    is_dir = entry.is_dir()
                    st = entry.stat(follow_symlinks=False)
                    entries.append(
                        {
                            "name": entry.name,
                            "path": str(entry),
                            "size": 0 if is_dir else st.st_size,
                            "ext": "" if is_dir else entry.suffix.lower(),
                            "is_dir": is_dir,
                        }
                    )
                    if not is_dir:
                        total_bytes += st.st_size
                    count += 1
                except OSError:
                    continue
            entries.sort(key=lambda e: (not e["is_dir"], e["name"].lower()))
        by_ext: dict = {}
        for e in entries:
            if not e["is_dir"]:
                by_ext[e["ext"] or "(none)"] = (
                    by_ext.get(e["ext"] or "(none)", 0) + 1
                )
        return {
            "path": str(p),
            "parent": parent,
            "is_dir": p.is_dir(),
            "recursive": recursive,
            "file_count": sum(1 for e in entries if not e["is_dir"]),
            "dir_count": sum(1 for e in entries if e["is_dir"]),
            "total_bytes": total_bytes,
            "truncated": truncated,
            "by_extension": by_ext,
            "entries": entries,
        }
    except (ValidationError, PathSecurityError):
        return error_response(
            400, "Invalid path", "Path validation failed", request_id
        )
    except Exception:
        logger.exception("[%s] docs_browse failed", request_id)
        return error_response(
            500, "Internal server error", "Browse request failed", request_id
        )


@router.post("/api/uar/docs/create_folder")
async def docs_create_folder(
    payload: dict,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """Create a folder inside the library directory."""
    _require_auth(credentials)
    request_id = str(uuid.uuid4())
    parent_path = payload.get("path")
    folder_name = payload.get("name")

    try:
        if not isinstance(parent_path, str) or not isinstance(
            folder_name, str
        ):
            return error_response(
                400, "Invalid input types",
                "Both 'path' and 'name' must be strings", request_id
            )

        if not parent_path or not folder_name:
            return error_response(
                400, "Missing required fields",
                "Both 'path' and 'name' are required", request_id
            )

        folder_name = folder_name.strip()
        if not folder_name:
            return error_response(
                400, "Invalid folder name",
                "Folder name cannot be empty or whitespace only", request_id
            )

        if (
            "/" in folder_name
            or "\\" in folder_name
            or ".." in folder_name
            or "\x00" in folder_name
            or any(ord(c) < 32 for c in folder_name)
        ):
            return error_response(
                400,
                "Invalid folder name",
                (
                    "Folder name cannot contain slashes, parent"
                    " directory references, null bytes, or control"
                    " characters"
                ),
                request_id,
            )

        reserved_names = {"CON", "PRN", "AUX", "NUL"}
        reserved_names.update(f"COM{i}" for i in range(1, 10))
        reserved_names.update(f"LPT{i}" for i in range(1, 10))
        if folder_name.upper() in reserved_names:
            return error_response(
                400, "Invalid folder name",
                "Folder name is a reserved Windows name", request_id
            )

        parent_path = os.path.normpath(parent_path).lstrip(os.sep)
        if ".." in parent_path.split(os.sep):
            return error_response(
                400, "Invalid path",
                "Parent path contains traversal attempt", request_id
            )

        library = _library_dir()
        try:
            target_parent = (library / parent_path).resolve()
            target_parent.relative_to(library.resolve())
        except (OSError, ValueError):
            return error_response(
                400, "Invalid path",
                "Parent path is outside library", request_id
            )

        new_folder = target_parent / folder_name
        try:
            new_folder.mkdir(parents=True, exist_ok=True)
        except OSError:
            logger.exception("[%s] Folder creation failed", request_id)
            return error_response(
                500, "Folder creation failed",
                "Folder creation failed", request_id
            )

        return {
            "created": str(new_folder),
            "name": folder_name,
            "path": str(target_parent),
            "request_id": request_id,
        }

    except (ValidationError, PathSecurityError) as e:
        logger.warning(
            "[%s] docs_create_folder validation error: %s",
            request_id,
            str(e),
        )
        return error_response(
            400, "Invalid path", "Invalid path provided", request_id
        )
    except Exception:
        logger.exception("[%s] docs_create_folder failed", request_id)
        return error_response(
            500, "Folder creation failed",
            "Internal server error", request_id
        )
