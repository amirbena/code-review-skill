#!/usr/bin/env python3
"""Coverage for the verdict-consistency comparator (verdict_consistency.py).

Contract: shared/policies/verdict-consistency.md. Regression focus: a
P0/P1-derived blocking decision can never proceed through a clean/approve
rendered signal or submitted event, and vice versa; REVIEW INCOMPLETE and
a missing formal event are sanctioned pass-throughs, never mismatches.
"""

from __future__ import annotations

import inspect
import re
import unittest
from pathlib import Path

from tests.reference.review import decision_semantics as ds
from tests.reference.review import verdict_consistency as vc
from tests.support.paths import REPO_ROOT

VERDICT_CONSISTENCY_POLICY = REPO_ROOT / "shared" / "policies" / "verdict-consistency.md"


def _text(path: Path) -> str:
    raw = path.read_text(encoding="utf-8").replace("**", "").replace("`", "")
    return re.sub(r"\s+", " ", raw)


class ConsistentRenderedSignalTests(unittest.TestCase):
    """A rendered signal that agrees with the mechanical decision passes."""

    def test_clean_decision_with_review_clean_is_consistent(self) -> None:
        result = vc.check_rendered_signal(
            ds.Decision.CLEAN.value, False, vc.RenderedSignal.REVIEW_CLEAN
        )
        self.assertEqual(result.verdict, vc.Verdict.CONSISTENT)

    def test_clean_decision_with_approve_is_consistent(self) -> None:
        result = vc.check_rendered_signal(
            ds.Decision.CLEAN.value, False, vc.RenderedSignal.APPROVE
        )
        self.assertEqual(result.verdict, vc.Verdict.CONSISTENT)

    def test_blocking_decision_with_changes_required_is_consistent(self) -> None:
        result = vc.check_rendered_signal(
            ds.Decision.CHANGES_REQUIRED.value, False, vc.RenderedSignal.CHANGES_REQUIRED
        )
        self.assertEqual(result.verdict, vc.Verdict.CONSISTENT)

    def test_blocking_decision_with_request_changes_is_consistent(self) -> None:
        result = vc.check_rendered_signal(
            ds.Decision.CHANGES_REQUIRED.value, False, vc.RenderedSignal.REQUEST_CHANGES
        )
        self.assertEqual(result.verdict, vc.Verdict.CONSISTENT)


class MismatchedRenderedSignalTests(unittest.TestCase):
    """A P0/P1-derived blocking decision cannot proceed through a
    clean/approve rendered signal, and a clean-derived decision cannot
    proceed through a blocking/request-changes rendered signal."""

    def test_blocking_decision_with_review_clean_is_inconsistent(self) -> None:
        result = vc.check_rendered_signal(
            ds.Decision.CHANGES_REQUIRED.value, False, vc.RenderedSignal.REVIEW_CLEAN
        )
        self.assertEqual(result.verdict, vc.Verdict.INCONSISTENT)

    def test_blocking_decision_with_approve_is_inconsistent(self) -> None:
        result = vc.check_rendered_signal(
            ds.Decision.CHANGES_REQUIRED.value, False, vc.RenderedSignal.APPROVE
        )
        self.assertEqual(result.verdict, vc.Verdict.INCONSISTENT)

    def test_clean_decision_with_changes_required_is_inconsistent(self) -> None:
        result = vc.check_rendered_signal(
            ds.Decision.CLEAN.value, False, vc.RenderedSignal.CHANGES_REQUIRED
        )
        self.assertEqual(result.verdict, vc.Verdict.INCONSISTENT)

    def test_clean_decision_with_request_changes_is_inconsistent(self) -> None:
        result = vc.check_rendered_signal(
            ds.Decision.CLEAN.value, False, vc.RenderedSignal.REQUEST_CHANGES
        )
        self.assertEqual(result.verdict, vc.Verdict.INCONSISTENT)


class ReviewIncompleteCarveOutTests(unittest.TestCase):
    """REVIEW INCOMPLETE is a sanctioned pass-through, never a mismatch,
    regardless of what the mechanical derivation alone would produce."""

    def test_incomplete_coverage_with_review_incomplete_signal_is_consistent(self) -> None:
        for decision in (ds.Decision.CLEAN.value, ds.Decision.CHANGES_REQUIRED.value):
            with self.subTest(decision=decision):
                result = vc.check_rendered_signal(
                    decision, True, vc.RenderedSignal.REVIEW_INCOMPLETE
                )
                self.assertEqual(result.verdict, vc.Verdict.CONSISTENT)

    def test_incomplete_coverage_with_clean_signal_is_inconsistent(self) -> None:
        result = vc.check_rendered_signal(
            ds.Decision.CLEAN.value, True, vc.RenderedSignal.REVIEW_CLEAN
        )
        self.assertEqual(result.verdict, vc.Verdict.INCONSISTENT)

    def test_complete_coverage_with_review_incomplete_signal_is_inconsistent(self) -> None:
        result = vc.check_rendered_signal(
            ds.Decision.CLEAN.value, False, vc.RenderedSignal.REVIEW_INCOMPLETE
        )
        self.assertEqual(result.verdict, vc.Verdict.INCONSISTENT)


