#!/usr/bin/env python3
"""Coverage for optional PR-context handling (pr_context_reconciliation.py).

Contract: skills/local-code-review/policies/pr-context.md.
"""

from __future__ import annotations

import inspect
import itertools
import os
import pathlib
import subprocess
import sys
import textwrap
import unittest

from tests.reference import pr_context_reconciliation as prc
from tests.reference import current_evidence as ce


# --- Fixtures --------------------------------------------------------------

LOCAL_DELTA_TOUCHES = frozenset({"src/payments/charge.py", "src/payments/charge_test.py"})
UNRELATED_TOUCHES = frozenset({"docs/marketing/landing-page-copy.md"})


class ClassificationTests(unittest.TestCase):
    """Scenario 7: later explicit resolution governs over earlier comments."""

    def test_latest_explicit_resolution_governs_over_earlier_comments(self) -> None:
        thread = [
            prc.ThreadComment(prc.Category.PREFERENCE, label="early: use a queue"),
            prc.ThreadComment(prc.Category.PREFERENCE, label="counter: use a lock instead"),
            prc.ThreadComment(
                prc.Category.DECISION,
                label="resolution: agreed on a lock, see follow-up commit",
                is_explicit_resolution=True,
            ),
        ]
        governing = prc.classify_thread(thread)
        self.assertEqual(governing.category, prc.Category.DECISION)
        self.assertIn("agreed on a lock", governing.label)

    def test_earlier_exploratory_comments_never_become_independent_findings(self) -> None:
        # The classifier returns exactly one governing comment for the
        # thread — earlier comments are never separately returned as if
        # each were its own classified item.
        thread = [
            prc.ThreadComment(prc.Category.FINDING, label="maybe a bug?"),
            prc.ThreadComment(prc.Category.RESOLVED_OBSOLETE, label="false alarm, not a bug", is_explicit_resolution=True),
        ]
        governing = prc.classify_thread(thread)
        self.assertEqual(governing.category, prc.Category.RESOLVED_OBSOLETE)

    def test_no_explicit_resolution_falls_back_to_latest_comment(self) -> None:
        thread = [
            prc.ThreadComment(prc.Category.INFORMATIONAL, label="fyi"),
            prc.ThreadComment(prc.Category.PREFERENCE, label="latest, unresolved preference"),
        ]
        governing = prc.classify_thread(thread)
        self.assertEqual(governing.label, "latest, unresolved preference")

    def test_empty_thread_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            prc.classify_thread([])


class ScopeAndRelevanceTests(unittest.TestCase):
    """Scenario 8: unrelated PR context is ignored, scope never expands."""

    def test_overlapping_touches_are_relevant(self) -> None:
        self.assertTrue(
            prc.is_relevant_to_local_delta({"src/payments/charge.py"}, LOCAL_DELTA_TOUCHES)
        )

    def test_disjoint_touches_are_not_relevant(self) -> None:
        self.assertFalse(prc.is_relevant_to_local_delta(UNRELATED_TOUCHES, LOCAL_DELTA_TOUCHES))

    def test_near_miss_paths_do_not_fuzzily_match(self) -> None:
        # Guards against an implementation that expands scope via prefix/
        # substring matching instead of exact path-set overlap.
        near_miss = frozenset({"src/payments/charge_v2.py"})
        self.assertFalse(prc.is_relevant_to_local_delta(near_miss, LOCAL_DELTA_TOUCHES))

    def test_item_with_no_recorded_touches_is_never_relevant(self) -> None:
        self.assertFalse(prc.is_relevant_to_local_delta(frozenset(), LOCAL_DELTA_TOUCHES))


