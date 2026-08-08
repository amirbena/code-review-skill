#!/usr/bin/env python3
"""Regression coverage for reviewer_ownership.resolve_review_mode.

Mirrors skills/github-pr-review/policies/reviewer-delta-review.md.

Run with:
    python3 scripts/test_reviewer_ownership.py
"""

from __future__ import annotations

import unittest

from reviewer_ownership import (
    DELTA_RE_REVIEW,
    NORMAL_FULL_REVIEW,
    NO_NEW_DELTA,
    SELF_REVIEW_SKIPPED,
    ReviewModeInput,
    resolve_review_mode,
)


class ReviewerOwnershipTests(unittest.TestCase):
    def test_same_reviewer_new_head_selects_delta_re_review(self) -> None:
        result = resolve_review_mode(
            ReviewModeInput(
                current_reviewer="alice",
                pr_author="carol",
                previous_review_exists=True,
                previous_reviewer="alice",
                previous_reviewed_sha="abc1234",
                current_head_sha="def5678",
            )
        )
        self.assertEqual(result.mode, DELTA_RE_REVIEW)

    def test_different_reviewer_new_head_selects_normal_full_review(self) -> None:
        result = resolve_review_mode(
            ReviewModeInput(
                current_reviewer="bob",
                pr_author="carol",
                previous_review_exists=True,
                previous_reviewer="alice",
                previous_reviewed_sha="abc1234",
                current_head_sha="def5678",
            )
        )
        self.assertEqual(result.mode, NORMAL_FULL_REVIEW)

    def test_no_previous_review_selects_normal_full_review(self) -> None:
        result = resolve_review_mode(
            ReviewModeInput(
                current_reviewer="alice",
                pr_author="carol",
                previous_review_exists=False,
            )
        )
        self.assertEqual(result.mode, NORMAL_FULL_REVIEW)

    def test_ambiguous_previous_reviewer_selects_normal_full_review(self) -> None:
        result = resolve_review_mode(
            ReviewModeInput(
                current_reviewer="alice",
                pr_author="carol",
                previous_review_exists=True,
                previous_reviewer="alice",
                previous_reviewer_ambiguous=True,
                previous_reviewed_sha="abc1234",
                current_head_sha="def5678",
            )
        )
        self.assertEqual(result.mode, NORMAL_FULL_REVIEW)

    def test_same_reviewer_but_reviewed_sha_unavailable_selects_normal_full_review(
        self,
    ) -> None:
        result = resolve_review_mode(
            ReviewModeInput(
                current_reviewer="alice",
                pr_author="carol",
                previous_review_exists=True,
                previous_reviewer="alice",
                previous_reviewed_sha=None,
                current_head_sha="def5678",
            )
        )
        self.assertEqual(result.mode, NORMAL_FULL_REVIEW)

    def test_same_reviewer_unchanged_head_selects_no_new_delta(self) -> None:
        result = resolve_review_mode(
            ReviewModeInput(
                current_reviewer="alice",
                pr_author="carol",
                previous_review_exists=True,
                previous_reviewer="alice",
                previous_reviewed_sha="abc1234",
                current_head_sha="abc1234",
            )
        )
        self.assertEqual(result.mode, NO_NEW_DELTA)

    def test_self_review_condition_terminates_before_review_mode_resolution(
        self,
    ) -> None:
        # current_reviewer == pr_author must win even though every other
        # fact below would otherwise select delta re-review — the
        # self-review guard is authoritative and runs first.
        result = resolve_review_mode(
            ReviewModeInput(
                current_reviewer="alice",
                pr_author="alice",
                previous_review_exists=True,
                previous_reviewer="alice",
                previous_reviewed_sha="abc1234",
                current_head_sha="def5678",
            )
        )
        self.assertEqual(result.mode, SELF_REVIEW_SKIPPED)

    def test_same_reviewer_materially_expanded_delta_escalates_to_full_review(
        self,
    ) -> None:
        result = resolve_review_mode(
            ReviewModeInput(
                current_reviewer="alice",
                pr_author="carol",
                previous_review_exists=True,
                previous_reviewer="alice",
                previous_reviewed_sha="abc1234",
                current_head_sha="def5678",
                delta_materially_changes_scope=True,
            )
        )
        self.assertEqual(result.mode, NORMAL_FULL_REVIEW)


if __name__ == "__main__":
    unittest.main()
