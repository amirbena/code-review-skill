#!/usr/bin/env python3
"""Stateful re-review regression fixtures (Issue #66).

The #61 analogue for *stateful delta re-review*: where
``test_finding_identity_regression.py`` is the data-driven identity corpus and
``test_delta_re_review.py`` proves the #64 reference semantics in isolation,
this module encodes **paired before/after review histories** and asserts, per
history, the machine-checkable outcomes the #64 semantic contract
(``docs/findings/delta-re-review-contract.md``) and the #65 packaged runtime
policy (``skills/github-pr-review/policies/stateful-delta-rereview.md``) require:

* the re-review **mode** actually selected (full / delta / no-new-delta /
  escalated), including every §2 fail-closed precondition and every §6/§7
  escalation trigger;
* the **change class** each prior identity / current candidate falls into
  (#64 §2), via ``tests/reference/delta_re_review.classify_change`` — never a
  second classifier;
* the **lifecycle event and resulting state** (#62 §7), via a direct
  transcription of that contract's state-transition table — the only
  projection #62 asks #66 to add, since #62's vocabulary is documented but
  not exposed as an importable enum;
* which prior findings **re-surface vs. are suppressed** (only a finding
  folded into ``RESOLVED`` is suppressed; everything carried forward is
  reported);
* the **mechanical decision** derived from the still-open findings, via
  ``tests/reference/decision_semantics.derive_decision`` — no re-review
  severity scale;
* **finding identity** continuity/separation at the re-review integration
  points, via ``tests/reference/finding_identity.effective_identity``;
* **exact-reviewed-HEAD** binding, via
  ``tests/reference/review_status_enforcement.resolve_status_publication``.

#64 is the semantic authority and #65 the runtime-policy authority; this
module *tests* them and never redefines them. The only module-local logic is
thin execution glue — the §2 eligibility gate and the §7 lifecycle table —
each a transcription of a rule those documents already state in full, cited
inline. Every semantic decision routes through an existing ``tests/reference``
model.

Two runs of the same corpus, exactly as #61:

1. ``ReReviewRegressionTests`` — the real reference models must satisfy every
   fixture;
2. ``InducedRegressionTests`` — each representative re-review bug (a mutated
   engine) must be caught by at least one fixture, proving the corpus bites.
"""

from __future__ import annotations

import dataclasses
import unittest
from collections import namedtuple
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional

from tests.reference.decision_semantics import (
    Decision,
    Finding as DecisionFinding,
    Severity,
    derive_decision,
)
from tests.reference.delta_re_review import (
    ChangeClass,
    EscalationSignals,
    LifecycleState,
    MatchOutcome,
    ResolutionEvidence,
    classify_change,
    is_reportable_outside_delta,
    requires_escalation,
)
from tests.reference.finding_identity import (
    build_descriptor,
    effective_identity,
    is_matchable,
    mint_identity,
)
from tests.reference.review_status_enforcement import (
    Reasoning,
    StatusPublicationInput,
    StatusState,
    map_verdict_to_status,
    resolve_status_publication,
)

# ---------------------------------------------------------------------------
# Shared evidence shorthands (#62 §5 resolution bar).
# ---------------------------------------------------------------------------

FULL_BAR = ResolutionEvidence(
    completed_review=True,
    verified_relevant_coverage=True,
    positive_absence_evidence=True,
    no_continuity_ambiguity=True,
    valid_prior_identity_and_state=True,
)
# Completed + covered, but no positive absence evidence and continuity still
# ambiguous — #62 §5 is NOT met, so this must never resolve.
PARTIAL_BAR = ResolutionEvidence(completed_review=True, verified_relevant_coverage=True)


# ---------------------------------------------------------------------------
# Re-review mode + the §2 eligibility gate (transcribes
# stateful-delta-rereview.md §2 fail-closed table and §6 escalation; adds no
# semantics of its own).
# ---------------------------------------------------------------------------


class ReReviewMode(Enum):
    """What a re-review invocation resolved to.

    ``FULL_REVIEW`` here means "no stateful reconciliation state was
    available — proceed as a normal review whose every observation is a first
    ``DETECTED``" (stateful-delta-rereview.md §2 fail-closed). ``ESCALATED_TO_FULL``
    is the distinct §6 outcome: eligible prior state existed, a bounded pass
    began, then a trigger fired — reported as the full review it became, never
    as a partial delta result presented as complete.
    """

    FULL_REVIEW = "full_review"
    DELTA_RE_REVIEW = "delta_re_review"
    NO_NEW_DELTA = "no_new_delta"
    ESCALATED_TO_FULL = "escalated_to_full"


@dataclass(frozen=True)
class PriorState:
    """The five stateful-delta-rereview.md §2 preconditions, plus whether any
    preceding completed review exists at all. Booleans only — §2 is a
    conjunction of established/​not-established facts, not a score."""

    has_prior_completed_review: bool = True
    repo_identity_matches: bool = True
    scope_reconstructable: bool = True
    same_reviewer_identity: bool = True
    prior_sha_exists_and_is_ancestor: bool = True
    trustworthy_prior_findings: bool = True


@dataclass(frozen=True)
class DeltaShape:
    reviewed_sha_equals_head: bool = False
    standard_unchanged: bool = True


def _eligibility_holds(prior: PriorState) -> bool:
    """stateful-delta-rereview.md §2: **all** preconditions must hold; any
    missing / ambiguous / weakly evidenced one fails closed."""
    return (
        prior.repo_identity_matches
        and prior.scope_reconstructable
        and prior.same_reviewer_identity
        and prior.prior_sha_exists_and_is_ancestor
        and prior.trustworthy_prior_findings
    )


def resolve_rereview_mode(
    prior: PriorState, delta: DeltaShape, escalation: EscalationSignals
) -> ReReviewMode:
    """stateful-delta-rereview.md §2 → §6 order: establish eligibility (fail
    closed), then watch the §6 triggers, then recognise ``NO NEW DELTA``."""
    if not prior.has_prior_completed_review:
        return ReReviewMode.FULL_REVIEW
    if not _eligibility_holds(prior):
        return ReReviewMode.FULL_REVIEW
    if requires_escalation(escalation):
        return ReReviewMode.ESCALATED_TO_FULL
    if delta.reviewed_sha_equals_head and delta.standard_unchanged:
        return ReReviewMode.NO_NEW_DELTA
    return ReReviewMode.DELTA_RE_REVIEW


# ---------------------------------------------------------------------------
# Lifecycle event + resulting state — a direct transcription of
# finding-lifecycle-contract.md §7 (the #62 state-transition table). #62 §10
# tells #66 to "inherit the fifteen scenarios in §9 and assert state plus
# event"; #62's vocabulary is documented, not an importable enum, so it is
# transcribed here verbatim and nowhere else.
# ---------------------------------------------------------------------------

_CARRY = "NO TRANSITION"


def lifecycle_event_and_state(
    *,
    prior_state: Optional[LifecycleState],
    match_outcome: Optional[MatchOutcome],
    still_present_evidence: bool,
    resolution_evidence: Optional[ResolutionEvidence],
    recurrence_evidence: bool,
    review_aborted: bool,
) -> tuple[str, Optional[LifecycleState]]:
    if review_aborted:
        return "UNCERTAIN", prior_state  # §7 last row: prior state preserved
    if prior_state is None:
        return "DETECTED", LifecycleState.OPEN
    if match_outcome is MatchOutcome.AMBIGUOUS:
        return "UNCERTAIN", prior_state
    if prior_state is LifecycleState.OPEN:
        if match_outcome is MatchOutcome.MATCH:
            if still_present_evidence:
                return "STILL_PRESENT", LifecycleState.OPEN
            return "UNCERTAIN", LifecycleState.OPEN
        # NO MATCH
        if resolution_evidence is not None and resolution_evidence.meets_bar():
            return "RESOLVED", LifecycleState.RESOLVED
        return "UNCERTAIN", LifecycleState.OPEN
    # prior_state is RESOLVED
    if not recurrence_evidence:
        return _CARRY, LifecycleState.RESOLVED
    if match_outcome is MatchOutcome.MATCH:
        return "REOPENED", LifecycleState.OPEN
    if match_outcome is MatchOutcome.NO_MATCH:
        return _CARRY, LifecycleState.RESOLVED
    return "UNCERTAIN", LifecycleState.RESOLVED


