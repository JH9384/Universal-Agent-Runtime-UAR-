# Operator Entity Retention

UAR stores lightweight operator workflow entities through metadata keys.

Snapshot retention is bounded to the latest 168 captures when metadata listing and deletion are available.

Operators can inspect metadata entity health through:

    GET /api/uar/operator/entity-health

The response reports backend metadata capabilities and per-entity discovery / retention status.
