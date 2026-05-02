# Changelog

All notable changes to Universal Agent Runtime are documented here.

This project uses semantic versioning for release tags.

## [Unreleased]

### Planned / Deferred
- Parallel executor expansion
- Replay timeline UI
- Dependency-aware scheduler
- SQLite or Postgres run store
- Production UI dependency pinning and blocking build gate

## [0.1.0] - Foundation Runtime Release

### Added
- Modular Python runtime foundation
- GoalSpec, StrategySpec, PipelineContext, and RunRecord contracts
- Runtime event stream contract: uar.event.v1
- Unified executor model: iter_events as execution truth and run as collector
- Skill registry and initial skill modules: section_sum, doc_ingest, dependency_map, sum_review
- Replay utilities for event validation and RunRecord reconstruction
- Orchestration graph manifest foundation
- FastAPI API surface: POST /api/uar/run, POST /api/uar/stream, GET /api/uar/runs
- SSE streaming endpoint
- JSONL run persistence via JsonRunStore
- CLI and local execution path
- React web control surface as staged UI
- React Flow graph surface as staged visualization
- Foundation CI validation workflow
- Manual one-click GitHub validation via workflow_dispatch
- One-command local launch via Makefile
- Shell launcher: scripts/run.sh
- Production documentation: SYSTEM.md, RELEASE_CHECKLIST.md, RELEASE.md
- Release controls: VERSION, make version, make sync-version, make release
- Environment config template: .env.example

### Changed
- Legacy live-server smoke test separated from default foundation CI.
- Legacy invariant tests moved to conformance scope.
- Web UI build treated as staged, non-blocking signal during foundation release.

### Fixed
- Python package discovery constrained to uar packages.
- TypeScript project config added for staged UI build.
- Streaming persistence no longer re-executes a run.
- Streaming tests aligned with orchestration-first event stream.

### Assumptions
- UAR 0.1.0 is a single-node foundation runtime.
- JSONL storage is acceptable for local development and early audit logs.
- UI is staged and not required for core runtime release.
- uar.event.v1 is the stable event contract for this release.

## [v0.2.2] - Legacy Prototype Baseline

### Added
- Initial prototype runtime
- Legacy execution and workflow endpoints
- Early invariant tests and CI

### Notes
- This is treated as a prototype and conformance baseline, not the current foundation runtime gate.
