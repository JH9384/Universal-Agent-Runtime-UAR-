"""Streaming endpoints for the UAR API.

Includes WebSocket (/api/uar/stream/ws, /ws/run) and SSE (/api/uar/stream)
handlers. Shared state (connection counters, rate limiters, service
instances) is imported lazily from uar.api.server to avoid circular
dependencies and preserve test-patch compatibility.
"""

import asyncio
import json
import logging
import os
import time
import uuid
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import ValidationError as PydanticValidationError
from starlette.websockets import WebSocketState

from uar.api.models import ErrorResponse, RunRequest
from uar.api.middleware import (
    auth_middleware,
    build_rate_limit_key,
    error_handler_middleware,
    rate_limit_middleware,
    rate_limiter,
    request_logging_middleware,
    RATE_LIMITS,
    _extract_skill_from_request_data,
)
from uar.api.tracing import trace_span
from uar.core.binary_stream import (
    serialize_trefoil,
    serialize_molecular,
    serialize_quantum_circuit,
)
from uar.core.exceptions import UARError, ValidationError
from uar.core.planner import SimplePlanner

router = APIRouter()

logger = logging.getLogger("uar.api.streaming")

security = HTTPBearer(auto_error=False)


async def _stream_binary_visualization(
    websocket: WebSocket,
    event: dict,
) -> None:
    """Send binary simulation data after a skill_complete JSON event.

    Detects visualization skills and streams their 3D data as
    binary WebSocket frames for efficient client rendering.
    """
    skill = event.get("skill")
    payload = event.get("payload", {})
    result = payload.get("result", {})

    serializers = {
        "trefoil_simulation": serialize_trefoil,
        "molecular_visualization": serialize_molecular,
        "quantum_circuit_visualization": serialize_quantum_circuit,
    }

    serializer = serializers.get(skill or "")
    if not serializer:
        return

    try:
        chunks = serializer(result)
        for name, data in chunks.items():
            await websocket.send_bytes(
                name.encode("utf-8") + b"\x00" + data
            )
    except Exception:
        # Binary streaming is best-effort; JSON event already sent
        pass


