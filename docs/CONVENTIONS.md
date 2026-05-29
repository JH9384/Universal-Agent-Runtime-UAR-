# UAR Engineering Conventions

Codified patterns from recurring bug-bounty findings.

## Logging

- **Always use parameterized logging.**  Never use f-strings or `.format()`
  inside `logger.info("...")` calls.
  - Bad: `logger.info(f"Value is {x}")`
  - Good: `logger.info("Value is %s", x)`
- **Never swallow exceptions silently.**  Every `except Exception:` block
  must either `raise`, call `logger.exception(...)`, or use
  `uar.core.safe_utils.swallow(...)`.

## Timeouts and Deadlines

- **Always use `time.monotonic()` for timeout arithmetic.**  `time.time()` is
  affected by NTP jumps and system clock changes.
  - Bad: `deadline = time.time() + timeout`
  - Good: `deadline = time.monotonic() + timeout`
- Prefer `MonotonicDeadline` from `uar.core.safe_utils` for new code.

## Resource Management

- **Every opened resource must have a matching `close()` in `finally`.**
  - Files, sockets, DB connections, `PipelineContext`, gzip handles, etc.
- Use context managers (`with`) where possible.
- For generators that acquire locks, add `finally:` to release even on
  `GeneratorExit`.

## getattr Safety

- **Never rely on `getattr(obj, "id", "")` for data-model fields.**  The
  fallback `""` silently corrupts data when the real field name is `run_id`,
  `goal_id`, etc.
- Prefer `safe_getattr(..., "run_id", "id", default="")` from
  `uar.core.safe_utils`, which warns when a fallback is hit.
- Even better: use dataclass fields or Pydantic models with explicit
  attribute access.

## Caching

- **Never put `@functools.lru_cache` on a bound method.**  Each instance
  creates a new cache that leaks memory via the `self` reference.
- Solutions:
  1. Move the cached logic to a module-level function (preferred).
  2. Use `class_lru_cache` from `uar.core.safe_utils` for pure methods
     that do not depend on mutable instance state.

## Lock Management

- **Always pair `acquire()` with `release()` in `try/finally`.**
- Prefer the context-manager form: `with lock:`.
- For re-entrant locks, track depth (see `TrackedLock` in
  `uar.core.safe_utils`).

## CSS / Frontend Theming

- **Never hardcode hex colors in component CSS.**  Use tokens from
  `apps/web/src/design-system/tokens.css`.
  - Bad: `background: #fff;`
  - Good: `background: var(--color-surface);`
- Dark mode is handled automatically by the `.dark` class on `<html>`
  toggling token values.  Do **not** add per-class `:global(.dark)`
  overrides.

## Pre-commit Guardrails

The local pre-commit hook (`scripts/check_no_fstring_logging.sh`) enforces
four of the highest-frequency bug categories:

1. f-string inside logger call
2. bare `except Exception:` without logging
3. `time.time()` used for timeout/deadline
4. `getattr(..., "id", ...)` fallback pattern

Run `pre-commit run --all-files` before pushing.
