#!/usr/bin/env python3
"""Regression coverage for the severity → decision contract.

Mirrors shared/policies/severity.md, "Decision derivation (mechanical)" and
"Repository conventions and severity." Exercises the pure decision-table
reference implementation in decision_semantics.py.

This is the regression suite for the motivating bug: a review containing
only a non-blocking P2 finding (for example, a repository-style-convention
violation) must resolve to a clean/approved decision, never a blocking one,
regardless of how strongly that P2 is recommended or where it originated.

Run with:
    python3 scripts/test_decision_semantics.py
"""

from __future__ import annotations

import inspect
import unittest

import decision_semantics as ds


class CaseATests(unittest.TestCase):
    """Case A: no findings -> clean decision."""

    def test_no_findings_is_clean(self) -> None:
        self.assertEqual(ds.derive_decision([]), ds.Decision.CLEAN)
        self.assertEqual(ds.blocking_findings([]), ())


class CaseBTests(unittest.TestCase):
    """Case B: one P2 -> clean decision, P2 remains in findings."""

    def test_single_p2_is_clean(self) -> None:
        findings = [ds.Finding("F1", ds.Severity.P2)]
        self.assertEqual(ds.derive_decision(findings), ds.Decision.CLEAN)
        self.assertEqual(ds.blocking_findings(findings), ())

    def test_single_p2_is_preserved_in_a_clean_report(self) -> None:
        findings = [ds.Finding("F1", ds.Severity.P2)]
        retained = ds.clean_report_retains_non_blocking_findings(findings)
        self.assertEqual(retained, tuple(findings))
        self.assertIn(ds.Finding("F1", ds.Severity.P2), retained)


class CaseCTests(unittest.TestCase):
    """Case C: multiple P2s -> still clean."""

    def test_multiple_p2s_are_clean(self) -> None:
        findings = [
            ds.Finding("F1", ds.Severity.P2),
            ds.Finding("F2", ds.Severity.P2),
            ds.Finding("F3", ds.Severity.P2),
        ]
        self.assertEqual(ds.derive_decision(findings), ds.Decision.CLEAN)
        self.assertEqual(ds.blocking_findings(findings), ())
        self.assertEqual(
            ds.clean_report_retains_non_blocking_findings(findings), tuple(findings)
        )


class CaseDTests(unittest.TestCase):
    """Case D: P1 + P2 -> blocking decision."""

    def test_p1_plus_p2_blocks(self) -> None:
        findings = [ds.Finding("F1", ds.Severity.P1), ds.Finding("F2", ds.Severity.P2)]
        self.assertEqual(ds.derive_decision(findings), ds.Decision.CHANGES_REQUIRED)
        blocking = ds.blocking_findings(findings)
        self.assertEqual(len(blocking), 1)
        self.assertEqual(blocking[0].id, "F1")


class CaseETests(unittest.TestCase):
    """Case E: a single P0 -> blocking decision."""

    def test_single_p0_blocks(self) -> None:
        findings = [ds.Finding("F1", ds.Severity.P0)]
        self.assertEqual(ds.derive_decision(findings), ds.Decision.CHANGES_REQUIRED)
        self.assertEqual(ds.blocking_findings(findings), tuple(findings))


class CaseFTests(unittest.TestCase):
    """Case F: a repository-convention-originated P2 stays clean.

    Generic — the fixture happens to use a style-convention example (as the
    motivating scenario does), but nothing here is em-dash-specific or
    hardcoded to any single convention; any P2-severity finding regardless
    of origin behaves identically, per CaseB/CaseC above.
    """

    def test_repository_convention_p2_does_not_escalate_the_decision(self) -> None:
        finding = ds.Finding(
            "F1", ds.Severity.P2, origin="repository_convention"
        )
        self.assertEqual(ds.derive_decision([finding]), ds.Decision.CLEAN)
        self.assertEqual(ds.blocking_findings([finding]), ())
        # The finding is still reported, just non-blocking.
        self.assertIn(finding, ds.clean_report_retains_non_blocking_findings([finding]))

    def test_origin_never_changes_blocking_membership_for_equal_severity(self) -> None:
        # A P1 is blocking regardless of origin; a P2 is never blocking
        # regardless of origin. Origin must never be consulted by the
        # mechanical derivation.
        origins = ("diff", "repository_convention", "pr_context", "review_context")
        for origin in origins:
            with self.subTest(origin=origin):
                p1 = ds.Finding("F-p1", ds.Severity.P1, origin=origin)
                p2 = ds.Finding("F-p2", ds.Severity.P2, origin=origin)
                self.assertEqual(ds.derive_decision([p1]), ds.Decision.CHANGES_REQUIRED)
                self.assertEqual(ds.derive_decision([p2]), ds.Decision.CLEAN)


class MixedSeverityTests(unittest.TestCase):
    """Cross-cutting: any P0 or P1 present blocks, no matter how many P2s
    accompany it; only P0/P1 members populate blocking_findings."""

    def test_p0_p1_p2_mixed_blocks_and_blocking_set_excludes_p2(self) -> None:
        findings = [
            ds.Finding("F1", ds.Severity.P0),
            ds.Finding("F2", ds.Severity.P1),
            ds.Finding("F3", ds.Severity.P2),
            ds.Finding("F4", ds.Severity.P2),
        ]
        self.assertEqual(ds.derive_decision(findings), ds.Decision.CHANGES_REQUIRED)
        blocking_ids = {f.id for f in ds.blocking_findings(findings)}
        self.assertEqual(blocking_ids, {"F1", "F2"})


class GovernanceInvariantTests(unittest.TestCase):
    """No independent, overridable decision path can be introduced here."""

    def test_no_function_accepts_an_override_or_force_parameter(self) -> None:
        for name, obj in inspect.getmembers(ds):
            if not inspect.isfunction(obj):
                continue
            for param_name in inspect.signature(obj).parameters:
                lowered = param_name.lower()
                for fragment in ds.PROHIBITED_OVERRIDE_PARAM_FRAGMENTS:
                    self.assertNotIn(
                        fragment,
                        lowered,
                        f"{name}() must not accept a decision-override parameter, "
                        f"found: {param_name}",
                    )

    def test_derive_decision_is_a_pure_function_of_severities_only(self) -> None:
        # Two finding sets that differ only in id/origin, but not severity,
        # must derive the same decision — proving origin/id play no role.
        set_a = [ds.Finding("F1", ds.Severity.P2, origin="repository_convention")]
        set_b = [ds.Finding("different-id", ds.Severity.P2, origin="diff")]
        self.assertEqual(ds.derive_decision(set_a), ds.derive_decision(set_b))

    def test_decision_enum_has_exactly_the_two_canonical_labels(self) -> None:
        labels = {member.value for member in ds.Decision}
        self.assertEqual(labels, {"REVIEW CLEAN", "CHANGES REQUIRED"})


if __name__ == "__main__":
    unittest.main()