def _contributes_to_decision(event: str, state: Optional[LifecycleState]) -> bool:
    """A finding feeds the mechanical decision iff its current state is OPEN —
    a ``RESOLVED`` finding is reported as resolved, never as a live blocker
    (#64 §5, #62 §8). ``event`` is accepted so a mutant can misuse it."""
    return state is LifecycleState.OPEN


def _status_published(reviewed_sha: str, current_sha: str, clean: bool) -> bool:
    """review-status-enforcement.md exact-HEAD binding: a status computed
    against SHA A is never retargeted onto a newer SHA."""
    inp = StatusPublicationInput(
        reasoning=Reasoning.CLEAN if clean else Reasoning.CHANGES_REQUIRED,
        repo="github.com/acme/widgets",
        pr_number=1,
        reviewed_head_sha=reviewed_sha,
        current_head_sha=current_sha,
    )
    return resolve_status_publication(inp).published


def _identity_relation(relation: str, a: dict, b: dict) -> bool:
    """The re-review identity integration points (#58/#59/#60 via
    ``effective_identity``). Not a re-run of the whole #61 corpus — only the
    continuity/separation cases a re-review actually depends on."""
    da, db = build_descriptor(**a), build_descriptor(**b)
    ma, mb = mint_identity(da), mint_identity(db)
    if relation == "retained":  # #59 MATCH after a move / reformat re-propagates
        return effective_identity(db, matched_prior_identity=ma) == ma and is_matchable(db)
    if relation == "distinct":  # genuinely different defect → its own identity
        return ma != mb
    if relation == "fresh_on_ambiguous":  # AMBIGUOUS never inherits (#62 §4)
        return effective_identity(db, matched_prior_identity=None) == mb and mb != ma
    if relation == "fail_closed":  # non-matchable mints fresh even if a prior is offered
        return not is_matchable(db) and effective_identity(db, matched_prior_identity=ma) == mb
    raise ValueError(f"unknown identity relation: {relation!r}")


# ---------------------------------------------------------------------------
# The engine under test: every semantic step as a swappable callable, exactly
# like #61's ``Impl``. REAL wires the real reference models; each mutant swaps
# exactly one callable.
# ---------------------------------------------------------------------------

Engine = namedtuple(
    "Engine",
    "classify lifecycle resolve_mode escalates contributes decide "
    "reportable_outside status_published identity",
)

def _reportable_outside(evidence_based: bool = True) -> bool:
    """§3: the delta bounds re-analysis *effort*, never finding *eligibility*."""
    return is_reportable_outside_delta(evidence_based=evidence_based)


REAL = Engine(
    classify=classify_change,
    lifecycle=lifecycle_event_and_state,
    resolve_mode=resolve_rereview_mode,
    escalates=requires_escalation,
    contributes=_contributes_to_decision,
    decide=derive_decision,
    reportable_outside=_reportable_outside,
    status_published=_status_published,
    identity=_identity_relation,
)


# ---------------------------------------------------------------------------
# Fixture data model.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FindingDelta:
    """One prior identity / current candidate under a re-review pass."""

    key: str
    prior_state: Optional[LifecycleState] = None
    match_outcome: Optional[MatchOutcome] = None
    still_present_evidence: bool = False
    resolution_evidence: Optional[ResolutionEvidence] = None
    recurrence_evidence: bool = False
    touched_by_delta: bool = False
    blast_radius_attributable: bool = False
    independently_supported: bool = False
    review_aborted: bool = False
    severity: Optional[Severity] = None
    identity: Optional[tuple[str, dict, dict]] = None
    # expectations — each asserted only when not None
    expect_class: Optional[ChangeClass] = None
    expect_error: bool = False
    expect_event: Optional[str] = None
    expect_state: Optional[LifecycleState] = None
    expect_surfaced: Optional[bool] = None

    def classify_inputs(self) -> dict:
        return dict(
            prior_state=self.prior_state,
            match_outcome=self.match_outcome,
            still_present_evidence=self.still_present_evidence,
            resolution_evidence=self.resolution_evidence,
            recurrence_evidence=self.recurrence_evidence,
            touched_by_delta=self.touched_by_delta,
            blast_radius_attributable=self.blast_radius_attributable,
            independently_supported=self.independently_supported,
        )

    def lifecycle_inputs(self) -> dict:
        return dict(
            prior_state=self.prior_state,
            match_outcome=self.match_outcome,
            still_present_evidence=self.still_present_evidence,
            resolution_evidence=self.resolution_evidence,
            recurrence_evidence=self.recurrence_evidence,
            review_aborted=self.review_aborted,
        )


@dataclass(frozen=True)
class Scenario:
    id: str
    group: str
    why: str
    findings: tuple[FindingDelta, ...] = ()
    prior: PriorState = PriorState()
    delta: DeltaShape = DeltaShape()
    escalation: EscalationSignals = EscalationSignals()
    expect_mode: ReReviewMode = ReReviewMode.DELTA_RE_REVIEW
    expect_escalation: bool = False
    expect_decision: Optional[Decision] = None
    # exact-HEAD: (reviewed_sha, current_sha, clean_verdict) -> expect published?
    head_case: Optional[tuple[str, str, bool]] = None
    expect_status_published: Optional[bool] = None
    assert_reportable_outside: bool = False
    lifecycle_ref: Optional[int] = None  # finding-lifecycle-contract.md §9 row


# ---------------------------------------------------------------------------
# The corpus.
# ---------------------------------------------------------------------------

_OPEN, _RESOLVED = LifecycleState.OPEN, LifecycleState.RESOLVED
_MATCH, _NO_MATCH, _AMBIG = (
    MatchOutcome.MATCH,
    MatchOutcome.NO_MATCH,
    MatchOutcome.AMBIGUOUS,
)


def _ident(**over: object) -> dict:
    """A fully-populated, source-backed, matchable finding (mirrors #61's
    ``_base`` shape, trimmed to what identity integration needs here)."""
    kw = dict(
        repository="github.com/acme/widgets",
        location="src/pay/retry.py:88",
        behavioral_claim_text=(
            "the row is re-enqueued before the commit so a retry processes "
            "the payment twice"
        ),
        anchor_fragment="queue.put(job)",
        mechanism_fragment="queue.put(job)",
        symbol="pay.retry.RetryHandler.run",
    )
    kw.update(over)
    return kw


_MOVED_IDENT = (
    "retained",
    _ident(),
    _ident(location="src/pay/retry.py:206", symbol="pay.retry.RetryHandler.dispatch"),
)
_REFORMAT_IDENT = (
    "retained",
    _ident(),
    _ident(anchor_fragment="queue . put(\n    job,\n)  # re-enqueue", mechanism_fragment="queue.put(  job  )"),
)
_DISTINCT_IDENT = (
    "distinct",
    _ident(),
    _ident(
        behavioral_claim_text="the lock is released early so two workers enter the section",
        anchor_fragment="lock.release()",
        mechanism_fragment="lock.release()",
        symbol="pay.retry.RetryHandler.finish",
    ),
)
_SAME_LINE_DISTINCT_IDENT = (
    "distinct",
    _ident(),
    _ident(
        behavioral_claim_text="the amount is parsed as a float so rounding drifts on large sums",
        anchor_fragment="total = float(amount)",
        mechanism_fragment="total = float(amount)",
        defect_kind_text="precision loss",
    ),
)
_AMBIG_IDENT = (
    "fresh_on_ambiguous",
    _ident(),
    _ident(
        behavioral_claim_text=(
            "the row is re-enqueued before the commit so the customer is "
            "double-charged on retry"
        )
    ),
)
_FAILCLOSED_IDENT = (
    "fail_closed",
    _ident(),
    _ident(behavioral_claim_text="the architecture is unclear", anchor_fragment=None, mechanism_fragment=None, symbol=None),
)


