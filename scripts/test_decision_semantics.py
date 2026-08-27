#!/usr/bin/env python3
"""Coverage for the severity → decision contract (decision_semantics.py).

Contract: shared/policies/severity.md. Regression focus: a P2-only review
resolves clean, never blocking, whatever the P2's strength or origin.
"""

from __future__ import annotations

import inspect
import re
import unittest
from pathlib import Path

import decision_semantics as ds

REPO_ROOT = Path(__file__).resolve().parent.parent
SEVERITY_POLICY = REPO_ROOT / "shared" / "policies" / "severity.md"
REVIEW_SUMMARY_TEMPLATE = REPO_ROOT / "shared" / "templates" / "review-summary.md"


def _text(path: Path) -> str:
    raw = path.read_text(encoding="utf-8").replace("**", "").replace("`", "")
    return re.sub(r"\s+", " ", raw)


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

    def test_no_function_accepts_a_correction_or_provisional_parameter(self) -> None:
        for name, obj in inspect.getmembers(ds):
            if not inspect.isfunction(obj):
                continue
            for param_name in inspect.signature(obj).parameters:
                lowered = param_name.lower()
                for fragment in ds.PROHIBITED_CORRECTION_FRAGMENTS:
                    self.assertNotIn(
                        fragment,
                        lowered,
                        f"{name}() must not accept a correction/provisional "
                        f"decision parameter, found: {param_name}",
                    )


class SingleDecisionSourceTests(unittest.TestCase):
    """A report's Result line and Decision section render one
    already-derived value — never two independently-derived outcomes, and
    never a provisional decision later superseded. `Decision.value` is
    already the canonical Decision-section text (see decision_semantics.py,
    the comment above RESULT_LABELS), so Result and Decision agreeing is
    structural whenever both come from the same `derive_decision(...)`
    call, as they always do here — there is no separate "do these two
    values match" check to maintain on top of that. The actual protection
    against a report ever disagreeing with itself lives in the policy
    prose pinned below (severity.md / review-summary.md), which governs
    the one thing Python code here cannot: how a report is actually
    composed. Mirrors severity.md, "Decision derivation (mechanical)" —
    the canonical test owner for decision semantics, extended rather than
    duplicated into a second test module."""

    def test_p2_only_findings_yield_clean_rendered_consistently(self) -> None:
        findings = [ds.Finding("F1", ds.Severity.P2)]
        decision = ds.derive_decision(findings)
        self.assertEqual(decision, ds.Decision.CLEAN)
        self.assertIn("Clean", ds.render_result_label(decision))
        self.assertEqual(decision.value, "REVIEW CLEAN")

    def test_any_p0_or_p1_yields_changes_required_rendered_consistently(self) -> None:
        for severity in (ds.Severity.P0, ds.Severity.P1):
            with self.subTest(severity=severity):
                findings = [ds.Finding("F1", severity)]
                decision = ds.derive_decision(findings)
                self.assertEqual(decision, ds.Decision.CHANGES_REQUIRED)
                self.assertIn("Changes", ds.render_result_label(decision))
                self.assertEqual(decision.value, "CHANGES REQUIRED")

    def test_severity_policy_states_decision_is_derived_and_rendered_once(self) -> None:
        text = _text(SEVERITY_POLICY)
        self.assertIn(
            "This derivation runs exactly once per invocation, after the "
            "finding set is finalized, and produces exactly one decision "
            "value",
            text,
        )
        self.assertIn(
            "A report must never show a provisional decision that is "
            "later superseded",
            text,
        )

    def test_review_summary_requires_result_and_decision_to_agree(self) -> None:
        text = _text(REVIEW_SUMMARY_TEMPLATE)
        self.assertIn(
            "Result and Decision render the same single, "
            "already-finalized decision value",
            text,
        )
        self.assertIn(
            "never a Result that disagrees with the Decision section",
            text,
        )
        self.assertIn(
            "never correction prose narrating that an earlier rendering "
            "was wrong",
            text,
        )


if __name__ == "__main__":
    unittest.main()
