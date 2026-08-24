"""Semantic replay primitives for UAR.

Ω-7B.S is a shadow-mode comparison layer over ordinary replay. It compares
machine-observable decision structure and deliberately does not record hidden
chain-of-thought or modify planning/execution.

The semantic object is treated as a causal, partially-observed structure:

    S = (P, Γ, Q, Ω, E, K, M)

P is the causal dependency relation, Γ generated candidates, Q four-valued
admissibility, Ω obstruction/certificate structure, E evidence relations, K
commitment, and M the observation mask for generated candidates whose decision
state was not observed.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import (
    Any,
    Dict,
    Hashable,
    Iterable,
    List,
    Mapping,
    Optional,
    Sequence,
    Set,
    Tuple,
)


class DecisionState(str, Enum):
    """Four-valued admissibility state."""

    ADMIT = "ADMIT"
    REJECT = "REJECT"
    DEFER = "DEFER"
    CONFLICT = "CONFLICT"

    @property
    def support_obstruction(self) -> Tuple[int, int]:
        return {
            DecisionState.DEFER: (0, 0),
            DecisionState.ADMIT: (1, 0),
            DecisionState.REJECT: (0, 1),
            DecisionState.CONFLICT: (1, 1),
        }[self]

    @property
    def dual(self) -> "DecisionState":
        return {
            DecisionState.ADMIT: DecisionState.REJECT,
            DecisionState.REJECT: DecisionState.ADMIT,
            DecisionState.DEFER: DecisionState.DEFER,
            DecisionState.CONFLICT: DecisionState.CONFLICT,
        }[self]


class ComparisonOutcome(str, Enum):
    """Certifier outcome under partial observation."""

    EQUIVALENT = "EQUIVALENT"
    DIFFERENT = "DIFFERENT"
    INDETERMINATE = "INDETERMINATE"


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

    Generated candidates without a decision are UNOBSERVED. This is observer
    ignorance and is deliberately distinct from runtime DEFER.
    """

    stage_id: str
    generated: frozenset[str]
    decisions: Tuple[CandidateDecision, ...] = ()
    committed: Optional[str] = None
    dependencies: Tuple[str, ...] = ()
    terminal: bool = False

    def decision_map(self) -> Dict[str, CandidateDecision]:
        return {decision.candidate_id: decision for decision in self.decisions}

    def partition(self) -> Dict[DecisionState, frozenset[str]]:
        out: Dict[DecisionState, Set[str]] = {
            state: set() for state in DecisionState
        }
        for decision in self.decisions:
            out[decision.state].add(decision.candidate_id)
        return {state: frozenset(values) for state, values in out.items()}

    def unobserved(self) -> frozenset[str]:
        return frozenset(self.generated - set(self.decision_map()))

    def observation_complete(self) -> bool:
        return not self.unobserved()

    def evidence_basis(self) -> frozenset[str]:
        """Legacy/global evidence inventory. Prefer relational_evidence()."""
        refs: Set[str] = set()
        for decision in self.decisions:
            refs.update(decision.evidence_refs)
            if decision.certificate_id:
                refs.add(f"certificate:{decision.certificate_id}")
        return frozenset(refs)

    def relational_evidence(self) -> frozenset[Tuple[str, str, str]]:
        out: Set[Tuple[str, str, str]] = set()
        for decision in self.decisions:
            for ref in decision.evidence_refs:
                out.add(
                    (self.stage_id, decision.candidate_id, f"evidence:{ref}")
                )
            if decision.certificate_id:
                out.add(
                    (
                        self.stage_id,
                        decision.candidate_id,
                        f"certificate:{decision.certificate_id}",
                    )
                )
        return frozenset(out)

    def relational_obstruction(
        self,
    ) -> frozenset[Tuple[str, str, str, str, str]]:
        out: Set[Tuple[str, str, str, str, str]] = set()
        for decision in self.decisions:
            if decision.state not in {
                DecisionState.REJECT,
                DecisionState.CONFLICT,
            }:
                continue
            out.add(
                (
                    self.stage_id,
                    decision.candidate_id,
                    decision.state.value,
                    decision.constraint_id or "",
                    decision.certificate_id or decision.reason_code or "",
                )
            )
        return frozenset(out)

    def decision_relation(self) -> frozenset[Tuple[str, str, str, str]]:
        return frozenset(
            (
                decision.candidate_id,
                decision.state.value,
                decision.constraint_id or "",
                decision.reason_code or "",
            )
            for decision in self.decisions
        )


