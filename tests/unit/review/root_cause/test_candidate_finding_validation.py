#!/usr/bin/env python3
"""Behavioral coverage for the candidate-finding validation model (Issue #382).

Contract:
docs/candidate-finding-validation/candidate-finding-validation-model.md.
Regression focus: semantic-role validation gates a candidate only when its
own reasoning depends on comparing two or more usages -- a comparison-
dependent mismatch never becomes a candidate, while a standalone candidate
(no comparison at all, e.g. a technical-invariant violation) is never
gated by it; reviewer inference alone never establishes a blocking premise
while every other grounding source (including technical invariant, with no
ticket) does; the causal chain and regression-proof checks require every
link/evidence piece, not merely some; disconfirmation can survive, drop,
downgrade, or reclassify a candidate; only a proven correctness defect is
normally blocking; and classification / blocking_justification_valid stay
orthogonal dimensions -- classification answers "what is this?" from
evidence alone, is never derived from material_impact, and a proven
correctness defect with insufficient material impact is still classified
as a proven correctness defect, only ineligible to block; claim_valid and
blocking_justification_valid likewise stay independent -- a kept finding
is never silently suppressed for failing the blocking bar alone.
"""

from __future__ import annotations

import unittest

from tests.reference.review import candidate_finding_validation as cfv

G = cfv.GroundingSource
D = cfv.DisconfirmationOutcome
C = cfv.Classification


def _complete_chain() -> cfv.CausalChain:
    return cfv.CausalChain(
        reviewed_change="split read/write with no lock",
        changed_assumption="single-writer assumed, not enforced",
        concrete_failure_condition="two concurrent debits interleave",
        observable_incorrect_result="balance can go negative",
    )


def _proven_regression() -> cfv.RegressionClaim:
    return cfv.RegressionClaim(
        prior_behavior_evidence="pre-change code path",
        change_evidence="the diff",
        failure_scenario_evidence="new behavior under the diff",
        causal_link_evidence="the diff caused the new behavior",
    )


class GroundingHierarchyTests(unittest.TestCase):
    def test_every_source_has_a_unique_rank(self) -> None:
        ranks = list(cfv.GROUNDING_RANK.values())
        self.assertEqual(sorted(ranks), list(range(1, 8)))

    def test_reviewer_inference_alone_cannot_establish_blocking_premise(self) -> None:
        self.assertFalse(cfv.can_establish_blocking_premise([G.REVIEWER_INFERENCE_ALONE]))

    def test_every_other_source_can_establish_blocking_premise_alone(self) -> None:
        for source in cfv.GroundingSource:
            if source is G.REVIEWER_INFERENCE_ALONE:
                continue
            self.assertTrue(cfv.can_establish_blocking_premise([source]), source)

    def test_technical_invariant_requires_no_ticket(self) -> None:
        # #382's explicit preservation: a technically-grounded blocking
        # finding needs no requirement/Jira source at all.
        self.assertIn(G.TECHNICAL_INVARIANT, cfv.NO_TICKET_REQUIRED)
        self.assertTrue(cfv.can_establish_blocking_premise([G.TECHNICAL_INVARIANT]))

    def test_mixed_sources_with_any_non_inference_source_qualify(self) -> None:
        self.assertTrue(
            cfv.can_establish_blocking_premise(
                [G.REVIEWER_INFERENCE_ALONE, G.NEARBY_PRECEDENT]
            )
        )


class SemanticRoleValidationTests(unittest.TestCase):
    def test_same_primitive_different_responsibility_is_not_comparable(self) -> None:
        self.assertFalse(
            cfv.semantic_roles_comparable(
                same_underlying_primitive=True, same_responsibility=False
            )
        )

    def test_same_primitive_same_responsibility_is_comparable(self) -> None:
        self.assertTrue(
            cfv.semantic_roles_comparable(
                same_underlying_primitive=True, same_responsibility=True
            )
        )

    def test_same_primitive_different_responsibility_cannot_support_a_defect(self) -> None:
        # Required case 1: a comparison-dependent candidate whose two usages
        # share a primitive but serve different responsibilities is dropped
        # entirely -- the comparison itself cannot support the claim.
        self.assertFalse(
            cfv.semantic_roles_comparable(
                same_underlying_primitive=True, same_responsibility=False
            )
        )
        outcome = cfv.evaluate_candidate(
            involves_comparison=True,
            semantic_roles_ok=cfv.semantic_roles_comparable(
                same_underlying_primitive=True, same_responsibility=False
            ),
            grounding_sources=[G.TECHNICAL_INVARIANT],
            causal_chain=_complete_chain(),
        )
        self.assertFalse(outcome.claim_valid)
        self.assertFalse(outcome.blocking_justification_valid)
        self.assertIsNone(outcome.classification)

    def test_standalone_technical_invariant_defect_needs_no_comparison(self) -> None:
        # Required case 2: a candidate that never compares usages at all
        # (design record Section 4, "Applicability") is fully eligible for
        # validation/blocking -- semantic_roles_ok is never even assessed,
        # and passing it as False changes nothing when involves_comparison
        # is False.
        outcome = cfv.evaluate_candidate(
            involves_comparison=False,
            semantic_roles_ok=False,
            grounding_sources=[G.TECHNICAL_INVARIANT],
            causal_chain=_complete_chain(),
            disconfirmation=D.SURVIVES,
        )
        self.assertTrue(outcome.claim_valid)
        self.assertTrue(outcome.blocking_justification_valid)
        self.assertEqual(outcome.classification, C.PROVEN_CORRECTNESS_DEFECT)


