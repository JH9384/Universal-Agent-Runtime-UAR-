---
description: GitHub Actions workflow and composite action authoring rules for UAR
tags: [ci, cd, github-actions, workflow]
globs: [".github/workflows/*.yml", ".github/actions/**/*.yml"]
---

# UAR GitHub Actions Rules

## 1. Python Environment Consistency

- **ALWAYS** use `make install PYTHON=python` to create the `.venv` virtual environment.
- **NEVER** install directly with system `python -m pip install` in jobs that also use `.venv/bin/python` or `.venv/bin/pytest`.
- If a job only needs system Python (e.g., optional-dependency-smoke where there is no Makefile target), document why in a comment.

## 2. API Payload Drift Guard

- Composite actions that call UAR API endpoints **MUST** use the current `RunRequest` schema.
- When the API model changes (e.g., `recipe_id` → `execution_order`), update **all** actions that construct payloads.
- Prefer reading the canonical model from `uar/api/models.py` rather than hardcoding field names.

## 3. Multi-Line `GITHUB_OUTPUT` Syntax

- **NEVER** use `echo "key=$(cat file)" >> "$GITHUB_OUTPUT"` for values that may contain newlines.
- **ALWAYS** use the heredoc syntax:

  ```bash
  {
    echo "key<<EOF"
    cat file
    echo "EOF"
  } >> "$GITHUB_OUTPUT"
  ```

## 4. Version Hardcoding Ban

- **NEVER** hardcode application/tool version strings (e.g., `cosign-release: 'v2.2.0'`) in workflow steps.
- **ALWAYS** either:
  - Omit the version to use the action's default/latest, **or**
  - Read from the `VERSION` file: `VERSION=$(cat VERSION)`.
- **Exception**: GitHub Actions reference versions (e.g., `actions/checkout@v4`, `actions/setup-python@v5`) are standard ecosystem conventions and are allowed.

## 4b. Dead Branch Reference Cleanup

- **NEVER** list feature branches in `branches:` arrays once they are merged or abandoned.
- Periodically audit workflow `on.push.branches` and `on.pull_request.branches` lists.
- If a branch no longer exists in the repo (`git branch -a | grep <branch>` returns nothing), remove it immediately.

## 5. Artifact Upload Resilience

- Upload-artifact steps **SHOULD** include `if: always()` when they capture diagnostic output from steps that may fail.
- Verify the artifact path is created by an upstream step before the upload runs.

## 6. Workflow Trigger Boundaries

- `pull_request:` triggers **SHOULD** specify `branches:` to avoid running on every draft PR to every branch.
- Default to `branches: [main]` unless there is an explicit reason to run on all branches.

## 7. Dependabot Coverage Completeness

- Every `package.json` in `apps/*` **MUST** have a corresponding `dependabot.yml` entry.
- When adding a new frontend app, add its npm ecosystem to `.github/dependabot.yml` before the first merge.

## 8. Node.js Frontend App Inclusion

- When a new frontend app is added under `apps/`, add a corresponding test job to:
  - `.github/workflows/ci.yml`
  - `.github/workflows/test.yml`
- Include the new job in the `needs:` array of the `sign-uor-artifacts` job (or any gate job).

## 9. YAML Validation Gate

- Before committing workflow changes, validate all YAML files:

  ```bash
  python3 -c "import yaml; [yaml.safe_load(open(f)) for f in [
      '.github/workflows/ci.yml',
      '.github/workflows/test.yml',
      '.github/workflows/burnin-hardening.yml',
      '.github/actions/run-recipe/action.yml',
      '.github/dependabot.yml',
  ]]"
  ```

## 10. PR Template Category Completeness

- When adding a new CI/CD feature, ensure the PR template's category list in `.github/pull_request_template.md` includes `CI/CD`.
