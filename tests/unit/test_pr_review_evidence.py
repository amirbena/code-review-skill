#!/usr/bin/env python3
"""Behavioral coverage for github-pr-review Existing Review Evidence.

Contract: shared/policies/review-evidence.md and
skills/github-pr-review/policies/{review-evidence,pr-scope}.md.
Analogous in spirit to tests/unit/test_pr_context_reconciliation.py, but the
review target is the current PR HEAD rather than a local delta.
"""

from __future__ import annotations

import unittest

from tests.reference import pr_review_evidence as prv
from tests.support import pr_simulation as sim

SHA_A = "a" * 40
SHA_B = "b" * 40


class ThreadConclusionTests(unittest.TestCase):
    """Explicit thread conclusion governs earlier exploratory comments."""

    def test_latest_explicit_conclusion_governs(self) -> None:
        thread = [
            prv.ThreadComment(prv.AuthorType.HUMAN_REVIEWER, label="maybe unsafe?"),
            prv.ThreadComment(prv.AuthorType.HUMAN_REVIEWER, label="counterpoint"),
            prv.ThreadComment(
                prv.AuthorType.MAINTAINER,
                is_explicit_conclusion=True,
                label="agreed: current approach is fine",
            ),
        ]
        governing = prv.classify_thread(thread)
        self.assertTrue(governing.is_explicit_conclusion)
        self.assertTrue(prv.thread_conclusion_is_authoritative(governing))

    def test_no_explicit_conclusion_falls_back_to_latest(self) -> None:
        thread = [
            prv.ThreadComment(prv.AuthorType.HUMAN_REVIEWER, label="fyi"),
            prv.ThreadComment(prv.AuthorType.HUMAN_REVIEWER, label="still unresolved"),
        ]
        self.assertEqual(prv.classify_thread(thread).label, "still unresolved")

    def test_bot_cannot_author_an_authoritative_conclusion(self) -> None:
        thread = [
            prv.ThreadComment(prv.AuthorType.HUMAN_REVIEWER, label="is this a bug?"),
            prv.ThreadComment(
                prv.AuthorType.AUTOMATION_BOT,
                is_explicit_conclusion=True,
                label="auto-closed by staleness bot",
            ),
        ]
        governing = prv.classify_thread(thread)
        self.assertFalse(prv.thread_conclusion_is_authoritative(governing))

    def test_empty_thread_rejected(self) -> None:
        with self.assertRaises(ValueError):
            prv.classify_thread([])

    def _reopened_thread(self) -> list[prv.ThreadComment]:
        return [
            prv.ThreadComment(prv.AuthorType.HUMAN_REVIEWER, label="missing guard"),
            prv.ThreadComment(
                prv.AuthorType.MAINTAINER,
                is_explicit_conclusion=True,
                label="fixed and accepted",
            ),
            prv.ThreadComment(
                prv.AuthorType.HUMAN_REVIEWER,
                reopens_current_target=True,
                label="guard is missing again on current HEAD",
            ),
        ]

    def test_current_head_regression_reopens_and_emits_a_fresh_finding(self) -> None:
        outcome = prv.reconcile_reopened_thread(
            self._reopened_thread(),
            historical_resolution=prv.ThreadResolution.RESOLVED,
            defect_present_on_current_head=True,
        )
        self.assertEqual(outcome, prv.RegressionOutcome.EMIT_FRESH_FINDING_REGRESSED)

    def test_reopening_rechecks_but_emits_nothing_when_defect_is_absent(self) -> None:
        outcome = prv.reconcile_reopened_thread(
            self._reopened_thread(),
            historical_resolution=prv.ThreadResolution.RESOLVED,
            defect_present_on_current_head=False,
        )
        self.assertEqual(outcome, prv.RegressionOutcome.NO_FINDING_STILL_FIXED)

    def test_reopening_comment_becomes_the_governing_evidence(self) -> None:
        governing = prv.classify_thread(self._reopened_thread())
        self.assertTrue(governing.reopens_current_target)
        self.assertEqual(governing.label, "guard is missing again on current HEAD")

    def test_follow_up_noise_does_not_reopen_an_explicit_resolution(self) -> None:
        resolution = prv.ThreadComment(
            prv.AuthorType.MAINTAINER,
            is_explicit_conclusion=True,
            label="fixed and accepted",
        )
        thread = [
            prv.ThreadComment(prv.AuthorType.HUMAN_REVIEWER, label="missing guard"),
            resolution,
            prv.ThreadComment(prv.AuthorType.HUMAN_REVIEWER, label="thanks"),
        ]
        self.assertIs(prv.classify_thread(thread), resolution)
        self.assertIsNone(
            prv.reconcile_reopened_thread(
                thread,
                historical_resolution=prv.ThreadResolution.RESOLVED,
                defect_present_on_current_head=True,
            )
        )


