#!/usr/bin/env python3
"""Test-only reference fixtures for the verdict-consistency corpus (Issue
#378, depends on #377: shared/policies/verdict-consistency.md).

#350 proves the normal mechanical severity -> decision path: when a real
review produces a P0/P1 finding, the rendered verdict must not be clean.
That is necessary but does not prove the runtime boundary #351 researched
and #377 implemented actually catches a *corrupted or inconsistent*
downstream surface. This module is deliberately adversarial: every case
starts from an already-finalized mechanical decision
(`tests/reference/review/decision_semantics.py`, `ds` below -- the same
single-derivation source of truth #377's comparator consumes) and then
deliberately drifts the about-to-be-rendered/submitted signal away from
it, exercising the real comparator
(`tests/reference/review/verdict_consistency.py`, `vc` below) through a
runbook-shaped wrapper -- `render_or_withhold` /
`publish_or_withhold` -- that mirrors each Skill's actual reconciliation
step: construct the protected artifact on a consistent signal, or
withhold it and report an internal-consistency failure on a mismatch.
Never a second decision path and never a correction path -- this module
adds no override, force, or resubmit capability, exactly like the
comparator it wraps.

This is **not** a duplicate of
`tests/unit/review/test_verdict_consistency.py`, which already proves the
comparator function `check_rendered_signal`/`check_submitted_event`
mechanically, in isolation, returning only a `Verdict` enum member. That
suite is *why* the boundary holds; this corpus is the declarative,
metadata-bearing **benchmark** layer #378 asks for, and it is the only
place that inspects the *actual withheld-or-emitted artifact* a
reconciliation point would construct -- proving withhold-and-report,
never silent skip and never self-correction -- across all four
reconciliation points #351's design record and `verdict-consistency.md`
name, including the pre-publish point (4) catching a second, silent
drift introduced after the pre-render point (3) already passed.

Like `delegation_fixtures.py`, `publication_mode_fixtures.py`, and
`trusted_host_nl_fixtures.py`, this boundary has no representation in the
`benchmark-case/v1` schema (`docs/benchmark/fixture-format.md`): that
schema's `expected` block is a patch plus expected review findings, with
no field for a finalized decision, a rendered/submitted signal, or a
withheld-artifact outcome. Rather than stretch that closed schema, this
module follows the same test-only, data-driven reference-fixture pattern,
documented in `docs/benchmark/corpus/verdict-consistency/README.md`.

Evaluation style (docs/benchmark/README.md convention): every comparison
here is a deterministic structural assertion -- never an LLM/rubric
score. This corpus is disjoint from the finding-precision/recall/severity
metrics (#41) and from every other domain corpus; it never touches a
finding's content beyond the closed P0/P1/P2 severity already used to
derive the mechanical decision it starts from.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from tests.reference.review import decision_semantics as ds
from tests.reference.review import verdict_consistency as vc

# ---------------------------------------------------------------------------
# Case taxonomy
# ---------------------------------------------------------------------------

CATEGORY_LOCAL_PRE_RENDER = "local_pre_render"
CATEGORY_PASSIVE_SEMI_PRE_RENDER = "passive_semi_pre_render"
CATEGORY_ACTIVE_PRE_RENDER = "active_pre_render"
CATEGORY_ACTIVE_PRE_PUBLISH = "active_pre_publish"
CATEGORY_SILENT_DRIFT_AFTER_PRERENDER = "silent_drift_after_prerender"
CATEGORY_INCOMPLETE_COVERAGE_MISMATCH = "incomplete_coverage_mismatch"
CATEGORY_CONTROL_CONSISTENT = "control_consistent"

VALID_CATEGORIES: frozenset[str] = frozenset(
    {
        CATEGORY_LOCAL_PRE_RENDER,
        CATEGORY_PASSIVE_SEMI_PRE_RENDER,
        CATEGORY_ACTIVE_PRE_RENDER,
        CATEGORY_ACTIVE_PRE_PUBLISH,
        CATEGORY_SILENT_DRIFT_AFTER_PRERENDER,
        CATEGORY_INCOMPLETE_COVERAGE_MISMATCH,
        CATEGORY_CONTROL_CONSISTENT,
    }
)

# The one classification a detected mismatch is ever reported under --
# withhold-and-report, per verdict-consistency.md. A case that observes
# any other reason string, or no `withheld` artifact at all where one is
# expected, has silently skipped or self-corrected instead of enforcing.
INTERNAL_CONSISTENCY_FAILURE_REASON = "internal_consistency_failure"


class VerdictConsistencyFixtureError(ValueError):
    """A verdict-consistency benchmark fixture is malformed."""


# ---------------------------------------------------------------------------
# The protected artifacts each reconciliation point constructs -- or
# withholds
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RenderedReportArtifact:
    """The report body a pre-render reconciliation point (1, 2, or 3)
    would actually construct once the rendered signal is confirmed
    consistent with the finalized mechanical decision."""

    signal: vc.RenderedSignal
    body: str


@dataclass(frozen=True)
class PublishedEventArtifact:
    """The literal GitHub review API event a pre-publish reconciliation
    point (4) would actually submit once confirmed consistent. `event is
    None` records the sanctioned no-formal-event carve-out (PASSIVE or a
    self-review informational COMMENT) -- still a "nothing to withhold"
    consistent outcome, distinct from a mismatch."""

    event: Optional[vc.SubmittedEvent]


@dataclass(frozen=True)
class WithheldArtifact:
    """What a detected mismatch produces instead of the protected
    artifact -- at every reconciliation point, always this shape, never a
    partial or "corrected" version of the protected artifact."""

    reason: str
    detail: str
    reconciliation_point: str


@dataclass(frozen=True)
class Observed:
    """What actually happened when a case's `run()` executed the
    runbook-shaped wrapper around the single real comparator. Exactly one
    of `rendered`, `published`, `withheld` is set -- never more than one,
    and never zero, for any case in this corpus."""

    reconciliation_point: str
    verdict: vc.Verdict
    rendered: Optional[RenderedReportArtifact] = None
    published: Optional[PublishedEventArtifact] = None
    withheld: Optional[WithheldArtifact] = None


# ---------------------------------------------------------------------------
# Runbook-shaped wrappers -- the real decision points this corpus
# benchmarks
# ---------------------------------------------------------------------------


def render_or_withhold(
    reconciliation_point: str,
    mechanical_decision: str,
    coverage_incomplete: bool,
    rendered_signal: vc.RenderedSignal,
    body: str = "## Review Summary\n\nResult: {signal}",
) -> Observed:
    """Reconciliation points 1-3: `local-code-review` pre-render,
    `github-pr-review` PASSIVE/SEMI pre-render, and `github-pr-review`
    ACTIVE pre-render. Mirrors the runbook step immediately before
    composing the report/review body: construct the report on a
    consistent signal, or withhold it and report an internal-consistency
    failure instead -- never both, and never a corrected report body.
    """
    result = vc.check_rendered_signal(mechanical_decision, coverage_incomplete, rendered_signal)
    if result.verdict is vc.Verdict.CONSISTENT:
        return Observed(
            reconciliation_point=reconciliation_point,
            verdict=result.verdict,
            rendered=RenderedReportArtifact(
                signal=rendered_signal, body=body.format(signal=rendered_signal.value)
            ),
        )
    return Observed(
        reconciliation_point=reconciliation_point,
        verdict=result.verdict,
        withheld=WithheldArtifact(
            reason=INTERNAL_CONSISTENCY_FAILURE_REASON,
            detail=result.detail,
            reconciliation_point=reconciliation_point,
        ),
    )


def publish_or_withhold(
    mechanical_decision: str,
    coverage_incomplete: bool,
    submitted_event: Optional[vc.SubmittedEvent],
) -> Observed:
    """Reconciliation point 4: `github-pr-review` ACTIVE pre-publish.
    Mirrors the runbook step immediately before submitting the review:
    re-checks the literal event object about to be sent to GitHub's API
    against the same mechanically-derived decision checked pre-render,
    catching a second, silent drift introduced between that check and
    actual submission.
    """
    result = vc.check_submitted_event(mechanical_decision, coverage_incomplete, submitted_event)
    if result.verdict is vc.Verdict.CONSISTENT:
        return Observed(
            reconciliation_point=CATEGORY_ACTIVE_PRE_PUBLISH,
            verdict=result.verdict,
            published=PublishedEventArtifact(event=submitted_event),
        )
    return Observed(
        reconciliation_point=CATEGORY_ACTIVE_PRE_PUBLISH,
        verdict=result.verdict,
        withheld=WithheldArtifact(
            reason=INTERNAL_CONSISTENCY_FAILURE_REASON,
            detail=result.detail,
            reconciliation_point=CATEGORY_ACTIVE_PRE_PUBLISH,
        ),
    )


def validate_observed_shape(observed: Observed) -> None:
    """Structural invariant every `Observed` must satisfy regardless of
    case: exactly one of rendered/published/withheld is set. Two set at
    once would mean a "best-effort partial render" alongside a withhold;
    zero set would mean neither path ran -- both are outcomes
    verdict-consistency.md forbids."""
    present = [x is not None for x in (observed.rendered, observed.published, observed.withheld)]
    if sum(present) != 1:
        raise VerdictConsistencyFixtureError(
            f"{observed.reconciliation_point}: exactly one of rendered/published/withheld "
            f"must be set, got {present}"
        )
    if observed.withheld is not None:
        if observed.rendered is not None or observed.published is not None:
            raise VerdictConsistencyFixtureError(
                f"{observed.reconciliation_point}: a withheld case must not also carry a "
                "rendered or published artifact (self-correction)"
            )
        if observed.withheld.reason != INTERNAL_CONSISTENCY_FAILURE_REASON:
            raise VerdictConsistencyFixtureError(
                f"{observed.reconciliation_point}: mismatch was not classified as "
                f"{INTERNAL_CONSISTENCY_FAILURE_REASON!r}, got {observed.withheld.reason!r} "
                "(silently skipped or misclassified)"
            )


# ---------------------------------------------------------------------------
# Case shape
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VerdictConsistencyCase:
    """One benchmark case. `run()` is a zero-argument callable exercising
    the real comparator through the runbook-shaped wrapper above,
    returning the decisive `Observed`; every other field is declarative
    metadata validated independently of execution."""

    case_id: str
    category: str
    covers: "frozenset[str]"
    description: str
    run: "Callable[[], Observed]"
    expect_withheld: bool
    notes: str = ""


def validate_case(case: VerdictConsistencyCase) -> None:
    """Fail-closed structural validation of one fixture's *data* --
    independent of running it."""
    if not isinstance(case.case_id, str) or not case.case_id.strip():
        raise VerdictConsistencyFixtureError("case_id must be a non-empty string")
    if case.category not in VALID_CATEGORIES:
        raise VerdictConsistencyFixtureError(
            f"{case.case_id}: category {case.category!r} not in {sorted(VALID_CATEGORIES)}"
        )
    if not isinstance(case.covers, frozenset) or not all(isinstance(t, str) for t in case.covers):
        raise VerdictConsistencyFixtureError(f"{case.case_id}: covers must be a frozenset[str]")
    if not isinstance(case.description, str) or not case.description.strip():
        raise VerdictConsistencyFixtureError(f"{case.case_id}: description must be a non-empty string")
    if not callable(case.run):
        raise VerdictConsistencyFixtureError(f"{case.case_id}: run must be callable")
    if not isinstance(case.expect_withheld, bool):
        raise VerdictConsistencyFixtureError(f"{case.case_id}: expect_withheld must be a bool")


def validate_corpus(cases: "tuple[VerdictConsistencyCase, ...]") -> None:
    """Corpus-wide structural checks: every case validates individually,
    case_ids are unique, and no category is left empty."""
    if not cases:
        raise VerdictConsistencyFixtureError("corpus must not be empty")
    seen: "set[str]" = set()
    for case in cases:
        validate_case(case)
        if case.case_id in seen:
            raise VerdictConsistencyFixtureError(f"duplicate case_id {case.case_id!r}")
        seen.add(case.case_id)


def cases_covering(tag: str) -> "tuple[VerdictConsistencyCase, ...]":
    return tuple(case for case in ALL_CASES if tag in case.covers)


def cases_in_category(category: str) -> "tuple[VerdictConsistencyCase, ...]":
    return tuple(case for case in ALL_CASES if case.category == category)


# ---------------------------------------------------------------------------
# Shared finding fixtures -- the finalized finding set each case's
# mechanical decision is derived from, downstream, exactly like a real
# review's already-finalized findings
# ---------------------------------------------------------------------------

_BLOCKING_FINDINGS = (ds.Finding(id="F1", severity=ds.Severity.P0),)
_CLEAN_FINDINGS = (ds.Finding(id="F1", severity=ds.Severity.P2),)

_BLOCKING_DECISION = ds.derive_decision(_BLOCKING_FINDINGS).value
_CLEAN_DECISION = ds.derive_decision(_CLEAN_FINDINGS).value


# ---------------------------------------------------------------------------
# local-code-review pre-render (reconciliation point 1)
# ---------------------------------------------------------------------------


def _run_local_blocking_to_clean_mismatch() -> Observed:
    # Highest-risk shape #378 requires at minimum: finalized blocking
    # findings, but a rendered signal that quietly claims clean.
    return render_or_withhold(
        CATEGORY_LOCAL_PRE_RENDER, _BLOCKING_DECISION, False, vc.RenderedSignal.REVIEW_CLEAN
    )


def _run_local_clean_to_blocking_mismatch() -> Observed:
    return render_or_withhold(
        CATEGORY_LOCAL_PRE_RENDER, _CLEAN_DECISION, False, vc.RenderedSignal.CHANGES_REQUIRED
    )


def _run_local_consistent_control() -> Observed:
    return render_or_withhold(
        CATEGORY_LOCAL_PRE_RENDER, _BLOCKING_DECISION, False, vc.RenderedSignal.CHANGES_REQUIRED
    )


# ---------------------------------------------------------------------------
# github-pr-review PASSIVE/SEMI pre-render (reconciliation point 2)
# ---------------------------------------------------------------------------


def _run_passive_semi_blocking_to_approve_mismatch() -> Observed:
    return render_or_withhold(
        CATEGORY_PASSIVE_SEMI_PRE_RENDER, _BLOCKING_DECISION, False, vc.RenderedSignal.APPROVE
    )


def _run_passive_semi_clean_to_request_changes_mismatch() -> Observed:
    return render_or_withhold(
        CATEGORY_PASSIVE_SEMI_PRE_RENDER, _CLEAN_DECISION, False, vc.RenderedSignal.REQUEST_CHANGES
    )


def _run_passive_semi_consistent_control() -> Observed:
    return render_or_withhold(
        CATEGORY_PASSIVE_SEMI_PRE_RENDER, _CLEAN_DECISION, False, vc.RenderedSignal.APPROVE
    )


# ---------------------------------------------------------------------------
# github-pr-review ACTIVE pre-render (reconciliation point 3)
# ---------------------------------------------------------------------------


def _run_active_prerender_blocking_to_approve_mismatch() -> Observed:
    return render_or_withhold(
        CATEGORY_ACTIVE_PRE_RENDER, _BLOCKING_DECISION, False, vc.RenderedSignal.APPROVE
    )


def _run_active_prerender_clean_to_request_changes_mismatch() -> Observed:
    return render_or_withhold(
        CATEGORY_ACTIVE_PRE_RENDER, _CLEAN_DECISION, False, vc.RenderedSignal.REQUEST_CHANGES
    )


def _run_active_prerender_consistent_control() -> Observed:
    return render_or_withhold(
        CATEGORY_ACTIVE_PRE_RENDER, _BLOCKING_DECISION, False, vc.RenderedSignal.REQUEST_CHANGES
    )


# ---------------------------------------------------------------------------
# github-pr-review ACTIVE pre-publish (reconciliation point 4)
# ---------------------------------------------------------------------------


def _run_active_prepublish_blocking_to_approve_event_mismatch() -> Observed:
    # The single most severe shape in this corpus: a blocking-findings
    # review about to submit a formal APPROVE event to GitHub's API.
    return publish_or_withhold(_BLOCKING_DECISION, False, vc.SubmittedEvent.APPROVE)


def _run_active_prepublish_clean_to_request_changes_event_mismatch() -> Observed:
    return publish_or_withhold(_CLEAN_DECISION, False, vc.SubmittedEvent.REQUEST_CHANGES)


def _run_active_prepublish_consistent_control() -> Observed:
    return publish_or_withhold(_BLOCKING_DECISION, False, vc.SubmittedEvent.REQUEST_CHANGES)


def _run_active_prepublish_no_formal_event_is_never_a_mismatch() -> Observed:
    # PASSIVE/self-review carve-out, re-affirmed at the pre-publish point:
    # no formal event exists for this invocation, so nothing is withheld.
    return publish_or_withhold(_BLOCKING_DECISION, False, None)


# ---------------------------------------------------------------------------
# Silent drift caught only at pre-publish, after pre-render already
# passed -- the exact "second, silent rendering...by the flow's own
# HEAD-revalidation branch" scenario verdict-consistency.md names for
# reconciliation point 4
# ---------------------------------------------------------------------------


def _run_silent_drift_prerender_passes_prepublish_catches_it() -> Observed:
    prerender = render_or_withhold(
        CATEGORY_ACTIVE_PRE_RENDER, _CLEAN_DECISION, False, vc.RenderedSignal.APPROVE
    )
    validate_observed_shape(prerender)
    if prerender.withheld is not None:
        raise VerdictConsistencyFixtureError(
            "fixture setup error: pre-render must pass consistently before the drift is introduced"
        )
    # A silent drift between pre-render and submission -- exactly the
    # regression point (4) exists to catch, independent of point (3)
    # already having passed.
    return publish_or_withhold(_CLEAN_DECISION, False, vc.SubmittedEvent.REQUEST_CHANGES)


# ---------------------------------------------------------------------------
# REVIEW INCOMPLETE carve-out under adversarial drift -- a mismatch
# involving the sanctioned coverage-incomplete outcome must still be
# caught, never misclassified as the carve-out itself
# ---------------------------------------------------------------------------


def _run_incomplete_coverage_but_rendered_clean_mismatch() -> Observed:
    return render_or_withhold(
        CATEGORY_INCOMPLETE_COVERAGE_MISMATCH, _CLEAN_DECISION, True, vc.RenderedSignal.REVIEW_CLEAN
    )


def _run_incomplete_coverage_but_approve_event_submitted_mismatch() -> Observed:
    return publish_or_withhold(_CLEAN_DECISION, True, vc.SubmittedEvent.APPROVE)


def _run_incomplete_coverage_review_incomplete_signal_is_consistent_control() -> Observed:
    return render_or_withhold(
        CATEGORY_CONTROL_CONSISTENT, _CLEAN_DECISION, True, vc.RenderedSignal.REVIEW_INCOMPLETE
    )


ALL_CASES: "tuple[VerdictConsistencyCase, ...]" = (
    VerdictConsistencyCase(
        case_id="vc-local-blocking-to-clean-mismatch",
        category=CATEGORY_LOCAL_PRE_RENDER,
        covers=frozenset({"local-code-review", "pre-render", "blocking-to-clean", "highest-risk"}),
        description=(
            "local-code-review: finalized P0 finding derives CHANGES REQUIRED, but the "
            "about-to-be-rendered signal is REVIEW CLEAN -- must be withheld before render."
        ),
        run=_run_local_blocking_to_clean_mismatch,
        expect_withheld=True,
    ),
    VerdictConsistencyCase(
        case_id="vc-local-clean-to-blocking-mismatch",
        category=CATEGORY_LOCAL_PRE_RENDER,
        covers=frozenset({"local-code-review", "pre-render", "clean-to-blocking"}),
        description=(
            "local-code-review: finalized clean decision, but the about-to-be-rendered "
            "signal is CHANGES REQUIRED -- must be withheld before render."
        ),
        run=_run_local_clean_to_blocking_mismatch,
        expect_withheld=True,
    ),
    VerdictConsistencyCase(
        case_id="vc-local-consistent-control",
        category=CATEGORY_CONTROL_CONSISTENT,
        covers=frozenset({"local-code-review", "pre-render", "control"}),
        description="local-code-review: a genuinely agreeing signal must never be withheld.",
        run=_run_local_consistent_control,
        expect_withheld=False,
    ),
    VerdictConsistencyCase(
        case_id="vc-passive-semi-blocking-to-approve-mismatch",
        category=CATEGORY_PASSIVE_SEMI_PRE_RENDER,
        covers=frozenset(
            {"github-pr-review", "passive", "semi", "pre-render", "blocking-to-clean", "highest-risk"}
        ),
        description=(
            "github-pr-review PASSIVE/SEMI: finalized blocking decision, but the rendered "
            "report signal is Approve -- must be withheld before render."
        ),
        run=_run_passive_semi_blocking_to_approve_mismatch,
        expect_withheld=True,
    ),
    VerdictConsistencyCase(
        case_id="vc-passive-semi-clean-to-request-changes-mismatch",
        category=CATEGORY_PASSIVE_SEMI_PRE_RENDER,
        covers=frozenset({"github-pr-review", "passive", "semi", "pre-render", "clean-to-blocking"}),
        description=(
            "github-pr-review PASSIVE/SEMI: finalized clean decision, but the rendered "
            "report signal is Request Changes -- must be withheld before render."
        ),
        run=_run_passive_semi_clean_to_request_changes_mismatch,
        expect_withheld=True,
    ),
    VerdictConsistencyCase(
        case_id="vc-passive-semi-consistent-control",
        category=CATEGORY_CONTROL_CONSISTENT,
        covers=frozenset({"github-pr-review", "passive", "semi", "pre-render", "control"}),
        description="github-pr-review PASSIVE/SEMI: a genuinely agreeing signal must never be withheld.",
        run=_run_passive_semi_consistent_control,
        expect_withheld=False,
    ),
    VerdictConsistencyCase(
        case_id="vc-active-prerender-blocking-to-approve-mismatch",
        category=CATEGORY_ACTIVE_PRE_RENDER,
        covers=frozenset(
            {"github-pr-review", "active", "pre-render", "blocking-to-clean", "highest-risk"}
        ),
        description=(
            "github-pr-review ACTIVE pre-render: finalized blocking decision, but the "
            "about-to-be-constructed review body signals Approve -- must be withheld "
            "before the review body/inline comments are constructed."
        ),
        run=_run_active_prerender_blocking_to_approve_mismatch,
        expect_withheld=True,
    ),
    VerdictConsistencyCase(
        case_id="vc-active-prerender-clean-to-request-changes-mismatch",
        category=CATEGORY_ACTIVE_PRE_RENDER,
        covers=frozenset({"github-pr-review", "active", "pre-render", "clean-to-blocking"}),
        description=(
            "github-pr-review ACTIVE pre-render: finalized clean decision, but the "
            "about-to-be-constructed review body signals Request Changes -- must be "
            "withheld before construction."
        ),
        run=_run_active_prerender_clean_to_request_changes_mismatch,
        expect_withheld=True,
    ),
    VerdictConsistencyCase(
        case_id="vc-active-prerender-consistent-control",
        category=CATEGORY_CONTROL_CONSISTENT,
        covers=frozenset({"github-pr-review", "active", "pre-render", "control"}),
        description="github-pr-review ACTIVE pre-render: a genuinely agreeing signal must never be withheld.",
        run=_run_active_prerender_consistent_control,
        expect_withheld=False,
    ),
    VerdictConsistencyCase(
        case_id="vc-active-prepublish-blocking-to-approve-event-mismatch",
        category=CATEGORY_ACTIVE_PRE_PUBLISH,
        covers=frozenset(
            {
                "github-pr-review",
                "active",
                "pre-publish",
                "blocking-to-clean",
                "highest-risk",
                "github-event",
            }
        ),
        description=(
            "github-pr-review ACTIVE pre-publish: finalized blocking decision, but the "
            "literal GitHub review API event about to be submitted is APPROVE -- must be "
            "withheld before submission, the single most severe shape in this corpus."
        ),
        run=_run_active_prepublish_blocking_to_approve_event_mismatch,
        expect_withheld=True,
    ),
    VerdictConsistencyCase(
        case_id="vc-active-prepublish-clean-to-request-changes-event-mismatch",
        category=CATEGORY_ACTIVE_PRE_PUBLISH,
        covers=frozenset({"github-pr-review", "active", "pre-publish", "clean-to-blocking", "github-event"}),
        description=(
            "github-pr-review ACTIVE pre-publish: finalized clean decision, but the literal "
            "GitHub review API event about to be submitted is REQUEST_CHANGES -- must be "
            "withheld before submission."
        ),
        run=_run_active_prepublish_clean_to_request_changes_event_mismatch,
        expect_withheld=True,
    ),
    VerdictConsistencyCase(
        case_id="vc-active-prepublish-consistent-control",
        category=CATEGORY_CONTROL_CONSISTENT,
        covers=frozenset({"github-pr-review", "active", "pre-publish", "control", "github-event"}),
        description="github-pr-review ACTIVE pre-publish: a genuinely agreeing event must never be withheld.",
        run=_run_active_prepublish_consistent_control,
        expect_withheld=False,
    ),
    VerdictConsistencyCase(
        case_id="vc-active-prepublish-no-formal-event-carve-out",
        category=CATEGORY_CONTROL_CONSISTENT,
        covers=frozenset({"github-pr-review", "active", "pre-publish", "no-formal-event", "control"}),
        description=(
            "PASSIVE/self-review carve-out re-affirmed at the pre-publish point: no formal "
            "event exists for this invocation, so nothing is withheld regardless of decision."
        ),
        run=_run_active_prepublish_no_formal_event_is_never_a_mismatch,
        expect_withheld=False,
    ),
    VerdictConsistencyCase(
        case_id="vc-silent-drift-caught-only-at-prepublish",
        category=CATEGORY_SILENT_DRIFT_AFTER_PRERENDER,
        covers=frozenset(
            {
                "github-pr-review",
                "active",
                "pre-publish",
                "silent-drift",
                "reconciliation-point-4",
                "highest-risk",
            }
        ),
        description=(
            "A review whose pre-render check (point 3) already passed consistently, but "
            "whose submitted event silently drifts away from the finalized decision before "
            "submission -- point (4) must independently catch it; point (3) having passed "
            "must never be treated as sufficient."
        ),
        run=_run_silent_drift_prerender_passes_prepublish_catches_it,
        expect_withheld=True,
    ),
    VerdictConsistencyCase(
        case_id="vc-incomplete-coverage-but-rendered-clean-mismatch",
        category=CATEGORY_INCOMPLETE_COVERAGE_MISMATCH,
        covers=frozenset({"review-incomplete", "pre-render", "coverage-incomplete", "not-a-carve-out"}),
        description=(
            "Coverage is incomplete (REVIEW INCOMPLETE is the sanctioned outcome), but the "
            "rendered signal is REVIEW CLEAN -- a mismatch, never the carve-out, and must be "
            "withheld."
        ),
        run=_run_incomplete_coverage_but_rendered_clean_mismatch,
        expect_withheld=True,
    ),
    VerdictConsistencyCase(
        case_id="vc-incomplete-coverage-but-approve-event-submitted-mismatch",
        category=CATEGORY_INCOMPLETE_COVERAGE_MISMATCH,
        covers=frozenset({"review-incomplete", "pre-publish", "coverage-incomplete", "github-event"}),
        description=(
            "Coverage is incomplete, but a formal APPROVE event is about to be submitted -- "
            "REVIEW INCOMPLETE never submits a formal event by policy, so this is a mismatch "
            "and must be withheld."
        ),
        run=_run_incomplete_coverage_but_approve_event_submitted_mismatch,
        expect_withheld=True,
    ),
    VerdictConsistencyCase(
        case_id="vc-incomplete-coverage-review-incomplete-signal-consistent-control",
        category=CATEGORY_CONTROL_CONSISTENT,
        covers=frozenset({"review-incomplete", "pre-render", "coverage-incomplete", "control"}),
        description=(
            "Coverage is incomplete and the rendered signal correctly reads REVIEW "
            "INCOMPLETE -- the sanctioned carve-out, never a mismatch."
        ),
        run=_run_incomplete_coverage_review_incomplete_signal_is_consistent_control,
        expect_withheld=False,
    ),
)
