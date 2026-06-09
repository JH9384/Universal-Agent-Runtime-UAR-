# D4D Backend Lint Recovery Evidence

## Status

Backend lint recovery is closed. Full-suite validation is also green at the local evidence level.

Final local evidence confirms:

- `ruff check .` passes.
- `pytest` passes the full repository test suite.
- Working tree is clean and aligned with `origin/main`.

## Source evidence

The backend lint artifact originally reported production and intentional-regression lint findings:

- `mission_control.py`: `F821 logger undefined`
- `uar/api/routers/operator/time_machine.py`: `F821 Dict undefined` / `F821 Any undefined`
- `uar/mcp/server.py`: `F401 UARMCPError imported but unused`
- `tests/core/test_skill_guard_regression.py`: intentional bad import used to validate `skill_guard` runtime error handling

## Fixes landed

- Restored `logger = logging.getLogger(__name__)` in Mission Control.
- Added `import logging` in Mission Control.
- Imported `Any` and `Dict` in the operator Time Machine router.
- Removed the unused `UARMCPError` import from the MCP server.
- Marked the intentional bad import in the `skill_guard` regression test with line-scoped `# noqa: F401`.
- Removed unused imports from `tests/core/test_skill_guard_regression.py`.
- Added Mission Control registry fallback for environments without a pre-bound global registry.
- Restored MCP legacy helper compatibility while preserving the read-only JSON-RPC allowlist path.

## Key commits

- `f531f428b25d27e83e007d3bd6740c4b42c4ca7d` — import operator Time Machine typing aliases
- `ab2cc382b32af7bd4d35508d016bcb0b6da733b4` — remove unused MCP error import
- `f0d041e00a44508790ac5939da4940d5a45af798` — restore Mission Control logger
- `4dab2b10b7afac47933d35c67fc09e697eaa6d97` — import logging for Mission Control logger
- `0d74742fcdab9b7bb1ce144b3238da90c3053269` — mark intentional bad import in skill guard regression
- `09bfc0f5057fae6f46154e41654914263ccc33e3` — remove unused skill guard regression imports
- `847882e` — tolerate missing global skill registry in Mission Control
- `2618fed` — restore MCP legacy server compatibility

## Guardrails

- No production lint rule was weakened.
- The intentional bad import remains executable at runtime so `skill_guard` behavior is still tested.
- The lint suppression is scoped to the exact intentional import line only.
- One-shot workflow files used during recovery were removed after execution.
- MCP production JSON-RPC tool calls remain deny-by-default/read-only through the explicit MCP tool allowlist.
- Legacy MCP helper behavior remains available for tests and direct in-process compatibility callers.

## Final evidence commands

Run from repository root:

```bash
git pull --rebase origin main
ulimit -n 8192
ruff check .
pytest
git status --short --branch
```

## Accepted local evidence

```text
git pull --rebase origin main
Already up to date.

ruff check .
All checks passed!

pytest
collected 5036 items
5023 passed, 13 skipped, 36 warnings in 180.96s (0:03:00)

git status --short --branch
## main...origin/main
```

## Environment note

The final green run was executed on macOS using Python 3.14.5 with the shell file descriptor limit raised to `8192`.

The project declares `requires-python = ">=3.10,<3.13"`, so release certification should still prefer Python 3.11 or Python 3.12 for canonical CI/release evidence. However, this local D4D recovery pass is stronger than the earlier failed run because the same shell now completes the full suite with zero failures after the targeted fixes.

## Operational conclusion

Backend lint recovery and full-suite D4D local validation are closed:

```text
ruff check .                         PASS
pytest                               PASS
Full suite                           5023 passed / 13 skipped / 0 failed
Working tree                         clean, aligned with origin/main
```