class PriorFindingStillValidTests(unittest.TestCase):
    def test_present_on_current_head_is_reused_and_represented_once(self) -> None:
        finding = prv.PriorFinding("F-PR-1", reviewed_sha=SHA_A)
        r = prv.reconcile_prior_finding(
            finding, current_head_sha=SHA_A, present_on_current_head=True
        )
        self.assertEqual(r.item_class, prv.PriorItemClass.STILL_RELEVANT)
        self.assertTrue(r.reuse_prior_evidence)
        self.assertTrue(r.emit_in_this_review)

    def test_independently_rediscovered_same_issue_is_one_finding_not_two(self) -> None:
        finding = prv.PriorFinding("F-PR-1", reviewed_sha=SHA_A)
        r = prv.reconcile_prior_finding(
            finding,
            current_head_sha=SHA_A,
            present_on_current_head=True,
            independently_rediscovered=True,
        )
        self.assertEqual(r.item_class, prv.PriorItemClass.DUPLICATE)
        self.assertTrue(prv.should_suppress_as_duplicate(r))

    def test_materially_different_issue_in_same_area_is_still_emitted(self) -> None:
        self.assertTrue(
            prv.should_emit_independent_finding(materially_different_from_prior=True)
        )

    def test_reconciliation_carries_no_severity_or_decision(self) -> None:
        fields = set(prv.Reconciliation.__dataclass_fields__)
        self.assertNotIn("severity", fields)
        self.assertNotIn("decision", fields)


class PriorFindingResolvedTests(unittest.TestCase):
    def test_absent_on_current_head_is_resolved_and_not_reported(self) -> None:
        finding = prv.PriorFinding("F-PR-2", reviewed_sha=SHA_A)
        r = prv.reconcile_prior_finding(
            finding, current_head_sha=SHA_A, present_on_current_head=False
        )
        self.assertEqual(r.item_class, prv.PriorItemClass.RESOLVED)
        self.assertFalse(r.emit_in_this_review)


class PriorFindingStaleAfterHeadChangeTests(unittest.TestCase):
    def test_undeterminable_applicability_forces_reevaluation(self) -> None:
        finding = prv.PriorFinding("F-PR-3", reviewed_sha=SHA_A)
        r = prv.reconcile_prior_finding(
            finding, current_head_sha=SHA_B, present_on_current_head=None
        )
        self.assertEqual(r.item_class, prv.PriorItemClass.STALE)
        self.assertTrue(r.reuse_prior_evidence)
        self.assertFalse(r.emit_in_this_review)

    def test_absent_but_heavy_churn_since_head_change_is_stale_not_auto_resolved(self) -> None:
        finding = prv.PriorFinding("F-PR-3", reviewed_sha=SHA_A)
        r = prv.reconcile_prior_finding(
            finding,
            current_head_sha=SHA_B,
            present_on_current_head=False,
            surrounding_code_materially_changed=True,
        )
        self.assertEqual(r.item_class, prv.PriorItemClass.STALE)
        self.assertFalse(r.emit_in_this_review)

    def test_head_change_neither_auto_resolves_nor_auto_applies(self) -> None:
        # Present -> still relevant; absent -> stale (churn) — never a blind
        # "resolved because HEAD moved" or "still applies because it was raised".
        finding = prv.PriorFinding("F-PR-3", reviewed_sha=SHA_A)
        present = prv.reconcile_prior_finding(
            finding, current_head_sha=SHA_B, present_on_current_head=True
        )
        self.assertEqual(present.item_class, prv.PriorItemClass.STILL_RELEVANT)


