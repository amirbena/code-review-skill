#!/usr/bin/env python3
"""Behavioral coverage for the shadow-validation methodology (Issue #335).
Contract: docs/benchmark/shadow-validation.md.
"""

from __future__ import annotations

import unittest
from fractions import Fraction

from tests.reference.benchmark import benchmark_shadow_validation as sv


class BurnInSampleTests(unittest.TestCase):
    def test_deduplicates_and_sorts_case_ids(self) -> None:
        sample = sv.BurnInSample(
            sample_id="pr-1",
            selected_case_ids=("b", "a", "a"),
            regressed_case_ids=("z", "z", "y"),
        )
        self.assertEqual(sample.selected_case_ids, ("a", "b"))
        self.assertEqual(sample.regressed_case_ids, ("y", "z"))


class EvaluateSampleTests(unittest.TestCase):
    def test_splits_regressions_into_missed_and_caught(self) -> None:
        sample = sv.BurnInSample(
            sample_id="pr-1",
            selected_case_ids=("case-a", "case-b"),
            regressed_case_ids=("case-b", "case-c"),
        )
        result = sv.evaluate_sample(sample)
        self.assertEqual(result.caught_case_ids, ("case-b",))
        self.assertEqual(result.missed_case_ids, ("case-c",))
        self.assertEqual(result.unexercised_selected_case_ids, ("case-a",))

    def test_no_regressions_means_nothing_missed_or_caught(self) -> None:
        sample = sv.BurnInSample(
            sample_id="pr-1", selected_case_ids=("case-a",), regressed_case_ids=()
        )
        result = sv.evaluate_sample(sample)
        self.assertEqual(result.missed_case_ids, ())
        self.assertEqual(result.caught_case_ids, ())
        self.assertEqual(result.unexercised_selected_case_ids, ("case-a",))


class AggregateBurnInTests(unittest.TestCase):
    def test_miss_rate_and_redundancy_over_a_window(self) -> None:
        samples = [
            sv.BurnInSample("pr-1", ("case-a", "case-b"), ("case-b",)),  # a unexercised, b caught
            sv.BurnInSample("pr-2", ("case-a",), ("case-c",)),  # a unexercised, c missed
            sv.BurnInSample("pr-3", ("case-c", "case-d"), ("case-c", "case-d")),  # both caught
        ]
        aggregate = sv.aggregate_burn_in(samples)

        self.assertEqual(aggregate.sample_count, 3)
        self.assertEqual(aggregate.total_regressions, 4)  # b (pr-1), c (pr-2), c+d (pr-3)
        self.assertEqual(aggregate.total_missed, 1)  # case-c in pr-2
        self.assertEqual(aggregate.miss_rate, Fraction(1, 4))

        # case-a was selected in pr-1 and pr-2, never once corresponded to a
        # caught regression across the whole window -> redundant.
        self.assertEqual(aggregate.distinct_selected_case_ids, ("case-a", "case-b", "case-c", "case-d"))
        self.assertEqual(aggregate.cases_never_caught_a_regression, ("case-a",))
        self.assertEqual(aggregate.redundancy_rate, Fraction(1, 4))

    def test_recurring_regression_counts_fresh_each_sample(self) -> None:
        samples = [
            sv.BurnInSample("pr-1", (), ("case-a",)),
            sv.BurnInSample("pr-2", (), ("case-a",)),
        ]
        aggregate = sv.aggregate_burn_in(samples)
        self.assertEqual(aggregate.total_regressions, 2)
        self.assertEqual(aggregate.total_missed, 2)
        self.assertEqual(aggregate.miss_rate, Fraction(1, 1))

    def test_empty_window_is_vacuous_not_zero(self) -> None:
        aggregate = sv.aggregate_burn_in([])
        self.assertEqual(aggregate.sample_count, 0)
        self.assertIsNone(aggregate.miss_rate)
        self.assertIsNone(aggregate.redundancy_rate)

    def test_no_regressions_in_window_is_vacuous_miss_rate(self) -> None:
        samples = [sv.BurnInSample("pr-1", ("case-a",), ())]
        aggregate = sv.aggregate_burn_in(samples)
        self.assertEqual(aggregate.total_regressions, 0)
        self.assertIsNone(aggregate.miss_rate)
        self.assertEqual(aggregate.redundancy_rate, Fraction(1, 1))  # case-a never caught anything

    def test_nothing_ever_selected_is_vacuous_redundancy_rate(self) -> None:
        samples = [sv.BurnInSample("pr-1", (), ("case-a",))]
        aggregate = sv.aggregate_burn_in(samples)
        self.assertIsNone(aggregate.redundancy_rate)
        self.assertEqual(aggregate.miss_rate, Fraction(1, 1))

    def test_perfect_selector_has_zero_miss_and_zero_redundancy(self) -> None:
        samples = [
            sv.BurnInSample("pr-1", ("case-a",), ("case-a",)),
            sv.BurnInSample("pr-2", ("case-b",), ("case-b",)),
        ]
        aggregate = sv.aggregate_burn_in(samples)
        self.assertEqual(aggregate.miss_rate, Fraction(0, 1))
        self.assertEqual(aggregate.redundancy_rate, Fraction(0, 1))


class BuildBurnInReportTests(unittest.TestCase):
    def test_report_carries_the_window_description_and_serializes_fractions(self) -> None:
        samples = [sv.BurnInSample("pr-1", ("case-a",), ("case-a", "case-b"))]
        aggregate = sv.aggregate_burn_in(samples)
        report = sv.build_burn_in_report(aggregate, window_description="2026-08-01..2026-09-01")

        self.assertEqual(report["window_description"], "2026-08-01..2026-09-01")
        self.assertEqual(report["miss_rate"]["numerator"], 1)
        self.assertEqual(report["miss_rate"]["denominator"], 2)
        self.assertAlmostEqual(report["miss_rate"]["float"], 0.5)
        self.assertEqual(len(report["per_sample"]), 1)
        self.assertNotIn("verdict", report)
        self.assertNotIn("passed", report)


if __name__ == "__main__":
    unittest.main()
