# UAR Test Suite

## Running Tests

```bash
# Full suite
python -m pytest tests/ -q

# With skip reporting
python -m pytest tests/ -q -rs

# Check for warnings
python -m pytest tests/ -q --tb=short 2>&1 | grep -E "^FAILED|warning|Warning"

# Filter by concern
python -m pytest tests/unit/ -q          # Fast unit tests only
python -m pytest tests/api/ -q           # API endpoint tests
python -m pytest tests/security/ -q        # Security tests
python -m pytest tests/store/ -q           # Persistence layer
python -m pytest tests/integration/ -q    # Cross-system integration
```

## Mocking Missing Dependencies

Tests that verify graceful degradation when optional dependencies are absent **must not skip** based on the current environment. Instead, mock `importlib.util.find_spec` to simulate the dependency being missing.

### Pattern

```python
from unittest import mock

def test_skill_missing_dependency():
    def _mock_find_spec(name):
        if name == "some_package":
            return None
        return __import__("importlib.util").find_spec(name)

    with mock.patch("importlib.util.find_spec", _mock_find_spec):
        ctx = _ctx({"operation": "example"})
        result = some_skill.skill_fn(ctx)
        assert result["status"] == "failed"
        assert "some_package" in result["error"].lower()
```

### Why

- **Determinism:** Tests always run the same code path regardless of what is installed.
- **CI hygiene:** The CI environment can run the full suite without installing every extra.
- **Coverage accuracy:** Missing-dep paths are tracked by coverage tools.

### Applicable Modules

This pattern is used for skills that wrap optional packages:

- `matplotlib` / `numpy` → `math_plot`
- `sympy` → `math_compute`, `relativity`
- `pycryptodome` (`Crypto`) → `cipher_ops`
- `biopython` → `bio_compute`
- `cryptography` → `doc_ingest`
- `rdflib` → `uor_bridge`

## Test Organization

| Directory            | Purpose                                           | Count |
|----------------------|---------------------------------------------------|-------|
| `tests/unit/`        | Pure unit tests (no external deps, fast)            | 15    |
| `tests/api/`         | FastAPI endpoint tests (uses TestClient)          | 11    |
| `tests/security/`    | Auth, sandbox, path traversal, guardrails           | 8     |
| `tests/store/`       | Persistence layer (JSON, SQLite, Postgres)          | 4     |
| `tests/integration/` | Cross-system integration (UOR, CrewAI, GraphRAG)     | 14    |
| `tests/skills/`      | Individual skill function tests                    | 4     |
| `tests/recipes/`     | Recipe system tests                                | 2     |
| `tests/runtime/`     | Execution runtime (executor, planner, replay)       | 12    |
| `tests/cli/`         | Command-line interface tests                       | 1     |
| `tests/performance/` | Benchmarks, smoke tests, performance tuning         | 5     |
| `tests/docs/`        | Documentation consistency and alignment            | 5     |
| `tests/regression/`  | Review regression tracking                         | 1     |
| `tests/conformance/` | UOR invariants and specification conformance         | 1     |
| `tests/hardening/`   | Operational resilience (oscillation, starvation)     | 5     |

## Pytest Markers

Custom markers are registered in `conftest.py` for cross-cutting filtering:

| Marker        | Use                                   |
|---------------|---------------------------------------|
| `slow`        | Tests that take >1s or involve I/O  |
| `integration` | External systems or cross-module     |
| `security`    | Vulnerabilities, auth, sandbox       |
| `api`         | FastAPI endpoint tests               |
| `store`       | Persistence layer tests              |
| `skills`      | Individual skill functions             |

Example:
```bash
python -m pytest tests/ -m "not slow" -q
python -m pytest tests/ -m security -q
```
