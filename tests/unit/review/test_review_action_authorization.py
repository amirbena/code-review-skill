#!/usr/bin/env python3
"""Regression coverage for the review-action authorization gate and the
self-review model, updated for issue #314's single canonical publication
mode (PASSIVE | SEMI | ACTIVE).

Mirrors skills/github-pr-review/policies/review-action-authorization.md,
skills/github-pr-review/policies/review-authority.md ("Self-review
capability"), and skills/github-pr-review/policies/review-output.md
("Review-action authorization gate").

Core invariant under test (issue #314): **an explicit ACTIVE request is
its own authorization.** When the caller explicitly requests ACTIVE
review, that request is, by itself, sufficient to publish the review's
own outcome — subject only to the existing self-review, reviewer-
independence, GitHub-permission, and HEAD-freshness rules, none of which
this delta weakens.

Run with:
    python3 -m unittest tests.unit.review.test_review_action_authorization
"""

from __future__ import annotations

import inspect
import unittest

from tests.reference.review import decision_semantics as ds
from tests.reference.review import review_action_authorization as raa
from tests.reference.review.reviewer_ownership import (
    DELTA_RE_REVIEW,
    NORMAL_FULL_REVIEW,
    ReviewModeInput,
    resolve_review_mode,
)

REPO = "octo/repo"
PR = 123
HEAD = "head000"


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


def _active(**kw) -> raa.ActionAuthorizationInput:
    return _base(
        requested_mode=raa.PublicationMode.ACTIVE,
        reviewer_independence=_independent(),
        **kw,
    )


# ==========================================================================
# Required #314 acceptance criteria
# ==========================================================================


class ActiveCleanApproves(unittest.TestCase):
    """active + clean -> APPROVE."""

    def test_active_clean_publishes_approve(self) -> None:
        out = raa.resolve_mutation_outcome(_active(verdict=raa.Verdict.CLEAN))
        self.assertTrue(out.mutated)
        self.assertEqual(out.event, raa.GitHubEvent.APPROVE)
        self.assertIsNone(out.withheld_reason)


class ActiveBlockingRequestsChanges(unittest.TestCase):
    """active + blocking -> REQUEST_CHANGES."""

    def test_active_blocking_publishes_request_changes(self) -> None:
        out = raa.resolve_mutation_outcome(_active(verdict=raa.Verdict.BLOCKING))
        self.assertTrue(out.mutated)
        self.assertEqual(out.event, raa.GitHubEvent.REQUEST_CHANGES)
        self.assertIsNone(out.withheld_reason)


class SemiCleanWouldApprove(unittest.TestCase):
    """semi + clean -> would publish APPROVE, no mutation."""

    def test_semi_clean_reports_would_publish_approve_without_mutating(self) -> None:
        inp = _base(
            verdict=raa.Verdict.CLEAN,
            requested_mode=raa.PublicationMode.SEMI,
            reviewer_independence=_independent(),
        )
        out = raa.resolve_mutation_outcome(inp)
        self.assertFalse(out.mutated)
        self.assertEqual(out.event, raa.GitHubEvent.NONE)
        self.assertEqual(out.would_publish, raa.GitHubEvent.APPROVE)


class SemiBlockingWouldRequestChanges(unittest.TestCase):
    """semi + blocking -> would publish REQUEST_CHANGES, no mutation."""

    def test_semi_blocking_reports_would_publish_request_changes_without_mutating(self) -> None:
        inp = _base(
            verdict=raa.Verdict.BLOCKING,
            requested_mode=raa.PublicationMode.SEMI,
            reviewer_independence=_independent(),
        )
        out = raa.resolve_mutation_outcome(inp)
        self.assertFalse(out.mutated)
        self.assertEqual(out.event, raa.GitHubEvent.NONE)
        self.assertEqual(out.would_publish, raa.GitHubEvent.REQUEST_CHANGES)


