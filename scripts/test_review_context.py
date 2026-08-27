#!/usr/bin/env python3
"""Coverage for optional review-context handling (review_context.py).

Contract: skills/local-code-review/policies/review-context.md.
"""

from __future__ import annotations

import inspect
import unittest

import review_context as rc


LOCAL_DELTA_TOUCHES = frozenset({"src/payments/charge.py", "src/payments/charge_test.py"})
UNRELATED_TOUCHES = frozenset({"docs/marketing/landing-page-copy.md"})


class NoContextTests(unittest.TestCase):
    """Scenario: no context supplied — existing review behavior is valid
    and unchanged, and this Skill never prompts for context."""

    def test_no_context_never_blocks_the_review(self) -> None:
        for state in rc.ReviewContextAvailability:
            with self.subTest(state=state):
                self.assertFalse(rc.should_block_local_review(state))

    def test_never_prompts_the_user_for_context(self) -> None:
        self.assertFalse(rc.should_prompt_user_for_context(context_supplied=False))
        self.assertFalse(rc.should_prompt_user_for_context(context_supplied=True))

    def test_no_context_never_shows_the_context_section(self) -> None:
        self.assertFalse(
            rc.context_section_required(
                context_supplied=False,
                focused_a_finding=True,
                surfaced_a_mismatch=True,
                non_goal_prevented_a_false_gap=True,
            )
        )


class FreeFormContextTests(unittest.TestCase):
    """Scenario: reviewer can consume plain free-form requirements."""

    def test_free_form_context_normalizes_with_only_raw_text_required(self) -> None:
        ctx = rc.ReviewContext(raw_context="Validation must happen before execution.")
        self.assertEqual(ctx.raw_context, "Validation must happen before execution.")
        self.assertIsNone(ctx.source_type)
        self.assertIsNone(ctx.source_name)
        self.assertEqual(ctx.acceptance_criteria, ())
        self.assertEqual(ctx.constraints, ())
        self.assertEqual(ctx.explicit_non_goals, ())


class AcceptanceCriteriaTests(unittest.TestCase):
    """Scenario: context can identify a behavior that should be inspected."""

    def test_jira_context_with_acceptance_criteria_normalizes_fully(self) -> None:
        ctx = rc.ReviewContext(
            raw_context="reject unsupported CC + RTP combinations",
            source_type="jira",
            source_name="BILLPAY-1234",
            acceptance_criteria=(
                "reject unsupported CC + RTP combinations",
                "preserve per-company IXP",
                "validation must occur before execution",
            ),
        )
        self.assertEqual(ctx.source_name, "BILLPAY-1234")
        self.assertEqual(len(ctx.acceptance_criteria), 3)

    def test_focus_area_overlapping_delta_is_in_scope(self) -> None:
        self.assertTrue(
            rc.is_within_current_delta_scope({"src/payments/charge.py"}, LOCAL_DELTA_TOUCHES)
        )

    def test_focus_area_outside_delta_is_out_of_scope(self) -> None:
        self.assertFalse(rc.is_within_current_delta_scope(UNRELATED_TOUCHES, LOCAL_DELTA_TOUCHES))

    def test_focus_area_with_no_touches_is_never_in_scope(self) -> None:
        self.assertFalse(rc.is_within_current_delta_scope(frozenset(), LOCAL_DELTA_TOUCHES))


class ContextDerivedFindingTests(unittest.TestCase):
    """Scenario: a concrete implementation violation can be associated with
    a supplied requirement."""

    def test_clear_violation_is_reported_unconditionally(self) -> None:
        classification = rc.classify_mismatch(
            implementation_clearly_contradicts_requirement=True,
            context_conflicts_with_repository_architecture=False,
            requirement_is_ambiguous=False,
            requirement_targets_code_outside_current_diff=False,
        )
        self.assertEqual(
            classification, rc.MismatchClassification.IMPLEMENTATION_VIOLATES_REQUIREMENT
        )
        self.assertTrue(rc.should_report_as_unconditional_finding(classification))

    def test_context_materially_shaping_review_shows_the_section(self) -> None:
        self.assertTrue(
            rc.context_section_required(context_supplied=True, focused_a_finding=True)
        )

    def test_context_with_no_material_effect_stays_quiet(self) -> None:
        self.assertFalse(rc.context_section_required(context_supplied=True))


