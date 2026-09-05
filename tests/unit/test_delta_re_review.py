"""Regression tests for the #64 delta re-review reference model.

Exercises tests/reference/delta_re_review.py against
docs/findings/delta-re-review-contract.md's acceptance criteria. This is
the #64 analogue of test_finding_identity_regression.py: it proves the
*semantics*, not #66's broader fixture/regression matrix.
"""

import unittest

from tests.reference.delta_re_review import (
    BlastRadiusClaim,
    ChangeClass,
    EscalationSignals,
    LifecycleState,
    MatchOutcome,
    ResolutionEvidence,
    SettledAssumption,
    classify_change,
    is_attributable,
    is_reportable_outside_delta,
    remains_settled,
    requires_escalation,
)


class ChangeClassificationTests(unittest.TestCase):
    """§2: each change class requires the evidence the contract names."""

    def test_first_detection_has_no_prior_identity(self) -> None:
        cls = classify_change(
            prior_state=None,
            match_outcome=None,
            independently_supported=True,
            touched_by_delta=True,
        )
        self.assertEqual(cls, ChangeClass.NEWLY_INTRODUCED)

    def test_first_detection_requires_independent_support(self) -> None:
        with self.assertRaises(ValueError):
            classify_change(prior_state=None, match_outcome=None, independently_supported=False)

    def test_unchanged_when_untouched_and_still_present(self) -> None:
        cls = classify_change(
            prior_state=LifecycleState.OPEN,
            match_outcome=MatchOutcome.MATCH,
            still_present_evidence=True,
            touched_by_delta=False,
        )
        self.assertEqual(cls, ChangeClass.UNCHANGED)

    def test_moved_when_matched_and_relocated_by_delta(self) -> None:
        cls = classify_change(
            prior_state=LifecycleState.OPEN,
            match_outcome=MatchOutcome.MATCH,
            still_present_evidence=True,
            touched_by_delta=True,
        )
        self.assertEqual(cls, ChangeClass.MOVED)

    def test_fixed_requires_full_resolution_bar(self) -> None:
        full = ResolutionEvidence(
            completed_review=True,
            verified_relevant_coverage=True,
            positive_absence_evidence=True,
            no_continuity_ambiguity=True,
            valid_prior_identity_and_state=True,
        )
        cls = classify_change(
            prior_state=LifecycleState.OPEN,
            match_outcome=MatchOutcome.NO_MATCH,
            resolution_evidence=full,
            touched_by_delta=True,
        )
        self.assertEqual(cls, ChangeClass.FIXED)

    def test_no_match_without_full_resolution_bar_is_ambiguous_not_fixed(self) -> None:
        """Mirrors #62 §5: 'no MATCH' or non-emission alone never resolves."""
        partial = ResolutionEvidence(completed_review=True, verified_relevant_coverage=True)
        cls = classify_change(
            prior_state=LifecycleState.OPEN,
            match_outcome=MatchOutcome.NO_MATCH,
            resolution_evidence=partial,
            touched_by_delta=True,
        )
        self.assertEqual(cls, ChangeClass.AMBIGUOUS)

    def test_reopened_requires_recurrence_evidence_and_match(self) -> None:
        cls = classify_change(
            prior_state=LifecycleState.RESOLVED,
            match_outcome=MatchOutcome.MATCH,
            recurrence_evidence=True,
        )
        self.assertEqual(cls, ChangeClass.REOPENED)

    def test_resolved_prior_without_recurrence_evidence_stays_unchanged(self) -> None:
        """Mirrors #62 §6: similarity elsewhere is not reopening."""
        cls = classify_change(
            prior_state=LifecycleState.RESOLVED,
            match_outcome=MatchOutcome.MATCH,
            recurrence_evidence=False,
        )
        self.assertEqual(cls, ChangeClass.UNCHANGED)

    def test_ambiguous_match_outcome_is_never_a_confident_transition(self) -> None:
        """Acceptance criterion: ambiguous identity never produces a
        confident lifecycle transition, for either prior state."""
        for prior in (LifecycleState.OPEN, LifecycleState.RESOLVED):
            with self.subTest(prior=prior):
                cls = classify_change(
                    prior_state=prior,
                    match_outcome=MatchOutcome.AMBIGUOUS,
                    still_present_evidence=True,
                    recurrence_evidence=True,
                    resolution_evidence=ResolutionEvidence(
                        completed_review=True,
                        verified_relevant_coverage=True,
                        positive_absence_evidence=True,
                        no_continuity_ambiguity=True,
                        valid_prior_identity_and_state=True,
                    ),
                )
                self.assertEqual(cls, ChangeClass.AMBIGUOUS)


class DeltaIsNotAFindingBoundaryTests(unittest.TestCase):
    """§3: delta scope is not treated as a restriction on findings."""

    def test_evidence_based_observation_outside_delta_is_reportable(self) -> None:
        self.assertTrue(is_reportable_outside_delta(evidence_based=True))

    def test_no_scope_parameter_gates_reportability(self) -> None:
        """The function's only input is whether the observation is
        evidence-based — there is deliberately no 'inside_delta' gate to
        pass, proving the contract's function signature itself carries no
        scope restriction."""
        import inspect

        params = inspect.signature(is_reportable_outside_delta).parameters
        self.assertEqual(set(params), {"evidence_based"})


