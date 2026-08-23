"""Semantic replay primitives for UAR.

This module adds a shadow-mode semantic comparison layer over ordinary replay.
It does not alter planning or execution. It compares observable decision
structure captured by runtime events: generated candidates, admissibility
states, evidence references, and commitments.

The design intentionally avoids free-form hidden reasoning. Only explicit,
machine-observable decision artifacts are represented.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple


class DecisionState(str, Enum):
    """Four-valued admissibility state."""

    ADMIT = "ADMIT"
    REJECT = "REJECT"
    DEFER = "DEFER"
    CONFLICT = "CONFLICT"


@dataclass(frozen=True, slots=True)
class CandidateDecision:
    """Observable decision state for one candidate at one semantic stage."""

    candidate_id: str
    state: DecisionState
    constraint_id: Optional[str] = None
    certificate_id: Optional[str] = None
    evidence_refs: Tuple[str, ...] = ()
    reason_code: Optional[str] = None


@dataclass(frozen=True, slots=True)
class SemanticStage:
    """One semantic decision stage.

    generated contains every candidate considered at the stage. decisions may
    omit candidates for legacy traces; absent decisions remain unclassified.
    committed is the selected candidate, if a commitment occurred.
    dependencies is a tuple of prior semantic stage ids required by this stage.
    """

    stage_id: str
    generated: frozenset[str]
    decisions: Tuple[CandidateDecision, ...] = ()
    committed: Optional[str] = None
    dependencies: Tuple[str, ...] = ()

    def partition(self) -> Dict[DecisionState, frozenset[str]]:
        out: Dict[DecisionState, Set[str]] = {
            state: set() for state in DecisionState
        }
        for decision in self.decisions:
            out[decision.state].add(decision.candidate_id)
        return {state: frozenset(values) for state, values in out.items()}

    def evidence_basis(self) -> frozenset[str]:
        refs: Set[str] = set()
        for decision in self.decisions:
            refs.update(decision.evidence_refs)
            if decision.certificate_id:
                refs.add(f"certificate:{decision.certificate_id}")
        return frozenset(refs)


@dataclass(frozen=True, slots=True)
class SemanticTrace:
    """Semantic replay trace reconstructed from observable runtime events."""

    stages: Tuple[SemanticStage, ...]
    final_result: Optional[str] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def stage_map(self) -> Dict[str, SemanticStage]:
        return {stage.stage_id: stage for stage in self.stages}


@dataclass(frozen=True, slots=True)
class SemanticDistance:
    """Vector-valued semantic distance between two traces."""

    result: float
    survivor: float
    obstruction: float
    filtration: float
    evidence: float

    @property
    def identical(self) -> bool:
        return all(
            value == 0.0
            for value in (
                self.result,
                self.survivor,
                self.obstruction,
                self.filtration,
                self.evidence,
            )
        )


@dataclass(frozen=True, slots=True)
class SemanticDivergence:
    """Earliest observable semantic divergence between two traces."""

    stage_id: Optional[str]
    category: Optional[str]
    details: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SemanticEquivalenceReport:
    """Shadow-mode semantic replay comparison artifact."""

    distance: SemanticDistance
    first_divergence: SemanticDivergence
    result_equivalent: bool
    survivor_equivalent: bool
    obstruction_equivalent: bool
    filtration_equivalent: bool
    evidence_equivalent: bool


def _jaccard_distance(left: Iterable[str], right: Iterable[str]) -> float:
    a = set(left)
    b = set(right)
    union = a | b
    if not union:
        return 0.0
    return 1.0 - (len(a & b) / len(union))


def _decision_map(stage: SemanticStage) -> Dict[str, CandidateDecision]:
    return {decision.candidate_id: decision for decision in stage.decisions}


def _survivors(stage: SemanticStage) -> frozenset[str]:
    return stage.partition()[DecisionState.ADMIT]


def _obstructions(stage: SemanticStage) -> frozenset[str]:
    return stage.partition()[DecisionState.REJECT]


def _stage_distance(left: SemanticStage, right: SemanticStage) -> float:
    """Filtration distance for aligned semantic stages."""

    generated = _jaccard_distance(left.generated, right.generated)
    admitted = _jaccard_distance(_survivors(left), _survivors(right))
    rejected = _jaccard_distance(_obstructions(left), _obstructions(right))
    deferred = _jaccard_distance(
        left.partition()[DecisionState.DEFER],
        right.partition()[DecisionState.DEFER],
    )
    conflicted = _jaccard_distance(
        left.partition()[DecisionState.CONFLICT],
        right.partition()[DecisionState.CONFLICT],
    )
    committed = 0.0 if left.committed == right.committed else 1.0
    return (
        generated
        + admitted
        + rejected
        + deferred
        + conflicted
        + committed
    ) / 6.0


def _align_stages(
    left: SemanticTrace, right: SemanticTrace
) -> List[Tuple[Optional[SemanticStage], Optional[SemanticStage]]]:
    """Align by stable stage id, preserving left order then right-only stages.

    Stable stage ids make comparison invariant to harmless wall-clock event
    reorderings when the semantic dependency stage remains the same.
    """

    left_map = left.stage_map()
    right_map = right.stage_map()
    ordered_ids: List[str] = [stage.stage_id for stage in left.stages]
    ordered_ids.extend(
        stage.stage_id
        for stage in right.stages
        if stage.stage_id not in left_map
    )
    return [(left_map.get(sid), right_map.get(sid)) for sid in ordered_ids]


def compare_semantic_traces(
    left: SemanticTrace, right: SemanticTrace
) -> SemanticEquivalenceReport:
    """Compare two semantic traces without collapsing differences to one score."""

    result_distance = 0.0 if left.final_result == right.final_result else 1.0

    left_final = _survivors(left.stages[-1]) if left.stages else frozenset()
    right_final = _survivors(right.stages[-1]) if right.stages else frozenset()
    survivor_distance = _jaccard_distance(left_final, right_final)

    left_obstructions: Set[str] = set()
    right_obstructions: Set[str] = set()
    for stage in left.stages:
        left_obstructions.update(_obstructions(stage))
    for stage in right.stages:
        right_obstructions.update(_obstructions(stage))
    obstruction_distance = _jaccard_distance(
        left_obstructions, right_obstructions
    )

    aligned = _align_stages(left, right)
    stage_distances: List[float] = []
    for left_stage, right_stage in aligned:
        if left_stage is None or right_stage is None:
            stage_distances.append(1.0)
        else:
            stage_distances.append(_stage_distance(left_stage, right_stage))
    filtration_distance = (
        sum(stage_distances) / len(stage_distances)
        if stage_distances
        else 0.0
    )

    left_evidence: Set[str] = set()
    right_evidence: Set[str] = set()
    for stage in left.stages:
        left_evidence.update(stage.evidence_basis())
    for stage in right.stages:
        right_evidence.update(stage.evidence_basis())
    evidence_distance = _jaccard_distance(left_evidence, right_evidence)

    distance = SemanticDistance(
        result=result_distance,
        survivor=survivor_distance,
        obstruction=obstruction_distance,
        filtration=filtration_distance,
        evidence=evidence_distance,
    )
    divergence = first_semantic_divergence(left, right)
    return SemanticEquivalenceReport(
        distance=distance,
        first_divergence=divergence,
        result_equivalent=result_distance == 0.0,
        survivor_equivalent=survivor_distance == 0.0,
        obstruction_equivalent=obstruction_distance == 0.0,
        filtration_equivalent=filtration_distance == 0.0,
        evidence_equivalent=evidence_distance == 0.0,
    )


def first_semantic_divergence(
    left: SemanticTrace, right: SemanticTrace
) -> SemanticDivergence:
    """Locate and classify the earliest aligned semantic difference.

    Categories:
      G-: candidate generation divergence
      A-: admissibility / obstruction divergence
      E-: evidence / certificate divergence
      K-: commitment divergence
    """

    for left_stage, right_stage in _align_stages(left, right):
        if left_stage is None or right_stage is None:
            stage = left_stage or right_stage
            return SemanticDivergence(
                stage_id=stage.stage_id if stage else None,
                category="G-",
                details={"reason": "stage_missing"},
            )

        if left_stage.generated != right_stage.generated:
            return SemanticDivergence(
                stage_id=left_stage.stage_id,
                category="G-",
                details={
                    "left_only": sorted(
                        left_stage.generated - right_stage.generated
                    ),
                    "right_only": sorted(
                        right_stage.generated - left_stage.generated
                    ),
                },
            )

        left_decisions = _decision_map(left_stage)
        right_decisions = _decision_map(right_stage)
        if set(left_decisions) != set(right_decisions):
            return SemanticDivergence(
                stage_id=left_stage.stage_id,
                category="A-",
                details={"reason": "decision_domain_changed"},
            )

        for candidate_id in sorted(left_decisions):
            l_decision = left_decisions[candidate_id]
            r_decision = right_decisions[candidate_id]
            if (
                l_decision.state != r_decision.state
                or l_decision.constraint_id != r_decision.constraint_id
                or l_decision.reason_code != r_decision.reason_code
            ):
                return SemanticDivergence(
                    stage_id=left_stage.stage_id,
                    category="A-",
                    details={
                        "candidate_id": candidate_id,
                        "left_state": l_decision.state.value,
                        "right_state": r_decision.state.value,
                    },
                )
            if (
                l_decision.certificate_id != r_decision.certificate_id
                or l_decision.evidence_refs != r_decision.evidence_refs
            ):
                return SemanticDivergence(
                    stage_id=left_stage.stage_id,
                    category="E-",
                    details={"candidate_id": candidate_id},
                )

        if left_stage.committed != right_stage.committed:
            return SemanticDivergence(
                stage_id=left_stage.stage_id,
                category="K-",
                details={
                    "left_committed": left_stage.committed,
                    "right_committed": right_stage.committed,
                },
            )

    if left.final_result != right.final_result:
        return SemanticDivergence(
            stage_id=None,
            category="K-",
            details={"reason": "final_result_changed"},
        )

    return SemanticDivergence(stage_id=None, category=None, details={})


def semantic_trace_from_events(events: Sequence[Mapping[str, Any]]) -> SemanticTrace:
    """Reconstruct a semantic trace from optional shadow-mode runtime events.

    Recognized event types:
      semantic_stage
      candidate_generated
      candidate_admitted
      candidate_rejected
      candidate_deferred
      candidate_conflicted
      evidence_acquired
      candidate_committed

    Events not in this vocabulary are ignored, allowing the semantic layer to
    coexist with existing UAR replay streams without modifying execution.
    """

    stage_order: List[str] = []
    generated: Dict[str, Set[str]] = {}
    decisions: Dict[str, Dict[str, CandidateDecision]] = {}
    committed: Dict[str, str] = {}
    dependencies: Dict[str, Tuple[str, ...]] = {}
    final_result: Optional[str] = None

    state_by_type = {
        "candidate_admitted": DecisionState.ADMIT,
        "candidate_rejected": DecisionState.REJECT,
        "candidate_deferred": DecisionState.DEFER,
        "candidate_conflicted": DecisionState.CONFLICT,
    }

    def ensure_stage(stage_id: str) -> None:
        if stage_id not in generated:
            stage_order.append(stage_id)
            generated[stage_id] = set()
            decisions[stage_id] = {}
            dependencies[stage_id] = ()

    for event in events:
        event_type = str(event.get("type", ""))
        payload = event.get("payload") or {}
        if not isinstance(payload, Mapping):
            continue

        if event_type == "complete":
            result = payload.get("semantic_result", payload.get("result_id"))
            if result is not None:
                final_result = str(result)
            continue

        if event_type not in {
            "semantic_stage",
            "candidate_generated",
            "candidate_admitted",
            "candidate_rejected",
            "candidate_deferred",
            "candidate_conflicted",
            "evidence_acquired",
            "candidate_committed",
        }:
            continue

        stage_id = str(payload.get("stage_id", "default"))
        ensure_stage(stage_id)

        if event_type == "semantic_stage":
            deps = payload.get("dependencies") or []
            dependencies[stage_id] = tuple(sorted(str(dep) for dep in deps))
            continue

        candidate_id = payload.get("candidate_id")
        if candidate_id is None:
            continue
        candidate_id = str(candidate_id)
        generated[stage_id].add(candidate_id)

        if event_type == "candidate_generated":
            continue

        if event_type in state_by_type:
            refs = payload.get("evidence_refs") or []
            decisions[stage_id][candidate_id] = CandidateDecision(
                candidate_id=candidate_id,
                state=state_by_type[event_type],
                constraint_id=(
                    str(payload["constraint_id"])
                    if payload.get("constraint_id") is not None
                    else None
                ),
                certificate_id=(
                    str(payload["certificate_id"])
                    if payload.get("certificate_id") is not None
                    else None
                ),
                evidence_refs=tuple(sorted(str(ref) for ref in refs)),
                reason_code=(
                    str(payload["reason_code"])
                    if payload.get("reason_code") is not None
                    else None
                ),
            )
            continue

        if event_type == "evidence_acquired":
            previous = decisions[stage_id].get(candidate_id)
            if previous is not None:
                refs = set(previous.evidence_refs)
                evidence_id = payload.get("evidence_id")
                if evidence_id is not None:
                    refs.add(str(evidence_id))
                decisions[stage_id][candidate_id] = CandidateDecision(
                    candidate_id=previous.candidate_id,
                    state=previous.state,
                    constraint_id=previous.constraint_id,
                    certificate_id=previous.certificate_id,
                    evidence_refs=tuple(sorted(refs)),
                    reason_code=previous.reason_code,
                )
            continue

        if event_type == "candidate_committed":
            committed[stage_id] = candidate_id

    stages = tuple(
        SemanticStage(
            stage_id=stage_id,
            generated=frozenset(generated[stage_id]),
            decisions=tuple(
                decisions[stage_id][candidate_id]
                for candidate_id in sorted(decisions[stage_id])
            ),
            committed=committed.get(stage_id),
            dependencies=dependencies.get(stage_id, ()),
        )
        for stage_id in stage_order
    )
    return SemanticTrace(stages=stages, final_result=final_result)


__all__ = [
    "CandidateDecision",
    "DecisionState",
    "SemanticDistance",
    "SemanticDivergence",
    "SemanticEquivalenceReport",
    "SemanticStage",
    "SemanticTrace",
    "compare_semantic_traces",
    "first_semantic_divergence",
    "semantic_trace_from_events",
]
