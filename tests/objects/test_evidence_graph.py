from __future__ import annotations

from uar.objects.evidence import emit_evidence, emit_execution_evidence
from uar.objects.evidence_graph import (
    mission_control_evidence_projection,
    project_evidence_graph,
)
from uar.objects.service import create_record, execute_runtime, register_runtime_object
from uar.objects.store import ObjectStore


def test_evidence_graph_follows_explicit_witness_links(tmp_path):
    store = ObjectStore(str(tmp_path / "graph.sqlite3"))
    witness = create_record(
        store,
        mediaType="application/json",
        mode="immutable",
        attributes={"kind": "witness"},
        links=[],
        content={"ok": True},
    )
    evidence = emit_evidence(
        store,
        control_id="ASS-03",
        claim="witness is graph-addressable",
        subject="test.graph",
        source="pytest",
        assessment_method="Test",
        result="observed",
        witness_digests=[witness["digest"]],
    )

    graph = project_evidence_graph(store, [evidence["digest"]])
    assert graph["roots"] == [evidence["digest"]]
    assert graph["unresolved"] == []
    assert {
        (edge["source"], edge["rel"], edge["target"])
        for edge in graph["edges"]
    } == {(evidence["digest"], "witness", witness["digest"])}
    assert {node["digest"] for node in graph["nodes"]} == {
        evidence["digest"],
        witness["digest"],
    }


def test_missing_witness_is_exposed_not_hidden(tmp_path):
    store = ObjectStore(str(tmp_path / "missing.sqlite3"))
    evidence = emit_evidence(
        store,
        control_id="ASS-02",
        claim="missing evidence is visible",
        subject="test.missing",
        source="pytest",
        assessment_method="Examine",
        result="observed",
        witness_digests=["sha256:does-not-exist"],
    )

    graph = project_evidence_graph(store, [evidence["digest"]])
    assert graph["unresolved"] == ["sha256:does-not-exist"]


def test_mission_control_projection_reports_facts_not_assessment(tmp_path):
    store = ObjectStore(str(tmp_path / "mission.sqlite3"))
    input_obj = create_record(
        store,
        mediaType="application/json",
        mode="immutable",
        attributes={"kind": "input"},
        links=[],
        content=7,
    )
    register_runtime_object(store, name="identity-evidence", code="values[0]")
    execution = execute_runtime(
        store,
        runtime_name="identity-evidence",
        runtime_object=None,
        inputs=[input_obj["digest"]],
        parameters={},
    )
    emit_execution_evidence(
        store,
        execution,
        control_id="CTL-04",
        decision="ALLOW",
        authority_path=["human:root", "agent:test"],
    )
    emit_evidence(
        store,
        control_id="OPS-01",
        claim="journal observation",
        subject="uar.store",
        source="pytest",
        assessment_method="Test",
        result="replayed",
    )

    projection = mission_control_evidence_projection(store)
    assert projection["evidence_count"] == 2
    assert projection["assessment_status"] == "not-assessed"
    assert [item["control_id"] for item in projection["controls"]] == [
        "CTL-04",
        "OPS-01",
    ]
    assert "compliant" not in projection
    assert "passed" not in projection
