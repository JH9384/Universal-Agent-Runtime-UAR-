# D4H Entity Integrity Evidence

## Purpose

D4H adds a structural integrity checker for operator metadata entities.

## What changed

- Added reusable checker module:
  - `uar/api/routers/operator/checkers/entity_integrity.py`
- Added endpoint:
  - `GET /api/uar/operator/entity-integrity`
- Added regression tests:
  - `tests/api/test_operator_entity_integrity.py`

## Integrity dimensions

The checker validates:

- Metadata discovery path
- Decodable payloads
- Missing entity identifiers
- Missing sort fields
- Duplicate identifiers
- Oldest / newest sort values

## Operational meaning

D4G made entity-retention capability visible. D4H verifies whether the retained operator entity layer is structurally trustworthy.

This is a burn-in support feature, not a new storage model.
