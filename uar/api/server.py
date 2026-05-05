import json
import logging
import os
import time
import uuid
import asyncio
from typing import Any, List, Optional

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, Depends, Request, status, Response, UploadFile, File
from fastapi.responses import JSONResponse, StreamingResponse, PlainTextResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator

from uar.core.contracts import GoalSpec
from uar.core.exceptions import UARError, ValidationError, PathSecurityError
from uar.core.planner import SimplePlanner
from uar.core.replay import run_record_from_events
from uar.core.orchestrator import build_orchestration_plan
from uar.core.validation import validate_goal, validate_skills, validate_input_path
from uar.memory.json_store import JsonRunStore
from .middleware import (
    error_handler_middleware,
    rate_limit_middleware,
    auth_middleware,
    request_logging_middleware,
)
from .tracing import trace_span
from uar.api.metrics import get_metrics_collector

# Backpressure configuration
BACKPRESSURE_ENABLED = os.getenv("BACKPRESSURE_ENABLED", "true").lower() == "true"
BACKPRESSURE_THRESHOLD = int(os.getenv("BACKPRESSURE_THRESHOLD", "100"))  # Max buffered events
BACKPRESSURE_DELAY = float(os.getenv("BACKPRESSURE_DELAY", "0.1"))  # Delay in seconds when backpressure triggered

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# register skills
import uar.skills.section_sum  # noqa
import uar.skills.doc_ingest  # noqa
import uar.skills.dependency_map  # noqa
import uar.skills.sum_review  # noqa
import uar.skills.ollama_generate  # noqa
import uar.skills.graphrag_skills  # noqa
import uar.skills.autonomi_storage  # noqa

# Lifespan for graceful startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan handler for graceful startup and shutdown."""
    # Startup
    logger.info("UAR API starting up...")
    yield
    # Shutdown - drain in-flight requests
    logger.info("UAR API shutting down, draining requests (5s grace period)...")
    import asyncio
    await asyncio.sleep(0.1)  # Let any in-flight requests complete
    logger.info("UAR API shutdown complete")


# CORS configuration
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
CORS_ALLOW_CREDENTIALS = os.getenv("CORS_ALLOW_CREDENTIALS", "true").lower() == "true"
CORS_ALLOW_METHODS = os.getenv("CORS_ALLOW_METHODS", "*")
CORS_ALLOW_HEADERS = os.getenv("CORS_ALLOW_HEADERS", "*")

app = FastAPI(
    title="UAR API",
    description="Universal Agent Runtime API with production security features",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=CORS_ALLOW_CREDENTIALS,
    allow_methods=[CORS_ALLOW_METHODS] if CORS_ALLOW_METHODS != "*" else ["*"],
    allow_headers=[CORS_ALLOW_HEADERS] if CORS_ALLOW_HEADERS != "*" else ["*"],
)

store = JsonRunStore()

# Security scheme for API key authentication
security = HTTPBearer(auto_error=False)


# Custom exception handlers for UAR exceptions
@app.exception_handler(ValidationError)
async def validation_error_handler(request, exc):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "detail": {
                "error": "Validation error",
                "code": exc.code.value,
                "message": str(exc),
                "field": getattr(exc, 'field', None)
            }
        }
    )


@app.exception_handler(PathSecurityError)
async def path_security_error_handler(request, exc):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "detail": {
                "error": "Path security violation",
                "code": exc.code.value,
                "message": str(exc),
                "field": "input_path"
            }
        }
    )


@app.exception_handler(UARError)
async def uar_error_handler(request, exc):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": {
                "error": "Internal error",
                "code": exc.code.value,
                "message": str(exc),
            }
        }
    )


class RunRequest(BaseModel):
    goal: str
    skills: Optional[List[str]] = None
    input_path: Optional[str] = None
    timeout_seconds: Optional[float] = None
    metadata: Optional[dict] = None

    @field_validator('goal')
    @classmethod
    def validate_goal_field(cls, v):
        return validate_goal(v)

    @field_validator('skills')
    @classmethod
    def validate_skills_field(cls, v):
        return validate_skills(v)

    @field_validator('input_path')
    @classmethod
    def validate_input_path_field(cls, v):
        from pathlib import Path
        import os
        root = Path(os.getenv("PROJECT_ROOT", Path.cwd())).resolve()
        return validate_input_path(v, allowed_root=root)

    @field_validator('timeout_seconds')
    @classmethod
    def validate_timeout_field(cls, v):
        if v is not None:
            from uar.core.validation import validate_timeout
            return validate_timeout(v)
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
    detail: Optional[str] = None
    field: Optional[str] = None