def _scenarios() -> list[Scenario]:
    S: list[Scenario] = []
    add = S.append

    # -- Change class: UNCHANGED --------------------------------------------
    add(Scenario(
        id="unchanged/open-still-present-not-relocated",
        group="unchanged",
        why="prior OPEN finding, site outside the delta, still positively present: "
        "carried forward as OPEN, event STILL_PRESENT — never re-minted as new.",
        lifecycle_ref=2,
        findings=(FindingDelta(
            key="retry double-charge",
            prior_state=_OPEN, match_outcome=_MATCH, still_present_evidence=True,
            touched_by_delta=False, severity=Severity.P1,
            expect_class=ChangeClass.UNCHANGED,
            expect_event="STILL_PRESENT", expect_state=_OPEN, expect_surfaced=True,
        ),),
        expect_decision=Decision.CHANGES_REQUIRED,
    ))
    add(Scenario(
        id="unchanged/untouched-code-not-reclassified-as-new",
        group="unchanged",
        why="#64 §2 note: unchanged, uninspected code is a re-analysis-scope "
        "conclusion — no lifecycle event, prior state as-is; not DETECTED.",
        findings=(FindingDelta(
            key="dormant P2",
            prior_state=_OPEN, match_outcome=_NO_MATCH, touched_by_delta=False,
            blast_radius_attributable=False, severity=Severity.P2,
            expect_class=ChangeClass.UNCHANGED,
            expect_event="UNCERTAIN", expect_state=_OPEN, expect_surfaced=True,
        ),),
        expect_decision=Decision.CLEAN,
    ))
    add(Scenario(
        id="unchanged/resolved-prior-no-recurrence-stays-resolved",
        group="unchanged",
        why="a RESOLVED identity with no positive recurrence signal takes no "
        "event and stays RESOLVED — similarity alone is not reopening (#62 §6).",
        lifecycle_ref=8,
        findings=(FindingDelta(
            key="old guard, since fixed",
            prior_state=_RESOLVED, match_outcome=_NO_MATCH, recurrence_evidence=False,
            expect_class=ChangeClass.UNCHANGED,
            expect_event=_CARRY, expect_state=_RESOLVED, expect_surfaced=False,
        ),),
        expect_decision=Decision.CLEAN,
    ))

    # -- Change class: FIXED ----------------------------------------------
    add(Scenario(
        id="fixed/definite-resolution-full-bar",
        group="fixed",
        why="#62 §5 bar fully met on a definite NO MATCH → RESOLVED; suppressed "
        "from the open finding set and from the decision.",
        lifecycle_ref=4,
        findings=(FindingDelta(
            key="retry double-charge, fixed",
            prior_state=_OPEN, match_outcome=_NO_MATCH, resolution_evidence=FULL_BAR,
            touched_by_delta=True, severity=Severity.P1,
            expect_class=ChangeClass.FIXED,
            expect_event="RESOLVED", expect_state=_RESOLVED, expect_surfaced=False,
        ),),
        expect_decision=Decision.CLEAN,
    ))
    add(Scenario(
        id="fixed/deleted-code-carrying-the-defect",
        group="fixed",
        why="#62 §9 row 14: the defect-bearing code is deleted, covered, no "
        "continuation → RESOLVED (CODE_REMOVED), not merely absent-from-diff.",
        lifecycle_ref=14,
        findings=(FindingDelta(
            key="removed unsafe branch",
            prior_state=_OPEN, match_outcome=_NO_MATCH, resolution_evidence=FULL_BAR,
            touched_by_delta=True, severity=Severity.P1,
            expect_class=ChangeClass.FIXED, expect_event="RESOLVED",
            expect_state=_RESOLVED, expect_surfaced=False,
        ),),
        expect_decision=Decision.CLEAN,
    ))
    add(Scenario(
        id="fixed/partial-bar-is-ambiguous-never-fixed",
        group="fixed",
        why="#62 §5 unmet (no positive absence evidence, continuity ambiguous): "
        "NO MATCH alone must not resolve — stays OPEN/UNCERTAIN.",
        lifecycle_ref=5,
        findings=(FindingDelta(
            key="maybe-fixed retry path",
            prior_state=_OPEN, match_outcome=_NO_MATCH, resolution_evidence=PARTIAL_BAR,
            touched_by_delta=True, severity=Severity.P1,
            expect_class=ChangeClass.AMBIGUOUS,
            expect_event="UNCERTAIN", expect_state=_OPEN, expect_surfaced=True,
        ),),
        expect_decision=Decision.CHANGES_REQUIRED,
    ))

    # -- Change class: MOVED --------------------------------------------
    add(Scenario(
        id="moved/relocated-defect-keeps-identity",
        group="moved",
        why="#59 MATCH after an extraction/rename: STILL_PRESENT, stays OPEN, "
        "same identity — not a duplicate, not a new finding (#64 §8).",
        lifecycle_ref=15,
        findings=(FindingDelta(
            key="retry defect, moved to dispatch()",
            prior_state=_OPEN, match_outcome=_MATCH, still_present_evidence=True,
            touched_by_delta=True, severity=Severity.P1, identity=_MOVED_IDENT,
            expect_class=ChangeClass.MOVED,
            expect_event="STILL_PRESENT", expect_state=_OPEN, expect_surfaced=True,
        ),),
        expect_decision=Decision.CHANGES_REQUIRED,
    ))
    add(Scenario(
        id="moved/partial-fix-same-defect-remains",
        group="moved",
        why="#62 §9 row 3: the site is edited but the cause→faulty-behavior "
        "path is still demonstrable → STILL_PRESENT, OPEN (not RESOLVED).",
        lifecycle_ref=3,
        findings=(FindingDelta(
            key="retry defect, narrowed but live",
            prior_state=_OPEN, match_outcome=_MATCH, still_present_evidence=True,
            touched_by_delta=True, severity=Severity.P1,
            expect_class=ChangeClass.MOVED, expect_event="STILL_PRESENT",
            expect_state=_OPEN, expect_surfaced=True,
        ),),
        expect_decision=Decision.CHANGES_REQUIRED,
    ))
    add(Scenario(
        id="moved/reformat-only-keeps-identity",
        group="moved",
        why="whitespace/wrapping churn on the anchor is not a new finding; a "
        "definite MATCH re-propagates the original identity.",
        findings=(FindingDelta(
            key="retry defect, reformatted",
            prior_state=_OPEN, match_outcome=_MATCH, still_present_evidence=True,
            touched_by_delta=True, severity=Severity.P2, identity=_REFORMAT_IDENT,
            expect_class=ChangeClass.MOVED, expect_event="STILL_PRESENT",
            expect_state=_OPEN, expect_surfaced=True,
        ),),
        expect_decision=Decision.CLEAN,
    ))

    # -- Change class: REOPENED --------------------------------------------
    add(Scenario(
        id="reopened/recurrence-plus-match-at-same-site",
        group="reopened",
        why="#62 §6 handshake: prior RESOLVED + positive recurrence evidence + "
        "definite MATCH → REOPENED, OPEN, original identity reused.",
        lifecycle_ref=7,
        findings=(FindingDelta(
            key="guard removed again",
            prior_state=_RESOLVED, match_outcome=_MATCH, recurrence_evidence=True,
            severity=Severity.P1, identity=("retained", _ident(), _ident()),
            expect_class=ChangeClass.REOPENED, expect_event="REOPENED",
            expect_state=_OPEN, expect_surfaced=True,
        ),),
        expect_decision=Decision.CHANGES_REQUIRED,
    ))
    add(Scenario(
        id="reopened/recurrence-without-match-stays-resolved",
        group="reopened",
        why="recurrence evidence only *permits* matching to reconsider; NO "
        "MATCH leaves the prior identity RESOLVED with no event.",
        findings=(FindingDelta(
            key="similar-looking but distinct defect",
            prior_state=_RESOLVED, match_outcome=_NO_MATCH, recurrence_evidence=True,
            expect_class=ChangeClass.UNCHANGED, expect_event=_CARRY,
            expect_state=_RESOLVED, expect_surfaced=False,
        ),),
        expect_decision=Decision.CLEAN,
    ))
    add(Scenario(
        id="reopened/recurrence-with-ambiguous-match-stays-resolved",
        group="reopened",
        why="#62 §7: prior RESOLVED + recurrence + AMBIGUOUS → UNCERTAIN, "
        "RESOLVED preserved — no fabricated reopen.",
        findings=(FindingDelta(
            key="contested recurrence",
            prior_state=_RESOLVED, match_outcome=_AMBIG, recurrence_evidence=True,
            expect_class=ChangeClass.AMBIGUOUS, expect_event="UNCERTAIN",
            expect_state=_RESOLVED, expect_surfaced=False,
        ),),
        expect_decision=Decision.CLEAN,
    ))

    # -- Change class: NEWLY INTRODUCED ----------------------------------
    add(Scenario(
        id="newly-introduced/fresh-defect-in-the-delta",
        group="newly_introduced",
        why="#62 §9 row 1: a supported current defect with no prior identity → "
        "DETECTED, OPEN.",
        lifecycle_ref=1,
        findings=(FindingDelta(
            key="new NPE in added branch",
            prior_state=None, match_outcome=None, independently_supported=True,
            touched_by_delta=True, severity=Severity.P1,
            expect_class=ChangeClass.NEWLY_INTRODUCED, expect_event="DETECTED",
            expect_state=_OPEN, expect_surfaced=True,
        ),),
        expect_decision=Decision.CHANGES_REQUIRED,
    ))
    add(Scenario(
        id="newly-introduced/no-prior-identity-inherited",
        group="newly_introduced",
        why="a genuinely new defect must not adopt a nearby prior finding's "
        "identity — distinct descriptor → distinct minted id.",
        findings=(FindingDelta(
            key="new race in refactored finish()",
            prior_state=None, match_outcome=None, independently_supported=True,
            touched_by_delta=True, severity=Severity.P2, identity=_DISTINCT_IDENT,
            expect_class=ChangeClass.NEWLY_INTRODUCED, expect_event="DETECTED",
            expect_state=_OPEN, expect_surfaced=True,
        ),),
        expect_decision=Decision.CLEAN,
    ))
    add(Scenario(
        id="newly-introduced/p2-only-does-not-block",
        group="newly_introduced",
        why="regression severity is by impact, not by the fact it appeared "
        "during re-review: a lone new P2 stays non-blocking.",
        findings=(FindingDelta(
            key="new minor style-of-logging issue",
            prior_state=None, match_outcome=None, independently_supported=True,
            touched_by_delta=True, severity=Severity.P2,
            expect_class=ChangeClass.NEWLY_INTRODUCED, expect_event="DETECTED",
            expect_state=_OPEN, expect_surfaced=True,
        ),),
        expect_decision=Decision.CLEAN,
    ))
    add(Scenario(
        id="newly-introduced/no-observation-no-classification",
        group="newly_introduced",
        why="no prior identity and no independently supported observation is "
        "not a finding at all — classify_change refuses rather than inventing one.",
        findings=(FindingDelta(
            key="nothing here",
            prior_state=None, match_outcome=None, independently_supported=False,
            expect_error=True,
        ),),
    ))

    # -- Change class: AMBIGUOUS / non-matchable ------------------------
    add(Scenario(
        id="ambiguous/open-prior-fails-closed",
        group="ambiguous",
        why="#62 §7: OPEN + AMBIGUOUS → UNCERTAIN, OPEN preserved; no confident "
        "transition even though the defect might be gone.",
        lifecycle_ref=6,
        findings=(FindingDelta(
            key="ambiguous continuity",
            prior_state=_OPEN, match_outcome=_AMBIG, still_present_evidence=True,
            severity=Severity.P1,
            expect_class=ChangeClass.AMBIGUOUS, expect_event="UNCERTAIN",
            expect_state=_OPEN, expect_surfaced=True, identity=_AMBIG_IDENT,
        ),),
        expect_decision=Decision.CHANGES_REQUIRED,
    ))
    add(Scenario(
        id="ambiguous/split-one-prior-into-two-candidates",
        group="ambiguous",
        why="#62 §9 row 11: one-to-many cannot transfer identity → UNCERTAIN, "
        "OPEN preserved for the prior identity.",
        lifecycle_ref=11,
        findings=(FindingDelta(
            key="prior finding, now split",
            prior_state=_OPEN, match_outcome=_AMBIG, still_present_evidence=True,
            severity=Severity.P1,
            expect_class=ChangeClass.AMBIGUOUS, expect_event="UNCERTAIN",
            expect_state=_OPEN, expect_surfaced=True,
        ),),
        expect_decision=Decision.CHANGES_REQUIRED,
    ))
    add(Scenario(
        id="ambiguous/collapse-two-priors-into-one-candidate",
        group="ambiguous",
        why="#62 §9 row 12: many-to-one cannot transfer either identity → "
        "UNCERTAIN each, both OPEN preserved.",
        lifecycle_ref=12,
        findings=(
            FindingDelta(
                key="prior A, collapsed",
                prior_state=_OPEN, match_outcome=_AMBIG, still_present_evidence=True,
                severity=Severity.P2,
                expect_class=ChangeClass.AMBIGUOUS, expect_event="UNCERTAIN",
                expect_state=_OPEN, expect_surfaced=True,
            ),
            FindingDelta(
                key="prior B, collapsed",
                prior_state=_OPEN, match_outcome=_AMBIG, still_present_evidence=True,
                severity=Severity.P1,
                expect_class=ChangeClass.AMBIGUOUS, expect_event="UNCERTAIN",
                expect_state=_OPEN, expect_surfaced=True,
            ),
        ),
        expect_decision=Decision.CHANGES_REQUIRED,
    ))
    add(Scenario(
        id="ambiguous/full-evidence-cannot-override-ambiguous-match",
        group="ambiguous",
        why="even with a complete resolution bar and recurrence evidence "
        "present, an AMBIGUOUS #59 outcome yields only UNCERTAIN (#64 §8).",
        findings=(FindingDelta(
            key="over-evidenced but ambiguous",
            prior_state=_OPEN, match_outcome=_AMBIG, still_present_evidence=True,
            resolution_evidence=FULL_BAR, recurrence_evidence=True, severity=Severity.P1,
            expect_class=ChangeClass.AMBIGUOUS, expect_event="UNCERTAIN",
            expect_state=_OPEN, expect_surfaced=True,
        ),),
        expect_decision=Decision.CHANGES_REQUIRED,
    ))
    add(Scenario(
        id="ambiguous/non-matchable-identity-does-not-transition",
        group="ambiguous",
        why="a source-less descriptor is non-matchable: it mints fresh even "
        "when a prior identity is offered — fail-closed at the hand-off.",
        findings=(FindingDelta(
            key="architecture-shaped observation",
            prior_state=_OPEN, match_outcome=_AMBIG, still_present_evidence=True,
            severity=Severity.P2, identity=_FAILCLOSED_IDENT,
            expect_class=ChangeClass.AMBIGUOUS, expect_event="UNCERTAIN",
            expect_state=_OPEN, expect_surfaced=True,
        ),),
        expect_decision=Decision.CLEAN,
    ))

    # -- #64 regression: fix resolves one, introduces another ----------
    add(Scenario(
        id="fix-induced/resolves-p1-introduces-p1",
        group="fix_induced_regression",
        why="#64 §3: a RESOLVED event on one identity never makes the fix "
        "delta clean — the new P1 surfaces independently and still blocks.",
        findings=(
            FindingDelta(
                key="original retry defect, fixed",
                prior_state=_OPEN, match_outcome=_NO_MATCH, resolution_evidence=FULL_BAR,
                touched_by_delta=True, severity=Severity.P1,
                expect_class=ChangeClass.FIXED, expect_event="RESOLVED",
                expect_state=_RESOLVED, expect_surfaced=False,
            ),
            FindingDelta(
                key="new off-by-one in the fix",
                prior_state=None, match_outcome=None, independently_supported=True,
                touched_by_delta=True, severity=Severity.P1,
                expect_class=ChangeClass.NEWLY_INTRODUCED, expect_event="DETECTED",
                expect_state=_OPEN, expect_surfaced=True,
            ),
        ),
        expect_decision=Decision.CHANGES_REQUIRED,
        assert_reportable_outside=True,
    ))
    add(Scenario(
        id="fix-induced/resolves-p1-introduces-p0",
        group="fix_induced_regression",
        why="the resolving lines are new code in this delta: a P0 they "
        "introduce is surfaced and the review is not incorrectly clean.",
        findings=(
            FindingDelta(
                key="original defect, fixed",
                prior_state=_OPEN, match_outcome=_NO_MATCH, resolution_evidence=FULL_BAR,
                touched_by_delta=True, severity=Severity.P1,
                expect_class=ChangeClass.FIXED, expect_event="RESOLVED",
                expect_state=_RESOLVED, expect_surfaced=False,
            ),
            FindingDelta(
                key="auth check dropped by the fix",
                prior_state=None, match_outcome=None, independently_supported=True,
                touched_by_delta=True, severity=Severity.P0,
                expect_class=ChangeClass.NEWLY_INTRODUCED, expect_event="DETECTED",
                expect_state=_OPEN, expect_surfaced=True,
            ),
        ),
        expect_decision=Decision.CHANGES_REQUIRED,
    ))
    add(Scenario(
        id="fix-induced/prior-resolution-retained-alongside-new-defect",
        group="fix_induced_regression",
        why="the valid prior resolution is kept (not rolled back) while the "
        "new defect is reported — both facts coexist.",
        findings=(
            FindingDelta(
                key="prior defect, legitimately fixed",
                prior_state=_OPEN, match_outcome=_NO_MATCH, resolution_evidence=FULL_BAR,
                touched_by_delta=True, severity=Severity.P2,
                expect_class=ChangeClass.FIXED, expect_event="RESOLVED",
                expect_state=_RESOLVED, expect_surfaced=False,
            ),
            FindingDelta(
                key="unrelated new P2 in the same hunk",
                prior_state=None, match_outcome=None, independently_supported=True,
                touched_by_delta=True, severity=Severity.P2,
                expect_class=ChangeClass.NEWLY_INTRODUCED, expect_event="DETECTED",
                expect_state=_OPEN, expect_surfaced=True,
            ),
        ),
        expect_decision=Decision.CLEAN,
    ))

    # -- #64 regression: blast radius --------------------------------
    add(Scenario(
        id="blast-radius/regression-outside-original-lines-attributable",
        group="blast_radius",
        why="#64 §4: a caller of changed logic breaks; concrete causal path "
        "→ NEWLY_INTRODUCED, reportable though its own lines are untouched.",
        findings=(FindingDelta(
            key="caller now passes wrong arg order",
            prior_state=None, match_outcome=None, independently_supported=True,
            blast_radius_attributable=True, touched_by_delta=False, severity=Severity.P1,
            expect_class=ChangeClass.NEWLY_INTRODUCED, expect_event="DETECTED",
            expect_state=_OPEN, expect_surfaced=True,
        ),),
        expect_decision=Decision.CHANGES_REQUIRED,
        assert_reportable_outside=True,
    ))
    add(Scenario(
        id="blast-radius/transitive-invariant-break",
        group="blast_radius",
        why="a component depending on an invariant the change altered is in "
        "scope even with no edited source lines of its own.",
        findings=(FindingDelta(
            key="cache consumer sees stale shape",
            prior_state=None, match_outcome=None, independently_supported=True,
            blast_radius_attributable=True, touched_by_delta=False, severity=Severity.P1,
            expect_class=ChangeClass.NEWLY_INTRODUCED, expect_event="DETECTED",
            expect_state=_OPEN, expect_surfaced=True,
        ),),
        expect_decision=Decision.CHANGES_REQUIRED,
    ))
    add(Scenario(
        id="blast-radius/no-mechanism-no-classification",
        group="blast_radius",
        why="#64 §4: 'same file' / 'nearby' is not attribution — with neither "
        "a delta touch nor an attributable path, there is nothing to classify.",
        findings=(FindingDelta(
            key="speculative same-file concern",
            prior_state=None, match_outcome=None, independently_supported=True,
            blast_radius_attributable=False, touched_by_delta=False,
            expect_error=True,
        ),),
    ))

    # -- #64 regression: settled assumptions -------------------------
    add(Scenario(
        id="settled/survives-unrelated-delta",
        group="settled_assumption",
        why="#64 §6: a settled non-finding stays settled while the delta leaves "
        "its basis untouched — no re-derivation forced.",
        findings=(FindingDelta(
            key="'input validated upstream' — still true",
            prior_state=_RESOLVED, match_outcome=_NO_MATCH, recurrence_evidence=False,
            expect_class=ChangeClass.UNCHANGED, expect_event=_CARRY,
            expect_state=_RESOLVED, expect_surfaced=False,
        ),),
        expect_decision=Decision.CLEAN,
    ))
    add(Scenario(
        id="settled/invalidated-by-direct-edit-becomes-finding",
        group="settled_assumption",
        why="#64 §6: the delta edits the code the settled conclusion depended "
        "on → it is re-evaluated and, failing, becomes a normal new finding.",
        findings=(FindingDelta(
            key="upstream validation removed",
            prior_state=None, match_outcome=None, independently_supported=True,
            touched_by_delta=True, severity=Severity.P1,
            expect_class=ChangeClass.NEWLY_INTRODUCED, expect_event="DETECTED",
            expect_state=_OPEN, expect_surfaced=True,
        ),),
        expect_decision=Decision.CHANGES_REQUIRED,
    ))
    add(Scenario(
        id="settled/invalidated-via-blast-radius-not-blindly-inherited",
        group="settled_assumption",
        why="#64 §6: invalidation may arrive via an attributable blast-radius "
        "path, not only a direct edit to the assumption's own site.",
        findings=(FindingDelta(
            key="shared schema change breaks a settled 'safe here'",
            prior_state=None, match_outcome=None, independently_supported=True,
            blast_radius_attributable=True, touched_by_delta=False, severity=Severity.P1,
            expect_class=ChangeClass.NEWLY_INTRODUCED, expect_event="DETECTED",
            expect_state=_OPEN, expect_surfaced=True,
        ),),
        expect_decision=Decision.CHANGES_REQUIRED,
        assert_reportable_outside=True,
    ))

    # -- #64/#65 escalation triggers -------------------------------
    for trig_id, signals, why in (
        (
            "assumptions-materially-invalidated",
            EscalationSignals(prior_assumptions_materially_invalidated=True),
            "a premise multiple settled conclusions / prior findings depended on "
            "changed — piecemeal re-validation cannot reconstruct a coherent picture.",
        ),
        (
            "blast-radius-unbounded",
            EscalationSignals(blast_radius_untraceable=True),
            "the delta's causal chains are too numerous/uncertain to trace "
            "individually — blast radius can no longer be bounded.",
        ),
        (
            "matching-broadly-unreliable",
            EscalationSignals(matching_broadly_unreliable=True),
            "AMBIGUOUS outcomes are pervasive across a meaningful share of the "
            "prior finding set — not a single ambiguous identity.",
        ),
        (
            "reviewed-state-boundary-violated",
            EscalationSignals(review_boundary_violated=True),
            "a reviewed-state precondition is violated in a way §2 fail-closed "
            "alone does not cover (e.g. irreconcilable base movement).",
        ),
    ):
        add(Scenario(
            id=f"escalation/{trig_id}",
            group="escalation",
            why=f"#64 §7 / #65 §6: {why} Bounded delta re-review stops; the pass "
            "completes as the full review it became, never a partial result "
            "presented as complete.",
            escalation=signals,
            expect_mode=ReReviewMode.ESCALATED_TO_FULL,
            expect_escalation=True,
        ))
    add(Scenario(
        id="escalation/no-signal-stays-bounded",
        group="escalation",
        why="control: with no trigger and full eligibility, the pass stays a "
        "bounded delta re-review — escalation is not the default.",
        expect_mode=ReReviewMode.DELTA_RE_REVIEW,
        expect_escalation=False,
    ))
    add(Scenario(
        id="escalation/aborted-review-commits-no-transition",
        group="escalation",
        why="#62 §9 row 13: a review that aborts before sufficient coverage "
        "records UNCERTAIN and preserves prior state — nothing is resolved.",
        lifecycle_ref=13,
        findings=(FindingDelta(
            key="coverage cut short",
            prior_state=_OPEN, match_outcome=_NO_MATCH, review_aborted=True,
            resolution_evidence=FULL_BAR, severity=Severity.P1,
            expect_event="UNCERTAIN", expect_state=_OPEN, expect_surfaced=True,
        ),),
        expect_decision=Decision.CHANGES_REQUIRED,
    ))

    # -- Prior-state eligibility / fail-closed -----------------------
    for fc_id, prior, why in (
        (
            "missing-reviewed-sha",
            PriorState(prior_sha_exists_and_is_ancestor=False),
            "the previous reviewed SHA no longer exists in the repository.",
        ),
        (
            "prior-sha-not-ancestor-history-rewrite",
            PriorState(prior_sha_exists_and_is_ancestor=False),
            "a rebase/force-push broke ancestry — prior..head is not a "
            "meaningful range; re-review state is not reused across the rewrite.",
        ),
        (
            "wrong-repository-scope",
            PriorState(repo_identity_matches=False),
            "the prior record's repository identity differs from the current one.",
        ),
        (
            "reviewer-identity-mismatch",
            PriorState(same_reviewer_identity=False),
            "reviewer ownership cannot be verified as the same identity on both sides.",
        ),
        (
            "untrusted-finding-provenance",
            PriorState(trustworthy_prior_findings=False),
            "prior findings are only weakly/ambiguously evidenced — not "
            "recoverable from authoritative provenance.",
        ),
        (
            "no-prior-completed-review",
            PriorState(has_prior_completed_review=False),
            "this is the first review of the branch — there is no prior state at all.",
        ),
        (
            "scope-not-reconstructable",
            PriorState(scope_reconstructable=False),
            "the prior base/merge-base cannot be reconstructed, so base movement "
            "cannot be detected.",
        ),
    ):
        add(Scenario(
            id=f"prior-state/{fc_id}",
            group="prior_state_failclosed",
            why=f"stateful-delta-rereview.md §2 fail-closed: {why} → normal "
            "review, every observation a first DETECTED; no invented delta "
            "state, no stale prior finding treated as authoritative.",
            prior=prior,
            findings=(FindingDelta(
                key="observation under fallback",
                prior_state=None, match_outcome=None, independently_supported=True,
                touched_by_delta=True, severity=Severity.P1,
                expect_class=ChangeClass.NEWLY_INTRODUCED, expect_event="DETECTED",
                expect_state=_OPEN, expect_surfaced=True,
            ),),
            expect_mode=ReReviewMode.FULL_REVIEW,
            expect_decision=Decision.CHANGES_REQUIRED,
        ))
    add(Scenario(
        id="prior-state/no-new-delta-recognised",
        group="prior_state_failclosed",
        why="the one legitimate 'reviewed SHA == current head' case: a valid "
        "record under an unchanged standard → NO NEW DELTA, no duplicate review.",
        delta=DeltaShape(reviewed_sha_equals_head=True, standard_unchanged=True),
        expect_mode=ReReviewMode.NO_NEW_DELTA,
    ))

    # -- #61 identity integration points ---------------------------
    for idn_id, relation_tuple, why in (
        (
            "moved-defect-retains-identity",
            _MOVED_IDENT,
            "location change + definite MATCH → original identity re-propagates.",
        ),
        (
            "reformat-retains-identity",
            _REFORMAT_IDENT,
            "formatting-only churn does not shift identity.",
        ),
        (
            "distinct-defect-distinct-identity",
            _DISTINCT_IDENT,
            "a genuinely different defect at the same symbol gets its own identity.",
        ),
        (
            "same-line-not-same-finding",
            _SAME_LINE_DISTINCT_IDENT,
            "two different defects on one line are two identities (#64 §8).",
        ),
        (
            "ambiguous-identity-mints-fresh",
            _AMBIG_IDENT,
            "an AMBIGUOUS relationship never inherits — it mints fresh.",
        ),
        (
            "fail-closed-mints-fresh-despite-prior",
            _FAILCLOSED_IDENT,
            "a non-matchable descriptor mints fresh even when a prior id is offered.",
        ),
    ):
        add(Scenario(
            id=f"identity/{idn_id}",
            group="identity_integration",
            why=f"#61/#60 inside re-review: {why}",
            findings=(FindingDelta(
                key=idn_id,
                prior_state=_OPEN, match_outcome=_MATCH, still_present_evidence=True,
                touched_by_delta=True, identity=relation_tuple,
                expect_class=ChangeClass.MOVED,
            ),),
        ))
    add(Scenario(
        id="identity/disappearing-location-is-not-auto-resolution",
        group="identity_integration",
        why="#64 §8 / #62 §5: a prior finding not visible in the changed lines "
        "is UNCERTAIN (coverage unproven), never RESOLVED by disappearance.",
        findings=(FindingDelta(
            key="prior finding, site not in diff",
            prior_state=_OPEN, match_outcome=_NO_MATCH, resolution_evidence=None,
            touched_by_delta=False, severity=Severity.P1,
            expect_class=ChangeClass.UNCHANGED, expect_event="UNCERTAIN",
            expect_state=_OPEN, expect_surfaced=True,
        ),),
        expect_decision=Decision.CHANGES_REQUIRED,
    ))

    # -- Exact reviewed-HEAD / stale-state -------------------------
    add(Scenario(
        id="exact-head/result-bound-to-exact-reviewed-head",
        group="exact_head",
        why="review-status-enforcement.md: a status for the exact reviewed HEAD "
        "(reviewed == current) is publishable.",
        head_case=("sha-A", "sha-A", False),
        expect_status_published=True,
    ))
    add(Scenario(
        id="exact-head/head-advance-withholds-stale-status",
        group="exact_head",
        why="HEAD advanced during the pass: a status computed against the old "
        "SHA is never retargeted onto the new one.",
        head_case=("sha-A", "sha-B", False),
        expect_status_published=False,
    ))
    add(Scenario(
        id="exact-head/stale-review-clean-cannot-survive-changed-head",
        group="exact_head",
        why="a prior REVIEW CLEAN verdict does not carry to a changed HEAD — "
        "the clean status is withheld once reviewed != current.",
        head_case=("sha-A", "sha-B", True),
        expect_status_published=False,
    ))

    # -- Severity / decision (mechanical semantics unchanged) -------
    add(Scenario(
        id="severity/prior-p1-resolved-plus-new-p1-still-changes-required",
        group="severity_decision",
        why="#64 §5: every prior blocker resolving does not unblock the "
        "decision when a new P1 is introduced in the same pass.",
        findings=(
            FindingDelta(
                key="prior P1, resolved",
                prior_state=_OPEN, match_outcome=_NO_MATCH, resolution_evidence=FULL_BAR,
                touched_by_delta=True, severity=Severity.P1,
                expect_class=ChangeClass.FIXED, expect_event="RESOLVED",
                expect_state=_RESOLVED, expect_surfaced=False,
            ),
            FindingDelta(
                key="new P1",
                prior_state=None, match_outcome=None, independently_supported=True,
                touched_by_delta=True, severity=Severity.P1,
                expect_class=ChangeClass.NEWLY_INTRODUCED, expect_event="DETECTED",
                expect_state=_OPEN, expect_surfaced=True,
            ),
        ),
        expect_decision=Decision.CHANGES_REQUIRED,
    ))
    add(Scenario(
        id="severity/all-blockers-resolved-no-new-blocker-is-clean",
        group="severity_decision",
        why="#62 §8: with every prior P0/P1 RESOLVED and nothing new blocking, "
        "the mechanical decision is CLEAN.",
        findings=(
            FindingDelta(
                key="prior P0, resolved",
                prior_state=_OPEN, match_outcome=_NO_MATCH, resolution_evidence=FULL_BAR,
                touched_by_delta=True, severity=Severity.P0,
                expect_class=ChangeClass.FIXED, expect_event="RESOLVED",
                expect_state=_RESOLVED, expect_surfaced=False,
            ),
            FindingDelta(
                key="prior P1, resolved",
                prior_state=_OPEN, match_outcome=_NO_MATCH, resolution_evidence=FULL_BAR,
                touched_by_delta=True, severity=Severity.P1,
                expect_class=ChangeClass.FIXED, expect_event="RESOLVED",
                expect_state=_RESOLVED, expect_surfaced=False,
            ),
        ),
        expect_decision=Decision.CLEAN,
    ))
    add(Scenario(
        id="severity/newly-introduced-p2-only-not-blocking",
        group="severity_decision",
        why="a P2-only newly introduced finding does not become blocking just "
        "because it surfaced during a bounded pass.",
        findings=(FindingDelta(
            key="new P2",
            prior_state=None, match_outcome=None, independently_supported=True,
            touched_by_delta=True, severity=Severity.P2,
            expect_class=ChangeClass.NEWLY_INTRODUCED, expect_event="DETECTED",
            expect_state=_OPEN, expect_surfaced=True,
        ),),
        expect_decision=Decision.CLEAN,
    ))
    add(Scenario(
        id="severity/increases-while-open-stays-still-present",
        group="severity_decision",
        why="#62 §9 row 9: a P2 re-rated P1 on a still-present defect keeps its "
        "identity and produces STILL_PRESENT — severity change alone is no event.",
        lifecycle_ref=9,
        findings=(FindingDelta(
            key="retry defect, re-rated P2 -> P1",
            prior_state=_OPEN, match_outcome=_MATCH, still_present_evidence=True,
            touched_by_delta=False, severity=Severity.P1,
            expect_class=ChangeClass.UNCHANGED, expect_event="STILL_PRESENT",
            expect_state=_OPEN, expect_surfaced=True,
        ),),
        expect_decision=Decision.CHANGES_REQUIRED,
    ))
    add(Scenario(
        id="severity/decreases-while-open-stays-still-present",
        group="severity_decision",
        why="#62 §9 row 10: a P1 re-rated P2 on a still-present defect is still "
        "STILL_PRESENT / OPEN; the lower current impact just no longer blocks.",
        lifecycle_ref=10,
        findings=(FindingDelta(
            key="retry defect, re-rated P1 -> P2",
            prior_state=_OPEN, match_outcome=_MATCH, still_present_evidence=True,
            touched_by_delta=False, severity=Severity.P2,
            expect_class=ChangeClass.UNCHANGED, expect_event="STILL_PRESENT",
            expect_state=_OPEN, expect_surfaced=True,
        ),),
        expect_decision=Decision.CLEAN,
    ))
    add(Scenario(
        id="severity/reopened-blocker-blocks-by-current-impact",
        group="severity_decision",
        why="#62 §8: a reopened finding is classified from current impact; a "
        "reopened P1 blocks exactly as any other P1.",
        findings=(FindingDelta(
            key="reopened P1",
            prior_state=_RESOLVED, match_outcome=_MATCH, recurrence_evidence=True,
            severity=Severity.P1,
            expect_class=ChangeClass.REOPENED, expect_event="REOPENED",
            expect_state=_OPEN, expect_surfaced=True,
        ),),
        expect_decision=Decision.CHANGES_REQUIRED,
    ))

    return S