class PassiveNeverPublishes(unittest.TestCase):
    """passive -> no publication."""

    def test_passive_never_mutates_for_any_verdict(self) -> None:
        for verdict in raa.Verdict:
            out = raa.resolve_mutation_outcome(
                _base(
                    verdict=verdict,
                    requested_mode=raa.PublicationMode.PASSIVE,
                    reviewer_independence=_independent(),
                )
            )
            self.assertFalse(out.mutated, verdict)
            self.assertEqual(out.event, raa.GitHubEvent.NONE)
            self.assertEqual(out.would_publish, raa.GitHubEvent.NONE)
            self.assertFalse(out.published_comment)


class SelfReviewNoFormalEventAcrossModes(unittest.TestCase):
    """self-review + passive / semi / active -> no formal event."""

    def test_self_review_passive_no_formal_event(self) -> None:
        out = raa.resolve_mutation_outcome(
            _base(self_review=True, requested_mode=raa.PublicationMode.PASSIVE)
        )
        self.assertFalse(out.mutated)
        self.assertEqual(out.event, raa.GitHubEvent.NONE)
        self.assertFalse(out.published_comment)  # passive publishes nothing at all

    def test_self_review_semi_no_formal_event(self) -> None:
        out = raa.resolve_mutation_outcome(
            _base(
                self_review=True,
                requested_mode=raa.PublicationMode.SEMI,
                reviewer_independence=_independent(),
            )
        )
        self.assertFalse(out.mutated)
        self.assertEqual(out.event, raa.GitHubEvent.NONE)
        self.assertFalse(out.published_comment)  # semi never publishes anything

    def test_self_review_active_no_formal_event(self) -> None:
        out = raa.resolve_mutation_outcome(_active(self_review=True))
        self.assertFalse(out.mutated)
        self.assertEqual(out.event, raa.GitHubEvent.NONE)
        self.assertTrue(out.published_comment)  # active may still publish a COMMENT
        self.assertIn("self-review", out.withheld_reason)


class AuthorityBoundaryCannotExpand(unittest.TestCase):
    """active cannot edit source / apply patch / commit / push / merge /
    mutate repo settings.

    This policy authorizes review-publication outputs only (inline
    comments, review body, APPROVE/REQUEST_CHANGES/COMMENT). Nothing in
    the model exposes any of these other capabilities — this is enforced
    both by the absence of any such field/return value and by the
    canonical threat-model / authority-capability catalog (issues #298 /
    #301) that this policy defers to instead of re-deriving.
    """

    PROHIBITED_CAPABILITY_FRAGMENTS = (
        "edit_source",
        "edit_file",
        "apply_patch",
        "commit",
        "push",
        "merge",
        "repo_settings",
        "repository_settings",
        "delete_branch",
        "spawn_agent",
    )

    def test_mutation_outcome_exposes_no_such_capability(self) -> None:
        fields = {f for f in raa.MutationOutcome.__dataclass_fields__}
        for fragment in self.PROHIBITED_CAPABILITY_FRAGMENTS:
            self.assertNotIn(fragment, fields)

    def test_github_event_enum_has_no_merge_or_source_mutation_member(self) -> None:
        names = {e.name.lower() for e in raa.GitHubEvent}
        for fragment in self.PROHIBITED_CAPABILITY_FRAGMENTS:
            self.assertFalse(any(fragment in n for n in names), fragment)

    def test_no_public_signature_exposes_a_prohibited_capability(self) -> None:
        for name, obj in vars(raa).items():
            if not callable(obj) or name.startswith("_"):
                continue
            try:
                params = " ".join(inspect.signature(obj).parameters).lower()
            except (TypeError, ValueError):
                continue
            for fragment in self.PROHIBITED_CAPABILITY_FRAGMENTS:
                self.assertNotIn(
                    fragment, params, f"{name} exposes a prohibited capability: {fragment}"
                )

    def test_active_mode_never_yields_mutated_true_for_a_non_review_event(self) -> None:
        # The only two events ACTIVE can ever submit are APPROVE and
        # REQUEST_CHANGES -- both are review-publication outputs.
        for verdict in raa.Verdict:
            out = raa.resolve_mutation_outcome(_active(verdict=verdict))
            if out.mutated:
                self.assertIn(
                    out.event, (raa.GitHubEvent.APPROVE, raa.GitHubEvent.REQUEST_CHANGES)
                )