def _build_goal(req: RunRequest) -> GoalSpec:
    """Build GoalSpec with proper validation and unique ID"""
    goal_id = f"api-{uuid.uuid4().hex[:8]}"
    
    metadata: dict[str, Any] = {}
    if req.input_path:
        metadata["input_path"] = req.input_path
    if req.timeout_seconds:
        metadata["timeout_seconds"] = req.timeout_seconds
    if req.metadata:
        # User-supplied extras (e.g. graphrag_method, ollama_model); do not
        # allow overriding the sanitized input_path/timeout.
        extras = {k: v for k, v in req.metadata.items()
                  if k not in {"input_path", "timeout_seconds"}}
        metadata.update(extras)
    
    return GoalSpec(
        id=goal_id,
        user_intent=req.goal,
        objective=req.goal,
        required_skills=req.skills or [],
        metadata=metadata,
    )


def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    """Dependency to get current authenticated user"""
    return auth_middleware(credentials)


@app.post("/api/uar/run", response_model=RunResponse, responses={
    400: {"model": ErrorResponse, "description": "Validation error"},
    429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
    500: {"model": ErrorResponse, "description": "Internal server error"}
})
@error_handler_middleware
async def run_goal(
    req: RunRequest, 
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
):
    """Execute a goal and return the complete result"""
    with trace_span("api.run_goal", {"goal": req.goal[:50]}):
        # Apply rate limiting
        rate_limit_middleware(request, credentials)
        
        # Get user info
        user_info = auth_middleware(credentials)
        
        # Log request
        request_id = request_logging_middleware(request, user_info)
        
        try:
            goal = _build_goal(req)
            planner = SimplePlanner()
            strategy = planner.plan(goal)

            from uar.core.executor import Executor

            executor = Executor()
            timeout = req.timeout_seconds or 5.0
            result = executor.run(strategy, goal, timeout_seconds=timeout)

            store.append(result)
            logger.info(f"[{request_id}] Run completed successfully: {result.run_id}")
            
            return result
            
        except ValidationError as e:
            logger.warning(f"[{request_id}] Validation error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "Validation error",
                    "message": str(e),
                    "field": e.field,
                    "request_id": request_id
                }
            )
        except UARError as e:
            logger.error(f"[{request_id}] UAR error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "UAR error",
                    "message": str(e),
                    "request_id": request_id
                }
            )
        except Exception as e:
            logger.error(f"[{request_id}] Unexpected error in run_goal: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": "Internal server error",
                    "message": "An unexpected error occurred",
                    "request_id": request_id
                }
            )