SCENARIOS = _scenarios()


# ---------------------------------------------------------------------------
# Driver: evaluate one scenario against an engine; return failure messages.
# ---------------------------------------------------------------------------


def _evaluate(scenario: Scenario, engine: Engine) -> list[str]:
    fails: list[str] = []

    mode = engine.resolve_mode(scenario.prior, scenario.delta, scenario.escalation)
    if mode != scenario.expect_mode:
        fails.append(f"mode: got {mode}, want {scenario.expect_mode}")

    if engine.escalates(scenario.escalation) != scenario.expect_escalation:
        fails.append("escalation flag mismatch")

    open_severities: list[Severity] = []
    for fd in scenario.findings:
        try:
            cls = engine.classify(**fd.classify_inputs())
            raised = False
        except Exception:  # a mutant may raise instead of returning a class
            cls, raised = None, True

        if fd.expect_error:
            if not raised:
                fails.append(f"{fd.key}: expected classify to refuse, got {cls}")
        else:
            if raised:
                fails.append(f"{fd.key}: classify raised unexpectedly")
            elif fd.expect_class is not None and cls != fd.expect_class:
                fails.append(f"{fd.key}: class {cls}, want {fd.expect_class}")

        event, state = engine.lifecycle(**fd.lifecycle_inputs())
        if fd.expect_event is not None and event != fd.expect_event:
            fails.append(f"{fd.key}: event {event!r}, want {fd.expect_event!r}")
        if fd.expect_state is not None and state != fd.expect_state:
            fails.append(f"{fd.key}: state {state}, want {fd.expect_state}")

        surfaced = state is LifecycleState.OPEN
        if fd.expect_surfaced is not None and surfaced != fd.expect_surfaced:
            fails.append(f"{fd.key}: surfaced={surfaced}, want {fd.expect_surfaced}")

        if fd.severity is not None and engine.contributes(event, state):
            open_severities.append(fd.severity)

        if fd.identity is not None and not engine.identity(*fd.identity):
            fails.append(f"{fd.key}: identity relation {fd.identity[0]!r} failed")

    if scenario.expect_decision is not None:
        decision = engine.decide(
            [_finding_stub(i, s) for i, s in enumerate(open_severities)]
        )
        if decision != scenario.expect_decision:
            fails.append(f"decision {decision}, want {scenario.expect_decision}")

    if scenario.head_case is not None:
        reviewed, current, clean = scenario.head_case
        published = engine.status_published(reviewed, current, clean)
        if published != scenario.expect_status_published:
            fails.append(
                f"status published={published}, want {scenario.expect_status_published}"
            )

    if scenario.assert_reportable_outside and engine.reportable_outside(True) is not True:
        fails.append("evidence-based observation outside the delta was not reportable")

    return fails