@router.websocket("/api/uar/stream/ws")
async def stream_goal_ws(websocket: WebSocket):
    """Execute a goal and stream events via WebSocket for real-time updates"""
    from uar.api.server import (
        _build_goal,
        _event_svc,
        _exec_svc,
        _ws_conn_counter,
        WS_HEARTBEAT_INTERVAL,
    )

    request_id = str(uuid.uuid4())
    correlation_id = str(uuid.uuid4())

    # Parse Authorization header first so we can rate-limit before
    # accepting the connection and consuming server resources.
    auth_header = websocket.headers.get("authorization", "")
    credentials: Optional[HTTPAuthorizationCredentials] = None
    if auth_header.lower().startswith("bearer "):
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=auth_header[7:],
        )

    # Apply connection-level rate limiting BEFORE accepting the
    # WebSocket, to prevent connection-exhaustion attacks.
    client_ip = websocket.client.host if websocket.client else "unknown"
    rate_limit_key, tier = build_rate_limit_key(client_ip, credentials)
    limit = RATE_LIMITS.get(tier, RATE_LIMITS["default"])["requests"]
    window = RATE_LIMITS.get(tier, RATE_LIMITS["default"])["window"]
    _ws_pre_allowed, _ws_pre_remaining = rate_limiter.is_allowed(
        rate_limit_key, limit, window
    )
    if not _ws_pre_allowed:
        await websocket.close(code=1008, reason="Rate limit exceeded")
        return

    # Enforce global WebSocket connection cap
    if not await _ws_conn_counter.acquire():
        await websocket.close(code=1008, reason="Too many connections")
        return

    try:
        await websocket.accept()
    except Exception:
        await _ws_conn_counter.release()
        raise

    websocket.state.correlation_id = correlation_id

    _goal_id = ""

    def create_event(
        event_type: str,
        run_id: str,
        skill=None,
        payload=None,
        error=None,
    ):
        return _event_svc.create(
            event_type=event_type,
            run_id=run_id,
            goal_id=_goal_id,
            skill=skill,
            payload=payload,
            error=error,
            correlation_id=correlation_id,
        )

    try:
        # Receive the run request from WebSocket with timeout
        # to prevent malicious clients from holding connections open
        # indefinitely
        websocket_timeout = max(
            1,
            int(
                os.getenv("WEBSOCKET_RECEIVE_TIMEOUT", "30").strip()
                or "30"
            ),
        )
        try:
            data = await asyncio.wait_for(
                websocket.receive_json(), timeout=websocket_timeout
            )
        except asyncio.TimeoutError:
            logger.warning(
                "[%s] WebSocket receive timeout after %ss",
                request_id,
                websocket_timeout,
            )
            await websocket.send_json(
                create_event(
                    "error",
                    run_id="unknown",
                    error="Receive timeout",
                    payload={
                        "message": "No data received within timeout",
                        "request_id": request_id,
                        "code": "RECEIVE_TIMEOUT",
                    },
                )
            )
            await websocket.close()
            return

        # Validate request size before parsing
        # Use same limit as HTTP endpoints (10MB)
        from uar.api.middleware import DEFAULT_MAX_REQUEST_BODY_BYTES

        max_body_size = int(
            os.getenv(
                "MAX_REQUEST_BODY_BYTES", str(DEFAULT_MAX_REQUEST_BODY_BYTES)
            )
        )
        json_size = len(json.dumps(data))
        if json_size > max_body_size:
            logger.warning(
                f"WebSocket request too large: {json_size} bytes > "
                f"{max_body_size}"
            )
            await websocket.send_json(
                create_event(
                    "error",
                    run_id="unknown",
                    error="Request body too large",
                    payload={
                        "message": (
                            f"Maximum body size is {max_body_size} bytes"
                        ),
                        "request_id": request_id,
                        "code": "BODY_TOO_LARGE",
                    },
                )
            )
            await websocket.close()
            return

        try:
            req = RunRequest(**data)
        except ValidationError as e:
            logger.warning(
                "[%s] WebSocket validation error: %s", request_id, str(e)
            )
            await websocket.send_json(
                create_event(
                    "error",
                    run_id="unknown",
                    error="Validation error",
                    payload={
                        "message": "Invalid input provided",
                        "request_id": request_id,
                        "code": "VALIDATION_ERROR",
                    },
                )
            )
            await websocket.close()
            return
        except PydanticValidationError as e:
            logger.warning(
                "[%s] WebSocket pydantic validation error: %s",
                request_id,
                str(e),
            )
            await websocket.send_json(
                create_event(
                    "error",
                    run_id="unknown",
                    error="Validation error",
                    payload={
                        "message": "Invalid input provided",
                        "request_id": request_id,
                        "code": "VALIDATION_ERROR",
                    },
                )
            )
            await websocket.close()
            return

        # Skill-specific rate limiting (post-parse, reuses pre-connect
        # token — connection-level check already consumed one token above).
        from uar.api.middleware import check_rate_limit

        skill_name = _extract_skill_from_request_data(
            req.skills, req.execution_order
        )

        limit, window, rate_limit_type = check_rate_limit(
            rate_limit_key, tier, skill_name
        )

        # Only re-check when the skill has a tighter limit than the tier.
        # Avoids double-consuming tokens on the default tier limit.
        allowed = _ws_pre_allowed
        if rate_limit_type == "skill":
            try:
                _rl_result = rate_limiter.is_allowed(
                    rate_limit_key, limit, window
                )
                allowed = bool(_rl_result[0])  # type: ignore[index,assignment]
            except Exception as rate_limit_error:
                logger.error(
                    f"[{request_id}] Rate limit check failed: "
                    f"{str(rate_limit_error)}"
                )
                await websocket.send_json(
                    create_event(
                        "error",
                        run_id="unknown",
                        error="Rate limit check failed",
                        payload={
                            "message": "Internal error checking rate limit",
                            "request_id": request_id,
                            "code": "RATE_LIMIT_ERROR",
                        },
                    )
                )
                try:
                    await websocket.close(
                        code=1008, reason="Rate limit error"
                    )
                except Exception:
                    logger.warning("WebSocket close failed", exc_info=True)
                return

        if not allowed:
            logger.warning(
                f"WebSocket rate limit exceeded for {rate_limit_key}"
            )
            await websocket.send_json(
                create_event(
                    "error",
                    run_id="unknown",
                    error="Rate limit exceeded",
                    payload={
                        "message": (
                            f"{limit} requests per {window} seconds allowed."
                        ),
                        "request_id": request_id,
                        "code": "RATE_LIMIT_EXCEEDED",
                        "skill": skill_name if skill_name else None,
                    },
                )
            )
            # Use standard WebSocket close code 1008 (policy violation)
            try:
                await websocket.close(code=1008, reason="Rate limit exceeded")
            except Exception as close_error:
                # If close fails, try without code
                logger.warning(
                    f"[{request_id}] WebSocket close with code failed: "
                    f"{str(close_error)}"
                )
                try:
                    await websocket.close()
                except Exception as fallback_error:
                    logger.error(
                        f"[{request_id}] WebSocket close fallback failed: "
                        f"{str(fallback_error)}"
                    )
            return

        # Get user info
        user_info = auth_middleware(credentials)

        # Log request (request_id generated at line 556)
        user_str = user_info["user"] if user_info else "anonymous"
        logger.info(
            "[%s] WebSocket request from %s", request_id, user_str
        )

        try:
            goal = _build_goal(req)
            strategy = SimplePlanner().plan(goal)
            _goal_id = strategy.goal_id

            # WebSocket heartbeat with coalescing
            last_hb = time.time()
            hb_interval = WS_HEARTBEAT_INTERVAL
            async for event in _exec_svc.stream_goal(
                goal, request_id, user_str, correlation_id,
                yield_persisted=True,
            ):
                await websocket.send_json(event)
                last_hb = time.time()

                # Stream binary visualization data for 3D skills
                if event.get("type") == "skill_complete":
                    try:
                        await _stream_binary_visualization(
                            websocket, event
                        )
                    except Exception as exc:
                        logger.warning(
                            "[%s] Binary visualization stream failed: %s",
                            request_id, exc,
                        )

                # Coalesced heartbeat: only emit if idle > interval
                now = time.time()
                if now - last_hb >= hb_interval:
                    await websocket.send_json(
                        _event_svc.heartbeat(
                            run_id="pending",
                            goal_id=_goal_id,
                            correlation_id=correlation_id,
                        )
                    )
                    last_hb = now

        except ValidationError:
            await websocket.send_json(
                {
                    "type": "error",
                    "error": "Invalid input",
                    "error_type": "ValidationError",
                    "request_id": request_id,
                }
            )
        except Exception as e:
            logger.error(
                f"[{request_id}] WebSocket error: {str(e)}",
                extra={
                    "request_id": request_id,
                    "client_host": (
                        websocket.client.host
                        if websocket.client
                        else "unknown"
                    ),
                    "authenticated": credentials is not None,
                },
            )
            await websocket.send_json(
                {
                    "type": "error",
                    "error": "Internal server error",
                    "error_type": "InternalError",
                    "request_id": request_id,
                }
            )

    except WebSocketDisconnect:
        logger.info("[%s] WebSocket disconnected", request_id)
    except Exception:
        logger.exception(
            "[%s] WebSocket connection error", request_id,
            extra={
                "request_id": request_id,
                "client_host": (
                    websocket.client.host if websocket.client else "unknown"
                ),
                "authenticated": credentials is not None,
            },
        )
    finally:
        await _ws_conn_counter.release()
        try:
            await websocket.close()
        except Exception:
            logger.warning("WebSocket close failed", exc_info=True)