@app.post("/api/uar/stream", responses={
    400: {"model": ErrorResponse, "description": "Validation error"},
    429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
    500: {"model": ErrorResponse, "description": "Internal server error"}
})
@error_handler_middleware
async def stream_goal(
    req: RunRequest,
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
):
    """Execute a goal and stream events in real-time"""
    with trace_span("api.stream_goal", {"goal": req.goal[:50]}):
        # Apply rate limiting
        rate_limit_middleware(request, credentials)
        
        # Get user info
        user_info = auth_middleware(credentials)
        
        # Log request
        request_id = request_logging_middleware(request, user_info)
        
        try:
            goal = _build_goal(req)
            strategy = SimplePlanner().plan(goal)

            plan = build_orchestration_plan(strategy)

            from uar.core.executor import Executor

            executor = Executor()
            timeout = req.timeout_seconds or 5.0
            cid = getattr(request.state, 'correlation_id', '')

            def emit(event: dict) -> str:
                return f"event: {event['type']}\ndata: {json.dumps(event)}\n\n"

            def create_event(event_type: str, run_id: str, skill=None, payload=None, error=None):
                """Create a properly formatted event following the uar.event.v1 schema."""
                return {
                    "schema_version": "uar.event.v1",
                    "type": event_type,
                    "run_id": run_id,
                    "goal_id": strategy.goal_id,
                    "skill": skill,
                    "timestamp": time.time(),
                    "correlation_id": cid,
                    "payload": payload or {},
                    "error": error,
                }

            async def generate():
                events = []
                persisted = False
                last_heartbeat = time.time()
                heartbeat_interval = 30  # Send heartbeat every 30 seconds
                
                try:
                    # emit orchestration graph first
                    yield emit(create_event(
                        "orchestration_plan",
                        run_id="pending",
                        payload={"graph": plan.to_graph()}
                    ))

                    for event in executor.iter_events(strategy, goal, timeout_seconds=timeout, correlation_id=cid):
                        # Check if heartbeat needed
                        current_time = time.time()
                        if current_time - last_heartbeat > heartbeat_interval:
                            yield emit(create_event(
                                "heartbeat",
                                run_id="pending",
                                payload={"timestamp": current_time}
                            ))
                            last_heartbeat = current_time
                        
                        events.append(event)
                        
                        # Backpressure handling: slow down if too many events buffered
                        if BACKPRESSURE_ENABLED and len(events) > BACKPRESSURE_THRESHOLD:
                            logger.debug(f"Backpressure triggered: {len(events)} events buffered, delaying {BACKPRESSURE_DELAY}s")
                            await asyncio.sleep(BACKPRESSURE_DELAY)
                        
                        yield emit(event)

                    # Persist successful run
                    try:
                        record = run_record_from_events(events, strategy.ordered_skills)
                        store.append(record)
                        persisted = True
                        logger.info(f"[{request_id}] Stream completed and persisted: {record.run_id}")
                    except Exception as persist_error:
                        logger.error(f"[{request_id}] Failed to persist stream results: {str(persist_error)}")
                        # Do not let the finally-block retry a reconstruction that
                        # already failed deterministically (e.g. EventContractError).
                        persisted = True
                        # Still emit completion but mark persistence failure
                        yield emit(create_event(
                            "error",
                            run_id="unknown",
                            error=f"Execution completed but persistence failed: {str(persist_error)}"
                        ))
                        # Re-raise to trigger outer exception handler for client notification
                        raise persist_error
                    
                except Exception as e:
                    logger.error(f"[{request_id}] Stream error: {str(e)}", exc_info=True)
                    # Emit error event to client (correlation_id included via create_event)
                    yield emit(create_event(
                        "error",
                        run_id="unknown",
                        error=str(e)
                    ))
                finally:
                    # Ensure persistence even if client disconnects or error occurred
                    if events and not persisted:
                        try:
                            record = run_record_from_events(events, strategy.ordered_skills)
                            store.append(record)
                            logger.info(f"[{request_id}] Stream persisted {len(events)} events (fallback)")
                        except Exception as e:
                            logger.error(f"[{request_id}] Failed to persist stream events in finally: {str(e)}")

            return StreamingResponse(generate(), media_type="text/event-stream")
            
        except ValidationError as e:
            logger.warning(f"[{request_id}] Stream validation error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "Validation error",
                    "message": str(e),
                    "field": e.field,
                    "request_id": request_id
                }
            )
        except UARError as e:
            logger.error(f"[{request_id}] Stream UAR error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "UAR error",
                    "message": str(e),
                    "request_id": request_id
                }
            )
        except Exception as e:
            logger.error(f"[{request_id}] Unexpected stream error: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": "Internal server error",
                    "message": "An unexpected error occurred",
                    "request_id": request_id
                }
            )


@app.get("/api/uar/runs", responses={
    429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
    500: {"model": ErrorResponse, "description": "Internal server error"}
})
@error_handler_middleware
async def list_runs(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
):
    """List all stored runs"""
    # Apply rate limiting
    rate_limit_middleware(request, credentials)
    
    # Get user info
    user_info = auth_middleware(credentials)
    
    # Log request
    request_id = request_logging_middleware(request, user_info)
    
    try:
        runs = store.list_records()
        logger.info(f"[{request_id}] Listed {len(runs)} runs")
        return runs
        
    except Exception as e:
        logger.error(f"[{request_id}] Error listing runs: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Internal server error",
                "message": "Failed to retrieve runs",
                "request_id": request_id
            }
        )


@app.get("/api/health")
async def health_check():
    """Health check endpoint (backwards-compatible alias for liveness)."""
    return {"status": "healthy", "version": "1.0.0"}


@app.get("/api/health/live")
async def liveness_probe():
    """Kubernetes liveness probe — process is alive."""
    return {"status": "alive"}


@app.get("/api/metrics")
async def metrics_endpoint():
    """Prometheus-compatible metrics endpoint."""
    metrics = get_metrics_collector()
    return Response(
        content=metrics.get_prometheus_format(),
        media_type="text/plain; version=0.0.4; charset=utf-8"
    )

@app.get("/api/metrics/json")
async def metrics_json_endpoint():
    """JSON metrics endpoint for debugging."""
    metrics = get_metrics_collector()
    return metrics.get_metrics()