def _finding_stub(index: int, severity: Severity) -> DecisionFinding:
    """``derive_decision`` takes already-classified findings; the corpus only
    supplies severities, so wrap each surfaced one in a minimal stub."""
    return DecisionFinding(id=f"f{index}", severity=severity)


# ---------------------------------------------------------------------------
# 1. The real reference models must satisfy every fixture.
# ---------------------------------------------------------------------------


class ReReviewRegressionTests(unittest.TestCase):
    def test_every_scenario_holds_for_the_reference_models(self) -> None:
        for scenario in SCENARIOS:
            with self.subTest(scenario=scenario.id):
                fails = _evaluate(scenario, REAL)
                self.assertEqual(fails, [], f"{scenario.id}: {fails}\n  why: {scenario.why}")

    def test_scenario_ids_are_unique(self) -> None:
        ids = [s.id for s in SCENARIOS]
        self.assertEqual(sorted(ids), sorted(set(ids)))

    def test_fixture_expectations_are_internally_coherent(self) -> None:
        """Guards the fixture *data*: a stated change class and a stated
        lifecycle event must not contradict the #65 §3 change-class → event
        table. ``UNCHANGED`` is the one many-to-one row (carry-forward can be
        STILL_PRESENT / NO TRANSITION / UNCERTAIN) and is exempted."""
        nominal = {
            ChangeClass.FIXED: {"RESOLVED"},
            ChangeClass.MOVED: {"STILL_PRESENT"},
            ChangeClass.REOPENED: {"REOPENED"},
            ChangeClass.NEWLY_INTRODUCED: {"DETECTED"},
            ChangeClass.AMBIGUOUS: {"UNCERTAIN"},
        }
        for s in SCENARIOS:
            for fd in s.findings:
                if fd.expect_class in nominal and fd.expect_event is not None:
                    self.assertIn(
                        fd.expect_event,
                        nominal[fd.expect_class],
                        f"{s.id}/{fd.key}: {fd.expect_class} vs event {fd.expect_event!r}",
                    )

    def test_no_new_delta_maps_to_no_status(self) -> None:
        """The reviewed HEAD already owns its status — NO NEW DELTA publishes
        nothing new."""
        self.assertIs(map_verdict_to_status(Reasoning.NO_NEW_DELTA), StatusState.NONE)


