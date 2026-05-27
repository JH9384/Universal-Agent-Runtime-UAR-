from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from uar.distributed.checkpoint_exchange import CheckpointExchange
from uar.distributed.replay_reconciliation import ReplayReconciler, ReplayReconciliationResult
from uar.distributed.replay_sync import ReplaySyncPacket, ReplaySynchronizer
from uar.distributed.sync_confidence import SyncConfidence, SyncConfidenceEstimator


@dataclass(slots=True)
class FabricOrchestrationResult:
    sync_packet: ReplaySyncPacket
    checkpoint_exchange: CheckpointExchange
    reconciliation: ReplayReconciliationResult
    sync_confidence: SyncConfidence
    anomaly_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {
            "sync_packet": self.sync_packet.to_dict(),
            "checkpoint_exchange": self.checkpoint_exchange.to_dict(),
            "reconciliation": self.reconciliation.to_dict(),
            "sync_confidence": self.sync_confidence.to_dict(),
            "anomaly_ids": list(self.anomaly_ids),
        }


class ContinuityFabricOrchestrator:
    def __init__(self) -> None:
        self.synchronizer = ReplaySynchronizer()
        self.reconciler = ReplayReconciler()
        self.confidence = SyncConfidenceEstimator()

    def orchestrate(
        self,
        source_identity: str,
        target_identity: str,
        source_replays: List[str],
        target_replays: List[str],
        checkpoint_ids: List[str],
        confidence_scores: List[float],
        anomaly_ids: List[str] | None = None,
    ) -> FabricOrchestrationResult:
        sync_packet = self.synchronizer.build_packet(
            source_identity=source_identity,
            target_identity=target_identity,
            replay_ids=source_replays,
            checkpoint_ids=checkpoint_ids,
        )
        checkpoint_exchange = CheckpointExchange(
            exchange_id=f"exchange-{source_identity}-{target_identity}",
            checkpoint_ids=list(checkpoint_ids),
        )
        reconciliation = self.reconciler.reconcile(
            source_identity=source_identity,
            target_identity=target_identity,
            source_replays=source_replays,
            target_replays=target_replays,
        )
        sync_confidence = self.confidence.estimate(
            identity_id=target_identity,
            scores=confidence_scores,
        )

        return FabricOrchestrationResult(
            sync_packet=sync_packet,
            checkpoint_exchange=checkpoint_exchange,
            reconciliation=reconciliation,
            sync_confidence=sync_confidence,
            anomaly_ids=list(anomaly_ids or []),
        )
