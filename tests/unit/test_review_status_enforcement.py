#!/usr/bin/env python3
"""Regression coverage for the exact-HEAD machine-readable review status
(Issue #34).

Mirrors skills/github-pr-review/policies/review-status-enforcement.md.

Core invariants under test:

* a status belongs only to its reviewed SHA — SHA A never satisfies SHA B;
* no false green — only a complete, current-HEAD `REVIEW CLEAN` can
  publish `success`, and only with the same trusted authorization +
  reviewer independence a native APPROVE needs;
* a self-review may publish a blocking status but never a `success` one;
* enforcement detection reads rulesets *and* classic branch protection;
* required-check setup is explicit, minimal, preserving, and idempotent;
* no merge capability is introduced.

Run with:
    python3 -m unittest tests.unit.test_review_status_enforcement
"""

from __future__ import annotations

import inspect
import unittest

from tests.reference import review_action_authorization as raa
from tests.reference import review_status_enforcement as rse

REPO = "octo/repo"
PR = 42
HEAD = "sha_a0000"
HEAD_B = "sha_b1111"


def _auth(
    provenance: raa.Provenance,
    *,
    repo: str = REPO,
    pr: int = PR,
    head: str = HEAD,
    action: raa.GitHubEvent = raa.GitHubEvent.APPROVE,
) -> raa.MutationAuthorization:
    return raa.MutationAuthorization(
        provenance=provenance,
        scope=raa.AuthorizationScope(
            repo=repo, pr_number=pr, head_sha=head, action=action
        ),
    )


def _pub_input(**kw) -> rse.StatusPublicationInput:
    base = dict(
        reasoning=rse.Reasoning.CLEAN,
        repo=REPO,
        pr_number=PR,
        reviewed_head_sha=HEAD,
        current_head_sha=HEAD,
    )
    base.update(kw)
    return rse.StatusPublicationInput(**base)


def _authorized_independent(**kw) -> rse.StatusPublicationInput:
    return _pub_input(
        requested_mode=raa.ActionMode.EXPLICITLY_AUTHORIZED_AUTO_ACTION,
        authorization=_auth(raa.Provenance.INDEPENDENT_TRUSTED),
        reviewer_independence=raa.ReviewerIndependence.INDEPENDENT,
        **kw,
    )


# --- 1 + 3 + verdict mapping ----------------------------------------


class VerdictMapping(unittest.TestCase):
    def test_clean_is_a_success_candidate(self) -> None:
        self.assertEqual(
            rse.map_verdict_to_status(rse.Reasoning.CLEAN), rse.StatusState.SUCCESS
        )

    def test_changes_required_is_failure(self) -> None:
        self.assertEqual(
            rse.map_verdict_to_status(rse.Reasoning.CHANGES_REQUIRED),
            rse.StatusState.FAILURE,
        )

    def test_non_clean_states_never_map_to_success(self) -> None:
        for reasoning in (
            rse.Reasoning.INCOMPLETE,
            rse.Reasoning.JIRA_UNRESOLVED,
            rse.Reasoning.CONTEXT_UNAVAILABLE,
        ):
            self.assertEqual(
                rse.map_verdict_to_status(reasoning), rse.StatusState.FAILURE
            )

    def test_no_new_delta_publishes_nothing(self) -> None:
        self.assertEqual(
            rse.map_verdict_to_status(rse.Reasoning.NO_NEW_DELTA), rse.StatusState.NONE
        )
        out = rse.resolve_status_publication(
            _pub_input(reasoning=rse.Reasoning.NO_NEW_DELTA)
        )
        self.assertFalse(out.published)


