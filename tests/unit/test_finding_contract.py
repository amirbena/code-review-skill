#!/usr/bin/env python3
"""Behavioral coverage for the canonical finding contract (Issue #37).

Contract: shared/templates/finding.md. Regression focus: the compact,
field-oriented shape and its field order stay stable; the mandatory core
(What/Where/Evidence/Impact/Fix) is never dropped for brevity; a longer
`Details` explanation is allowed only for the controlled-exception
categories; optional fields never render as empty boilerplate; a clean
review renders the fixed no-findings line; severities render one-per
finding, visible first.
"""

from __future__ import annotations

import unittest

from tests.reference import finding_contract as fc


def _finding(**overrides) -> fc.Finding:
    base = dict(
        id="F1",
        severity=fc.Severity.P1,
        title="Retry can duplicate processing",
        location="src/pay/retry.py:88",
        evidence="The handler re-enqueues before marking the row done.",
        impact="A retried delivery processes the same payment twice.",
        fix="Mark the row processed in the same transaction as the enqueue.",
    )
    base.update(overrides)
    return fc.Finding(**base)


class FullRenderingShapeTests(unittest.TestCase):
    def test_field_labels_appear_in_canonical_order(self) -> None:
        rendered = fc.render_full(_finding())
        for label in ("**Location:**", "**Evidence:**", "**Impact:**", "**Fix:**"):
            self.assertIn(label, rendered)
        self.assertLess(rendered.index("**Location:**"), rendered.index("**Evidence:**"))
        self.assertLess(rendered.index("**Evidence:**"), rendered.index("**Impact:**"))
        self.assertLess(rendered.index("**Impact:**"), rendered.index("**Fix:**"))

    def test_severity_is_visible_first_on_the_heading(self) -> None:
        rendered = fc.render_full(_finding(severity=fc.Severity.P0))
        self.assertTrue(rendered.startswith("### F1 [P0] "))

    def test_optional_fields_absent_do_not_render_as_empty_lines(self) -> None:
        rendered = fc.render_full(_finding())
        self.assertNotIn("Details:", rendered)
        self.assertNotIn("Implementation prompt:", rendered)
        # no dangling label with nothing after it
        for line in rendered.splitlines():
            if line.startswith("- **"):
                self.assertRegex(line, r"- \*\*[A-Za-z ]+:\*\* \S")

    def test_location_source_annotation_is_a_trailing_addition(self) -> None:
        rendered = fc.render_full(_finding(location_source_annotation="staged"))
        self.assertIn("- **Location:** `src/pay/retry.py:88` _(staged)_", rendered)

    def test_implementation_prompt_is_opt_in_and_local_only(self) -> None:
        f = _finding(implementation_prompt="Do the thing.")
        self.assertNotIn("Implementation prompt:", fc.render_full(f))
        self.assertIn(
            "Implementation prompt:",
            fc.render_full(f, surface=fc.Surface.LOCAL_REPORT, include_fix_prompt=True),
        )
        # github body never renders it, even if asked
        self.assertNotIn(
            "Implementation prompt:",
            fc.render_full(
                f, surface=fc.Surface.GITHUB_BODY, include_fix_prompt=True
            ),
        )


class InlineRenderingShapeTests(unittest.TestCase):
    def test_inline_omits_id_and_location_keeps_severity_first(self) -> None:
        rendered = fc.render_inline(_finding())
        self.assertTrue(rendered.startswith("[P1] "))
        self.assertNotIn("F1", rendered)
        self.assertNotIn("Location:", rendered)
        self.assertNotIn("src/pay/retry.py", rendered)
        for label in ("Evidence:", "Impact:", "Fix:"):
            self.assertIn(label, rendered)

    def test_inline_finding_still_has_full_mandatory_core(self) -> None:
        self.assertEqual(
            fc.missing_mandatory_fields(_finding(), surface=fc.Surface.GITHUB_INLINE),
            (),
        )


class MandatoryCoreTests(unittest.TestCase):
    def test_publishable_finding_has_no_missing_core_fields(self) -> None:
        self.assertEqual(
            fc.missing_mandatory_fields(_finding(), surface=fc.Surface.LOCAL_REPORT),
            (),
        )

    def test_dropping_evidence_impact_or_fix_is_a_contract_violation(self) -> None:
        for field in ("evidence", "impact", "fix"):
            with self.subTest(field=field):
                broken = _finding(**{field: "   "})
                self.assertIn(
                    field,
                    fc.missing_mandatory_fields(
                        broken, surface=fc.Surface.LOCAL_REPORT
                    ),
                )

    def test_core_field_set_and_order_are_stable(self) -> None:
        self.assertEqual(
            fc.MANDATORY_CORE,
            ("id", "severity", "title", "location", "evidence", "impact", "fix"),
        )


