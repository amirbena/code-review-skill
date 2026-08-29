#!/usr/bin/env python3
"""Test-only reference for the review-action authorization gate.

Mirrors skills/github-pr-review/policies/review-action-authorization.md
(and the enforcement point in
skills/github-pr-review/policies/review-output.md, "Review-action
authorization gate"). Not runtime logic, not packaged.

The model deliberately keeps four concerns separate, exactly as the
policy does:

* whether **review analysis** may run (`analysis_allowed`) — authorship
  never blocks it;
* the review **verdict** (mechanically derived elsewhere from finding
  severities — see decision_semantics.py — and never an input to
  authority here, and never rewritten because mutation was withheld);
* the review-action **mode** (recommendation-only | block-only |
  explicitly-authorized auto-action) — an internal representation of
  requested behavior; users express intent in natural language;
* whether a formal GitHub **mutation** (APPROVE / REQUEST_CHANGES) may be
  submitted (`formal_review_mutation_allowed`).

Core invariant: **self-review is allowed; self-approval is not.** A
reviewer may analyze its own work, produce a verdict, and publish the
result as an informational GitHub COMMENT — but it never submits a formal
APPROVE or REQUEST_CHANGES on its own work, regardless of mode,
natural-language request, or any authorization. A COMMENT is an
informational publication, not a governance decision.

Everything else fails closed: any unknown, ambiguous, or agent-controlled
input resolves to the safe, non-mutating outcome.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ActionMode(Enum):
    RECOMMENDATION_ONLY = "recommendation-only"
    BLOCK_ONLY = "block-only"
    EXPLICITLY_AUTHORIZED_AUTO_ACTION = "explicitly-authorized-auto-action"


class Verdict(Enum):
    CLEAN = "clean"
    BLOCKING = "blocking"  # a blocking review verdict, derived elsewhere


class GitHubEvent(Enum):
    NONE = "none"
    APPROVE = "APPROVE"
    REQUEST_CHANGES = "REQUEST_CHANGES"


class Provenance(Enum):
    """Where a claimed mutation authorization came from."""

    NONE = "none"  # nothing was supplied
    AGENT_CONTROLLED = "agent_controlled"  # reachable/forgeable by the review agent
    AMBIGUOUS = "ambiguous"  # cannot be classified with confidence
    INDEPENDENT_TRUSTED = "independent_trusted"  # out-of-band, principal-originated


class ReviewerIndependence(Enum):
    """Authority separation between the reviewer and the change's author."""

    SAME_AUTHORITY = "same_authority"  # different identity, same controlling authority
    AMBIGUOUS = "ambiguous"
    INDEPENDENT = "independent"  # authority originates outside the implementing agent


# Channels the invoking / orchestrating agent can set, write, relay, or
# select. None of these can carry trusted authorization (policy,
# "What can never establish it").
AGENT_CONTROLLED_CHANNELS: frozenset[str] = frozenset(
    {
        "cli_flag",
        "action_mode_flag",
        "prompt_text",
        "generated_instruction",
        "approve_if_clean_text",
        "nested_skill_invocation",
        "nested_agent_instruction",
        "sub_agent",
        "spawned_process",
        "env_var",
        "config_file",
        "orchestration_metadata",
        "alternate_token",
        "alternate_username",
        "bot_identity",
        "service_account",
        "github_app_identity",
        "review_verdict",
        "prior_review_approval",
        "resolved_review_thread",
    }
)

# Channels that, by contract, originate outside the review-performing
# agent. A runtime that cannot furnish one of these simply never unlocks
# auto-action.
INDEPENDENT_TRUSTED_CHANNELS: frozenset[str] = frozenset(
    {
        "human_principal_out_of_band",
        "runtime_verified_principal_authorization",
    }
)