# ---------------------------------------------------------------------------
# 2. Coverage guards — the corpus must span what #66 is required to cover.
# ---------------------------------------------------------------------------


class CoverageGuardTests(unittest.TestCase):
    def test_all_six_change_classes_are_exercised(self) -> None:
        seen = {
            fd.expect_class
            for s in SCENARIOS
            for fd in s.findings
            if fd.expect_class is not None
        }
        self.assertEqual(seen, set(ChangeClass))

    def test_all_fifteen_lifecycle_contract_scenarios_are_inherited(self) -> None:
        """finding-lifecycle-contract.md §10: #66 fixtures must inherit the
        fifteen §9 scenarios and assert state plus event."""
        refs = {s.lifecycle_ref for s in SCENARIOS if s.lifecycle_ref is not None}
        self.assertEqual(refs, set(range(1, 16)))

    def test_each_lifecycle_ref_asserts_state_and_event(self) -> None:
        for s in SCENARIOS:
            if s.lifecycle_ref is None:
                continue
            with self.subTest(scenario=s.id):
                self.assertTrue(
                    any(
                        fd.expect_event is not None and fd.expect_state is not None
                        for fd in s.findings
                    ),
                    f"{s.id} claims lifecycle §9 row {s.lifecycle_ref} but asserts "
                    "no (state, event) pair",
                )

    def test_required_groups_meet_their_floor(self) -> None:
        floors = {
            "unchanged": 3,
            "fixed": 3,
            "moved": 3,
            "reopened": 3,
            "newly_introduced": 3,
            "ambiguous": 5,
            "fix_induced_regression": 3,
            "blast_radius": 3,
            "settled_assumption": 3,
            "escalation": 4,
            "prior_state_failclosed": 6,
            "identity_integration": 6,
            "exact_head": 3,
            "severity_decision": 4,
        }
        counts: dict[str, int] = {}
        for s in SCENARIOS:
            counts[s.group] = counts.get(s.group, 0) + 1
        for group, floor in floors.items():
            self.assertGreaterEqual(counts.get(group, 0), floor, group)
        # No orphan groups outside the declared set.
        self.assertEqual(set(counts), set(floors))

    def test_corpus_is_substantive(self) -> None:
        self.assertGreaterEqual(len(SCENARIOS), 45)

    def test_every_escalation_trigger_is_covered_individually(self) -> None:
        covered = set()
        for s in SCENARIOS:
            if s.expect_mode is not ReReviewMode.ESCALATED_TO_FULL:
                continue
            for f in dataclasses.fields(EscalationSignals):
                if getattr(s.escalation, f.name):
                    covered.add(f.name)
        self.assertEqual(
            covered,
            {f.name for f in dataclasses.fields(EscalationSignals)},
        )

    def test_fail_closed_covers_every_precondition(self) -> None:
        """Each stateful-delta-rereview.md §2 precondition has a fixture that
        drops exactly it and expects the full-review fallback."""
        toggled = set()
        default = PriorState()
        for s in SCENARIOS:
            if s.expect_mode is not ReReviewMode.FULL_REVIEW:
                continue
            for f in dataclasses.fields(PriorState):
                if getattr(s.prior, f.name) != getattr(default, f.name):
                    toggled.add(f.name)
        self.assertEqual(toggled, {f.name for f in dataclasses.fields(PriorState)})


