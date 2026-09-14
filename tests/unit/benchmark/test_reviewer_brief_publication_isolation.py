"""Publication-isolation benchmark for the private Reviewer Brief
(Issue #309, depends on #304). Proves -- against the GitHub-bound
artifact itself, never against the caller-facing object alone -- that no
Reviewer Brief text or field reaches the consolidated GitHub review body
or inline comments, per
skills/github-pr-review/policies/reviewer-brief.md, "Never published to
GitHub", and the existing documentation-contract coverage in
tests/policy/review/test_reviewer_brief_docs.py (which asserts the
*policy prose* states the boundary; this module asserts the boundary
holds over concrete field values for concrete cases, including a
deliberately-leaking negative fixture that proves the check itself would
catch a real regression rather than vacuously passing).
"""

from __future__ import annotations

import unittest

from tests.reference.benchmark.reviewer_brief_fixtures import (
    ALL_CASES,
    ReviewerBriefCase,
)

_BRIEF_MARKERS = ("Reviewer Brief", "Manual review focus", "User-provided focus")


def github_bound_text(case: ReviewerBriefCase) -> str:
    """The complete GitHub-bound representation for one case: the review
    body plus every inline comment, concatenated. This -- not the
    caller-facing brief object -- is what a leak check must inspect."""
    return "\n".join((case.github_review_body, *case.github_inline_comments))


def brief_leaked_into_github(case: ReviewerBriefCase) -> list[str]:
    """Return every Reviewer Brief field value (and structural marker)
    found inside the GitHub-bound text for this case. Empty means clean."""
    github_text = github_bound_text(case)
    leaked: list[str] = []
    for field_value in case.brief_field_strings():
        if field_value and field_value in github_text:
            leaked.append(field_value)
    for marker in _BRIEF_MARKERS:
        if marker in github_text:
            leaked.append(marker)
    return leaked


class NoLeakageIntoGithubPayloadTests(unittest.TestCase):
    """Explicitly inspects case.github_review_body and
    case.github_inline_comments -- the GitHub-bound representation -- for
    every fixture, not the private brief object."""

    def test_no_brief_field_value_appears_in_github_review_body(self) -> None:
        for case in ALL_CASES:
            with self.subTest(case=case.case_id):
                for field_value in case.brief_field_strings():
                    if not field_value:
                        continue
                    self.assertNotIn(field_value, case.github_review_body)

    def test_no_brief_field_value_appears_in_any_inline_comment(self) -> None:
        for case in ALL_CASES:
            for comment in case.github_inline_comments:
                with self.subTest(case=case.case_id, comment=comment):
                    for field_value in case.brief_field_strings():
                        if not field_value:
                            continue
                        self.assertNotIn(field_value, comment)

    def test_no_reviewer_brief_structural_marker_in_github_payload(self) -> None:
        for case in ALL_CASES:
            with self.subTest(case=case.case_id):
                github_text = github_bound_text(case)
                for marker in _BRIEF_MARKERS:
                    self.assertNotIn(marker, github_text)

    def test_leak_checker_reports_clean_for_every_real_case(self) -> None:
        for case in ALL_CASES:
            with self.subTest(case=case.case_id):
                self.assertEqual(brief_leaked_into_github(case), [])


class PassiveReviewNeverPublishesTests(unittest.TestCase):
    """Passive review publishes nothing at all, so the isolation guarantee
    is automatically satisfied there (reviewer-brief.md, "Composition
    with invocation modes") -- but the brief must still be present for
    the caller."""

    def test_passive_case_has_empty_github_payload(self) -> None:
        for case in ALL_CASES:
            if case.mode != "passive":
                continue
            with self.subTest(case=case.case_id):
                self.assertEqual(case.github_inline_comments, ())

    def test_passive_case_still_returns_a_populated_brief(self) -> None:
        for case in ALL_CASES:
            if case.mode != "passive":
                continue
            with self.subTest(case=case.case_id):
                self.assertTrue(case.what_changed.strip())
                self.assertGreaterEqual(len(case.manual_review_focus), 2)


class ActiveReviewCallerStillGetsTheBriefTests(unittest.TestCase):
    """Active publication excludes the brief from GitHub, but the brief
    must still be available to the caller alongside the published
    result -- a test that only checked the caller-facing object would
    miss a regression that publishes AND drops the brief, or that leaks
    AND still returns a brief; both must be checked together per case."""

    def test_active_case_has_both_a_github_payload_and_a_populated_brief(self) -> None:
        for case in ALL_CASES:
            if case.mode != "active":
                continue
            with self.subTest(case=case.case_id):
                self.assertTrue(case.github_review_body.strip())
                self.assertTrue(case.what_changed.strip())
                self.assertGreaterEqual(len(case.manual_review_focus), 2)


class LeakCheckerCatchesARealLeakTests(unittest.TestCase):
    """A leakage assertion that could never fail is worthless. This
    proves brief_leaked_into_github() actually detects a regression where
    Reviewer Brief content is folded into the GitHub-bound payload --
    the exact bug shape #309 exists to catch -- using a deliberately
    broken fixture, never one of the real corpus cases above."""

    def test_leak_checker_flags_brief_text_folded_into_review_body(self) -> None:
        leaky = ReviewerBriefCase(
            case_id="__negative_canary_brief_folded_into_review_body__",
            covers=frozenset(),
            mode="active",
            human_review_output=False,
            decision="changes-required",
            user_focus_input=None,
            what_changed="Adds an export endpoint.",
            user_provided_focus_field="none provided",
            manual_review_focus=(
                "Confirm the export endpoint enforces the same auth as the "
                "read endpoint it wraps.",
                "Check the exported file name for path traversal.",
            ),
            open_questions=None,
            independent_focus_present=True,
            references_finalized_finding=False,
            # The bug under test: the review body wrongly includes the
            # private brief section verbatim.
            github_review_body=(
                "## Summary\nChanges required.\n\n"
                "## Reviewer Brief\n"
                "- **What changed:** Adds an export endpoint.\n"
                "- **Manual review focus:**\n"
                "  - Confirm the export endpoint enforces the same auth as "
                "the read endpoint it wraps.\n"
            ),
            github_inline_comments=(),
        )
        leaked = brief_leaked_into_github(leaky)
        self.assertNotEqual(leaked, [], "leak checker failed to catch a real leak")
        self.assertIn("Reviewer Brief", leaked)
        self.assertIn(leaky.what_changed, leaked)

    def test_leak_checker_flags_brief_bullet_folded_into_an_inline_comment(self) -> None:
        leaky = ReviewerBriefCase(
            case_id="__negative_canary_brief_folded_into_inline_comment__",
            covers=frozenset(),
            mode="active",
            human_review_output=False,
            decision="changes-required",
            user_focus_input=None,
            what_changed="Adds an export endpoint.",
            user_provided_focus_field="none provided",
            manual_review_focus=(
                "Confirm the export endpoint enforces the same auth as the "
                "read endpoint it wraps.",
                "Check the exported file name for path traversal.",
            ),
            open_questions=None,
            independent_focus_present=True,
            references_finalized_finding=False,
            github_review_body="## Summary\nChanges required.",
            github_inline_comments=(
                "F1 [P2] Missing auth check. Manual review focus: Confirm "
                "the export endpoint enforces the same auth as the read "
                "endpoint it wraps.",
            ),
        )
        leaked = brief_leaked_into_github(leaky)
        self.assertNotEqual(leaked, [])


if __name__ == "__main__":
    unittest.main()