@dataclass(frozen=True, slots=True)
class SemanticTrace:
    """Semantic replay trace reconstructed from observable runtime events."""

    stages: Tuple[SemanticStage, ...]
    final_result: Optional[str] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def stage_map(self) -> Dict[str, SemanticStage]:
        return {stage.stage_id: stage for stage in self.stages}

    def dependency_edges(self) -> frozenset[Tuple[str, str]]:
        return frozenset(
            (dependency, stage.stage_id)
            for stage in self.stages
            for dependency in stage.dependencies
        )

    def causal_closure(self) -> frozenset[Tuple[str, str]]:
        """Return canonical reachability relation for declared dependencies."""
        ids = set(self.stage_map())
        reach: Dict[str, Set[str]] = {stage_id: set() for stage_id in ids}
        for src, dst in self.dependency_edges():
            if src in ids and dst in ids:
                reach[src].add(dst)
        changed = True
        while changed:
            changed = False
            for src in ids:
                expanded = set(reach[src])
                for mid in tuple(reach[src]):
                    expanded.update(reach.get(mid, set()))
                if expanded != reach[src]:
                    reach[src] = expanded
                    changed = True
        return frozenset(
            (src, dst) for src, values in reach.items() for dst in values
        )

    def causal_predecessors(self, stage_id: str) -> frozenset[str]:
        return frozenset(
            src for src, dst in self.causal_closure() if dst == stage_id
        )

    def terminal_stage_ids(self) -> frozenset[str]:
        explicit = frozenset(
            stage.stage_id for stage in self.stages if stage.terminal
        )
        if explicit:
            return explicit
        ids = set(self.stage_map())
        non_sinks = {src for src, _ in self.causal_closure() if src in ids}
        return frozenset(ids - non_sinks)

    def terminal_survivors(self) -> frozenset[str]:
        stage_map = self.stage_map()
        survivors: Set[str] = set()
        for stage_id in self.terminal_stage_ids():
            stage = stage_map.get(stage_id)
            if stage is not None:
                survivors.update(stage.partition()[DecisionState.ADMIT])
        return frozenset(survivors)

    def observation_complete(self) -> bool:
        return all(stage.observation_complete() for stage in self.stages)

    def observation_ratio(self) -> float:
        generated = sum(len(stage.generated) for stage in self.stages)
        if generated == 0:
            return 1.0
        observed = sum(
            len(set(stage.decision_map()) & set(stage.generated))
            for stage in self.stages
        )
        return observed / generated


@dataclass(frozen=True, slots=True)
class TraceValidationIssue:
    stage_id: Optional[str]
    code: str
    details: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SemanticDistance:
    """Vector-valued observed semantic divergence."""

    result: float
    survivor: float
    obstruction: float
    filtration: float
    evidence: float
    causal: float = 0.0
    max_filtration: float = 0.0

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
                self.causal,
            )
        )


@dataclass(frozen=True, slots=True)
class SemanticDivergence:
    stage_id: Optional[str]
    category: Optional[str]
    details: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SemanticEquivalenceReport:
    distance: SemanticDistance
    first_divergence: SemanticDivergence
    result_equivalent: bool
    survivor_equivalent: bool
    obstruction_equivalent: bool
    filtration_equivalent: bool
    evidence_equivalent: bool
    causal_equivalent: bool
    observation_complete: bool
    outcome: ComparisonOutcome
    minimal_divergences: Tuple[SemanticDivergence, ...] = ()


@dataclass(frozen=True, slots=True)
class IntegrityReport:
    checked_certificates: int
    missing_certificates: Tuple[Tuple[str, str], ...]
    invalid_certificates: Tuple[Tuple[str, str, str], ...]

    @property
    def verified(self) -> bool:
        return not self.missing_certificates and not self.invalid_certificates