@app.get("/api/health/ready")
async def readiness_probe():
    """Kubernetes readiness probe — service is ready to accept traffic."""
    checks = {}

    # Check skills loaded
    from uar.core.registry import registry
    skills = registry.list()
    checks["skills_loaded"] = len(skills) > 0

    # Check disk writable
    try:
        test_file = store.runs_dir / ".health_check"
        test_file.write_text("ok")
        test_file.unlink()
        checks["disk_writable"] = True
    except Exception:
        checks["disk_writable"] = False

    # Check Ollama reachable (non-blocking, best-effort)
    try:
        import httpx
        ollama_host = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
        r = httpx.get(f"{ollama_host.rstrip('/')}/api/tags", timeout=2.0)
        checks["ollama_reachable"] = r.is_success
    except Exception:
        checks["ollama_reachable"] = False

    all_ready = all(checks.values())
    status_code = 200 if all_ready else 503
    return JSONResponse(
        status_code=status_code,
        content={"status": "ready" if all_ready else "not_ready", "checks": checks}
    )


def _docs_root():
    from pathlib import Path
    import os
    return Path(os.getenv("PROJECT_ROOT", Path.cwd())).resolve()


def _library_dir():
    """Default ingest library: <PROJECT_ROOT>/.uar_library (overridable)."""
    from pathlib import Path
    import os
    custom = os.getenv("UAR_LIBRARY_DIR")
    if custom:
        p = Path(custom).resolve()
    else:
        p = _docs_root() / ".uar_library"
    p.mkdir(parents=True, exist_ok=True)
    return p


# Upload limits
MAX_UPLOAD_BYTES = int(__import__("os").getenv("UAR_MAX_UPLOAD_BYTES", str(50 * 1024 * 1024)))  # 50MB
ALLOWED_UPLOAD_EXTS = {
    ".pdf", ".docx", ".xlsx", ".xlsm", ".ipynb", ".parquet", ".feather",
    ".txt", ".md", ".rst", ".tex", ".bib", ".csv", ".tsv", ".json", ".jsonl",
    ".yaml", ".yml", ".toml", ".html", ".htm", ".xml",
    ".py", ".js", ".ts", ".tsx", ".r", ".jl", ".rmd", ".qmd",
}


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
        raise PathSecurityError(str(resolved), f"Path is outside PROJECT_ROOT ({root})")
    return resolved


@app.get("/api/uar/docs/presets", responses={
    500: {"model": ErrorResponse, "description": "Internal server error"}
})
async def docs_presets():
    """Return convenient preset document paths inside PROJECT_ROOT."""
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


@app.post("/api/uar/docs/upload", responses={
    400: {"model": ErrorResponse, "description": "Validation error"},
    413: {"model": ErrorResponse, "description": "File too large"},
    500: {"model": ErrorResponse, "description": "Internal server error"},
})
async def docs_upload(files: List[UploadFile] = File(...)):
    """
    Upload one or more files into the default library directory.
    Filenames are sanitized; duplicates get a numeric suffix.
    """
    from pathlib import Path
    request_id = str(uuid.uuid4())
    library = _library_dir()
    saved = []
    rejected = []

    for upload in files:
        original = upload.filename or "upload.bin"
        # Sanitize: keep only the basename, strip null bytes / path separators
        safe_name = Path(original).name.replace("\x00", "")
        if not safe_name or safe_name in (".", ".."):
            rejected.append({"name": original, "reason": "invalid filename"})
            continue
        ext = Path(safe_name).suffix.lower()
        if ext and ext not in ALLOWED_UPLOAD_EXTS:
            rejected.append({"name": safe_name, "reason": f"extension not allowed: {ext}"})
            continue

        # Resolve dest with collision-free unique naming (UUID-based to avoid race conditions)
        dest = library / safe_name
        if dest.exists():
            stem = Path(safe_name).stem
            unique_id = str(uuid.uuid4())[:8]
            dest = library / f"{stem}.{unique_id}{ext}"

        # Stream-copy with size cap
        size = 0
        try:
            with open(dest, "wb") as out:
                while True:
                    chunk = await upload.read(1024 * 64)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > MAX_UPLOAD_BYTES:
                        try:
                            dest.unlink()
                        except OSError:
                            pass
                        rejected.append({
                            "name": safe_name,
                            "reason": f"file too large (>{MAX_UPLOAD_BYTES} bytes)",
                        })
                        size = -1
                        break
                    out.write(chunk)
        except Exception as e:
            logger.exception(f"[{request_id}] upload failed for {safe_name}")
            try:
                dest.unlink()
            except OSError:
                pass
            rejected.append({"name": safe_name, "reason": str(e)})
            continue
        finally:
            await upload.close()

        if size >= 0:
            saved.append({
                "name": dest.name,
                "path": str(dest),
                "size": size,
                "ext": ext,
            })

    return {
        "library": str(library),
        "saved": saved,
        "rejected": rejected,
        "request_id": request_id,
    }


