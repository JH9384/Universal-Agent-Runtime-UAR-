---
description: WebSocket endpoints must validate auth and rate-limit BEFORE accepting
tags: [websocket, security, rate-limiting, fastapi]
---

# WebSocket Pre-Accept Security Rule

## Problem
WebSocket endpoints that call `websocket.accept()` before rate limiting or authentication are vulnerable to connection-exhaustion attacks. An attacker can open thousands of connections and hold them open indefinitely, consuming server resources before any security checks run.

## Forbidden Pattern
```python
@router.websocket("/ws/run")
async def websocket_run(websocket: WebSocket):
    if not await _ws_conn_counter.acquire():
        await websocket.close(code=1008)
        return
    await websocket.accept()  # DANGEROUS — accepted before rate limit
    
    auth_header = websocket.headers.get("authorization", "")
    # ... parse auth ...
    
    # Rate limit check happens AFTER accept — too late
    allowed, _ = rate_limiter.is_allowed(rate_limit_key, limit, window)
```

## Required Pattern
```python
@router.websocket("/ws/run")
async def websocket_run(websocket: WebSocket):
    # 1. Parse auth header FIRST (needed for rate-limit key)
    auth_header = websocket.headers.get("authorization", "")
    credentials = None
    if auth_header.lower().startswith("bearer "):
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials=auth_header[7:]
        )
    
    # 2. Rate limit BEFORE accepting
    client_ip = websocket.client.host if websocket.client else "unknown"
    rate_limit_key, tier = build_rate_limit_key(client_ip, credentials)
    allowed, _ = rate_limiter.is_allowed(rate_limit_key, limit, window)
    if not allowed:
        await websocket.close(code=1008, reason="Rate limit exceeded")
        return
    
    # 3. Connection cap check
    if not await _ws_conn_counter.acquire():
        await websocket.close(code=1008, reason="Too many connections")
        return
    
    # 4. NOW accept the connection
    await websocket.accept()
```

## Enforcement
- All WebSocket endpoints MUST parse auth headers before `websocket.accept()`.
- Rate limiting MUST occur before `websocket.accept()`.
- Request size validation MUST occur after JSON receive but before processing.

## Rationale
Once a WebSocket is accepted, server resources are allocated (event loop registration, buffers). Pre-accept validation prevents resource exhaustion attacks and ensures fairness.