class HeadChangeSemanticsTests(unittest.TestCase):
    def test_head_change_resets_applicability(self) -> None:
        self.assertTrue(prv.head_change_resets_applicability(SHA_A, SHA_B))
        self.assertFalse(prv.head_change_resets_applicability(SHA_A, SHA_A))

    def test_prior_findings_remain_investigation_evidence(self) -> None:
        self.assertTrue(prv.prior_findings_remain_investigation_evidence_after_head_change())

    def test_old_approval_never_authorizes_new_head(self) -> None:
        self.assertFalse(prv.old_approval_carries_to_new_head(SHA_A, SHA_B))
        self.assertFalse(prv.old_approval_carries_to_new_head(SHA_A, SHA_A))

    def test_prior_human_findings_must_be_reclassified_on_head_change(self) -> None:
        self.assertTrue(prv.must_reclassify_prior_human_findings(SHA_A, SHA_B))
        self.assertFalse(prv.must_reclassify_prior_human_findings(SHA_A, SHA_A))


class RegressionAfterResolvedThreadTests(unittest.TestCase):
    """reviewer reports -> fixed -> thread resolved -> later commit reintroduces."""

    def test_resolved_thread_but_defect_back_on_head_is_a_fresh_finding(self) -> None:
        outcome = prv.evaluate_possibly_regressed(
            prv.ThreadResolution.RESOLVED, defect_present_on_current_head=True
        )
        self.assertEqual(outcome, prv.RegressionOutcome.EMIT_FRESH_FINDING_REGRESSED)

    def test_resolved_thread_and_defect_absent_is_no_finding(self) -> None:
        outcome = prv.evaluate_possibly_regressed(
            prv.ThreadResolution.RESOLVED, defect_present_on_current_head=False
        )
        self.assertEqual(outcome, prv.RegressionOutcome.NO_FINDING_STILL_FIXED)

    def test_unresolved_thread_and_defect_present_still_emits(self) -> None:
        outcome = prv.evaluate_possibly_regressed(
            prv.ThreadResolution.UNRESOLVED, defect_present_on_current_head=True
        )
        self.assertEqual(outcome, prv.RegressionOutcome.EMIT_FINDING_NEVER_FIXED)

    def test_resolved_flag_is_not_a_correctness_oracle(self) -> None:
        self.assertFalse(prv.resolved_flag_is_correctness_oracle())

    def test_regression_via_reconcile_path_is_still_relevant(self) -> None:
        # The reconcile path agrees: a resolved thread's defect present again
        # on the current HEAD is STILL_RELEVANT and emitted.
        finding = prv.PriorFinding("F-PR-9", reviewed_sha=SHA_A)
        r = prv.reconcile_prior_finding(
            finding, current_head_sha=SHA_B, present_on_current_head=True
        )
        self.assertEqual(r.item_class, prv.PriorItemClass.STILL_RELEVANT)
        self.assertTrue(r.emit_in_this_review)


class SettledDecisionTests(unittest.TestCase):
    def _human_decision(self) -> prv.SettledDecision:
        return prv.SettledDecision("D-1", prv.AuthorType.MAINTAINER, has_explicit_agreement=True)

    def test_followed_settled_decision_emits_no_finding(self) -> None:
        r = prv.reconcile_settled_decision(self._human_decision(), current_delta_follows=True)
        self.assertEqual(r.status, prv.DecisionStatus.FOLLOWED)
        self.assertFalse(r.emit_finding)

    def test_violated_settled_decision_without_evidence_is_a_finding(self) -> None:
        r = prv.reconcile_settled_decision(self._human_decision(), current_delta_follows=False)
        self.assertEqual(r.status, prv.DecisionStatus.VIOLATED)
        self.assertTrue(r.emit_finding)

    def test_superseded_with_concrete_new_evidence_is_not_a_finding(self) -> None:
        r = prv.reconcile_settled_decision(
            self._human_decision(),
            current_delta_follows=False,
            supersession_evidence=frozenset({"invalidated_assumption"}),
        )
        self.assertEqual(r.status, prv.DecisionStatus.SUPERSEDED)
        self.assertFalse(r.emit_finding)

    def test_unrecognized_supersession_evidence_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            prv.reconcile_settled_decision(
                self._human_decision(),
                current_delta_follows=False,
                supersession_evidence=frozenset({"i_prefer_this"}),
            )

    def test_unsettled_reviewer_preference_is_never_a_constraint(self) -> None:
        preference = prv.SettledDecision(
            "D-2", prv.AuthorType.HUMAN_REVIEWER, has_explicit_agreement=False
        )
        for follows in (True, False):
            r = prv.reconcile_settled_decision(preference, current_delta_follows=follows)
            self.assertEqual(r.status, prv.DecisionStatus.NOT_SETTLED)
            self.assertFalse(r.emit_finding)

    def test_bot_authored_decision_is_never_settled(self) -> None:
        bot_decision = prv.SettledDecision(
            "D-3", prv.AuthorType.AUTOMATION_BOT, has_explicit_agreement=True
        )
        self.assertFalse(prv.decision_is_settled(bot_decision))
        r = prv.reconcile_settled_decision(bot_decision, current_delta_follows=False)
        self.assertEqual(r.status, prv.DecisionStatus.NOT_SETTLED)

    def test_settled_decision_cannot_suppress_safety_critical_defect(self) -> None:
        for category in ("correctness", "security", "data_integrity", "safety"):
            self.assertFalse(prv.settled_decision_suppresses_defect(category))
        self.assertTrue(prv.settled_decision_suppresses_defect("style_preference"))


