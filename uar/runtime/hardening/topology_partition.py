"""Topology partition simulation primitives for UAR burn-in."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PartitionNode:
    node_id: str
    partition_id: str


@dataclass(frozen=True)
class PartitionResult:
    partitions: tuple[str, ...]
    isolated_nodes: tuple[str, ...]

    def healthy(self) -> bool:
        return len(self.partitions) <= 1 and not self.isolated_nodes


def analyze(nodes: tuple[PartitionNode, ...]) -> PartitionResult:
    partitions = sorted({node.partition_id for node in nodes})

    isolated = tuple(
        node.node_id
        for node in nodes
        if sum(1 for peer in nodes if peer.partition_id == node.partition_id) == 1
    )

    return PartitionResult(tuple(partitions), isolated)
