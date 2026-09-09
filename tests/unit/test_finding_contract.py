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


class HumanInlineRenderingTests(unittest.TestCase):
    """Issue #166: the opt-in concise "human inline" rendering
    (`human_inline_findings`) is a re-voicing of the *same* finding — not a
    weaker one and not a relocation."""

    def test_heading_keeps_severity_and_drops_the_bracket_form(self) -> None:
        rendered = fc.render_human_inline(_finding(severity=fc.Severity.P2))
        self.assertTrue(rendered.startswith("P2: "))
        self.assertNotIn("[P2]", rendered)

    def test_no_evidence_impact_fix_labels(self) -> None:
        rendered = fc.render_human_inline(_finding())
        for label in ("Evidence:", "Impact:", "Fix:"):
            self.assertNotIn(label, rendered)

    def test_semantic_content_of_every_core_field_survives(self) -> None:
        f = _finding()
        rendered = fc.render_human_inline(f)
        self.assertIn(f.evidence, rendered)
        self.assertIn(f.impact, rendered)
        self.assertIn(f.fix, rendered)

    def test_mandatory_core_is_still_complete_on_the_inline_surface(self) -> None:
        self.assertEqual(
            fc.missing_mandatory_fields(_finding(), surface=fc.Surface.GITHUB_INLINE),
            (),
        )

    def test_structured_and_human_are_two_renderings_of_one_finding(self) -> None:
        f = _finding(
            evidence_location="src/pay/gateway.py:200",  # distinct evidence loc
        )
        self.assertTrue(fc.human_inline_preserves_semantics(f))
        structured = fc.render_inline(f)
        human = fc.render_human_inline(f)
        # same severity, same title substance, no relocation: neither inline
        # form carries an id/Location machine field, and the pointer (which
        # *does* carry location) is identical regardless of inline voice.
        self.assertTrue(structured.startswith("[P1] "))
        self.assertTrue(human.startswith("P1: "))
        self.assertEqual(
            fc.render_summary_pointer(f),
            "- **P1 — Retry can duplicate processing**\n  `src/pay/retry.py:88`",
        )

    def test_distinct_evidence_location_can_be_named_in_prose_without_moving_anchor(self) -> None:
        # the human prose may reference the evidence location; the finding's
        # canonical location (the inline anchor) is unchanged.
        f = _finding(evidence_location="src/pay/gateway.py:200")
        self.assertEqual(f.location, "src/pay/retry.py:88")
        self.assertIn("`src/pay/retry.py:88`", fc.render_summary_pointer(f))
        self.assertNotIn("gateway.py", fc.render_summary_pointer(f))

    def test_unresolved_fix_location_is_not_promoted_by_the_human_voice(self) -> None:
        f = _finding(
            location="src/pay/gateway.py:200",
            evidence_location="src/pay/gateway.py:200",
            fix_location_resolved=False,
        )
        # rendering voice is orthogonal to the resolved/unresolved state
        self.assertFalse(fc.renders_evidence_location(f))
        self.assertTrue(fc.human_inline_preserves_semantics(f))

    def test_details_default_off_inline_and_folds_into_prose_when_selected(self) -> None:
        f = _finding(
            details="Ordering: worker A commits after worker B reads.",
            long_form_category="concurrency_or_ordering",
        )
        self.assertNotIn("worker A commits", fc.render_human_inline(f))
        with_details = fc.render_human_inline(f, finding_detail_override=True)
        self.assertIn("worker A commits", with_details)
        self.assertNotIn("Details:", with_details)

    def test_structured_rendering_is_unchanged_when_the_option_is_not_used(self) -> None:
        # existing callers that select the structured inline shape are intact
        rendered = fc.render_inline(_finding())
        self.assertTrue(rendered.startswith("[P1] "))
        for label in ("Evidence:", "Impact:", "Fix:"):
            self.assertIn(label, rendered)


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


class EvidenceVsFixLocationTests(unittest.TestCase):
    """Issue #164: the finding's `location` is the canonical fix/action
    location; a distinct evidence location renders explicitly; an
    unresolved fix/action location is stated, never promoted from the
    evidence location."""

    def test_no_evidence_location_line_when_it_equals_location(self) -> None:
        rendered = fc.render_full(
            _finding(evidence_location="src/pay/retry.py:88")
        )
        self.assertNotIn("**Evidence location:**", rendered)

    def test_no_evidence_location_line_when_unset(self) -> None:
        self.assertNotIn("**Evidence location:**", fc.render_full(_finding()))

    def test_distinct_evidence_location_renders_after_location(self) -> None:
        rendered = fc.render_full(
            _finding(evidence_location="src/pay/gateway.py:200")
        )
        self.assertIn("- **Evidence location:** src/pay/gateway.py:200", rendered)
        self.assertLess(
            rendered.index("**Location:**"), rendered.index("**Evidence location:**")
        )
        self.assertLess(
            rendered.index("**Evidence location:**"), rendered.index("**Evidence:**")
        )

    def test_canonical_field_order_survives_the_evidence_location_line(self) -> None:
        rendered = fc.render_full(
            _finding(evidence_location="src/pay/gateway.py:200")
        )
        for a, b in (
            ("**Location:**", "**Evidence:**"),
            ("**Evidence:**", "**Impact:**"),
            ("**Impact:**", "**Fix:**"),
        ):
            self.assertLess(rendered.index(a), rendered.index(b))

    def test_unresolved_fix_location_is_annotated_not_promoted(self) -> None:
        rendered = fc.render_full(
            _finding(
                location="src/pay/gateway.py:200",
                evidence_location="src/pay/gateway.py:200",
                fix_location_resolved=False,
            )
        )
        self.assertIn(
            "_(evidence location; fix/action location unresolved)_", rendered
        )
        # no separate Evidence location line in the unresolved case
        self.assertNotIn("**Evidence location:**", rendered)
        self.assertFalse(fc.renders_evidence_location(
            _finding(
                evidence_location="src/pay/gateway.py:200",
                fix_location_resolved=False,
            )
        ))

    def test_unresolved_annotation_follows_source_state_annotation(self) -> None:
        rendered = fc.render_full(
            _finding(
                location_source_annotation="unstaged",
                fix_location_resolved=False,
            )
        )
        self.assertIn(
            "`src/pay/retry.py:88` _(unstaged)_ "
            "_(evidence location; fix/action location unresolved)_",
            rendered,
        )

    def test_inline_rendering_never_adds_an_evidence_location_line(self) -> None:
        rendered = fc.render_inline(
            _finding(evidence_location="src/pay/gateway.py:200")
        )
        self.assertNotIn("Evidence location:", rendered)

    def test_summary_pointer_uses_the_canonical_fix_action_location(self) -> None:
        pointer = fc.render_summary_pointer(
            _finding(
                location="src/pay/retry.py:88",
                evidence_location="src/pay/gateway.py:200",
            )
        )
        self.assertIn("`src/pay/retry.py:88`", pointer)
        self.assertNotIn("gateway.py", pointer)

    def test_new_fields_are_optional_and_backward_compatible(self) -> None:
        # a finding constructed the old way still renders identically
        self.assertNotIn("Evidence location", fc.render_full(_finding()))
        self.assertEqual(
            fc.missing_mandatory_fields(_finding(), surface=fc.Surface.LOCAL_REPORT),
            (),
        )


class SeveritySemanticsUnchangedTests(unittest.TestCase):
    def test_only_the_three_canonical_severities_exist(self) -> None:
        self.assertEqual(
            {s.value for s in fc.Severity}, {"P0", "P1", "P2"}
        )


if __name__ == "__main__":
    unittest.main()
