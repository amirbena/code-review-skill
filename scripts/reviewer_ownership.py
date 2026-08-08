#!/usr/bin/env python3
"""Deterministic reference implementation of the reviewer-ownership rule.

Governs whether a `github-pr-review` invocation may perform a bounded
delta-only re-review or must perform a normal full review of the current
PR state, per
skills/github-pr-review/policies/github-review.md, "Reviewer ownership
and delta re-review". This module has no Git/GitHub or network
dependency: it operates purely on already-resolved identity/SHA facts,
so the decision rule itself can be exercised deterministically in
scripts/test_reviewer_ownership.py without live GitHub calls.

This is a reference/test aid, not part of either packaged Skill archive
(see scripts/package-skills.sh / scripts/package-skills.ps1) — the
Skills themselves are prompt-driven and reason about this rule directly
from the canonical policy text.
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
    """Already-resolved facts a caller supplies to the decision rule.

    current_reviewer and pr_author are required: self-review identity
    resolution is its own upstream incapability (see
    skills/github-pr-review/policies/github-review.md, "Self-review
    capability" — "treat resolution failure as its own explicit
    incapability rather than silently defaulting to a full review"),
    handled by the caller before this decision table ever runs. Making
    these fields optional here would let an unresolved identity silently
    fall through to a normal-full-review result, which is exactly the
    outcome that policy forbids.

    The remaining None / False values represent "unresolved" or "not
    established" for the *review-mode* facts this table does own — the
    rule fails conservative (normal full review) on missing or ambiguous
    evidence for those.
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

    Order matters and mirrors the policy's "Review Mode Resolution":
    self-review guard first and authoritative, then previous-review
    existence, then reviewer-identity ambiguity, then reviewer match,
    then SHA availability/equality, then material-delta escalation.
    """

    # Self-review guard runs first and is authoritative; it can never be
    # bypassed by review-mode resolution. current_reviewer/pr_author are
    # required fields (see ReviewModeInput), so there is no unresolved-
    # identity case to silently fall through here.
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
