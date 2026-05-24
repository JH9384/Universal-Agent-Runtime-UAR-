# UAR Test Suite

## Running Tests

```bash
# Full suite
python -m pytest tests/ -q

# With skip reporting
python -m pytest tests/ -q -rs

# Check for warnings
python -m pytest tests/ -q --tb=short 2>&1 | grep -E "^FAILED|warning|Warning"
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

| Directory            | Purpose                                      |
|----------------------|----------------------------------------------|
| `tests/`             | Unit and integration tests                   |
| `tests/conformance/` | UOR invariants and specification conformance |
