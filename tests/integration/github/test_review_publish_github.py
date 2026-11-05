"""review-publish-github guarantees against a minimal in-memory PR (#844).

The fake enforces only what GitHub enforces; the Skill's own rules are
checked as text in tests/unit/review/core. Run with:
    python3 -m unittest tests.integration.github.test_review_publish_github
"""

from __future__ import annotations

import unittest

from tests.support.pr_publication_fake import FakePr, Forbidden, UnprocessableAnchor

HEAD = "a" * 40
COMMENT = {"path": "src/a.py", "line": 10, "body": "[P1] t"}


def submit(pr: FakePr, event: str = "COMMENT", comments=(COMMENT,), commit_id: str = HEAD):
    return pr.submit_review(event=event, body="## Review", comments=list(comments), commit_id=commit_id)


class SelfReviewTests(unittest.TestCase):
    def test_comment_is_the_only_event_an_author_can_submit(self) -> None:
        pr = FakePr(viewer="alice")
        self.assertEqual(submit(pr)["event"], "COMMENT")
        for event in ("APPROVE", "REQUEST_CHANGES"):
            with self.subTest(event=event), self.assertRaises(Forbidden):
                submit(pr, event)
        self.assertEqual(pr.writes, 1)

    def test_an_independent_reviewer_can_approve(self) -> None:
        self.assertEqual(submit(FakePr(), "APPROVE")["event"], "APPROVE")


class StaleHeadTests(unittest.TestCase):
    def test_a_moved_head_is_observable_before_submit(self) -> None:
        pr = FakePr()
        reviewed = pr.get_head()
        pr.head_sha = "b" * 40
        self.assertNotEqual(pr.get_head(), reviewed)
        self.assertEqual(pr.writes, 0)

    def test_the_submitted_review_records_the_reviewed_commit(self) -> None:
        self.assertEqual(submit(FakePr())["commit_id"], HEAD)


class PermissionTests(unittest.TestCase):
    def test_denied_permission_writes_nothing(self) -> None:
        pr = FakePr(can_review=False)
        with self.assertRaises(Forbidden):
            submit(pr, "COMMENT")
        self.assertEqual((pr.writes, pr.reviews), (0, []))


class BatchedSubmissionTests(unittest.TestCase):
    def test_one_call_carries_summary_and_inline_comments(self) -> None:
        pr = FakePr()
        review = submit(pr, comments=[COMMENT, {**COMMENT, "line": 11}])
        self.assertEqual((pr.writes, len(review["comments"]), review["body"]), (1, 2, "## Review"))

    def test_a_rejected_anchor_leaves_no_partial_review(self) -> None:
        pr = FakePr()
        with self.assertRaises(UnprocessableAnchor):
            submit(pr, comments=[COMMENT, {**COMMENT, "line": 99}])
        self.assertEqual(pr.writes, 0)
        submit(pr, comments=[COMMENT])
        self.assertEqual(pr.writes, 1)


if __name__ == "__main__":
    unittest.main()
