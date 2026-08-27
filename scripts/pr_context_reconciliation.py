#!/usr/bin/env python3
"""Test-only reference for optional PR-context handling.

Mirrors skills/local-code-review/policies/pr-context.md.
Not runtime logic, not packaged.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import FrozenSet, Optional, Sequence


# --- Classification (pr-context.md, "Classifying PR review context") ----


class Category(Enum):
    FINDING = "actionable_defect_finding"
    DECISION = "architectural_design_decision"
    PREFERENCE = "implementation_preference_suggestion"
    INFORMATIONAL = "informational_comment"
    RESOLVED_OBSOLETE = "resolved_or_obsolete_feedback"


@dataclass(frozen=True)
class ThreadComment:
    """One comment in a PR review thread."""

    category: Category
    label: str = ""
    is_explicit_resolution: bool = False


def classify_thread(comments: Sequence[ThreadComment]) -> ThreadComment:
    """The latest explicit resolution governs; else the most recent comment."""
    if not comments:
        raise ValueError("a thread must contain at least one comment")
    for comment in reversed(comments):
        if comment.is_explicit_resolution:
            return comment
    return comments[-1]


# --- Scope / relevance (pr-context.md, "Targeted retrieval") ------------


def is_relevant_to_local_delta(
    item_touches: FrozenSet[str], local_delta_touches: FrozenSet[str]
) -> bool:
    """Overlap with the current local delta. An empty touch set is never
    relevant."""
    if not item_touches:
        return False
    return bool(item_touches & local_delta_touches)


# --- Existing reviewer finding reconciliation ----------------------------
# (pr-context.md, "Reconciling existing reviewer findings")


class FindingStatus(Enum):
    STILL_VALID = "still_valid"
    RESOLVED = "resolved"
    REQUIRES_REEVALUATION = "requires_reevaluation"
    OUT_OF_SCOPE = "outside_current_local_review_scope"


@dataclass(frozen=True)
class ExistingFinding:
    id: str
    touches: FrozenSet[str]


@dataclass(frozen=True)
class FindingReconciliation:
    """Reconciliation outcome for one existing reviewer finding.

    No `severity` field by design — severity stays local-code-review's own.
    """

    finding_id: str
    status: FindingStatus
    reuse_evidence: bool


def reconcile_finding(
    finding: ExistingFinding,
    local_delta_touches: FrozenSet[str],
    *,
    issue_still_present: Optional[bool],
) -> FindingReconciliation:
    """Resolve one finding's status against the current local delta.

    `issue_still_present` is about the *current* delta, never historical PR
    state; `None` (undeterminable) maps to REQUIRES_REEVALUATION.
    """
    if not is_relevant_to_local_delta(finding.touches, local_delta_touches):
        return FindingReconciliation(finding.id, FindingStatus.OUT_OF_SCOPE, reuse_evidence=False)
    if issue_still_present is None:
        return FindingReconciliation(
            finding.id, FindingStatus.REQUIRES_REEVALUATION, reuse_evidence=True
        )
    if issue_still_present:
        return FindingReconciliation(finding.id, FindingStatus.STILL_VALID, reuse_evidence=True)
    return FindingReconciliation(finding.id, FindingStatus.RESOLVED, reuse_evidence=False)


def should_emit_separate_finding(
    reconciliation: FindingReconciliation, *, independently_discovered_same_issue: bool
) -> bool:
    """A still-valid finding the review also found independently is not
    emitted again; anything else may be."""
    if (
        reconciliation.status == FindingStatus.STILL_VALID
        and independently_discovered_same_issue
    ):
        return False
    return True


# --- Architectural/design decisions --------------------------------------
# (pr-context.md, "Architectural/design decisions")


class DecisionStatus(Enum):
    NOT_SETTLED = "not_settled_preference_only"
    OUT_OF_SCOPE = "outside_current_local_review_scope"
    FOLLOWED = "followed"
    SUPERSEDED = "intentionally_superseded"
    VIOLATED = "violated"


# Evidence sufficient to challenge a settled decision (exhaustive per policy;
# an unknown kind is a caller error).
SUPERSESSION_EVIDENCE_KINDS: FrozenSet[str] = frozenset(
    {
        "changed_requirements",
        "correctness_or_reliability_problem",
        "invalidated_assumption",
        "new_dependency_or_constraint",
        "security_or_performance_concern",
        "newer_explicit_decision",
    }
)


@dataclass(frozen=True)
class ArchitecturalDecision:
    id: str
    touches: FrozenSet[str]
    is_settled: bool  # explicit agreement/resolution evidence exists in PR context


@dataclass(frozen=True)
class DecisionReconciliation:
    decision_id: str
    status: DecisionStatus
    emit_finding: bool


def reconcile_decision(
    decision: ArchitecturalDecision,
    local_delta_touches: FrozenSet[str],
    *,
    delta_follows_decision: bool,
    supersession_evidence: FrozenSet[str] = frozenset(),
) -> DecisionReconciliation:
    """Resolve one decision's status against the current local delta.

    A non-settled decision is never treated as a constraint, even if the
    delta happens to agree with it.
    """
    if not is_relevant_to_local_delta(decision.touches, local_delta_touches):
        return DecisionReconciliation(decision.id, DecisionStatus.OUT_OF_SCOPE, emit_finding=False)
    if not decision.is_settled:
        return DecisionReconciliation(decision.id, DecisionStatus.NOT_SETTLED, emit_finding=False)
    if delta_follows_decision:
        return DecisionReconciliation(decision.id, DecisionStatus.FOLLOWED, emit_finding=False)

    unknown_evidence = supersession_evidence - SUPERSESSION_EVIDENCE_KINDS
    if unknown_evidence:
        raise ValueError(f"unrecognized supersession evidence kind(s): {sorted(unknown_evidence)}")

    if supersession_evidence:
        return DecisionReconciliation(decision.id, DecisionStatus.SUPERSEDED, emit_finding=False)
    return DecisionReconciliation(decision.id, DecisionStatus.VIOLATED, emit_finding=True)


# --- Availability / fallback (pr-context.md, "Unavailable or unresolved
# PR context") -------------------------------------------------------------


class PRContextAvailability(Enum):
    NOT_SUPPLIED = "not_supplied"
    SUPPLIED_AVAILABLE = "supplied_available"
    SUPPLIED_UNAVAILABLE = "supplied_unavailable"  # unresolved ref / no GitHub read access


def should_block_local_review(availability: PRContextAvailability) -> bool:
    """PR context never blocks the local review — every availability state
    maps to the same answer."""
    del availability
    return False


# --- Report-section inclusion (pr-context.md, "Output") -------------------


def pr_context_section_required(
    pr_reference_supplied: bool,
    finding_reconciliations: Sequence[FindingReconciliation] = (),
    decision_reconciliations: Sequence[DecisionReconciliation] = (),
) -> bool:
    """The "PR Context" section appears only when a PR reference was supplied
    *and* it materially shaped the review."""
    if not pr_reference_supplied:
        return False
    material_finding = any(
        f.status in (FindingStatus.STILL_VALID, FindingStatus.REQUIRES_REEVALUATION)
        for f in finding_reconciliations
    )
    material_decision = any(
        d.status in (DecisionStatus.VIOLATED, DecisionStatus.SUPERSEDED)
        for d in decision_reconciliations
    )
    return material_finding or material_decision


# --- Governance: this module's own shape never grows GitHub-mutation or
# authority-bearing capability ---------------------------------------------

# Fragments a GitHub-mutating or approval/ownership-bypassing capability
# would use. This layer is read-only; the test checks every public name.
PROHIBITED_CAPABILITY_NAME_FRAGMENTS: FrozenSet[str] = frozenset(
    {
        "publish",
        "submit",
        "post_",
        "approve",
        "request_changes",
        "merge",
        "delete",
        "push",
        "commit",
        "comment_on_pr",
        "bypass_approval",
        "skip_approval",
        "auto_approve",
        "override_ownership",
    }
)
