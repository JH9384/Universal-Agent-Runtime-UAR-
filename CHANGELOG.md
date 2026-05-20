# Changelog

All notable changes to Universal Agent Runtime are documented here.

This project uses semantic versioning for release tags.

## [1.0.0] - Production Runtime Release

### Added
- Additional skill modules: ollama_generate, graphrag_skills
- Document management API endpoints: upload, browse, library, presets
- Security middleware: rate limiting, auth, request logging, error handling
- Path security validation for file operations
- Production hardening: timeout handling, memory limits, error recovery
- Web UI enhancements: UARPanel component, design system tokens
- Docker production image and compose configuration
- Comprehensive test suite expansion (81 tests total)
- Type safety improvements with Mypy integration
- Code quality enforcement with Ruff linting

### Changed
- API server production-ready with middleware stack
- Executor timeout handling improved with float precision
- Memory store JSONL persistence with file locking
- Skill return types standardized to Dict[str, Any]
- Web dependencies pinned for reproducible builds

### Fixed
- Type annotation issues across codebase
- Unused import cleanup
- Inline code formatting for readability
- Mypy configuration for multi-package structure
- Node.js dependency version conflicts

### Security
- Input validation on all API endpoints
- Path traversal protection
- Safe file handling with size limits and extension checks

## [Unreleased]

### Added
- Hierarchical recipe execution with discrete unit semantics
  - Recipes execute as nested scopes with snapshot, retry, and parameter scoping
  - Frontend toggle (🔀 Nested / ➡ Flat) in UARPanel.tsx
  - Opt-in via `UAR_HIERARCHICAL_EXECUTION` env var or `use_hierarchical` metadata flag
  - Recipe-level caching: cache context mutations keyed by recipe ID and parameters
  - Recipe-level timeout overrides via `_recipe_timeout` hook
- UOR-ADDR-1 bounded shape recursion implementation
  - Typed JSON value handling with case distinction (CT-T)
  - Bounded recursion depth enforcement (CT-B) with max 1000 levels
  - JCS-RFC8785 canonicalization for standard compliance
  - Unicode NFC normalization for consistent string representation
  - Content-derived address computation with SHA-256 digests
  - Maximum array length (10,000) and object key count (10,000) limits
  - Comprehensive test suite for UOR alignment validation
  - Note: Native Python implementation aligned with UOR Foundation Rust specification
    (no official Python uor-addr package exists on PyPI)
- UOR Ecosystem Integration Layer (`uar.core.uor_ecosystem`)
  - Active integrations: UOR-ADDR canonicalization, Hologram API client,
    Moltbook forum client
  - Placeholder stubs with graceful degradation for prism-btc, Severance AI,
    Anunix (pending public API availability)
  - 13 new ecosystem skills registered: `uor_addr_canonicalize`,
    `uor_addr_resolve`, `hologram_query`, `hologram_status`, `moltbook_list`,
    `moltbook_search`, `moltbook_post`, `prism_btc_anchor`, `prism_btc_verify`,
    `severance_infer`, `severance_verify`, `anunix_health`, `anunix_run`
  - Ecosystem status skill (`uor_ecosystem_status`) for health monitoring
- Dependency compliance documentation (docs/DEPENDENCY_COMPLIANCE.md)
- Autonomi experimental status warnings in configuration and documentation

### Changed
- Environment variable renamed: `ENABLE_METRICS` → `METRICS_ENABLED` for consistency
  - Backward compatibility maintained: `ENABLE_METRICS` still supported
  - New deployments should use `METRICS_ENABLED`

### Fixed
- Race condition in rate limit headers - now uses actual state from rate limit check
- Added `graphrag_init` to available skills in web UI
- Timeout validation minimum changed from 0 to 0.1s to prevent zero timeout
- Removed redundant import in config.py

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
