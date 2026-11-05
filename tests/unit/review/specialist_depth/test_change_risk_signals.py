"""Behavioral fixtures for change-risk signals and review depth (Issue #86)."""

from __future__ import annotations

import unittest

from tests.reference.review import change_risk_signals as crs
from tests.reference.review.change_risk_signals import Depth, DiffSize, ObservedFact, Tier


def fact(fact_id: str, *labels: str, evidence: str = "") -> ObservedFact:
    return ObservedFact(
        fact_id=fact_id,
        labels=frozenset(labels),
        evidence=evidence or f"{fact_id} evidence",
    )


class PerSignalDetectionAndTierTests(unittest.TestCase):
    def test_each_deep_signal_alone_is_deep(self) -> None:
        for label in ("auth", "migration", "concurrency", "public_api"):
            with self.subTest(label=label):
                result = crs.classify([fact("f1", label)])
                self.assertEqual(result.depth, Depth.DEEP)
                self.assertEqual(result.occurrences[0].tier, Tier.DEEP)

    def test_each_elevated_signal_alone_is_elevated(self) -> None:
        for label in ("sensitive_path", "infra_config"):
            with self.subTest(label=label):
                result = crs.classify([fact("f1", label)])
                self.assertEqual(result.depth, Depth.ELEVATED)
                self.assertEqual(result.occurrences[0].tier, Tier.ELEVATED)

    def test_no_signal_is_standard_with_no_occurrences(self) -> None:
        result = crs.classify([fact("f1")], DiffSize(changed_lines=40, changed_files=2))
        self.assertEqual(result.depth, Depth.STANDARD)
        self.assertEqual(result.occurrences, ())

    def test_unknown_label_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            crs.classify([ObservedFact("f1", frozenset({"typosquat"}))])

    def test_duplicate_fact_id_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            crs.classify([fact("f1", "auth"), fact("f1", "infra_config")])


class DiffSizeBoundaryTests(unittest.TestCase):
    """Immediately below, exactly at, and immediately above each authoritative
    boundary. ``>=`` semantics."""

    def _tier(self, *, lines: int, files: int) -> Tier | None:
        return crs.diff_size_tier(DiffSize(changed_lines=lines, changed_files=files))

    def test_changed_lines_elevated_boundary_149_150_151(self) -> None:
        self.assertIsNone(self._tier(lines=149, files=0))
        self.assertEqual(self._tier(lines=150, files=0), Tier.ELEVATED)
        self.assertEqual(self._tier(lines=151, files=0), Tier.ELEVATED)

    def test_changed_lines_deep_boundary_599_600_601(self) -> None:
        self.assertEqual(self._tier(lines=599, files=0), Tier.ELEVATED)
        self.assertEqual(self._tier(lines=600, files=0), Tier.DEEP)
        self.assertEqual(self._tier(lines=601, files=0), Tier.DEEP)

    def test_changed_files_elevated_boundary_9_10_11(self) -> None:
        self.assertIsNone(self._tier(lines=0, files=9))
        self.assertEqual(self._tier(lines=0, files=10), Tier.ELEVATED)
        self.assertEqual(self._tier(lines=0, files=11), Tier.ELEVATED)

    def test_changed_files_deep_boundary_29_30_31(self) -> None:
        self.assertEqual(self._tier(lines=0, files=29), Tier.ELEVATED)
        self.assertEqual(self._tier(lines=0, files=30), Tier.DEEP)
        self.assertEqual(self._tier(lines=0, files=31), Tier.DEEP)

    def test_higher_of_line_and_file_tier_wins(self) -> None:
        self.assertEqual(self._tier(lines=200, files=30), Tier.DEEP)
        self.assertEqual(self._tier(lines=50, files=12), Tier.ELEVATED)

    def test_non_reviewable_exclusion_moves_a_delta_below_the_boundary(self) -> None:
        # Caller measures size AFTER excluding non-reviewable files; 700 raw
        # lines that are 120 once a generated file is dropped is not a signal.
        raw = crs.classify([], DiffSize(changed_lines=700, changed_files=3))
        self.assertEqual(raw.depth, Depth.DEEP)
        reviewable_only = crs.classify([], DiffSize(changed_lines=120, changed_files=2))
        self.assertEqual(reviewable_only.depth, Depth.STANDARD)

    def test_negative_measurements_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            crs.diff_size_tier(DiffSize(changed_lines=-1, changed_files=0))