class CleanSuccessNeedsPositiveAuthorization(unittest.TestCase):
    """Scenario 1."""

    def test_clean_publishes_success_only_with_trusted_auth_and_independence(self) -> None:
        out = rse.resolve_status_publication(_authorized_independent())
        self.assertTrue(out.published)
        self.assertEqual(out.published_state, rse.StatusState.SUCCESS)
        self.assertEqual(out.target_sha, HEAD)

    def test_clean_without_authorization_withholds_success(self) -> None:
        out = rse.resolve_status_publication(_pub_input())
        self.assertFalse(out.published)
        self.assertNotEqual(out.published_state, rse.StatusState.SUCCESS)

    def test_clean_independent_but_not_auto_action_withholds_success(self) -> None:
        out = rse.resolve_status_publication(
            _pub_input(reviewer_independence=raa.ReviewerIndependence.INDEPENDENT)
        )
        self.assertFalse(out.published)

    def test_clean_auto_action_but_ambiguous_independence_fails_closed(self) -> None:
        out = rse.resolve_status_publication(
            _pub_input(
                requested_mode=raa.ActionMode.EXPLICITLY_AUTHORIZED_AUTO_ACTION,
                authorization=_auth(raa.Provenance.INDEPENDENT_TRUSTED),
                reviewer_independence=raa.ReviewerIndependence.AMBIGUOUS,
            )
        )
        self.assertFalse(out.published)

    def test_agent_controlled_authorization_never_publishes_success(self) -> None:
        out = rse.resolve_status_publication(
            _pub_input(
                requested_mode=raa.ActionMode.EXPLICITLY_AUTHORIZED_AUTO_ACTION,
                authorization=_auth(raa.Provenance.AGENT_CONTROLLED),
                reviewer_independence=raa.ReviewerIndependence.INDEPENDENT,
            )
        )
        self.assertFalse(out.published)


class BlockingStatusIsBlockingOnly(unittest.TestCase):
    """Scenario 2."""

    def test_changes_required_publishes_failure_when_write_permitted(self) -> None:
        out = rse.resolve_status_publication(
            _pub_input(reasoning=rse.Reasoning.CHANGES_REQUIRED)
        )
        self.assertTrue(out.published)
        self.assertEqual(out.published_state, rse.StatusState.FAILURE)

    def test_blocking_status_needs_no_reviewer_independence(self) -> None:
        out = rse.resolve_status_publication(
            _pub_input(
                reasoning=rse.Reasoning.CHANGES_REQUIRED,
                reviewer_independence=raa.ReviewerIndependence.AMBIGUOUS,
            )
        )
        self.assertTrue(out.published)

    def test_incomplete_review_publishes_failure_never_success(self) -> None:
        out = rse.resolve_status_publication(
            _pub_input(reasoning=rse.Reasoning.INCOMPLETE)
        )
        self.assertTrue(out.published)
        self.assertEqual(out.published_state, rse.StatusState.FAILURE)

    def test_blocking_status_withheld_without_write_capability(self) -> None:
        out = rse.resolve_status_publication(
            _pub_input(
                reasoning=rse.Reasoning.CHANGES_REQUIRED, status_write_permitted=False
            )
        )
        self.assertFalse(out.published)


class SelfReview(unittest.TestCase):
    """Scenarios 3 + 4."""

    def test_self_review_may_publish_a_blocking_status(self) -> None:
        for kw in ({"self_review": True}, {"same_controlling_authority_as_author": True}):
            out = rse.resolve_status_publication(
                _pub_input(reasoning=rse.Reasoning.CHANGES_REQUIRED, **kw)
            )
            self.assertTrue(out.published, kw)
            self.assertEqual(out.published_state, rse.StatusState.FAILURE)

    def test_self_review_never_publishes_success_even_when_otherwise_authorized(self) -> None:
        for kw in ({"self_review": True}, {"same_controlling_authority_as_author": True}):
            out = rse.resolve_status_publication(_authorized_independent(**kw))
            self.assertFalse(out.published, kw)
            self.assertNotEqual(out.published_state, rse.StatusState.SUCCESS)
            self.assertIn("self-review", out.withheld_reason)

    def test_self_review_success_forbidden_across_the_whole_input_space(self) -> None:
        for rmode in raa.ActionMode:
            for prov in raa.Provenance:
                for indep in raa.ReviewerIndependence:
                    for kw in (
                        {"self_review": True},
                        {"same_controlling_authority_as_author": True},
                    ):
                        out = rse.resolve_status_publication(
                            _pub_input(
                                reasoning=rse.Reasoning.CLEAN,
                                requested_mode=rmode,
                                authorization=_auth(prov),
                                reviewer_independence=indep,
                                **kw,
                            )
                        )
                        self.assertNotEqual(
                            out.published_state, rse.StatusState.SUCCESS
                        )
                        self.assertFalse(
                            out.published and out.published_state is rse.StatusState.SUCCESS
                        )


class IncompleteNeverGreen(unittest.TestCase):
    """Scenario 5."""

    def test_no_reasoning_result_other_than_clean_can_publish_success(self) -> None:
        for reasoning in rse.Reasoning:
            if reasoning is rse.Reasoning.CLEAN:
                continue
            out = rse.resolve_status_publication(
                _authorized_independent(reasoning=reasoning)
            )
            self.assertNotEqual(out.published_state, rse.StatusState.SUCCESS, reasoning)