class ExistingFindingReconciliationTests(unittest.TestCase):
    """Scenarios 1 and 2: still-valid and resolved existing findings."""

    def test_scenario_1_still_valid_finding_is_reused_not_duplicated(self) -> None:
        finding = prc.ExistingFinding(id="F-PR-12", touches={"src/payments/charge.py"})
        result = prc.reconcile_finding(finding, LOCAL_DELTA_TOUCHES, issue_still_present=True)

        self.assertEqual(result.status, prc.FindingStatus.STILL_VALID)
        self.assertTrue(result.reuse_evidence)
        # The local review independently noticing the same issue must not
        # produce a second, duplicate finding.
        self.assertFalse(
            prc.should_emit_separate_finding(result, independently_discovered_same_issue=True)
        )

    def test_scenario_1_materially_different_issue_in_same_area_is_still_reported(self) -> None:
        finding = prc.ExistingFinding(id="F-PR-12", touches={"src/payments/charge.py"})
        result = prc.reconcile_finding(finding, LOCAL_DELTA_TOUCHES, issue_still_present=True)

        # A different, independently-discovered problem in the same file
        # is not suppressed merely because an unrelated finding in that
        # file was reconciled.
        self.assertTrue(
            prc.should_emit_separate_finding(result, independently_discovered_same_issue=False)
        )

    def test_scenario_1_final_severity_is_never_carried_by_reconciliation(self) -> None:
        # Governance: "Existing reviewer findings are evidence and
        # context, not authority" — this Skill assigns its own severity
        # per the shared severity policy. Structural guarantee: the
        # reconciliation result has no severity field to inherit from.
        dataclass_fields = {f.name for f in prc.FindingReconciliation.__dataclass_fields__.values()}
        self.assertNotIn("severity", dataclass_fields)
        self.assertNotIn("decision", dataclass_fields)

    def test_scenario_2_fixed_issue_is_classified_resolved(self) -> None:
        finding = prc.ExistingFinding(id="F-PR-9", touches={"src/payments/charge.py"})
        result = prc.reconcile_finding(finding, LOCAL_DELTA_TOUCHES, issue_still_present=False)

        self.assertEqual(result.status, prc.FindingStatus.RESOLVED)
        self.assertFalse(result.reuse_evidence)

    def test_scenario_2_resolved_finding_alone_does_not_require_report_noise(self) -> None:
        finding = prc.ExistingFinding(id="F-PR-9", touches={"src/payments/charge.py"})
        resolved = prc.reconcile_finding(finding, LOCAL_DELTA_TOUCHES, issue_still_present=False)

        self.assertFalse(
            prc.pr_context_section_required(
                pr_reference_supplied=True, finding_reconciliations=[resolved]
            )
        )

    def test_regression_after_resolved_thread_is_still_reported_with_fresh_evidence(self) -> None:
        # The thread was explicitly resolved ("false alarm / fixed")...
        thread = [
            prc.ThreadComment(prc.Category.FINDING, label="charge path not idempotent"),
            prc.ThreadComment(
                prc.Category.RESOLVED_OBSOLETE,
                label="fixed in follow-up, resolving",
                is_explicit_resolution=True,
            ),
        ]
        self.assertEqual(prc.classify_thread(thread).category, prc.Category.RESOLVED_OBSOLETE)

        # ...but the current local delta reintroduces the defect. The
        # historical resolution is evidence, not proof: reconciliation
        # against the *current* delta still classifies it STILL_VALID and
        # emits it.
        finding = prc.ExistingFinding(id="F-PR-9", touches={"src/payments/charge.py"})
        result = prc.reconcile_finding(finding, LOCAL_DELTA_TOUCHES, issue_still_present=True)
        self.assertEqual(result.status, prc.FindingStatus.STILL_VALID)
        self.assertTrue(
            prc.should_emit_separate_finding(result, independently_discovered_same_issue=False)
        )

    def test_unclear_applicability_requires_reevaluation_and_reuses_evidence(self) -> None:
        finding = prc.ExistingFinding(id="F-PR-3", touches={"src/payments/charge.py"})
        result = prc.reconcile_finding(finding, LOCAL_DELTA_TOUCHES, issue_still_present=None)

        self.assertEqual(result.status, prc.FindingStatus.REQUIRES_REEVALUATION)
        self.assertTrue(result.reuse_evidence)

    def test_scenario_8_finding_outside_local_delta_is_out_of_scope(self) -> None:
        finding = prc.ExistingFinding(id="F-PR-1", touches=UNRELATED_TOUCHES)
        result = prc.reconcile_finding(finding, LOCAL_DELTA_TOUCHES, issue_still_present=True)

        self.assertEqual(result.status, prc.FindingStatus.OUT_OF_SCOPE)
        self.assertFalse(result.reuse_evidence)