class ClassificationOrderingTests(unittest.TestCase):
    def test_one_fact_two_elevated_labels_dedups_to_one_elevated_occurrence(self) -> None:
        result = crs.classify([fact("gateway", "sensitive_path", "infra_config")])
        self.assertEqual(result.depth, Depth.ELEVATED)
        self.assertEqual(len(result.occurrences), 1)
        self.assertEqual(result.occurrences[0].tier, Tier.ELEVATED)
        self.assertEqual(
            result.occurrences[0].signals, ("infra_config", "sensitive_path")
        )

    def test_one_fact_with_auth_overlap_resolves_to_deep_without_downgrade(self) -> None:
        result = crs.classify(
            [fact("gateway", "sensitive_path", "infra_config", "auth")]
        )
        self.assertEqual(result.depth, Depth.DEEP)
        self.assertEqual(len(result.occurrences), 1)
        self.assertEqual(result.occurrences[0].tier, Tier.DEEP)

    def test_two_distinct_elevated_facts_escalate_to_deep(self) -> None:
        result = crs.classify(
            [fact("ci", "infra_config"), fact("payments_file", "sensitive_path")]
        )
        self.assertEqual(result.depth, Depth.DEEP)
        self.assertEqual(len(result.occurrences), 2)
        self.assertTrue(all(o.tier is Tier.ELEVATED for o in result.occurrences))

    def test_diff_size_threshold_one_plus_one_distinct_elevated_fact_is_deep(self) -> None:
        result = crs.classify(
            [fact("ci", "infra_config")],
            DiffSize(changed_lines=150, changed_files=1),
        )
        self.assertEqual(result.depth, Depth.DEEP)
        self.assertEqual(
            sorted(o.source for o in result.occurrences), ["ci", "diff-size"]
        )

    def test_diff_size_threshold_one_alone_is_elevated(self) -> None:
        result = crs.classify([], DiffSize(changed_lines=300, changed_files=6))
        self.assertEqual(result.depth, Depth.ELEVATED)
        self.assertEqual(len(result.occurrences), 1)

    def test_single_elevated_occurrence_is_elevated(self) -> None:
        self.assertEqual(
            crs.classify([fact("ci", "infra_config")]).depth, Depth.ELEVATED
        )

    def test_no_occurrences_is_standard(self) -> None:
        self.assertEqual(crs.classify([]).depth, Depth.STANDARD)


class DepthOnlyTieBreakTests(unittest.TestCase):
    def test_ambiguous_depth_resolves_to_the_higher_effort_level(self) -> None:
        result = crs.classify(
            [fact("ci", "infra_config")],
            ambiguous_depth_candidates=[Depth.DEEP],
        )
        self.assertEqual(result.depth, Depth.DEEP)

    def test_tie_break_never_lowers_the_derived_depth(self) -> None:
        result = crs.classify(
            [fact("auth_file", "auth")],
            ambiguous_depth_candidates=[Depth.STANDARD, Depth.ELEVATED],
        )
        self.assertEqual(result.depth, Depth.DEEP)

    def test_tie_break_does_not_touch_occurrence_tiers_or_evidence(self) -> None:
        # The depth label goes up; the underlying signal occurrences — which a
        # finding's severity/confidence would key off — are untouched.
        plain = crs.classify([fact("ci", "infra_config", evidence="ci.yml")])
        bumped = crs.classify(
            [fact("ci", "infra_config", evidence="ci.yml")],
            ambiguous_depth_candidates=[Depth.DEEP],
        )
        self.assertEqual(plain.occurrences, bumped.occurrences)
        self.assertEqual(bumped.occurrences[0].tier, Tier.ELEVATED)
        self.assertEqual(bumped.occurrences[0].evidence, "ci.yml")


class RationaleEmissionTests(unittest.TestCase):
    def test_standard_still_emits_a_line_with_no_signals(self) -> None:
        lines = crs.rationale_lines(crs.classify([]))
        self.assertIn("Change-risk depth: standard", lines)
        self.assertIn("Change-risk signals: none", lines)

    def test_each_activating_signal_is_named_with_tier_and_evidence(self) -> None:
        result = crs.classify(
            [fact("mig", "migration", evidence="db/migrations/0007_add_col.sql")]
        )
        lines = crs.rationale_lines(result)
        self.assertIn("Change-risk depth: deep", lines)
        self.assertIn(
            "Change-risk signal: migration (deep) — db/migrations/0007_add_col.sql",
            lines,
        )

    def test_machine_model_has_one_entry_per_resolved_occurrence(self) -> None:
        # One changed fact matching two labels is one occurrence, one entry.
        model = crs.classify(
            [fact("gateway", "sensitive_path", "infra_config")]
        ).to_machine_model()
        self.assertEqual(set(model), {"change_risk"})
        self.assertEqual(model["change_risk"]["depth"], "elevated")
        occurrences = model["change_risk"]["occurrences"]
        self.assertEqual(len(occurrences), 1)
        self.assertEqual(
            set(occurrences[0]["signals"]), {"sensitive_path", "infra_config"}
        )
        self.assertEqual(occurrences[0]["tier"], "elevated")

    def test_two_distinct_facts_are_two_entries(self) -> None:
        model = crs.classify(
            [fact("ci", "infra_config"), fact("payments", "sensitive_path")]
        ).to_machine_model()
        self.assertEqual(len(model["change_risk"]["occurrences"]), 2)

    def test_standard_machine_model_has_no_occurrences(self) -> None:
        model = crs.classify([]).to_machine_model()
        self.assertEqual(model["change_risk"], {"depth": "standard", "occurrences": []})


if __name__ == "__main__":
    unittest.main()
