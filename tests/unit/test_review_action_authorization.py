#!/usr/bin/env python3
"""Regression coverage for the review-action authorization gate.

Mirrors skills/github-pr-review/policies/review-action-authorization.md
and skills/github-pr-review/policies/review-output.md, "Review-action
authorization gate". Scenario numbers map to Issue #101's acceptance
coverage list.

Run with:
    python3 -m unittest tests.unit.test_review_action_authorization
"""

from __future__ import annotations

import inspect
import unittest

from tests.reference import decision_semantics as ds
from tests.reference import review_action_authorization as raa
from tests.reference.reviewer_ownership import (
    SELF_REVIEW_SKIPPED,
    ReviewModeInput,
    resolve_review_mode,
)

REPO = "octo/repo"
PR = 123
HEAD = "head000"


def _auth(provenance: raa.Provenance, *, repo=REPO, pr=PR, head=HEAD,
          action=raa.GitHubEvent.APPROVE, scoped=True) -> raa.MutationAuthorization:
    scope = (
        raa.AuthorizationScope(repo=repo, pr_number=pr, head_sha=head, action=action)
        if scoped
        else None
    )
    return raa.MutationAuthorization(provenance=provenance, scope=scope)


def _base(**kw) -> raa.ActionAuthorizationInput:
    params = dict(
        verdict=raa.Verdict.CLEAN,
        repo=REPO,
        pr_number=PR,
        reviewed_head_sha=HEAD,
        current_head_sha=HEAD,
        permitted_events=frozenset(
            {raa.GitHubEvent.APPROVE, raa.GitHubEvent.REQUEST_CHANGES}
        ),
    )
    params.update(kw)
    return raa.ActionAuthorizationInput(**params)


def _independent() -> raa.ReviewerIndependence:
    return raa.classify_reviewer_independence(
        reviewer_actor_selected_by_implementing_agent=False,
        reviewer_provenance_known=True,
    )


class Scenario01_AutonomousNoAuthorization(unittest.TestCase):
    def test_review_completes_and_no_mutation_occurs(self) -> None:
        out = raa.resolve_mutation_outcome(_base())
        self.assertEqual(out.mode, raa.ActionMode.RECOMMENDATION_ONLY)
        self.assertFalse(out.mutated)
        self.assertEqual(out.event, raa.GitHubEvent.NONE)
        # The verdict is still produced and reported.
        self.assertEqual(out.verdict, raa.Verdict.CLEAN)
        self.assertIsNotNone(out.withheld_reason)


class Scenario02_AgentEnablesAutoActionItself(unittest.TestCase):
    def test_agent_set_flag_does_not_authorize(self) -> None:
        out = raa.resolve_mutation_outcome(
            _base(
                requested_mode=raa.ActionMode.EXPLICITLY_AUTHORIZED_AUTO_ACTION,
                authorization=_auth(
                    raa.classify_provenance("action_mode_flag")
                ),
                reviewer_independence=_independent(),
            )
        )
        self.assertNotEqual(
            out.mode, raa.ActionMode.EXPLICITLY_AUTHORIZED_AUTO_ACTION
        )
        self.assertFalse(out.mutated)


class Scenario03_ApproveIfCleanText(unittest.TestCase):
    def test_generated_text_is_not_authorization(self) -> None:
        self.assertEqual(
            raa.classify_provenance("approve_if_clean_text"),
            raa.Provenance.AGENT_CONTROLLED,
        )
        out = raa.resolve_mutation_outcome(
            _base(
                requested_mode=raa.ActionMode.EXPLICITLY_AUTHORIZED_AUTO_ACTION,
                authorization=_auth(raa.classify_provenance("approve_if_clean_text")),
                reviewer_independence=_independent(),
            )
        )
        self.assertFalse(out.mutated)


class Scenario04_NestedSkillOrAgentGrant(unittest.TestCase):
    def test_nested_invocation_cannot_grant_authority(self) -> None:
        for channel in ("nested_skill_invocation", "nested_agent_instruction",
                        "sub_agent", "spawned_process"):
            with self.subTest(channel=channel):
                self.assertEqual(
                    raa.classify_provenance(channel),
                    raa.Provenance.AGENT_CONTROLLED,
                )
                out = raa.resolve_mutation_outcome(
                    _base(
                        requested_mode=raa.ActionMode.EXPLICITLY_AUTHORIZED_AUTO_ACTION,
                        authorization=_auth(raa.classify_provenance(channel)),
                        reviewer_independence=_independent(),
                    )
                )
                self.assertFalse(out.mutated)