class ArchitecturalDecisionTests(unittest.TestCase):
    """Scenarios 3, 4, 5, 6: settled decisions, violations, supersession,
    and mere preferences."""

    def test_scenario_3_followed_settled_decision_emits_no_finding(self) -> None:
        decision = prc.ArchitecturalDecision(
            id="D-1", touches={"src/payments/charge.py"}, is_settled=True
        )
        result = prc.reconcile_decision(
            decision, LOCAL_DELTA_TOUCHES, delta_follows_decision=True
        )

        self.assertEqual(result.status, prc.DecisionStatus.FOLLOWED)
        self.assertFalse(result.emit_finding)

    def test_scenario_4_violated_settled_decision_without_evidence_is_a_finding(self) -> None:
        decision = prc.ArchitecturalDecision(
            id="D-2", touches={"src/payments/charge.py"}, is_settled=True
        )
        result = prc.reconcile_decision(
            decision, LOCAL_DELTA_TOUCHES, delta_follows_decision=False
        )

        self.assertEqual(result.status, prc.DecisionStatus.VIOLATED)
        self.assertTrue(result.emit_finding)
        # Provenance: the finding is traceable back to the specific
        # decision it violates.
        self.assertEqual(result.decision_id, "D-2")

    def test_scenario_5_violation_with_concrete_new_evidence_is_superseded_not_a_finding(
        self,
    ) -> None:
        decision = prc.ArchitecturalDecision(
            id="D-3", touches={"src/payments/charge.py"}, is_settled=True
        )
        result = prc.reconcile_decision(
            decision,
            LOCAL_DELTA_TOUCHES,
            delta_follows_decision=False,
            current_evidence=frozenset({ce.CurrentEvidenceKind.INVALIDATED_ASSUMPTION}),
        )

        self.assertEqual(result.status, prc.DecisionStatus.SUPERSEDED)
        self.assertFalse(result.emit_finding)

    def test_scenario_5_unrecognized_evidence_kind_is_rejected_not_silently_accepted(
        self,
    ) -> None:
        decision = prc.ArchitecturalDecision(
            id="D-3", touches={"src/payments/charge.py"}, is_settled=True
        )
        with self.assertRaises(ValueError):
            prc.reconcile_decision(
                decision,
                LOCAL_DELTA_TOUCHES,
                delta_follows_decision=False,
                current_evidence=frozenset({"i_just_prefer_this"}),
            )

    def test_mixed_overriding_and_invalid_evidence_is_rejected_in_every_order(self) -> None:
        decision = prc.ArchitecturalDecision(
            id="D-invalid-override", touches={"src/payments/charge.py"}, is_settled=True
        )
        for evidence in (
            (ce.CurrentEvidenceKind.CORRECTNESS_DEFECT, "invalid"),
            ("invalid", ce.CurrentEvidenceKind.CORRECTNESS_DEFECT),
        ):
            with self.subTest(evidence=evidence), self.assertRaises(ValueError):
                prc.reconcile_decision(
                    decision,
                    LOCAL_DELTA_TOUCHES,
                    delta_follows_decision=True,
                    current_evidence=evidence,
                )

    def test_mixed_non_overriding_and_invalid_evidence_is_rejected_in_every_order(self) -> None:
        decision = prc.ArchitecturalDecision(
            id="D-invalid-preference", touches={"src/payments/charge.py"}, is_settled=True
        )
        for evidence in (
            (ce.CurrentEvidenceKind.STYLE_PREFERENCE, "invalid"),
            ("invalid", ce.CurrentEvidenceKind.STYLE_PREFERENCE),
        ):
            with self.subTest(evidence=evidence), self.assertRaises(ValueError):
                prc.reconcile_decision(
                    decision,
                    LOCAL_DELTA_TOUCHES,
                    delta_follows_decision=True,
                    current_evidence=evidence,
                )

    def test_current_material_defects_override_even_when_delta_follows(self) -> None:
        decision = prc.ArchitecturalDecision(
            id="D-current", touches={"src/payments/charge.py"}, is_settled=True
        )
        for evidence in (
            ce.CurrentEvidenceKind.CORRECTNESS_DEFECT,
            ce.CurrentEvidenceKind.RELIABILITY_DEFECT,
            ce.CurrentEvidenceKind.MATERIAL_SECURITY_CONCERN,
            ce.CurrentEvidenceKind.MATERIAL_PERFORMANCE_CONCERN,
            ce.CurrentEvidenceKind.DATA_INTEGRITY_DEFECT,
            ce.CurrentEvidenceKind.SAFETY_DEFECT,
        ):
            with self.subTest(evidence=evidence):
                result = prc.reconcile_decision(
                    decision,
                    LOCAL_DELTA_TOUCHES,
                    delta_follows_decision=True,
                    current_evidence=frozenset({evidence}),
                )
                self.assertEqual(result.status, prc.DecisionStatus.SUPERSEDED)
                self.assertNotEqual(result.status, prc.DecisionStatus.FOLLOWED)

    def test_non_material_evidence_can_leave_followed_decision_authoritative(self) -> None:
        decision = prc.ArchitecturalDecision(
            id="D-preference", touches={"src/payments/charge.py"}, is_settled=True
        )
        for evidence in (
            ce.CurrentEvidenceKind.STYLE_PREFERENCE,
            ce.CurrentEvidenceKind.SPECULATIVE_OPTIMIZATION,
            ce.CurrentEvidenceKind.NON_MATERIAL_REVIEWER_PREFERENCE,
        ):
            with self.subTest(evidence=evidence):
                result = prc.reconcile_decision(
                    decision,
                    LOCAL_DELTA_TOUCHES,
                    delta_follows_decision=True,
                    current_evidence=frozenset({evidence}),
                )
                self.assertEqual(result.status, prc.DecisionStatus.FOLLOWED)

    def test_local_and_github_models_share_current_evidence_owner(self) -> None:
        from tests.reference import pr_review_evidence as prv

        self.assertIs(prc.CurrentEvidenceKind, ce.CurrentEvidenceKind)
        self.assertIs(prv.CurrentEvidenceKind, ce.CurrentEvidenceKind)
        self.assertIs(
            prc.current_evidence_collection_overrides_historical_authority,
            ce.current_evidence_collection_overrides_historical_authority,
        )
        self.assertIs(
            prv.current_evidence_collection_overrides_historical_authority,
            ce.current_evidence_collection_overrides_historical_authority,
        )

    def test_local_and_github_models_reject_the_same_malformed_collections(self) -> None:
        from tests.reference import pr_review_evidence as prv

        local_decision = prc.ArchitecturalDecision(
            id="D-parity", touches={"src/payments/charge.py"}, is_settled=True
        )
        github_decision = prv.SettledDecision(
            "D-parity", prv.AuthorType.MAINTAINER, has_explicit_agreement=True
        )
        for evidence in (
            (ce.CurrentEvidenceKind.SAFETY_DEFECT, "invalid"),
            ("invalid", ce.CurrentEvidenceKind.SAFETY_DEFECT),
            (ce.CurrentEvidenceKind.NON_MATERIAL_REVIEWER_PREFERENCE, "invalid"),
            ("invalid", ce.CurrentEvidenceKind.NON_MATERIAL_REVIEWER_PREFERENCE),
        ):
            with self.subTest(model="local", evidence=evidence), self.assertRaises(ValueError):
                prc.reconcile_decision(
                    local_decision,
                    LOCAL_DELTA_TOUCHES,
                    delta_follows_decision=True,
                    current_evidence=evidence,
                )
            with self.subTest(model="github", evidence=evidence), self.assertRaises(ValueError):
                prv.reconcile_settled_decision(
                    github_decision,
                    current_delta_follows=True,
                    current_evidence=evidence,
                )

    def test_local_and_github_models_preserve_valid_collection_semantics(self) -> None:
        from tests.reference import pr_review_evidence as prv

        local_decision = prc.ArchitecturalDecision(
            id="D-valid-parity", touches={"src/payments/charge.py"}, is_settled=True
        )
        github_decision = prv.SettledDecision(
            "D-valid-parity", prv.AuthorType.MAINTAINER, has_explicit_agreement=True
        )
        cases = (
            (
                (
                    ce.CurrentEvidenceKind.STYLE_PREFERENCE,
                    ce.CurrentEvidenceKind.RELIABILITY_DEFECT,
                ),
                prc.DecisionStatus.SUPERSEDED,
                prv.DecisionStatus.SUPERSEDED,
            ),
            (
                (
                    ce.CurrentEvidenceKind.STYLE_PREFERENCE,
                    ce.CurrentEvidenceKind.SPECULATIVE_OPTIMIZATION,
                    ce.CurrentEvidenceKind.NON_MATERIAL_REVIEWER_PREFERENCE,
                ),
                prc.DecisionStatus.FOLLOWED,
                prv.DecisionStatus.FOLLOWED,
            ),
        )
        for evidence, local_status, github_status in cases:
            with self.subTest(evidence=evidence):
                self.assertEqual(
                    prc.reconcile_decision(
                        local_decision,
                        LOCAL_DELTA_TOUCHES,
                        delta_follows_decision=True,
                        current_evidence=evidence,
                    ).status,
                    local_status,
                )
                self.assertEqual(
                    prv.reconcile_settled_decision(
                        github_decision,
                        current_delta_follows=True,
                        current_evidence=evidence,
                    ).status,
                    github_status,
                )

    def test_scenario_6_unsettled_preference_is_never_a_constraint(self) -> None:
        # A reviewer preference with no agreement/resolution never becomes
        # a settled decision, regardless of whether the delta happens to
        # match or diverge from it.
        preference = prc.ArchitecturalDecision(
            id="D-4", touches={"src/payments/charge.py"}, is_settled=False
        )

        diverges = prc.reconcile_decision(
            preference, LOCAL_DELTA_TOUCHES, delta_follows_decision=False
        )
        matches = prc.reconcile_decision(
            preference, LOCAL_DELTA_TOUCHES, delta_follows_decision=True
        )

        for result in (diverges, matches):
            self.assertEqual(result.status, prc.DecisionStatus.NOT_SETTLED)
            self.assertFalse(result.emit_finding)

    def test_scenario_8_decision_outside_local_delta_is_out_of_scope(self) -> None:
        decision = prc.ArchitecturalDecision(id="D-5", touches=UNRELATED_TOUCHES, is_settled=True)
        result = prc.reconcile_decision(
            decision, LOCAL_DELTA_TOUCHES, delta_follows_decision=False
        )

        self.assertEqual(result.status, prc.DecisionStatus.OUT_OF_SCOPE)
        self.assertFalse(result.emit_finding)