def _jaccard_distance(
    left: Iterable[Hashable], right: Iterable[Hashable]
) -> float:
    a = set(left)
    b = set(right)
    union = a | b
    if not union:
        return 0.0
    return 1.0 - (len(a & b) / len(union))


def validate_semantic_trace(
    trace: SemanticTrace,
) -> Tuple[TraceValidationIssue, ...]:
    """Validate conservation, identity, and causal integrity constraints."""
    issues: List[TraceValidationIssue] = []
    stage_ids = [stage.stage_id for stage in trace.stages]
    duplicates = sorted(
        {stage_id for stage_id in stage_ids if stage_ids.count(stage_id) > 1}
    )
    for stage_id in duplicates:
        issues.append(TraceValidationIssue(stage_id, "duplicate_stage_id"))

    known = set(stage_ids)
    for stage in trace.stages:
        decision_ids = [decision.candidate_id for decision in stage.decisions]
        duplicate_decisions = sorted(
            {
                candidate_id
                for candidate_id in decision_ids
                if decision_ids.count(candidate_id) > 1
            }
        )
        if duplicate_decisions:
            issues.append(
                TraceValidationIssue(
                    stage.stage_id,
                    "duplicate_candidate_decision",
                    {"candidate_ids": duplicate_decisions},
                )
            )
        outside = sorted(set(decision_ids) - set(stage.generated))
        if outside:
            issues.append(
                TraceValidationIssue(
                    stage.stage_id,
                    "decision_without_generation",
                    {"candidate_ids": outside},
                )
            )
        if (
            stage.committed is not None
            and stage.committed not in stage.generated
        ):
            issues.append(
                TraceValidationIssue(
                    stage.stage_id,
                    "commit_without_generation",
                    {"candidate_id": stage.committed},
                )
            )
        unknown_dependencies = sorted(set(stage.dependencies) - known)
        if unknown_dependencies:
            issues.append(
                TraceValidationIssue(
                    stage.stage_id,
                    "unknown_dependency",
                    {"stage_ids": unknown_dependencies},
                )
            )
        if stage.stage_id in stage.dependencies:
            issues.append(
                TraceValidationIssue(stage.stage_id, "self_dependency")
            )

    closure = trace.causal_closure()
    for stage_id in known:
        if (stage_id, stage_id) in closure:
            issues.append(TraceValidationIssue(stage_id, "causal_cycle"))

    return tuple(issues)


def _align_stages(
    left: SemanticTrace, right: SemanticTrace
) -> List[Tuple[str, Optional[SemanticStage], Optional[SemanticStage]]]:
    left_map = left.stage_map()
    right_map = right.stage_map()
    ordered_ids = sorted(set(left_map) | set(right_map))
    return [
        (stage_id, left_map.get(stage_id), right_map.get(stage_id))
        for stage_id in ordered_ids
    ]


def _stage_distance(left: SemanticStage, right: SemanticStage) -> float:
    generated = _jaccard_distance(left.generated, right.generated)
    decisions = _jaccard_distance(
        left.decision_relation(), right.decision_relation()
    )
    committed = 0.0 if left.committed == right.committed else 1.0
    return (generated + decisions + committed) / 3.0


def _evidence_relation(
    trace: SemanticTrace,
) -> frozenset[Tuple[str, str, str]]:
    return frozenset(
        item for stage in trace.stages for item in stage.relational_evidence()
    )


def _obstruction_relation(
    trace: SemanticTrace,
) -> frozenset[Tuple[str, str, str, str, str]]:
    return frozenset(
        item
        for stage in trace.stages
        for item in stage.relational_obstruction()
    )


def _causal_signature(trace: SemanticTrace) -> frozenset[Tuple[str, str, str]]:
    tagged: Set[Tuple[str, str, str]] = {
        ("edge", src, dst) for src, dst in trace.causal_closure()
    }
    tagged.update(
        ("terminal", stage_id, "") for stage_id in trace.terminal_stage_ids()
    )
    return frozenset(tagged)