class Scenario05_GenuineTrustedAuthorization(unittest.TestCase):
    def test_trusted_scoped_authorization_approves_a_clean_pr(self) -> None:
        out = raa.resolve_mutation_outcome(
            _base(
                requested_mode=raa.ActionMode.EXPLICITLY_AUTHORIZED_AUTO_ACTION,
                authorization=_auth(
                    raa.classify_provenance("human_principal_out_of_band")
                ),
                reviewer_independence=_independent(),
            )
        )
        self.assertEqual(
            out.mode, raa.ActionMode.EXPLICITLY_AUTHORIZED_AUTO_ACTION
        )
        self.assertTrue(out.mutated)
        self.assertEqual(out.event, raa.GitHubEvent.APPROVE)
        self.assertIsNone(out.withheld_reason)


class Scenario06_CleanVerdictWithoutAuthorization(unittest.TestCase):
    def test_clean_without_authorization_is_non_mutating(self) -> None:
        out = raa.resolve_mutation_outcome(_base(verdict=raa.Verdict.CLEAN))
        self.assertFalse(out.mutated)
        self.assertEqual(out.verdict, raa.Verdict.CLEAN)


class Scenario07_StaleHeadBlocksMutation(unittest.TestCase):
    def test_stale_head_withholds_even_with_authorization(self) -> None:
        out = raa.resolve_mutation_outcome(
            _base(
                reviewed_head_sha="old111",
                current_head_sha="new222",
                requested_mode=raa.ActionMode.EXPLICITLY_AUTHORIZED_AUTO_ACTION,
                authorization=_auth(
                    raa.classify_provenance("human_principal_out_of_band"),
                    head="old111",
                ),
                reviewer_independence=_independent(),
            )
        )
        self.assertFalse(out.mutated)
        self.assertIn("stale", out.withheld_reason)


class Scenario08_ApprovalIsNotMergeAuthority(unittest.TestCase):
    def test_model_cannot_express_a_merge_event(self) -> None:
        events = {e.name for e in raa.GitHubEvent}
        self.assertNotIn("MERGE", events)
        self.assertEqual(events, {"NONE", "APPROVE", "REQUEST_CHANGES"})

    def test_a_submitted_approval_yields_only_an_approve_event(self) -> None:
        out = raa.resolve_mutation_outcome(
            _base(
                requested_mode=raa.ActionMode.EXPLICITLY_AUTHORIZED_AUTO_ACTION,
                authorization=_auth(
                    raa.classify_provenance("runtime_verified_principal_authorization")
                ),
                reviewer_independence=_independent(),
            )
        )
        self.assertEqual(out.event, raa.GitHubEvent.APPROVE)
        # No field, flag, or return value implies merge.
        self.assertNotIn("merge", repr(out).lower())


class Scenario09_SelfReviewSameIdentity(unittest.TestCase):
    def test_self_review_is_rejected_regardless_of_everything_else(self) -> None:
        out = raa.resolve_mutation_outcome(
            _base(
                self_review=True,
                requested_mode=raa.ActionMode.EXPLICITLY_AUTHORIZED_AUTO_ACTION,
                authorization=_auth(
                    raa.classify_provenance("human_principal_out_of_band")
                ),
                reviewer_independence=_independent(),
            )
        )
        self.assertFalse(out.mutated)
        self.assertIn("self-review", out.withheld_reason)


class Scenario10_SelfReviewViaAnotherControlledIdentity(unittest.TestCase):
    def test_agent_selected_reviewer_is_not_independent(self) -> None:
        independence = raa.classify_reviewer_independence(
            reviewer_actor_selected_by_implementing_agent=True,
            reviewer_provenance_known=True,
        )
        self.assertEqual(independence, raa.ReviewerIndependence.SAME_AUTHORITY)
        out = raa.resolve_mutation_outcome(
            _base(
                requested_mode=raa.ActionMode.EXPLICITLY_AUTHORIZED_AUTO_ACTION,
                authorization=_auth(
                    raa.classify_provenance("human_principal_out_of_band")
                ),
                reviewer_independence=independence,
            )
        )
        self.assertFalse(out.mutated)