# ==========================================================================
# PR #297-style regression case (#314): explicit ACTIVE + REVIEW CLEAN +
# otherwise-permitted caller -> APPROVE published, no second phrase needed.
# ==========================================================================


class ActiveRequestIsSufficientAuthorization(unittest.TestCase):
    def test_explicit_active_clean_permitted_caller_approves_without_second_signal(self) -> None:
        # No authorization/provenance concept exists anywhere in this
        # input -- the model has no such field left to populate.
        inp = raa.ActionAuthorizationInput(
            verdict=raa.Verdict.CLEAN,
            repo=REPO,
            pr_number=PR,
            reviewed_head_sha=HEAD,
            current_head_sha=HEAD,
            requested_mode=raa.PublicationMode.ACTIVE,
            reviewer_independence=_independent(),
            permitted_events=frozenset({raa.GitHubEvent.APPROVE, raa.GitHubEvent.REQUEST_CHANGES}),
        )
        out = raa.resolve_mutation_outcome(inp)
        self.assertEqual(out.event, raa.GitHubEvent.APPROVE)
        self.assertTrue(out.mutated)
        self.assertIsNone(out.withheld_reason)

    def test_anti_regression_guard_clean_approve_never_withheld_for_missing_activation(self) -> None:
        # The exact broken state this issue forbids:
        #   REVIEW CLEAN / decision = APPROVE / mutation = WITHHELD
        #   because activation missing
        # must be unreachable for a fully-qualified ACTIVE invocation.
        out = raa.resolve_mutation_outcome(_active(verdict=raa.Verdict.CLEAN))
        self.assertEqual(out.verdict, raa.Verdict.CLEAN)
        self.assertEqual(out.event, raa.GitHubEvent.APPROVE)
        self.assertNotEqual(out.mode.name, "RECOMMENDATION_ONLY")  # legacy name is gone
        self.assertIsNone(out.withheld_reason)

    def test_model_has_no_authorization_or_provenance_concept_left(self) -> None:
        # These pre-#314 names must not exist anywhere in the module --
        # there is nothing left for a caller (or a stale test) to
        # withhold in isolation.
        for gone in ("Provenance", "MutationAuthorization", "AuthorizationScope",
                     "authorization_covers", "ActionMode", "classify_provenance"):
            self.assertFalse(hasattr(raa, gone), gone)


# --------------------------------------------------------------------------
# own PR + clean review -> analysis runs -> REVIEW CLEAN -> no APPROVE
# --------------------------------------------------------------------------
class OwnPrCleanReview(unittest.TestCase):
    def test_analysis_runs_verdict_clean_no_approve(self) -> None:
        inp = _base(self_review=True, verdict=raa.Verdict.CLEAN,
                    requested_mode=raa.PublicationMode.ACTIVE)
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
# own PR + P1 -> analysis runs -> CHANGES REQUIRED -> no formal REQUEST_CHANGES
# --------------------------------------------------------------------------
class OwnPrBlockingReview(unittest.TestCase):
    def test_analysis_runs_verdict_blocking_no_request_changes(self) -> None:
        inp = _base(self_review=True, verdict=raa.Verdict.BLOCKING,
                    requested_mode=raa.PublicationMode.ACTIVE)
        out = raa.resolve_mutation_outcome(inp)
        self.assertEqual(out.verdict, raa.Verdict.BLOCKING)  # not softened
        self.assertEqual(out.event, raa.GitHubEvent.NONE)  # no formal decision
        self.assertFalse(out.mutated)
        self.assertTrue(out.published_comment)  # informational COMMENT allowed
        self.assertIn("self-review", out.withheld_reason)