class CausalChainTests(unittest.TestCase):
    def test_complete_chain_is_complete(self) -> None:
        self.assertTrue(_complete_chain().is_complete())

    def test_missing_any_link_is_incomplete(self) -> None:
        base = _complete_chain()
        for field_name in (
            "reviewed_change",
            "changed_assumption",
            "concrete_failure_condition",
            "observable_incorrect_result",
        ):
            kwargs = {
                "reviewed_change": base.reviewed_change,
                "changed_assumption": base.changed_assumption,
                "concrete_failure_condition": base.concrete_failure_condition,
                "observable_incorrect_result": base.observable_incorrect_result,
            }
            kwargs[field_name] = ""
            self.assertFalse(cfv.CausalChain(**kwargs).is_complete(), field_name)

    def test_inconsistency_alone_is_incomplete(self) -> None:
        # "These paths are inconsistent" supplies at most links 1-2.
        chain = cfv.CausalChain(
            reviewed_change="path A now differs from path B",
            changed_assumption="handling diverged",
        )
        self.assertFalse(chain.is_complete())


class RegressionProofTests(unittest.TestCase):
    def test_all_four_pieces_present_is_proven(self) -> None:
        self.assertTrue(_proven_regression().is_proven())

    def test_missing_prior_behavior_evidence_is_not_proven(self) -> None:
        claim = cfv.RegressionClaim(
            change_evidence="the diff",
            failure_scenario_evidence="new behavior",
            causal_link_evidence="the diff caused it",
        )
        self.assertFalse(claim.is_proven())

    def test_empty_claim_is_not_proven(self) -> None:
        self.assertFalse(cfv.RegressionClaim().is_proven())


class DisconfirmationTests(unittest.TestCase):
    def test_no_contradiction_survives(self) -> None:
        self.assertEqual(cfv.disconfirm(), D.SURVIVES)

    def test_non_authoritative_contradiction_survives(self) -> None:
        self.assertEqual(
            cfv.disconfirm(
                contradicting_evidence_found=True, contradiction_is_authoritative=False
            ),
            D.SURVIVES,
        )

    def test_authoritative_full_disproof_is_dropped(self) -> None:
        self.assertEqual(
            cfv.disconfirm(
                contradicting_evidence_found=True,
                contradiction_is_authoritative=True,
                contradiction_fully_disproves=True,
            ),
            D.DROPPED,
        )

    def test_authoritative_reclassifying_contradiction_is_reclassified(self) -> None:
        self.assertEqual(
            cfv.disconfirm(
                contradicting_evidence_found=True,
                contradiction_is_authoritative=True,
                contradiction_reclassifies=True,
            ),
            D.RECLASSIFIED,
        )

    def test_authoritative_partial_contradiction_is_downgraded(self) -> None:
        self.assertEqual(
            cfv.disconfirm(
                contradicting_evidence_found=True, contradiction_is_authoritative=True
            ),
            D.DOWNGRADED,
        )


class ClassificationBlockingTests(unittest.TestCase):
    def test_only_proven_correctness_defect_is_normally_blocking(self) -> None:
        self.assertEqual(cfv.NORMALLY_BLOCKING, frozenset({C.PROVEN_CORRECTNESS_DEFECT}))
        for classification in cfv.Classification:
            expected = classification is C.PROVEN_CORRECTNESS_DEFECT
            self.assertEqual(cfv.is_normally_blocking(classification), expected)


