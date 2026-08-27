#!/usr/bin/env python3
"""Test-only reference for review-context normalization semantics.

Mirrors skills/local-code-review/policies/review-context.md.
Not runtime logic, not packaged.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import FrozenSet, Optional, Sequence


# --- Evidence hierarchy (review-context.md, "Evidence hierarchy") ---------


class EvidenceSource(Enum):
    CODE_DIFF_TESTS_CONFIG = 1
    REPOSITORY_INSTRUCTIONS = 2
    SUPPLIED_REVIEW_CONTEXT = 3
    REVIEWER_INFERENCE = 4


# Strongest first: a lower enum value outranks a higher one.
EVIDENCE_PRECEDENCE_ORDER: tuple[EvidenceSource, ...] = (
    EvidenceSource.CODE_DIFF_TESTS_CONFIG,
    EvidenceSource.REPOSITORY_INSTRUCTIONS,
    EvidenceSource.SUPPLIED_REVIEW_CONTEXT,
    EvidenceSource.REVIEWER_INFERENCE,
)


def stronger_source(a: EvidenceSource, b: EvidenceSource) -> EvidenceSource:
    """The stronger of two evidence sources (code > repo instructions >
    supplied context > inference)."""
    return a if a.value < b.value else b


def context_outranks_code(source: EvidenceSource) -> bool:
    """Whether `source` could override actual code evidence. Always False
    for every non-code source."""
    return (
        source != EvidenceSource.CODE_DIFF_TESTS_CONFIG
        and stronger_source(source, EvidenceSource.CODE_DIFF_TESTS_CONFIG) == source
    )


# --- Normalization (review-context.md, "Recommended internal
# normalization") --------------------------------------------------------


@dataclass(frozen=True)
class ReviewContext:
    """Illustrative normalized shape; only `raw_context` is required."""

    raw_context: str
    source_type: Optional[str] = None
    source_name: Optional[str] = None
    intended_behavior: Optional[str] = None
    acceptance_criteria: tuple[str, ...] = field(default_factory=tuple)
    constraints: tuple[str, ...] = field(default_factory=tuple)
    explicit_non_goals: tuple[str, ...] = field(default_factory=tuple)


class ReviewContextAvailability(Enum):
    NOT_SUPPLIED = "not_supplied"
    SUPPLIED = "supplied"


def should_block_local_review(availability: ReviewContextAvailability) -> bool:
    """Review context never blocks the local review — every state maps to
    the same answer."""
    del availability
    return False


def should_prompt_user_for_context(context_supplied: bool) -> bool:
    """Always False — review context is opt-in; the Skill never asks."""
    del context_supplied
    return False


# --- Scope discipline (review-context.md, "Scope discipline: no scope
# explosion" / "Using context to focus review attention") ------------------


def is_within_current_delta_scope(
    focus_area_touches: FrozenSet[str], local_delta_touches: FrozenSet[str]
) -> bool:
    """Exact overlap with the current local delta. An empty touch set is
    never in scope; context never expands scope beyond the delta."""
    if not focus_area_touches:
        return False
    return bool(focus_area_touches & local_delta_touches)


class NonGoalEffect(Enum):
    SUPPRESSES_MISSING_IMPLEMENTATION_FINDING = "suppresses_missing_implementation_finding"
    DOES_NOT_SUPPRESS_REGRESSION_FINDING = "does_not_suppress_regression_finding"


def apply_explicit_non_goal(
    *, would_be_missing_implementation_finding: bool, introduces_regression: bool
) -> Optional[NonGoalEffect]:
    """A non-goal suppresses a missing-implementation finding for the
    out-of-scope work, but never a regression the change introduces."""
    if introduces_regression:
        return NonGoalEffect.DOES_NOT_SUPPRESS_REGRESSION_FINDING
    if would_be_missing_implementation_finding:
        return NonGoalEffect.SUPPRESSES_MISSING_IMPLEMENTATION_FINDING
    return None


# --- Context mismatch vs. implementation defect (review-context.md,
# "Context mismatch vs. implementation defect") ----------------------------


class MismatchClassification(Enum):
    IMPLEMENTATION_VIOLATES_REQUIREMENT = "implementation_violates_requirement"
    CONTEXT_STALE_OR_CONFLICTS_WITH_ARCHITECTURE = "context_stale_or_conflicts_with_architecture"
    REQUIREMENT_AMBIGUOUS = "requirement_ambiguous"
    OUTSIDE_CURRENT_DIFF = "outside_current_diff"


def classify_mismatch(
    *,
    implementation_clearly_contradicts_requirement: bool,
    context_conflicts_with_repository_architecture: bool,
    requirement_is_ambiguous: bool,
    requirement_targets_code_outside_current_diff: bool,
) -> MismatchClassification:
    """Classify a context/implementation discrepancy. Check order matters:
    a clear violation first (the only unconditional-finding case), then
    stale context, then ambiguity, then out-of-diff."""
    if implementation_clearly_contradicts_requirement:
        return MismatchClassification.IMPLEMENTATION_VIOLATES_REQUIREMENT
    if context_conflicts_with_repository_architecture:
        return MismatchClassification.CONTEXT_STALE_OR_CONFLICTS_WITH_ARCHITECTURE
    if requirement_is_ambiguous:
        return MismatchClassification.REQUIREMENT_AMBIGUOUS
    return MismatchClassification.OUTSIDE_CURRENT_DIFF


def should_report_as_unconditional_finding(classification: MismatchClassification) -> bool:
    """Only a clear implementation violation is an unconditional finding;
    the other cases are notes, not automatic findings."""
    return classification == MismatchClassification.IMPLEMENTATION_VIOLATES_REQUIREMENT


# --- Output-section inclusion (review-context.md, "Output") ---------------


def context_section_required(
    context_supplied: bool,
    *,
    focused_a_finding: bool = False,
    surfaced_a_mismatch: bool = False,
    non_goal_prevented_a_false_gap: bool = False,
) -> bool:
    """The "Context" section appears only when context was supplied *and*
    it materially shaped the review."""
    if not context_supplied:
        return False
    return focused_a_finding or surfaced_a_mismatch or non_goal_prevented_a_false_gap


# --- Governance: this module's own shape never grows GitHub-mutation,
# approval-bypass, or context-overrides-code capability ---------------------

PROHIBITED_CAPABILITY_NAME_FRAGMENTS: FrozenSet[str] = frozenset(
    {
        "publish",
        "submit",
        "post_",
        "approve",
        "request_changes",
        "merge",
        "delete",
        "push",
        "commit",
        "bypass_approval",
        "skip_approval",
        "auto_approve",
        "override_ownership",
        "context_overrides_code",
        "trust_context_over_code",
        "assume_implemented",
    }
)