class AuthorshipAuthorityTests(unittest.TestCase):
    def test_maintainer_clarification_is_maintainer_only(self) -> None:
        kind = "maintainer_clarification"
        self.assertFalse(prv.author_can_establish(prv.AuthorType.HUMAN_REVIEWER, kind))
        self.assertTrue(prv.author_can_establish(prv.AuthorType.MAINTAINER, kind))
        self.assertFalse(prv.author_can_establish(prv.AuthorType.AUTOMATION_BOT, kind))

    def test_human_reviewer_can_establish_reviewer_acceptance(self) -> None:
        kind = "reviewer_acceptance"
        self.assertTrue(prv.author_can_establish(prv.AuthorType.HUMAN_REVIEWER, kind))
        self.assertTrue(prv.author_can_establish(prv.AuthorType.MAINTAINER, kind))
        self.assertFalse(prv.author_can_establish(prv.AuthorType.AUTOMATION_BOT, kind))

    def test_non_human_authors_cannot_establish_any_authority_kind(self) -> None:
        for kind in prv.AUTHORITY_KINDS:
            self.assertFalse(prv.author_can_establish(prv.AuthorType.AUTOMATION_BOT, kind))
            self.assertFalse(prv.author_can_establish(prv.AuthorType.CI_STATUS, kind))
            self.assertFalse(prv.author_can_establish(prv.AuthorType.UNKNOWN, kind))

    def test_automation_never_establishes_any_authority_kind(self) -> None:
        for kind in prv.AUTHORITY_KINDS:
            self.assertFalse(prv.automation_can_establish(kind))

    def test_unknown_authority_kind_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            prv.author_can_establish(prv.AuthorType.MAINTAINER, "make_me_admin")

    def test_automation_output_is_observation_only(self) -> None:
        self.assertEqual(
            prv.automation_contribution(prv.AuthorType.AUTOMATION_BOT), "observation_only"
        )
        self.assertEqual(
            prv.automation_contribution(prv.AuthorType.CI_STATUS), "observation_only"
        )
        self.assertEqual(
            prv.automation_contribution(prv.AuthorType.MAINTAINER), "authoritative_capable"
        )

    def test_no_reputation_or_allowlist_surface(self) -> None:
        banned = ("reputation", "allowlist", "allow_list", "trust_score", "trust_weight")
        for name in dir(prv):
            lowered = name.lower()
            for fragment in banned:
                self.assertNotIn(fragment, lowered)


class RetrievalCompletenessTests(unittest.TestCase):
    def test_incomplete_history_never_blocks_review(self) -> None:
        for c in prv.HistoryCompleteness:
            self.assertFalse(prv.history_blocks_review(c))

    def test_complete_dedup_claim_only_when_history_complete(self) -> None:
        self.assertTrue(prv.may_claim_complete_deduplication(prv.HistoryCompleteness.COMPLETE))
        self.assertFalse(prv.may_claim_complete_deduplication(prv.HistoryCompleteness.PARTIAL))
        self.assertFalse(
            prv.may_claim_complete_deduplication(prv.HistoryCompleteness.UNAVAILABLE)
        )

    def test_uncertainty_reported_when_material_and_history_incomplete(self) -> None:
        self.assertTrue(
            prv.must_report_history_uncertainty(prv.HistoryCompleteness.PARTIAL)
        )
        self.assertFalse(
            prv.must_report_history_uncertainty(
                prv.HistoryCompleteness.PARTIAL, material_to_dedup=False
            )
        )
        self.assertFalse(
            prv.must_report_history_uncertainty(prv.HistoryCompleteness.COMPLETE)
        )

    def test_required_retrieval_surfaces_cover_states_and_threads(self) -> None:
        for surface in (
            "submitted_reviews",
            "review_state",
            "inline_review_comments",
            "issue_comments",
            "review_threads",
            "thread_resolution_state",
        ):
            self.assertIn(surface, prv.REQUIRED_RETRIEVAL_SURFACES)
        self.assertTrue(prv.PAGINATION_TO_EXHAUSTION)

    def test_review_state_vocabulary_matches_github(self) -> None:
        self.assertEqual(
            {s.value for s in prv.ReviewState},
            {"APPROVED", "CHANGES_REQUESTED", "COMMENTED", "DISMISSED"},
        )


