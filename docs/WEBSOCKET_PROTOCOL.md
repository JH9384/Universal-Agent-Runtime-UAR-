# WebSocket Protocol — `/ws/run`

## Overview

The `/ws/run` endpoint provides a bidirectional WebSocket streaming interface for executing goals and receiving real-time execution events. It is the low-latency alternative to the SSE `/api/uar/stream` endpoint.

## Connection

```
GET ws://<host>/ws/run
```

The server accepts the connection immediately and expects a single JSON message containing the run request.

## Request Format

After connection, send one JSON message:

```json
{
  "goal": "string (required) — the execution objective",
  "skills": ["optional", "list", "of", "skill", "names"],
  "input_path": "optional filesystem path",
  "timeout_seconds": 30.0,
  "metadata": {},
  "execution_order": [
    {"type": "skill", "content": "doc_ingest", "id": "s1"},
    {"type": "recipe", "content": "review", "id": "r1"}
  ]
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `goal` | string | **Yes** | The execution objective. Max 500 chars. |
| `skills` | string[] | No | Explicit skill list. Ignored if `execution_order` is provided. |
| `input_path` | string | No | Filesystem path for skills that read files. |
| `timeout_seconds` | float | No | Per-skill timeout. Default: 5.0s |
| `metadata` | object | No | Opaque metadata forwarded to the executor. |
| `execution_order` | object[] | No | Unified order of skills and recipes. See [Recipe Guide](RECIPE_CONDITIONS.md). |

## Event Schema

All events share a common envelope:

```json
{
  "schema_version": "uar.event.v1",
  "type": "<event_type>",
  "run_id": "<run-id or 'pending'>",
  "goal_id": "<goal-id>",
  "skill": "<skill-name or null>",
  "timestamp": 1716141234.567,
  "correlation_id": "<8-char-id>",
  "payload": {},
  "error": null
}
```

## Event Types

### `orchestration_plan`
Sent once at the start of execution. Contains the execution graph.

```json
{
  "type": "orchestration_plan",
  "payload": {
    "graph": { "nodes": [...], "edges": [...] }
  }
}
```

### `start`
Execution has begun.

```json
{ "type": "start", "payload": {} }
```

### `skill_start`
A skill is about to execute.

```json
{ "type": "skill_start", "skill": "doc_ingest", "payload": {} }
```

### `skill_complete`
A skill finished successfully.

```json
{
  "type": "skill_complete",
  "skill": "doc_ingest",
  "payload": { "result": "..." }
}
```

### `skill_failed`
A skill failed (may be retried).

```json
{
  "type": "skill_failed",
  "skill": "doc_ingest",
  "error": "error message"
}
```

### `recipe_start`
A recipe expansion has begun.

```json
{
  "type": "recipe_start",
  "payload": {
    "recipe_id": "review",
    "instance_id": "r1",
    "max_retries": 0
  }
}
```

### `recipe_end`
A recipe expansion has completed.

```json
{
  "type": "recipe_end",
  "payload": {
    "recipe_id": "review",
    "instance_id": "r1",
    "status": "complete"
  }
}
```

### `recipe_skipped`
A recipe was skipped because its condition evaluated to false.

```json
{
  "type": "recipe_skipped",
  "payload": {
    "recipe_id": "review",
    "instance_id": "r1",
    "reason": "condition_false"
  }
}
```

### `metrics`
Emitted just before `complete`. Contains execution statistics.

```json
{
  "type": "metrics",
  "payload": {
    "total_time_sec": 2.341,
    "event_count": 12,
    "cache_hits": 1,
    "cache_misses": 2,
    "skill_times_ms": {
      "doc_ingest": 0.523,
      "ollama_generate": 1.612
    }
  }
}
```

### `complete`
Execution finished (success or partial failure).

```json
{ "type": "complete", "payload": {} }
```

### `persisted`
Run record has been saved to the store.

```json
{ "type": "persisted", "payload": {} }
```

### `heartbeat`
Sent periodically to keep the connection alive. Clients should ignore it in UI logs but use it for liveness detection.

```json
{
  "type": "heartbeat",
  "payload": { "timestamp": 1716141234.567 }
}
```

### `error`
Fatal error that terminates the stream.

```json
{ "type": "error", "error": "Event limit reached (5000)." }
```

## Server-Side Behavior

### Heartbeat
- Interval: 20 seconds (`WS_HEARTBEAT_INTERVAL`)
- Purpose: Detect stale clients, keep proxies from dropping idle connections
- Client should track `lastPong` and close/reconnect if no message received for 45s

### Batching
- Batch size: 10 events (`WS_BATCH_SIZE`)
- Batch timeout: 50ms (`WS_BATCH_TIMEOUT`)
- Events are accumulated and flushed together to reduce network round trips

### Bounded Buffers
- Event ring buffer size: 200 events (`EVENT_BUFFER_SIZE`)
- Hard event cap: 5000 events (`MAX_STREAM_EVENTS`)
- When the cap is reached, the server emits an `error` event and closes the stream

### Graceful Close
1. Server finishes iterating events
2. Remaining batch is flushed
3. Run record is persisted
4. `persisted` event is sent
5. Heartbeat task is cancelled
6. WebSocket is closed

## Client Best Practices

### Auto-Reconnect
```
Max retries: 3
Base delay: 1000ms
Backoff: exponential (1s, 2s, 4s)
```

### Connection State Machine
```
idle → connecting → open → [reconnecting] → closed → error
```

### Handling Heartbeat
- Do **not** add `heartbeat` events to the UI event log
- Track `Date.now()` on every message; if > 45s since last message, assume connection is dead and reconnect

### Error Recovery
- `error` event → display to user, stop run
- Parse errors on individual messages → log to console, continue stream
- Connection drop → trigger reconnect with backoff

## Example Session

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/run');

ws.onopen = () => {
  ws.send(JSON.stringify({ goal: 'Analyze codebase' }));
};

ws.onmessage = (msg) => {
  const event = JSON.parse(msg.data);
  if (event.type === 'heartbeat') return; // Skip UI noise
  console.log(event.type, event.skill || '');
  if (event.type === 'persisted') ws.close();
};
```

## Differences from SSE

| Feature | WebSocket | SSE |
|---------|-----------|-----|
| Transport | Bidirectional | Server → client only |
| Reconnect | Client-managed (auto-reconnect) | Browser-managed (EventSource) |
| Heartbeat | Server → client `heartbeat` events | Client-side timeout on `reader.read()` |
| Batching | Server batches up to 10 events | Line-delimited, one event per chunk |
| Headers | No custom headers possible | Standard HTTP auth headers |
| Binary data | Supported natively | Base64 in JSON |

## Constants (Server-Side)

| Constant | Value | Description |
|----------|-------|-------------|
| `WS_HEARTBEAT_INTERVAL` | 20s | Heartbeat send interval |
| `WS_BATCH_SIZE` | 10 | Max events per batch |
| `WS_BATCH_TIMEOUT` | 0.05s | Max time to wait before flushing |
| `EVENT_BUFFER_SIZE` | 200 | Ring buffer size for persistence |
| `MAX_STREAM_EVENTS` | 5000 | Hard cap before stream termination |