def classify_provenance(channel: Optional[str]) -> Provenance:
    """Map an authorization-delivery channel name to its trust class.

    Unknown or missing channels are never trusted — they fail closed to
    NONE / AMBIGUOUS, never to INDEPENDENT_TRUSTED.
    """
    if not channel:
        return Provenance.NONE
    if channel in AGENT_CONTROLLED_CHANNELS:
        return Provenance.AGENT_CONTROLLED
    if channel in INDEPENDENT_TRUSTED_CHANNELS:
        return Provenance.INDEPENDENT_TRUSTED
    return Provenance.AMBIGUOUS


def classify_reviewer_independence(
    *,
    reviewer_actor_selected_by_implementing_agent: bool,
    reviewer_provenance_known: bool,
) -> ReviewerIndependence:
    """Authority separation, not identity separation.

    A reviewer whose identity/credentials/instructions are controlled by
    the implementing or orchestrating agent is the *same authority* even
    with a different username. Unknown provenance fails closed.
    """
    if reviewer_actor_selected_by_implementing_agent:
        return ReviewerIndependence.SAME_AUTHORITY
    if not reviewer_provenance_known:
        return ReviewerIndependence.AMBIGUOUS
    return ReviewerIndependence.INDEPENDENT


# Natural-language intent → internal mode. Illustrative normalization,
# not a real NLP parser: it shows that users express behavior in ordinary
# language and never need a keyword or flag. The result is only a
# *requested* mode — it is not, by itself, trusted mutation authorization.
def normalize_intent(text: Optional[str]) -> ActionMode:
    if not text:
        return ActionMode.RECOMMENDATION_ONLY
    t = text.lower()
    asks_approve = ("approve if" in t) or ("approve it if" in t) or ("auto-approve" in t)
    forbids_approve = ("don't approve" in t) or ("do not approve" in t) or ("never approve" in t)
    asks_block = ("block it" in t) or ("request changes if" in t) or ("block if" in t)
    if asks_approve and not forbids_approve:
        return ActionMode.EXPLICITLY_AUTHORIZED_AUTO_ACTION  # a *candidate* only
    if asks_block or (forbids_approve and asks_block):
        return ActionMode.BLOCK_ONLY
    # "just review this", "review it", anything ambiguous → safe default.
    return ActionMode.RECOMMENDATION_ONLY


@dataclass(frozen=True)
class AuthorizationScope:
    """The narrow binding of a relied-upon authorization (policy,
    "Authorization scope (no replay)")."""

    repo: str
    pr_number: int
    head_sha: str
    action: GitHubEvent


@dataclass(frozen=True)
class MutationAuthorization:
    provenance: Provenance
    scope: Optional[AuthorizationScope] = None


def authorization_covers(
    auth: Optional[MutationAuthorization],
    *,
    repo: str,
    pr_number: int,
    head_sha: str,
    action: GitHubEvent,
) -> bool:
    """True only when a trusted authorization is scoped to exactly this
    repo / PR / reviewed HEAD / action. Any mismatch (a replay attempt
    for another PR, a stale or advanced HEAD, or a different action) is
    rejected."""
    if auth is None or auth.provenance is not Provenance.INDEPENDENT_TRUSTED:
        return False
    s = auth.scope
    if s is None:
        return False
    return (
        s.repo == repo
        and s.pr_number == pr_number
        and s.head_sha == head_sha
        and s.action == action
    )


@dataclass(frozen=True)
class ActionAuthorizationInput:
    """Already-resolved facts for the gate.

    `requested_mode` is what the caller/agent asked for (normalized from
    natural language upstream); it is only a *request* and never
    sufficient on its own. Everything else is a resolved fact from
    earlier gates (HEAD revalidation, GitHub event capability) plus the
    authorship / authorization / independence classification above.

    `self_review` is true when the authenticated reviewer *is* the PR
    author. `same_controlling_authority_as_author` is true when the
    reviewer is a distinct identity (alternate account/token/bot/service
    account/GitHub App/nested agent/spawned process) that is nonetheless
    under the PR author's controlling authority. Either makes this a
    self-review for the mutation boundary; neither blocks analysis.
    """

    verdict: Verdict
    repo: str
    pr_number: int
    reviewed_head_sha: str
    current_head_sha: str
    passive: bool = False
    self_review: bool = False
    same_controlling_authority_as_author: bool = False
    requested_mode: ActionMode = ActionMode.RECOMMENDATION_ONLY
    authorization: Optional[MutationAuthorization] = None
    reviewer_independence: ReviewerIndependence = ReviewerIndependence.AMBIGUOUS
    permitted_events: frozenset[GitHubEvent] = field(default_factory=frozenset)


