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
        if any(row.status in incomplete for row in rows)
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
        if row.status is not RequirementStatus.NOT_APPLICABLE and not row.evidence:
            raise ValueError("evidence is required for this status")


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
