from __future__ import annotations

from uar.objects.evidence import EVIDENCE_SCHEMA, emit_evidence, emit_execution_evidence
from uar.objects.service import create_record, execute_runtime, register_runtime_object
from uar.objects.store import ObjectStore


def test_emit_evidence_is_immutable_and_linked(tmp_path):
    store = ObjectStore(str(tmp_path / "evidence.sqlite3"))
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
        claim="control produced evidence",
        subject="test.subject",
        source="pytest",
        assessment_method="Test",
        result="observed",
        witness_digests=[witness["digest"]],
        limitations=["test fixture only"],
    )

    persisted = store.get_object(evidence["digest"])
    assert persisted["mode"] == "immutable"
    assert persisted["attributes"]["schema"] == EVIDENCE_SCHEMA
    assert persisted["content"]["result"] == "observed"
    assert persisted["content"]["limitations"] == ["test fixture only"]
    assert persisted["links"] == [
        {"rel": "witness", "target": witness["digest"]}
    ]


def test_execution_evidence_wraps_existing_execution_without_self_assessment(tmp_path):
    store = ObjectStore(str(tmp_path / "execution.sqlite3"))
    input_obj = create_record(
        store,
        mediaType="application/json",
        mode="immutable",
        attributes={"kind": "input"},
        links=[],
        content=2,
    )
    register_runtime_object(store, name="identity-test", code="values[0]")
    execution = execute_runtime(
        store,
        runtime_name="identity-test",
        runtime_object=None,
        inputs=[input_obj["digest"]],
        parameters={},
    )

    evidence = emit_execution_evidence(
        store,
        execution,
        authority_path=["human:root", "agent:test"],
        policy_version="policy-test-v1",
        decision="ALLOW",
    )
    content = evidence["content"]
    assert content["result"] == "completed"
    assert content["decision"] == "ALLOW"
    assert content["authority_path"] == ["human:root", "agent:test"]
    assert set(link["target"] for link in evidence["links"]) == {
        execution["executionRecord"],
        execution["output"],
    }
    assert "satisfied" not in content
    assert "passed" not in content
