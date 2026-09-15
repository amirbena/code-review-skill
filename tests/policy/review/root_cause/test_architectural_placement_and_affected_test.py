#!/usr/bin/env python3
"""Architectural placement / execution-lifecycle fidelity and
affected-test / test-impact analysis.

Contract: shared/policies/architectural-placement.md and
shared/policies/affected-test-analysis.md, extracted from review-scope.md
(Issues #264 and #198 respectively); review-scope.md keeps a thin routing
paragraph under each heading (see test_review_scope_core_wiring.py for the
reachability/routing checks that span every extracted pass).
Prose checks only — there is deliberately no second implementation of the
rules (see policies/skill-development-policy.md, "Runbook Design").
"""

from __future__ import annotations

import unittest

from tests.support.paths import REPO_ROOT
from tests.support.policy_docs import (
    GITHUB_ACTIVE_RUNBOOK,
    GITHUB_PASSIVE_RUNBOOK,
    GITHUB_REASONING,
    GITHUB_REVIEW_INDEX,
    LOCAL_RUNBOOK,
)
from tests.support.policy_docs import extract_section as _section
from tests.support.policy_docs import load_normalized_text as _text

ARCHITECTURAL_PLACEMENT = REPO_ROOT / "shared/policies/architectural-placement.md"
AFFECTED_TEST = REPO_ROOT / "shared/policies/affected-test-analysis.md"


class ArchitecturalPlacementSectionTests(unittest.TestCase):
    """(shared semantics) the placement section is an application of the
    existing scope/evidence model — semantic-risk triggered, bounded,
    evidence-gated, never a name detector or a second scope model."""

    def setUp(self) -> None:
        self.section = _section(
            _text(ARCHITECTURAL_PLACEMENT),
            "## Architectural placement and execution-lifecycle fidelity",
        )

    def test_it_extends_rather_than_replaces_the_existing_model(self) -> None:
        self.assertIn("one concrete application of the proportional-scope", self.section)
        self.assertIn("does not", self.section)
        self.assertIn("introduce a second scope model or a second evidence standard", self.section)
        self.assertIn("Related changes as one unit", self.section)
        self.assertIn("Existing behavior ownership", self.section)
        self.assertIn("Findings beyond the changed lines", self.section)

    def test_triggers_are_semantic_risk_categories_not_structure(self) -> None:
        for category in (
            "control flow / whether downstream code executes at all",
            "externally visible or otherwise irreversible side effects",
            "retry, exception, fallback, or error-propagation behavior",
            "transaction boundaries or transactional ordering",
            "authorization, permission, or policy enforcement",
            "routing, dispatch, handler/strategy selection, or orchestration",
            "idempotency or duplicate suppression",
            "state-mutation ordering",
            "lifecycle bookkeeping",
            "resource ownership or cleanup",
            "concurrency or ordering guarantees",
            "correctness depends on a caller or callee contract",
        ):
            self.assertIn(category, self.section)

    def test_structural_shape_is_explicitly_not_a_trigger(self) -> None:
        self.assertIn(
            "Do not expand context merely because a method is large, a file "
            "changed, an early return exists, or a particular framework, base "
            "class, or method name appears",
            self.section,
        )
        self.assertIn("Structural shape is never itself the trigger", self.section)

    def test_it_is_not_a_fixed_method_name_detector(self) -> None:
        self.assertIn("not a fixed-vocabulary detector", self.section)
        for name in ("shouldHandleEvent", "handle", "supports", "canHandle", "matches"):
            self.assertIn(name, self.section)
        self.assertIn("may appear only in fixtures or examples", self.section)
        self.assertIn("never about matching a name", self.section)

    def test_context_expansion_is_bounded_ring_by_ring(self) -> None:
        self.assertIn("minimum-context-first", self.section)
        self.assertIn("direct caller / callee", self.section)
        self.assertIn("owning abstraction / interface / orchestrator / lifecycle boundary", self.section)
        self.assertIn("only if still necessary", self.section)
        self.assertIn("Do not default to repository-wide exploration", self.section)

    def test_stop_conditions_include_insufficient_evidence_as_terminal(self) -> None:
        self.assertIn("responsibility/lifecycle contract is established", self.section)
        self.assertIn("correctly placed", self.section)
        self.assertIn("would not materially change the review conclusion", self.section)
        self.assertIn("insufficient or ambiguous — fail closed", self.section)
        self.assertIn("disproportionate to the changed behavior", self.section)
        self.assertIn(
            '"Insufficient evidence" is a valid terminal outcome', self.section
        )

    def test_ineligible_vs_must_execute_and_fail_is_distinguished(self) -> None:
        self.assertIn("Ineligible versus must-execute-and-fail", self.section)
        self.assertIn("NotFoundException", self.section)
        self.assertIn("existing retry semantics are preserved", self.section)
        self.assertIn("is not a misplacement", self.section)
        self.assertIn("not from a special-cased rule", self.section)

    def test_guardrails_forbid_naming_only_inference_and_preference_findings(self) -> None:
        self.assertIn("Do not infer an architectural boundary from naming alone", self.section)
        self.assertIn("Do not flag an alternative design merely because the reviewer prefers", self.section)
        self.assertIn(
            "Preserve intentional execution-time validation, retry/error "
            "semantics, transaction semantics",
            self.section,
        )
        self.assertIn("do not invent it", self.section)

    def test_finding_requires_evidence_of_both_placement_and_boundary(self) -> None:
        self.assertIn(
            "concrete repository evidence of both the changed code's actual placement",
            self.section,
        )
        self.assertIn("the responsibility boundary it allegedly violates", self.section)
        self.assertIn("Naming similarity alone is insufficient", self.section)
        self.assertIn("unresolvable ambiguity yields no finding", self.section)

    def test_evidence_labels_are_reused_not_redefined(self) -> None:
        self.assertIn(
            "confirmed defect / credible engineering risk / optional improvement",
            self.section,
        )