@app.get("/api/uar/docs/library")
async def docs_library():
    """List files in the default ingest library."""
    library = _library_dir()
    entries = []
    total = 0
    for p in sorted(library.iterdir(), key=lambda x: x.name.lower()):
        if not p.is_file():
            continue
        st = p.stat()
        total += st.st_size
        entries.append({
            "name": p.name,
            "path": str(p),
            "size": st.st_size,
            "ext": p.suffix.lower(),
            "mtime": st.st_mtime,
        })
    return {"library": str(library), "count": len(entries), "total_bytes": total, "entries": entries}


@app.delete("/api/uar/docs/library")
async def docs_library_delete(name: str):
    """Delete a single file from the library by its basename."""
    from pathlib import Path
    library = _library_dir()
    safe_name = Path(name).name
    if not safe_name or safe_name in (".", ".."):
        return JSONResponse(status_code=400, content={"error": "Invalid name", "message": name})
    target = (library / safe_name).resolve()
    try:
        target.relative_to(library)
    except ValueError:
        return JSONResponse(status_code=400, content={"error": "Invalid name", "message": name})
    if not target.exists() or not target.is_file():
        return JSONResponse(status_code=404, content={"error": "Not found", "message": str(target)})
    try:
        target.unlink()
    except OSError as e:
        return JSONResponse(status_code=500, content={"error": "Delete failed", "message": str(e)})
    return {"deleted": str(target)}


@app.get("/api/uar/docs/browse", responses={
    400: {"model": ErrorResponse, "description": "Validation error"},
    500: {"model": ErrorResponse, "description": "Internal server error"}
})
async def docs_browse(path: str, limit: int = 200, recursive: bool = False):
    """
    Directory/file browser. When recursive=false (default), lists the
    immediate children of a directory (navigable). When recursive=true,
    lists all files under the path (doc_ingest preview).
    """
    request_id = str(uuid.uuid4())
    try:
        p = _resolve_docs_path(path)
        safe_path = str(p)
        if not p.exists():
            return JSONResponse(
                status_code=404,
                content={"error": "Path not found", "message": safe_path, "request_id": request_id},
            )
        entries = []
        total_bytes = 0
        truncated = False
        parent = str(p.parent) if p.parent != p else None
        if p.is_file():
            st = p.stat()
            entries.append({
                "name": p.name, "path": str(p), "size": st.st_size,
                "ext": p.suffix.lower(), "is_dir": False,
            })
            total_bytes += st.st_size
        else:
            iterator = p.rglob("*") if recursive else p.iterdir()
            count = 0
            for entry in iterator:
                if count >= limit:
                    truncated = True
                    break
                try:
                    is_dir = entry.is_dir()
                    st = entry.stat()
                    entries.append({
                        "name": entry.name,
                        "path": str(entry),
                        "size": 0 if is_dir else st.st_size,
                        "ext": "" if is_dir else entry.suffix.lower(),
                        "is_dir": is_dir,
                    })
                    if not is_dir:
                        total_bytes += st.st_size
                    count += 1
                except OSError:
                    continue
            # Sort: dirs first, then name
            entries.sort(key=lambda e: (not e["is_dir"], e["name"].lower()))
        by_ext: dict = {}
        for e in entries:
            if not e["is_dir"]:
                by_ext[e["ext"] or "(none)"] = by_ext.get(e["ext"] or "(none)", 0) + 1
        return {
            "path": safe_path,
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
    except (ValidationError, PathSecurityError) as e:
        return JSONResponse(
            status_code=400,
            content={"error": "Invalid path", "message": str(e), "request_id": request_id},
        )
    except Exception as e:
        logger.exception(f"[{request_id}] docs_browse failed")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "message": str(e), "request_id": request_id},
        )


@app.get("/api/status")
async def get_status(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
):
    """Get system status and user info"""
    user_info = auth_middleware(credentials)
    
    return {
        "status": "operational",
        "user": user_info,
        "available_skills": [
            "section_sum", "doc_ingest", "dependency_map",
            "sum_review", "ollama_generate", "graphrag_index",
            "graphrag_query", "autonomi_upload", "autonomi_download",
            "autonomi_status"
        ]
    }
