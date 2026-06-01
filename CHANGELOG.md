# Changelog

All notable changes to Universal Agent Runtime are documented here.

This project uses semantic versioning for release tags.

## [Unreleased] — Trust Spine Hardening Phase

Phase transition: 2026-05-31

UAR has moved from Trust Spine Construction into Trust Spine
Hardening. All six Trust Spine phases (T1–T6) are implemented.
Remaining work is performance, persistence, and correctness hardening.

### Hardening Backlog (open)

- #85 Runtime Health Query Consolidation
- #86 Burn-In Persistence Layer
- #87 Certification Engine Refactor

## [1.1.0-construction] — Trust Spine Construction Complete

Date: 2026-05-31
Test suite: 3721 passed, 1 pre-existing failure (yolo_detect)

### Added

- T1 Replay Confidence: `uar/core/replay_confidence.py` — score 0-100,
  tier, warnings, evidence report
- T2 Runtime Health: `uar/core/runtime_health.py` — component health
  scoring (execution, skills, events, streaming, pressure)
- T3 Burn-In Framework: `uar/testing/burnin/` — contracts, scenarios
  (direct + HTTP modes), `BurnInRunner`
- T4 Certification Engine: `uar/core/certification.py` — Gold/Silver/
  Experimental levels from T1/T2/T3 evidence
- T5 Mission Control: `uar/core/mission_control.py` — operator snapshot
  aggregating all Trust Spine evidence
- T6 Replay Explorer: `uar/api/routers/replay_explorer.py` — per-run
  bundle (timeline, confidence, failure path, events)
- API routers for all phases mounted under `uor_router`
- 48 Trust Spine tests across T1–T6

### Fixed (P0 hardening)

- `BurnInProxy` extracted to `burn_in.py` as single shared class;
  removed 3 duplicate inline definitions from other routers
- `_latest_report` is now written via `_set_latest_report()` under
  `threading.RLock`; concurrent `POST /burnin/run` cannot corrupt state
- Dead per-endpoint auth guards removed from runtime_health,
  certification, and mission_control routers (uor_router already
  enforces `require_auth` globally via boot.py dependency injection)
- `replay_explorer` now enforces per-run ownership check; admins bypass
- `timeline_from_record`, `score_replay`, `run_record_from_dict`
  promoted to module-level imports in `replay_explorer.py`
- 22 regression tests added in `tests/api/test_trust_spine_fixes.py`

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

## [1.1.0] - 2026-05-27

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

### Security
- Removed hardcoded API keys; now loaded from `API_KEYS` environment variable
- Fixed race condition in rate limiter with `threading.Lock()` on per-key deques
- Comprehensive path traversal protection (null bytes, hex encoding, symlink detection, cross-device hard links)
- Fixed file descriptor leaks in `doc_ingest` with context managers and generator-based streaming
- Added `MAX_TOTAL_SIZE` (100MB) and file count limits in directory traversal
- Added `validate_environment()` and `validate_docker_environment()` runtime checks
- Created `scripts/docker-entrypoint.sh` for container startup validation
- Standardized error response formats across all endpoints (`error`, `message`, `request_id`)

### Documentation
- README: comprehensive 124-skill inventory organized into 9 categories with dependency tables
- README: new Recipes, Metrics & Observability, Examples, and Security sections
- ONBOARDING: updated positioning to reflect dual agent runtime + scientific computing sandbox
- ONBOARDING: added STEM sandbox as primary quick-start path and molecular visualization example
- ARCHITECTURE: updated system overview to describe both agent runtime and scientific computing roles
- `.env.example`: documented `UAR_HIERARCHICAL_EXECUTION` env var with inline docs
- `README.md`: linked `docs/RECIPE_CONDITIONS.md` in documentation table
- `docs/USER_EXAMPLES.md`: expanded STEM section with quantum circuits, molecular structures,
  hardware emulation (RISC-V, Verilator, PlatformIO), and geometric topology (trefoil simulation)

### Test Coverage
- Expanded test suite from 535 → 572 tests
- Added unit tests for core skills: `section_sum`, `sum_review`, `math_compute`, `cipher_ops`, `dependency_map`
- Added 30 unit tests for UOR modules: `secure_keys`, `object_cache`, `rate_limiting`, `rdf_formats`