class AnalogueBasedPlacementPatternInferenceTests(unittest.TestCase):
    """Issue #327: a second, independently gated trigger class for an
    undocumented structural/organizational responsibility-placement
    pattern, distinct from the lifecycle-semantic trigger vocabulary
    above and never a generic style-consistency checker."""

    def setUp(self) -> None:
        self.full_text = _text(ARCHITECTURAL_PLACEMENT)
        self.section = _section(
            self.full_text,
            "## Analogue-based responsibility/placement pattern inference",
        )

    def test_it_is_a_second_trigger_class_not_a_modification_of_the_first(self) -> None:
        self.assertIn("second, independently gated trigger class", self.section)
        self.assertIn(
            "this section adds a second trigger class, it does not modify the first",
            self.section,
        )
        intro = _section(
            self.full_text,
            "# Shared Policy",
            "## Architectural placement and execution-lifecycle fidelity",
        )
        self.assertIn("Analogue-based responsibility/", intro)

    def test_it_is_not_a_generic_style_consistency_checker(self) -> None:
        self.assertIn("not a generic style-consistency checker", self.section)
        self.assertIn(
            "does not encode any specific preferred structure", self.section
        )
        self.assertIn(
            "Repeated structure alone is never proof that a new, differently "
            "organized implementation is wrong",
            self.section,
        )

    def test_applicability_requires_no_explicit_instruction_and_no_lifecycle_trigger(
        self,
    ) -> None:
        self.assertIn("### When this trigger applies", self.section)
        self.assertIn("repository-instructions.md", self.section)
        self.assertIn(
            "does not already trip one of the semantic-risk triggers above",
            self.section,
        )
        self.assertIn(
            "never a second route to the same lifecycle-semantic findings",
            self.section,
        )

    def test_reasoning_sequence_matches_the_issue_order(self) -> None:
        self.assertIn("### Reasoning sequence", self.section)
        self.assertIn(
            "Identify the specific responsibility the change introduces, "
            "moves, or reorganizes",
            self.section,
        )
        self.assertIn("nearest meaningful analogous implementations", self.section)
        self.assertIn(
            "minimum-context-first, one-ring-at-a-time investigation model",
            self.section,
        )
        self.assertIn("cosmetic repetition", self.section)
        self.assertIn(
            "investigate whether the deviation is intentional or otherwise "
            "justified",
            self.section,
        )
        self.assertIn(
            "concrete architectural, ownership, lifecycle, or integration",
            self.section,
        )

    def test_repetition_is_evidence_never_authority_guardrail(self) -> None:
        self.assertIn(
            "Frequency or repetition of a structural pattern across the "
            "repository is, at most, evidence that a convention may exist",
            self.section,
        )
        self.assertIn("never authority", self.section)
        self.assertIn(
            "never by itself proof that a differently organized "
            "implementation is defective",
            self.section,
        )

    def test_explicit_instructions_outrank_inferred_patterns(self) -> None:
        self.assertIn(
            "### Explicit instructions versus inferred patterns", self.section
        )
        self.assertIn("remain the authoritative source", self.section)
        self.assertIn(
            "never overrides or contradicts an explicit instruction that does",
            self.section,
        )

    def test_analogue_inspection_is_bounded_not_unbounded(self) -> None:
        self.assertIn("### Bounded, not an unbounded search", self.section)
        self.assertIn(
            'reuses "Bounded context expansion" and "Stop conditions" above '
            "without modification",
            self.section,
        )
        self.assertIn("insufficient evidence", self.section)
        self.assertIn(
            "never license to enumerate every file in the repository",
            self.section,
        )

    def test_interaction_with_root_cause_consolidation_is_documented(self) -> None:
        self.assertIn("### Interaction with root-cause consolidation", self.section)
        self.assertIn("root-cause-consolidation.md", self.section)
        self.assertIn(
            "this section documents the interaction, it does not redefine "
            "that policy's clustering model",
            self.section,
        )
        self.assertIn(
            "never automatically split into one finding per site merely "
            "because the same deviation surfaced at more than one location",
            self.section,
        )

    def test_guardrails_forbid_naming_and_preference_findings(self) -> None:
        self.assertIn(
            'Every guardrail in "Guardrails" above applies unchanged '
            "to this trigger",
            self.section,
        )
        self.assertIn(
            "coincidental structural resemblance", self.section
        )
        self.assertIn(
            "a concrete consequence is required, never aesthetic or "
            "stylistic preference",
            self.section,
        )
        self.assertIn(
            "never itself raises the severity of a resulting finding",
            self.section,
        )

    def test_non_goals_forbid_style_enforcement_and_auto_refactor(self) -> None:
        self.assertIn("### Non-goals", self.section)
        self.assertIn("Automatically refactoring or moving a deviating", self.section)
        self.assertIn("detection/finding only", self.section)


