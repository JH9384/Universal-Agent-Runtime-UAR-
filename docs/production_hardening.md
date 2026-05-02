# UAR Production Hardening Checklist

## Runtime
- Add timeouts for each skill execution
- Add retry policy per skill
- Add circuit breaker for failing skills

## API
- Add authentication (JWT / API keys)
- Rate limiting (per IP / per user)
- Request validation + size limits

## Streaming
- Heartbeat events
- Client reconnect logic
- Backpressure handling

## Graph / Data
- Node/edge size caps
- Incremental graph updates
- Schema versioning

## Observability
- Structured logging (JSON logs)
- Metrics (latency, success rate)
- Tracing (OpenTelemetry)

## Reliability
- Persistent queue (Redis / Kafka for jobs)
- Worker model for async execution

## Security
- Path sanitization for doc_ingest
- Sandbox execution for arbitrary skills

## DevEx
- CLI improvements (replay, inspect runs)
- Debug panel in UI

## Scaling
- Separate API / worker / UI services
- Containerization (Docker)
- Horizontal scaling
