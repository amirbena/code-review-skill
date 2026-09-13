#!/usr/bin/env python3
"""Existing-behavior ownership, related-changes-as-one-unit, and
failure/retry/recovery ownership semantics.

Contract: shared/policies/review-scope.md ("Existing behavior ownership"
and "Related changes as one unit" sections) and
shared/policies/failure-retry-recovery.md, extracted from review-scope.md
(Issue #264); review-scope.md keeps a thin routing paragraph under its own
"Failure state, retry safety, and recovery" heading (see
test_review_scope_core_wiring.py for the reachability/routing checks that
span every extracted pass, and test_observability_and_metrics.py for the
observability-specific behavior owned by the same policy).
Prose checks only — there is deliberately no second implementation of the
rules (see policies/skill-development-policy.md, "Runbook Design").
"""

from __future__ import annotations

import unittest

from tests.support.paths import REPO_ROOT
from tests.support.policy_docs import REVIEW_SCOPE
from tests.support.policy_docs import extract_section as _section
from tests.support.policy_docs import load_normalized_text as _text

FAILURE_RETRY_RECOVERY = REPO_ROOT / "shared/policies/failure-retry-recovery.md"


class OwnershipReuseIsTargetedTests(unittest.TestCase):
    """(shared semantics) ownership/reuse remains targeted, not generic
    DRY auditing."""

    def setUp(self) -> None:
        self.section = _section(
            _text(REVIEW_SCOPE),
            "## Existing behavior ownership",
            "## Failure state, retry safety, and recovery",
        )

    def test_search_is_scoped_to_blast_radius(self) -> None:
        self.assertIn("scoped to the current delta's realistic blast radius", self.section)

    def test_generic_dry_is_explicitly_disclaimed(self) -> None:
        self.assertIn("not generic", self.section)
        self.assertIn("not a repository-wide", self.section)

    def test_finding_requires_a_real_risk_not_mere_duplication(self) -> None:
        self.assertIn(
            "Raise a finding only when the evidence supports a real "
            "consistency, correctness, or maintainability risk",
            self.section,
        )


class FailureRetryRecoverySignalTriggeredTests(unittest.TestCase):
    """(shared semantics) failure/retry/recovery remains signal-triggered."""

    def setUp(self) -> None:
        self.section = _section(
            _text(FAILURE_RETRY_RECOVERY),
            "## Failure state, retry safety, and recovery",
        )

    def test_absent_a_signal_the_section_does_not_apply(self) -> None:
        self.assertIn(
            "Absent such a signal, this section does not apply and requires no action",
            self.section,
        )

    def test_not_an_exhaustive_checklist(self) -> None:
        self.assertIn(
            "does not require enumerating every failure point in every review",
            self.section,
        )

    def test_recovery_must_be_evidenced_not_assumed(self) -> None:
        self.assertIn(
            'never accepted merely because "another process will eventually '
            'fix it," with no evidence that such a process exists',
            self.section,
        )


class ContractExceptionBlastRadiusTests(unittest.TestCase):
    """(shared semantics) contract/exception analysis follows actual
    callers/consumers within justified blast radius."""

    def setUp(self) -> None:
        self.section = _section(
            _text(REVIEW_SCOPE),
            "## Related changes as one unit",
            "## Existing behavior ownership",
        )

    def test_caller_visible_changes_are_followed_to_consumers(self) -> None:
        self.assertIn(
            "following a changed return value, exception, status/state "
            "value, or event/message to its actual callers or consumers "
            "within the diff's blast radius",
            self.section,
        )

    def test_swallowed_translated_and_fallback_exceptions_are_named(self) -> None:
        self.assertIn("swallowed", self.section)
        self.assertIn("translated/wrapped", self.section)
        self.assertIn("fallback value that can", self.section)


if __name__ == "__main__":
    unittest.main()