def _stage_divergence(
    stage_id: str,
    left: Optional[SemanticStage],
    right: Optional[SemanticStage],
    left_trace: SemanticTrace,
    right_trace: SemanticTrace,
) -> Optional[SemanticDivergence]:
    if left is None or right is None:
        return SemanticDivergence(stage_id, "G-", {"reason": "stage_missing"})

    left_predecessors = left_trace.causal_predecessors(stage_id)
    right_predecessors = right_trace.causal_predecessors(stage_id)
    if left_predecessors != right_predecessors:
        return SemanticDivergence(
            stage_id,
            "P-",
            {
                "left_predecessors": sorted(left_predecessors),
                "right_predecessors": sorted(right_predecessors),
            },
        )

    if left.generated != right.generated:
        return SemanticDivergence(
            stage_id,
            "G-",
            {
                "left_only": sorted(left.generated - right.generated),
                "right_only": sorted(right.generated - left.generated),
            },
        )

    left_decisions = left.decision_map()
    right_decisions = right.decision_map()
    if set(left_decisions) != set(right_decisions):
        return SemanticDivergence(
            stage_id,
            "O-",
            {
                "reason": "observation_domain_changed",
                "left_unobserved": sorted(left.unobserved()),
                "right_unobserved": sorted(right.unobserved()),
            },
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
                stage_id,
                "A-",
                {
                    "candidate_id": candidate_id,
                    "left_state": l_decision.state.value,
                    "right_state": r_decision.state.value,
                    "left_constraint": l_decision.constraint_id,
                    "right_constraint": r_decision.constraint_id,
                    "left_reason": l_decision.reason_code,
                    "right_reason": r_decision.reason_code,
                },
            )
        if l_decision.certificate_id != r_decision.certificate_id or tuple(
            sorted(l_decision.evidence_refs)
        ) != tuple(sorted(r_decision.evidence_refs)):
            return SemanticDivergence(
                stage_id,
                "E-",
                {"candidate_id": candidate_id},
            )

    if left.committed != right.committed:
        return SemanticDivergence(
            stage_id,
            "K-",
            {
                "left_committed": left.committed,
                "right_committed": right.committed,
            },
        )

    left_terminal = stage_id in left_trace.terminal_stage_ids()
    right_terminal = stage_id in right_trace.terminal_stage_ids()
    if left_terminal != right_terminal:
        return SemanticDivergence(
            stage_id,
            "P-",
            {"reason": "terminal_semantics_changed"},
        )

    return None


def _minimal_divergences(
    left: SemanticTrace, right: SemanticTrace
) -> Tuple[SemanticDivergence, ...]:
    divergences: Dict[str, SemanticDivergence] = {}
    for stage_id, left_stage, right_stage in _align_stages(left, right):
        divergence = _stage_divergence(
            stage_id, left_stage, right_stage, left, right
        )
        if divergence is not None:
            divergences[stage_id] = divergence

    if not divergences:
        if left.final_result != right.final_result:
            return (
                SemanticDivergence(
                    None,
                    "K-",
                    {"reason": "final_result_changed"},
                ),
            )
        return ()

    causal = set(left.causal_closure()) | set(right.causal_closure())
    minimal: List[SemanticDivergence] = []
    for stage_id, divergence in divergences.items():
        has_divergent_predecessor = any(
            predecessor in divergences and (predecessor, stage_id) in causal
            for predecessor in divergences
        )
        if not has_divergent_predecessor:
            minimal.append(divergence)
    return tuple(
        sorted(
            minimal,
            key=lambda item: (item.stage_id or "", item.category or ""),
        )
    )


def _has_observed_hard_difference(
    left: SemanticTrace, right: SemanticTrace
) -> bool:
    """Return true when shared observations directly witness a difference.

    An earlier observation-domain defect still controls earliest-divergence
    localization, but it must not hide a later decision that both traces
    actually observed and reported differently.
    """

    for _, left_stage, right_stage in _align_stages(left, right):
        if left_stage is None or right_stage is None:
            return True
        if left_stage.generated != right_stage.generated:
            return True
        left_decisions = left_stage.decision_map()
        right_decisions = right_stage.decision_map()
        for candidate_id in set(left_decisions) & set(right_decisions):
            if left_decisions[candidate_id] != right_decisions[candidate_id]:
                return True
        if left_stage.committed != right_stage.committed and (
            left_stage.committed is not None
            and right_stage.committed is not None
        ):
            return True
        if (
            left_stage.stage_id in left.terminal_stage_ids()
        ) != (
            right_stage.stage_id in right.terminal_stage_ids()
        ):
            return True
    return False


