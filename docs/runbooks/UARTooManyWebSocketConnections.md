# Runbook: UARTooManyWebSocketConnections

## Alert

`UARTooManyWebSocketConnections` — Active WebSocket connections > 900 (limit: 1,000).

## Impact

- Approaching connection cap. New clients will be rejected with 1008.
- Potential memory pressure from accumulated connection state.

## Diagnosis Steps

1. Check `uar_websocket_connections` gauge trend — sudden spike or gradual growth?
2. Check for leaked connections: clients that disconnected without proper close handshake.
3. Review `_WebSocketConnectionCounter.release()` paths for exceptions that skip cleanup.

## Mitigation

- Increase `WEBSOCKET_MAX_CONNECTIONS` env var if infrastructure supports it.
- Restart uar-api to force-close stale connections (last resort).
- Add connection timeout: `WEBSOCKET_RECEIVE_TIMEOUT`.

## Escalation

- P2 if connections exceed 1,000 and new users cannot connect.
