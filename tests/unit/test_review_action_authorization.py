#!/usr/bin/env python3
"""Regression coverage for the review-action authorization gate and the
self-review model.

Mirrors skills/github-pr-review/policies/review-action-authorization.md,
skills/github-pr-review/policies/review-authority.md ("Self-review
capability"), and skills/github-pr-review/policies/review-output.md
("Review-action authorization gate").

Core invariant under test: **self-review is allowed; self-approval is
not.** Authorship gates the formal GitHub review event, never the
analysis or the verdict.

Run with:
    python3 -m unittest tests.unit.test_review_action_authorization
"""

from __future__ import annotations

import inspect
import unittest

from tests.reference import decision_semantics as ds
from tests.reference import review_action_authorization as raa
from tests.reference.reviewer_ownership import (
    DELTA_RE_REVIEW,
    NORMAL_FULL_REVIEW,
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


def _same_authority() -> raa.ReviewerIndependence:
    return raa.classify_reviewer_independence(
        reviewer_actor_selected_by_implementing_agent=True,
        reviewer_provenance_known=True,
    )


# --------------------------------------------------------------------------
# 1. own PR + clean review → analysis runs → REVIEW CLEAN → no APPROVE
# --------------------------------------------------------------------------
class OwnPrCleanReview(unittest.TestCase):
    def test_analysis_runs_verdict_clean_no_approve(self) -> None:
        inp = _base(self_review=True, verdict=raa.Verdict.CLEAN)
        elig = raa.review_eligibility(inp)
        self.assertTrue(elig.analysis_allowed)
        self.assertFalse(elig.formal_review_mutation_allowed)

        out = raa.resolve_mutation_outcome(inp)
        self.assertEqual(out.verdict, raa.Verdict.CLEAN)  # verdict preserved
        self.assertEqual(out.event, raa.GitHubEvent.NONE)  # no formal decision
        self.assertFalse(out.mutated)
        self.assertTrue(out.published_comment)  # informational COMMENT allowed
        self.assertIn("self-review", out.withheld_reason)


# --------------------------------------------------------------------------
# 2. own PR + P1 → analysis runs → CHANGES REQUIRED → no formal REQUEST_CHANGES
# --------------------------------------------------------------------------
class OwnPrBlockingReview(unittest.TestCase):
    def test_analysis_runs_verdict_blocking_no_request_changes(self) -> None:
        inp = _base(self_review=True, verdict=raa.Verdict.BLOCKING)
        out = raa.resolve_mutation_outcome(inp)
        self.assertEqual(out.verdict, raa.Verdict.BLOCKING)  # not softened
        self.assertEqual(out.event, raa.GitHubEvent.NONE)  # no formal decision
        self.assertFalse(out.mutated)
        self.assertTrue(out.published_comment)  # informational COMMENT allowed
        self.assertIn("self-review", out.withheld_reason)


# --------------------------------------------------------------------------
# 3. own PR + natural-language "approve if clean" → approval still withheld
# --------------------------------------------------------------------------
class OwnPrNaturalLanguageApprove(unittest.TestCase):
    def test_nl_approve_if_clean_does_not_unlock_self_approval(self) -> None:
        requested = raa.normalize_intent("Review it; approve if clean.")
        self.assertEqual(
            requested, raa.ActionMode.EXPLICITLY_AUTHORIZED_AUTO_ACTION
        )
        inp = _base(
            self_review=True,
            verdict=raa.Verdict.CLEAN,
            requested_mode=requested,
            # even a genuine trusted authorization cannot override authorship
            authorization=_auth(raa.classify_provenance("human_principal_out_of_band")),
            reviewer_independence=_independent(),
        )
        out = raa.resolve_mutation_outcome(inp)
        self.assertFalse(out.mutated)
        self.assertIn("self-review", out.withheld_reason)


# --------------------------------------------------------------------------
# 4. own PR + natural-language "request changes if blocking" → withheld
# --------------------------------------------------------------------------
class OwnPrNaturalLanguageRequestChanges(unittest.TestCase):
    def test_nl_request_changes_if_blocking_is_withheld_on_own_pr(self) -> None:
        requested = raa.normalize_intent(
            "Review it and block it if there are serious issues, but don't approve it."
        )
        self.assertEqual(requested, raa.ActionMode.BLOCK_ONLY)
        inp = _base(
            self_review=True,
            verdict=raa.Verdict.BLOCKING,
            requested_mode=requested,
            reviewer_independence=_independent(),
        )
        out = raa.resolve_mutation_outcome(inp)
        self.assertFalse(out.mutated)
        self.assertIn("self-review", out.withheld_reason)


# --------------------------------------------------------------------------
# 5. own PR + alternate token controlled by same authority → analysis, no mutation
# 6. own PR + alternate GitHub account controlled by same authority → same
# 7. own PR + nested/spawned review agent → no manufactured independence
# --------------------------------------------------------------------------
class OwnPrManufacturedIndependence(unittest.TestCase):
    CHANNELS = ("alternate_token", "alternate_username", "bot_identity",
                "service_account", "github_app_identity",
                "nested_agent_instruction", "sub_agent", "spawned_process")

    def test_controlled_alternate_identity_runs_analysis_but_never_mutates(self) -> None:
        for channel in self.CHANNELS:
            with self.subTest(channel=channel):
                self.assertEqual(
                    raa.classify_provenance(channel),
                    raa.Provenance.AGENT_CONTROLLED,
                )
                inp = _base(
                    same_controlling_authority_as_author=True,
                    verdict=raa.Verdict.CLEAN,
                    requested_mode=raa.ActionMode.EXPLICITLY_AUTHORIZED_AUTO_ACTION,
                    authorization=_auth(raa.classify_provenance(channel)),
                    reviewer_independence=_same_authority(),
                )
                self.assertTrue(raa.review_eligibility(inp).analysis_allowed)
                self.assertFalse(
                    raa.review_eligibility(inp).formal_review_mutation_allowed
                )
                out = raa.resolve_mutation_outcome(inp)
                self.assertFalse(out.mutated)
                self.assertIn("self-review", out.withheld_reason)

    def test_is_self_review_covers_controlled_alternate_identity(self) -> None:
        self.assertTrue(
            raa.is_self_review(_base(same_controlling_authority_as_author=True))
        )


# --------------------------------------------------------------------------
# 8. genuinely independent reviewer + clean + valid trusted authorization
#    → APPROVE may be submitted
# --------------------------------------------------------------------------
class IndependentReviewerApprove(unittest.TestCase):
    def test_independent_clean_trusted_authorization_approves(self) -> None:
        inp = _base(
            verdict=raa.Verdict.CLEAN,
            requested_mode=raa.ActionMode.EXPLICITLY_AUTHORIZED_AUTO_ACTION,
            authorization=_auth(raa.classify_provenance("human_principal_out_of_band")),
            reviewer_independence=_independent(),
        )
        self.assertTrue(raa.review_eligibility(inp).formal_review_mutation_allowed)
        out = raa.resolve_mutation_outcome(inp)
        self.assertTrue(out.mutated)
        self.assertEqual(out.event, raa.GitHubEvent.APPROVE)
        self.assertIsNone(out.withheld_reason)


# --------------------------------------------------------------------------
# 9. genuinely independent reviewer + blocking + permitted mode/auth
#    → REQUEST_CHANGES may be submitted
# --------------------------------------------------------------------------
class IndependentReviewerRequestChanges(unittest.TestCase):
    def test_independent_blocking_block_only_requests_changes(self) -> None:
        inp = _base(
            verdict=raa.Verdict.BLOCKING,
            requested_mode=raa.ActionMode.BLOCK_ONLY,
            reviewer_independence=_independent(),
        )
        out = raa.resolve_mutation_outcome(inp)
        self.assertTrue(out.mutated)
        self.assertEqual(out.event, raa.GitHubEvent.REQUEST_CHANGES)


# --------------------------------------------------------------------------
# 10. independent reviewer without trusted approval authorization
#     → REVIEW CLEAN still produced → APPROVE withheld
# --------------------------------------------------------------------------
class IndependentReviewerNoAuthorization(unittest.TestCase):
    def test_clean_verdict_produced_but_approve_withheld(self) -> None:
        inp = _base(verdict=raa.Verdict.CLEAN, reviewer_independence=_independent())
        out = raa.resolve_mutation_outcome(inp)
        self.assertEqual(out.verdict, raa.Verdict.CLEAN)
        self.assertFalse(out.mutated)
        self.assertEqual(out.mode, raa.ActionMode.RECOMMENDATION_ONLY)


# --------------------------------------------------------------------------
# 11. stale reviewed HEAD → verdict reported → mutation blocked
# --------------------------------------------------------------------------
class StaleHeadBlocksMutation(unittest.TestCase):
    def test_stale_head_reports_verdict_and_blocks_mutation(self) -> None:
        inp = _base(
            reviewed_head_sha="old111",
            current_head_sha="new222",
            verdict=raa.Verdict.CLEAN,
            requested_mode=raa.ActionMode.EXPLICITLY_AUTHORIZED_AUTO_ACTION,
            authorization=_auth(
                raa.classify_provenance("human_principal_out_of_band"), head="old111"
            ),
            reviewer_independence=_independent(),
        )
        out = raa.resolve_mutation_outcome(inp)
        self.assertEqual(out.verdict, raa.Verdict.CLEAN)
        self.assertFalse(out.mutated)
        self.assertIn("stale", out.withheld_reason)


# --------------------------------------------------------------------------
# 12. natural-language intent maps to internal behavior without mode keywords
# --------------------------------------------------------------------------
class NaturalLanguageIntentMapping(unittest.TestCase):
    def test_plain_review_request_is_recommendation_only(self) -> None:
        for phrase in ("Just review this PR.", "review it", "take a look at this PR"):
            self.assertEqual(
                raa.normalize_intent(phrase), raa.ActionMode.RECOMMENDATION_ONLY
            )

    def test_block_but_do_not_approve_is_block_only(self) -> None:
        self.assertEqual(
            raa.normalize_intent(
                "Review it and block it if there are serious issues, but don't approve it."
            ),
            raa.ActionMode.BLOCK_ONLY,
        )

    def test_approve_if_clean_is_an_auto_action_candidate(self) -> None:
        self.assertEqual(
            raa.normalize_intent(
                "Review it; approve if clean, request changes if there are blocking findings."
            ),
            raa.ActionMode.EXPLICITLY_AUTHORIZED_AUTO_ACTION,
        )

    def test_no_cli_keyword_syntax_is_required_or_recognised(self) -> None:
        # The normalizer takes ordinary language, not flags. A bare
        # "--auto-action" string is not a recognised mode selector and
        # falls through to the safe default.
        for flagish in ("--auto-action", "--block-only", "--recommendation-only"):
            self.assertEqual(
                raa.normalize_intent(flagish), raa.ActionMode.RECOMMENDATION_ONLY
            )

    def test_ambiguous_or_empty_intent_is_recommendation_only(self) -> None:
        for phrase in ("", None, "make it helpful", "do a good job"):
            self.assertEqual(
                raa.normalize_intent(phrase), raa.ActionMode.RECOMMENDATION_ONLY
            )

    def test_requested_mode_is_not_authorization(self) -> None:
        # An auto-action *request* with no trusted authorization still
        # produces no mutation.
        inp = _base(
            verdict=raa.Verdict.CLEAN,
            requested_mode=raa.normalize_intent("approve if clean"),
            reviewer_independence=_independent(),
        )
        out = raa.resolve_mutation_outcome(inp)
        self.assertFalse(out.mutated)


# --------------------------------------------------------------------------
# 13. unknown/ambiguous reviewer provenance → analysis not blocked → mutation fails closed
# --------------------------------------------------------------------------
class AmbiguousReviewerProvenance(unittest.TestCase):
    def test_ambiguous_provenance_allows_analysis_and_fails_mutation_closed(self) -> None:
        independence = raa.classify_reviewer_independence(
            reviewer_actor_selected_by_implementing_agent=False,
            reviewer_provenance_known=False,
        )
        self.assertEqual(independence, raa.ReviewerIndependence.AMBIGUOUS)
        inp = _base(
            verdict=raa.Verdict.CLEAN,
            requested_mode=raa.ActionMode.EXPLICITLY_AUTHORIZED_AUTO_ACTION,
            authorization=_auth(raa.classify_provenance("human_principal_out_of_band")),
            reviewer_independence=independence,
        )
        # analysis is not an ambiguity-gated concern here
        self.assertTrue(raa.analysis_allowed(inp))
        out = raa.resolve_mutation_outcome(inp)
        self.assertFalse(out.mutated)


class AmbiguousAuthorizationProvenance(unittest.TestCase):
    def test_ambiguous_authorization_channel_fails_closed(self) -> None:
        self.assertEqual(
            raa.classify_provenance("mystery_channel"), raa.Provenance.AMBIGUOUS
        )
        out = raa.resolve_mutation_outcome(
            _base(
                requested_mode=raa.ActionMode.EXPLICITLY_AUTHORIZED_AUTO_ACTION,
                authorization=_auth(raa.classify_provenance("mystery_channel")),
                reviewer_independence=_independent(),
            )
        )
        self.assertFalse(out.mutated)
        self.assertEqual(out.mode, raa.ActionMode.RECOMMENDATION_ONLY)


# --------------------------------------------------------------------------
# 14. verdict derivation remains independent of the authorization gate
# --------------------------------------------------------------------------
class VerdictIndependentOfGate(unittest.TestCase):
    def test_mechanical_decision_derivation_untouched(self) -> None:
        self.assertEqual(ds.derive_decision([]), ds.Decision.CLEAN)
        self.assertEqual(
            ds.derive_decision([ds.Finding("F1", ds.Severity.P1)]),
            ds.Decision.CHANGES_REQUIRED,
        )

    def test_gate_reports_the_verdict_it_was_given_for_every_reviewer_kind(self) -> None:
        for verdict in (raa.Verdict.CLEAN, raa.Verdict.BLOCKING):
            for kw in (
                {},
                {"self_review": True},
                {"same_controlling_authority_as_author": True},
                {"reviewer_independence": _independent()},
            ):
                with self.subTest(verdict=verdict, kw=kw):
                    out = raa.resolve_mutation_outcome(_base(verdict=verdict, **kw))
                    self.assertEqual(out.verdict, verdict)

    def test_gate_module_carries_no_severity_or_decision_logic(self) -> None:
        self.assertFalse(hasattr(raa, "Severity"))
        self.assertFalse(hasattr(raa, "derive_decision"))
        self.assertFalse(hasattr(raa, "blocking_findings"))
        self.assertEqual(
            list(inspect.signature(raa.resolve_mutation_outcome).parameters), ["inp"]
        )
        self.assertIn(
            "verdict",
            inspect.signature(raa.ActionAuthorizationInput).parameters,
        )


# --------------------------------------------------------------------------
# 15. delta re-review / reviewer-ownership semantics unchanged by this delta
# --------------------------------------------------------------------------
class ReviewModeSemanticsUnchanged(unittest.TestCase):
    def test_external_delta_re_review_still_resolves(self) -> None:
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
        self.assertEqual(result.mode, DELTA_RE_REVIEW)

    def test_self_review_resolves_mode_like_an_external_review(self) -> None:
        # current_reviewer == pr_author no longer short-circuits mode
        # resolution: with a prior self-review and a new HEAD this is a
        # delta re-review, not a skip.
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
        self.assertEqual(result.mode, DELTA_RE_REVIEW)

    def test_self_review_no_prior_review_is_normal_full_review(self) -> None:
        result = resolve_review_mode(
            ReviewModeInput(
                current_reviewer="alice",
                pr_author="alice",
                previous_review_exists=False,
            )
        )
        self.assertEqual(result.mode, NORMAL_FULL_REVIEW)


# --------------------------------------------------------------------------
# Analysis-vs-mutation eligibility split (Issue-#101 delta requirement 4/8)
# --------------------------------------------------------------------------
class AnalysisVsMutationEligibility(unittest.TestCase):
    def test_self_review_is_analysis_true_mutation_false(self) -> None:
        elig = raa.review_eligibility(_base(self_review=True))
        self.assertTrue(elig.analysis_allowed)
        self.assertFalse(elig.formal_review_mutation_allowed)

    def test_external_review_is_analysis_true_mutation_gate_open(self) -> None:
        elig = raa.review_eligibility(_base(reviewer_independence=_independent()))
        self.assertTrue(elig.analysis_allowed)
        self.assertTrue(elig.formal_review_mutation_allowed)

    def test_analysis_allowed_is_never_blocked_by_authorship(self) -> None:
        for kw in ({"self_review": True},
                   {"same_controlling_authority_as_author": True}):
            self.assertTrue(raa.analysis_allowed(_base(**kw)))

    def test_two_concerns_are_not_one_boolean(self) -> None:
        # ReviewEligibility exposes both, separately.
        fields = inspect.signature(raa.ReviewEligibility).parameters
        self.assertIn("analysis_allowed", fields)
        self.assertIn("formal_review_mutation_allowed", fields)


# --------------------------------------------------------------------------
# Self-review may publish an informational COMMENT, never a formal decision
# --------------------------------------------------------------------------
class SelfReviewInformationalComment(unittest.TestCase):
    def test_clean_self_review_publishes_comment_and_withholds_approve(self) -> None:
        out = raa.resolve_mutation_outcome(_base(self_review=True, verdict=raa.Verdict.CLEAN))
        self.assertTrue(out.published_comment)
        self.assertFalse(out.mutated)
        self.assertEqual(out.event, raa.GitHubEvent.NONE)
        self.assertEqual(out.verdict, raa.Verdict.CLEAN)

    def test_blocking_self_review_publishes_comment_and_withholds_request_changes(self) -> None:
        out = raa.resolve_mutation_outcome(_base(self_review=True, verdict=raa.Verdict.BLOCKING))
        self.assertTrue(out.published_comment)
        self.assertFalse(out.mutated)
        self.assertEqual(out.event, raa.GitHubEvent.NONE)
        self.assertEqual(out.verdict, raa.Verdict.BLOCKING)

    def test_comment_is_not_a_formal_event_and_does_not_unlock_one(self) -> None:
        # Even with an auto-action request + trusted authorization, a
        # self-review's COMMENT never becomes / accompanies APPROVE or
        # REQUEST_CHANGES.
        out = raa.resolve_mutation_outcome(_base(
            self_review=True,
            verdict=raa.Verdict.CLEAN,
            requested_mode=raa.ActionMode.EXPLICITLY_AUTHORIZED_AUTO_ACTION,
            authorization=_auth(raa.classify_provenance("human_principal_out_of_band")),
            reviewer_independence=_independent(),
        ))
        self.assertTrue(out.published_comment)
        self.assertNotIn(out.event, (raa.GitHubEvent.APPROVE, raa.GitHubEvent.REQUEST_CHANGES))
        self.assertFalse(out.mutated)

    def test_external_review_never_emits_the_self_review_comment(self) -> None:
        for kw in (
            {},  # recommendation-only default
            {"reviewer_independence": _independent()},
            {"reviewer_independence": _independent(),
             "requested_mode": raa.ActionMode.BLOCK_ONLY, "verdict": raa.Verdict.BLOCKING},
            {"reviewer_independence": _independent(),
             "requested_mode": raa.ActionMode.EXPLICITLY_AUTHORIZED_AUTO_ACTION,
             "authorization": _auth(raa.classify_provenance("human_principal_out_of_band"))},
            {"passive": True},
        ):
            out = raa.resolve_mutation_outcome(_base(**kw))
            self.assertFalse(out.published_comment, kw)


# --------------------------------------------------------------------------
# Merge boundary + governance sweeps
# --------------------------------------------------------------------------
class MergeBoundary(unittest.TestCase):
    def test_model_cannot_express_a_merge_event(self) -> None:
        self.assertEqual(
            {e.name for e in raa.GitHubEvent}, {"NONE", "APPROVE", "REQUEST_CHANGES"}
        )

    def test_a_submitted_approval_is_only_an_approve_event(self) -> None:
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
        self.assertNotIn("merge", repr(out).lower())


class AuthorizationScopeNoReplay(unittest.TestCase):
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

    def test_rejected_across_pr_head_repo_action(self) -> None:
        self.assertFalse(raa.authorization_covers(
            self.auth, repo=REPO, pr_number=PR + 1, head_sha=HEAD,
            action=raa.GitHubEvent.APPROVE))
        self.assertFalse(raa.authorization_covers(
            self.auth, repo=REPO, pr_number=PR, head_sha="advanced999",
            action=raa.GitHubEvent.APPROVE))
        self.assertFalse(raa.authorization_covers(
            self.auth, repo="evil/fork", pr_number=PR, head_sha=HEAD,
            action=raa.GitHubEvent.APPROVE))
        self.assertFalse(raa.authorization_covers(
            self.auth, repo=REPO, pr_number=PR, head_sha=HEAD,
            action=raa.GitHubEvent.REQUEST_CHANGES))

    def test_gate_rejects_authorization_scoped_to_another_pr(self) -> None:
        out = raa.resolve_mutation_outcome(
            _base(
                requested_mode=raa.ActionMode.EXPLICITLY_AUTHORIZED_AUTO_ACTION,
                authorization=_auth(
                    raa.classify_provenance("human_principal_out_of_band"), pr=999
                ),
                reviewer_independence=_independent(),
            )
        )
        self.assertFalse(out.mutated)
        self.assertIn("scope", out.withheld_reason)


class GovernanceSweeps(unittest.TestCase):
    def test_default_requested_mode_is_recommendation_only(self) -> None:
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

    def test_self_review_never_mutates_across_the_whole_input_space(self) -> None:
        for verdict in raa.Verdict:
            for rmode in raa.ActionMode:
                for prov in raa.Provenance:
                    for indep in raa.ReviewerIndependence:
                        for author_kw in ({"self_review": True},
                                          {"same_controlling_authority_as_author": True}):
                            out = raa.resolve_mutation_outcome(_base(
                                verdict=verdict, requested_mode=rmode,
                                authorization=_auth(prov),
                                reviewer_independence=indep, **author_kw,
                            ))
                            self.assertFalse(out.mutated)
                            self.assertEqual(out.event, raa.GitHubEvent.NONE)
                            self.assertTrue(out.published_comment)
                            self.assertIn("self-review", out.withheld_reason)
                            self.assertEqual(out.verdict, verdict)

    def test_approve_only_ever_with_auto_action_trusted_and_independent(self) -> None:
        for verdict in raa.Verdict:
            for rmode in raa.ActionMode:
                for prov in raa.Provenance:
                    for indep in raa.ReviewerIndependence:
                        out = raa.resolve_mutation_outcome(_base(
                            verdict=verdict, requested_mode=rmode,
                            authorization=_auth(prov), reviewer_independence=indep,
                        ))
                        if out.event is raa.GitHubEvent.APPROVE:
                            self.assertEqual(
                                out.mode,
                                raa.ActionMode.EXPLICITLY_AUTHORIZED_AUTO_ACTION,
                            )
                            self.assertEqual(verdict, raa.Verdict.CLEAN)
                            self.assertEqual(indep, raa.ReviewerIndependence.INDEPENDENT)
                            self.assertEqual(prov, raa.Provenance.INDEPENDENT_TRUSTED)

    def test_passive_review_never_mutates(self) -> None:
        for verdict in raa.Verdict:
            for rmode in raa.ActionMode:
                out = raa.resolve_mutation_outcome(_base(
                    passive=True, verdict=verdict, requested_mode=rmode,
                    authorization=_auth(raa.Provenance.INDEPENDENT_TRUSTED),
                    reviewer_independence=raa.ReviewerIndependence.INDEPENDENT,
                ))
                self.assertFalse(out.mutated)

    def test_every_agent_controlled_channel_is_untrusted(self) -> None:
        for channel in raa.AGENT_CONTROLLED_CHANNELS:
            self.assertEqual(
                raa.classify_provenance(channel), raa.Provenance.AGENT_CONTROLLED
            )

    def test_missing_channel_is_never_trusted(self) -> None:
        self.assertEqual(raa.classify_provenance(None), raa.Provenance.NONE)
        self.assertEqual(raa.classify_provenance(""), raa.Provenance.NONE)


if __name__ == "__main__":
    unittest.main()
