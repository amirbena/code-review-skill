"""Test-only reference model for review stopping criteria (Issue #89).

This is test-only: not runtime logic, not packaged, and not imported by
any Skill. The canonical behavior lives in
``shared/policies/review-stopping-criteria.md``; this module makes that
policy's coverage/exit-condition definition and its incomplete-triggers
catalog executable so the unit tests can pin them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from tests.reference.change_risk_signals import Depth


class IncompleteTrigger(str, Enum):
    """Closed set — "Incomplete triggers (closed set, evaluated per-pass)"."""

    REQUIRED_PASS_NOT_PRODUCED = "required-pass-not-produced"
    PARTITION_NOT_COMPLETED = "partition-not-completed"
    REVIEW_TARGET_NOT_ESTABLISHED = "review-target-not-established"
    REQUIRED_VALIDATION_UNAVAILABLE = "required-validation-unavailable"


@dataclass(frozen=True)
class IncompleteReason:
    trigger: IncompleteTrigger
    detail: str


@dataclass(frozen=True)
class PassResult:
    """One required pass's own report of whether it reached its stop
    condition. A pass that reached "insufficient evidence, stop here" is
    still ``reached_stop_condition=True`` — that is a valid terminal
    outcome, not a coverage gap (see review-scope.md, "Stop conditions")."""

    name: str
    reached_stop_condition: bool
    required_at: tuple[Depth, ...] = (Depth.STANDARD, Depth.ELEVATED, Depth.DEEP)


@dataclass(frozen=True)
class PartitionCompletion:
    partition_id: str
    completed: bool


@dataclass(frozen=True)
class CoverageResult:
    coverage: str  # "complete" | "incomplete"
    depth: Depth
    partitioned: bool
    reasons: tuple[IncompleteReason, ...] = field(default_factory=tuple)

    def to_machine_model(self) -> dict[str, object]:
        inner: dict[str, object] = {
            "coverage": self.coverage,
            "depth": self.depth.value,
            "partitioned": self.partitioned,
        }
        if self.coverage == "incomplete":
            inner["incomplete_reasons"] = [
                {"trigger": r.trigger.value, "detail": r.detail} for r in self.reasons
            ]
        return {"review_stopping_criteria": inner}


def evaluate_coverage(
    depth: Depth,
    passes: tuple[PassResult, ...],
    review_target_established: bool = True,
    partitions: tuple[PartitionCompletion, ...] = (),
    validation_gap: IncompleteReason | None = None,
) -> CoverageResult:
    """Aggregate already-made per-pass/per-partition completion signals
    into one review-level coverage result — "Coverage" and "Incomplete
    triggers". This function decides nothing about *whether* an
    individual pass or partition finished; it only rolls up those
    already-made determinations, exactly as the policy requires."""
    reasons: list[IncompleteReason] = []

    if not review_target_established:
        reasons.append(
            IncompleteReason(
                IncompleteTrigger.REVIEW_TARGET_NOT_ESTABLISHED,
                "the complete Review Target could not be established",
            )
        )

    for p in passes:
        if depth not in p.required_at:
            continue
        if not p.reached_stop_condition:
            reasons.append(
                IncompleteReason(
                    IncompleteTrigger.REQUIRED_PASS_NOT_PRODUCED,
                    f"required pass '{p.name}' did not reach its stop condition",
                )
            )

    for part in partitions:
        if not part.completed:
            reasons.append(
                IncompleteReason(
                    IncompleteTrigger.PARTITION_NOT_COMPLETED,
                    f"partition {part.partition_id} could not be completed",
                )
            )

    if validation_gap is not None:
        reasons.append(validation_gap)

    coverage = "incomplete" if reasons else "complete"
    return CoverageResult(
        coverage=coverage,
        depth=depth,
        partitioned=bool(partitions),
        reasons=tuple(reasons),
    )


def decision_label(
    coverage: CoverageResult, mechanical_decision: str
) -> str:
    """"Labeling — incomplete must never present as clean": coverage is
    the one gate that can override severity.md's mechanical derivation.
    ``mechanical_decision`` is whatever severity.md would otherwise
    render (e.g. "REVIEW CLEAN" / "CHANGES REQUIRED")."""
    if coverage.coverage == "incomplete":
        return "REVIEW INCOMPLETE"
    return mechanical_decision