class CurrentEvidenceValidationOrderingTests(unittest.TestCase):
    """Issue #27: the complete current-evidence collection is validated by the
    canonical owner before every ``reconcile_decision`` return.

    Malformed / unknown evidence is rejected deterministically regardless of
    scope, settlement state, companion evidence materiality, collection type,
    or item ordering.
    """

    RELEVANT_TOUCHES = frozenset({"src/payments/charge.py"})

    OVERRIDING_COMPANION = ce.CurrentEvidenceKind.CORRECTNESS_DEFECT
    NON_OVERRIDING_COMPANION = ce.CurrentEvidenceKind.STYLE_PREFERENCE
    BAD = "not_a_current_evidence_kind"

    def _settled(self, touches: frozenset) -> prc.ArchitecturalDecision:
        return prc.ArchitecturalDecision(id="D-27", touches=touches, is_settled=True)

    def _mixed_orderings(self, companion):
        """Every ordering / container the malformed collection can arrive in."""
        return (
            (companion, self.BAD),
            (self.BAD, companion),
            [companion, self.BAD],
            [self.BAD, companion],
            (self.BAD,),
        )

    # 1. Local relevant + settled + malformed evidence -------------------

    def test_relevant_settled_malformed_evidence_is_rejected(self) -> None:
        decision = self._settled(self.RELEVANT_TOUCHES)
        for companion in (self.OVERRIDING_COMPANION, self.NON_OVERRIDING_COMPANION):
            for evidence in self._mixed_orderings(companion):
                with self.subTest(companion=companion, evidence=evidence):
                    with self.assertRaises(ValueError):
                        prc.reconcile_decision(
                            decision,
                            LOCAL_DELTA_TOUCHES,
                            delta_follows_decision=True,
                            current_evidence=evidence,
                        )

    # 2. Local OUT_OF_SCOPE + malformed evidence ------------------------

    def test_out_of_scope_cannot_hide_malformed_evidence(self) -> None:
        decision = self._settled(UNRELATED_TOUCHES)
        # Sanity: identical valid call really would return OUT_OF_SCOPE.
        self.assertEqual(
            prc.reconcile_decision(
                decision, LOCAL_DELTA_TOUCHES, delta_follows_decision=False
            ).status,
            prc.DecisionStatus.OUT_OF_SCOPE,
        )
        for companion in (self.OVERRIDING_COMPANION, self.NON_OVERRIDING_COMPANION):
            for evidence in self._mixed_orderings(companion):
                with self.subTest(companion=companion, evidence=evidence):
                    with self.assertRaises(ValueError):
                        prc.reconcile_decision(
                            decision,
                            LOCAL_DELTA_TOUCHES,
                            delta_follows_decision=False,
                            current_evidence=evidence,
                        )

    # 3. Local NOT_SETTLED + malformed evidence ------------------------

    def test_not_settled_cannot_hide_malformed_evidence(self) -> None:
        preference = prc.ArchitecturalDecision(
            id="D-27-pref", touches=self.RELEVANT_TOUCHES, is_settled=False
        )
        self.assertEqual(
            prc.reconcile_decision(
                preference, LOCAL_DELTA_TOUCHES, delta_follows_decision=True
            ).status,
            prc.DecisionStatus.NOT_SETTLED,
        )
        for companion in (self.OVERRIDING_COMPANION, self.NON_OVERRIDING_COMPANION):
            for evidence in self._mixed_orderings(companion):
                with self.subTest(companion=companion, evidence=evidence):
                    with self.assertRaises(ValueError):
                        prc.reconcile_decision(
                            preference,
                            LOCAL_DELTA_TOUCHES,
                            delta_follows_decision=True,
                            current_evidence=evidence,
                        )

    # 5. Valid early-return behavior is unchanged ---------------------

    def test_valid_evidence_preserves_out_of_scope_and_not_settled(self) -> None:
        out_of_scope = self._settled(UNRELATED_TOUCHES)
        preference = prc.ArchitecturalDecision(
            id="D-27-pref", touches=self.RELEVANT_TOUCHES, is_settled=False
        )
        valid_collections = (
            frozenset(),
            frozenset({self.OVERRIDING_COMPANION}),
            frozenset({self.NON_OVERRIDING_COMPANION}),
            (self.NON_OVERRIDING_COMPANION, self.OVERRIDING_COMPANION),
        )
        for evidence in valid_collections:
            with self.subTest(evidence=evidence):
                self.assertEqual(
                    prc.reconcile_decision(
                        out_of_scope,
                        LOCAL_DELTA_TOUCHES,
                        delta_follows_decision=False,
                        current_evidence=evidence,
                    ).status,
                    prc.DecisionStatus.OUT_OF_SCOPE,
                )
                self.assertEqual(
                    prc.reconcile_decision(
                        preference,
                        LOCAL_DELTA_TOUCHES,
                        delta_follows_decision=True,
                        current_evidence=evidence,
                    ).status,
                    prc.DecisionStatus.NOT_SETTLED,
                )

    # 6. Order independence ------------------------------------------

    def test_malformed_mixed_collection_fails_in_every_order(self) -> None:
        decision = self._settled(self.RELEVANT_TOUCHES)
        base = [
            self.OVERRIDING_COMPANION,
            self.NON_OVERRIDING_COMPANION,
            self.BAD,
        ]
        for ordering in itertools.permutations(base):
            with self.subTest(ordering=ordering), self.assertRaises(ValueError):
                prc.reconcile_decision(
                    decision,
                    LOCAL_DELTA_TOUCHES,
                    delta_follows_decision=True,
                    current_evidence=list(ordering),
                )

    # 7. Hash-seed independence -------------------------------------

    def test_rejection_is_stable_across_hash_seeds(self) -> None:
        program = textwrap.dedent(
            """
            from tests.reference import pr_context_reconciliation as prc
            from tests.reference import current_evidence as ce

            decision = prc.ArchitecturalDecision(
                id="D", touches=frozenset({"src/payments/charge.py"}), is_settled=True
            )
            delta = frozenset({"src/payments/charge.py"})
            evidence = {
                ce.CurrentEvidenceKind.CORRECTNESS_DEFECT,
                ce.CurrentEvidenceKind.STYLE_PREFERENCE,
                "bad",
            }
            try:
                prc.reconcile_decision(
                    decision, delta, delta_follows_decision=True,
                    current_evidence=evidence,
                )
            except ValueError:
                print("rejected")
            else:
                raise SystemExit("malformed evidence was not rejected")
            """
        )
        repo_root = pathlib.Path(__file__).resolve().parents[2]
        for seed in ("0", "1", "42", "12345"):
            with self.subTest(seed=seed):
                env = dict(os.environ, PYTHONHASHSEED=seed)
                result = subprocess.run(
                    [sys.executable, "-c", program],
                    cwd=repo_root,
                    env=env,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.strip(), "rejected")