@dataclass(frozen=True)
class ReviewEligibility:
    """The two concerns, kept explicitly separate."""

    analysis_allowed: bool
    formal_review_mutation_allowed: bool
    reason: str


@dataclass(frozen=True)
class MutationOutcome:
    mode: ActionMode
    event: GitHubEvent  # the FORMAL review event submitted (NONE when withheld)
    verdict: Verdict  # unchanged, always reported
    withheld_reason: Optional[str] = None
    # An informational GitHub review COMMENT publishing the result. This is
    # a publication, not a governance decision: it never counts as APPROVE,
    # REQUEST_CHANGES, or merge authorization, and does not set `mutated`.
    comment: bool = False

    @property
    def mutated(self) -> bool:
        """A FORMAL review decision was submitted (APPROVE / REQUEST_CHANGES)."""
        return self.event is not GitHubEvent.NONE

    @property
    def published_comment(self) -> bool:
        return self.comment


def is_self_review(inp: ActionAuthorizationInput) -> bool:
    """Authorship as a mutation boundary: identity match, or a distinct
    identity under the author's controlling authority."""
    return inp.self_review or inp.same_controlling_authority_as_author


def analysis_allowed(inp: ActionAuthorizationInput) -> bool:
    """Authorship never blocks analysis. (Concerns that *can* stop a
    review before analysis — Agent review ownership, unresolved Jira
    context, incomplete scope — are owned by other policies and are out
    of scope for this model.)"""
    return True


def review_eligibility(inp: ActionAuthorizationInput) -> ReviewEligibility:
    """Separate analysis eligibility from formal-mutation eligibility.

    A self-review: analysis_allowed = True, formal_review_mutation_allowed
    = False. An external review: analysis_allowed = True, and whether a
    formal event is actually submitted is then decided by
    resolve_mutation_outcome (mode + trusted authorization + independence
    + HEAD + permission)."""
    if is_self_review(inp):
        return ReviewEligibility(
            analysis_allowed=True,
            formal_review_mutation_allowed=False,
            reason="self-review: reviewer is the PR author (or under the "
            "author's controlling authority); no formal review event on own work",
        )
    return ReviewEligibility(
        analysis_allowed=True,
        formal_review_mutation_allowed=True,
        reason="external review: formal mutation subject to the authorization gate",
    )


def _head_is_stale(inp: ActionAuthorizationInput) -> bool:
    return inp.reviewed_head_sha != inp.current_head_sha


def resolve_action_mode(inp: ActionAuthorizationInput) -> ActionMode:
    """Resolve the effective mode. Safe default is RECOMMENDATION_ONLY;
    every ambiguity fails closed to it (or to BLOCK_ONLY only when
    independence is firmly established and the verdict is blocking)."""

    # Passive review and self-review are always non-mutating; the "mode"
    # is moot for them (no formal event is submitted regardless).
    if inp.passive or is_self_review(inp):
        return ActionMode.RECOMMENDATION_ONLY

    independent = inp.reviewer_independence is ReviewerIndependence.INDEPENDENT

    if inp.requested_mode is ActionMode.EXPLICITLY_AUTHORIZED_AUTO_ACTION:
        auth = inp.authorization
        trusted = auth is not None and auth.provenance is Provenance.INDEPENDENT_TRUSTED
        if trusted and independent:
            return ActionMode.EXPLICITLY_AUTHORIZED_AUTO_ACTION
        # Fall through: auto-action not established.
        if independent and inp.verdict is Verdict.BLOCKING:
            return ActionMode.BLOCK_ONLY
        return ActionMode.RECOMMENDATION_ONLY

    if inp.requested_mode is ActionMode.BLOCK_ONLY:
        return ActionMode.BLOCK_ONLY if independent else ActionMode.RECOMMENDATION_ONLY

    return ActionMode.RECOMMENDATION_ONLY


