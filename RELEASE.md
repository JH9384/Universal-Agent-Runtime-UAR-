# Release Process

## Purpose

Defines the exact, repeatable steps required to release a version of UAR.

---

## Preconditions

All of the following must be true:

- CI is green (foundation tests pass)
- No failing streaming or replay tests
- Contract schema (uar.event.v1) unchanged or intentionally versioned
- Documentation updated (SYSTEM.md, CHANGELOG.md, RELEASE_CHECKLIST.md)
- D4C gate passes if promoting fleet/operator/recurrence/evidence work

---

## Steps

### 1. Update version

Edit the VERSION file:

```text
0.1.1
```

---

### 2. Update CHANGELOG

Add a new section under `[Unreleased]` and move it to a versioned entry.

---

### 3. Validate system

```bash
make validate
```

If the release includes D4C fleet/operator/recurrence/evidence changes, also run:

```bash
make d4c-release-gate
```

This performs focused D4C validation and writes a validation result stub.

---

### 4. Sync version

```bash
make sync-version
```

Ensures pyproject.toml matches VERSION.

---

### 5. Final consistency check

The release command enforces:

- VERSION
- pyproject.toml
- CHANGELOG.md
- RELEASE.md
- SYSTEM.md
- RELEASE_CHECKLIST.md

All must be committed and in sync.

---

### 6. Tag release

```bash
make release
```

This will:

- create annotated tag `vX.Y.Z`
- push tag to origin

---

## Versioning Rules

- Semantic versioning: MAJOR.MINOR.PATCH
- VERSION file is the source of truth
- pyproject.toml must match VERSION
- Tags must match VERSION exactly

---

## D4C Release Rule

For D4C fleet/operator/recurrence/evidence releases:

- `make d4c-release-gate` must pass,
- a local validation result or CI validation artifact must exist,
- anti-sprawl criteria in `docs/operations/D4C_RELEASE_PROMOTION_CHECKLIST.md` must remain satisfied,
- do not tag until explicit approval is given.

---

## Rollback Strategy

If release is invalid:

```bash
git tag -d vX.Y.Z
git push origin :refs/tags/vX.Y.Z
```

---

## Notes

- UI is staged and not required for runtime release
- JSONL persistence is acceptable for v1
- Conformance tests do not block foundation release

---

## Guiding Rule

"If CI is not green, it is not releasable."