class SimulationBackedScenarioTests(unittest.TestCase):
    """A couple of end-to-end reconciliations driven by the in-memory
    review-history fixtures in tests/support/pr_simulation.py."""

    def test_changes_requested_then_fixed_then_regressed(self) -> None:
        history = sim.review_history(
            reviews=(
                sim.SimReview("CHANGES_REQUESTED", "missing idempotency guard", SHA_A),
                sim.SimReview("COMMENTED", "looks fixed now", SHA_B),
            ),
            threads=(
                sim.SimReviewThread(
                    "src/pay.py",
                    is_resolved=True,
                    comments=(
                        sim.SimReviewComment("src/pay.py", "not idempotent"),
                        sim.SimReviewComment("src/pay.py", "fixed, resolving", resolves_thread=True),
                    ),
                ),
            ),
        )
        thread = history.threads[0]
        resolution = (
            prv.ThreadResolution.RESOLVED if thread.is_resolved else prv.ThreadResolution.UNRESOLVED
        )
        # A later commit reintroduced the defect on the current HEAD.
        outcome = prv.evaluate_possibly_regressed(resolution, defect_present_on_current_head=True)
        self.assertEqual(outcome, prv.RegressionOutcome.EMIT_FRESH_FINDING_REGRESSED)

    def test_partial_history_from_fixture_bars_idempotency_claim(self) -> None:
        history = sim.review_history(
            reviews=(sim.SimReview("COMMENTED", "partial page", SHA_A),), complete=False
        )
        completeness = (
            prv.HistoryCompleteness.COMPLETE
            if history.complete
            else prv.HistoryCompleteness.PARTIAL
        )
        self.assertFalse(prv.history_blocks_review(completeness))
        self.assertFalse(prv.may_claim_complete_deduplication(completeness))
        self.assertTrue(prv.must_report_history_uncertainty(completeness))

    def test_bot_issue_comment_cannot_settle_a_decision(self) -> None:
        history = sim.review_history(
            issue_comments=(
                sim.SimIssueComment("Deploy preview ready ✅", author_type="automation_bot"),
            )
        )
        author = prv.AuthorType(history.issue_comments[0].author_type)
        self.assertFalse(prv.author_can_establish(author, "settled_architectural_decision"))


class GovernanceInvariantTests(unittest.TestCase):
    def test_module_defines_no_github_mutating_capability(self) -> None:
        public = {n for n in dir(prv) if not n.startswith("_")}
        offending = {
            n
            for n in public
            if any(frag in n.lower() for frag in prv.PROHIBITED_CAPABILITY_NAME_FRAGMENTS)
        }
        self.assertEqual(offending, set())

    def test_no_function_takes_an_approval_or_bypass_parameter(self) -> None:
        import inspect

        for name, obj in inspect.getmembers(prv, inspect.isfunction):
            for param in inspect.signature(obj).parameters:
                lowered = param.lower()
                for fragment in ("approv", "bypass", "ownership"):
                    self.assertNotIn(fragment, lowered, f"{name}() param {param}")

    def test_status_vocabularies_contain_no_pr_verdicts(self) -> None:
        prohibited = {"APPROVE", "REQUEST_CHANGES", "MERGE"}
        names = (
            {m.name for m in prv.PriorItemClass}
            | {m.name for m in prv.DecisionStatus}
            | {m.name for m in prv.RegressionOutcome}
        )
        self.assertEqual(names & prohibited, set())


if __name__ == "__main__":
    unittest.main()
