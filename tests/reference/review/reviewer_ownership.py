#!/usr/bin/env python3
"""Test-only reference for the reviewer-ownership / delta-review rule.

Mirrors skills/github-pr-review/policies/reviewer-delta-review.md.
Not runtime logic, not packaged.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

NORMAL_FULL_REVIEW = "normal_full_review"
DELTA_RE_REVIEW = "delta_re_review"
NO_NEW_DELTA = "no_new_delta"


@dataclass(frozen=True)
class ReviewModeInput:
    """Already-resolved facts for the decision rule.

    `current_reviewer`/`pr_author` are required; other None/False fields
    mean "unresolved" and fail conservative (normal full review).

    `current_reviewer == pr_author` (a self-review) does **not** change
    review-mode selection — a self-review is a full or delta re-review on
    the same terms as an external one. Whether a self-review may submit a
    formal GitHub event is a separate concern owned by
    review_action_authorization.py.
    """

    current_reviewer: str
    pr_author: str
    previous_review_exists: bool
    previous_reviewer: Optional[str] = None
    previous_reviewer_ambiguous: bool = False
    previous_reviewed_sha: Optional[str] = None
    current_head_sha: Optional[str] = None
    delta_materially_changes_scope: bool = False


@dataclass(frozen=True)
class ReviewModeResult:
    mode: str
    reason: str


def resolve_review_mode(inp: ReviewModeInput) -> ReviewModeResult:
    """Resolve the review mode. Order: previous-review existence, reviewer
    ambiguity/match, SHA checks, delta escalation.

    Authorship (`current_reviewer == pr_author`) is deliberately not
    consulted here: a self-review resolves its mode exactly like an
    external review. The self-review mutation boundary is applied
    elsewhere and never skips analysis or mode resolution.
    """

    if not inp.previous_review_exists:
        return ReviewModeResult(NORMAL_FULL_REVIEW, "no previous completed review")

    if inp.previous_reviewer_ambiguous or inp.previous_reviewer is None:
        return ReviewModeResult(
            NORMAL_FULL_REVIEW, "previous reviewer identity unavailable or ambiguous"
        )

    if inp.previous_reviewer != inp.current_reviewer:
        return ReviewModeResult(
            NORMAL_FULL_REVIEW, "current reviewer differs from previous reviewer"
        )

    if not inp.previous_reviewed_sha or not inp.current_head_sha:
        return ReviewModeResult(
            NORMAL_FULL_REVIEW, "previously reviewed SHA cannot be established reliably"
        )

    if inp.previous_reviewed_sha == inp.current_head_sha:
        return ReviewModeResult(
            NO_NEW_DELTA, "same reviewer and HEAD unchanged since previous review"
        )

    if inp.delta_materially_changes_scope:
        return ReviewModeResult(
            NORMAL_FULL_REVIEW,
            "delta materially changes scope; escalated from delta re-review",
        )

    return ReviewModeResult(
        DELTA_RE_REVIEW,
        "same reviewer as immediately preceding completed review; reviewing bounded delta",
    )
