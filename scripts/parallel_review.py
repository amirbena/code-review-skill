#!/usr/bin/env python3
"""Test-only reference for portable parallel-review planning and aggregation.

Mirrors shared/policies/parallel-review.md and
skills/github-pr-review/policies/parallel-review.md.
Not runtime logic, not packaged.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Sequence

import decision_semantics as ds


class ParallelCapability(Enum):
    """What the current runtime can actually do."""

    NONE = "none"                      # sequential only
    SUBAGENTS = "subagents"            # ordinary isolated sub-agents
    AGENT_TEAMS = "agent_teams"        # Claude Code Agent Teams (experimental)
    CONCURRENT_AGENTS = "concurrent_agents"  # Codex-style concurrent agents


class ReviewDimension(Enum):
    SCOPE_REQUIREMENTS = "scope_requirements"
    ARCHITECTURE_INVARIANTS = "architecture_invariants"
    CORRECTNESS_REGRESSION = "correctness_regression"
    TESTS_CONFIG = "tests_config"
    EXISTING_REVIEW_RECONCILIATION = "existing_review_reconciliation"


@dataclass(frozen=True)
class ReviewSignals:
    """Resolved review-shape inputs to the execution-policy decision."""

    changed_file_count: int = 0
    material_dimensions: tuple[ReviewDimension, ...] = ()
    dimensions_are_independent: bool = False
    expected_latency_reduction: bool = False
    shared_context_normalized: bool = False
    repository_instructions_resolved: bool = False


@dataclass(frozen=True)
class ReviewPlan:
    parallel: bool
    dimensions: tuple[ReviewDimension, ...]
    reason: str


def _independent_material_dimensions(
    signals: ReviewSignals,
    requested: tuple[ReviewDimension, ...],
) -> tuple[ReviewDimension, ...]:
    material = set(signals.material_dimensions)
    return tuple(dimension for dimension in requested if dimension in material)


def plan_review_execution(
    signals: ReviewSignals,
    capability: ParallelCapability,
    dimensions: Sequence[ReviewDimension] = tuple(ReviewDimension),
) -> ReviewPlan:
    """Select parallelism only for independent work with a latency benefit."""
    dims = tuple(dimensions)
    if capability is ParallelCapability.NONE:
        return ReviewPlan(False, dims, "runtime exposes no reliable parallel capability")
    if not signals.shared_context_normalized or not signals.repository_instructions_resolved:
        return ReviewPlan(False, dims, "shared review context is not fully resolved")
    material = _independent_material_dimensions(signals, dims)
    if len(material) < 2 or not signals.dimensions_are_independent:
        return ReviewPlan(False, dims, "fewer than two materially independent dimensions")
    if not signals.expected_latency_reduction:
        return ReviewPlan(False, dims, "parallel overhead is not expected to reduce latency")
    return ReviewPlan(True, dims, f"independent dimensions justify {capability.value}")


@dataclass(frozen=True)
class WorkerInput:
    """The bounded, normalized input every worker gets — identical for all
    workers except `dimension` and `applicable_policies`."""

    review_target: str
    review_context: str
    repository_context_location: str
    repository_snapshot_identity: str
    repository_instruction_context_identity: str
    existing_review_evidence: str
    dimension: ReviewDimension
    applicable_policies: tuple[str, ...]

    def shared_key(self) -> tuple[str, str, str, str, str, str]:
        """The parts that must be identical across a run's workers."""
        return (
            self.review_target,
            self.review_context,
            self.repository_context_location,
            self.repository_snapshot_identity,
            self.repository_instruction_context_identity,
            self.existing_review_evidence,
        )


def build_worker_inputs(
    *,
    review_target: str,
    review_context: str,
    repository_context_location: str,
    repository_snapshot_identity: str,
    repository_instruction_context_identity: str,
    existing_review_evidence: str,
    dimensions: Sequence[ReviewDimension],
    policies_by_dimension: dict[ReviewDimension, tuple[str, ...]],
) -> list[WorkerInput]:
    return [
        WorkerInput(
            review_target=review_target,
            review_context=review_context,
            repository_context_location=repository_context_location,
            repository_snapshot_identity=repository_snapshot_identity,
            repository_instruction_context_identity=repository_instruction_context_identity,
            existing_review_evidence=existing_review_evidence,
            dimension=dim,
            applicable_policies=policies_by_dimension.get(dim, ()),
        )
        for dim in dimensions
    ]


@dataclass(frozen=True)
class WorkerFinding:
    """One candidate finding from a worker. Portable across runtimes — no
    provider conversation metadata."""

    location: str
    finding: str
    evidence: str
    impact: str
    candidate_severity: ds.Severity
    dimension: ReviewDimension
    related_prior_context: Optional[str] = None

    def identity(self) -> tuple[str, str]:
        """Normalized dedup key: same location + same normalized claim."""
        return (self.location.strip().lower(), _normalize(self.finding))


class WorkerStatus(Enum):
    OK = "ok"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    MALFORMED = "malformed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class WorkerResult:
    dimension: ReviewDimension
    status: WorkerStatus
    findings: tuple[WorkerFinding, ...] = ()
    required: bool = True  # a required dimension cannot be silently skipped


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


class AggregateOutcome(Enum):
    GRADED = "graded"          # a real REVIEW CLEAN / CHANGES REQUIRED
    INCOMPLETE = "incomplete"  # a required dimension is missing -> ungraded


@dataclass(frozen=True)
class AggregatedReview:
    outcome: AggregateOutcome
    decision: Optional[ds.Decision]
    findings: tuple[ds.Finding, ...]
    missing_dimensions: tuple[ReviewDimension, ...]
    recovered_dimensions: tuple[ReviewDimension, ...]


def aggregate(
    results: Sequence[WorkerResult],
    *,
    parent_can_recover: bool = True,
) -> AggregatedReview:
    """The single reconciliation stage. Worker completion order never affects
    the result; workers never derive the final decision."""
    ordered = sorted(results, key=lambda r: r.dimension.value)

    missing: list[ReviewDimension] = []
    recovered: list[ReviewDimension] = []
    usable: list[WorkerResult] = []
    for r in ordered:
        if r.status is WorkerStatus.OK:
            usable.append(r)
            continue
        if not r.required and parent_can_recover:
            recovered.append(r.dimension)  # parent redoes this dimension itself
            continue
        missing.append(r.dimension)

    if missing:
        return AggregatedReview(
            AggregateOutcome.INCOMPLETE, None, (), tuple(missing), tuple(recovered)
        )

    # normalize -> deduplicate -> reconcile severity -> derive decision
    best: dict[tuple[str, str], WorkerFinding] = {}
    for r in usable:
        for f in r.findings:
            key = f.identity()
            current = best.get(key)
            if current is None or _sev_rank(f.candidate_severity) < _sev_rank(current.candidate_severity):
                best[key] = f  # highest candidate severity wins on a duplicate

    findings = tuple(
        ds.Finding(id=f"F{i + 1}", severity=wf.candidate_severity, origin=wf.dimension.value)
        for i, wf in enumerate(sorted(best.values(), key=lambda f: (f.identity())))
    )
    return AggregatedReview(
        AggregateOutcome.GRADED,
        ds.derive_decision(findings),
        findings,
        (),
        tuple(recovered),
    )


def _sev_rank(s: ds.Severity) -> int:
    return {ds.Severity.P0: 0, ds.Severity.P1: 1, ds.Severity.P2: 2}[s]