# ---------------------------------------------------------------------------
# 3. Induced-regression / mutation check: each representative re-review bug
#    must be caught by >= 1 fixture, and must actually perturb an output.
# ---------------------------------------------------------------------------


def _mut_ambiguous_as_match(engine: Engine) -> Engine:
    """Bug: reconciliation treats an AMBIGUOUS #59 outcome as a MATCH — an
    uncertain continuation is silently converted into a confident transition."""

    def classify(**kw: object) -> ChangeClass:
        if kw.get("match_outcome") is MatchOutcome.AMBIGUOUS:
            kw = {**kw, "match_outcome": MatchOutcome.MATCH}
        return classify_change(**kw)  # type: ignore[arg-type]

    return engine._replace(classify=classify)


def _mut_moved_as_new(engine: Engine) -> Engine:
    """Bug: a matched-after-move finding is reported as newly introduced —
    manufacturing a false resolution of the original and a false detection."""

    def classify(**kw: object) -> ChangeClass:
        result = classify_change(**kw)  # type: ignore[arg-type]
        return ChangeClass.NEWLY_INTRODUCED if result is ChangeClass.MOVED else result

    return engine._replace(classify=classify)


def _mut_suppress_new_when_prior_resolved(engine: Engine) -> Engine:
    """Bug: a fix that resolves a prior finding is allowed to suppress a
    *different* new defect in the same pass — the new DETECTED finding is
    dropped from the decision set."""

    def contributes(event: str, state: Optional[LifecycleState]) -> bool:
        if event == "DETECTED":
            return False
        return _contributes_to_decision(event, state)

    return engine._replace(contributes=contributes)


