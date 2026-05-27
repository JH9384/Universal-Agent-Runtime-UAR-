from uar.core.runtime_ingress import RuntimeIngressRecord


def test_runtime_ingress_record_serialization():
    record = RuntimeIngressRecord(
        ingress_id="ingress-001",
        runtime_mode="deterministic_replay",
        replay_safe=True,
        authority_validated=True,
        lineage_continuity=True,
    )

    payload = record.to_dict()

    assert payload["replay_safe"] is True
    assert payload["authority_validated"] is True
    assert payload["lineage_continuity"] is True
