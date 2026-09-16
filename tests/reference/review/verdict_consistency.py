#!/usr/bin/env python3
"""Test-only reference for the shared verdict-consistency comparator.

Mirrors shared/policies/verdict-consistency.md. A natural sibling of
decision_semantics.py: this module never re-derives a decision, it only
compares an already-finalized one against a rendered/submitted signal.
Not runtime logic, not packaged, and not imported by any Skill.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class RenderedSignal(str, Enum):
    """The closed set of fixed-vocabulary decision markers this MVP
    recognizes -- local report wording, GitHub-facing report wording
    (including a SEMI-mode "would publish" line), and the sanctioned
    coverage-incomplete outcome."""

    REVIEW_CLEAN = "REVIEW CLEAN"
    CHANGES_REQUIRED = "CHANGES REQUIRED"
    APPROVE = "Approve"
    REQUEST_CHANGES = "Request Changes"
    REVIEW_INCOMPLETE = "REVIEW INCOMPLETE"


class SubmittedEvent(str, Enum):
    """The literal GitHub review API `event` values this MVP recognizes."""

    APPROVE = "APPROVE"
    REQUEST_CHANGES = "REQUEST_CHANGES"
    COMMENT = "COMMENT"


# Which rendered signal a clean vs. blocking mechanical decision permits.
_CLEAN_SIGNALS = frozenset({RenderedSignal.REVIEW_CLEAN, RenderedSignal.APPROVE})
_BLOCKING_SIGNALS = frozenset(
    {RenderedSignal.CHANGES_REQUIRED, RenderedSignal.REQUEST_CHANGES}
)

# Which submitted event a clean vs. blocking mechanical decision permits.
_CLEAN_EVENTS = frozenset({SubmittedEvent.APPROVE})
_BLOCKING_EVENTS = frozenset({SubmittedEvent.REQUEST_CHANGES})


class Verdict(str, Enum):
    """Consistent, or inconsistent with which signal disagreed. Nothing
    else -- this comparator is read-only and has exactly these two
    output shapes."""

    CONSISTENT = "consistent"
    INCONSISTENT = "inconsistent"


@dataclass(frozen=True)
class ConsistencyResult:
    verdict: Verdict
    detail: str = ""


def check_rendered_signal(
    mechanical_decision: str,
    coverage_incomplete: bool,
    rendered_signal: RenderedSignal,
) -> ConsistencyResult:
    """Reconciliation points 1-3: compare the about-to-be-rendered signal
    against the already-finalized mechanical decision (or the sanctioned
    incomplete outcome, when coverage did not complete).

    `mechanical_decision` is whatever severity.md's derivation already
    produced (e.g. "REVIEW CLEAN" / "CHANGES REQUIRED"); this function
    never recomputes it from findings.
    """
    if coverage_incomplete:
        if rendered_signal is RenderedSignal.REVIEW_INCOMPLETE:
            return ConsistencyResult(Verdict.CONSISTENT)
        return ConsistencyResult(
            Verdict.INCONSISTENT,
            f"coverage is incomplete but rendered signal was {rendered_signal.value}",
        )

    if rendered_signal is RenderedSignal.REVIEW_INCOMPLETE:
        return ConsistencyResult(
            Verdict.INCONSISTENT,
            "rendered REVIEW INCOMPLETE but coverage was not incomplete",
        )

    is_clean_decision = mechanical_decision == "REVIEW CLEAN"
    permitted = _CLEAN_SIGNALS if is_clean_decision else _BLOCKING_SIGNALS
    if rendered_signal in permitted:
        return ConsistencyResult(Verdict.CONSISTENT)
    return ConsistencyResult(
        Verdict.INCONSISTENT,
        f"mechanical decision {mechanical_decision!r} disagrees with "
        f"rendered signal {rendered_signal.value!r}",
    )


def check_submitted_event(
    mechanical_decision: str,
    coverage_incomplete: bool,
    submitted_event: Optional[SubmittedEvent],
) -> ConsistencyResult:
    """Reconciliation point 4: compare the literal event object about to
    be submitted to GitHub's API against the same mechanically-derived
    decision checked pre-render.

    `submitted_event=None` means no formal event exists for this
    invocation (PASSIVE, or SEMI's non-submitting preview) -- this
    carve-out is never a mismatch; only a pre-render check (via
    `check_rendered_signal`) applies in that case. An informational
    self-review `COMMENT` is likewise never compared against the
    mechanical decision: it is not a formal APPROVE/REQUEST_CHANGES
    event and carries no decision claim of its own.
    """
    if submitted_event is None or submitted_event is SubmittedEvent.COMMENT:
        return ConsistencyResult(Verdict.CONSISTENT)

    if coverage_incomplete:
        # REVIEW INCOMPLETE never submits a formal APPROVE/REQUEST_CHANGES
        # event by policy; any formal event submitted alongside it is
        # already a mismatch this comparator must catch.
        return ConsistencyResult(
            Verdict.INCONSISTENT,
            f"coverage is incomplete but a formal event {submitted_event.value} "
            "was about to be submitted",
        )

    is_clean_decision = mechanical_decision == "REVIEW CLEAN"
    permitted = _CLEAN_EVENTS if is_clean_decision else _BLOCKING_EVENTS
    if submitted_event in permitted:
        return ConsistencyResult(Verdict.CONSISTENT)
    return ConsistencyResult(
        Verdict.INCONSISTENT,
        f"mechanical decision {mechanical_decision!r} disagrees with "
        f"submitted event {submitted_event.value!r}",
    )


# Governance: name fragments whose presence would mean a second,
# overridable or provisional decision path crept into this read-only
# comparator. test_verdict_consistency.py checks public signatures
# against these -- the same sets decision_semantics.py already defines.
PROHIBITED_OVERRIDE_PARAM_FRAGMENTS: frozenset[str] = frozenset(
    {
        "override",
        "force",
        "bypass",
        "ignore_severity",
        "manual_decision",
        "recommend_block",
        "should_block",
    }
)

PROHIBITED_CORRECTION_FRAGMENTS: frozenset[str] = frozenset(
    {
        "correction",
        "correct_decision",
        "provisional",
        "supersede",
        "resubmit_decision",
        "revise_decision",
    }
)