def _mut_narrow_to_prior_finding_lines(engine: Engine) -> Engine:
    """Bug: re-review refuses to classify (or report) any observation that is
    not on lines the delta literally edited — attributable blast-radius
    regressions vanish."""

    def classify(**kw: object) -> ChangeClass:
        if kw.get("blast_radius_attributable") and not kw.get("touched_by_delta"):
            raise RuntimeError("narrowed to prior-finding lines only")
        return classify_change(**kw)  # type: ignore[arg-type]

    def reportable_outside(evidence_based: bool = True) -> bool:
        return False

    return engine._replace(classify=classify, reportable_outside=reportable_outside)


def _mut_no_escalation_on_invalidated_assumptions(engine: Engine) -> Engine:
    """Bug: the 'prior assumptions materially invalidated' trigger is ignored,
    so a delta that invalidates settled premises is still treated as bounded."""

    def escalates(signals: EscalationSignals) -> bool:
        return requires_escalation(
            dataclasses.replace(signals, prior_assumptions_materially_invalidated=False)
        )

    def resolve_mode(
        prior: PriorState, delta: DeltaShape, signals: EscalationSignals
    ) -> ReReviewMode:
        return resolve_rereview_mode(
            prior,
            delta,
            dataclasses.replace(signals, prior_assumptions_materially_invalidated=False),
        )

    return engine._replace(escalates=escalates, resolve_mode=resolve_mode)


def _mut_allow_stale_reviewed_sha(engine: Engine) -> Engine:
    """Bug: a broken-ancestry prior SHA (rebase/force-push) still unlocks a
    delta re-review instead of failing closed to a full review."""

    def resolve_mode(
        prior: PriorState, delta: DeltaShape, signals: EscalationSignals
    ) -> ReReviewMode:
        return resolve_rereview_mode(
            dataclasses.replace(prior, prior_sha_exists_and_is_ancestor=True),
            delta,
            signals,
        )

    return engine._replace(resolve_mode=resolve_mode)


def _mut_stale_clean_survives_head_advance(engine: Engine) -> Engine:
    """Bug: a status/verdict computed against the old HEAD is published against
    the new HEAD — a stale REVIEW CLEAN survives a changed HEAD."""

    def status_published(reviewed_sha: str, current_sha: str, clean: bool) -> bool:
        return _status_published(reviewed_sha, reviewed_sha, clean)

    return engine._replace(status_published=status_published)


MUTANTS: dict[str, Callable[[Engine], Engine]] = {
    "ambiguous-as-match": _mut_ambiguous_as_match,
    "moved-as-new": _mut_moved_as_new,
    "suppress-new-when-prior-resolved": _mut_suppress_new_when_prior_resolved,
    "narrow-to-prior-finding-lines": _mut_narrow_to_prior_finding_lines,
    "no-escalation-on-invalidated-assumptions": _mut_no_escalation_on_invalidated_assumptions,
    "allow-stale-reviewed-sha": _mut_allow_stale_reviewed_sha,
    "stale-clean-survives-head-advance": _mut_stale_clean_survives_head_advance,
}


class InducedRegressionTests(unittest.TestCase):
    def test_real_engine_passes_every_scenario(self) -> None:
        offenders = [s.id for s in SCENARIOS if _evaluate(s, REAL)]
        self.assertEqual(offenders, [])

    def test_each_mutant_is_caught_by_the_corpus(self) -> None:
        for name, mutate in MUTANTS.items():
            with self.subTest(mutant=name):
                mutant = mutate(REAL)
                caught = [s.id for s in SCENARIOS if _evaluate(s, mutant)]
                self.assertTrue(
                    caught, f"mutant {name!r} slipped past the entire corpus"
                )

    def test_each_mutant_actually_perturbs_an_output(self) -> None:
        """Non-vacuity: a mutant that changed nothing observable could never be
        'caught'. Each must move at least one engine output on some scenario."""
        for name, mutate in MUTANTS.items():
            with self.subTest(mutant=name):
                mutant = mutate(REAL)
                moved = any(
                    _evaluate(s, REAL) != _evaluate(s, mutant) for s in SCENARIOS
                )
                self.assertTrue(moved, f"mutant {name!r} is a no-op")


if __name__ == "__main__":
    unittest.main()