class WorkedExampleCorpusTests(unittest.TestCase):
    """Each case mirrors a "Worked example N" block in the design record."""

    def test_example_1_technical_invariant_no_jira_blocking(self) -> None:
        outcome = cfv.evaluate_candidate(
            involves_comparison=False,
            grounding_sources=[G.TECHNICAL_INVARIANT],
            causal_chain=_complete_chain(),
            disconfirmation=D.SURVIVES,
        )
        self.assertTrue(outcome.claim_valid)
        self.assertTrue(outcome.blocking_justification_valid)
        self.assertEqual(outcome.classification, C.PROVEN_CORRECTNESS_DEFECT)

    def test_example_2_semantic_role_mismatch_is_never_a_candidate(self) -> None:
        outcome = cfv.evaluate_candidate(
            involves_comparison=True,
            semantic_roles_ok=False,
            grounding_sources=[G.TECHNICAL_INVARIANT],
            causal_chain=_complete_chain(),
        )
        self.assertFalse(outcome.claim_valid)
        self.assertIsNone(outcome.classification)

    def test_example_3_unproven_regression_is_downgraded_not_discarded(self) -> None:
        outcome = cfv.evaluate_candidate(
            semantic_roles_ok=True,
            grounding_sources=[G.ESTABLISHED_PRODUCTION_BEHAVIOR],
            causal_chain=_complete_chain(),
            is_regression_claim=True,
            regression_claim=cfv.RegressionClaim(change_evidence="the diff"),
        )
        self.assertTrue(outcome.claim_valid)
        self.assertFalse(outcome.blocking_justification_valid)
        self.assertEqual(outcome.classification, C.TEST_COVERAGE_GAP)

    def test_example_4_reviewer_inference_alone_is_non_blocking(self) -> None:
        outcome = cfv.evaluate_candidate(
            semantic_roles_ok=True,
            grounding_sources=[G.REVIEWER_INFERENCE_ALONE],
            causal_chain=_complete_chain(),
        )
        self.assertTrue(outcome.claim_valid)
        self.assertFalse(outcome.blocking_justification_valid)
        self.assertEqual(outcome.classification, C.MAINTAINABILITY_CONCERN)

    def test_example_5_disconfirmation_drops_the_candidate(self) -> None:
        outcome = cfv.evaluate_candidate(
            semantic_roles_ok=True,
            grounding_sources=[G.TECHNICAL_INVARIANT],
            causal_chain=_complete_chain(),
            disconfirmation=D.DROPPED,
        )
        self.assertFalse(outcome.claim_valid)
        self.assertFalse(outcome.blocking_justification_valid)
        self.assertIsNone(outcome.classification)


class FindingValidityVsBlockingJustificationTests(unittest.TestCase):
    def test_kept_but_downgraded_finding_is_not_suppressed(self) -> None:
        # No Jira, no test, no established behavior, no technical invariant
        # -- only reviewer inference. Still kept, just not blocking.
        outcome = cfv.evaluate_candidate(
            semantic_roles_ok=True,
            grounding_sources=[G.REVIEWER_INFERENCE_ALONE],
            causal_chain=_complete_chain(),
        )
        self.assertTrue(outcome.claim_valid, "a downgraded finding is kept, not dropped")
        self.assertFalse(outcome.blocking_justification_valid)

    def test_incomplete_causal_chain_is_a_coverage_gap_not_a_proven_defect(self) -> None:
        outcome = cfv.evaluate_candidate(
            semantic_roles_ok=True,
            grounding_sources=[G.TECHNICAL_INVARIANT],
            causal_chain=cfv.CausalChain(
                reviewed_change="path diverges",
                changed_assumption="handling changed",
            ),
        )
        self.assertTrue(outcome.claim_valid)
        self.assertFalse(outcome.blocking_justification_valid)
        self.assertEqual(outcome.classification, C.TEST_COVERAGE_GAP)

    def test_no_material_impact_is_never_blocking(self) -> None:
        outcome = cfv.evaluate_candidate(
            semantic_roles_ok=True,
            grounding_sources=[G.TECHNICAL_INVARIANT],
            causal_chain=_complete_chain(),
            material_impact=False,
        )
        self.assertTrue(outcome.claim_valid)
        self.assertFalse(outcome.blocking_justification_valid)
        # Classification answers "what is this?" from evidence alone -- low
        # impact never demotes a proven defect to another classification.
        self.assertEqual(outcome.classification, C.PROVEN_CORRECTNESS_DEFECT)

    def test_case_a_proven_defect_non_blocking_impact_stays_a_defect(self) -> None:
        # #382 follow-up 2, Case A: a fully proven correctness defect whose
        # impact does not clear the P0/P1 bar remains classified as exactly
        # that defect -- it must not fall through to REQUIREMENT_AMBIGUITY,
        # TEST_COVERAGE_GAP, or MAINTAINABILITY_CONCERN merely because
        # material_impact is False.
        outcome = cfv.evaluate_candidate(
            grounding_sources=[G.TECHNICAL_INVARIANT],
            causal_chain=_complete_chain(),
            disconfirmation=D.SURVIVES,
            material_impact=False,
        )
        self.assertTrue(outcome.claim_valid)
        self.assertEqual(outcome.classification, C.PROVEN_CORRECTNESS_DEFECT)
        self.assertFalse(outcome.blocking_justification_valid)

    def test_case_b_same_proven_defect_with_blocking_impact(self) -> None:
        # #382 follow-up 2, Case B: the positive counterpart of Case A --
        # identical evidence, but material impact is now established, so
        # the same classification also clears the blocking bar.
        outcome = cfv.evaluate_candidate(
            grounding_sources=[G.TECHNICAL_INVARIANT],
            causal_chain=_complete_chain(),
            disconfirmation=D.SURVIVES,
            material_impact=True,
        )
        self.assertTrue(outcome.claim_valid)
        self.assertEqual(outcome.classification, C.PROVEN_CORRECTNESS_DEFECT)
        self.assertTrue(outcome.blocking_justification_valid)

    def test_downgraded_disconfirmation_classifies_as_requirement_ambiguity(self) -> None:
        # A DOWNGRADED disconfirmation outcome means contradicting evidence
        # weakened the premise itself (Section 8's table) -- distinct from
        # low material impact, and independent of it: even with material
        # impact still true, a weakened premise cannot classify as a proven
        # defect.
        outcome = cfv.evaluate_candidate(
            grounding_sources=[G.TECHNICAL_INVARIANT],
            causal_chain=_complete_chain(),
            disconfirmation=D.DOWNGRADED,
            material_impact=True,
        )
        self.assertTrue(outcome.claim_valid)
        self.assertEqual(outcome.classification, C.REQUIREMENT_AMBIGUITY)
        self.assertFalse(outcome.blocking_justification_valid)


