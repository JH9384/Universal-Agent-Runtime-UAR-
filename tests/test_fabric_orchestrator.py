from uar.distributed.fabric_orchestrator import ContinuityFabricOrchestrator


def test_fabric_orchestration_result() -> None:
    orchestrator = ContinuityFabricOrchestrator()

    result = orchestrator.orchestrate(
        source_identity="runtime-a",
        target_identity="runtime-b",
        source_replays=["r1", "r2"],
        target_replays=["r2"],
        checkpoint_ids=["c1"],
        confidence_scores=[0.9, 0.8],
        anomaly_ids=["a1"],
    )

    payload = result.to_dict()

    assert payload["sync_packet"]["source_identity"] == "runtime-a"
    assert payload["reconciliation"]["missing_from_target"] == ["r1"]
    assert payload["sync_confidence"]["confidence"] > 0.0
