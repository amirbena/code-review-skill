"""review-publish-github publication paths against an in-memory PR fake (#844).

Contract: skills/review-publish-github/SKILL.md (S7). Run with:
    python3 -m unittest tests.integration.github.test_review_publish_github
"""

from __future__ import annotations

import unittest

from tests.reference.review import publish_github as pg
from tests.reference.review.publish_github import (
    CHANGES, CLEAN, INCOMPLETE, CoreResult, Event, ExistingComment, FakeGitHub, Finding, PrFacts, Status,
)

HEAD = "a" * 40
MOVED = "b" * 40
F1 = Finding("F1", "P1", "Off by one in pagination", "src/a.py", 10)
F2 = Finding("F2", "P1", "Missing retry on timeout", "src/b.py", None)
F3 = Finding("F3", "P2", "Misleading doc", "src/c.py", 99)


def pr(**kw) -> PrFacts:
    base = dict(author="alice", viewer="reviewer", head_sha=HEAD)
    base.update(kw)
    return PrFacts(**base)


def world(facts=None, **kw) -> FakeGitHub:
    return FakeGitHub(facts or pr(), changed={"src/a.py": {10, 11}, "src/b.py": {1}, "src/c.py": {1}}, **kw)


def core(decision=CLEAN, *findings) -> CoreResult:
    return CoreResult(decision, tuple(findings), HEAD)


def run(gh, c, **kw):
    return pg.publish(gh, c, user_asked_to_publish=kw.pop("asked", True), **kw)


class RequestGateTests(unittest.TestCase):
    def test_nothing_is_published_without_a_request(self) -> None:
        gh = world()
        out = run(gh, core(), asked=False)
        self.assertEqual(out.status, Status.NOT_REQUESTED)
        self.assertEqual(gh.writes, [])

    def test_auto_mode_alone_never_publishes(self) -> None:
        gh = world()
        out = run(gh, core(), asked=False, mode_is_auto=True)
        self.assertEqual((out.status, gh.writes), (Status.NOT_REQUESTED, []))


class SelfReviewTests(unittest.TestCase):
    def test_author_review_is_comment_only_even_when_clean(self) -> None:
        gh = world(pr(viewer="alice"))
        out = run(gh, core(CLEAN))
        self.assertEqual(out.event, Event.COMMENT)

    def test_author_review_with_blocking_findings_is_not_request_changes(self) -> None:
        gh = world(pr(viewer="alice"))
        out = run(gh, core(CHANGES, F1))
        self.assertEqual(out.event, Event.COMMENT)
        self.assertIn(CHANGES, out.submission.body)

    def test_shared_authority_counts_as_self(self) -> None:
        out = run(world(pr(shared_authority=True)), core(CLEAN))
        self.assertEqual(out.event, Event.COMMENT)

    def test_unresolvable_identity_fails_closed_to_comment(self) -> None:
        out = run(world(pr(viewer="")), core(CLEAN))
        self.assertEqual(out.event, Event.COMMENT)


class EventTests(unittest.TestCase):
    def test_independent_reviewer_events(self) -> None:
        self.assertEqual(run(world(), core(CLEAN)).event, Event.APPROVE)
        self.assertEqual(run(world(), core(CHANGES, F1)).event, Event.REQUEST_CHANGES)

    def test_incomplete_draft_and_unconfirmed_fork_are_comment(self) -> None:
        self.assertEqual(run(world(), core(INCOMPLETE)).event, Event.COMMENT)
        self.assertEqual(run(world(pr(draft=True)), core(CLEAN)).event, Event.COMMENT)
        self.assertEqual(run(world(pr(fork=True)), core(CLEAN)).event, Event.COMMENT)
        self.assertEqual(run(world(pr(fork=True, fork_upstream_confirmed=True)), core(CLEAN)).event, Event.APPROVE)


class StaleHeadTests(unittest.TestCase):
    def test_moved_head_aborts_and_never_approves(self) -> None:
        gh = world(head_reads=[MOVED])
        out = run(gh, core(CLEAN))
        self.assertEqual(out.status, Status.STALE_HEAD)
        self.assertEqual(gh.writes, [])

    def test_head_is_revalidated_after_placement_not_only_at_start(self) -> None:
        gh = world(head_reads=[MOVED])
        self.assertEqual(run(gh, core(CHANGES, F1)).status, Status.STALE_HEAD)


class PermissionTests(unittest.TestCase):
    def test_no_review_permission_publishes_nothing(self) -> None:
        gh = world(pr(can_review=False))
        out = run(gh, core(CHANGES, F1))
        self.assertEqual((out.status, gh.writes), (Status.PERMISSION_DENIED, []))

    def test_undeterminable_permission_fails_closed(self) -> None:
        gh = world(pr(can_review=None))
        self.assertEqual((run(gh, core(CLEAN)).status, gh.writes), (Status.PERMISSION_DENIED, []))

    def test_refused_event_is_reported_and_not_retried_stronger(self) -> None:
        gh = world(refuse_events=frozenset({Event.APPROVE}))
        out = run(gh, core(CLEAN))
        self.assertEqual((out.status, gh.writes), (Status.PERMISSION_DENIED, []))


class BatchedSubmissionTests(unittest.TestCase):
    def test_exactly_one_review_with_inline_and_summary_placement(self) -> None:
        gh = world()
        out = run(gh, core(CHANGES, F1, F2))
        self.assertEqual(len(gh.writes), 1)
        sub = gh.writes[0]
        self.assertEqual([(c.path, c.line) for c in sub.comments], [("src/a.py", 10)])
        self.assertIn("F2", sub.body)
        self.assertNotIn("Evidence: e", sub.body.split("### Findings")[1].split("**F2")[0])
        self.assertEqual(out.status, Status.SUBMITTED)

    def test_finding_outside_the_diff_goes_to_the_summary(self) -> None:
        gh = world()
        run(gh, core(CHANGES, F3))
        self.assertEqual(gh.writes[0].comments, ())
        self.assertIn("F3", gh.writes[0].body)

    def test_rejected_inline_location_moves_to_summary_in_one_retry(self) -> None:
        gh = world(reject_inline=frozenset({("src/a.py", 10)}))
        out = run(gh, core(CHANGES, F1))
        self.assertEqual(out.status, Status.SUBMITTED)
        self.assertEqual(len(gh.writes), 1)
        self.assertEqual(gh.writes[0].comments, ())
        self.assertIn("Evidence: e", gh.writes[0].body)


class ReconciliationTests(unittest.TestCase):
    def test_already_raised_finding_is_skipped(self) -> None:
        gh = world(comments=(ExistingComment("src/a.py", "off by one in pagination"),))
        out = run(gh, core(CHANGES, F1, F2))
        self.assertEqual(out.skipped_existing, 1)
        self.assertEqual(gh.writes[0].comments, ())

    def test_resolved_thread_whose_defect_returned_is_republished(self) -> None:
        gh = world(comments=(ExistingComment("src/a.py", F1.title, resolved=True, defect_present_at_head=True),))
        out = run(gh, core(CHANGES, F1))
        self.assertEqual(out.skipped_existing, 0)
        self.assertEqual(len(gh.writes[0].comments), 1)


if __name__ == "__main__":
    unittest.main()
