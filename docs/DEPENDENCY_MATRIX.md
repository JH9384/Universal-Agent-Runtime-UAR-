# Dependency Matrix

## Runtime Dependencies

| Dependency | Purpose |
|---|---|
| FastAPI | runtime API |
| uvicorn | runtime server |
| sqlite3 | persistence |

## Optional Dependencies

| Dependency | Purpose |
|---|---|
| Docker | runtime deployment |
| docker-compose | runtime orchestration |

## Future Dependencies

| Dependency | Purpose |
|---|---|
| PostgreSQL | production persistence |
| React | runtime UI |
| WebSocket frontend client | operator interaction |

## Rule

All new runtime dependencies must be documented before becoming authoritative runtime requirements.