def compare_semantic_traces(
    left: SemanticTrace, right: SemanticTrace
) -> SemanticEquivalenceReport:
    """Compare two semantic traces as causal, partially-observed structures."""

    result_distance = 0.0 if left.final_result == right.final_result else 1.0
    survivor_distance = _jaccard_distance(
        left.terminal_survivors(), right.terminal_survivors()
    )
    obstruction_distance = _jaccard_distance(
        _obstruction_relation(left), _obstruction_relation(right)
    )
    evidence_distance = _jaccard_distance(
        _evidence_relation(left), _evidence_relation(right)
    )
    causal_distance = _jaccard_distance(
        _causal_signature(left), _causal_signature(right)
    )

    stage_distances: List[float] = []
    for _, left_stage, right_stage in _align_stages(left, right):
        if left_stage is None or right_stage is None:
            stage_distances.append(1.0)
        else:
            stage_distances.append(_stage_distance(left_stage, right_stage))
    filtration_distance = (
        sum(stage_distances) / len(stage_distances) if stage_distances else 0.0
    )
    max_filtration = max(stage_distances, default=0.0)

    distance = SemanticDistance(
        result=result_distance,
        survivor=survivor_distance,
        obstruction=obstruction_distance,
        filtration=filtration_distance,
        evidence=evidence_distance,
        causal=causal_distance,
        max_filtration=max_filtration,
    )

    minimal = _minimal_divergences(left, right)
    first = minimal[0] if minimal else SemanticDivergence(None, None, {})
    observation_complete = (
        left.observation_complete() and right.observation_complete()
    )

    hard_categories = {
        div.category for div in minimal if div.category not in {None, "O-"}
    }
    if (
        hard_categories
        or result_distance > 0.0
        or causal_distance > 0.0
        or _has_observed_hard_difference(left, right)
    ):
        outcome = ComparisonOutcome.DIFFERENT
    elif not observation_complete or any(
        div.category == "O-" for div in minimal
    ):
        outcome = ComparisonOutcome.INDETERMINATE
    else:
        outcome = ComparisonOutcome.EQUIVALENT

    return SemanticEquivalenceReport(
        distance=distance,
        first_divergence=first,
        result_equivalent=result_distance == 0.0,
        survivor_equivalent=survivor_distance == 0.0,
        obstruction_equivalent=obstruction_distance == 0.0,
        filtration_equivalent=filtration_distance == 0.0,
        evidence_equivalent=evidence_distance == 0.0,
        causal_equivalent=causal_distance == 0.0,
        observation_complete=observation_complete,
        outcome=outcome,
        minimal_divergences=minimal,
    )


def first_semantic_divergence(
    left: SemanticTrace, right: SemanticTrace
) -> SemanticDivergence:
    return compare_semantic_traces(left, right).first_divergence


def _canonical_trace_payload(trace: SemanticTrace) -> Mapping[str, Any]:
    terminal_ids = trace.terminal_stage_ids()
    stage_payload = []
    for stage in sorted(trace.stages, key=lambda item: item.stage_id):
        stage_payload.append(
            {
                "stage_id": stage.stage_id,
                "generated": sorted(stage.generated),
                "decisions": [
                    {
                        "candidate_id": decision.candidate_id,
                        "state": decision.state.value,
                        "constraint_id": decision.constraint_id,
                        "certificate_id": decision.certificate_id,
                        "evidence_refs": sorted(decision.evidence_refs),
                        "reason_code": decision.reason_code,
                    }
                    for decision in sorted(
                        stage.decisions, key=lambda item: item.candidate_id
                    )
                ],
                "committed": stage.committed,
                "causal_predecessors": sorted(
                    trace.causal_predecessors(stage.stage_id)
                ),
                "terminal": stage.stage_id in terminal_ids,
                "unobserved": sorted(stage.unobserved()),
            }
        )
    return {
        "schema": "uar.semantic.v1",
        "stages": stage_payload,
        "causal_closure": [
            list(edge) for edge in sorted(trace.causal_closure())
        ],
        "terminal_stage_ids": sorted(terminal_ids),
        "final_result": trace.final_result,
    }