class ShaBinding(unittest.TestCase):
    """Scenarios 6 + 7."""

    def test_status_target_is_the_reviewed_sha(self) -> None:
        out = rse.resolve_status_publication(_authorized_independent())
        self.assertEqual(out.target_sha, HEAD)
        self.assertNotEqual(out.target_sha, HEAD_B)

    def test_a_status_for_sha_a_is_not_evidence_for_sha_b(self) -> None:
        # The published status is bound to HEAD (SHA A). A later review of
        # SHA B starts with no publication for B until B is reviewed.
        a = rse.resolve_status_publication(_authorized_independent())
        self.assertTrue(a.published)
        b_before_review = rse.resolve_status_publication(
            _pub_input(
                reasoning=rse.Reasoning.NO_NEW_DELTA,
                reviewed_head_sha=HEAD_B,
                current_head_sha=HEAD_B,
            )
        )
        self.assertFalse(b_before_review.published)

    def test_head_advanced_between_review_and_publication_withholds(self) -> None:
        out = rse.resolve_status_publication(
            _authorized_independent(current_head_sha=HEAD_B)
        )
        self.assertFalse(out.published)
        self.assertIn("HEAD advanced", out.withheld_reason)

    def test_head_advanced_also_withholds_a_blocking_status(self) -> None:
        out = rse.resolve_status_publication(
            _pub_input(
                reasoning=rse.Reasoning.CHANGES_REQUIRED, current_head_sha=HEAD_B
            )
        )
        self.assertFalse(out.published)


class ParallelWorkerCannotPublish(unittest.TestCase):
    """Scenario 8."""

    def test_worker_never_publishes_success_or_failure(self) -> None:
        for reasoning in (rse.Reasoning.CLEAN, rse.Reasoning.CHANGES_REQUIRED):
            out = rse.resolve_status_publication(
                _authorized_independent(reasoning=reasoning, is_parallel_worker=True)
            )
            self.assertFalse(out.published)
            self.assertIn("worker", out.withheld_reason)


class EnforcementDetection(unittest.TestCase):
    """Scenario 9."""

    def test_enforced_via_ruleset(self) -> None:
        cfg = rse.BranchEnforcementConfig(
            readable=True,
            ruleset_required_contexts=frozenset({rse.STATUS_CONTEXT}),
        )
        self.assertEqual(rse.detect_enforcement(cfg), rse.EnforcementState.ENFORCED)

    def test_enforced_via_classic_branch_protection(self) -> None:
        cfg = rse.BranchEnforcementConfig(
            readable=True,
            classic_required_contexts=frozenset({rse.STATUS_CONTEXT}),
        )
        self.assertEqual(rse.detect_enforcement(cfg), rse.EnforcementState.ENFORCED)

    def test_not_enforced_when_context_absent(self) -> None:
        cfg = rse.BranchEnforcementConfig(
            readable=True,
            ruleset_required_contexts=frozenset({"test", "lint"}),
        )
        self.assertEqual(rse.detect_enforcement(cfg), rse.EnforcementState.NOT_ENFORCED)

    def test_unknown_when_configuration_unreadable(self) -> None:
        cfg = rse.BranchEnforcementConfig(readable=False)
        self.assertEqual(rse.detect_enforcement(cfg), rse.EnforcementState.UNKNOWN)


