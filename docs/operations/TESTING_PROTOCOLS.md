# UAR Testing Protocols & Recommendations

## Current State

- ~1,040 tests across 14 domain directories
- CI runs on Python 3.10, 3.11, 3.12
- Makefile targets: `test`, `test-backend`, `test-alignment`, `gate`, `validate`
- pytest with custom markers (`slow`, `integration`, `security`, `api`, `store`, `skills`)
- No coverage enforcement
- No async test client
- No property-based testing
- No mutation testing
- No test parallelization
- No API contract fuzzing
- No testcontainers for integration testing

## Recommended Additions

### 1. Coverage Enforcement

Add to `pyproject.toml`:

```toml
[tool.coverage.run]
source = ["uar"]
branch = true
omit = [
    "uar/**/__init__.py",
    "tests/*",
]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "if TYPE_CHECKING:",
    "raise NotImplementedError",
    "if __name__ == .__main__.:",
]
fail_under = 70  # Start here, increase over time
show_missing = true
skip_covered = false
```

CI addition (`.github/workflows/ci.yml`):
```yaml
- name: Upload coverage
  uses: actions/upload-artifact@v4
  with:
    name: coverage-report-py${{ matrix.python-version }}
    path: htmlcov/
    retention-days: 14
```

### 2. Async Test Client (FastAPI Best Practice)

Replace synchronous `TestClient` in API tests with async `httpx.AsyncClient`:

```python
import pytest
from httpx import AsyncClient, ASGITransport
from uar.api.server import app

@pytest.fixture
async def async_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
```

Why: Prevents event loop errors with DB-backed tests.

### 3. Test Parallelization (pytest-xdist)

Add to dev dependencies:
```
pytest-xdist>=3.0
```

Makefile update:
```makefile
test-fast: $(VENV_STAMP)
	$(PYTEST) tests/ -q --tb=short -n auto
```

CI update:
```yaml
- name: Validate backend (parallel)
  run: make test-fast PYTHON=python
```

### 4. Property-Based Testing (Hypothesis)

Add to dev dependencies:
```
hypothesis>=6.0
```

Use for input validation, serialization, store operations:

```python
from hypothesis import given, strategies as st

@given(st.dictionaries(st.text(), st.text()))
def test_run_record_from_dict_accepts_any_dict(data):
    # Should not crash on any dict input
    result = run_record_from_dict(data)
    assert result is not None
```

### 5. API Contract Fuzzing (Schemathesis)

Add to dev dependencies:
```
schemathesis>=3.0
```

Add CI job:
```yaml
schemathesis-fuzz:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with:
        python-version: '3.12'
    - run: |
        python -m pip install -e ".[dev]"
        pip install schemathesis
    - run: |
        # Start server in background, fuzz for 5 minutes
        uvicorn uar.api.server:app --host 127.0.0.1 --port 8000 &
        sleep 2
        st run http://127.0.0.1:8000/openapi.json \
          --max-response-time=2000 \
          --checks all \
          --hypothesis-max-examples=500
```

### 6. Testcontainers for Integration Tests

Add to dev dependencies:
```
testcontainers>=4.0
```

Use for real PostgreSQL testing:

```python
import pytest
from testcontainers.postgres import PostgresContainer

@pytest.fixture(scope="session")
def postgres_url():
    with PostgresContainer("postgres:16-alpine") as postgres:
        yield postgres.get_connection_url()
```

### 7. Test Isolation (pytest-randomly, pytest-socket)

Add to dev dependencies:
```
pytest-randomly>=3.0
pytest-socket>=0.6
```

`pytest-randomly` shuffles test order to catch inter-test dependencies.
`pytest-socket` prevents accidental network calls in unit tests:

```toml
[tool.pytest.ini_options]
addopts = "--disable-socket --allow-unix-socket"
```

### 8. Mutation Testing (mutmut)

Add to dev dependencies:
```
mutmut>=3.0
```

Run periodically (weekly or before releases):
```bash
mutmut run
mutmut results
mutmut html
```

Target: achieve >50% mutation score over time.

### 9. Test Result Artifacts

Update CI to always upload test results:

```yaml
- name: Test with junit output
  run: |
    .venv/bin/pytest tests/ -q --tb=short \
      --junitxml=test-results.xml
  if: always()

- name: Upload Test Results
  uses: actions/upload-artifact@v4
  if: always()
  with:
    name: test-results-py${{ matrix.python-version }}
    path: test-results.xml
```

### 10. tox or nox for Multi-Env Local Testing

Create `tox.ini`:

```ini
[tox]
envlist = py310,py311,py312,lint

[testenv]
deps =
    pytest
    pytest-cov
    pytest-asyncio
    httpx
commands =
    pytest tests/ -q --tb=short --cov=uar --cov-report=term-missing

[testenv:lint]
deps = ruff
commands =
    ruff check uar/ tests/ --select=E,W,F
    ruff format uar/ tests/ --check
```

### 11. Benchmark Regression Detection

Store benchmark baseline in repo, fail CI if >10% regression:

```yaml
- name: Run benchmarks
  run: |
    .venv/bin/python tests/performance/benchmark_skills.py --json > benchmark.json
- name: Compare benchmarks
  run: |
    .venv/bin/python scripts/compare_benchmarks.py benchmark.json baseline.json
```

### 12. Slow Test Alert

Add to CI to fail if tests take too long:

```yaml
- name: Check test duration
  run: |
    .venv/bin/pytest tests/ --durations=10 -q
    # Fail if any test >30s
    .venv/bin/pytest tests/ --timeout=30
```

### 13. Dependabot for Test Dependencies

Already configured, but ensure `tests/` path is covered in dependabot.yml.

### 14. Test Documentation Standards

Enforce docstrings on all test functions via ruff rule:

```toml
[tool.ruff.lint]
select = ["D", "E", "W", "F"]

[tool.ruff.lint.pydocstyle]
convention = "google"
```

## Implementation Priority

| Priority | Protocol | Effort | Impact |
|----------|----------|--------|--------|
| P0 | Coverage enforcement | Low | High |
| P0 | Async test client | Low | High |
| P1 | pytest-xdist | Low | Medium |
| P1 | Test result artifacts | Low | Medium |
| P1 | pytest-randomly + pytest-socket | Low | Medium |
| P2 | Schemathesis fuzzing | Medium | High |
| P2 | Property-based testing | Medium | Medium |
| P2 | Testcontainers | Medium | High |
| P3 | Mutation testing | High | Medium |
| P3 | tox/nox | Medium | Low |

## Next Steps

1. Pick 2-3 P0/P1 items to implement immediately
2. Create follow-up issues for P2/P3 items
3. Set baseline coverage target (recommend 70%, increase 5% per quarter)
4. Schedule mutation testing before next major release