class ResolvedFindingDoesNotSuppressNewDefectTests(unittest.TestCase):
    """Acceptance criterion: resolving a prior finding does not suppress a
    different defect the fix introduces."""

    def test_fixed_prior_and_newly_introduced_defect_coexist(self) -> None:
        full = ResolutionEvidence(
            completed_review=True,
            verified_relevant_coverage=True,
            positive_absence_evidence=True,
            no_continuity_ambiguity=True,
            valid_prior_identity_and_state=True,
        )
        prior_class = classify_change(
            prior_state=LifecycleState.OPEN,
            match_outcome=MatchOutcome.NO_MATCH,
            resolution_evidence=full,
            touched_by_delta=True,
        )
        new_defect_class = classify_change(
            prior_state=None,
            match_outcome=None,
            independently_supported=True,
            touched_by_delta=True,
        )
        self.assertEqual(prior_class, ChangeClass.FIXED)
        self.assertEqual(new_defect_class, ChangeClass.NEWLY_INTRODUCED)
        self.assertTrue(is_reportable_outside_delta(evidence_based=True))


class BlastRadiusTests(unittest.TestCase):
    """§4: attribution is evidence-based, not proximity-based."""

    def test_concrete_mechanism_is_attributable(self) -> None:
        claim = BlastRadiusClaim(causal_mechanism="caller invokes changed signature", source_changed=True)
        self.assertTrue(is_attributable(claim))

    def test_same_file_alone_is_not_attributable(self) -> None:
        claim = BlastRadiusClaim(causal_mechanism=None, source_changed=True)
        self.assertFalse(is_attributable(claim))

    def test_untouched_source_is_not_attributable(self) -> None:
        claim = BlastRadiusClaim(causal_mechanism="shares a config key", source_changed=False)
        self.assertFalse(is_attributable(claim))

    def test_regression_via_blast_radius_is_newly_introduced_and_reportable(self) -> None:
        claim = BlastRadiusClaim(causal_mechanism="shared schema changed", source_changed=True)
        self.assertTrue(is_attributable(claim))
        cls = classify_change(
            prior_state=None,
            match_outcome=None,
            independently_supported=True,
            blast_radius_attributable=is_attributable(claim),
        )
        self.assertEqual(cls, ChangeClass.NEWLY_INTRODUCED)
        self.assertTrue(is_reportable_outside_delta(evidence_based=True))


class SettledAssumptionTests(unittest.TestCase):
    """§6: settled non-findings/assumptions stay settled only while their
    basis is untouched by the new delta."""

    def test_settled_assumption_survives_unrelated_delta(self) -> None:
        assumption = SettledAssumption(basis_touched_by_delta=False, blast_radius_attributable=False)
        self.assertTrue(remains_settled(assumption))

    def test_settled_assumption_invalidated_when_delta_touches_its_basis(self) -> None:
        assumption = SettledAssumption(basis_touched_by_delta=True)
        self.assertFalse(remains_settled(assumption))

    def test_settled_assumption_invalidated_via_blast_radius(self) -> None:
        """Acceptance criterion: the new delta invalidates a previously
        settled assumption, including via blast radius rather than a
        direct edit to the assumption's own site."""
        assumption = SettledAssumption(basis_touched_by_delta=False, blast_radius_attributable=True)
        self.assertFalse(remains_settled(assumption))


class EscalationTests(unittest.TestCase):
    """§7: escalation is a semantic OR of four triggers, not a numeric
    threshold."""

    def test_no_signals_means_no_escalation(self) -> None:
        self.assertFalse(requires_escalation(EscalationSignals()))

    def test_invalidated_assumptions_trigger_escalation(self) -> None:
        self.assertTrue(
            requires_escalation(EscalationSignals(prior_assumptions_materially_invalidated=True))
        )

    def test_untraceable_blast_radius_triggers_escalation(self) -> None:
        self.assertTrue(requires_escalation(EscalationSignals(blast_radius_untraceable=True)))

    def test_broadly_unreliable_matching_triggers_escalation(self) -> None:
        self.assertTrue(requires_escalation(EscalationSignals(matching_broadly_unreliable=True)))

    def test_review_boundary_violation_triggers_escalation(self) -> None:
        self.assertTrue(requires_escalation(EscalationSignals(review_boundary_violated=True)))

    def test_signals_are_boolean_not_numeric(self) -> None:
        """No field looks like a count/threshold — the contract deliberately
        defines no arbitrary numeric trigger."""
        import dataclasses
        import typing

        hints = typing.get_type_hints(EscalationSignals)
        for f in dataclasses.fields(EscalationSignals):
            self.assertIs(hints[f.name], bool)
            self.assertEqual(f.default, False)


if __name__ == "__main__":
    unittest.main()
