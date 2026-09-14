"""Adversarial publication-boundary tests for the Reviewer Brief (Issue #304).

These deliberately try to smuggle private Reviewer Brief content into the
GitHub-bound publication payload (review body, inline comments, and the
APPROVE / REQUEST_CHANGES / COMMENT event) and assert it is absent every
time. Canonical behavior:
skills/github-pr-review/policies/reviewer-brief.md, "Never published to
GitHub"; skills/github-pr-review/policies/review-output.md, "Private
Reviewer Brief (never published)".
"""

from __future__ import annotations

import inspect
import unittest

from tests.reference.review.reviewer_brief import (
    FinalizedReview,
    Finding,
    ReviewerBrief,
    Severity,
    Verdict,
    build_publication_payload,
    compose_reviewer_brief,
)

SECRET_BRIEF_MARKER = "REVIEWER-BRIEF-ONLY-MARKER-4f2c9a"


def _review_with_secret_marker_findings() -> FinalizedReview:
    # Even the finding text itself never contains brief-only content in a
    # real review; used here only to prove the marker doesn't leak through
    # unrelated fields either.
    return FinalizedReview(
        findings=(
            Finding("F1", Severity.P1, "Ordering not preserved", "src/lookup.py:12"),
        ),
        verdict=Verdict.CHANGES_REQUIRED,
        coverage_complete=True,
        reviewed_sha="deadbee",
    )


def _brief_with_marker() -> ReviewerBrief:
    review = _review_with_secret_marker_findings()
    return compose_reviewer_brief(
        review,
        what_changed=f"Change summary containing {SECRET_BRIEF_MARKER}.",
        user_provided_focus=f"User focus containing {SECRET_BRIEF_MARKER}.",
        reviewer_derived_focus=[
            f"Reviewer-derived bullet with {SECRET_BRIEF_MARKER}.",
            "Second bullet.",
        ],
        open_questions=[f"Open question with {SECRET_BRIEF_MARKER}."],
    )


class SignatureCannotAcceptABriefTests(unittest.TestCase):
    """The strongest form of the guarantee: it is not merely that nobody
    currently passes the brief in — the function has no parameter that
    could carry it."""

    def test_build_publication_payload_has_no_brief_parameter(self) -> None:
        sig = inspect.signature(build_publication_payload)
        for name, param in sig.parameters.items():
            self.assertNotIn("brief", name.lower())
            self.assertNotEqual(
                param.kind,
                inspect.Parameter.VAR_KEYWORD,
                "build_publication_payload must not accept **kwargs — a "
                "catch-all would let a ReviewerBrief be smuggled in under "
                "any key",
            )

    def test_build_publication_payload_rejects_a_brief_positionally(self) -> None:
        review = _review_with_secret_marker_findings()
        brief = _brief_with_marker()
        with self.assertRaises(TypeError):
            build_publication_payload(review, "COMMENT", brief)  # type: ignore[call-arg,misc]

    def test_build_publication_payload_rejects_a_brief_as_keyword(self) -> None:
        review = _review_with_secret_marker_findings()
        brief = _brief_with_marker()
        with self.assertRaises(TypeError):
            build_publication_payload(review, event="COMMENT", brief=brief)  # type: ignore[call-arg]


class MarkerAbsentFromReviewBodyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.review = _review_with_secret_marker_findings()
        self.brief = _brief_with_marker()  # composed but never passed in below

    def test_marker_present_in_brief_render(self) -> None:
        # Sanity check the adversarial fixture actually carries the marker,
        # so an absence below is a real negative result, not a vacuous one.
        self.assertIn(SECRET_BRIEF_MARKER, self.brief.render())

    def test_marker_absent_from_review_body_for_every_event(self) -> None:
        for event in ("APPROVE", "REQUEST_CHANGES", "COMMENT"):
            payload = build_publication_payload(self.review, event)
            self.assertNotIn(
                SECRET_BRIEF_MARKER,
                payload.body,
                f"Reviewer Brief content leaked into the review body for event={event}",
            )

    def test_marker_absent_from_inline_comments_for_every_event(self) -> None:
        for event in ("APPROVE", "REQUEST_CHANGES", "COMMENT"):
            payload = build_publication_payload(self.review, event)
            for comment in payload.inline_comments:
                self.assertNotIn(
                    SECRET_BRIEF_MARKER,
                    comment.body,
                    f"Reviewer Brief content leaked into an inline comment for event={event}",
                )

    def test_marker_absent_from_the_event_field_itself(self) -> None:
        for event in ("APPROVE", "REQUEST_CHANGES", "COMMENT"):
            payload = build_publication_payload(self.review, event)
            self.assertNotIn(SECRET_BRIEF_MARKER, payload.event)


class CleanReviewApproveBoundaryTests(unittest.TestCase):
    """APPROVE is the highest-trust positive event; prove it carries no
    brief content even on the simplest, clean-review path."""

    def test_approve_payload_on_clean_review_has_no_brief_content(self) -> None:
        review = FinalizedReview(
            findings=(),
            verdict=Verdict.CLEAN,
            coverage_complete=True,
            reviewed_sha="a1b2c3d",
        )
        brief = compose_reviewer_brief(
            review,
            what_changed=f"Adds a health endpoint. {SECRET_BRIEF_MARKER}",
            user_provided_focus=None,
            reviewer_derived_focus=["a", "b"],
        )
        self.assertIn(SECRET_BRIEF_MARKER, brief.render())
        payload = build_publication_payload(review, "APPROVE")
        self.assertNotIn(SECRET_BRIEF_MARKER, payload.body)
        self.assertEqual(payload.inline_comments, ())


class RequestChangesBoundaryTests(unittest.TestCase):
    def test_request_changes_payload_has_no_brief_content(self) -> None:
        review = _review_with_secret_marker_findings()
        _brief_with_marker()
        payload = build_publication_payload(review, "REQUEST_CHANGES")
        self.assertNotIn(SECRET_BRIEF_MARKER, payload.body)
        for c in payload.inline_comments:
            self.assertNotIn(SECRET_BRIEF_MARKER, c.body)


class InformationalCommentBoundaryTests(unittest.TestCase):
    """Self-review publishes the same body as an informational COMMENT —
    still no brief content."""

    def test_comment_event_payload_has_no_brief_content(self) -> None:
        review = _review_with_secret_marker_findings()
        _brief_with_marker()
        payload = build_publication_payload(review, "COMMENT")
        self.assertNotIn(SECRET_BRIEF_MARKER, payload.body)


class BriefTypeNeverAppearsInPayloadTypeTests(unittest.TestCase):
    """Belt-and-suspenders: even if a future change added a field, prove
    today's PublicationPayload has no ReviewerBrief-typed attribute at
    all."""

    def test_publication_payload_dataclass_fields_exclude_reviewer_brief_type(
        self,
    ) -> None:
        import dataclasses

        from tests.reference.review.reviewer_brief import PublicationPayload

        for f in dataclasses.fields(PublicationPayload):
            self.assertNotEqual(f.type, "ReviewerBrief")
            self.assertNotIn("brief", f.name.lower())


if __name__ == "__main__":
    unittest.main()
