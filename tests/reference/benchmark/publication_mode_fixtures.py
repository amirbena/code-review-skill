#!/usr/bin/env python3
"""Test-only reference fixtures for the passive/semi/active publication-mode
benchmark corpus (Issue #316, depends on #314:
skills/github-pr-review/policies/review-action-authorization.md).

Issue #314 collapsed `github-pr-review`'s publication semantics into one
canonical switch -- `PASSIVE` | `SEMI` | `ACTIVE`
(`tests/reference/review/review_action_authorization.py`, `raa` below) --
and its own unit suite (`tests/unit/review/test_review_action_authorization.py`)
already proves that resolver mechanically, including a PR #297-style
regression test (`ActiveRequestIsSufficientAuthorization`). This module is
deliberately **not** a duplicate of that suite: it is the declarative,
metadata-bearing **benchmark** layer #316 asks for, proving something that
suite does not -- that the *GitHub-bound publication artifact itself*
(the object `github-pr-review` would actually hand to GitHub: one review
submission of `body + inline comments + event`, per
`skills/github-pr-review/policies/review-output.md`, "Batched review
construction and submission") is emitted, or not emitted, exactly as the
mode requires. A caller-facing sentence saying nothing was posted is not
evidence (#316's "Publication-artifact verification" requirement); this
corpus inspects the artifact's own structure instead.

Like `delegation_fixtures.py` and `reviewer_brief_fixtures.py`, this
boundary has no representation in the `benchmark-case/v1` schema
(`docs/benchmark/fixture-format.md`): that schema's `expected` block is a
patch plus expected review findings, with no field for a publication mode,
a "would publish" preview, or a GitHub-bound artifact's shape. Rather than
stretch that closed schema, this module follows the same test-only,
data-driven reference-fixture pattern, documented in
`docs/benchmark/corpus/publication-mode/README.md`.

Evaluation style (docs/benchmark/README.md convention): every comparison
here is a deterministic structural assertion -- resolved mode, formal
event, "would publish" event, and the emitted (or absent) publication
artifact's own fields -- never an LLM/rubric score. This corpus is
disjoint from the finding-precision/recall/severity metrics (#41) and from
every other domain corpus; it never touches a finding's content, only
publication-boundary structure. The one exception is the natural-language
"invocation phrasing robustness" category, which reuses `raa`'s own
`normalize_intent` -- an illustrative, non-NLP normalizer already labeled
as such in that module -- exactly as documented in
`review-action-authorization.md`, "Natural-language publication intent";
this module invents no new phrasing beyond that policy's own canonical
examples plus their close synonyms, and it is not a general NL-parser
benchmark (#316 non-goal).
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Callable, Optional

from tests.reference.review import review_action_authorization as raa

# ---------------------------------------------------------------------------
# Case taxonomy
# ---------------------------------------------------------------------------

CATEGORY_PASSIVE = "passive"
CATEGORY_SEMI = "semi"
CATEGORY_ACTIVE = "active"
CATEGORY_REGRESSION_297 = "regression_297"
CATEGORY_MODE_INVARIANT = "mode_invariant"
CATEGORY_SELF_REVIEW = "self_review"
CATEGORY_AUTHORITY_BOUNDARY = "authority_boundary"
CATEGORY_PHRASING = "phrasing"

VALID_CATEGORIES: frozenset[str] = frozenset(
    {
        CATEGORY_PASSIVE,
        CATEGORY_SEMI,
        CATEGORY_ACTIVE,
        CATEGORY_REGRESSION_297,
        CATEGORY_MODE_INVARIANT,
        CATEGORY_SELF_REVIEW,
        CATEGORY_AUTHORITY_BOUNDARY,
        CATEGORY_PHRASING,
    }
)

# The GitHub-bound outputs review-action-authorization.md, "Authority
# boundary" explicitly says publication authority is scoped to -- and
# nothing else. Mirrors review-output.md's "one GitHub review submission
# (body + inline comments + event)" shape.
GITHUB_PUBLICATION_CAPABILITIES: frozenset[str] = frozenset(
    {
        "inline_review_comment",
        "consolidated_review_body",
        "approve_event",
        "request_changes_event",
        "informational_comment_event",
    }
)

# Fragments naming a capability review-action-authorization.md's "Authority
# boundary" section explicitly says an ACTIVE publication must never gain --
# reused verbatim from that policy's own enumerated list (file
# modification/patch application, commit, push, merge, repository settings,
# unrelated issue/PR mutation, runtime sandbox capability, agent spawning),
# in the same spelling test_review_action_authorization.py's own
# `PROHIBITED_CAPABILITY_FRAGMENTS` already checks against the resolver.
# This module checks the same fragments against the constructed
# *publication artifact* instead -- a distinct surface that suite does not
# cover.
PROHIBITED_UNRELATED_MUTATION_FRAGMENTS: "tuple[str, ...]" = (
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
    "issue_mutation",
    "unrelated_pr",
    "sandbox",
)


class PublicationModeFixtureError(ValueError):
    """A publication-mode benchmark fixture is malformed."""


# ---------------------------------------------------------------------------
# The GitHub-bound publication artifact
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GithubPublicationArtifact:
    """The single GitHub-bound object `github-pr-review` would actually
    submit for one invocation -- mirrors review-output.md, "Batched review
    construction and submission" (`kind="formal_review"`: one review
    submission of `body` + `inline_comments` + `event`) or the self-review
    informational exception (`kind="informational_comment"`: `review-output.md`,
    "Review-action authorization gate" -- a `COMMENT` that carries no event
    and, being an informational note rather than a batched review, no
    inline comments). Deliberately has no field for anything outside
    `GITHUB_PUBLICATION_CAPABILITIES` -- see `ArtifactAuthorityBoundary`
    in the corpus test module, which checks this by construction.
    """

    kind: str  # "formal_review" | "informational_comment"
    event: raa.GitHubEvent
    body: str
    inline_comments: "tuple[str, ...]"


def emit_publication_artifact(
    outcome: raa.MutationOutcome,
    findings: "tuple[str, ...]" = ("Example finding",),
) -> Optional[GithubPublicationArtifact]:
    """The real decision point this corpus benchmarks: does *any*
    GitHub-bound artifact reach the publication boundary, and if so, which
    kind? `PASSIVE` and a withheld `SEMI`/`ACTIVE` outcome return `None` --
    literally nothing is constructed, not merely "nothing reported" to the
    caller. A submitted formal event returns the one-review-submission
    artifact; a self-review `ACTIVE` informational `COMMENT` returns the
    narrower informational artifact. Never derives from anything but the
    already-resolved `MutationOutcome` -- this function adds no second
    authorization decision.
    """
    if outcome.mutated:
        return GithubPublicationArtifact(
            kind="formal_review",
            event=outcome.event,
            body=f"## Review Summary\n\nVerdict: {outcome.verdict.value}\nEvent: {outcome.event.value}",
            inline_comments=tuple(findings) if outcome.verdict is raa.Verdict.BLOCKING else (),
        )
    if outcome.comment:
        return GithubPublicationArtifact(
            kind="informational_comment",
            event=raa.GitHubEvent.NONE,
            body=(
                "## Review Summary (informational)\n\n"
                f"Verdict: {outcome.verdict.value}\n"
                f"Formal decision withheld: {outcome.withheld_reason}"
            ),
            inline_comments=(),
        )
    return None


# ---------------------------------------------------------------------------
# Case + observation shapes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Observed:
    """What actually happened when a case's `run()` executed against the
    single reference model (plus `emit_publication_artifact` for the
    artifact-level checks)."""

    resolved_mode: raa.PublicationMode
    event: raa.GitHubEvent = raa.GitHubEvent.NONE
    verdict: Optional[raa.Verdict] = None
    withheld_reason: Optional[str] = None
    would_publish: raa.GitHubEvent = raa.GitHubEvent.NONE
    artifact: Optional[GithubPublicationArtifact] = None


@dataclass(frozen=True)
class PublicationModeCase:
    """One benchmark case for the passive/semi/active publication-mode
    boundary. `run()` is a zero-argument callable exercising the single
    reference model and returning the decisive `Observed`; every other
    field is declarative metadata validated independently of execution."""

    case_id: str
    category: str
    covers: "frozenset[str]"
    description: str
    run: "Callable[[], Observed]"
    expected_resolved_mode: raa.PublicationMode
    expected_event: raa.GitHubEvent = raa.GitHubEvent.NONE
    expected_would_publish: raa.GitHubEvent = raa.GitHubEvent.NONE
    expected_artifact_emitted: bool = False
    expected_artifact_kind: Optional[str] = None
    notes: str = ""


def validate_case(case: PublicationModeCase) -> None:
    """Fail-closed structural validation of one fixture's *data* --
    independent of running it."""
    if not isinstance(case.case_id, str) or not case.case_id.strip():
        raise PublicationModeFixtureError("case_id must be a non-empty string")
    if case.category not in VALID_CATEGORIES:
        raise PublicationModeFixtureError(
            f"{case.case_id}: category {case.category!r} not in {sorted(VALID_CATEGORIES)}"
        )
    if not isinstance(case.covers, frozenset) or not all(isinstance(t, str) for t in case.covers):
        raise PublicationModeFixtureError(f"{case.case_id}: covers must be a frozenset[str]")
    if not isinstance(case.description, str) or not case.description.strip():
        raise PublicationModeFixtureError(f"{case.case_id}: description must be a non-empty string")
    if not callable(case.run):
        raise PublicationModeFixtureError(f"{case.case_id}: run must be callable")
    if not isinstance(case.expected_resolved_mode, raa.PublicationMode):
        raise PublicationModeFixtureError(f"{case.case_id}: expected_resolved_mode must be a PublicationMode")
    if not isinstance(case.expected_event, raa.GitHubEvent):
        raise PublicationModeFixtureError(f"{case.case_id}: expected_event must be a GitHubEvent")
    if not isinstance(case.expected_would_publish, raa.GitHubEvent):
        raise PublicationModeFixtureError(f"{case.case_id}: expected_would_publish must be a GitHubEvent")
    if case.expected_artifact_emitted and case.expected_artifact_kind not in ("formal_review", "informational_comment"):
        raise PublicationModeFixtureError(
            f"{case.case_id}: an artifact-emitting case must state a valid expected_artifact_kind"
        )
    if not case.expected_artifact_emitted and case.expected_artifact_kind is not None:
        raise PublicationModeFixtureError(
            f"{case.case_id}: expected_artifact_kind must be unset when no artifact is expected"
        )


def validate_corpus(cases: "tuple[PublicationModeCase, ...]") -> None:
    """Corpus-wide structural checks: every case validates individually,
    case_ids are unique, and no category is left empty."""
    if not cases:
        raise PublicationModeFixtureError("corpus must not be empty")
    seen: "set[str]" = set()
    for case in cases:
        validate_case(case)
        if case.case_id in seen:
            raise PublicationModeFixtureError(f"duplicate case_id {case.case_id!r}")
        seen.add(case.case_id)


def cases_covering(tag: str) -> "tuple[PublicationModeCase, ...]":
    return tuple(case for case in ALL_CASES if tag in case.covers)


def cases_in_category(category: str) -> "tuple[PublicationModeCase, ...]":
    return tuple(case for case in ALL_CASES if case.category == category)


def cases_where(predicate: "Callable[[PublicationModeCase], bool]") -> "tuple[PublicationModeCase, ...]":
    return tuple(case for case in ALL_CASES if predicate(case))


# ---------------------------------------------------------------------------
# Shared input construction
# ---------------------------------------------------------------------------

REPO = "acme/widgets"
PR_NUMBER = 42
HEAD_SHA = "a" * 40
STALE_HEAD_SHA = "b" * 40

_BOTH_EVENTS: "frozenset[raa.GitHubEvent]" = frozenset({raa.GitHubEvent.APPROVE, raa.GitHubEvent.REQUEST_CHANGES})


def _input(
    *,
    verdict: raa.Verdict = raa.Verdict.CLEAN,
    mode: raa.PublicationMode = raa.PublicationMode.PASSIVE,
    self_review: bool = False,
    same_controlling_authority: bool = False,
    independence: raa.ReviewerIndependence = raa.ReviewerIndependence.INDEPENDENT,
    permitted: "frozenset[raa.GitHubEvent]" = _BOTH_EVENTS,
    reviewed_head: str = HEAD_SHA,
    current_head: str = HEAD_SHA,
    approval_declined: bool = False,
) -> raa.ActionAuthorizationInput:
    """A caller who is otherwise allowed to publish: independent reviewer,
    both events permitted, current HEAD -- unless a specific case overrides
    one of these to exercise a different gate."""
    return raa.ActionAuthorizationInput(
        verdict=verdict,
        repo=REPO,
        pr_number=PR_NUMBER,
        reviewed_head_sha=reviewed_head,
        current_head_sha=current_head,
        self_review=self_review,
        same_controlling_authority_as_author=same_controlling_authority,
        requested_mode=mode,
        reviewer_independence=independence,
        permitted_events=permitted,
        approval_declined_by_caller=approval_declined,
    )


def _observe(inp: raa.ActionAuthorizationInput) -> Observed:
    outcome = raa.resolve_mutation_outcome(inp)
    artifact = emit_publication_artifact(outcome)
    return Observed(
        resolved_mode=outcome.mode,
        event=outcome.event,
        verdict=outcome.verdict,
        withheld_reason=outcome.withheld_reason,
        would_publish=outcome.would_publish,
        artifact=artifact,
    )


# ---------------------------------------------------------------------------
# PASSIVE
# ---------------------------------------------------------------------------


def _run_passive_clean_no_publication() -> Observed:
    return _observe(_input(mode=raa.PublicationMode.PASSIVE, verdict=raa.Verdict.CLEAN))


def _run_passive_blocking_no_publication() -> Observed:
    return _observe(_input(mode=raa.PublicationMode.PASSIVE, verdict=raa.Verdict.BLOCKING))


_PASSIVE_CASES = (
    PublicationModeCase(
        case_id="PUB-PASSIVE-001-clean-returned-to-caller-only",
        category=CATEGORY_PASSIVE,
        covers=frozenset({"passive_no_publication", "no_inline_comments", "no_formal_event"}),
        description=(
            "A clean PASSIVE review returns its verdict to the caller and emits no "
            "GitHub-bound artifact at all -- no inline comments, no consolidated review "
            "mutation, no formal review event."
        ),
        run=_run_passive_clean_no_publication,
        expected_resolved_mode=raa.PublicationMode.PASSIVE,
        expected_event=raa.GitHubEvent.NONE,
        expected_would_publish=raa.GitHubEvent.NONE,
        expected_artifact_emitted=False,
    ),
    PublicationModeCase(
        case_id="PUB-PASSIVE-002-blocking-returned-to-caller-only",
        category=CATEGORY_PASSIVE,
        covers=frozenset({"passive_no_publication", "no_inline_comments", "no_formal_event"}),
        description="A blocking PASSIVE review also performs no GitHub publication of any kind.",
        run=_run_passive_blocking_no_publication,
        expected_resolved_mode=raa.PublicationMode.PASSIVE,
        expected_event=raa.GitHubEvent.NONE,
        expected_would_publish=raa.GitHubEvent.NONE,
        expected_artifact_emitted=False,
    ),
)


# ---------------------------------------------------------------------------
# SEMI
# ---------------------------------------------------------------------------


def _run_semi_clean_would_approve() -> Observed:
    return _observe(_input(mode=raa.PublicationMode.SEMI, verdict=raa.Verdict.CLEAN))


def _run_semi_blocking_would_request_changes() -> Observed:
    return _observe(_input(mode=raa.PublicationMode.SEMI, verdict=raa.Verdict.BLOCKING))


_SEMI_CASES = (
    PublicationModeCase(
        case_id="PUB-SEMI-001-clean-would-publish-approve-no-mutation",
        category=CATEGORY_SEMI,
        covers=frozenset({"semi_computes_intent", "semi_never_mutates"}),
        description=(
            "SEMI runs the same decision path as ACTIVE and computes the exact event ACTIVE "
            "would submit ('would publish APPROVE'), but performs no GitHub mutation -- must "
            "not degrade into ordinary PASSIVE behavior that stops computing intent."
        ),
        run=_run_semi_clean_would_approve,
        expected_resolved_mode=raa.PublicationMode.SEMI,
        expected_event=raa.GitHubEvent.NONE,
        expected_would_publish=raa.GitHubEvent.APPROVE,
        expected_artifact_emitted=False,
    ),
    PublicationModeCase(
        case_id="PUB-SEMI-002-blocking-would-publish-request-changes-no-mutation",
        category=CATEGORY_SEMI,
        covers=frozenset({"semi_computes_intent", "semi_never_mutates"}),
        description="SEMI over a blocking review computes 'would publish REQUEST_CHANGES', never submits it.",
        run=_run_semi_blocking_would_request_changes,
        expected_resolved_mode=raa.PublicationMode.SEMI,
        expected_event=raa.GitHubEvent.NONE,
        expected_would_publish=raa.GitHubEvent.REQUEST_CHANGES,
        expected_artifact_emitted=False,
    ),
)


# ---------------------------------------------------------------------------
# ACTIVE
# ---------------------------------------------------------------------------


def _run_active_clean_approves() -> Observed:
    return _observe(_input(mode=raa.PublicationMode.ACTIVE, verdict=raa.Verdict.CLEAN))


def _run_active_blocking_requests_changes() -> Observed:
    return _observe(_input(mode=raa.PublicationMode.ACTIVE, verdict=raa.Verdict.BLOCKING))


_ACTIVE_CASES = (
    PublicationModeCase(
        case_id="PUB-ACTIVE-001-clean-approve-reaches-publication-boundary",
        category=CATEGORY_ACTIVE,
        covers=frozenset({"active_publishes", "artifact_verification"}),
        description=(
            "An explicit ACTIVE request over a clean review, with independence/permission/HEAD "
            "all favorable, is sufficient authorization to publish APPROVE -- the GitHub-bound "
            "formal_review artifact must actually be constructed, not merely reported."
        ),
        run=_run_active_clean_approves,
        expected_resolved_mode=raa.PublicationMode.ACTIVE,
        expected_event=raa.GitHubEvent.APPROVE,
        expected_would_publish=raa.GitHubEvent.NONE,
        expected_artifact_emitted=True,
        expected_artifact_kind="formal_review",
    ),
    PublicationModeCase(
        case_id="PUB-ACTIVE-002-blocking-request-changes-reaches-publication-boundary",
        category=CATEGORY_ACTIVE,
        covers=frozenset({"active_publishes", "artifact_verification"}),
        description="An explicit ACTIVE request over a blocking review publishes REQUEST_CHANGES.",
        run=_run_active_blocking_requests_changes,
        expected_resolved_mode=raa.PublicationMode.ACTIVE,
        expected_event=raa.GitHubEvent.REQUEST_CHANGES,
        expected_would_publish=raa.GitHubEvent.NONE,
        expected_artifact_emitted=True,
        expected_artifact_kind="formal_review",
    ),
)


# ---------------------------------------------------------------------------
# PR #297-style regression fixture
# ---------------------------------------------------------------------------


def _run_pr297_regression_shape() -> Observed:
    # Deliberately built with NO second activation-phrase concept anywhere
    # in this input -- ActionAuthorizationInput has no such field to set
    # (see review_action_authorization.py's PROHIBITED_ESCAPE_HATCH_FRAGMENTS,
    # which includes "activation_phrase"). The explicit ACTIVE request is
    # the caller's entire request.
    return _observe(
        _input(
            mode=raa.PublicationMode.ACTIVE,
            verdict=raa.Verdict.CLEAN,
            independence=raa.ReviewerIndependence.INDEPENDENT,
            permitted=_BOTH_EVENTS,
            reviewed_head=HEAD_SHA,
            current_head=HEAD_SHA,
        )
    )


_REGRESSION_297_CASES = (
    PublicationModeCase(
        case_id="PUB-REGRESSION-297-explicit-active-clean-approve-not-withheld",
        category=CATEGORY_REGRESSION_297,
        covers=frozenset({"pr297_regression", "no_second_activation_phrase"}),
        description=(
            "Stable named fixture reproducing the PR #297 behavioral shape (issue #314's "
            "'Anti-regression guard'), independent of the historical PR object itself: an "
            "explicit ACTIVE request, a clean review, a reasoned APPROVE, and a caller "
            "otherwise allowed to publish (independent reviewer, APPROVE permitted, current "
            "HEAD) -- with no second activation phrase anywhere in the input. Must resolve "
            "to publication=true / formal action=APPROVE. Must FAIL if this regresses to "
            "decision=APPROVE / publication=withheld / reason='missing activation'."
        ),
        run=_run_pr297_regression_shape,
        expected_resolved_mode=raa.PublicationMode.ACTIVE,
        expected_event=raa.GitHubEvent.APPROVE,
        expected_would_publish=raa.GitHubEvent.NONE,
        expected_artifact_emitted=True,
        expected_artifact_kind="formal_review",
        notes="Canonical PR #297 regression fixture required by issue #316.",
    ),
)


# ---------------------------------------------------------------------------
# Mode invariants: identical review input, only the mode varies
# ---------------------------------------------------------------------------


def _run_invariant_passive() -> Observed:
    return _observe(_input(mode=raa.PublicationMode.PASSIVE, verdict=raa.Verdict.CLEAN))


def _run_invariant_semi() -> Observed:
    return _observe(_input(mode=raa.PublicationMode.SEMI, verdict=raa.Verdict.CLEAN))


def _run_invariant_active() -> Observed:
    return _observe(_input(mode=raa.PublicationMode.ACTIVE, verdict=raa.Verdict.CLEAN))


_MODE_INVARIANT_CASES = (
    PublicationModeCase(
        case_id="PUB-INVARIANT-001-passive-publication-false",
        category=CATEGORY_MODE_INVARIANT,
        covers=frozenset({"mode_invariant", "semi_active_equivalence"}),
        description="For equivalent review input, PASSIVE always resolves publication=false.",
        run=_run_invariant_passive,
        expected_resolved_mode=raa.PublicationMode.PASSIVE,
        expected_event=raa.GitHubEvent.NONE,
        expected_would_publish=raa.GitHubEvent.NONE,
        expected_artifact_emitted=False,
    ),
    PublicationModeCase(
        case_id="PUB-INVARIANT-002-semi-publication-false-intent-computed",
        category=CATEGORY_MODE_INVARIANT,
        covers=frozenset({"mode_invariant", "semi_active_equivalence"}),
        description=(
            "For the same review input, SEMI resolves publication=false but still computes "
            "the intended publication action (APPROVE) -- the value equivalence with ACTIVE "
            "below is asserted in the corpus test module."
        ),
        run=_run_invariant_semi,
        expected_resolved_mode=raa.PublicationMode.SEMI,
        expected_event=raa.GitHubEvent.NONE,
        expected_would_publish=raa.GitHubEvent.APPROVE,
        expected_artifact_emitted=False,
    ),
    PublicationModeCase(
        case_id="PUB-INVARIANT-003-active-publication-true",
        category=CATEGORY_MODE_INVARIANT,
        covers=frozenset({"mode_invariant", "semi_active_equivalence"}),
        description="For the same review input, ACTIVE resolves publication=true (APPROVE).",
        run=_run_invariant_active,
        expected_resolved_mode=raa.PublicationMode.ACTIVE,
        expected_event=raa.GitHubEvent.APPROVE,
        expected_would_publish=raa.GitHubEvent.NONE,
        expected_artifact_emitted=True,
        expected_artifact_kind="formal_review",
    ),
)


# ---------------------------------------------------------------------------
# Self-review boundary, across all three modes
# ---------------------------------------------------------------------------


def _run_self_review_passive_clean() -> Observed:
    return _observe(_input(mode=raa.PublicationMode.PASSIVE, verdict=raa.Verdict.CLEAN, self_review=True))


def _run_self_review_semi_clean() -> Observed:
    return _observe(_input(mode=raa.PublicationMode.SEMI, verdict=raa.Verdict.CLEAN, self_review=True))


def _run_self_review_active_clean() -> Observed:
    return _observe(_input(mode=raa.PublicationMode.ACTIVE, verdict=raa.Verdict.CLEAN, self_review=True))


def _run_self_review_active_blocking() -> Observed:
    return _observe(_input(mode=raa.PublicationMode.ACTIVE, verdict=raa.Verdict.BLOCKING, self_review=True))


_SELF_REVIEW_CASES = (
    PublicationModeCase(
        case_id="PUB-SELFREVIEW-001-passive-clean-no-formal-event",
        category=CATEGORY_SELF_REVIEW,
        covers=frozenset({"self_review_boundary"}),
        description="Self-review under PASSIVE: no formal event, no artifact of any kind.",
        run=_run_self_review_passive_clean,
        expected_resolved_mode=raa.PublicationMode.PASSIVE,
        expected_event=raa.GitHubEvent.NONE,
        expected_artifact_emitted=False,
    ),
    PublicationModeCase(
        case_id="PUB-SELFREVIEW-002-semi-clean-no-formal-event",
        category=CATEGORY_SELF_REVIEW,
        covers=frozenset({"self_review_boundary"}),
        description=(
            "Self-review under SEMI: no formal event and no informational comment either -- "
            "SEMI never publishes anything, self-review or not."
        ),
        run=_run_self_review_semi_clean,
        expected_resolved_mode=raa.PublicationMode.SEMI,
        expected_event=raa.GitHubEvent.NONE,
        expected_artifact_emitted=False,
    ),
    PublicationModeCase(
        case_id="PUB-SELFREVIEW-003-active-clean-comment-only-no-approve",
        category=CATEGORY_SELF_REVIEW,
        covers=frozenset({"self_review_boundary"}),
        description=(
            "Self-review under ACTIVE: formal review action remains unavailable (no APPROVE) "
            "even on a clean verdict; the canonical contract's explicitly-allowed informational "
            "COMMENT artifact is the only thing emitted."
        ),
        run=_run_self_review_active_clean,
        expected_resolved_mode=raa.PublicationMode.ACTIVE,
        expected_event=raa.GitHubEvent.NONE,
        expected_artifact_emitted=True,
        expected_artifact_kind="informational_comment",
    ),
    PublicationModeCase(
        case_id="PUB-SELFREVIEW-004-active-blocking-comment-only-no-request-changes",
        category=CATEGORY_SELF_REVIEW,
        covers=frozenset({"self_review_boundary"}),
        description="Self-review under ACTIVE on a blocking verdict: no REQUEST_CHANGES either, comment only.",
        run=_run_self_review_active_blocking,
        expected_resolved_mode=raa.PublicationMode.ACTIVE,
        expected_event=raa.GitHubEvent.NONE,
        expected_artifact_emitted=True,
        expected_artifact_kind="informational_comment",
    ),
)


# ---------------------------------------------------------------------------
# Authority boundary: ACTIVE grants review-publication authority only
# ---------------------------------------------------------------------------


def _run_authority_active_clean() -> Observed:
    return _observe(_input(mode=raa.PublicationMode.ACTIVE, verdict=raa.Verdict.CLEAN))


def _run_authority_active_blocking() -> Observed:
    return _observe(_input(mode=raa.PublicationMode.ACTIVE, verdict=raa.Verdict.BLOCKING))


_AUTHORITY_BOUNDARY_CASES = (
    PublicationModeCase(
        case_id="PUB-AUTHORITY-001-active-approve-artifact-carries-no-unrelated-capability",
        category=CATEGORY_AUTHORITY_BOUNDARY,
        covers=frozenset({"authority_boundary", "no_unrelated_mutation"}),
        description=(
            "The formal_review artifact an ACTIVE APPROVE constructs carries only "
            "GITHUB_PUBLICATION_CAPABILITIES fields -- never file-edit, patch, commit, push, "
            "merge, repository-settings, unrelated issue/PR mutation, sandbox, or spawn "
            "capability. Checked structurally in the corpus test module "
            "(ArtifactAuthorityBoundaryTests), not simulated against #301's mutation executor."
        ),
        run=_run_authority_active_clean,
        expected_resolved_mode=raa.PublicationMode.ACTIVE,
        expected_event=raa.GitHubEvent.APPROVE,
        expected_artifact_emitted=True,
        expected_artifact_kind="formal_review",
    ),
    PublicationModeCase(
        case_id="PUB-AUTHORITY-002-active-request-changes-artifact-carries-no-unrelated-capability",
        category=CATEGORY_AUTHORITY_BOUNDARY,
        covers=frozenset({"authority_boundary", "no_unrelated_mutation"}),
        description="Same authority-boundary property, for a REQUEST_CHANGES artifact.",
        run=_run_authority_active_blocking,
        expected_resolved_mode=raa.PublicationMode.ACTIVE,
        expected_event=raa.GitHubEvent.REQUEST_CHANGES,
        expected_artifact_emitted=True,
        expected_artifact_kind="formal_review",
    ),
)


# ---------------------------------------------------------------------------
# Invocation phrasing robustness -- canonical documented examples only
# (review-action-authorization.md, "Natural-language publication intent")
# plus their close synonyms already recognized by raa.normalize_intent.
# ---------------------------------------------------------------------------


def _phrasing_run(text: str) -> "Callable[[], Observed]":
    def _run() -> Observed:
        return Observed(resolved_mode=raa.normalize_intent(text))

    return _run


_PHRASING_CASES = (
    PublicationModeCase(
        case_id="PUB-PHRASING-001-just-review-this-pr-is-passive",
        category=CATEGORY_PHRASING,
        covers=frozenset({"phrasing_robustness"}),
        description="Canonical documented example: 'Just review this PR.' resolves to PASSIVE.",
        run=_phrasing_run("Just review this PR."),
        expected_resolved_mode=raa.PublicationMode.PASSIVE,
    ),
    PublicationModeCase(
        case_id="PUB-PHRASING-002-report-only-dry-run-is-semi",
        category=CATEGORY_PHRASING,
        covers=frozenset({"phrasing_robustness"}),
        description=(
            "Canonical documented example: 'Review it and tell me what would happen, but "
            "don't touch GitHub.' resolves to SEMI."
        ),
        run=_phrasing_run("Review it and tell me what would happen, but don't touch GitHub."),
        expected_resolved_mode=raa.PublicationMode.SEMI,
    ),
    PublicationModeCase(
        case_id="PUB-PHRASING-003-approve-if-clean-request-changes-is-active",
        category=CATEGORY_PHRASING,
        covers=frozenset({"phrasing_robustness"}),
        description=(
            "Canonical documented example: 'Review it; approve if clean, request changes if "
            "there are blocking findings.' resolves to ACTIVE, with no second activation phrase."
        ),
        run=_phrasing_run("Review it; approve if clean, request changes if there are blocking findings."),
        expected_resolved_mode=raa.PublicationMode.ACTIVE,
    ),
    PublicationModeCase(
        case_id="PUB-PHRASING-004-actively-review-pr-is-active",
        category=CATEGORY_PHRASING,
        covers=frozenset({"phrasing_robustness"}),
        description="Canonical documented example: 'Actively review PR #123.' resolves to ACTIVE.",
        run=_phrasing_run("Actively review PR #123."),
        expected_resolved_mode=raa.PublicationMode.ACTIVE,
    ),
    PublicationModeCase(
        case_id="PUB-PHRASING-005-active-review-synonym-phrasing-is-active",
        category=CATEGORY_PHRASING,
        covers=frozenset({"phrasing_robustness"}),
        description=(
            "Close synonym of the canonical 'active review' phrasing ('Please run an active "
            "review of this pull request.') still resolves to ACTIVE -- no magic exact phrase "
            "is required."
        ),
        run=_phrasing_run("Please run an active review of this pull request."),
        expected_resolved_mode=raa.PublicationMode.ACTIVE,
    ),
    PublicationModeCase(
        case_id="PUB-PHRASING-006-preview-synonym-phrasing-is-semi",
        category=CATEGORY_PHRASING,
        covers=frozenset({"phrasing_robustness"}),
        description=(
            "Close synonym of a preview/dry-run request ('Give me a preview of the outcome "
            "without publishing anything.') resolves to SEMI."
        ),
        run=_phrasing_run("Give me a preview of the outcome without publishing anything."),
        expected_resolved_mode=raa.PublicationMode.SEMI,
    ),
)


# ---------------------------------------------------------------------------
# The corpus
# ---------------------------------------------------------------------------

ALL_CASES: "tuple[PublicationModeCase, ...]" = (
    _PASSIVE_CASES
    + _SEMI_CASES
    + _ACTIVE_CASES
    + _REGRESSION_297_CASES
    + _MODE_INVARIANT_CASES
    + _SELF_REVIEW_CASES
    + _AUTHORITY_BOUNDARY_CASES
    + _PHRASING_CASES
)


# Governance: every field name a `GithubPublicationArtifact` declares --
# checked by the corpus test module against
# PROHIBITED_UNRELATED_MUTATION_FRAGMENTS so a future field addition that
# widens the artifact's capability surface cannot land unnoticed.
ARTIFACT_FIELD_NAMES: "frozenset[str]" = frozenset(f.name for f in fields(GithubPublicationArtifact))