# --------------------------------------------------------------------------
# own PR + natural-language "approve if clean" -> approval still withheld
# --------------------------------------------------------------------------
class OwnPrNaturalLanguageApprove(unittest.TestCase):
    def test_nl_approve_if_clean_does_not_unlock_self_approval(self) -> None:
        requested = raa.normalize_intent("Review it; approve if clean.")
        self.assertEqual(requested, raa.PublicationMode.ACTIVE)
        inp = _base(
            self_review=True,
            verdict=raa.Verdict.CLEAN,
            requested_mode=requested,
            reviewer_independence=_independent(),
        )
        out = raa.resolve_mutation_outcome(inp)
        self.assertFalse(out.mutated)
        self.assertIn("self-review", out.withheld_reason)


# --------------------------------------------------------------------------
# own PR + alternate token/identity controlled by same authority -> analysis, no mutation
# --------------------------------------------------------------------------
class OwnPrManufacturedIndependence(unittest.TestCase):
    def test_controlled_alternate_identity_runs_analysis_but_never_mutates(self) -> None:
        inp = _base(
            same_controlling_authority_as_author=True,
            verdict=raa.Verdict.CLEAN,
            requested_mode=raa.PublicationMode.ACTIVE,
            reviewer_independence=_same_authority(),
        )
        self.assertTrue(raa.review_eligibility(inp).analysis_allowed)
        self.assertFalse(raa.review_eligibility(inp).formal_review_mutation_allowed)
        out = raa.resolve_mutation_outcome(inp)
        self.assertFalse(out.mutated)
        self.assertIn("self-review", out.withheld_reason)

    def test_is_self_review_covers_controlled_alternate_identity(self) -> None:
        self.assertTrue(
            raa.is_self_review(_base(same_controlling_authority_as_author=True))
        )


# --------------------------------------------------------------------------
# genuinely independent reviewer + clean + explicit ACTIVE request -> APPROVE
# --------------------------------------------------------------------------
class IndependentReviewerApprove(unittest.TestCase):
    def test_independent_clean_active_request_approves(self) -> None:
        inp = _active(verdict=raa.Verdict.CLEAN)
        self.assertTrue(raa.review_eligibility(inp).formal_review_mutation_allowed)
        out = raa.resolve_mutation_outcome(inp)
        self.assertTrue(out.mutated)
        self.assertEqual(out.event, raa.GitHubEvent.APPROVE)
        self.assertIsNone(out.withheld_reason)


# --------------------------------------------------------------------------
# genuinely independent reviewer + blocking + ACTIVE -> REQUEST_CHANGES
# --------------------------------------------------------------------------
class IndependentReviewerRequestChanges(unittest.TestCase):
    def test_independent_blocking_active_requests_changes(self) -> None:
        out = raa.resolve_mutation_outcome(_active(verdict=raa.Verdict.BLOCKING))
        self.assertTrue(out.mutated)
        self.assertEqual(out.event, raa.GitHubEvent.REQUEST_CHANGES)


# --------------------------------------------------------------------------
# independent reviewer, but PASSIVE requested -> REVIEW CLEAN still
# produced -> APPROVE not submitted (never requested)
# --------------------------------------------------------------------------
class IndependentReviewerNoActiveRequest(unittest.TestCase):
    def test_clean_verdict_produced_but_approve_not_submitted_without_active(self) -> None:
        inp = _base(verdict=raa.Verdict.CLEAN, reviewer_independence=_independent())
        out = raa.resolve_mutation_outcome(inp)
        self.assertEqual(out.verdict, raa.Verdict.CLEAN)
        self.assertFalse(out.mutated)
        self.assertEqual(out.mode, raa.PublicationMode.PASSIVE)


# --------------------------------------------------------------------------
# stale reviewed HEAD -> verdict reported -> mutation blocked
# --------------------------------------------------------------------------
class StaleHeadBlocksMutation(unittest.TestCase):
    def test_stale_head_reports_verdict_and_blocks_mutation(self) -> None:
        inp = _active(
            reviewed_head_sha="old111",
            current_head_sha="new222",
            verdict=raa.Verdict.CLEAN,
        )
        out = raa.resolve_mutation_outcome(inp)
        self.assertEqual(out.verdict, raa.Verdict.CLEAN)
        self.assertFalse(out.mutated)
        self.assertIn("stale", out.withheld_reason)