class LongerExplanationTests(unittest.TestCase):
    def test_details_requires_a_controlled_exception_category(self) -> None:
        justified = _finding(
            details="Ordering: worker A commits the row after worker B reads it.",
            long_form_category="concurrency_or_ordering",
        )
        self.assertTrue(fc.has_justified_long_form(justified))

    def test_details_without_a_listed_category_is_not_justified(self) -> None:
        unjustified = _finding(
            details="A long-winded restatement of the title over three sentences.",
            long_form_category=None,
        )
        self.assertFalse(fc.has_justified_long_form(unjustified))

    def test_ordinary_finding_needs_no_justification(self) -> None:
        self.assertTrue(fc.has_justified_long_form(_finding()))

    def test_details_renders_after_fix_for_human_first_order(self) -> None:
        rendered = fc.render_full(
            _finding(
                details="The invariant is established in loader.py and broken here.",
                long_form_category="complex_invariant_violation",
            )
        )
        self.assertLess(rendered.index("**Evidence:**"), rendered.index("**Impact:**"))
        self.assertLess(rendered.index("**Impact:**"), rendered.index("**Fix:**"))
        self.assertLess(rendered.index("**Fix:**"), rendered.index("**Details:**"))

    def test_local_details_default_true(self) -> None:
        rendered = fc.render_full(_finding(details="Useful context."))
        self.assertIn("**Details:**", rendered)

    def test_github_details_default_false(self) -> None:
        rendered = fc.render_full(
            _finding(details="Useful context."), surface=fc.Surface.GITHUB_BODY
        )
        self.assertNotIn("**Details:**", rendered)

    def test_github_finding_level_override_beats_invocation(self) -> None:
        rendered = fc.render_full(
            _finding(details="Race ordering."),
            surface=fc.Surface.GITHUB_BODY,
            include_finding_details=False,
            finding_detail_override=True,
        )
        self.assertIn("**Details:** Race ordering.", rendered)

    def test_finding_level_false_beats_local_default(self) -> None:
        rendered = fc.render_full(
            _finding(details="Redundant context."), finding_detail_override=False
        )
        self.assertNotIn("**Details:**", rendered)

    def test_finding_level_override_is_not_part_of_finding_data(self) -> None:
        self.assertNotIn("include_details", fc.Finding.__dataclass_fields__)

    def test_implementation_prompt_stays_before_supporting_details(self) -> None:
        rendered = fc.render_full(
            _finding(details="Supporting context.", implementation_prompt="Implement safely."),
            include_fix_prompt=True,
        )
        self.assertLess(rendered.index("**Fix:**"), rendered.index("**Implementation prompt:**"))
        self.assertLess(rendered.index("**Implementation prompt:**"), rendered.index("**Details:**"))


class ReviewSummaryAlignmentTests(unittest.TestCase):
    def test_clean_review_omits_the_findings_section_body(self) -> None:
        self.assertEqual(fc.render_findings_section([]), "")

    def test_multiple_severities_each_render_once_severity_first(self) -> None:
        findings = [
            _finding(id="F1", severity=fc.Severity.P0, title="Broken prod flow"),
            _finding(id="F2", severity=fc.Severity.P1, title="Missing edge case"),
            _finding(id="F3", severity=fc.Severity.P2, title="Naming inconsistency"),
        ]
        section = fc.render_findings_section(findings)
        self.assertEqual(section.count("### F1 [P0] "), 1)
        self.assertEqual(section.count("### F2 [P1] "), 1)
        self.assertEqual(section.count("### F3 [P2] "), 1)

    def test_summary_pointer_form_is_severity_title_then_location(self) -> None:
        pointer = fc.render_summary_pointer(_finding())
        self.assertEqual(
            pointer,
            "- **P1 — Retry can duplicate processing**\n  `src/pay/retry.py:88`",
        )


class SeveritySemanticsUnchangedTests(unittest.TestCase):
    def test_only_the_three_canonical_severities_exist(self) -> None:
        self.assertEqual(
            {s.value for s in fc.Severity}, {"P0", "P1", "P2"}
        )


if __name__ == "__main__":
    unittest.main()
