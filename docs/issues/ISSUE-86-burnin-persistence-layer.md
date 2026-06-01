# Issue #86 — Burn-In Persistence Layer

Status: Open
Priority: P2
Phase: Trust Spine Hardening
Depends on: T3 (Burn-In Framework)

## Problem

`_latest_report` in `uar/api/routers/burn_in.py` is an in-process
module-level variable. It is thread-safe (RLock added in the P0
fixes) but it does not survive:

- Process restart
- Worker replacement (gunicorn pre-fork model)
- Deployment of a new container

This means Certification and Mission Control lose all burn-in evidence
after any restart, silently degrading to `Experimental` level even if
a full smoke pass was run minutes before.

## Goal

Persist the latest `BurnInReport` to the run store so it survives
restarts and is visible across workers.

## Proposed Design

Store the burn-in report as a special run record with a fixed
`run_id` sentinel:

```python
BURNIN_REPORT_RUN_ID = "__burnin_latest__"
```

`_set_latest_report(report_dict)` writes to both the in-process slot
(for same-request fast reads) and the store:

```python
def _set_latest_report(report_dict: dict, store=None) -> None:
    global _latest_report
    with _report_lock:
        _latest_report = report_dict
    if store is not None:
        store.put_metadata(BURNIN_REPORT_RUN_ID, report_dict)
```

`BurnInProxy.from_latest(store=None)` falls back to store read on
cache miss:

```python
@classmethod
def from_latest(cls, store=None):
    with _report_lock:
        report = _latest_report
    if report is None and store is not None:
        report = store.get_metadata(BURNIN_REPORT_RUN_ID)
        if report is not None:
            with _report_lock:
                global _latest_report
                _latest_report = report
    return cls(report) if report is not None else None
```

## Store Interface Extension

Add `put_metadata(key, value)` and `get_metadata(key)` to
`SqliteRunStore` backed by a `uar_metadata` table:

```sql
CREATE TABLE IF NOT EXISTS uar_metadata (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
```

## Acceptance Criteria

- `POST /api/uar/burnin/run` persists report to store
- After in-process restart (simulated by setting `_latest_report = None`),
  `BurnInProxy.from_latest(store)` recovers from the store
- New tests cover: persist, recover-on-restart, concurrent write safety
- All existing burn-in and certification tests continue to pass

## Out of Scope

- Full burn-in history / audit trail (follow-on)
- Soak and pressure burn-in classes
