# Runtime API Runbook

## Objective

Provide a concrete runtime entrypoint for operational telemetry, replay visibility, transport delivery, and live runtime interaction.

## Endpoints

### GET /health
Returns runtime health status.

### GET /telemetry
Returns runtime telemetry snapshots.

### POST /emit/{category}
Publishes a runtime telemetry event and transport envelope.

### WS /ws/runtime
Provides live runtime websocket interaction.

## Local Startup

```bash
bash scripts/run_runtime_api.sh
```

## Dependencies

Recommended runtime dependencies:

- fastapi
- uvicorn
- websockets

## Strategic Direction

This runtime API transitions UAR from runtime infrastructure into a live operational runtime surface.