@router.post(
    "/api/uar/stream",
    responses={
        400: {"model": ErrorResponse, "description": "Validation error"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
@error_handler_middleware
async def stream_goal(
    req: RunRequest,
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """Execute a goal and stream events in real-time"""
    from uar.api.server import (
        _build_goal,
        _event_svc,
        _exec_svc,
        _MAX_CONCURRENT_SSE_PER_IP,
        _sse_connections,
        _sse_connections_lock,
        WS_HEARTBEAT_INTERVAL,
    )

    with trace_span("api.stream_goal", {"goal": req.goal[:50]}):
        # Apply rate limiting (pass parsed skill to avoid ASGI stream reuse)
        first_skill = _extract_skill_from_request_data(
            req.skills, req.execution_order
        )
        rate_limit_middleware(request, credentials, first_skill=first_skill)

        # Get user info
        user_info = auth_middleware(credentials)
        user_id = user_info["user"] if user_info else None

        # Log request
        request_id = request_logging_middleware(request, user_info)

        client_ip = request.client.host if request.client else "unknown"
        async with _sse_connections_lock:
            current_conns = _sse_connections.get(client_ip, 0)
            if current_conns >= _MAX_CONCURRENT_SSE_PER_IP:
                logger.warning(
                    "SSE rate limit exceeded for IP %s "
                    "(limit: %s)",
                    client_ip,
                    _MAX_CONCURRENT_SSE_PER_IP,
                )
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": "rate_limit_exceeded",
                        "message": (
                            "Too many concurrent streaming connections. "
                            "Please try again later."
                        ),
                    },
                )
            _sse_connections[client_ip] = current_conns + 1

        async def _release_sse_connection() -> None:
            async with _sse_connections_lock:
                if client_ip in _sse_connections:
                    _sse_connections[client_ip] = max(
                        0, _sse_connections[client_ip] - 1
                    )
                    if _sse_connections[client_ip] == 0:
                        _sse_connections.pop(client_ip, None)

        try:
            cid = getattr(request.state, "correlation_id", "")

            _sse_emit = _event_svc.emit_sse

            async def _generate():
                try:
                    goal = _build_goal(req)
                    last_hb = time.time()
                    hb_interval = WS_HEARTBEAT_INTERVAL
                    stream = _exec_svc.stream_goal(
                        goal, request_id, user_id, cid
                    )
                    while True:
                        elapsed = time.time() - last_hb
                        timeout = max(0.1, hb_interval - elapsed)
                        try:
                            event = await asyncio.wait_for(
                                stream.__anext__(), timeout=timeout
                            )
                        except StopAsyncIteration:
                            break
                        except asyncio.TimeoutError:
                            now = time.time()
                            if now - last_hb >= hb_interval:
                                yield _sse_emit(
                                    _event_svc.heartbeat(
                                        run_id="pending",
                                        goal_id="",
                                        correlation_id=cid,
                                    )
                                )
                                last_hb = now
                            continue

                        if await request.is_disconnected():
                            break
                        yield _sse_emit(event)
                        last_hb = time.time()
                except Exception as e:
                    logger.error(
                        f"[{request_id}] Stream error: {e}",
                        exc_info=True,
                    )
                    yield _sse_emit(
                        _event_svc.error(
                            run_id="unknown",
                            error_msg="Stream error",
                            request_id=request_id,
                            goal_id="",
                            correlation_id=cid,
                        )
                    )
                finally:
                    await _release_sse_connection()

            return StreamingResponse(
                _generate(), media_type="text/event-stream"
            )

        except ValidationError as e:
            logger.warning("[%s] Stream validation error: %s", request_id, e)
            # Provide user-friendly error messages based on field
            if e.field == "goal":
                user_message = (
                    "Invalid goal. Please provide a clear goal "
                    "description (3-10,000 characters)."
                )
            elif e.field == "skills":
                user_message = (
                    "Invalid skills. Please check that the skills "
                    "are available in the system."
                )
            elif e.field == "input_path":
                user_message = (
                    "Invalid input path. Please provide a valid "
                    "path within the project directory."
                )
            elif e.field == "timeout_seconds":
                user_message = (
                    "Invalid timeout. Please provide a timeout "
                    "between 1 and 300 seconds."
                )
            elif e.field == "execution_order":
                user_message = (
                    "Invalid execution order. Please check that "
                    "all skills and recipes are valid."
                )
            else:
                user_message = "Invalid input provided"

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "Validation error",
                    "message": user_message,
                    "field": e.field,
                    "request_id": request_id,
                    "suggestion": (
                        "Check your request parameters and try again. "
                        "For help, see the API documentation."
                    ),
                },
            )
        except UARError as e:
            logger.error("[%s] Stream UAR error: %s", request_id, e)
            # Provide more context for UARError types
            error_type = type(e).__name__
            suggestion = "Please check your request and try again."
            if "Path" in error_type:
                suggestion = (
                    "Please verify the file path exists and is accessible."
                )
            elif "Permission" in error_type:
                suggestion = "Please check file permissions and try again."
            elif "Timeout" in error_type:
                suggestion = (
                    "Consider increasing the timeout or reducing "
                    "the task complexity."
                )

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "UAR error",
                    "message": "Request failed",
                    "error_type": error_type,
                    "request_id": request_id,
                    "suggestion": suggestion,
                },
            )
        except Exception as e:
            await _release_sse_connection()
            logger.error(
                f"[{request_id}] Unexpected stream error: {str(e)}",
                exc_info=True,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": "Internal server error",
                    "message": (
                        "An unexpected error occurred while "
                        "processing your request"
                    ),
                    "request_id": request_id,
                    "suggestion": (
                        "Please try again later. If the problem persists, "
                        "contact support with the request ID."
                    ),
                },
            )


