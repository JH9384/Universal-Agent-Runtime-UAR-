# Contributing to Universal Agent Runtime (UAR)

Thank you for contributing. UAR treats repository process as part of system correctness: changes should be reviewable, reproducible, and traceable to evidence.

## Development flow

1. Branch from the current `main`.
2. Keep each pull request focused on one coherent change.
3. Do not mix unrelated repository cleanup into feature or validation evidence.
4. Add or update tests for behavior changes.
5. Run the relevant validation locally before opening or updating a pull request.
6. Open a pull request; do not push intended release changes directly to `main`.

## Required validation

At minimum, changes should pass the checks relevant to the touched surface. For broad runtime or release-impacting changes, run the repository gate and the full CI matrix.

Typical commands include:

```bash
make gate
make test-coverage
make lint-py
make check-version
make validate-uor
```

Frontend work should use the lockfile for its workspace and run that workspace's tests and build.

## Pull request expectations

A pull request should state:

- what changed and why;
- what is intentionally out of scope;
- the exact validation performed;
- any known risks, follow-up work, or evidence still required;
- whether the change affects release identity, provenance, signatures, trust, or governance.

Keep validated evidence attached to a stable commit. If the head changes materially, rerun the affected validation rather than carrying forward a stale PASS claim.

## Dependency updates

Prefer grouped, workspace-scoped minor/patch updates. Major dependency migrations should be deliberate changes with explicit compatibility testing rather than incidental automated merges.

## Generated and local artifacts

Do not commit generated caches, local editor settings, runtime databases, build output, coverage output, or generated evidence packs unless a specific reviewed artifact is intentionally part of the repository contract.

## Release discipline

A release is not defined by a tag alone. `VERSION`, `pyproject.toml`, changelog/release notes, package metadata, and the release tag must agree before the repository state is described as a release.
