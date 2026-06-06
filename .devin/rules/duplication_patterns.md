---
description: Common code duplication patterns in UAR and how to avoid them
---

# UAR Code Duplication Patterns

This document catalogs repetitive patterns found across the UAR codebase and
prescribes canonical ways to eliminate them.

Last counted (2026-06-06):

| Pattern | Count | Canonical Fix | Location |
| --- | --- | --- | --- |
| `meta = ctx.goal.metadata or {}` | 59 skills | Helper or re-export | `uar/skills/` |
| `from uar.core.registry import register_skill` | 46 files | Re-export module | `uar/skills/` |
| `logger = logging.getLogger(__name__)` | 143 files | Acceptable (Python std) | All modules |
| `return {"status": "failed", "error": ...}` | 45 skills | `require_field()` helper | `uar/skills/` |
| `except ImportError:` soft-dependency guard | 14 skills | `require_package()` | `uar/skills/` |
| `except httpx.HTTPError` handler | 6 files | Class-based client | `uar/objects/alm_client.py` |
| `if self.client is None:` mock fallback | 6 files | `_mock_result()` helper | `uar/core/uor_ecosystem.py` |
| Inline `compute_uor_digest` try/except | 20 files | `wrap_with_digest()` | `uar/core/skill_utils.py` |
| `@register_skill` + `@skill_guard` pair | 105 skills | Decorator ordering rule | `uar/skills/` |

---

## 1. Metadata Extraction (`meta = ctx.goal.metadata or {}`)

**Problem:** Every skill repeats the same two lines to extract metadata.

**Fix:** Add a `get_metadata()` helper to `PipelineContext` or a standalone
function in `skill_utils.py`.

```python
# BAD — repeated in 59 skills
meta = ctx.goal.metadata or {}
value = meta.get("key")

# GOOD — one-liner
meta = get_metadata(ctx)  # or ctx.get_metadata()
```

---

## 2. Skill Bootstrap Imports

**Problem:** Every skill imports the same 3-4 symbols.

**Fix:** Use a convenience re-export module.

```python
# BAD — 46 files repeat this
from uar.core.registry import register_skill
from uar.core.contracts import PipelineContext
from uar.core.skill_utils import skill_guard

# GOOD — single import
from uar.core.skill_bootstrap import (
    register_skill, PipelineContext, skill_guard
)
```

**Decision:** Not yet implemented. Evaluating whether a re-export module adds
enough value versus explicit imports.

---

## 3. Early Validation (`return {"status": "failed", ...}`)

**Problem:** Skills manually validate required metadata fields.

**Fix:** Use `require_field()` from `uar.core.skill_utils`.

```python
# BAD
meta = ctx.goal.metadata or {}
digest = meta.get("digest", "")
if not digest:
    return {"status": "failed", "error": "metadata 'digest' required"}

# GOOD
from uar.core.skill_utils import require_field
meta = ctx.goal.metadata or {}
err = require_field(meta, "digest")
if err:
    return err
digest = meta["digest"]
```

Applied to `uar/skills/uor_ecosystem_skills.py` (8 skills).

---

## 4. Soft-Dependency Guards (`except ImportError`)

**Problem:** Skills repeat `importlib.util.find_spec` checks.

**Fix:** Use `require_package()` from `uar.core.skill_utils`.

```python
# BAD
import importlib.util
if importlib.util.find_spec("scipy") is None:
    return {"status": "failed", "error": "scipy not installed"}

# GOOD
from uar.core.skill_utils import require_package
err = require_package("scipy", install_hint="pip install scipy")
if err:
    return err
```

---

## 5. HTTP Error Handling (`except httpx.HTTPError`)

**Problem:** Multiple files repeat identical httpx error handling.

**Fix:** Centralise in `uar/objects/alm_client.py` or a generic HTTP wrapper.

```python
# BAD — repeated in 6 files
try:
    response = client.get(url)
    response.raise_for_status()
    return response.json()
except httpx.HTTPError:
    logger.exception("HTTP error")
    return {"status": "error", "error": "Request failed"}

# GOOD — use ALMClient or a generic _http_get/_http_post helper
from uar.core.uor_ecosystem import _http_get, _http_post
```

---

## 6. Mock Fallback with Digest (`if self.client is None:`)

**Problem:** Mock responses when HTTP clients are missing lack digests unless
code is duplicated.

**Fix:** Use `_mock_result()` from `uar.core.uor_ecosystem`.

```python
# BAD
if client is None:
    result = {"status": "mock", "note": "httpx not installed"}
    try:
        from uar.uor.bounded_json import compute_uor_digest
        result["uor_digest"] = compute_uor_digest(result)
    except Exception:
        pass
    return result

# GOOD
from uar.core.uor_ecosystem import _mock_result
if client is None:
    return _mock_result("httpx not installed")
```

Applied to `uar/core/uor_ecosystem.py`.

---

## 7. UOR Digest Injection (`compute_uor_digest` inline)

**Problem:** ~20 files inline the same try/except/import pattern.

**Fix:** Use `wrap_with_digest()` from `uar.core.skill_utils`.

```python
# BAD
try:
    from uar.uor.bounded_json import compute_uor_digest
    result["uor_digest"] = compute_uor_digest(result)
except Exception:
    pass

# GOOD
from uar.core.skill_utils import wrap_with_digest
wrap_with_digest(result)
```

Applied to:

- `uar/skills/atomic_lang_model.py`
- `uar/skills/fpga_verify.py`
- `uar/objects/alm_client.py`
- `uar/skills/riscv_sim.py`
- `uar/skills/riscv_cycle.py`
- `uar/core/multi_run_intelligence.py`
- `uar/core/crewai_integration.py`
- `uar/core/flexible_graphrag.py`
- `uar/core/uor_ecosystem.py`

---

## 8. Decorator Ordering

**Rule:** `@register_skill` must always be the outermost decorator,
`@skill_guard` the innermost (directly above the function).

```python
# CORRECT
@register_skill("my_skill")
@with_circuit_breaker("my_skill")
@skill_guard("My skill", status="failed")
def my_skill(ctx: PipelineContext) -> Dict[str, Any]:
    ...
```

---

## Action Items

1. [ ] Create `uar.core.skill_bootstrap` re-export module (evaluate cost/benefit)
2. [ ] Add `PipelineContext.get_metadata()` convenience method
3. [ ] Apply `require_field()` to all skills with single-field validation
4. [ ] Apply `require_package()` to all soft-dependency skills
5. [ ] Migrate remaining `compute_uor_digest` inline blocks to `wrap_with_digest()`
6. [ ] Audit new skills in review for these patterns