@router.websocket("/ws/run")
async def websocket_run(websocket: WebSocket):
    """Execute a goal and stream events via WebSocket.

    Includes heartbeat/ping-pong, batching, bounded buffers,
    and graceful error handling.
    """
    from uar.api.server import (
        _build_goal,
        _event_svc,
        _exec_svc,
        _ws_conn_counter,
        WS_HEARTBEAT_INTERVAL,
        WS_BATCH_SIZE,
        WS_BATCH_TIMEOUT,
    )

    request_id = str(uuid.uuid4())
    correlation_id = str(uuid.uuid4())
    _goal_id = ""

    def create_event(
        event_type: str,
        run_id: str,
        skill=None,
        payload=None,
        error=None,
    ):
        return _event_svc.create(
            event_type=event_type,
            run_id=run_id,
            goal_id=_goal_id,
            skill=skill,
            payload=payload,
            error=error,
            correlation_id=correlation_id,
        )

    # Enforce global WebSocket connection cap
    if not await _ws_conn_counter.acquire():
        await websocket.close(code=1008, reason="Too many connections")
        return

    try:
        await websocket.accept()
    except Exception:
        await _ws_conn_counter.release()
        raise

    heartbeat_task = None
    heartbeat_stop = asyncio.Event()
    try:
        # Parse Authorization header manually because HTTPBearer
        # depends on a Request object which is unavailable for
        # WebSocket connections in FastAPI/TestClient.
        auth_header = websocket.headers.get("authorization", "")
        credentials: Optional[HTTPAuthorizationCredentials] = None
        if auth_header.lower().startswith("bearer "):
            credentials = HTTPAuthorizationCredentials(
                scheme="Bearer",
                credentials=auth_header[7:],
            )

        # Browser WebSocket cannot send custom headers, so also accept
        # token via query parameter (e.g. /ws/run?token=...).
        if credentials is None:
            token = websocket.query_params.get("token")
            if token:
                credentials = HTTPAuthorizationCredentials(
                    scheme="Bearer",
                    credentials=token,
                )

        # Get user info for ownership tracking
        user_info = auth_middleware(credentials)
        user_str = user_info["user"] if user_info else None

        # Apply rate limiting
        client_ip = websocket.client.host if websocket.client else "unknown"
        rate_limit_key, tier = build_rate_limit_key(client_ip, credentials)
        allowed, _ = rate_limiter.is_allowed(
            rate_limit_key,
            RATE_LIMITS.get(tier, RATE_LIMITS["default"])["requests"],
            RATE_LIMITS.get(tier, RATE_LIMITS["default"])["window"],
        )
        if not allowed:
            await websocket.send_json(
                create_event(
                    "error",
                    run_id="unknown",
                    error="Rate limit exceeded",
                    payload={
                        "request_id": request_id,
                    },
                )
            )
            await websocket.close(code=1008)
            return

        websocket_timeout = max(
            1,
            int(
                os.getenv("WEBSOCKET_RECEIVE_TIMEOUT", "30").strip()
                or "30"
            ),
        )
        try:
            data = await asyncio.wait_for(
                websocket.receive_json(),
                timeout=websocket_timeout,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "[%s] WebSocket receive timeout after %ss",
                request_id,
                websocket_timeout,
            )
            await websocket.send_json(
                create_event(
                    "error",
                    run_id="unknown",
                    error="Receive timeout",
                    payload={
                        "message": "No data received within timeout",
                        "request_id": request_id,
                    },
                )
            )
            await websocket.close()
            return
        try:
            req = RunRequest(**data)
        except PydanticValidationError as e:
            logger.warning(
                "[%s] WebSocket pydantic validation error: %s",
                request_id,
                str(e),
            )
            await websocket.send_json(
                create_event(
                    "error",
                    run_id="unknown",
                    error="Validation error",
                    payload={
                        "message": "Invalid input provided",
                        "request_id": request_id,
                        "code": "VALIDATION_ERROR",
                    },
                )
            )
            await websocket.close()
            return
        goal = _build_goal(req)
        strategy = SimplePlanner().plan(goal)
        _goal_id = strategy.goal_id

        # Heartbeat: keep connection alive and detect stale clients
        heartbeat_stop = asyncio.Event()

        async def _heartbeat():
            while not heartbeat_stop.is_set():
                try:
                    await asyncio.wait_for(
                        heartbeat_stop.wait(),
                        timeout=WS_HEARTBEAT_INTERVAL,
                    )
                except asyncio.TimeoutError:
                    pass
                if heartbeat_stop.is_set():
                    break
                try:
                    await websocket.send_json(
                        create_event(
                            "heartbeat",
                            run_id="pending",
                            payload={"timestamp": time.time()},
                        )
                    )
                except Exception:
                    break

        heartbeat_task = asyncio.create_task(_heartbeat())

        batch: list[dict] = []
        batch_deadline: float | None = None

        async def _flush_batch() -> None:
            nonlocal batch, batch_deadline
            if batch:
                for ev in batch:
                    try:
                        await websocket.send_json(ev)
                    except Exception as exc:
                        logger.warning(
                            "[%s] WebSocket send_json dropped event: %s",
                            request_id, exc,
                        )
                    # Stream binary visualization data for 3D skills
                    if ev.get("type") == "skill_complete":
                        try:
                            await _stream_binary_visualization(
                                websocket, ev
                            )
                        except Exception as exc:
                            logger.warning(
                                "[%s] Batch binary visualization failed: %s",
                                request_id, exc,
                            )
                batch = []
                batch_deadline = None

        try:
            async for event in _exec_svc.stream_goal(
                goal, request_id, user_str, correlation_id,
                yield_persisted=True,
            ):
                batch.append(event)
                if batch_deadline is None:
                    batch_deadline = time.time() + WS_BATCH_TIMEOUT
                if len(batch) >= WS_BATCH_SIZE:
                    await _flush_batch()
                elif time.time() >= batch_deadline:
                    await _flush_batch()
                # Terminal events must reach client immediately
                if event.get("type") in ("complete", "error"):
                    await _flush_batch()
        finally:
            await _flush_batch()

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception:
        logger.exception("WebSocket error")
        if websocket.client_state == WebSocketState.CONNECTED:
            try:
                safe_error = "Internal server error"
                await websocket.send_json(
                    {"type": "error", "error": safe_error}
                )
            except Exception as exc:
                logger.warning(
                    "[%s] Failed to send error frame to client: %s",
                    request_id, exc,
                )
    finally:
        await _ws_conn_counter.release()
        heartbeat_stop.set()
        if heartbeat_task and not heartbeat_task.done():
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass
        try:
            await websocket.close()
        except Exception:
            logger.warning("WebSocket close failed", exc_info=True)