class RequiredCheckSetup(unittest.TestCase):
    """Scenarios 10 + 11."""

    def _current(self, **kw) -> rse.RequiredCheckConfig:
        base = dict(
            readable=True,
            required_contexts=frozenset({"test", "lint"}),
            bypass_actors=("release-app", "admin-role"),
            approving_review_count=1,
            dismiss_stale_reviews_on_push=False,
            require_last_push_approval=False,
            other_rules=("non_fast_forward", "deletion"),
        )
        base.update(kw)
        return rse.RequiredCheckConfig(**base)

    def _plan(self, current, **kw) -> rse.SetupPlan:
        base = dict(
            explicit_request=True,
            authorization=_auth(raa.Provenance.INDEPENDENT_TRUSTED),
            repo=REPO,
            pr_number=PR,
            head_sha=HEAD,
            reviewer_independence=raa.ReviewerIndependence.INDEPENDENT,
        )
        base.update(kw)
        return rse.plan_required_check_setup(current, **base)

    def test_setup_never_runs_during_an_ordinary_review(self) -> None:
        plan = self._plan(self._current(), explicit_request=False)
        self.assertFalse(plan.apply)
        self.assertIn("explicit", plan.withheld_reason)

    def test_setup_adds_only_the_one_context_and_preserves_the_rest(self) -> None:
        plan = self._plan(self._current())
        self.assertTrue(plan.apply)
        self.assertTrue(plan.preserved)
        self.assertEqual(plan.resulting_contexts, frozenset({"test", "lint", rse.STATUS_CONTEXT}))
        self.assertLess(
            len({"test", "lint"} - plan.resulting_contexts), 1
        )  # every prior check survives

    def test_setup_is_idempotent_when_already_required(self) -> None:
        current = self._current(
            required_contexts=frozenset({"test", "lint", rse.STATUS_CONTEXT})
        )
        plan = self._plan(current)
        self.assertTrue(plan.noop)
        self.assertFalse(plan.apply)

    def test_setup_requires_trusted_authorization(self) -> None:
        plan = self._plan(
            self._current(), authorization=_auth(raa.Provenance.AGENT_CONTROLLED)
        )
        self.assertFalse(plan.apply)

    def test_setup_does_not_mutate_when_config_unreadable(self) -> None:
        plan = self._plan(self._current(readable=False, required_contexts=frozenset()))
        self.assertFalse(plan.apply)

    def test_read_back_verification_accepts_a_minimal_preserving_change(self) -> None:
        before = self._current()
        after = self._current(
            required_contexts=frozenset({"test", "lint", rse.STATUS_CONTEXT})
        )
        self.assertTrue(rse.verify_required_check_setup(before, after))

    def test_read_back_verification_rejects_a_dropped_unrelated_check(self) -> None:
        before = self._current()
        after = self._current(required_contexts=frozenset({"test", rse.STATUS_CONTEXT}))
        self.assertFalse(rse.verify_required_check_setup(before, after))

    def test_read_back_verification_rejects_touched_bypass_actors(self) -> None:
        before = self._current()
        after = self._current(
            required_contexts=frozenset({"test", "lint", rse.STATUS_CONTEXT}),
            bypass_actors=("release-app",),
        )
        self.assertFalse(rse.verify_required_check_setup(before, after))

    def test_read_back_verification_rejects_touched_stale_review_settings(self) -> None:
        before = self._current()
        after = self._current(
            required_contexts=frozenset({"test", "lint", rse.STATUS_CONTEXT}),
            dismiss_stale_reviews_on_push=True,
        )
        self.assertFalse(rse.verify_required_check_setup(before, after))


class IdempotentPublication(unittest.TestCase):
    """Scenario 11 (publication side)."""

    def test_same_sha_same_verdict_converges_on_one_status(self) -> None:
        first = rse.resolve_status_publication(_authorized_independent())
        second = rse.resolve_status_publication(_authorized_independent())
        self.assertEqual(first.context, second.context)
        self.assertEqual(first.target_sha, second.target_sha)
        self.assertEqual(first.published_state, second.published_state)


class NoMergeCapability(unittest.TestCase):
    """Scenario 12."""

    def test_module_exposes_no_merge_function(self) -> None:
        for name in vars(rse):
            self.assertNotIn("merge", name.lower(), f"{name} hints at a merge capability")

    def test_no_public_signature_has_an_escape_hatch_parameter(self) -> None:
        for name, obj in vars(rse).items():
            if not callable(obj) or name.startswith("_"):
                continue
            try:
                params = " ".join(inspect.signature(obj).parameters).lower()
            except (TypeError, ValueError):
                continue
            for fragment in rse.PROHIBITED_ESCAPE_HATCH_FRAGMENTS:
                self.assertNotIn(
                    fragment, params, f"{name} exposes an escape hatch: {fragment}"
                )

    def test_status_publication_is_never_a_merge(self) -> None:
        out = rse.resolve_status_publication(_authorized_independent())
        self.assertFalse(out.merged)

    def test_gate_carries_no_severity_or_decision_logic(self) -> None:
        # It only maps an already-derived reasoning result.
        self.assertEqual(
            list(inspect.signature(rse.map_verdict_to_status).parameters), ["reasoning"]
        )
        self.assertEqual(
            list(inspect.signature(rse.resolve_status_publication).parameters), ["inp"]
        )


if __name__ == "__main__":
    unittest.main()
