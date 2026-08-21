#!/usr/bin/env python3
"""Reference/test implementation of review-context normalization semantics.

Mirrors skills/local-code-review/policies/review-context.md. Pure
decision-table logic (no code understanding, no LLM reasoning) so
test_review_context.py can exercise the contract deterministically. This
is NOT production/runtime logic: the packaged `local-code-review` Skill
implements this behavior entirely through its policy/runbook contract
(review-context.md, SKILL.md section 2/3, runbook step 7) and does not import, invoke, or otherwise depend on this module at runtime.
No packaged Skill file imports Python, and this module is not part of
either packaged Skill archive (see scripts/package-skills.sh /
scripts/package-skills.ps1's local-code-review file list, which omits
scripts/). It exists solely so this repository's own test suite can
verify the policy's decision tables are internally consistent — the same
role pr_context_reconciliation.py plays for pr-context.md.

This module never determines whether described behavior actually exists in
the implementation, never assigns a finding's severity, and never decides
the final review decision — those require actually reading the code and
applying severity.md, which is `local-code-review`'s own job (see
review-context.md, "Evidence hierarchy": actual code/diff/tests/config
outranks supplied context). This module only encodes the normalization,
scope, and output-inclusion decision tables that policy defines once those
facts are known.
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


#: Strongest first, per policy. A lower enum value always outranks a higher
#: one when two sources disagree.
EVIDENCE_PRECEDENCE_ORDER: tuple[EvidenceSource, ...] = (
    EvidenceSource.CODE_DIFF_TESTS_CONFIG,
    EvidenceSource.REPOSITORY_INSTRUCTIONS,
    EvidenceSource.SUPPLIED_REVIEW_CONTEXT,
    EvidenceSource.REVIEWER_INFERENCE,
)


def stronger_source(a: EvidenceSource, b: EvidenceSource) -> EvidenceSource:
    """Return whichever of two evidence sources outranks the other.

    Per review-context.md, "Evidence hierarchy": code/diff/tests/config
    outranks repository instructions, which outranks supplied review
    context, which outranks reviewer inference. Supplied context never
    outranks actual implementation evidence.
    """
    return a if a.value < b.value else b


def context_outranks_code(source: EvidenceSource) -> bool:
    """Whether `source` could legitimately override actual code evidence.

    Per policy, only actual code/diff/tests/config sits above itself — no
    other source, including supplied review context, ever outranks it. This
    is the structural guard behind "do not state that something is
    implemented merely because the context says it should be."
    """
    return (
        source != EvidenceSource.CODE_DIFF_TESTS_CONFIG
        and stronger_source(source, EvidenceSource.CODE_DIFF_TESTS_CONFIG) == source
    )


# --- Normalization (review-context.md, "Recommended internal
# normalization") --------------------------------------------------------


@dataclass(frozen=True)
class ReviewContext:
    """Illustrative normalized shape for supplied review context.

    Every field but `raw_context` is optional, per policy — a short,
    already-concrete context block needs no further structure.
    """

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
    """Review context — present or absent — never blocks the local review.

    Mirrors pr_context_reconciliation.should_block_local_review: every state
    maps to the same answer, by design, per review-context.md's backward-
    compatibility guarantee.
    """
    del availability
    return False


def should_prompt_user_for_context(context_supplied: bool) -> bool:
    """This Skill never asks for context when none was supplied.

    Per review-context.md, "Why this exists" / SKILL.md, section 2: review
    context is opt-in only. This always returns False regardless of input —
    a structural guarantee, not a conditional prompt policy.
    """
    del context_supplied
    return False


# --- Scope discipline (review-context.md, "Scope discipline: no scope
# explosion" / "Using context to focus review attention") ------------------


def is_within_current_delta_scope(
    focus_area_touches: FrozenSet[str], local_delta_touches: FrozenSet[str]
) -> bool:
    """Whether a context-derived focus area overlaps the current local delta.

    Mirrors pr_context_reconciliation.is_relevant_to_local_delta: an empty
    touches set is never in scope, and scope is exact-overlap, not fuzzy
    prefix/substring matching — context narrows attention *within* the
    delta, it never expands review scope beyond it.
    """
    if not focus_area_touches:
        return False
    return bool(focus_area_touches & local_delta_touches)


class NonGoalEffect(Enum):
    SUPPRESSES_MISSING_IMPLEMENTATION_FINDING = "suppresses_missing_implementation_finding"
    DOES_NOT_SUPPRESS_REGRESSION_FINDING = "does_not_suppress_regression_finding"


def apply_explicit_non_goal(
    *, would_be_missing_implementation_finding: bool, introduces_regression: bool
) -> Optional[NonGoalEffect]:
    """How a stated non-goal affects one candidate finding.

    Per review-context.md, "Explicit non-goals": "A stated non-goal narrows
    what's expected to be built; it never narrows what's expected to be
    safe." A non-goal legitimately suppresses a *missing-implementation*
    finding for the out-of-scope work, but never suppresses a genuine
    regression the current change introduces.
    """
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
    """Classify a context/implementation discrepancy per policy's four cases.

    Order matters and mirrors the policy's own presentation order — an
    ambiguous requirement is checked before assuming it targets out-of-diff
    code, and a clear implementation violation is checked first since it is
    the only case that alone justifies an unconditional finding.
    """
    if implementation_clearly_contradicts_requirement:
        return MismatchClassification.IMPLEMENTATION_VIOLATES_REQUIREMENT
    if context_conflicts_with_repository_architecture:
        return MismatchClassification.CONTEXT_STALE_OR_CONFLICTS_WITH_ARCHITECTURE
    if requirement_is_ambiguous:
        return MismatchClassification.REQUIREMENT_AMBIGUOUS
    return MismatchClassification.OUTSIDE_CURRENT_DIFF


def should_report_as_unconditional_finding(classification: MismatchClassification) -> bool:
    """Only a clear implementation violation is reported as an unconditional
    finding; the other three are reported as notes/uncertainty, never as an
    automatic finding against either side."""
    return classification == MismatchClassification.IMPLEMENTATION_VIOLATES_REQUIREMENT


# --- Output-section inclusion (review-context.md, "Output") ---------------


def context_section_required(
    context_supplied: bool,
    *,
    focused_a_finding: bool = False,
    surfaced_a_mismatch: bool = False,
    non_goal_prevented_a_false_gap: bool = False,
) -> bool:
    """Whether the optional "Context" report section should appear.

    Per review-context.md, "Output": omitted entirely when no context was
    supplied, and otherwise included only when it materially shaped the
    review — never merely because context exists.
    """
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