class Scenario11_AlternateToken(unittest.TestCase):
    def test_alternate_token_is_agent_controlled_and_not_independent(self) -> None:
        self.assertEqual(
            raa.classify_provenance("alternate_token"),
            raa.Provenance.AGENT_CONTROLLED,
        )
        out = raa.resolve_mutation_outcome(
            _base(
                requested_mode=raa.ActionMode.EXPLICITLY_AUTHORIZED_AUTO_ACTION,
                authorization=_auth(raa.classify_provenance("alternate_token")),
                reviewer_independence=raa.classify_reviewer_independence(
                    reviewer_actor_selected_by_implementing_agent=True,
                    reviewer_provenance_known=True,
                ),
            )
        )
        self.assertFalse(out.mutated)


class Scenario12_BotServiceOrAppIdentity(unittest.TestCase):
    def test_agent_driven_machine_identity_does_not_bypass_the_guard(self) -> None:
        for channel in ("bot_identity", "service_account", "github_app_identity"):
            with self.subTest(channel=channel):
                self.assertEqual(
                    raa.classify_provenance(channel),
                    raa.Provenance.AGENT_CONTROLLED,
                )
        independence = raa.classify_reviewer_independence(
            reviewer_actor_selected_by_implementing_agent=True,
            reviewer_provenance_known=True,
        )
        out = raa.resolve_mutation_outcome(
            _base(
                requested_mode=raa.ActionMode.EXPLICITLY_AUTHORIZED_AUTO_ACTION,
                authorization=_auth(raa.classify_provenance("github_app_identity")),
                reviewer_independence=independence,
            )
        )
        self.assertFalse(out.mutated)


class Scenario13_NestedReviewerUnderSameAuthority(unittest.TestCase):
    def test_nested_reviewer_agent_is_not_external_review(self) -> None:
        independence = raa.classify_reviewer_independence(
            reviewer_actor_selected_by_implementing_agent=True,
            reviewer_provenance_known=True,
        )
        self.assertEqual(independence, raa.ReviewerIndependence.SAME_AUTHORITY)
        out = raa.resolve_mutation_outcome(
            _base(reviewer_independence=independence,
                  requested_mode=raa.ActionMode.BLOCK_ONLY,
                  verdict=raa.Verdict.BLOCKING)
        )
        # Not even a block is issued by a non-independent reviewer.
        self.assertFalse(out.mutated)
        self.assertIn("independence", out.withheld_reason)


class Scenario14_GenuinelyIndependentTrustedReviewer(unittest.TestCase):
    def test_independent_reviewer_with_trusted_authorization_succeeds(self) -> None:
        out = raa.resolve_mutation_outcome(
            _base(
                requested_mode=raa.ActionMode.EXPLICITLY_AUTHORIZED_AUTO_ACTION,
                authorization=_auth(
                    raa.classify_provenance("human_principal_out_of_band")
                ),
                reviewer_independence=_independent(),
            )
        )
        self.assertTrue(out.mutated)
        self.assertEqual(out.event, raa.GitHubEvent.APPROVE)

    def test_independent_reviewer_can_block_without_auto_action_authorization(self) -> None:
        out = raa.resolve_mutation_outcome(
            _base(
                verdict=raa.Verdict.BLOCKING,
                requested_mode=raa.ActionMode.BLOCK_ONLY,
                reviewer_independence=_independent(),
            )
        )
        self.assertEqual(out.event, raa.GitHubEvent.REQUEST_CHANGES)
        self.assertTrue(out.mutated)


class Scenario15_AmbiguousAuthorizationProvenance(unittest.TestCase):
    def test_ambiguous_provenance_fails_closed(self) -> None:
        self.assertEqual(
            raa.classify_provenance("some_unknown_channel"),
            raa.Provenance.AMBIGUOUS,
        )
        out = raa.resolve_mutation_outcome(
            _base(
                requested_mode=raa.ActionMode.EXPLICITLY_AUTHORIZED_AUTO_ACTION,
                authorization=_auth(raa.classify_provenance("some_unknown_channel")),
                reviewer_independence=_independent(),
            )
        )
        self.assertFalse(out.mutated)
        self.assertEqual(out.mode, raa.ActionMode.RECOMMENDATION_ONLY)


class Scenario16_AmbiguousReviewerProvenance(unittest.TestCase):
    def test_ambiguous_reviewer_provenance_fails_closed(self) -> None:
        independence = raa.classify_reviewer_independence(
            reviewer_actor_selected_by_implementing_agent=False,
            reviewer_provenance_known=False,
        )
        self.assertEqual(independence, raa.ReviewerIndependence.AMBIGUOUS)
        out = raa.resolve_mutation_outcome(
            _base(
                requested_mode=raa.ActionMode.EXPLICITLY_AUTHORIZED_AUTO_ACTION,
                authorization=_auth(
                    raa.classify_provenance("human_principal_out_of_band")
                ),
                reviewer_independence=independence,
            )
        )
        self.assertFalse(out.mutated)


