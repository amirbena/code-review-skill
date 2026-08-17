#!/usr/bin/env python3
"""Deterministic reference implementation of optional PR-context handling.

Mirrors skills/local-code-review/policies/pr-context.md. Pure decision-table
logic (no Git/GitHub calls, no code understanding) so
test_pr_context_reconciliation.py can exercise it deterministically. Not
part of either packaged Skill archive — the Skill reasons from the
canonical policy text directly.

This module never determines whether an issue is "still present" in the
current local delta, whether code was changed, or what severity a finding
deserves — those require actually reading the code, which is
`local-code-review`'s own job (see pr-context.md, "Reconciling existing
reviewer findings": "Existing reviewer findings are evidence and context,
not authority"). This module only encodes the classification/reconciliation
*decision table* that policy defines once those facts are known, exactly
as reviewer_ownership.py encodes github-pr-review's review-mode decision
table rather than actually talking to GitHub.
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
    """Return the governing comment for a thread.

    Per pr-context.md, "Classifying PR review context": reason over a
    thread as a whole; the latest explicit resolution/conclusion governs,
    and earlier exploratory comments in the same thread are context for
    it, not independent findings. Absent any comment explicitly marked as
    a resolution, the thread's most recent comment governs.
    """
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
    """Whether a PR thread/item overlaps the current local delta.

    Per pr-context.md, "Targeted retrieval": only threads touching files,
    hunks, or symbols that overlap the current local delta are in scope.
    An empty item_touches set is never considered relevant — it carries no
    evidence of overlap.
    """
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

    Deliberately carries no `severity` field: severity remains
    `local-code-review`'s own, assigned independently per the shared
    severity policy — this reconciliation step supplies status and
    evidence-reuse guidance only, never a severity or a final decision.
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
    """Resolve one existing finding's status against the current local delta.

    `issue_still_present` is an already-resolved fact about the *current*
    local delta (never the historical PR state) — `None` means the
    reviewer could not determine this from PR context alone (ambiguous or
    the surrounding code changed enough that applicability is unclear),
    which maps to REQUIRES_REEVALUATION per policy.
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
    """Whether the local review should emit a *separate* new finding.

    Per pr-context.md, "Avoiding duplicate findings": a still-valid
    reconciled finding that the local review also independently notices is
    reconciled into one finding, never duplicated. Any other case
    (materially different issue, or nothing reconciled) may be reported.
    """
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


# The concrete evidence categories pr-context.md lists as sufficient to
# challenge a settled decision. Exhaustive per policy text — an unknown
# kind is a caller error, not a silently-accepted supersession.
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
    """Resolve one PR-context decision's status against the current local delta.

    A decision that is not `is_settled` (a single opinion, an unresolved
    suggestion, one side of an unfinished disagreement) is never treated
    as a constraint, regardless of whether the local delta happens to
    agree with it — per policy, "Do not treat every reviewer opinion as
    an architectural constraint."
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
    """PR context — present, absent, or unavailable — never blocks the
    local review itself. See pr-context.md, "Unavailable or unresolved PR
    context": "never a reason to fail, block, or degrade the local review
    itself."
    """
    del availability  # every state maps to the same answer, by design
    return False


# --- Report-section inclusion (pr-context.md, "Output") -------------------


def pr_context_section_required(
    pr_reference_supplied: bool,
    finding_reconciliations: Sequence[FindingReconciliation] = (),
    decision_reconciliations: Sequence[DecisionReconciliation] = (),
) -> bool:
    """Whether the optional "PR Context" report section should appear.

    Per pr-context.md, "Output": omitted entirely whenever no PR reference
    was supplied, and otherwise included only when it materially shaped
    the review (a still-valid or re-evaluated finding, or a violated/
    superseded decision) — never merely because a PR reference exists.
    """
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

#: Substrings that must never appear (case-insensitively) in any public
#: name this module defines — their presence would mean this read-only
#: reconciliation layer grew a GitHub-mutating or an
#: approval/ownership-bypassing capability, which pr-context.md prohibits
#: (see "Boundary with `github-pr-review`"). Checked by
#: test_pr_context_reconciliation.py via substring matching against
#: `dir(prc)`, not exact-name matching — a name like `submit_pr_review`
#: must be caught, not just a bare `submit`.
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
