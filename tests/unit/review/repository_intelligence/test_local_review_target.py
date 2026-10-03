#!/usr/bin/env python3
"""Coverage for the single-repository local Review Target reference.

Contract: skills/local-code-review/policies/repository-state.md.
"""

from __future__ import annotations

import dataclasses
import hashlib
import unittest

from tests.reference.review.local_review_target import (
    CategoryScope,
    LocalReviewTarget,
    LocalReviewTargetError,
    SyncStatus,
    staged_scope_from_raw_diff,
)
from tests.reference.review.pr_context_reconciliation import ReviewedState

BASE_SHA = "a" * 40
HEAD_SHA = "b" * 40
EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()


def make_target(**overrides) -> LocalReviewTarget:
    fields = dict(
        base_branch="main",
        base_sha=BASE_SHA,
        head_sha=HEAD_SHA,
        sync_status=SyncStatus.IN_SYNC,
        remote_head_sha=HEAD_SHA,
        committed=CategoryScope(included=True),
        staged=staged_scope_from_raw_diff(b""),
        unstaged=CategoryScope(included=True),
        untracked=CategoryScope(included=True),
    )
    fields.update(overrides)
    return LocalReviewTarget(**fields)


class ValidTargetTests(unittest.TestCase):
    def test_all_categories_included(self) -> None:
        self.assertTrue(make_target().committed.included)

    def test_excluded_categories_with_reasons(self) -> None:
        target = make_target(
            committed=CategoryScope.excluded("caller asked for working tree only"),
            untracked=CategoryScope.excluded("none present"),
        )
        self.assertFalse(target.committed.included)
        self.assertEqual(target.untracked.reason, "none present")

    def test_no_tracking_branch_without_remote_head(self) -> None:
        target = make_target(
            sync_status=SyncStatus.NO_TRACKING_BRANCH, remote_head_sha=None
        )
        self.assertIsNone(target.remote_head_sha)

    def test_excluded_staged_may_omit_fingerprint(self) -> None:
        make_target(staged=CategoryScope.excluded("not requested"))

    def test_short_sha_accepted(self) -> None:
        make_target(head_sha="abc1234", remote_head_sha="abc1234")


class EmptyStagedFingerprintTests(unittest.TestCase):
    def test_nothing_staged_is_empty_input_hash(self) -> None:
        self.assertEqual(staged_scope_from_raw_diff(b"").fingerprint, EMPTY_SHA256)

    def test_nonempty_raw_diff_differs_from_empty(self) -> None:
        raw = b":100644 100644 1111111 2222222 M\0file.txt\0"
        self.assertEqual(
            staged_scope_from_raw_diff(raw).fingerprint, hashlib.sha256(raw).hexdigest()
        )
        self.assertNotEqual(staged_scope_from_raw_diff(raw).fingerprint, EMPTY_SHA256)


class InvalidTargetTests(unittest.TestCase):
    def assert_rejected(self, **overrides) -> None:
        with self.assertRaises(LocalReviewTargetError):
            make_target(**overrides)

    def test_empty_base_branch(self) -> None:
        self.assert_rejected(base_branch="")

    def test_malformed_base_sha(self) -> None:
        for bad in ("", "xyz1234", "abc12", "a" * 65):
            with self.subTest(bad=bad):
                self.assert_rejected(base_sha=bad)

    def test_malformed_head_sha(self) -> None:
        self.assert_rejected(head_sha="not-a-sha")

    def test_malformed_remote_head(self) -> None:
        self.assert_rejected(remote_head_sha="zzzzzzz")

    def test_tracking_branch_requires_remote_head(self) -> None:
        self.assert_rejected(remote_head_sha=None)

    def test_no_tracking_branch_rejects_remote_head(self) -> None:
        self.assert_rejected(sync_status=SyncStatus.NO_TRACKING_BRANCH)

    def test_excluded_category_requires_reason(self) -> None:
        for name in ("committed", "staged", "unstaged", "untracked"):
            with self.subTest(category=name):
                self.assert_rejected(**{name: CategoryScope(included=False)})

    def test_empty_reason_rejected(self) -> None:
        for reason in ("", "   ", "\t\n"):
            with self.subTest(reason=reason):
                self.assert_rejected(unstaged=CategoryScope(included=False, reason=reason))

    def test_in_sync_requires_matching_remote_head(self) -> None:
        self.assert_rejected(sync_status=SyncStatus.IN_SYNC, remote_head_sha=BASE_SHA)

    def test_in_sync_accepts_abbreviated_and_full_forms_of_one_commit(self) -> None:
        make_target(head_sha=HEAD_SHA, remote_head_sha=HEAD_SHA[:7].upper())
        make_target(head_sha=HEAD_SHA[:7], remote_head_sha=HEAD_SHA)

    def test_diverged_may_have_different_remote_head(self) -> None:
        make_target(sync_status=SyncStatus.DIVERGED, remote_head_sha=BASE_SHA)

    def test_included_staged_requires_fingerprint(self) -> None:
        self.assert_rejected(staged=CategoryScope(included=True))

    def test_fingerprint_must_be_sha256_hex(self) -> None:
        for bad in ("abc1234", "g" * 64, "A" * 64, EMPTY_SHA256 + "0"):
            with self.subTest(bad=bad):
                self.assert_rejected(staged=CategoryScope(included=True, fingerprint=bad))

    def test_unstaged_and_untracked_never_carry_fingerprint(self) -> None:
        for name in ("committed", "unstaged", "untracked"):
            with self.subTest(category=name):
                self.assert_rejected(
                    **{name: CategoryScope(included=True, fingerprint=EMPTY_SHA256)}
                )


class ReviewedStateProjectionTests(unittest.TestCase):
    def test_projection_equals_reviewed_state(self) -> None:
        self.assertEqual(
            make_target().to_reviewed_state(),
            ReviewedState(
                staged_fingerprint=EMPTY_SHA256, base_sha=BASE_SHA, head_sha=HEAD_SHA
            ),
        )

    def test_projection_tracks_staged_fingerprint(self) -> None:
        raw = b":100644 100644 1111111 2222222 M\0f\0"
        target = make_target(staged=staged_scope_from_raw_diff(raw))
        self.assertNotEqual(target.to_reviewed_state(), make_target().to_reviewed_state())

    def test_unstaged_and_untracked_do_not_affect_projection(self) -> None:
        other = make_target(unstaged=CategoryScope.excluded("x"))
        self.assertEqual(other.to_reviewed_state(), make_target().to_reviewed_state())

    def test_projection_without_fingerprint_is_rejected(self) -> None:
        target = make_target(staged=CategoryScope.excluded("not requested"))
        with self.assertRaises(LocalReviewTargetError):
            target.to_reviewed_state()

    def test_target_is_immutable(self) -> None:
        with self.assertRaises(dataclasses.FrozenInstanceError):
            make_target().head_sha = BASE_SHA  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
