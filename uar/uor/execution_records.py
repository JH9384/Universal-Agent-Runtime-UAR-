"""Execution record emission as UOR objects.

Emits execution records as UOR objects for traceability, audit trails,
and reproducibility of agent workflows.
"""

import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

from .bounded_json import compute_uor_digest

logger = logging.getLogger(__name__)


@dataclass
class ExecutionRecord:
    """Execution record as a UOR object."""

    execution_id: str
    skill: str
    input_digest: str
    output_digest: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    duration_ms: Optional[float] = None
    status: str = "success"
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


class ExecutionRecordEmitter:
    """Emits execution records as UOR objects."""

    def __init__(self):
        """Initialize the execution record emitter."""
        self.records: List[ExecutionRecord] = []

    def create_record(
        self,
        execution_id: str,
        skill: str,
        input_content: Any,
        output_content: Any,
        duration_ms: Optional[float] = None,
        status: str = "success",
        metadata: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> ExecutionRecord:
        """Create an execution record.

        Args:
            execution_id: Unique execution identifier
            skill: Skill name that was executed
            input_content: Input content
            output_content: Output content
            duration_ms: Execution duration in milliseconds
            status: Execution status (success, failure, timeout)
            metadata: Additional metadata
            error: Error message if status is failure

        Returns:
            Execution record
        """
        input_digest = compute_uor_digest(input_content)
        output_digest = compute_uor_digest(output_content)

        record = ExecutionRecord(
            execution_id=execution_id,
            skill=skill,
            input_digest=input_digest,
            output_digest=output_digest,
            duration_ms=duration_ms,
            status=status,
            metadata=metadata or {},
            error=error,
        )

        self.records.append(record)
        return record

    def to_uor_envelope(self, record: ExecutionRecord) -> Dict[str, Any]:
        """Convert execution record to UOR envelope.

        Args:
            record: Execution record

        Returns:
            UOR envelope dictionary
        """
        envelope_content = {
            "execution_id": record.execution_id,
            "skill": record.skill,
            "input_digest": record.input_digest,
            "output_digest": record.output_digest,
            "timestamp": record.timestamp.isoformat(),
            "duration_ms": record.duration_ms,
            "status": record.status,
            "metadata": record.metadata,
        }

        if record.error:
            envelope_content["error"] = record.error

        envelope = {
            "digest": compute_uor_digest(envelope_content),
            "mediaType": "application/json",
            "mode": "immutable_singular",
            "schema": "uar.schema.execution_record.v1",
            "attributes": {
                "execution_id": record.execution_id,
                "skill": record.skill,
                "status": record.status,
                "timestamp": record.timestamp.isoformat(),
            },
            "links": [
                {
                    "rel": "input",
                    "target": record.input_digest,
                },
                {
                    "rel": "output",
                    "target": record.output_digest,
                },
            ],
            "content": envelope_content,
        }

        return envelope

    def build_derivation_graph(self) -> Dict[str, Any]:
        """Build derivation graph from execution records.

        Returns:
            Graph structure showing execution dependencies
        """
        nodes = []
        edges = []

        for record in self.records:
            # Add execution node
            nodes.append({
                "id": record.execution_id,
                "type": "execution",
                "skill": record.skill,
                "timestamp": record.timestamp.isoformat(),
                "status": record.status,
            })

            # Add edges from input to execution
            edges.append({
                "source": record.input_digest,
                "target": record.execution_id,
                "relation": "input_to",
            })

            # Add edges from execution to output
            edges.append({
                "source": record.execution_id,
                "target": record.output_digest,
                "relation": "execution_to",
            })

        return {
            "nodes": nodes,
            "edges": edges,
            "node_count": len(nodes),
            "edge_count": len(edges),
        }

    def query_by_skill(self, skill: str) -> List[ExecutionRecord]:
        """Query execution records by skill name.

        Args:
            skill: Skill name to filter by

        Returns:
            List of matching execution records
        """
        return [r for r in self.records if r.skill == skill]

    def query_by_status(self, status: str) -> List[ExecutionRecord]:
        """Query execution records by status.

        Args:
            status: Status to filter by

        Returns:
            List of matching execution records
        """
        return [r for r in self.records if r.status == status]

    def get_statistics(self) -> Dict[str, Any]:
        """Get execution statistics.

        Returns:
            Dictionary with execution statistics
        """
        if not self.records:
            return {
                "total_executions": 0,
                "success_count": 0,
                "failure_count": 0,
                "average_duration_ms": 0,
            }

        success_count = len([r for r in self.records if r.status == "success"])
        failure_count = len([r for r in self.records if r.status == "failure"])

        durations = [r.duration_ms for r in self.records if r.duration_ms]
        avg_duration = sum(durations) / len(durations) if durations else 0

        return {
            "total_executions": len(self.records),
            "success_count": success_count,
            "failure_count": failure_count,
            "average_duration_ms": avg_duration,
        }
