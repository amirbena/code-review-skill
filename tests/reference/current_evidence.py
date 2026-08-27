#!/usr/bin/env python3
"""Test-only canonical classification for current evidence.

Not runtime logic, not packaged.
"""

from __future__ import annotations

from enum import Enum
from typing import FrozenSet, Iterable


class CurrentEvidenceKind(Enum):
    CHANGED_REQUIREMENTS = "changed_requirements"
    CORRECTNESS_DEFECT = "correctness_defect"
    RELIABILITY_DEFECT = "reliability_defect"
    INVALIDATED_ASSUMPTION = "invalidated_assumption"
    NEW_DEPENDENCY_OR_CONSTRAINT = "new_dependency_or_constraint"
    MATERIAL_SECURITY_CONCERN = "material_security_concern"
    MATERIAL_PERFORMANCE_CONCERN = "material_performance_concern"
    DATA_INTEGRITY_DEFECT = "data_integrity_defect"
    SAFETY_DEFECT = "safety_defect"
    NEWER_EXPLICIT_DECISION = "newer_explicit_decision"
    STYLE_PREFERENCE = "style_preference"
    SPECULATIVE_OPTIMIZATION = "speculative_optimization"
    NON_MATERIAL_REVIEWER_PREFERENCE = "non_material_reviewer_preference"


OVERRIDING_CURRENT_EVIDENCE: FrozenSet[CurrentEvidenceKind] = frozenset(
    {
        CurrentEvidenceKind.CHANGED_REQUIREMENTS,
        CurrentEvidenceKind.CORRECTNESS_DEFECT,
        CurrentEvidenceKind.RELIABILITY_DEFECT,
        CurrentEvidenceKind.INVALIDATED_ASSUMPTION,
        CurrentEvidenceKind.NEW_DEPENDENCY_OR_CONSTRAINT,
        CurrentEvidenceKind.MATERIAL_SECURITY_CONCERN,
        CurrentEvidenceKind.MATERIAL_PERFORMANCE_CONCERN,
        CurrentEvidenceKind.DATA_INTEGRITY_DEFECT,
        CurrentEvidenceKind.SAFETY_DEFECT,
        CurrentEvidenceKind.NEWER_EXPLICIT_DECISION,
    }
)


def current_evidence_overrides_historical_authority(
    evidence: CurrentEvidenceKind,
) -> bool:
    """Concrete material evidence overrides historical review authority."""
    if not isinstance(evidence, CurrentEvidenceKind):
        raise ValueError(f"unrecognized current evidence kind: {evidence!r}")
    return evidence in OVERRIDING_CURRENT_EVIDENCE


def current_evidence_collection_overrides_historical_authority(
    evidence_items: Iterable[object],
) -> bool:
    """Validate the complete collection before deciding whether it overrides."""
    classifications = [
        current_evidence_overrides_historical_authority(evidence)
        for evidence in evidence_items
    ]
    return any(classifications)
