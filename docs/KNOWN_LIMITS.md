# Known Limits

**Last Updated:** 2026-05-27 (v1.1.0 — commit fe0f2b4)

This file is intentionally blunt. These are real limits, not aspirational gaps.

---

## Execution

- **Not OS-isolated.** Skills run in the same process as the server. A skill that calls `os.system()` or opens arbitrary files has full OS access. The WASM sandbox gates expression evaluation only, not skill execution.
- **No network isolation.** Skills that make outbound HTTP calls (Hologram, Moltbook, etc.) are not sandboxed. Use firewall rules at the infra layer if needed.
- **Timeout + memory caps only.** Per-skill timeout (default 5s) and document size caps (100MB) are enforced. No cgroups or OS-level memory hard limits.
- **Thread pool bounded, not infinite.** `_TIMEOUT_POOL` is a fixed-size thread pool. Very long skill queues will block.

## Workflows

- **Parallel waves, not arbitrary DAGs.** The planner groups skills into sequential waves; within a wave, skills run concurrently. True arbitrary DAG scheduling (e.g., skill B depends on skill A's output) is not yet implemented.
- **Recipe nesting is one level deep in the executor.** Frontend supports nested recipes in `execution_order`, but the executor flattens recipes into a skill list. Full hierarchical tree execution is deferred.
- **No conditional branching at runtime.** Recipe conditions (`exists`, `equals`, `not_equals`) control whether a recipe runs, not mid-stream branching.

## Storage

- **SQLite run store has per-process locking only.** `SqliteRunStore` uses `threading.Lock()` + `BEGIN IMMEDIATE`. Multiple OS-level processes writing to the same `.db` file concurrently may produce lock contention. Use a single-worker deployment or Redis for multi-worker.
- **JSONL store has no compaction.** `JsonRunStore` append-only files grow indefinitely. No automated rotation.
- **No Postgres or distributed store.** SQLite is the only persistent backend.

## Security

- **Production-safe for single-tenant, firewalled deployments.** All session-1/2/3 security issues are fixed (API key auth, rate limiting, path validation, connection counters). Do **not** expose to the public internet without:
  - Setting `API_KEYS` (required in `ENVIRONMENT=production`)
  - Configuring Redis for multi-worker rate limiting
  - Placing behind a TLS-terminating reverse proxy
- **Skill code is trusted.** Skills are Python modules loaded at startup. A malicious skill module has full process access. Do not load third-party skill packages without review.
- **SSRF prevention is best-effort.** URL validation blocks obvious cases; bypasses via DNS rebinding or IPv6 are possible.

## Observability

- **Metrics are in-memory only.** Metrics reset on restart. No external metrics persistence (Prometheus push gateway, InfluxDB, etc.) is wired by default.
- **No distributed tracing.** OpenTelemetry spans are emitted locally but there is no collector configured out of the box.
- **No alerting.** Grafana dashboard is ready but alert rules and notification channels must be configured manually.

## Architecture

- **Entry point is `uar.api.server:app` (uvicorn).** The legacy `main.py` stub is no longer canonical.
- **Single-node only.** No built-in clustering, sharding, or leader election. All state (rate limiter deques, connection counters, idempotency cache) is per-process.

## Interpretation Rule

If you need guarantees outside these limits, UAR does not provide them yet. File an issue or check `docs/SLA.md` for the roadmap.
