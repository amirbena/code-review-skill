#!/usr/bin/env python3
"""Test-only decision tables for github-pr-review Existing Review Evidence.

Mirrors shared/policies/review-evidence.md and
skills/github-pr-review/policies/{review-evidence,pr-scope}.md.
Not runtime logic, not packaged.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import FrozenSet, Iterable, Optional, Sequence, Union

from tests.reference.current_evidence import (
    CurrentEvidenceKind,
    current_evidence_collection_overrides_historical_authority,
    current_evidence_overrides_historical_authority,
)


# --- Authorship (review-evidence.md, "Comment authorship") --------------


class AuthorType(Enum):
    HUMAN_REVIEWER = "human_reviewer"
    MAINTAINER = "maintainer"
    AUTOMATION_BOT = "automation_bot"
    CI_STATUS = "ci_status"
    UNKNOWN = "unknown"


HUMAN_AUTHOR_TYPES: FrozenSet[AuthorType] = frozenset(
    {AuthorType.HUMAN_REVIEWER, AuthorType.MAINTAINER}
)
AUTOMATION_AUTHOR_TYPES: FrozenSet[AuthorType] = frozenset(
    {AuthorType.AUTOMATION_BOT, AuthorType.CI_STATUS}
)

# The authority kinds automation output must never establish on its own.
AUTHORITY_KINDS: FrozenSet[str] = frozenset(
    {
        "settled_architectural_decision",
        "maintainer_clarification",
        "reviewer_acceptance",
        "authoritative_correctness_resolution",
    }
)


def _validate_authority_kind(kind: str) -> None:
    if kind not in AUTHORITY_KINDS:
        raise ValueError(f"unknown authority kind: {kind!r}")


def author_can_establish(author_type: AuthorType, kind: str) -> bool:
    """Apply the authority level required by the conclusion type."""
    _validate_authority_kind(kind)
    if kind == "maintainer_clarification":
        return author_type is AuthorType.MAINTAINER
    return author_type in HUMAN_AUTHOR_TYPES


def automation_can_establish(kind: str) -> bool:
    """Automation/bot output never establishes any authority kind alone."""
    _validate_authority_kind(kind)
    return False


def automation_contribution(author_type: AuthorType) -> str:
    """Bot output is an observation to verify; human output can be authoritative."""
    if author_type in AUTOMATION_AUTHOR_TYPES:
        return "observation_only"
    if author_type in HUMAN_AUTHOR_TYPES:
        return "authoritative_capable"
    return "non_authoritative_unknown"


# --- Thread classification (evidence.md, "Classify each item") ----------


class PriorItemClass(Enum):
    STILL_RELEVANT = "still_relevant_finding"
    RESOLVED = "resolved_finding"
    STALE = "stale_requires_reevaluation"
    DUPLICATE = "duplicate"
    SETTLED_DECISION = "settled_decision"
    SPECULATIVE = "speculative_discussion"


class ThreadResolution(Enum):
    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"
    UNKNOWN = "unknown"


class ConclusionKind(Enum):
    SETTLED_ARCHITECTURAL_DECISION = "settled_architectural_decision"
    MAINTAINER_CLARIFICATION = "maintainer_clarification"
    REVIEWER_ACCEPTANCE = "reviewer_acceptance"
    AUTHORITATIVE_CORRECTNESS_RESOLUTION = "authoritative_correctness_resolution"


@dataclass(frozen=True)
class ThreadComment:
    author_type: AuthorType
    conclusion_kind: Optional[ConclusionKind] = None
    is_explicit_conclusion: bool = False
    reopens_current_target: bool = False
    label: str = ""


def thread_conclusion_is_authoritative(comment: ThreadComment) -> bool:
    """Authority depends on both the author and conclusion kind."""
    return (
        comment.is_explicit_conclusion
        and comment.conclusion_kind is not None
        and author_can_establish(comment.author_type, comment.conclusion_kind.value)
    )


def classify_thread(comments: Sequence[ThreadComment]) -> ThreadComment:
    """Latest authoritative conclusion or reopening governs the thread."""
    if not comments:
        raise ValueError("a thread must contain at least one comment")
    for comment in reversed(comments):
        if thread_conclusion_is_authoritative(comment) or (
            comment.reopens_current_target
            and comment.author_type in HUMAN_AUTHOR_TYPES
        ):
            return comment
    return comments[-1]


# --- Reconciliation against the CURRENT PR HEAD ------------------------
# (evidence.md, "Reconciliation outcomes"; pr-scope.md, "Existing review
# awareness")


class ReviewState(Enum):
    APPROVED = "APPROVED"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"
    COMMENTED = "COMMENTED"
    DISMISSED = "DISMISSED"


@dataclass(frozen=True)
class PriorFinding:
    id: str
    reviewed_sha: str  # PR HEAD the prior reviewer saw


@dataclass(frozen=True)
class Reconciliation:
    finding_id: str
    item_class: PriorItemClass
    reuse_prior_evidence: bool
    emit_in_this_review: bool


def reconcile_prior_finding(
    finding: PriorFinding,
    *,
    current_head_sha: str,
    present_on_current_head: Optional[bool],
    surrounding_code_materially_changed: bool = False,
    independently_rediscovered: bool = False,
) -> Reconciliation:
    """Resolve one prior finding's status against the current PR HEAD.

    `present_on_current_head` is about the current HEAD, never the historical
    state; `None` (undeterminable) forces re-evaluation, never an assumption.
    """
    head_changed = finding.reviewed_sha != current_head_sha

    if present_on_current_head is None:
        return Reconciliation(finding.id, PriorItemClass.STALE, True, False)

    if present_on_current_head:
        cls = PriorItemClass.DUPLICATE if independently_rediscovered else PriorItemClass.STILL_RELEVANT
        return Reconciliation(finding.id, cls, True, True)

    # Absent on the current HEAD, but heavy churn since means "absent" needs
    # a fresh look rather than a blind "resolved".
    if head_changed and surrounding_code_materially_changed:
        return Reconciliation(finding.id, PriorItemClass.STALE, True, False)

    return Reconciliation(finding.id, PriorItemClass.RESOLVED, False, False)


def should_emit_independent_finding(*, materially_different_from_prior: bool) -> bool:
    """A materially different current defect in the same area is always its
    own finding, never suppressed as a duplicate."""
    return materially_different_from_prior


def should_suppress_as_duplicate(reconciliation: Reconciliation) -> bool:
    """Suppress publication only for a true same-issue duplicate this review
    also found independently."""
    return reconciliation.item_class == PriorItemClass.DUPLICATE


# --- Regression after a resolved thread --------------------------------
# (evidence.md, "Interpret prior evidence against the current target")


class RegressionOutcome(Enum):
    NO_FINDING_STILL_FIXED = "no_finding_still_fixed"
    EMIT_FRESH_FINDING_REGRESSED = "emit_fresh_finding_regressed"
    EMIT_FINDING_NEVER_FIXED = "emit_finding_never_fixed"


def evaluate_possibly_regressed(
    thread_resolution: ThreadResolution, defect_present_on_current_head: bool
) -> RegressionOutcome:
    """A resolved flag is a past conclusion, not proof of present correctness."""
    if not defect_present_on_current_head:
        return RegressionOutcome.NO_FINDING_STILL_FIXED
    if thread_resolution is ThreadResolution.RESOLVED:
        return RegressionOutcome.EMIT_FRESH_FINDING_REGRESSED
    return RegressionOutcome.EMIT_FINDING_NEVER_FIXED


def reconcile_reopened_thread(
    comments: Sequence[ThreadComment],
    *,
    historical_resolution: ThreadResolution,
    defect_present_on_current_head: Optional[bool],
) -> Optional[Union[RegressionOutcome, PriorItemClass]]:
    """Re-evaluate only when classification finds a current-target reopening.

    None preserves the historical conclusion without entering regression handling.
    """
    governing = classify_thread(comments)
    if not governing.reopens_current_target:
        return None
    if defect_present_on_current_head is None:
        return PriorItemClass.STALE
    return evaluate_possibly_regressed(
        historical_resolution, defect_present_on_current_head
    )


def resolved_flag_is_correctness_oracle() -> bool:
    """Never. The current HEAD determines present correctness."""
    return False


# --- HEAD-change semantics (pr-scope.md; review-evidence.md, "HEAD
# changes reset applicability") ----------------------------------------


def head_change_resets_applicability(prior_sha: str, current_sha: str) -> bool:
    return prior_sha != current_sha


def must_reclassify_prior_human_findings(prior_sha: str, current_sha: str) -> bool:
    return prior_sha != current_sha


def prior_findings_remain_investigation_evidence_after_head_change() -> bool:
    return True


def old_approval_carries_to_new_head(prior_reviewed_sha: str, current_head_sha: str) -> bool:
    """Never. An old approval does not authorize a different HEAD."""
    del prior_reviewed_sha, current_head_sha
    return False


# --- Settled decisions (evidence.md, "Settled decisions") --------------


class DecisionStatus(Enum):
    NOT_SETTLED = "not_settled_preference_only"
    FOLLOWED = "followed"
    SUPERSEDED = "intentionally_superseded"
    VIOLATED = "violated"


@dataclass(frozen=True)
class SettledDecision:
    id: str
    established_by: AuthorType
    has_explicit_agreement: bool


def decision_is_settled(decision: SettledDecision) -> bool:
    """Settled requires explicit agreement AND a human/maintainer author."""
    return decision.has_explicit_agreement and decision.established_by in HUMAN_AUTHOR_TYPES


def settled_decision_from_thread(
    comments: Sequence[ThreadComment], *, decision_id: str
) -> Optional[SettledDecision]:
    """Return a settled decision only from authoritative governing evidence."""
    governing = classify_thread(comments)
    if (
        governing.conclusion_kind
        is not ConclusionKind.SETTLED_ARCHITECTURAL_DECISION
        or not thread_conclusion_is_authoritative(governing)
    ):
        return None
    return SettledDecision(decision_id, governing.author_type, True)


@dataclass(frozen=True)
class DecisionReconciliation:
    decision_id: str
    status: DecisionStatus
    emit_finding: bool


def reconcile_settled_decision(
    decision: SettledDecision,
    *,
    current_delta_follows: bool,
    current_evidence: Iterable[object] = frozenset(),
) -> DecisionReconciliation:
    if not decision_is_settled(decision):
        return DecisionReconciliation(decision.id, DecisionStatus.NOT_SETTLED, False)

    if current_evidence_collection_overrides_historical_authority(current_evidence):
        return DecisionReconciliation(decision.id, DecisionStatus.SUPERSEDED, False)
    if current_delta_follows:
        return DecisionReconciliation(decision.id, DecisionStatus.FOLLOWED, False)
    return DecisionReconciliation(decision.id, DecisionStatus.VIOLATED, True)


def settled_decision_suppresses_evidence(evidence: CurrentEvidenceKind) -> bool:
    """Suppression is the inverse of the canonical override classification."""
    return not current_evidence_overrides_historical_authority(evidence)


def governing_conclusion_suppresses_defect(
    comments: Sequence[ThreadComment], evidence: CurrentEvidenceKind
) -> bool:
    """Only authoritative evidence may constrain non-critical preferences."""
    governing = classify_thread(comments)
    return thread_conclusion_is_authoritative(
        governing
    ) and settled_decision_suppresses_evidence(evidence)


# --- Retrieval completeness (pr-scope.md, "Retrieving prior review
# activity") ----------------------------------------------------------

# The surfaces retrieval must cover, paginated to exhaustion.
REQUIRED_RETRIEVAL_SURFACES: tuple[str, ...] = (
    "submitted_reviews",
    "review_state",
    "review_body",
    "inline_review_comments",
    "issue_comments",
    "review_threads",
    "thread_resolution_state",
)
PAGINATION_TO_EXHAUSTION = True


class HistoryCompleteness(Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


def history_blocks_review(completeness: HistoryCompleteness) -> bool:
    """Incomplete history never blocks the review of the current PR."""
    del completeness
    return False


def may_claim_complete_deduplication(completeness: HistoryCompleteness) -> bool:
    return completeness is HistoryCompleteness.COMPLETE


def must_report_history_uncertainty(
    completeness: HistoryCompleteness, *, material_to_dedup: bool = True
) -> bool:
    return completeness is not HistoryCompleteness.COMPLETE and material_to_dedup


# --- Governance: this module stays read-only and carries no PR verdict --

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
        "dismiss_review",
        "resolve_thread",
        "bypass",
        "override_ownership",
    }
)
