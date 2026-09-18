"""Regression tests for the #134 review-base policy compliance reference
model.

Exercises tests/reference/review/review_base_policy.py against
docs/review-base-policy/review-base-policy-model.md's acceptance-criteria
cases: a violating base emits one P0 naming both branches; a satisfying
base emits nothing; an unresolvable base fails closed; HEAD is never
substituted as the repository-resolved review base; and a legitimate
stacked-PR intermediate layer is never flagged.
"""

import unittest

from tests.reference.review.review_base_policy import (
    ReviewBaseResolution,
    check_review_base_compliance,
    resolve_repository_review_base,
)


class RepositoryReviewBaseResolutionTests(unittest.TestCase):
    """§3: ranked resolution signals."""

    def test_explicit_statement_ranks_above_default_branch(self) -> None:
        resolution = resolve_repository_review_base(
            explicit_statement_branch="develop", default_branch="main"
        )
        self.assertTrue(resolution.resolved)
        self.assertEqual(resolution.branch, "develop")
        self.assertEqual(resolution.source, "explicit_statement")

    def test_default_branch_used_absent_explicit_statement(self) -> None:
        resolution = resolve_repository_review_base(default_branch="main")
        self.assertTrue(resolution.resolved)
        self.assertEqual(resolution.branch, "main")
        self.assertEqual(resolution.source, "default_branch")

    def test_unresolved_when_neither_signal_available(self) -> None:
        resolution = resolve_repository_review_base()
        self.assertFalse(resolution.resolved)
        self.assertIsNone(resolution.branch)

    def test_unresolved_when_default_branch_signal_ambiguous(self) -> None:
        resolution = resolve_repository_review_base(
            default_branch="main", default_branch_ambiguous=True
        )
        self.assertFalse(resolution.resolved)


class ViolationCheckTests(unittest.TestCase):
    """§4/§5/§6: the violation check, fail-closed rule, and one-P0 finding
    naming both branches."""

    def test_violating_base_emits_one_p0_naming_both_branches(self) -> None:
        resolution = ReviewBaseResolution(resolved=True, branch="main", source="default_branch")
        finding = check_review_base_compliance(
            base_under_review="feature/unrelated", repository_resolved_base=resolution
        )
        self.assertIsNotNone(finding)
        self.assertEqual(finding.severity, "P0")
        self.assertEqual(finding.base_under_review, "feature/unrelated")
        self.assertEqual(finding.required_base, "main")

    def test_compliant_base_emits_no_finding(self) -> None:
        resolution = ReviewBaseResolution(resolved=True, branch="main", source="default_branch")
        finding = check_review_base_compliance(
            base_under_review="main", repository_resolved_base=resolution
        )
        self.assertIsNone(finding)

    def test_unresolved_repository_base_fails_closed(self) -> None:
        resolution = resolve_repository_review_base()
        finding = check_review_base_compliance(
            base_under_review="feature/unrelated", repository_resolved_base=resolution
        )
        self.assertIsNone(finding)

    def test_unresolved_base_under_review_fails_closed_head_not_substituted(self) -> None:
        # Models a stack whose own topology could not be resolved reliably
        # (base_under_review=None), and a caller that might otherwise be
        # tempted to substitute HEAD or another convenient local value —
        # the reference model has no such fallback path at all, so the
        # only observable outcome is "no finding."
        resolution = ReviewBaseResolution(resolved=True, branch="main", source="default_branch")
        finding = check_review_base_compliance(
            base_under_review=None, repository_resolved_base=resolution
        )
        self.assertIsNone(finding)

    def test_legitimate_stack_parent_is_never_flagged(self) -> None:
        resolution = ReviewBaseResolution(resolved=True, branch="main", source="default_branch")
        finding = check_review_base_compliance(
            base_under_review="feature/pr-a",
            repository_resolved_base=resolution,
            is_legitimate_stack_parent=True,
        )
        self.assertIsNone(finding)


if __name__ == "__main__":
    unittest.main()