class SubmittedEventTests(unittest.TestCase):
    """ACTIVE publication cannot submit an API event inconsistent with
    the finalized decision."""

    def test_clean_decision_with_approve_event_is_consistent(self) -> None:
        result = vc.check_submitted_event(
            ds.Decision.CLEAN.value, False, vc.SubmittedEvent.APPROVE
        )
        self.assertEqual(result.verdict, vc.Verdict.CONSISTENT)

    def test_blocking_decision_with_request_changes_event_is_consistent(self) -> None:
        result = vc.check_submitted_event(
            ds.Decision.CHANGES_REQUIRED.value, False, vc.SubmittedEvent.REQUEST_CHANGES
        )
        self.assertEqual(result.verdict, vc.Verdict.CONSISTENT)

    def test_blocking_decision_with_approve_event_is_inconsistent(self) -> None:
        result = vc.check_submitted_event(
            ds.Decision.CHANGES_REQUIRED.value, False, vc.SubmittedEvent.APPROVE
        )
        self.assertEqual(result.verdict, vc.Verdict.INCONSISTENT)

    def test_clean_decision_with_request_changes_event_is_inconsistent(self) -> None:
        result = vc.check_submitted_event(
            ds.Decision.CLEAN.value, False, vc.SubmittedEvent.REQUEST_CHANGES
        )
        self.assertEqual(result.verdict, vc.Verdict.INCONSISTENT)

    def test_incomplete_coverage_with_any_formal_event_is_inconsistent(self) -> None:
        for event in (vc.SubmittedEvent.APPROVE, vc.SubmittedEvent.REQUEST_CHANGES):
            with self.subTest(event=event):
                result = vc.check_submitted_event(
                    ds.Decision.CLEAN.value, True, event
                )
                self.assertEqual(result.verdict, vc.Verdict.INCONSISTENT)


class NoFormalEventCarveOutTests(unittest.TestCase):
    """PASSIVE/self-review flows do not require a nonexistent formal
    event -- only the rendered report signal is checked in that case."""

    def test_missing_event_is_always_consistent(self) -> None:
        for decision in (ds.Decision.CLEAN.value, ds.Decision.CHANGES_REQUIRED.value):
            for incomplete in (False, True):
                with self.subTest(decision=decision, incomplete=incomplete):
                    result = vc.check_submitted_event(decision, incomplete, None)
                    self.assertEqual(result.verdict, vc.Verdict.CONSISTENT)

    def test_self_review_comment_event_is_always_consistent(self) -> None:
        for decision in (ds.Decision.CLEAN.value, ds.Decision.CHANGES_REQUIRED.value):
            for incomplete in (False, True):
                with self.subTest(decision=decision, incomplete=incomplete):
                    result = vc.check_submitted_event(
                        decision, incomplete, vc.SubmittedEvent.COMMENT
                    )
                    self.assertEqual(result.verdict, vc.Verdict.CONSISTENT)


class GovernanceInvariantTests(unittest.TestCase):
    """No independent, overridable decision path can be introduced into
    this read-only comparator."""

    def test_no_function_accepts_an_override_or_force_parameter(self) -> None:
        for name, obj in inspect.getmembers(vc):
            if not inspect.isfunction(obj):
                continue
            for param_name in inspect.signature(obj).parameters:
                lowered = param_name.lower()
                for fragment in vc.PROHIBITED_OVERRIDE_PARAM_FRAGMENTS:
                    self.assertNotIn(
                        fragment,
                        lowered,
                        f"{name}() must not accept a decision-override parameter, "
                        f"found: {param_name}",
                    )

    def test_no_function_accepts_a_correction_or_provisional_parameter(self) -> None:
        for name, obj in inspect.getmembers(vc):
            if not inspect.isfunction(obj):
                continue
            for param_name in inspect.signature(obj).parameters:
                lowered = param_name.lower()
                for fragment in vc.PROHIBITED_CORRECTION_FRAGMENTS:
                    self.assertNotIn(
                        fragment,
                        lowered,
                        f"{name}() must not accept a correction/provisional "
                        f"decision parameter, found: {param_name}",
                    )

    def test_prohibited_fragment_sets_match_decision_semantics(self) -> None:
        # One canonical governance vocabulary, never forked per module.
        self.assertEqual(
            vc.PROHIBITED_OVERRIDE_PARAM_FRAGMENTS, ds.PROHIBITED_OVERRIDE_PARAM_FRAGMENTS
        )
        self.assertEqual(
            vc.PROHIBITED_CORRECTION_FRAGMENTS, ds.PROHIBITED_CORRECTION_FRAGMENTS
        )

    def test_comparator_output_has_exactly_two_shapes(self) -> None:
        labels = {member.value for member in vc.Verdict}
        self.assertEqual(labels, {"consistent", "inconsistent"})


class PolicyProseTests(unittest.TestCase):
    """Pin the policy's withhold-and-report and non-goal prose, per the
    established severity.md/decision_semantics.py pinning pattern."""

    def test_policy_requires_withhold_and_report_never_self_correct(self) -> None:
        text = _text(VERDICT_CONSISTENCY_POLICY)
        self.assertIn(
            "withhold the protected render or publication action, and report "
            "an internal-consistency failure in its place",
            text,
        )
        self.assertIn(
            "never self-corrects the mismatched signal",
            text,
        )
        self.assertIn(
            "never warns and proceeds anyway",
            text,
        )

    def test_policy_declares_one_canonical_comparator(self) -> None:
        text = _text(VERDICT_CONSISTENCY_POLICY)
        self.assertIn(
            "This is the single canonical verdict-consistency comparator",
            text,
        )


if __name__ == "__main__":
    unittest.main()