class AvailabilityFallbackTests(unittest.TestCase):
    """Scenarios 9 and 10: no PR / unavailable PR context never blocks review."""

    def test_no_availability_state_ever_blocks_the_local_review(self) -> None:
        for state in prc.PRContextAvailability:
            with self.subTest(state=state):
                self.assertFalse(prc.should_block_local_review(state))


class ReportSectionInclusionTests(unittest.TestCase):
    """Scenario 9 (no PR) and the "avoid output noise" rule."""

    def test_scenario_9_no_pr_supplied_never_shows_the_section(self) -> None:
        still_valid = prc.FindingReconciliation("F1", prc.FindingStatus.STILL_VALID, True)
        violated = prc.DecisionReconciliation("D1", prc.DecisionStatus.VIOLATED, True)

        self.assertFalse(
            prc.pr_context_section_required(
                pr_reference_supplied=False,
                finding_reconciliations=[still_valid],
                decision_reconciliations=[violated],
            )
        )

    def test_pr_supplied_with_only_resolved_and_followed_outcomes_stays_quiet(self) -> None:
        resolved = prc.FindingReconciliation("F2", prc.FindingStatus.RESOLVED, False)
        followed = prc.DecisionReconciliation("D2", prc.DecisionStatus.FOLLOWED, False)

        self.assertFalse(
            prc.pr_context_section_required(
                pr_reference_supplied=True,
                finding_reconciliations=[resolved],
                decision_reconciliations=[followed],
            )
        )

    def test_pr_supplied_with_material_finding_shows_the_section(self) -> None:
        still_valid = prc.FindingReconciliation("F3", prc.FindingStatus.STILL_VALID, True)

        self.assertTrue(
            prc.pr_context_section_required(
                pr_reference_supplied=True, finding_reconciliations=[still_valid]
            )
        )

    def test_pr_supplied_with_violated_decision_shows_the_section(self) -> None:
        violated = prc.DecisionReconciliation("D3", prc.DecisionStatus.VIOLATED, True)

        self.assertTrue(
            prc.pr_context_section_required(
                pr_reference_supplied=True, decision_reconciliations=[violated]
            )
        )