### Fixed
- `uar/uor/object_cache.py`: `prefetch()` now correctly checks cache via `get()` instead of broken `in` operator
- `uar/uor/rate_limiting.py`: fixed `min()` on empty list when `max_requests=0` in both `RateLimiter` and `SlidingWindowRateLimiter`

### Bug Fixes — Session 2 (Resource Management & Concurrency)
- `asyncio.run()` inside thread pool executor → safe fallback to new event loop when running loop is detected
- Unbounded `_coalesce_locks`/`_coalesce_results` dicts → bounded LRU with `_COALESCE_MAX_ENTRIES=256` via `collections.OrderedDict`
- Duplicate `_eval_condition` closure inside `iter_events` shadowing module-level function → removed closure
- Dead `_zero_copy_serialize()` function → removed
- `_idempotency_cache` unbounded, TTL declared but unused → `(timestamp, result)` tuples with TTL expiry + FIFO cap (`_IDEMPOTENCY_MAX=1000`), protected by `threading.Lock()`
- `_WebSocketConnectionCounter.acquire()` bypassed `self.lock` on unlimited path → all paths route through `async with self.lock`
- SSE per-IP counter double-decremented on `ValidationError`/`UARError` → generator `finally` is sole release point
- WS endpoint consumed two rate-limit tokens per connection → pre-connect result reused for post-parse check
- WS constants (`WS_HEARTBEAT_INTERVAL`, `WS_BATCH_SIZE`, `WS_BATCH_TIMEOUT`) hardcoded → read from env vars
- `RedisRateLimiter.is_allowed()` non-atomic (add then rollback race) → Lua script for atomic sliding-window check-and-increment
- Dead `_extract_skill_from_request()` stub always returning `None` → removed
- `validation.py` dangerous path patterns not anchored (`~/`, `/`) → anchored to `^~/`, `^/`
- Dead `_persist(events, ...)` method (never called) → removed

### Bug Fixes — Session 3 (Production Review)
- **C1 (Critical)** `sqlite_store.append_many`: missing `COMMIT` after `executemany` → silent data loss and exclusive lock held indefinitely
- **C2 (Critical)** `WS_HEARTBEAT_INTERVAL` had three divergent defaults (20s, 30s, 30s hardcoded) → single constant used everywhere
- **C3 (Critical)** `_WebSocketConnectionCounter.release()` not async-safe (no lock) → `async def` + `async with self.lock`; all 4 call sites updated to `await`
- **H1 (High)** `sandbox.WASMSandbox.eval_expr` stub always returned `0.0` → WASM path gated off; subprocess AST evaluator always used; `health()` reports `wasm_evaluator_active: False`
- **H2 (High)** `FastAPI(version="1.0.0")` and `"server_version": "1.1.0"` hardcoded → both use `get_uar_version()`
- **H3 (High)** SSE connection counter leaked +1 on `_build_goal` `ValidationError` → `_build_goal` moved inside `_generate()` so `finally` always runs
- **H4 (High)** `uor/rate_limiting.py` `get_object`/`put_object` TODO stubs returned `None` silently → `raise NotImplementedError`
- **H5 (High)** Blocking `httpx.get()` in async `readiness_probe` → `loop.run_in_executor(None, lambda: httpx.get(...))`
- **H6 (High)** `get_provenance` used wrong DB path; connection not closed → `SqliteRunStore()` default; `finally: run_store.close()`
- **M1 (Medium)** Backpressure semaphore `async with _backpressure_sem: yield` was no-op → explicit `acquire/try/yield/finally/release`
- **M2 (Medium)** FIFO eviction docstring mislabelled as LRU → corrected
- **M4 (Medium)** Circuit breaker endpoint accessed `cb._failures` directly → `getattr(cb, "_failures", 0)`
- **M5 (Medium)** `/api/health/dashboard` unauthenticated → `Depends(security)` added
- **M7 (Medium)** `events.pop(0)` O(n) ring buffer in execution service → `collections.deque(maxlen=...)`
- **M8 (Medium)** `_guardrail_cache` key in `ctx.data` leaked into `final_context` API response → renamed `__guardrail_cache`; `__`-prefixed keys stripped from both `complete` event emit sites
- **L4 (Low)** 13 invalid ARIA attribute values (`aria-expanded={bool}`, `aria-pressed={bool}`) in `UARPanel.tsx` → ternary string literals
- **L6 (Low)** `mmap` line decode could raise on malformed UTF-8 → `errors="replace"`
- **L7 (Low)** Dead `_PATH_DANGEROUS_RE` compiled regex list in `validation.py` → removed