class ArchitecturalPlacementWiredIntoBothSkillsTests(unittest.TestCase):
    def test_github_review_reasoning_forwards_to_the_shared_section(self) -> None:
        text = _text(GITHUB_REASONING)
        self.assertIn("## Architectural Placement Review", text)
        self.assertIn("Architectural placement and execution-lifecycle fidelity", text)
        self.assertIn("this PR-specific policy does not restate them", text)

    def test_github_review_reasoning_gate_also_covers_the_analogue_trigger(self) -> None:
        # Issue #327: the entry gate above must not be scoped to the
        # lifecycle-semantic trigger alone, or github-pr-review would never
        # reach the second, independently gated analogue-based trigger.
        section = _section(
            _text(GITHUB_REASONING),
            "## Architectural Placement Review",
            "## Code Impact / Dependency Analysis",
        )
        self.assertIn("Analogue-based responsibility/", section)
        self.assertIn(
            "both the lifecycle-semantic vocabulary and the independently "
            "gated analogue-based structural/organizational trigger",
            section,
        )

    def test_github_review_index_lists_placement_reasoning(self) -> None:
        text = _text(GITHUB_REVIEW_INDEX)
        self.assertIn("architectural placement", text)

    def test_local_runbook_marks_the_section_signal_triggered(self) -> None:
        text = _text(LOCAL_RUNBOOK)
        window = _section(
            text,
            "Architectural placement and execution-lifecycle",
            "Classify findings per",
        )
        self.assertIn("signal-triggered per that policy's own gating conditions", window)
        self.assertIn("not applied", window)
        self.assertIn("unconditionally to every diff", window)


