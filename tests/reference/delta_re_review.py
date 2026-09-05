#!/usr/bin/env python3
"""Test-only reference for delta re-review semantics (Issue #64).

Not runtime logic, not packaged — the packaged Skills are Markdown/YAML
only, matching tests/reference/finding_identity.py's own framing. The
packaged runtime installation is
skills/github-pr-review/policies/stateful-delta-rereview.md (Issue #65).

Mirrors docs/findings/delta-re-review-contract.md: change-class
classification, the delta-is-not-a-finding-boundary invariant,
blast-radius attribution, settled-assumption reconsideration, and the
semantic (non-numeric) escalation trigger.

Consumes the #58/#59/#60 identity/matching vocabulary and the #62
lifecycle vocabulary rather than re-deriving them — this module adds no
second identity or matching system. `MatchOutcome` and `LifecycleState`
are declared here only because #59's/#62's own outcome vocabulary is
documented, not (yet) exposed as an importable Python enum; their members
are named identically to the canonical docs on purpose.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class MatchOutcome(Enum):
    """#59's three matching outcomes (finding-matching-strategy.md)."""

    MATCH = "MATCH"
    NO_MATCH = "NO_MATCH"
    AMBIGUOUS = "AMBIGUOUS"


class LifecycleState(Enum):
    """#62's two persisted lifecycle states (finding-lifecycle-contract.md)."""

    OPEN = "OPEN"
    RESOLVED = "RESOLVED"


class ChangeClass(Enum):
    """The six #64 change classes (delta-re-review-contract.md, §2)."""

    UNCHANGED = "unchanged"
    FIXED = "fixed"
    MOVED = "moved"
    REOPENED = "reopened"
    NEWLY_INTRODUCED = "newly_introduced"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True)
class ResolutionEvidence:
    """The five requirements #62 §5 demands for `OPEN -> RESOLVED` (all
    must hold; this module does not weaken or shortcut any one of them)."""

    completed_review: bool = False
    verified_relevant_coverage: bool = False
    positive_absence_evidence: bool = False
    no_continuity_ambiguity: bool = False
    valid_prior_identity_and_state: bool = False

    def meets_bar(self) -> bool:
        return (
            self.valid_prior_identity_and_state
            and self.completed_review
            and self.verified_relevant_coverage
            and self.positive_absence_evidence
            and self.no_continuity_ambiguity
        )


def classify_change(
    *,
    prior_state: Optional[LifecycleState],
    match_outcome: Optional[MatchOutcome],
    still_present_evidence: bool = False,
    resolution_evidence: Optional[ResolutionEvidence] = None,
    recurrence_evidence: bool = False,
    touched_by_delta: bool = False,
    blast_radius_attributable: bool = False,
    independently_supported: bool = False,
) -> ChangeClass:
    """§2: classify one prior identity / current candidate relationship.

    This function only classifies; it never itself authorizes a lifecycle
    transition. #62 remains the sole owner of whether a transition is
    actually applied (`meets_bar()` above mirrors, not replaces, that
    gate).
    """
    # No prior identity at all: either a fresh detection or nothing to say.
    if prior_state is None:
        if independently_supported and (touched_by_delta or blast_radius_attributable):
            return ChangeClass.NEWLY_INTRODUCED
        raise ValueError("no prior identity and no independently supported observation")

    if match_outcome is MatchOutcome.AMBIGUOUS:
        return ChangeClass.AMBIGUOUS

    if prior_state is LifecycleState.OPEN:
        if match_outcome is MatchOutcome.MATCH and still_present_evidence:
            return ChangeClass.MOVED if touched_by_delta else ChangeClass.UNCHANGED
        if (
            match_outcome is MatchOutcome.NO_MATCH
            and resolution_evidence is not None
            and resolution_evidence.meets_bar()
        ):
            return ChangeClass.FIXED
        if not touched_by_delta and not blast_radius_attributable:
            return ChangeClass.UNCHANGED
        return ChangeClass.AMBIGUOUS

    if prior_state is LifecycleState.RESOLVED:
        if recurrence_evidence and match_outcome is MatchOutcome.MATCH:
            return ChangeClass.REOPENED
        return ChangeClass.UNCHANGED

    raise ValueError(f"unhandled prior_state: {prior_state!r}")


def is_reportable_outside_delta(*, evidence_based: bool) -> bool:
    """§3: the delta bounds re-analysis *effort*, never finding
    *eligibility*. A well-evidenced observation is reportable regardless
    of whether its location falls inside the literal diff — the only
    gate is whether it is evidence-based at all."""
    return evidence_based


@dataclass(frozen=True)
class BlastRadiusClaim:
    """§4: a candidate attribution from a changed location to another."""

    causal_mechanism: Optional[str] = None
    source_changed: bool = False


def is_attributable(claim: BlastRadiusClaim) -> bool:
    """§4: attribution requires a concrete, statable causal mechanism —
    proximity ("same file") or mere plausibility is not attribution."""
    return bool(claim.source_changed and claim.causal_mechanism and claim.causal_mechanism.strip())


@dataclass(frozen=True)
class SettledAssumption:
    """§6: a prior review's settled non-finding / architectural or
    behavioral assumption."""

    basis_touched_by_delta: bool = False
    blast_radius_attributable: bool = False


def remains_settled(assumption: SettledAssumption) -> bool:
    """§6: settled while the delta leaves its basis intact; reconsidered
    (not necessarily overturned) once the delta reaches it."""
    return not (assumption.basis_touched_by_delta or assumption.blast_radius_attributable)


@dataclass(frozen=True)
class EscalationSignals:
    """§7: the four semantic escalation triggers. Deliberately booleans,
    not counts/percentages/line-counts — #64 defines no numeric threshold
    because neither the Issue nor an existing canonical policy sets one."""

    prior_assumptions_materially_invalidated: bool = False
    blast_radius_untraceable: bool = False
    matching_broadly_unreliable: bool = False
    review_boundary_violated: bool = False


def requires_escalation(signals: EscalationSignals) -> bool:
    """§7: escalate when bounded delta re-review can no longer produce a
    trustworthy result — any one semantic trigger is sufficient."""
    return (
        signals.prior_assumptions_materially_invalidated
        or signals.blast_radius_untraceable
        or signals.matching_broadly_unreliable
        or signals.review_boundary_violated
    )
