#!/usr/bin/env python3
"""Test-only reference for the exact-HEAD machine-readable review status.

Mirrors skills/github-pr-review/policies/review-status-enforcement.md.
Not runtime logic, not packaged.

Four concerns are kept separate, exactly as the policy does:

* the canonical **verdict** — mechanically derived elsewhere
  (decision_semantics.py) and only *mapped* here, never recomputed;
* whether a status may be **published**, split by direction: a blocking
  (non-success) status is blocking-only enforcement and may be published
  even by a self-review; a `success` status is positive/unblocking and
  needs the same trusted authorization + reviewer independence as a
  native APPROVE, and is never published by a self-review;
* **enforcement-state detection** — ENFORCED / NOT ENFORCED / UNKNOWN,
  read-only, from rulesets *and* classic branch protection;
* **required-check setup** — explicit, opt-in, minimal, preserving, and
  idempotent.

Everything ambiguous fails closed to "no success / no publication". This
module exposes no merge capability by construction.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from tests.reference import review_action_authorization as raa

# One stable aggregated context. Illustrative value; the policy only
# requires that it is a single stable identity.
STATUS_CONTEXT = "code-review/github-pr-review"


class Reasoning(Enum):
    """The reasoning results this gate maps from (a subset of
    review-output.md, "Final decision")."""

    CLEAN = "REVIEW CLEAN"
    CHANGES_REQUIRED = "CHANGES REQUIRED"
    INCOMPLETE = "REVIEW INCOMPLETE"
    JIRA_UNRESOLVED = "JIRA CONTEXT UNRESOLVED"
    CONTEXT_UNAVAILABLE = "REPOSITORY CONTEXT UNAVAILABLE"
    NO_NEW_DELTA = "NO NEW DELTA"


class StatusState(Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    NONE = "none"  # nothing to publish (NO NEW DELTA)


# Reasoning results that are a complete, current-HEAD clean verdict.
_CLEAN = frozenset({Reasoning.CLEAN})
# Reasoning results that must never publish success but do warrant a
# blocking status (a red gate is the safe, honest signal).
_NON_GREEN = frozenset(
    {
        Reasoning.CHANGES_REQUIRED,
        Reasoning.INCOMPLETE,
        Reasoning.JIRA_UNRESOLVED,
        Reasoning.CONTEXT_UNAVAILABLE,
    }
)


class EnforcementState(Enum):
    ENFORCED = "ENFORCED"
    NOT_ENFORCED = "NOT ENFORCED"
    UNKNOWN = "UNKNOWN"


def map_verdict_to_status(reasoning: Reasoning) -> StatusState:
    """Canonical verdict → intended status state. No second severity or
    verdict path: this only re-expresses an already-derived result.

    A clean, complete, current-HEAD verdict is a *candidate* success
    (publication is still gated). Every non-green reasoning result maps to
    FAILURE — never SUCCESS. NO NEW DELTA maps to NONE (the existing
    SHA-bound status already belongs to the current HEAD).
    """
    if reasoning in _CLEAN:
        return StatusState.SUCCESS
    if reasoning is Reasoning.NO_NEW_DELTA:
        return StatusState.NONE
    return StatusState.FAILURE


@dataclass(frozen=True)
class StatusPublicationInput:
    """Already-resolved facts for the status-publication gate.

    `reasoning` is the canonical verdict computed upstream. `authorization`
    / `reviewer_independence` / `requested_mode` / `self_review` /
    `same_controlling_authority_as_author` reuse
    review_action_authorization.py exactly — a `success` status is the
    APPROVE-equivalent positive action.
    """

    reasoning: Reasoning
    repo: str
    pr_number: int
    reviewed_head_sha: str
    current_head_sha: str
    status_write_permitted: bool = True
    is_parallel_worker: bool = False
    self_review: bool = False
    same_controlling_authority_as_author: bool = False
    requested_mode: raa.ActionMode = raa.ActionMode.RECOMMENDATION_ONLY
    authorization: Optional[raa.MutationAuthorization] = None
    reviewer_independence: raa.ReviewerIndependence = (
        raa.ReviewerIndependence.AMBIGUOUS
    )


@dataclass(frozen=True)
class StatusPublication:
    context: str
    target_sha: str
    intended_state: StatusState
    published: bool
    published_state: StatusState
    withheld_reason: Optional[str] = None

    @property
    def merged(self) -> bool:  # pragma: no cover - always False, by construction
        return False


def _is_self_review(inp: StatusPublicationInput) -> bool:
    return inp.self_review or inp.same_controlling_authority_as_author


def _head_is_stale(inp: StatusPublicationInput) -> bool:
    return inp.reviewed_head_sha != inp.current_head_sha


def _success_authorized(inp: StatusPublicationInput) -> bool:
    """A `success` status is the APPROVE-equivalent positive action: it
    needs auto-action mode established by trusted, scope-bound
    authorization AND established reviewer independence. A self-review can
    never reach here."""
    if _is_self_review(inp):
        return False
    if inp.reviewer_independence is not raa.ReviewerIndependence.INDEPENDENT:
        return False
    if inp.requested_mode is not raa.ActionMode.EXPLICITLY_AUTHORIZED_AUTO_ACTION:
        return False
    return raa.authorization_covers(
        inp.authorization,
        repo=inp.repo,
        pr_number=inp.pr_number,
        head_sha=inp.current_head_sha,
        action=raa.GitHubEvent.APPROVE,
    )


def resolve_status_publication(inp: StatusPublicationInput) -> StatusPublication:
    """Decide whether the one aggregated status is published, and in which
    state. Fails closed: any doubt → no success (a blocking status, or no
    publication)."""

    intended = map_verdict_to_status(inp.reasoning)

    def withheld(reason: str, *, state: StatusState = StatusState.NONE) -> StatusPublication:
        return StatusPublication(
            context=STATUS_CONTEXT,
            target_sha=inp.reviewed_head_sha,
            intended_state=intended,
            published=False,
            published_state=state,
            withheld_reason=reason,
        )

    def published(state: StatusState) -> StatusPublication:
        return StatusPublication(
            context=STATUS_CONTEXT,
            target_sha=inp.reviewed_head_sha,
            intended_state=intended,
            published=True,
            published_state=state,
            withheld_reason=None,
        )

    # Only the authoritative aggregator publishes the required status.
    if inp.is_parallel_worker:
        return withheld("parallel worker cannot publish the aggregated status")

    # Nothing to publish for NO NEW DELTA — the existing SHA-bound status
    # already belongs to the current HEAD.
    if intended is StatusState.NONE:
        return withheld("no new delta; existing status already covers this HEAD")

    # A status on SHA A must never be retargeted onto a newer SHA.
    if _head_is_stale(inp):
        return withheld("HEAD advanced; status not published")

    if not inp.status_write_permitted:
        return withheld("no GitHub status write capability")

    # Blocking (non-success) status: blocking-only enforcement. Permitted
    # even for a self-review — it can only make the gate stricter.
    if intended is StatusState.FAILURE:
        return published(StatusState.FAILURE)

    # intended is SUCCESS — the positive, unblocking action.
    if _is_self_review(inp):
        return withheld("self-review: success not published", state=StatusState.NONE)
    if not _success_authorized(inp):
        return withheld(
            "success requires trusted positive authorization and reviewer independence",
            state=StatusState.NONE,
        )
    return published(StatusState.SUCCESS)


# --- Enforcement-state detection --------------------------------------


@dataclass(frozen=True)
class BranchEnforcementConfig:
    """What a read of the base branch's protection returned.

    `readable` is False when neither rulesets nor classic branch
    protection could be read (permission / API failure) — that is UNKNOWN,
    never NOT ENFORCED.
    """

    readable: bool
    ruleset_required_contexts: frozenset[str] = frozenset()
    classic_required_contexts: frozenset[str] = frozenset()


def detect_enforcement(
    config: BranchEnforcementConfig, *, context: str = STATUS_CONTEXT
) -> EnforcementState:
    if not config.readable:
        return EnforcementState.UNKNOWN
    required = config.ruleset_required_contexts | config.classic_required_contexts
    if context in required:
        return EnforcementState.ENFORCED
    return EnforcementState.NOT_ENFORCED


# --- Explicit opt-in required-check setup ----------------------------


@dataclass(frozen=True)
class RequiredCheckConfig:
    """Normalized, complete base-branch configuration relevant to setup.

    Every field other than `required_contexts` is passthrough state the
    setup must preserve untouched.
    """

    readable: bool
    required_contexts: frozenset[str]
    bypass_actors: tuple[str, ...] = ()
    approving_review_count: int = 0
    dismiss_stale_reviews_on_push: bool = False
    require_last_push_approval: bool = False
    other_rules: tuple[str, ...] = ()


@dataclass(frozen=True)
class SetupPlan:
    apply: bool
    noop: bool
    resulting_contexts: frozenset[str]
    preserved: bool
    withheld_reason: Optional[str] = None


def plan_required_check_setup(
    current: RequiredCheckConfig,
    *,
    context: str = STATUS_CONTEXT,
    explicit_request: bool,
    authorization: Optional[raa.MutationAuthorization] = None,
    repo: str,
    pr_number: int,
    head_sha: str,
    reviewer_independence: raa.ReviewerIndependence = raa.ReviewerIndependence.AMBIGUOUS,
) -> SetupPlan:
    """Plan the minimal, preserving, idempotent addition of `context` to
    the base branch's required checks. Never performed during an ordinary
    review; gated by the same trusted authorization as a `success`
    status."""

    unchanged = frozenset(current.required_contexts)

    def withheld(reason: str) -> SetupPlan:
        return SetupPlan(
            apply=False,
            noop=False,
            resulting_contexts=unchanged,
            preserved=True,
            withheld_reason=reason,
        )

    if not explicit_request:
        return withheld("setup is explicit and opt-in; not performed during review")

    if not current.readable:
        return withheld("current configuration could not be read; no mutation")

    # Same bar as publishing a success status.
    authorized = (
        reviewer_independence is raa.ReviewerIndependence.INDEPENDENT
        and raa.authorization_covers(
            authorization,
            repo=repo,
            pr_number=pr_number,
            head_sha=head_sha,
            action=raa.GitHubEvent.APPROVE,
        )
    )
    if not authorized:
        return withheld("setup requires trusted positive authorization and reviewer independence")

    if context in current.required_contexts:
        return SetupPlan(
            apply=False,
            noop=True,
            resulting_contexts=unchanged,
            preserved=True,
            withheld_reason=None,
        )

    resulting = unchanged | {context}
    return SetupPlan(
        apply=True,
        noop=False,
        resulting_contexts=resulting,
        # Minimal change: every prior required check is still present, and
        # only `context` was added.
        preserved=unchanged <= resulting and (resulting - unchanged) == {context},
        withheld_reason=None,
    )


def verify_required_check_setup(
    before: RequiredCheckConfig,
    after: RequiredCheckConfig,
    *,
    context: str = STATUS_CONTEXT,
) -> bool:
    """Read-back verification: the context is now required, every prior
    required check survived, and none of the passthrough governance state
    changed."""
    return (
        context in after.required_contexts
        and frozenset(before.required_contexts) <= frozenset(after.required_contexts)
        and before.bypass_actors == after.bypass_actors
        and before.approving_review_count == after.approving_review_count
        and before.dismiss_stale_reviews_on_push == after.dismiss_stale_reviews_on_push
        and before.require_last_push_approval == after.require_last_push_approval
        and before.other_rules == after.other_rules
    )


# Governance: name fragments that, if they appeared in this module's
# public function signatures, would mean an escape hatch crept in — a
# caller-controlled flag that publishes green anyway, merges, or edits
# unrelated governance. test_review_status_enforcement.py checks public
# signatures against these.
PROHIBITED_ESCAPE_HATCH_FRAGMENTS: frozenset[str] = frozenset(
    {
        "override",
        "force",
        "bypass_check",
        "skip_gate",
        "assume_authorized",
        "allow_self_review_success",
        "merge",
        "auto_merge",
        "set_approval_count",
        "set_dismiss_stale",
        "set_require_last_push",
        "modify_bypass_actors",
        "replace_required_checks",
    }
)
