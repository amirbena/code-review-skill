"""Unit tests pinning the review-stopping-criteria reference model
(Issue #89).

Canonical behavior: ``shared/policies/review-stopping-criteria.md``.
"""

from __future__ import annotations

import unittest

from tests.reference.change_risk_signals import Depth
from tests.reference.review_stopping_criteria import (
    IncompleteReason,
    IncompleteTrigger,
    PartitionCompletion,
    PassResult,
    decision_label,
    evaluate_coverage,
)


class CoverageAggregationTests(unittest.TestCase):
    def test_all_passes_reaching_stop_condition_is_complete(self) -> None:
        result = evaluate_coverage(
            Depth.STANDARD,
            passes=(PassResult("review-scope", True), PassResult("change-risk", True)),
        )
        self.assertEqual(result.coverage, "complete")
        self.assertEqual(result.reasons, ())

    def test_insufficient_evidence_stop_condition_still_counts_as_reached(self) -> None:
        # review-scope.md, "Stop conditions": stopping because evidence was
        # insufficient is a valid terminal outcome, not a coverage gap.
        result = evaluate_coverage(
            Depth.ELEVATED,
            passes=(PassResult("architectural-placement", reached_stop_condition=True),),
        )
        self.assertEqual(result.coverage, "complete")

    def test_required_pass_not_reaching_stop_condition_is_incomplete(self) -> None:
        result = evaluate_coverage(
            Depth.DEEP,
            passes=(PassResult("affected-test-analysis", reached_stop_condition=False),),
        )
        self.assertEqual(result.coverage, "incomplete")
        self.assertEqual(len(result.reasons), 1)
        self.assertEqual(
            result.reasons[0].trigger, IncompleteTrigger.REQUIRED_PASS_NOT_PRODUCED
        )

    def test_pass_not_required_at_this_depth_is_ignored(self) -> None:
        deep_only = PassResult(
            "deep-only-pass", reached_stop_condition=False, required_at=(Depth.DEEP,)
        )
        result = evaluate_coverage(Depth.STANDARD, passes=(deep_only,))
        self.assertEqual(result.coverage, "complete")

    def test_unestablished_review_target_is_incomplete(self) -> None:
        result = evaluate_coverage(
            Depth.STANDARD, passes=(), review_target_established=False
        )
        self.assertEqual(result.coverage, "incomplete")
        self.assertEqual(
            result.reasons[0].trigger, IncompleteTrigger.REVIEW_TARGET_NOT_ESTABLISHED
        )

    def test_incomplete_partition_makes_whole_review_incomplete(self) -> None:
        result = evaluate_coverage(
            Depth.DEEP,
            passes=(),
            partitions=(
                PartitionCompletion("P1", completed=True),
                PartitionCompletion("P2", completed=False),
            ),
        )
        self.assertEqual(result.coverage, "incomplete")
        self.assertTrue(result.partitioned)
        self.assertEqual(
            result.reasons[0].trigger, IncompleteTrigger.PARTITION_NOT_COMPLETED
        )

    def test_all_partitions_completed_is_complete(self) -> None:
        result = evaluate_coverage(
            Depth.STANDARD,
            passes=(),
            partitions=(
                PartitionCompletion("P1", completed=True),
                PartitionCompletion("P2", completed=True),
            ),
        )
        self.assertEqual(result.coverage, "complete")
        self.assertTrue(result.partitioned)

    def test_no_partitions_means_not_partitioned(self) -> None:
        result = evaluate_coverage(Depth.STANDARD, passes=())
        self.assertFalse(result.partitioned)

    def test_required_validation_gap_is_incomplete(self) -> None:
        gap = IncompleteReason(
            IncompleteTrigger.REQUIRED_VALIDATION_UNAVAILABLE,
            "the one command that could confirm the finding was unavailable",
        )
        result = evaluate_coverage(Depth.DEEP, passes=(), validation_gap=gap)
        self.assertEqual(result.coverage, "incomplete")
        self.assertIn(gap, result.reasons)


class MachineModelTests(unittest.TestCase):
    def test_complete_model_has_no_reasons_key(self) -> None:
        result = evaluate_coverage(Depth.STANDARD, passes=())
        model = result.to_machine_model()["review_stopping_criteria"]
        self.assertEqual(model["coverage"], "complete")
        self.assertNotIn("incomplete_reasons", model)

    def test_incomplete_model_carries_reasons(self) -> None:
        result = evaluate_coverage(
            Depth.STANDARD, passes=(), review_target_established=False
        )
        model = result.to_machine_model()["review_stopping_criteria"]
        self.assertEqual(model["coverage"], "incomplete")
        self.assertEqual(len(model["incomplete_reasons"]), 1)
        self.assertEqual(
            model["incomplete_reasons"][0]["trigger"],
            "review-target-not-established",
        )


class DecisionLabelOverrideTests(unittest.TestCase):
    def test_complete_coverage_leaves_mechanical_decision_unchanged(self) -> None:
        result = evaluate_coverage(Depth.STANDARD, passes=())
        self.assertEqual(decision_label(result, "REVIEW CLEAN"), "REVIEW CLEAN")
        self.assertEqual(
            decision_label(result, "CHANGES REQUIRED"), "CHANGES REQUIRED"
        )

    def test_incomplete_coverage_overrides_a_clean_decision(self) -> None:
        result = evaluate_coverage(
            Depth.STANDARD, passes=(), review_target_established=False
        )
        self.assertEqual(decision_label(result, "REVIEW CLEAN"), "REVIEW INCOMPLETE")

    def test_incomplete_coverage_overrides_a_blocking_decision_too(self) -> None:
        # Incomplete is at least as strict as blocking: a reader must never
        # see a clean-reading outcome when coverage did not finish, even if
        # findings gathered so far would already have blocked on their own.
        result = evaluate_coverage(
            Depth.STANDARD, passes=(), review_target_established=False
        )
        self.assertEqual(
            decision_label(result, "CHANGES REQUIRED"), "REVIEW INCOMPLETE"
        )


if __name__ == "__main__":
    unittest.main()
