"""Test-only reference model for requirement coverage (Issue #176)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence


class RequirementStatus(Enum):
    IMPLEMENTED = "implemented"
    PARTIALLY_EVIDENCED = "partially_evidenced"
    NOT_EVIDENCED = "not_evidenced"
    NOT_APPLICABLE = "not_applicable"


class Completeness(Enum):
    COMPLETE = "complete"
    INCOMPLETE = "incomplete"


class Applicability(Enum):
    APPLIES = "applies"
    NOT_APPLICABLE = "not_applicable"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True)
class RequirementSource:
    evidence_type: str
    name: str
    citation: str


@dataclass(frozen=True)
class RequirementCoverage:
    requirement_id: str
    requirement: str
    source: RequirementSource
    status: RequirementStatus
    evidence: tuple[str, ...]
    explanation: str
    ambiguity: str | None = None


@dataclass(frozen=True)
class ObligationEvidence:
    obligation_id: str
    code_evidence: tuple[str, ...]
    test_evidence: tuple[str, ...] = ()


@dataclass(frozen=True)
class RequirementAssessment:
    requirement_id: str
    requirement: str
    source: RequirementSource
    obligation_ids: tuple[str, ...]
    observed: tuple[ObligationEvidence, ...]
    test_required: bool = False
    inspection_evidence: tuple[str, ...] = ()
    applicability: Applicability = Applicability.APPLIES
    applicability_evidence: tuple[str, ...] = ()
    ambiguity: str | None = None


def coverage_is_active(authoritative_types: Sequence[str]) -> bool:
    """Only authoritative task-contract types activate coverage."""
    return any(
        item in {"requirement", "acceptance_criteria"}
        for item in authoritative_types
    )


def completeness(rows: Sequence[RequirementCoverage]) -> Completeness | None:
    """Return no signal for inert coverage; otherwise derive it from rows."""
    if not rows:
        return None
    incomplete = {
        RequirementStatus.PARTIALLY_EVIDENCED,
        RequirementStatus.NOT_EVIDENCED,
    }
    return (
        Completeness.INCOMPLETE
        if any(row.status in incomplete or row.ambiguity for row in rows)
        else Completeness.COMPLETE
    )


def validate(rows: Sequence[RequirementCoverage]) -> None:
    """Enforce evidence and explanation invariants of the portable model."""
    seen: set[str] = set()
    for row in rows:
        if row.requirement_id in seen:
            raise ValueError("requirement ids must be unique")
        seen.add(row.requirement_id)
        if not row.requirement or not row.explanation:
            raise ValueError("requirement and explanation are required")
        if row.source.evidence_type not in {"requirement", "acceptance_criteria"}:
            raise ValueError("source must be an authoritative task-contract type")
        if not row.evidence and not row.ambiguity:
            raise ValueError("evidence is required for this status")


def classify(assessment: RequirementAssessment) -> RequirementCoverage:
    """Derive coverage from structured applicability and obligation evidence."""
    if assessment.applicability is Applicability.AMBIGUOUS:
        if not assessment.ambiguity:
            raise ValueError("ambiguous applicability requires an explanation")
        return RequirementCoverage(
            assessment.requirement_id,
            assessment.requirement,
            assessment.source,
            RequirementStatus.NOT_APPLICABLE,
            assessment.applicability_evidence,
            "Applicability cannot be resolved from authoritative context.",
            assessment.ambiguity,
        )
    if assessment.applicability is Applicability.NOT_APPLICABLE:
        if not assessment.applicability_evidence:
            raise ValueError("non-applicability requires affirmative evidence")
        return RequirementCoverage(
            assessment.requirement_id,
            assessment.requirement,
            assessment.source,
            RequirementStatus.NOT_APPLICABLE,
            assessment.applicability_evidence,
            "Authoritative scope evidence establishes non-applicability.",
        )

    required = set(assessment.obligation_ids)
    if not required:
        raise ValueError("requirements must have at least one obligation")
    evidenced = {
        item.obligation_id
        for item in assessment.observed
        if item.code_evidence
        and (not assessment.test_required or item.test_evidence)
        and item.obligation_id in required
    }
    if evidenced == required:
        status = RequirementStatus.IMPLEMENTED
    elif evidenced:
        status = RequirementStatus.PARTIALLY_EVIDENCED
    else:
        status = RequirementStatus.NOT_EVIDENCED
    evidence = tuple(
        citation
        for item in assessment.observed
        for citation in (*item.code_evidence, *item.test_evidence)
    )
    if status is RequirementStatus.NOT_EVIDENCED and not evidence:
        evidence = assessment.inspection_evidence
    if not evidence:
        raise ValueError("coverage classification requires concrete evidence")
    missing = required - evidenced
    explanation = (
        "All required obligations have concrete implementation evidence."
        if not missing
        else f"Missing implementation evidence for: {', '.join(sorted(missing))}."
    )
    return RequirementCoverage(
        assessment.requirement_id,
        assessment.requirement,
        assessment.source,
        status,
        evidence,
        explanation,
    )


def to_machine_model(rows: Sequence[RequirementCoverage]) -> dict[str, object] | None:
    """Render the policy's machine-readable shape, or nothing when inert."""
    overall = completeness(rows)
    if overall is None:
        return None
    validate(rows)
    return {
        "requirement_coverage": {
            "status": overall.value,
            "requirements": [
                {
                    "id": row.requirement_id,
                    "requirement": row.requirement,
                    "source": {
                        "type": row.source.evidence_type,
                        "name": row.source.name,
                        "citation": row.source.citation,
                    },
                    "status": row.status.value,
                    "evidence": list(row.evidence),
                    "explanation": row.explanation,
                    **({"ambiguity": row.ambiguity} if row.ambiguity else {}),
                }
                for row in rows
            ],
        }
    }
