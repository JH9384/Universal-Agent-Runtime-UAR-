# Coverage Gap Tasks — Ready for Remediation

## Summary
- Boot module: **99%** covered — effectively complete
- Overall project: **82%** — significant room remains

---

## Task 1: Skills Modules — Highest-Impact Uncovered Code

**Priority: HIGH** — Many skills modules are at 10–30% coverage and represent
a large fraction of remaining missing statements.

### Approach
1. Run `pytest --cov` filtered to `uar/skills/` to rank by missing statements
2. Target the top 3 modules by uncovered line count
3. Focus on:
   - Error handling branches (`except` blocks, validation failures)
   - Edge-case input sanitization
   - Async/sync path bifurcations

### Modules likely needing attention (verify with fresh coverage run)
- `uar/skills/plugin.py` — plugin loading, registration
- `uar/skills/riscv_sim.py` — encoder/decoder edge cases
- `uar/skills/*.py` — any module < 50% coverage

---

## Task 2: Router Error Handling Branches

**Priority: MEDIUM**

### Approach
1. Run `pytest --cov=uar/api/routers --cov-report=term-missing`
2. Identify `except` blocks and early-exit validation failures not hit by tests
3. Write tests that send malformed payloads / trigger downstream failures

### Common patterns to cover
- `HTTPException` with non-200 status codes
- `ValidationError` from Pydantic
- `RuntimeError` / `ConnectionError` in async paths
- Missing parameters / empty collections

---

## Task 3: Core Module Error Branches

**Priority: MEDIUM**

### Modules to inspect
- `uar/core/executor.py` — coalesce lock, task failure paths
- `uar/core/safe_utils.py` — timeout edge cases already covered, but any new additions
- `uar/core/http_client.py` — retry logic, circuit breaker integration

---

## Task 4: Boot Module — Final 1% (Infrastructural)

**Priority: LOW** — Diminishing returns; requires platform-specific or signal-level testing.

### Remaining gaps (6 branch exits, 2 statements)
| Line(s) | Code | Path to cover |
|---------|------|---------------|
| `536->exit` | `sys.platform == "win32"` | Run tests on Windows CI |
| `583->588` | `fp.close()` failure in except | Mock `open()` returning object whose `close()` raises |
| `761->767` | Web health check → dashboard block | Single test with both web and dashboard `Path.exists` returning True |
| `787->798` | Dashboard health check → final log | Same as above |
| `862->860` | `_monitor` while → KeyboardInterrupt | Send SIGINT to test process |
| `867-868` | `except KeyboardInterrupt: pass` | Same as above |

**Recommendation:** Skip unless CI infrastructure changes.

---

## Verification Commands

```bash
# Full suite (baseline)
python -m pytest tests/ --timeout=120 -q --tb=line

# Skills coverage ranking
python -m pytest tests/ --cov=uar.skills --cov-report=term-missing -q

# Router coverage
python -m pytest tests/ --cov=uar.api.routers --cov-report=term-missing -q

# Core coverage
python -m pytest tests/ --cov=uar.core --cov-report=term-missing -q
```

---

## Completion Criteria
- [ ] Skills modules: top 3 modules each at ≥ 80% coverage
- [ ] Router error branches: all `except` and early-exit paths covered
- [ ] Core modules: all failure-path `except` blocks covered
- [ ] Overall project coverage ≥ 90%
