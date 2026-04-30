# Known Limits

This file is intentionally blunt.

## Execution
- Not OS-isolated
- No network/file restrictions
- Timeout + memory caps only

## Workflows
- Linear only
- No branching or DAG

## Storage
- SQLite only
- No concurrency guarantees

## Security
- Not production safe
- Do not expose publicly

## Architecture
- `main.py` is still canonical
- Modules are incomplete

## Interpretation Rule

If you need guarantees outside these limits, UAR does not provide them yet.
