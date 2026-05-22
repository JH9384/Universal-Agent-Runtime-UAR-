---
description: Formal regression testing workflow for UAR
---

# UAR Regression Testing Workflow

Run this workflow before every commit or PR to ensure nothing is broken.

## Quick Run (Full Suite)

```bash
make test-regression
```

This runs: backend tests → frontend tests → frontend build → lint checks.

## Individual Stages

### 1. Backend Tests
```bash
make test-backend
```
- Runs all Python tests via pytest (`tests/`)
- Expected: ~490 passed, ~37 skipped
- Critical alignment tests included:
  - `test_skill_alignment.py` — frontend skills match backend registrations
  - `test_feature_alignment.py` — recipes, events, endpoints aligned
  - `test_tips_alignment.py` — every skill group has Tips popup content

### 2. Frontend Tests
```bash
make test-frontend
```
- Runs Vitest on `apps/web/src/components/__tests__/`
- Expected: 28 passed

### 3. Frontend Build
```bash
make build-frontend
```
- TypeScript compilation + Vite production build
- Must produce `apps/web/dist/` with no errors

### 4. Lint Checks
```bash
make lint
```
- **Python:** `ruff check uar/ tests/` (line length, unused imports, etc.)
- **TypeScript:** `tsc --noEmit` in `apps/web/`

### 5. Alignment Tests Only
```bash
make test-alignment
```
- Fast check for skill/recipe/event/tips alignment
- Run this after adding new skills, recipes, or skill groups

## Clean Start

If builds or tests act strange, purge caches:

```bash
make clean
```

This removes: `.pytest_cache`, `__pycache__`, `dist/`, `.vite/`, `.mypy_cache`, `.ruff_cache`

## CI / Pre-Commit Checklist

- [ ] `make test-backend` passes
- [ ] `make test-frontend` passes
- [ ] `make build-frontend` succeeds
- [ ] `make lint` has no new errors (existing warnings are OK)
- [ ] `make test-alignment` passes (after any skill/recipe changes)

## What Each Alignment Test Covers

| Test | Checks | Fails If |
|------|--------|----------|
| `test_skill_alignment` | Backend `register_skill` ↔ Frontend `SKILL_GROUPS` | Skill declared in one but missing in other |
| `test_feature_alignment` | Backend recipes/events ↔ Frontend `RECIPES`/handlers | Recipe or event type unknown to frontend |
| `test_tips_alignment` | `SKILL_GROUPS` entries ↔ Tips popup conditionals | Skill group has blank Tips section |

## Troubleshooting

**"dark mode selectors missing in built CSS"**
→ Ensure all `.dark ` in `*.module.css` use `:global(.dark) `

**"Tips popup section is blank"**
→ Add `{group.name === 'GroupName' && (<li>...</li>)}` block in `UARPanel.tsx`

**"skill buttons not found in tests"**
→ Tests must click the group header to expand collapsed groups before querying skills
