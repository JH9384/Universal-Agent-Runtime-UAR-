# UAR Roundout Plan

## Goal
Round out the Universal Agent Runtime before new feature expansion. The target is a trustworthy baseline that can run, fail safely, validate itself, and support production hardening.

## Phase 1 — Safety Baseline
- Restrict document ingestion to an allowed workspace root.
- Prevent path traversal outside that root.
- Add explicit tests for allowed and blocked ingestion paths.

## Phase 2 — Execution Control
- Add skill timeout support to the executor.
- Preserve failure details in RunRecord.
- Add tests for missing skills and timeout/failure behavior.

## Phase 3 — Observability
- Add structured runtime logging.
- Emit skill_start, skill_complete, and skill_failed events in non-streaming execution as well.
- Preserve events in memory records.

## Phase 4 — Replay / Inspection
- Add CLI support to list and replay stored runs.
- Keep replay read-only and deterministic.

## Phase 5 — Validation Gate
- CI must run Python tests and web build.
- Add API, streaming, graph integrity, failure-path, and security tests.

## Phase 6 — Production Backlog
- Authentication and rate limiting.
- Request size limits.
- Async worker queue.
- OpenTelemetry tracing.
- Docker/container deployment.
- UI timeline/debugger panel.
