from uar.core.evidence_pack import (
    available_section,
    build_evidence_pack,
    render_evidence_pack_markdown,
    unavailable_section,
)


def test_available_section_contract():
    section = available_section("mission_control", {"timestamp": 1})

    assert section.to_dict() == {
        "available": True,
        "source": "mission_control",
        "data": {"timestamp": 1},
        "missing": [],
    }


def test_unavailable_section_contract():
    section = unavailable_section("burnin", "burn-in evidence not provided")

    assert section.to_dict() == {
        "available": False,
        "source": "burnin",
        "data": None,
        "missing": ["burn-in evidence not provided"],
    }


def test_build_evidence_pack_requires_run_id():
    try:
        build_evidence_pack(run_id="")
    except ValueError as exc:
        assert "run_id is required" in str(exc)
    else:
        raise AssertionError("Expected ValueError for empty run_id")


def test_build_evidence_pack_marks_missing_data_explicitly():
    pack = build_evidence_pack(run_id="run-1")
    data = pack.to_dict()

    assert data["run_id"] == "run-1"
    assert data["evidence_pack_id"] == "evidence-pack:run-1"
    assert data["mission_control"]["available"] is False
    assert data["replay"]["available"] is False
    assert data["burnin"]["available"] is False
    assert data["certification"]["available"] is False
    assert data["trust"]["available"] is False
    assert data["outcome"]["available"] is False
    assert data["closure"]["available"] is False
    assert data["mission_control"]["missing"]


def test_build_evidence_pack_includes_supplied_sections():
    pack = build_evidence_pack(
        run_id="run-2",
        mission_control={"runtime_health": {"score": 100}},
        replay={"replay_confidence_score": 96},
        burnin={"passed": True, "score": 99},
        certification={"level": "Gold", "score": 95},
        trust={"top_trust_score": 0.9},
        signal={"severity": "warning"},
        outcome={"outcome_type": "resolved"},
        closure={"status": "closed"},
    )
    data = pack.to_dict()

    assert data["mission_control"]["available"] is True
    assert data["mission_control"]["data"]["runtime_health"]["score"] == 100
    assert data["replay"]["data"]["replay_confidence_score"] == 96
    assert data["burnin"]["data"]["passed"] is True
    assert data["certification"]["data"]["level"] == "Gold"
    assert data["trust"]["data"]["top_trust_score"] == 0.9
    assert data["signal"]["data"]["severity"] == "warning"
    assert data["outcome"]["data"]["outcome_type"] == "resolved"
    assert data["closure"]["data"]["status"] == "closed"


def test_render_evidence_pack_markdown_includes_d5b_path():
    pack = build_evidence_pack(
        run_id="run-3",
        replay={"replay_available": True},
    )

    markdown = render_evidence_pack_markdown(pack)

    assert (
        "Signal -> Mission Control -> Replay -> Evidence Pack -> Outcome -> "
        "Trust Movement" in markdown
    )
    assert "Evidence Pack v2" in markdown
    assert "`run-3`" in markdown
    assert "| `replay` | `True` | `replay` | - |" in markdown