def resolve_mutation_outcome(inp: ActionAuthorizationInput) -> MutationOutcome:
    """Decide whether a formal GitHub review event is submitted. The
    verdict is computed elsewhere and only *reported* here — it is never
    an input to authority, and never rewritten because the event was
    withheld."""

    mode = resolve_action_mode(inp)
    desired = (
        GitHubEvent.APPROVE
        if inp.verdict is Verdict.CLEAN
        else GitHubEvent.REQUEST_CHANGES
    )

    def withheld(reason: str) -> MutationOutcome:
        return MutationOutcome(mode, GitHubEvent.NONE, inp.verdict, reason)

    # Self-review is absolute for the FORMAL decision: analysis already ran
    # and produced the verdict above; no APPROVE / REQUEST_CHANGES is ever
    # submitted on own work, whatever the mode, request, or authorization.
    # The result MAY still be published as an informational COMMENT.
    if is_self_review(inp):
        return MutationOutcome(
            mode,
            GitHubEvent.NONE,
            inp.verdict,
            "self-review: reviewer is the PR author; formal review decision "
            "withheld — informational COMMENT only",
            comment=True,
        )

    # A stronger request than recommendation-only requires established
    # reviewer independence before anything else — report that precisely
    # rather than as a generic "no authorization".
    if (
        inp.requested_mode is not ActionMode.RECOMMENDATION_ONLY
        and inp.reviewer_independence is not ReviewerIndependence.INDEPENDENT
    ):
        return withheld("reviewer independence not established")

    if mode is ActionMode.RECOMMENDATION_ONLY:
        return withheld(
            "no trusted mutation authorization; default recommendation-only"
        )

    if _head_is_stale(inp):
        return withheld("reviewed HEAD is stale; mutation not submitted")

    if desired not in inp.permitted_events:
        return withheld(f"GitHub event {desired.value} not permitted for this identity")

    if inp.reviewer_independence is not ReviewerIndependence.INDEPENDENT:
        return withheld("reviewer independence not established")

    if desired is GitHubEvent.REQUEST_CHANGES:
        # block-only and auto-action may both request changes; no
        # additional auto-action authorization is required because it
        # cannot approve or unblock.
        return MutationOutcome(mode, GitHubEvent.REQUEST_CHANGES, inp.verdict, None)

    # desired is APPROVE — the privileged, positive action.
    if mode is not ActionMode.EXPLICITLY_AUTHORIZED_AUTO_ACTION:
        return withheld("clean verdict without auto-action authorization; approval withheld")

    if not authorization_covers(
        inp.authorization,
        repo=inp.repo,
        pr_number=inp.pr_number,
        head_sha=inp.current_head_sha,
        action=GitHubEvent.APPROVE,
    ):
        return withheld("authorization scope does not match this repo/PR/HEAD/action")

    return MutationOutcome(mode, GitHubEvent.APPROVE, inp.verdict, None)


# Governance: fragments that, if they appeared in this module's public
# function signatures, would mean a caller-controlled escape hatch crept
# in (a flag that flips the gate open). test_review_action_authorization.py
# checks public signatures against these.
PROHIBITED_ESCAPE_HATCH_FRAGMENTS: frozenset[str] = frozenset(
    {
        "override",
        "force",
        "bypass",
        "skip_gate",
        "trust_caller",
        "assume_authorized",
        "allow_self_review",
        "disable_independence_check",
    }
)
