"""Tests for reuse-first Evidence Pack v2 composer."""

from uar.core.evidence_pack_v2 import compose_evidence_pack_v2


def test_compose_evidence_pack_v2_includes_fleet_section():
    pack = compose_evidence_pack_v2([], generated_at=123.0)

    assert pack["title"] == "UAR Evidence Pack v2"
    assert pack["version"] == "v2"
    assert pack["generated_at"] == 123.0
    assert len(pack["sections"]) == 1
    assert pack["sections"][0]["section"] == "fleet_signal_evidence"
    assert "# UAR Evidence Pack v2" in pack["markdown"]
    assert "## Fleet Signal Evidence" in pack["markdown"]


def test_compose_evidence_pack_v2_carries_fleet_signal_markdown():
    records = [
        {
            "run_id": "run-pack-1",
            "goal_id": "g1",
            "status": "failed",
            "skills": ["echo"],
            "metadata": {"service": "svc-pack"},
            "created_at": 100.0,
        }
    ]

    pack = compose_evidence_pack_v2(records, generated_at=456.0)

    assert pack["sections"][0]["summary"]["status"] == "critical"
    assert "Service signal: svc-pack" in pack["markdown"]
    assert "Latest replay run: `run-pack-1`" in pack["markdown"]