class GovernanceInvariantTests(unittest.TestCase):
    """Cross-cutting invariants from pr-context.md, "Boundary with
    `github-pr-review`", that must hold regardless of any single scenario."""

    def test_module_defines_no_github_mutating_or_approval_bypassing_capability(self) -> None:
        # Substring match, not exact-name match: a regression like
        # `submit_pr_review` or `approve_pr` must be caught, not just a
        # public name that is bare "submit" or "approve" verbatim.
        public_names = {name for name in dir(prc) if not name.startswith("_")}
        offending = {
            name
            for name in public_names
            if any(fragment in name.lower() for fragment in prc.PROHIBITED_CAPABILITY_NAME_FRAGMENTS)
        }
        self.assertEqual(
            offending,
            set(),
            "pr_context_reconciliation.py must stay read-only and must never "
            "gain a GitHub-mutating or approval/ownership-bypassing capability",
        )

    def test_no_function_accepts_an_approval_or_ownership_bypass_parameter(self) -> None:
        # PR context must never be able to supply or short-circuit the
        # invocation-approval or review-ownership gates — those remain
        # entirely outside this module's concern per pr-context.md,
        # "Boundary with `github-pr-review`".
        suspicious_param_fragments = ("approv", "ownership", "bypass")
        for name, obj in inspect.getmembers(prc):
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

    def test_decision_and_finding_statuses_contain_no_pr_review_verdicts(self) -> None:
        # This Skill must never become a second github-pr-review workflow:
        # its own reconciliation vocabulary must not encode
        # Approve/Request Changes-style PR verdicts.
        prohibited_tokens = {"APPROVE", "REQUEST_CHANGES", "MERGE"}
        all_values = {member.name for member in prc.FindingStatus} | {
            member.name for member in prc.DecisionStatus
        }
        self.assertEqual(all_values & prohibited_tokens, set())


if __name__ == "__main__":
    unittest.main()