class Scenario17_AuthorizationScopeCannotBeReplayed(unittest.TestCase):
    def setUp(self) -> None:
        self.auth = _auth(
            raa.classify_provenance("human_principal_out_of_band"),
            repo=REPO, pr=PR, head=HEAD, action=raa.GitHubEvent.APPROVE,
        )

    def test_matches_only_its_exact_scope(self) -> None:
        self.assertTrue(
            raa.authorization_covers(
                self.auth, repo=REPO, pr_number=PR, head_sha=HEAD,
                action=raa.GitHubEvent.APPROVE,
            )
        )

    def test_rejected_for_another_pr(self) -> None:
        self.assertFalse(
            raa.authorization_covers(
                self.auth, repo=REPO, pr_number=PR + 1, head_sha=HEAD,
                action=raa.GitHubEvent.APPROVE,
            )
        )

    def test_rejected_for_another_head(self) -> None:
        self.assertFalse(
            raa.authorization_covers(
                self.auth, repo=REPO, pr_number=PR, head_sha="advanced999",
                action=raa.GitHubEvent.APPROVE,
            )
        )

    def test_rejected_for_another_repo(self) -> None:
        self.assertFalse(
            raa.authorization_covers(
                self.auth, repo="evil/fork", pr_number=PR, head_sha=HEAD,
                action=raa.GitHubEvent.APPROVE,
            )
        )

    def test_rejected_for_another_action(self) -> None:
        self.assertFalse(
            raa.authorization_covers(
                self.auth, repo=REPO, pr_number=PR, head_sha=HEAD,
                action=raa.GitHubEvent.REQUEST_CHANGES,
            )
        )

    def test_gate_rejects_replayed_authorization_on_advanced_head(self) -> None:
        out = raa.resolve_mutation_outcome(
            _base(
                reviewed_head_sha=HEAD,
                current_head_sha=HEAD,  # HEAD not stale...
                requested_mode=raa.ActionMode.EXPLICITLY_AUTHORIZED_AUTO_ACTION,
                # ...but the authorization was issued for a *different* PR
                authorization=_auth(
                    raa.classify_provenance("human_principal_out_of_band"),
                    pr=999,
                ),
                reviewer_independence=_independent(),
            )
        )
        self.assertFalse(out.mutated)
        self.assertIn("scope", out.withheld_reason)


class Scenario18_SeverityDecisionUnchanged(unittest.TestCase):
    def test_mechanical_decision_derivation_is_untouched(self) -> None:
        self.assertEqual(ds.derive_decision([]), ds.Decision.CLEAN)
        self.assertEqual(
            ds.derive_decision([ds.Finding("F1", ds.Severity.P1)]),
            ds.Decision.CHANGES_REQUIRED,
        )

    def test_gate_reports_the_verdict_it_was_given_without_changing_it(self) -> None:
        for verdict in (raa.Verdict.CLEAN, raa.Verdict.BLOCKING):
            with self.subTest(verdict=verdict):
                out = raa.resolve_mutation_outcome(_base(verdict=verdict))
                self.assertEqual(out.verdict, verdict)

    def test_gate_module_does_not_reimplement_severity_or_decision(self) -> None:
        # The gate consumes an already-derived verdict; it must not carry
        # its own severity model or decision derivation.
        self.assertFalse(hasattr(raa, "Severity"))
        self.assertFalse(hasattr(raa, "derive_decision"))
        self.assertFalse(hasattr(raa, "blocking_findings"))
        sig = inspect.signature(raa.resolve_mutation_outcome)
        # verdict is an input, never computed here.
        self.assertEqual(list(sig.parameters), ["inp"])
        self.assertIn("verdict", inspect.signature(raa.ActionAuthorizationInput).parameters)