# --------------------------------------------------------------------------
# natural-language intent maps to internal behavior without mode keywords
# --------------------------------------------------------------------------
class NaturalLanguageIntentMapping(unittest.TestCase):
    def test_plain_review_request_is_passive(self) -> None:
        for phrase in ("Just review this PR.", "review it", "take a look at this PR"):
            self.assertEqual(raa.normalize_intent(phrase), raa.PublicationMode.PASSIVE)

    def test_dry_run_phrasing_is_semi(self) -> None:
        self.assertEqual(
            raa.normalize_intent("Review it and tell me what would happen, but don't touch GitHub."),
            raa.PublicationMode.SEMI,
        )

    def test_approve_if_clean_is_active(self) -> None:
        self.assertEqual(
            raa.normalize_intent(
                "Review it; approve if clean, request changes if there are blocking findings."
            ),
            raa.PublicationMode.ACTIVE,
        )

    def test_no_cli_keyword_syntax_is_required_or_recognised(self) -> None:
        for flagish in ("--active", "--semi", "--passive"):
            self.assertEqual(raa.normalize_intent(flagish), raa.PublicationMode.PASSIVE)

    def test_ambiguous_or_empty_intent_is_passive(self) -> None:
        for phrase in ("", None, "make it helpful", "do a good job"):
            self.assertEqual(raa.normalize_intent(phrase), raa.PublicationMode.PASSIVE)

    def test_requested_active_mode_is_immediately_effective(self) -> None:
        # #314: unlike the old "candidate" model, an ACTIVE request that
        # clears independence/permission/HEAD mutates immediately.
        inp = _base(
            verdict=raa.Verdict.CLEAN,
            requested_mode=raa.normalize_intent("approve if clean"),
            reviewer_independence=_independent(),
        )
        out = raa.resolve_mutation_outcome(inp)
        self.assertTrue(out.mutated)


# --------------------------------------------------------------------------
# unknown/ambiguous reviewer provenance -> analysis not blocked -> mutation fails closed
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
            requested_mode=raa.PublicationMode.ACTIVE,
            reviewer_independence=independence,
        )
        self.assertTrue(raa.analysis_allowed(inp))
        out = raa.resolve_mutation_outcome(inp)
        self.assertFalse(out.mutated)
        self.assertIn("independence", out.withheld_reason)


# --------------------------------------------------------------------------
# verdict derivation remains independent of the authorization gate
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
# delta re-review / reviewer-ownership semantics unchanged by this delta
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

    def test_external_review_is_analysis_true_mutation_gate_open_when_active(self) -> None:
        elig = raa.review_eligibility(_active())
        self.assertTrue(elig.analysis_allowed)
        self.assertTrue(elig.formal_review_mutation_allowed)

    def test_analysis_allowed_is_never_blocked_by_authorship(self) -> None:
        for kw in ({"self_review": True},
                   {"same_controlling_authority_as_author": True}):
            self.assertTrue(raa.analysis_allowed(_base(**kw)))

    def test_two_concerns_are_not_one_boolean(self) -> None:
        fields = inspect.signature(raa.ReviewEligibility).parameters
        self.assertIn("analysis_allowed", fields)
        self.assertIn("formal_review_mutation_allowed", fields)