def semantic_trace_hash(trace: SemanticTrace) -> str:
    payload = json.dumps(
        _canonical_trace_payload(trace),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


SEMANTIC_EVENT_TYPES = frozenset(
    {
        "semantic_stage",
        "candidate_generated",
        "candidate_admitted",
        "candidate_rejected",
        "candidate_deferred",
        "candidate_conflicted",
        "evidence_acquired",
        "candidate_committed",
        "semantic_result",
    }
)


def project_nonsemantic_events(
    events: Sequence[Mapping[str, Any]],
) -> Tuple[Mapping[str, Any], ...]:
    """Erase shadow events for deterministic non-interference checks."""
    return tuple(
        event
        for event in events
        if str(event.get("type", "")) not in SEMANTIC_EVENT_TYPES
    )


def projected_event_hash(events: Sequence[Mapping[str, Any]]) -> str:
    payload = json.dumps(
        project_nonsemantic_events(events),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def semantic_trace_from_events(
    events: Sequence[Mapping[str, Any]],
) -> SemanticTrace:
    """Reconstruct semantics independent of harmless event arrival order."""

    stage_order: List[str] = []
    generated: Dict[str, Set[str]] = {}
    decisions: Dict[str, Dict[str, CandidateDecision]] = {}
    evidence: Dict[Tuple[str, str], Set[str]] = {}
    committed: Dict[str, str] = {}
    dependencies: Dict[str, Tuple[str, ...]] = {}
    terminal: Dict[str, bool] = {}
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
            terminal[stage_id] = False

    for event in events:
        event_type = str(event.get("type", ""))
        payload = event.get("payload") or {}
        if not isinstance(payload, Mapping):
            continue

        if event_type in {"complete", "semantic_result"}:
            result = payload.get("semantic_result", payload.get("result_id"))
            if result is not None:
                final_result = str(result)
            continue

        if event_type not in SEMANTIC_EVENT_TYPES:
            continue

        stage_id = str(payload.get("stage_id", "default"))
        ensure_stage(stage_id)

        if event_type == "semantic_stage":
            deps = payload.get("dependencies") or []
            dependencies[stage_id] = tuple(sorted(str(dep) for dep in deps))
            terminal[stage_id] = bool(payload.get("terminal", False))
            continue

        candidate_id = payload.get("candidate_id")
        if candidate_id is None:
            continue
        candidate_id = str(candidate_id)
        generated[stage_id].add(candidate_id)
        key = (stage_id, candidate_id)

        if event_type == "candidate_generated":
            continue

        if event_type == "evidence_acquired":
            evidence_id = payload.get("evidence_id")
            if evidence_id is not None:
                evidence.setdefault(key, set()).add(str(evidence_id))
            continue

        if event_type in state_by_type:
            refs = set(
                str(ref) for ref in (payload.get("evidence_refs") or [])
            )
            refs.update(evidence.get(key, set()))
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
                evidence_refs=tuple(sorted(refs)),
                reason_code=(
                    str(payload["reason_code"])
                    if payload.get("reason_code") is not None
                    else None
                ),
            )
            continue

        if event_type == "candidate_committed":
            committed[stage_id] = candidate_id

    for (stage_id, candidate_id), refs in evidence.items():
        previous = decisions.get(stage_id, {}).get(candidate_id)
        if previous is not None:
            merged = set(previous.evidence_refs) | refs
            decisions[stage_id][candidate_id] = CandidateDecision(
                candidate_id=previous.candidate_id,
                state=previous.state,
                constraint_id=previous.constraint_id,
                certificate_id=previous.certificate_id,
                evidence_refs=tuple(sorted(merged)),
                reason_code=previous.reason_code,
            )

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
            terminal=terminal.get(stage_id, False),
        )
        for stage_id in stage_order
    )
    return SemanticTrace(stages=stages, final_result=final_result)