class Scenario19_DeltaReReviewUnchanged(unittest.TestCase):
    def test_reviewer_delta_mode_resolution_still_behaves(self) -> None:
        result = resolve_review_mode(
            ReviewModeInput(
                current_reviewer="alice",
                pr_author="carol",
                previous_review_exists=True,
                previous_reviewer="alice",
                previous_reviewed_sha="abc",
                current_head_sha="def",
            )
        )
        self.assertEqual(result.mode, "delta_re_review")

    def test_action_gate_does_not_depend_on_delta_state(self) -> None:
        sig = inspect.signature(raa.resolve_mutation_outcome)
        # The gate consumes only resolved facts; it never re-derives the
        # review mode.
        self.assertEqual(list(sig.parameters), ["inp"])
        self.assertNotIn("delta", inspect.getsource(raa).lower())


class Scenario20_ReviewerOwnershipUnchanged(unittest.TestCase):
    def test_self_review_guard_still_wins_in_ownership_resolution(self) -> None:
        result = resolve_review_mode(
            ReviewModeInput(
                current_reviewer="alice",
                pr_author="alice",
                previous_review_exists=True,
                previous_reviewer="alice",
                previous_reviewed_sha="abc",
                current_head_sha="def",
            )
        )
        self.assertEqual(result.mode, SELF_REVIEW_SKIPPED)


class GovernanceTests(unittest.TestCase):
    def test_default_mode_is_recommendation_only(self) -> None:
        self.assertEqual(
            raa.resolve_action_mode(_base()), raa.ActionMode.RECOMMENDATION_ONLY
        )
        self.assertEqual(
            raa.ActionAuthorizationInput(
                verdict=raa.Verdict.CLEAN, repo=REPO, pr_number=PR,
                reviewed_head_sha=HEAD, current_head_sha=HEAD,
            ).requested_mode,
            raa.ActionMode.RECOMMENDATION_ONLY,
        )

    def test_no_public_signature_has_an_escape_hatch_parameter(self) -> None:
        for name, obj in vars(raa).items():
            if not callable(obj) or name.startswith("_"):
                continue
            try:
                params = " ".join(inspect.signature(obj).parameters).lower()
            except (TypeError, ValueError):
                continue
            for fragment in raa.PROHIBITED_ESCAPE_HATCH_FRAGMENTS:
                self.assertNotIn(
                    fragment, params, f"{name} exposes an escape hatch: {fragment}"
                )

    def test_approve_is_never_submitted_outside_auto_action_mode(self) -> None:
        # Exhaustive-ish sweep: no combination of verdict / requested mode /
        # provenance / independence yields an APPROVE event unless the
        # resolved mode is explicitly-authorized auto-action.
        provenances = list(raa.Provenance)
        independences = list(raa.ReviewerIndependence)
        modes = list(raa.ActionMode)
        for verdict in raa.Verdict:
            for rmode in modes:
                for prov in provenances:
                    for indep in independences:
                        inp = _base(
                            verdict=verdict,
                            requested_mode=rmode,
                            authorization=_auth(prov),
                            reviewer_independence=indep,
                        )
                        out = raa.resolve_mutation_outcome(inp)
                        if out.event is raa.GitHubEvent.APPROVE:
                            self.assertEqual(
                                out.mode,
                                raa.ActionMode.EXPLICITLY_AUTHORIZED_AUTO_ACTION,
                            )
                            self.assertEqual(verdict, raa.Verdict.CLEAN)
                            self.assertEqual(indep, raa.ReviewerIndependence.INDEPENDENT)
                            self.assertEqual(prov, raa.Provenance.INDEPENDENT_TRUSTED)

    def test_passive_review_is_always_non_mutating(self) -> None:
        for verdict in raa.Verdict:
            for rmode in raa.ActionMode:
                out = raa.resolve_mutation_outcome(
                    _base(
                        passive=True,
                        verdict=verdict,
                        requested_mode=rmode,
                        authorization=_auth(raa.Provenance.INDEPENDENT_TRUSTED),
                        reviewer_independence=raa.ReviewerIndependence.INDEPENDENT,
                    )
                )
                self.assertFalse(out.mutated)
                self.assertEqual(out.mode, raa.ActionMode.RECOMMENDATION_ONLY)

    def test_every_agent_controlled_channel_classifies_as_untrusted(self) -> None:
        for channel in raa.AGENT_CONTROLLED_CHANNELS:
            self.assertEqual(
                raa.classify_provenance(channel), raa.Provenance.AGENT_CONTROLLED
            )

    def test_missing_or_empty_channel_is_never_trusted(self) -> None:
        self.assertEqual(raa.classify_provenance(None), raa.Provenance.NONE)
        self.assertEqual(raa.classify_provenance(""), raa.Provenance.NONE)


if __name__ == "__main__":
    unittest.main()