class ContextContradictionTests(unittest.TestCase):
    """Scenario: context alone must not override stronger repository/code
    evidence."""

    def test_evidence_precedence_order_is_code_then_repo_then_context_then_inference(
        self,
    ) -> None:
        self.assertEqual(
            rc.EVIDENCE_PRECEDENCE_ORDER,
            (
                rc.EvidenceSource.CODE_DIFF_TESTS_CONFIG,
                rc.EvidenceSource.REPOSITORY_INSTRUCTIONS,
                rc.EvidenceSource.SUPPLIED_REVIEW_CONTEXT,
                rc.EvidenceSource.REVIEWER_INFERENCE,
            ),
        )

    def test_code_evidence_always_outranks_supplied_context(self) -> None:
        self.assertEqual(
            rc.stronger_source(
                rc.EvidenceSource.CODE_DIFF_TESTS_CONFIG,
                rc.EvidenceSource.SUPPLIED_REVIEW_CONTEXT,
            ),
            rc.EvidenceSource.CODE_DIFF_TESTS_CONFIG,
        )

    def test_no_source_ever_outranks_code_evidence(self) -> None:
        for source in rc.EvidenceSource:
            with self.subTest(source=source):
                self.assertFalse(rc.context_outranks_code(source))

    def test_stale_or_conflicting_context_is_not_an_automatic_finding(self) -> None:
        classification = rc.classify_mismatch(
            implementation_clearly_contradicts_requirement=False,
            context_conflicts_with_repository_architecture=True,
            requirement_is_ambiguous=False,
            requirement_targets_code_outside_current_diff=False,
        )
        self.assertEqual(
            classification,
            rc.MismatchClassification.CONTEXT_STALE_OR_CONFLICTS_WITH_ARCHITECTURE,
        )
        self.assertFalse(rc.should_report_as_unconditional_finding(classification))

    def test_ambiguous_requirement_is_not_an_automatic_finding(self) -> None:
        classification = rc.classify_mismatch(
            implementation_clearly_contradicts_requirement=False,
            context_conflicts_with_repository_architecture=False,
            requirement_is_ambiguous=True,
            requirement_targets_code_outside_current_diff=False,
        )
        self.assertEqual(classification, rc.MismatchClassification.REQUIREMENT_AMBIGUOUS)
        self.assertFalse(rc.should_report_as_unconditional_finding(classification))


class NonGoalTests(unittest.TestCase):
    """Scenario: explicit context saying something is outside scope should
    prevent accidental scope expansion where appropriate — but never
    suppress a genuine regression."""

    def test_non_goal_suppresses_missing_implementation_finding(self) -> None:
        effect = rc.apply_explicit_non_goal(
            would_be_missing_implementation_finding=True, introduces_regression=False
        )
        self.assertEqual(effect, rc.NonGoalEffect.SUPPRESSES_MISSING_IMPLEMENTATION_FINDING)

    def test_non_goal_never_suppresses_a_genuine_regression(self) -> None:
        effect = rc.apply_explicit_non_goal(
            would_be_missing_implementation_finding=True, introduces_regression=True
        )
        self.assertEqual(effect, rc.NonGoalEffect.DOES_NOT_SUPPRESS_REGRESSION_FINDING)

    def test_out_of_scope_requirement_with_no_regression_and_no_gap_is_a_noop(self) -> None:
        effect = rc.apply_explicit_non_goal(
            would_be_missing_implementation_finding=False, introduces_regression=False
        )
        self.assertIsNone(effect)

    def test_non_goal_prevented_false_gap_shows_the_context_section(self) -> None:
        self.assertTrue(
            rc.context_section_required(
                context_supplied=True, non_goal_prevented_a_false_gap=True
            )
        )


class OutOfDiffRequirementTests(unittest.TestCase):
    """Scenario: context describes work outside the current diff — do not
    demand unrelated implementation."""

    def test_requirement_outside_diff_falls_through_to_out_of_scope_classification(
        self,
    ) -> None:
        classification = rc.classify_mismatch(
            implementation_clearly_contradicts_requirement=False,
            context_conflicts_with_repository_architecture=False,
            requirement_is_ambiguous=False,
            requirement_targets_code_outside_current_diff=True,
        )
        self.assertEqual(classification, rc.MismatchClassification.OUTSIDE_CURRENT_DIFF)
        self.assertFalse(rc.should_report_as_unconditional_finding(classification))


class GovernanceInvariantTests(unittest.TestCase):
    """Cross-cutting invariants that must hold regardless of any single
    scenario, mirroring pr_context_reconciliation.py's governance tests."""

    def test_module_defines_no_github_mutating_or_context_trusting_capability(self) -> None:
        public_names = {name for name in dir(rc) if not name.startswith("_")}
        offending = {
            name
            for name in public_names
            if any(fragment in name.lower() for fragment in rc.PROHIBITED_CAPABILITY_NAME_FRAGMENTS)
        }
        self.assertEqual(
            offending,
            set(),
            "review_context.py must stay read-only and must never let supplied "
            "context outrank code evidence or gain a GitHub-mutating capability",
        )

    def test_no_function_accepts_an_approval_or_ownership_bypass_parameter(self) -> None:
        suspicious_param_fragments = ("approv", "ownership", "bypass")
        for name, obj in inspect.getmembers(rc):
            if not inspect.isfunction(obj):
                continue
            for param_name in inspect.signature(obj).parameters:
                lowered = param_name.lower()
                for fragment in suspicious_param_fragments:
                    self.assertNotIn(
                        fragment,
                        lowered,
                        f"{name}() must not accept an approval/ownership-bypass "
                        f"parameter, found: {param_name}",
                    )

    def test_review_context_dataclass_carries_no_severity_or_decision_field(self) -> None:
        # Governance: context informs findings/severity, it never assigns
        # them itself — see review-context.md, "Evidence hierarchy" /
        # "Output." Structural guarantee: no such field exists to misuse.
        dataclass_fields = {f.name for f in rc.ReviewContext.__dataclass_fields__.values()}
        self.assertNotIn("severity", dataclass_fields)
        self.assertNotIn("decision", dataclass_fields)


if __name__ == "__main__":
    unittest.main()