class ClassificationIsEvidenceDrivenNotImpactDrivenTests(unittest.TestCase):
    """Every fallback branch classifies on what the evidence establishes,
    never mechanically on whether the candidate cleared the blocking bar."""

    def test_reclassified_disconfirmation_classifies_independent_of_impact(self) -> None:
        for material_impact in (True, False):
            outcome = cfv.evaluate_candidate(
                grounding_sources=[G.TECHNICAL_INVARIANT],
                causal_chain=_complete_chain(),
                disconfirmation=D.RECLASSIFIED,
                material_impact=material_impact,
            )
            self.assertTrue(outcome.claim_valid)
            self.assertEqual(outcome.classification, C.TEST_COVERAGE_GAP, material_impact)
            self.assertFalse(outcome.blocking_justification_valid)

    def test_unproven_regression_classifies_independent_of_impact(self) -> None:
        for material_impact in (True, False):
            outcome = cfv.evaluate_candidate(
                grounding_sources=[G.ESTABLISHED_PRODUCTION_BEHAVIOR],
                causal_chain=_complete_chain(),
                is_regression_claim=True,
                regression_claim=cfv.RegressionClaim(change_evidence="the diff"),
                material_impact=material_impact,
            )
            self.assertTrue(outcome.claim_valid)
            self.assertEqual(outcome.classification, C.TEST_COVERAGE_GAP, material_impact)
            self.assertFalse(outcome.blocking_justification_valid)

    def test_reviewer_inference_alone_classifies_independent_of_impact(self) -> None:
        for material_impact in (True, False):
            outcome = cfv.evaluate_candidate(
                grounding_sources=[G.REVIEWER_INFERENCE_ALONE],
                causal_chain=_complete_chain(),
                material_impact=material_impact,
            )
            self.assertTrue(outcome.claim_valid)
            self.assertEqual(
                outcome.classification, C.MAINTAINABILITY_CONCERN, material_impact
            )
            self.assertFalse(outcome.blocking_justification_valid)

    def test_incomplete_causal_chain_classifies_independent_of_impact(self) -> None:
        for material_impact in (True, False):
            outcome = cfv.evaluate_candidate(
                grounding_sources=[G.TECHNICAL_INVARIANT],
                causal_chain=cfv.CausalChain(
                    reviewed_change="path diverges",
                    changed_assumption="handling changed",
                ),
                material_impact=material_impact,
            )
            self.assertTrue(outcome.claim_valid)
            self.assertEqual(outcome.classification, C.TEST_COVERAGE_GAP, material_impact)
            self.assertFalse(outcome.blocking_justification_valid)


class GovernanceTests(unittest.TestCase):
    def test_no_public_callable_carries_a_prohibited_capability_fragment(self) -> None:
        for name in cfv.public_callables():
            for fragment in cfv.PROHIBITED_CAPABILITY_NAME_FRAGMENTS:
                self.assertNotIn(fragment, name, (name, fragment))

    def test_severity_and_chain_of_thought_fragments_are_prohibited(self) -> None:
        for fragment in ("compute_severity", "derive_severity", "expose_reasoning"):
            self.assertIn(fragment, cfv.PROHIBITED_CAPABILITY_NAME_FRAGMENTS)


if __name__ == "__main__":
    unittest.main()
