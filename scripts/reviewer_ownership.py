#!/usr/bin/env python3
"""Deterministic reference implementation of the reviewer-ownership rule.

Mirrors skills/github-pr-review/policies/reviewer-delta-review.md. Pure
logic (no Git/GitHub calls) so test_reviewer_ownership.py can exercise it
deterministically. Not part of either packaged Skill archive — the
Skills reason from the canonical policy text directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

SELF_REVIEW_SKIPPED = "self_review_skipped"
NORMAL_FULL_REVIEW = "normal_full_review"
DELTA_RE_REVIEW = "delta_re_review"
NO_NEW_DELTA = "no_new_delta"


@dataclass(frozen=True)
class ReviewModeInput:
    """Already-resolved facts for the decision rule.

    current_reviewer/pr_author are required: unresolved identity is the
    caller's own incapability to handle, not a case that should silently
    fall through to normal-full-review here. Other None/False fields mean
    "unresolved" and fail conservative (normal full review).
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
    """Resolve the review mode per the canonical decision table.

    Order: self-review guard first (authoritative), then previous-review
    existence, reviewer-identity ambiguity, reviewer match, SHA
    availability/equality, then material-delta escalation.
    """

    # Self-review guard is authoritative and can never be bypassed below.
    if inp.current_reviewer == inp.pr_author:
        return ReviewModeResult(SELF_REVIEW_SKIPPED, "current reviewer is the PR author")

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
