#!/usr/bin/env python3
"""Reference/test implementation of the behavioral review-signal heuristics.

Mirrors shared/policies/review-scope.md, "Existing behavior ownership" and
"Failure state, retry safety, and recovery," plus the related tightening in
"Related changes as one unit" (contract/exception semantics) and the
complementary scaling clarification in shared/policies/evidence.md,
"Findings beyond the changed lines."

Pure decision-table logic (no code understanding, no LLM reasoning) so
test_behavioral_review_signals.py can exercise the contract deterministically
— the same role review_context.py and decision_semantics.py play for their
own policies. This is NOT production/runtime logic: the packaged
`local-code-review` and `github-pr-review` Skills implement this behavior
entirely through shared/policies/review-scope.md and evidence.md (consumed
identically by both, per their own SKILL.md "Required Policy Loading"
sections and runbooks) and do not import, invoke, or otherwise depend on
this module at runtime. No packaged Skill file imports Python, and this
module is not part of either packaged Skill archive (see
scripts/package-skills.sh / scripts/package-skills.ps1's file lists, which
omit scripts/).

This module never determines whether a given diff actually exhibits a
signal (that requires reading code, which is a Code Review Skill's own job)
and never assigns a finding's final severity — that remains
shared/policies/severity.md's job. It only encodes the trigger/gating and
classification decision tables these two policy sections define once the
underlying facts are known, so this repository's own test suite can verify
they are internally consistent, signal-triggered rather than mandatory, and
never collapse into a generic "scan everything" or "always add a metric"
rule.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import FrozenSet


# --- Existing behavior ownership (review-scope.md, "Existing behavior
# ownership") -------------------------------------------------------------


def introduces_behavior_worth_an_ownership_search(
    *,
    is_business_or_domain_rule: bool = False,
    is_validation_logic: bool = False,
    is_calculation: bool = False,
    is_state_transition_logic: bool = False,
    is_integration_or_side_effect_handling: bool = False,
    is_helper_or_service_logic_representing_shared_semantics: bool = False,
) -> bool:
    """Whether the diff's own shape gives concrete reason to search for an
    existing canonical owner of the behavior it introduces.

    Per policy, the search is targeted — gated on the change actually
    resembling one of these categories, never performed unconditionally.
    """
    return any(
        (
            is_business_or_domain_rule,
            is_validation_logic,
            is_calculation,
            is_state_transition_logic,
            is_integration_or_side_effect_handling,
            is_helper_or_service_logic_representing_shared_semantics,
        )
    )


class BehaviorResemblance(Enum):
    HARMLESS_LOCAL_SIMILARITY = "harmless_local_similarity"
    LEGITIMATE_INDEPENDENT_IMPLEMENTATION = "legitimate_independent_implementation"
    DUPLICATES_EXISTING_OWNER = "duplicates_existing_owner"


def classify_resemblance(
    *,
    canonical_owner_found: bool,
    new_code_bypasses_or_diverges_from_it: bool,
) -> BehaviorResemblance:
    """Classify what a targeted ownership search turned up.

    Finding a canonical owner is not itself a defect — only diverging from
    or bypassing it while implementing equivalent semantics is.
    """
    if not canonical_owner_found:
        return BehaviorResemblance.LEGITIMATE_INDEPENDENT_IMPLEMENTATION
    if new_code_bypasses_or_diverges_from_it:
        return BehaviorResemblance.DUPLICATES_EXISTING_OWNER
    return BehaviorResemblance.HARMLESS_LOCAL_SIMILARITY


def should_report_ownership_finding(
    classification: BehaviorResemblance,
    *,
    has_consistency_or_correctness_or_maintainability_risk: bool,
) -> bool:
    """A duplicated-ownership finding requires both the classification and
    a real, evidenced risk — never raised merely because a second
    implementation exists (generic DRY policing is explicitly out of
    scope)."""
    return (
        classification is BehaviorResemblance.DUPLICATES_EXISTING_OWNER
        and has_consistency_or_correctness_or_maintainability_risk
    )


# --- Failure state, retry safety, and recovery (review-scope.md, "Failure
# state, retry safety, and recovery") --------------------------------------


def failure_retry_recovery_analysis_triggered(
    *,
    has_multiple_side_effecting_steps: bool = False,
    is_retryable_or_redeliverable_entry_point: bool = False,
    external_call_combined_with_state_mutation: bool = False,
) -> bool:
    """Whether the signal-triggered failure/retry/recovery reasoning move
    applies to this diff. Per policy: absent any of these signals, this
    section does not apply and requires no action — it is never run as an
    unconditional checklist against every diff."""
    return any(
        (
            has_multiple_side_effecting_steps,
            is_retryable_or_redeliverable_entry_point,
            external_call_combined_with_state_mutation,
        )
    )


@dataclass(frozen=True)
class RecoveryClaim:
    """A claim, found in code/comments/context, that some other process
    reconciles stranded state left by a partial failure."""

    claimed: bool
    evidenced_in_repository: bool
    evidenced_path_covers_this_new_state: bool


def recovery_claim_is_trustworthy(claim: RecoveryClaim) -> bool:
    """A recovery claim is accepted only when it is both evidenced in the
    repository and actually covers the new state — never merely assumed
    because "another process will eventually fix it."""
    if not claim.claimed:
        return False
    return claim.evidenced_in_repository and claim.evidenced_path_covers_this_new_state


