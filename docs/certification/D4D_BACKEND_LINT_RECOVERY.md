# D4D Backend Lint Recovery Evidence

## Status

Backend lint recovery is closed for the scoped production lint findings. Local evidence confirms `ruff check .` passes and the targeted `skill_guard` regression test passes.

A full-suite `pytest` run was attempted but is not accepted as D4D pass/fail evidence from the current shell because it ran under Python 3.14.5, while the project declares `requires-python = ">=3.10,<3.13"`. The run eventually aborted during pytest cleanup with `OSError: [Errno 24] Too many open files` after many unrelated failures/errors. Full-suite D4D validation should be rerun in a supported Python 3.11 or 3.12 virtual environment.

## Source evidence

The backend lint artifact reported production and intentional-regression lint findings:

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

## Key commits

- `f531f428b25d27e83e007d3bd6740c4b42c4ca7d` — import operator Time Machine typing aliases
- `ab2cc382b32af7bd4d35508d016bcb0b6da733b4` — remove unused MCP error import
- `f0d041e00a44508790ac5939da4940d5a45af798` — restore Mission Control logger
- `4dab2b10b7afac47933d35c67fc09e697eaa6d97` — import logging for Mission Control logger
- `0d74742fcdab9b7bb1ce144b3238da90c3053269` — mark intentional bad import in skill guard regression
- `09bfc0f5057fae6f46154e41654914263ccc33e3` — remove unused skill guard regression imports

## Guardrails

- No production lint rule was weakened.
- The intentional bad import remains executable at runtime so `skill_guard` behavior is still tested.
- The lint suppression is scoped to the exact intentional import line only.
- One-shot workflow files used during recovery were removed after execution.

## Final evidence commands

Run from repository root:

```bash
git pull --rebase origin main
ruff check .
pytest tests/core/test_skill_guard_regression.py
git status --short --branch
```

## Accepted local evidence

```text
git pull --rebase origin main
Already up to date.

ruff check .
All checks passed!

pytest tests/core/test_skill_guard_regression.py
collected 7 items
tests/core/test_skill_guard_regression.py ....... [100%]
7 passed, 3 warnings in 4.06s

git status --short --branch
## main...origin/main
```

## Full-suite environment note

A full `pytest` run was also attempted from the repository root. It used Python 3.14.5 and collected 5036 tests, but this environment is outside the declared project support range and eventually aborted during pytest tempdir cleanup:

```text
platform darwin -- Python 3.14.5
requires-python = >=3.10,<3.13
OSError: [Errno 24] Too many open files
```

Operational conclusion: backend lint recovery is closed. Full-suite D4D validation remains open and should be rerun under Python 3.11 or Python 3.12 with a clean virtual environment and raised file-descriptor limit if needed.