class AffectedTestImpactAnalysisTests(unittest.TestCase):
    """(shared semantics) affected-test / test-impact analysis is
    signal-triggered, read-only, evidence-gated, bounded to blast radius,
    and explicitly not a "did the PR add tests?" check or a second scope
    model."""

    def setUp(self) -> None:
        self.section = _section(
            _text(AFFECTED_TEST),
            "## Affected-test / test-impact analysis",
        )

    def test_reasoning_chain_runs_from_changed_code_into_dependent_tests(self) -> None:
        self.assertIn(
            "affected observable behavior / contract / branch / interaction",
            self.section,
        )
        self.assertIn(
            "existing tests that exercise or depend on that behavior", self.section
        )
        self.assertIn("regression / coverage impact", self.section)

    def test_unchanged_tests_outside_the_diff_are_in_bounds_evidence(self) -> None:
        self.assertIn("frequently not in the diff", self.section)
        self.assertIn('complement of "Related changes as one unit"', self.section)
        self.assertIn(
            "including tests outside the changed-file set", self.section
        )

    def test_it_is_signal_triggered_not_every_diff(self) -> None:
        self.assertIn("### When this applies — signal-triggered", self.section)
        self.assertIn(
            "does not trigger it and requires no action", self.section
        )

    def test_it_is_not_did_the_pr_add_tests(self) -> None:
        self.assertIn('not "did the PR add tests?"', self.section)
        self.assertIn(
            "a production change is never required to add or modify a test "
            "on its own",
            self.section,
        )

    def test_discovery_is_not_claimed_exhaustive(self) -> None:
        self.assertIn("No exhaustive impact discovery", self.section)
        self.assertIn(
            "not to prove every affected test was found", self.section
        )

    def test_read_only_never_runs_target_repository_tests(self) -> None:
        self.assertIn(
            "authorizes running the target repository's tests", self.section
        )
        self.assertIn("git-safety.md", self.section)
        self.assertIn("runtime-validation.md", self.section)

    def test_not_a_repository_wide_test_audit(self) -> None:
        self.assertIn("Not a repository-wide test audit", self.section)
        self.assertIn("merely shares a name or module", self.section)
        self.assertIn(
            "pre-existing test weakness the change does not touch", self.section
        )

    def test_reuses_existing_evidence_and_decision_model(self) -> None:
        self.assertIn("adds no second scope or evidence model", self.section)
        self.assertIn(
            "confirmed defect / credible engineering risk / optional improvement",
            self.section,
        )
        self.assertIn("still derives the decision mechanically", self.section)

    def test_severity_examples_follow_severity_md_bar(self) -> None:
        self.assertIn("is typically P1", self.section)
        self.assertIn("a lower-risk gap is P2", self.section)


class AffectedTestImpactWiredIntoBothSkillsTests(unittest.TestCase):
    def test_github_review_reasoning_forwards_to_the_shared_section(self) -> None:
        text = _text(GITHUB_REASONING)
        self.assertIn("## Affected-Test Impact Review", text)
        self.assertIn("Affected-test / test-impact analysis", text)
        self.assertIn("this PR-specific policy does not restate them", text)
        self.assertIn("not a second scope model", text)

    def test_github_review_index_lists_affected_test_reasoning(self) -> None:
        text = _text(GITHUB_REVIEW_INDEX)
        self.assertIn("affected-test", text)

    def test_both_github_runbooks_name_the_forwarding_subsection(self) -> None:
        for runbook in (GITHUB_ACTIVE_RUNBOOK, GITHUB_PASSIVE_RUNBOOK):
            text = _text(runbook)
            self.assertIn("Affected-Test Impact Review", text)

    def test_local_runbook_marks_the_section_signal_triggered(self) -> None:
        text = _text(LOCAL_RUNBOOK)
        window = _section(
            text,
            "Affected-test / test-impact analysis",
            "Classify findings per",
        )
        self.assertIn(
            "signal-triggered per that policy's own gating conditions", window
        )
        self.assertIn("not applied", window)
        self.assertIn("unconditionally to every diff", window)


if __name__ == "__main__":
    unittest.main()