# --- Proportional observability decision model (review-scope.md, same
# section) ------------------------------------------------------------------


class ObservabilityRegime(Enum):
    ESTABLISHED_METRICS_OR_ALERTS = "established_metrics_or_alerts"
    PRIMARILY_LOGS = "primarily_logs"
    NONE_ESTABLISHED = "none_established"


def established_metrics_finding_required(
    *, new_or_changed_failure_path_participates_consistently: bool
) -> bool:
    """Under an established metrics/alerts regime, the only question is
    consistent participation — never whether a new metric/alert should be
    invented."""
    return not new_or_changed_failure_path_participates_consistently


def log_based_finding_required(
    *, existing_convention_distinguishes_meaningful_cases_for_this_change: bool
) -> bool:
    """Under a log-primary regime, the only question is whether the
    existing logging convention still distinguishes the meaningful cases
    this change affects — never a generic "add more logs" recommendation."""
    return not existing_convention_distinguishes_meaningful_cases_for_this_change


def undetectable_failure_finding_required(
    *,
    has_established_observability_precedent: bool,
    diff_introduces_or_materially_changes_high_impact_failure_mode: bool,
    effectively_undiagnosable_via_anything_already_in_repo: bool,
) -> bool:
    """Absent any established precedent, a missing signal is only a finding
    when both the impact and the undiagnosability are real — never merely
    because a particular metric happens to be absent."""
    if has_established_observability_precedent:
        # Covered by established_metrics_finding_required /
        # log_based_finding_required instead.
        return False
    return (
        diff_introduces_or_materially_changes_high_impact_failure_mode
        and effectively_undiagnosable_via_anything_already_in_repo
    )


def observability_regime_for(
    *, system_has_established_metrics_or_alerts: bool, system_relies_primarily_on_logs: bool
) -> ObservabilityRegime:
    if system_has_established_metrics_or_alerts:
        return ObservabilityRegime.ESTABLISHED_METRICS_OR_ALERTS
    if system_relies_primarily_on_logs:
        return ObservabilityRegime.PRIMARILY_LOGS
    return ObservabilityRegime.NONE_ESTABLISHED


# --- Contract / exception semantics tightening (review-scope.md, "Related
# changes as one unit") ------------------------------------------------------


def caller_visible_change_requires_consumer_check(
    *,
    return_value_changed: bool = False,
    exception_behavior_changed: bool = False,
    status_or_state_value_changed: bool = False,
    event_or_message_shape_changed: bool = False,
) -> bool:
    """Any caller-visible contract change routes review to the actual
    callers/consumers within blast radius, per the tightened "Related
    changes as one unit" invariant."""
    return any(
        (
            return_value_changed,
            exception_behavior_changed,
            status_or_state_value_changed,
            event_or_message_shape_changed,
        )
    )


class ExceptionSemanticsChange(Enum):
    PROPAGATED_UNCHANGED = "propagated_unchanged"
    SWALLOWED = "swallowed"
    TRANSLATED_OR_WRAPPED = "translated_or_wrapped"
    FALLBACK_MASKS_FAILURE = "fallback_masks_failure"


#: Every change except leaving propagation unchanged is a signal worth
#: following to the caller — swallowing, translation/wrapping, and a
#: fallback value can each let a lower-level failure read as success higher
#: in the call chain.
EXCEPTION_CHANGES_REQUIRING_CALLER_TRACE: FrozenSet[ExceptionSemanticsChange] = frozenset(
    {
        ExceptionSemanticsChange.SWALLOWED,
        ExceptionSemanticsChange.TRANSLATED_OR_WRAPPED,
        ExceptionSemanticsChange.FALLBACK_MASKS_FAILURE,
    }
)


def exception_change_requires_caller_trace(change: ExceptionSemanticsChange) -> bool:
    return change in EXCEPTION_CHANGES_REQUIRING_CALLER_TRACE


# --- Blast-radius scaling shared with evidence.md ("Findings beyond the
# changed lines") — the same scaling governs both new sections identically
# to any other cross-file reasoning. -----------------------------------------


def ownership_and_failure_signal_search_is_scoped_to_blast_radius() -> bool:
    """Structural marker: both new heuristics are scaling-governed, never a
    repository-wide audit. Always True — this is a documented invariant,
    not a conditional policy; see PROHIBITED_UNSCOPED_SEARCH_NAME_FRAGMENTS
    below for the corresponding governance guard."""
    return True


# --- Governance: this module's own shape never grows an unconditional,
# repository-wide-audit, or "always add a metric" capability -----------------

PROHIBITED_UNSCOPED_SEARCH_NAME_FRAGMENTS: FrozenSet[str] = frozenset(
    {
        "repository_wide",
        "full_repo_scan",
        "scan_entire_codebase",
        "audit_all_files",
        "always_add_metric",
        "always_add_alert",
        "mandatory_for_every_diff",
        "require_metric_always",
    }
)