### Dependencies
- `vite`: `^6.0.1` → `7.3.3` (resolves GHSA-67mh-4wv8-2f99 esbuild dev-server CORS bypass)
- `vitest`: `^1.1.0` → `3.2.4`
- `@vitest/ui`: `^1.1.0` → `3.2.4`

### Bug Fixes — Session 6 (Logging Refactor & Frontend Polish)
- **Logging refactor across 56 Python files**: converted f-string log messages to %-style lazy
  evaluation (`logger.info("User: %s", user)` instead of `logger.info(f"User: {user}")`)
  for deferred string formatting and consistent formatting style
- Replaced `logger.error(..., exc_info=True)` with `logger.exception(...)` for conciseness
  and guaranteed traceback capture in catch-all exception handlers
- **Frontend: Presets error visibility**: fetch failures for `/api/uar/docs/presets` now show
  `"Failed to load presets — check server"` in red instead of silently displaying `"(none)"`
- **Frontend: User-editable folder presets**: inline add/remove controls for custom folder
  presets persisted to `localStorage`; merged with server presets without duplication
- **Frontend: Dark mode UOR icon visibility**: added light background behind transparent
  PNG UOR icon so dark icon content is visible on dark theme
- **Python < 3.12 compatibility**: removed `follow_symlinks=False` from `Path.is_dir()`
  call (argument added in 3.12); symlink skipping already handled by preceding
  `entry.is_symlink()` check. Fixes `TypeError` in production runtime

### Bug Fixes — Session 7 (Codebase Review & Documentation Consistency)
- **Type safety**: `JsonRunStore.list_all` signature updated to accept `limit` parameter,
  matching `RunStoreProtocol`
- **Protocol completeness**: Added `purge_old_records` to `RunStoreProtocol`; implemented
  in `PostgresRunStore` with PostgreSQL `DELETE ... WHERE created_at < cutoff`
- **Skill correctness**: `llamaindex_query` fixed `result.sources` → `result.retrieved_nodes`
  to match `RAGResult` dataclass field name
- **RDF format types**: `RDFConversionResult.data` widened from `str | Graph` to include
  `Dict[str, Any]`; `_add_property_to_graph` subject type widened from `URIRef` to
  `Union[URIRef, BNode]` for nested object support
- **Hierarchical execution**: Environment variable `UAR_HIERARCHICAL_EXECUTION` now
  correctly parses `"false"`, `"0"`, `""` as falsy instead of any non-empty string
  being truthy
- **Static analysis cleanup**: Removed unused `logging`, `UARError`, `ValidationError`
  imports across `advanced_integrations.py` and `advanced_endpoints.py`
- **Frontend documentation**: Added 21 missing stub skills to `SkillGuide.tsx`
  (`airflow_dag`, `autogluon_ml`, `cern_root`, `crypto_analyze`, `dbt_transform`,
  `face_recognize`, `flaml_auto`, `kubeflow_pipe`, `mlflow_deploy`, `mlflow_track`,
  `model_reg`, `nft_mint`, `osint_recon`, `pentest_scan`, `pycaret_ml`, `security_audit`,
  `smart_contract`, `snowflake_etl`, `solana_tx`, `spark_process`, `video_analyze`)
- **Documentation tests**: New `tests/test_documentation_consistency.py` (16 tests)
  covering: skill registry ↔ frontend consistency, recipe consistency, CLI help coverage,
  frontend tips/help validation, architecture doc ↔ code consistency, event type docs,
  README/Getting Started validation

### Test Coverage
- Expanded test suite to 1128 tests (+31 from documentation consistency tests)
- All tests passing (16.56s full suite)

### Planned / Deferred
- Parallel executor expansion
- Replay timeline UI
- Dependency-aware scheduler
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