def verify_decision_certificates(
    trace: SemanticTrace,
    verified_certificates: Mapping[str, bool],
) -> IntegrityReport:
    """Compare reported certificate claims to independent verification."""

    missing: List[Tuple[str, str]] = []
    invalid: List[Tuple[str, str, str]] = []
    checked = 0
    for stage in trace.stages:
        for decision in stage.decisions:
            if decision.certificate_id is None:
                continue
            checked += 1
            if decision.certificate_id not in verified_certificates:
                missing.append((stage.stage_id, decision.candidate_id))
            elif not verified_certificates[decision.certificate_id]:
                invalid.append(
                    (
                        stage.stage_id,
                        decision.candidate_id,
                        decision.certificate_id,
                    )
                )
    return IntegrityReport(
        checked_certificates=checked,
        missing_certificates=tuple(sorted(missing)),
        invalid_certificates=tuple(sorted(invalid)),
    )


def local_diamond_report(
    left_linearization: SemanticTrace,
    right_linearization: SemanticTrace,
) -> SemanticEquivalenceReport:
    """Compare declared scheduler linearizations of one local diamond."""
    return compare_semantic_traces(left_linearization, right_linearization)


def directed_transition_risk(
    before: DecisionState,
    after: DecisionState,
    risk_matrix: Mapping[Tuple[DecisionState, DecisionState], float],
) -> float:
    """Return policy-provided directional risk separately from distance."""
    return float(risk_matrix.get((before, after), 0.0))


def remap_semantic_trace(
    trace: SemanticTrace,
    *,
    stage_ids: Mapping[str, str] = {},
    candidate_ids: Mapping[str, str] = {},
    evidence_ids: Mapping[str, str] = {},
) -> SemanticTrace:
    """Apply an explicitly declared semantic isomorphism/gauge mapping.

    Automatic graph isomorphism inference is intentionally out of scope. This
    helper lets callers compare traces after supplying a trusted ID mapping.
    """

    def map_stage(value: str) -> str:
        return stage_ids.get(value, value)

    def map_candidate(value: str) -> str:
        return candidate_ids.get(value, value)

    stages: List[SemanticStage] = []
    for stage in trace.stages:
        stages.append(
            SemanticStage(
                stage_id=map_stage(stage.stage_id),
                generated=frozenset(
                    map_candidate(value) for value in stage.generated
                ),
                decisions=tuple(
                    CandidateDecision(
                        candidate_id=map_candidate(decision.candidate_id),
                        state=decision.state,
                        constraint_id=decision.constraint_id,
                        certificate_id=decision.certificate_id,
                        evidence_refs=tuple(
                            sorted(
                                evidence_ids.get(ref, ref)
                                for ref in decision.evidence_refs
                            )
                        ),
                        reason_code=decision.reason_code,
                    )
                    for decision in stage.decisions
                ),
                committed=(
                    map_candidate(stage.committed)
                    if stage.committed is not None
                    else None
                ),
                dependencies=tuple(
                    sorted(map_stage(dep) for dep in stage.dependencies)
                ),
                terminal=stage.terminal,
            )
        )
    return SemanticTrace(
        stages=tuple(stages),
        final_result=(
            map_candidate(trace.final_result)
            if trace.final_result is not None
            else None
        ),
        metadata=trace.metadata,
    )


__all__ = [
    "CandidateDecision",
    "ComparisonOutcome",
    "DecisionState",
    "IntegrityReport",
    "SemanticDistance",
    "SemanticDivergence",
    "SemanticEquivalenceReport",
    "SemanticStage",
    "SemanticTrace",
    "TraceValidationIssue",
    "compare_semantic_traces",
    "directed_transition_risk",
    "first_semantic_divergence",
    "local_diamond_report",
    "project_nonsemantic_events",
    "projected_event_hash",
    "remap_semantic_trace",
    "semantic_trace_from_events",
    "semantic_trace_hash",
    "validate_semantic_trace",
    "verify_decision_certificates",
]
