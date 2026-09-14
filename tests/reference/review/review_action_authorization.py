#!/usr/bin/env python3
"""Test-only reference for the review-action authorization gate.

Mirrors skills/github-pr-review/policies/review-action-authorization.md
(and the enforcement point in
skills/github-pr-review/policies/review-output.md, "Review-action
authorization gate"). Not runtime logic, not packaged.

Issue #314 collapsed the pre-#314 two-switch model (a passive/active
review-type axis crossed with an independent `recommendation-only` /
`block-only` / `explicitly-authorized auto-action` "review-action mode"
that additionally required an out-of-band "trusted mutation
authorization" signal) into **one** canonical switch: `PublicationMode`
(`PASSIVE` | `SEMI` | `ACTIVE`).

Core invariant (issue #314): **an explicit ACTIVE request is its own
authorization.** When the caller explicitly requests `ACTIVE`, that
request is, by itself, sufficient to publish the review's own outcome —
no second activation phrase, approval prompt, or out-of-band
authorization channel is consulted. This is enforced by construction:
`resolve_mutation_outcome` never consults a `Provenance`/authorization
channel to decide whether an ACTIVE request may publish — there is no
`MutationAuthorization` concept (the pre-#314 bundling of a provenance
classification with a publication decision) left in this module for a
caller (or a stale test) to withhold in isolation. What *does* still gate
`ACTIVE` publication, unchanged from before #314:

* the **self-review boundary** — absolute; no formal event is ever
  submitted on the reviewer's own work, regardless of mode;
* **trusted reviewer independence** — authority separation, not just a
  different username;
* **GitHub event permission** — the authenticated identity must actually
  hold the capability to submit the desired event;
* **HEAD revalidation** — a stale reviewed HEAD is never approved.

The model deliberately keeps two concerns separate, exactly as the policy
does:

* whether **review analysis** may run (`analysis_allowed`) — authorship
  never blocks it;
* the review **verdict** (mechanically derived elsewhere from finding
  severities — see decision_semantics.py — and never an input to
  authority here, and never rewritten because mutation was withheld);

and one governing switch:

* the **publication mode** (`PASSIVE` | `SEMI` | `ACTIVE`) — the single,
  canonical answer to "should this review actually be published?"

Everything else fails closed: any unknown, ambiguous, or agent-controlled
input resolves to the safe, non-mutating outcome.

This module still exposes `Provenance` / `classify_provenance` /
`AGENT_CONTROLLED_CHANNELS` / `INDEPENDENT_TRUSTED_CHANNELS` /
`AuthorizationScope` as general-purpose channel-trust-classification and
scope-binding primitives -- they are not specific to review publication
and #314 does not remove them. shared/policies/agent-delegation.md and
tests/reference/review/agent_delegation.py reuse them unchanged for the
confused-deputy / single-use spawn-authorization boundary rather than
inventing a second identity model. What #314 removes is only their use
*here* as a second, independently-withholdable gate on publication
(`MutationAuthorization` / `authorization_covers`): `PublicationMode`
supersedes that role entirely, and `resolve_mutation_outcome` never takes
a `Provenance` or `AuthorizationScope` as input.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class PublicationMode(Enum):
    """The single canonical publication switch (issue #314).

    PASSIVE: active-review execution = False, publication = False.
    SEMI:    active-review execution = True,  publication = False.
    ACTIVE:  active-review execution = True,  publication = True.
    """

    PASSIVE = "passive"
    SEMI = "semi"
    ACTIVE = "active"

    @property
    def active_review_execution(self) -> bool:
        return self is not PublicationMode.PASSIVE

    @property
    def publication(self) -> bool:
        return self is PublicationMode.ACTIVE


class Verdict(Enum):
    CLEAN = "clean"
    BLOCKING = "blocking"  # a blocking review verdict, derived elsewhere


class GitHubEvent(Enum):
    NONE = "none"
    APPROVE = "APPROVE"
    REQUEST_CHANGES = "REQUEST_CHANGES"


class ReviewerIndependence(Enum):
    """Authority separation between the reviewer and the change's author."""

    SAME_AUTHORITY = "same_authority"  # different identity, same controlling authority
    AMBIGUOUS = "ambiguous"
    INDEPENDENT = "independent"  # authority originates outside the implementing agent


class Provenance(Enum):
    """Where a claimed authorization or identity signal came from.

    General-purpose channel-trust classification -- not specific to
    review publication (see module docstring). Reused unchanged by
    shared/policies/agent-delegation.md's confused-deputy check.
    """

    NONE = "none"  # nothing was supplied
    AGENT_CONTROLLED = "agent_controlled"  # reachable/forgeable by the review agent
    AMBIGUOUS = "ambiguous"  # cannot be classified with confidence
    INDEPENDENT_TRUSTED = "independent_trusted"  # out-of-band, principal-originated


# Channels the invoking / orchestrating agent can set, write, relay, or
# select. None of these can carry trusted authorization or identity
# (policy, "What can never establish it").
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
# the capability gated behind INDEPENDENT_TRUSTED.
INDEPENDENT_TRUSTED_CHANNELS: frozenset[str] = frozenset(
    {
        "human_principal_out_of_band",
        "runtime_verified_principal_authorization",
    }
)


def classify_provenance(channel: Optional[str]) -> Provenance:
    """Map an authorization-delivery channel name to its trust class.

    Unknown or missing channels are never trusted -- they fail closed to
    NONE / AMBIGUOUS, never to INDEPENDENT_TRUSTED.
    """
    if not channel:
        return Provenance.NONE
    if channel in AGENT_CONTROLLED_CHANNELS:
        return Provenance.AGENT_CONTROLLED
    if channel in INDEPENDENT_TRUSTED_CHANNELS:
        return Provenance.INDEPENDENT_TRUSTED
    return Provenance.AMBIGUOUS


@dataclass(frozen=True)
class AuthorizationScope:
    """The narrow binding of a relied-upon authorization (policy,
    "Authorization scope (no replay)"). General-purpose scope primitive;
    reused by shared/policies/agent-delegation.md for single-use
    spawn/delegation authorization rather than review-publication
    authorization."""

    repo: str
    pr_number: int
    head_sha: str
    action: "GitHubEvent"


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


# Natural-language intent -> canonical publication mode. Illustrative
# normalization, not a real NLP parser: it shows that users express
# behavior in ordinary language and never need a keyword or flag. An
# ACTIVE result is a real, effective request (issue #314's core
# invariant) -- it is not merely a "candidate" awaiting a second signal.
#
# "block it if there are serious issues, but don't approve it" and other
# block/request-changes phrasing are themselves an ACTIVE request -- the
# trailing "don't approve" is content-level scoping of *which* event an
# ACTIVE request publishes (see normalize_approval_declined), never a
# reason to fall back to PASSIVE. Dropping such a request to PASSIVE
# would silently withhold REQUEST_CHANGES too, which review-action-
# authorization.md, "Migration from the pre-#314 model" explicitly
# promises never happens.
def normalize_intent(text: Optional[str]) -> PublicationMode:
    if not text:
        return PublicationMode.PASSIVE
    t = text.lower()
    asks_active = (
        "approve if" in t
        or "approve it if" in t
        or "auto-approve" in t
        or "actively review" in t
        or "active review" in t
        or "request changes if" in t
        or "block it" in t
        or "block if" in t
    )
    asks_semi = (
        "don't touch github" in t
        or "do not touch github" in t
        or "without publishing" in t
        or "dry run" in t
        or "dry-run" in t
        or "what would happen" in t
        or "preview" in t
    )
    if asks_semi:
        return PublicationMode.SEMI
    if asks_active:
        return PublicationMode.ACTIVE
    # "just review this", "review it", anything ambiguous -> safe default.
    return PublicationMode.PASSIVE


# Natural-language "don't approve" scoping -> the one content-level
# option that survives from the old `block-only` phrasing (policy,
# "Migration from the pre-#314 model"). Independent of normalize_intent:
# it never introduces a new authorization channel or publication mode --
# it only ever suppresses the specific APPROVE event of an otherwise-
# qualifying ACTIVE request, exactly like ActionAuthorizationInput.
# approval_declined_by_caller documents. A caller combines this with
# normalize_intent's result the same way any other request detail is
# combined; on its own it never changes the requested mode.
def normalize_approval_declined(text: Optional[str]) -> bool:
    if not text:
        return False
    t = text.lower()
    return "don't approve" in t or "do not approve" in t or "never approve" in t


@dataclass(frozen=True)
class ActionAuthorizationInput:
    """Already-resolved facts for the gate.

    `requested_mode` is what the caller/agent asked for (normalized from
    natural language upstream). Everything else is a resolved fact from
    earlier gates (HEAD revalidation, GitHub event capability) plus the
    authorship / independence classification.

    `self_review` is true when the authenticated reviewer *is* the PR
    author. `same_controlling_authority_as_author` is true when the
    reviewer is a distinct identity (alternate account/token/bot/service
    account/GitHub App/nested agent/spawned process) that is nonetheless
    under the PR author's controlling authority. Either makes this a
    self-review for the mutation boundary; neither blocks analysis.

    `approval_declined_by_caller` is the one content-level scoping option
    that survives from the old `block-only` phrasing ("block it, but
    don't approve it"): it never introduces a new authorization channel,
    it only suppresses the specific APPROVE event when the caller
    explicitly asked not to see it, exactly the way a caller could ask to
    skip any other part of a request. See `normalize_approval_declined`
    for deriving it from natural language.
    """

    verdict: Verdict
    repo: str
    pr_number: int
    reviewed_head_sha: str
    current_head_sha: str
    self_review: bool = False
    same_controlling_authority_as_author: bool = False
    requested_mode: PublicationMode = PublicationMode.PASSIVE
    reviewer_independence: ReviewerIndependence = ReviewerIndependence.AMBIGUOUS
    permitted_events: frozenset[GitHubEvent] = field(default_factory=frozenset)
    approval_declined_by_caller: bool = False


@dataclass(frozen=True)
class ReviewEligibility:
    """The two concerns, kept explicitly separate."""

    analysis_allowed: bool
    formal_review_mutation_allowed: bool
    reason: str


@dataclass(frozen=True)
class MutationOutcome:
    mode: PublicationMode
    event: GitHubEvent  # the FORMAL review event submitted (NONE when withheld)
    verdict: Verdict  # unchanged, always reported
    withheld_reason: Optional[str] = None
    # SEMI only: the event ACTIVE would have submitted, never actually sent.
    would_publish: GitHubEvent = GitHubEvent.NONE
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
    review before analysis -- Agent review ownership, unresolved Jira
    context, incomplete scope -- are owned by other policies and are out
    of scope for this model.)"""
    return True


def review_eligibility(inp: ActionAuthorizationInput) -> ReviewEligibility:
    """Separate analysis eligibility from formal-mutation eligibility.

    A self-review: analysis_allowed = True, formal_review_mutation_allowed
    = False. An external review: analysis_allowed = True, and whether a
    formal event is actually submitted is then decided by
    resolve_mutation_outcome (mode + independence + permission + HEAD)."""
    if is_self_review(inp):
        return ReviewEligibility(
            analysis_allowed=True,
            formal_review_mutation_allowed=False,
            reason="self-review: reviewer is the PR author (or under the "
            "author's controlling authority); no formal review event on own work",
        )
    return ReviewEligibility(
        analysis_allowed=True,
        formal_review_mutation_allowed=inp.requested_mode is PublicationMode.ACTIVE,
        reason="external review: formal mutation subject to the ACTIVE "
        "publication mode plus independence/permission/HEAD",
    )


def _head_is_stale(inp: ActionAuthorizationInput) -> bool:
    return inp.reviewed_head_sha != inp.current_head_sha


def _desired_event(verdict: Verdict) -> GitHubEvent:
    return GitHubEvent.APPROVE if verdict is Verdict.CLEAN else GitHubEvent.REQUEST_CHANGES


def resolve_mutation_outcome(inp: ActionAuthorizationInput) -> MutationOutcome:
    """Decide whether a formal GitHub review event is submitted (ACTIVE),
    would be submitted (SEMI, reported but never sent), or is out of
    scope (PASSIVE). The verdict is computed elsewhere and only
    *reported* here -- it is never an input to authority, and never
    rewritten because the event was withheld.

    Core invariant (#314): for an ACTIVE, non-self-review invocation with
    independent reviewer, permitted event, and a current HEAD, the
    desired event is submitted -- there is no further "authorization"
    check beyond those already-required facts.
    """

    mode = inp.requested_mode
    desired = _desired_event(inp.verdict)

    def withheld(reason: str, **kw) -> MutationOutcome:
        return MutationOutcome(mode, GitHubEvent.NONE, inp.verdict, reason, **kw)

    # Self-review is absolute for the FORMAL decision, in every mode:
    # analysis already ran and produced the verdict above; no APPROVE /
    # REQUEST_CHANGES is ever submitted on own work, whatever the mode.
    # An ACTIVE self-review MAY still publish an informational COMMENT;
    # PASSIVE/SEMI publish nothing at all (they publish nothing for
    # anyone, self-review or not).
    if is_self_review(inp):
        comment = mode is PublicationMode.ACTIVE
        return MutationOutcome(
            mode,
            GitHubEvent.NONE,
            inp.verdict,
            "self-review: reviewer is the PR author; formal review decision "
            "withheld"
            + (" -- informational COMMENT only" if comment else ""),
            comment=comment,
        )

    if mode is PublicationMode.PASSIVE:
        return withheld("publication mode is PASSIVE")

    if mode is PublicationMode.SEMI:
        # A dry run: never submits anything, regardless of independence,
        # permission, or HEAD -- those are irrelevant to a non-publishing
        # preview, but the "would publish" event is still the exact one
        # ACTIVE would compute.
        return MutationOutcome(
            mode,
            GitHubEvent.NONE,
            inp.verdict,
            "SEMI mode: publication suppressed by design (dry run)",
            would_publish=desired,
        )

    # mode is ACTIVE, not a self-review: the core invariant applies,
    # subject only to the unchanged independence/permission/HEAD guards.
    if inp.reviewer_independence is not ReviewerIndependence.INDEPENDENT:
        return withheld("reviewer independence not established")

    if _head_is_stale(inp):
        return withheld("reviewed HEAD is stale; re-reviewing the new delta")

    if desired not in inp.permitted_events:
        return withheld(
            f"GitHub event permission not held by this identity ({desired.value})"
        )

    if desired is GitHubEvent.APPROVE and inp.approval_declined_by_caller:
        # Content-level scoping only (the old "block it, don't approve
        # it" phrasing) -- never a re-introduced authorization gate. It
        # only ever suppresses APPROVE; REQUEST_CHANGES is unaffected.
        return withheld("caller explicitly declined approval for this request")

    # No further gate: an explicit ACTIVE request, past self-review,
    # independence, permission, and HEAD, is its own authorization.
    return MutationOutcome(mode, desired, inp.verdict, None)


# Governance: fragments that, if they appeared in this module's public
# function signatures, would mean a caller-controlled escape hatch, or a
# reintroduced second authorization channel, crept in.
# test_review_action_authorization.py checks public signatures against
# these.
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
        "activation_phrase",
        "trusted_authorization",
        "mutation_authorization",
    }
)