# --------------------------------------------------------------------------
# Self-review may publish an informational COMMENT, never a formal decision
# --------------------------------------------------------------------------
class SelfReviewInformationalComment(unittest.TestCase):
    def test_clean_self_review_publishes_comment_and_withholds_approve(self) -> None:
        out = raa.resolve_mutation_outcome(
            _base(self_review=True, verdict=raa.Verdict.CLEAN,
                  requested_mode=raa.PublicationMode.ACTIVE)
        )
        self.assertTrue(out.published_comment)
        self.assertFalse(out.mutated)
        self.assertEqual(out.event, raa.GitHubEvent.NONE)
        self.assertEqual(out.verdict, raa.Verdict.CLEAN)

    def test_blocking_self_review_publishes_comment_and_withholds_request_changes(self) -> None:
        out = raa.resolve_mutation_outcome(
            _base(self_review=True, verdict=raa.Verdict.BLOCKING,
                  requested_mode=raa.PublicationMode.ACTIVE)
        )
        self.assertTrue(out.published_comment)
        self.assertFalse(out.mutated)
        self.assertEqual(out.event, raa.GitHubEvent.NONE)
        self.assertEqual(out.verdict, raa.Verdict.BLOCKING)

    def test_comment_is_not_a_formal_event_and_does_not_unlock_one(self) -> None:
        out = raa.resolve_mutation_outcome(_active(self_review=True, verdict=raa.Verdict.CLEAN))
        self.assertTrue(out.published_comment)
        self.assertNotIn(out.event, (raa.GitHubEvent.APPROVE, raa.GitHubEvent.REQUEST_CHANGES))
        self.assertFalse(out.mutated)

    def test_external_review_never_emits_the_self_review_comment(self) -> None:
        for kw in (
            {},  # passive default
            {"reviewer_independence": _independent()},
            {"reviewer_independence": _independent(),
             "requested_mode": raa.PublicationMode.ACTIVE, "verdict": raa.Verdict.BLOCKING},
            {"reviewer_independence": _independent(),
             "requested_mode": raa.PublicationMode.ACTIVE},
            {"requested_mode": raa.PublicationMode.PASSIVE},
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
        out = raa.resolve_mutation_outcome(_active())
        self.assertEqual(out.event, raa.GitHubEvent.APPROVE)
        self.assertNotIn("merge", repr(out).lower())


class GovernanceSweeps(unittest.TestCase):
    def test_default_requested_mode_is_passive(self) -> None:
        self.assertEqual(
            raa.ActionAuthorizationInput(
                verdict=raa.Verdict.CLEAN, repo=REPO, pr_number=PR,
                reviewed_head_sha=HEAD, current_head_sha=HEAD,
            ).requested_mode,
            raa.PublicationMode.PASSIVE,
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
            for rmode in raa.PublicationMode:
                for indep in raa.ReviewerIndependence:
                    for author_kw in ({"self_review": True},
                                      {"same_controlling_authority_as_author": True}):
                        out = raa.resolve_mutation_outcome(_base(
                            verdict=verdict, requested_mode=rmode,
                            reviewer_independence=indep, **author_kw,
                        ))
                        self.assertFalse(out.mutated)
                        self.assertEqual(out.event, raa.GitHubEvent.NONE)
                        self.assertEqual(out.verdict, verdict)
                        if rmode is raa.PublicationMode.ACTIVE:
                            self.assertTrue(out.published_comment)
                            self.assertIn("self-review", out.withheld_reason)
                        else:
                            self.assertFalse(out.published_comment)

    def test_approve_only_ever_with_active_mode_and_independence(self) -> None:
        for verdict in raa.Verdict:
            for rmode in raa.PublicationMode:
                for indep in raa.ReviewerIndependence:
                    out = raa.resolve_mutation_outcome(_base(
                        verdict=verdict, requested_mode=rmode, reviewer_independence=indep,
                    ))
                    if out.event is raa.GitHubEvent.APPROVE:
                        self.assertEqual(out.mode, raa.PublicationMode.ACTIVE)
                        self.assertEqual(verdict, raa.Verdict.CLEAN)
                        self.assertEqual(indep, raa.ReviewerIndependence.INDEPENDENT)

    def test_passive_review_never_mutates(self) -> None:
        for verdict in raa.Verdict:
            out = raa.resolve_mutation_outcome(_base(
                requested_mode=raa.PublicationMode.PASSIVE,
                verdict=verdict,
                reviewer_independence=raa.ReviewerIndependence.INDEPENDENT,
            ))
            self.assertFalse(out.mutated)

    def test_semi_review_never_mutates(self) -> None:
        for verdict in raa.Verdict:
            out = raa.resolve_mutation_outcome(_base(
                requested_mode=raa.PublicationMode.SEMI,
                verdict=verdict,
                reviewer_independence=raa.ReviewerIndependence.INDEPENDENT,
            ))
            self.assertFalse(out.mutated)


if __name__ == "__main__":
    unittest.main()
