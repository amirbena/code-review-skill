#!/usr/bin/env python3
"""Regression coverage for the behavioral review-signal heuristics added to
local-code-review (and, via shared policy reuse, github-pr-review).

Mirrors shared/policies/review-scope.md, "Existing behavior ownership" and
"Failure state, retry safety, and recovery," the tightened "Related changes
as one unit," and the complementary clarification in
shared/policies/evidence.md, "Findings beyond the changed lines." Exercises
the pure decision-table reference implementation in
behavioral_review_signals.py.

Run with:
    python3 scripts/test_behavioral_review_signals.py
"""

from __future__ import annotations

import inspect
import unittest
from pathlib import Path

import behavioral_review_signals as brs


REPO_ROOT = Path(__file__).resolve().parent.parent
REVIEW_SCOPE = (REPO_ROOT / "shared" / "policies" / "review-scope.md").read_text(encoding="utf-8")
EVIDENCE = (REPO_ROOT / "shared" / "policies" / "evidence.md").read_text(encoding="utf-8")
LOCAL_RUNBOOK = (
    REPO_ROOT / "skills" / "local-code-review" / "runbooks" / "local-review.md"
).read_text(encoding="utf-8")
LOCAL_SKILL = (REPO_ROOT / "skills" / "local-code-review" / "SKILL.md").read_text(
    encoding="utf-8"
)
GITHUB_SKILL = (REPO_ROOT / "skills" / "github-pr-review" / "SKILL.md").read_text(
    encoding="utf-8"
)
GITHUB_REASONING = (
    REPO_ROOT / "skills" / "github-pr-review" / "policies" / "review-reasoning.md"
).read_text(encoding="utf-8")


class PolicyWiringTests(unittest.TestCase):
    """(1) The Skill's normal review path actually consumes the policy
    containing the new heuristics — not disconnected prose the Skill runner
    is unlikely to encounter."""

    def test_review_scope_contains_both_new_sections(self) -> None:
        self.assertIn("## Existing behavior ownership", REVIEW_SCOPE)
        self.assertIn("## Failure state, retry safety, and recovery", REVIEW_SCOPE)

    def test_local_skill_always_loads_review_scope_and_evidence(self) -> None:
        # SKILL.md section 3, "Required Policy Loading" — always, not
        # conditional on any optional input.
        self.assertIn("review-scope.md", LOCAL_SKILL)
        self.assertIn("evidence.md", LOCAL_SKILL)

    def test_local_runbook_step_9_names_both_new_sections(self) -> None:
        self.assertIn("Existing behavior ownership", LOCAL_RUNBOOK)
        self.assertIn("Failure state, retry safety, and recovery", LOCAL_RUNBOOK)
        # Named alongside the pre-existing, already-wired invariants, not in
        # a disconnected location.
        review_step = LOCAL_RUNBOOK.find("9. Review the complete delta against")
        ownership_mention = LOCAL_RUNBOOK.find("Existing behavior ownership")
        next_step = LOCAL_RUNBOOK.find("10. Classify findings per")
        self.assertTrue(0 <= review_step < ownership_mention < next_step)

    def test_github_pr_review_inherits_through_shared_policy_reuse(self) -> None:
        # github-pr-review never forks or restates review-scope.md's
        # content — it forwards to it generically, so the new sections
        # apply automatically without any github-pr-review-specific edit.
        self.assertIn("review-scope.md", GITHUB_SKILL)
        self.assertIn("review-scope.md", GITHUB_REASONING)
        self.assertNotIn("Existing behavior ownership", GITHUB_REASONING)
        self.assertNotIn("Failure state, retry safety, and recovery", GITHUB_REASONING)
        self.assertIn("this file does not restate their full text", GITHUB_REASONING)

    def test_evidence_md_cross_references_the_same_blast_radius_scaling(self) -> None:
        self.assertIn("Existing behavior ownership", EVIDENCE)
        self.assertIn("Failure state, retry safety, and recovery", EVIDENCE)
        self.assertIn("repository-wide audit", EVIDENCE)


class OwnershipReuseTests(unittest.TestCase):
    """(2) Ownership/reuse is framed as targeted existing-behavior
    discovery, not generic DRY / repo-wide scanning."""

    def test_search_is_gated_on_a_concrete_behavior_resemblance_signal(self) -> None:
        self.assertFalse(brs.introduces_behavior_worth_an_ownership_search())
        self.assertTrue(
            brs.introduces_behavior_worth_an_ownership_search(is_validation_logic=True)
        )

    def test_finding_an_owner_with_no_divergence_is_harmless(self) -> None:
        classification = brs.classify_resemblance(
            canonical_owner_found=True, new_code_bypasses_or_diverges_from_it=False
        )
        self.assertEqual(classification, brs.BehaviorResemblance.HARMLESS_LOCAL_SIMILARITY)
        self.assertFalse(
            brs.should_report_ownership_finding(
                classification, has_consistency_or_correctness_or_maintainability_risk=True
            )
        )

    def test_no_owner_found_is_a_legitimate_independent_implementation(self) -> None:
        classification = brs.classify_resemblance(
            canonical_owner_found=False, new_code_bypasses_or_diverges_from_it=False
        )
        self.assertEqual(
            classification, brs.BehaviorResemblance.LEGITIMATE_INDEPENDENT_IMPLEMENTATION
        )

    def test_divergence_from_a_found_owner_without_risk_is_not_reported(self) -> None:
        # Generic DRY policing guard: duplication alone, without an
        # evidenced risk, must not become a finding.
        classification = brs.classify_resemblance(
            canonical_owner_found=True, new_code_bypasses_or_diverges_from_it=True
        )
        self.assertEqual(classification, brs.BehaviorResemblance.DUPLICATES_EXISTING_OWNER)
        self.assertFalse(
            brs.should_report_ownership_finding(
                classification, has_consistency_or_correctness_or_maintainability_risk=False
            )
        )

    def test_divergence_from_a_found_owner_with_risk_is_reported(self) -> None:
        classification = brs.classify_resemblance(
            canonical_owner_found=True, new_code_bypasses_or_diverges_from_it=True
        )
        self.assertTrue(
            brs.should_report_ownership_finding(
                classification, has_consistency_or_correctness_or_maintainability_risk=True
            )
        )

    def test_review_scope_explicitly_disclaims_generic_dry_and_repo_wide_audit(self) -> None:
        section = REVIEW_SCOPE[REVIEW_SCOPE.index("## Existing behavior ownership") :]
        self.assertIn("not generic", section)
        self.assertIn("not a repository-wide", section)


class FailureRetryRecoveryTriggerTests(unittest.TestCase):
    """(3) Failure/retry/recovery logic remains signal-triggered rather than
    mandatory for every diff."""

    def test_no_signal_means_not_triggered(self) -> None:
        self.assertFalse(brs.failure_retry_recovery_analysis_triggered())

    def test_any_single_signal_triggers_it(self) -> None:
        self.assertTrue(
            brs.failure_retry_recovery_analysis_triggered(has_multiple_side_effecting_steps=True)
        )
        self.assertTrue(
            brs.failure_retry_recovery_analysis_triggered(
                is_retryable_or_redeliverable_entry_point=True
            )
        )
        self.assertTrue(
            brs.failure_retry_recovery_analysis_triggered(
                external_call_combined_with_state_mutation=True
            )
        )

    def test_review_scope_states_the_section_does_not_apply_without_a_signal(self) -> None:
        section = REVIEW_SCOPE[
            REVIEW_SCOPE.index("## Failure state, retry safety, and recovery") :
        ]
        normalized = " ".join(section.split())
        self.assertIn(
            "Absent such a signal, this section does not apply and requires no action",
            normalized,
        )
        self.assertIn("does not require enumerating every failure point", normalized.lower())


class RecoveryEvidenceTests(unittest.TestCase):
    """Recovery must be evidenced, never merely assumed."""

    def test_unclaimed_recovery_is_not_trustworthy(self) -> None:
        claim = brs.RecoveryClaim(
            claimed=False, evidenced_in_repository=False, evidenced_path_covers_this_new_state=False
        )
        self.assertFalse(brs.recovery_claim_is_trustworthy(claim))

    def test_claimed_but_unevidenced_recovery_is_not_trustworthy(self) -> None:
        claim = brs.RecoveryClaim(
            claimed=True, evidenced_in_repository=False, evidenced_path_covers_this_new_state=False
        )
        self.assertFalse(brs.recovery_claim_is_trustworthy(claim))

    def test_evidenced_but_non_covering_recovery_is_not_trustworthy(self) -> None:
        claim = brs.RecoveryClaim(
            claimed=True, evidenced_in_repository=True, evidenced_path_covers_this_new_state=False
        )
        self.assertFalse(brs.recovery_claim_is_trustworthy(claim))

    def test_claimed_evidenced_and_covering_recovery_is_trustworthy(self) -> None:
        claim = brs.RecoveryClaim(
            claimed=True, evidenced_in_repository=True, evidenced_path_covers_this_new_state=True
        )
        self.assertTrue(brs.recovery_claim_is_trustworthy(claim))


class ObservabilityDoesNotMeanAlwaysAddAMetricTests(unittest.TestCase):
    """(4) Observability does not imply that every failure requires a new
    metric or alert."""

    def test_established_regime_only_checks_consistent_participation(self) -> None:
        self.assertFalse(
            brs.established_metrics_finding_required(
                new_or_changed_failure_path_participates_consistently=True
            )
        )
        self.assertTrue(
            brs.established_metrics_finding_required(
                new_or_changed_failure_path_participates_consistently=False
            )
        )

    def test_no_established_precedent_and_low_impact_never_forces_a_finding(self) -> None:
        self.assertFalse(
            brs.undetectable_failure_finding_required(
                has_established_observability_precedent=False,
                diff_introduces_or_materially_changes_high_impact_failure_mode=False,
                effectively_undiagnosable_via_anything_already_in_repo=True,
            )
        )

    def test_review_scope_explicitly_rejects_generic_add_more_logs_language(self) -> None:
        section = REVIEW_SCOPE[
            REVIEW_SCOPE.index("## Failure state, retry safety, and recovery") :
        ]
        self.assertIn('never a generic "add more logs" recommendation', section)
        self.assertIn(
            "the concern\n  is that the failure is undetectable, not merely that a "
            "particular\n  metric is absent.".replace("\n  ", " "),
            " ".join(section.split()),
        )


class ExistingLogsAreValidObservabilityTests(unittest.TestCase):
    """(5) Existing logs are a valid observability mechanism when
    appropriate."""

    def test_log_regime_is_selected_when_no_metrics_exist(self) -> None:
        regime = brs.observability_regime_for(
            system_has_established_metrics_or_alerts=False,
            system_relies_primarily_on_logs=True,
        )
        self.assertEqual(regime, brs.ObservabilityRegime.PRIMARILY_LOGS)

    def test_log_based_finding_only_when_convention_fails_to_distinguish_cases(self) -> None:
        self.assertFalse(
            brs.log_based_finding_required(
                existing_convention_distinguishes_meaningful_cases_for_this_change=True
            )
        )
        self.assertTrue(
            brs.log_based_finding_required(
                existing_convention_distinguishes_meaningful_cases_for_this_change=False
            )
        )

    def test_neither_regime_established_falls_through_to_none(self) -> None:
        regime = brs.observability_regime_for(
            system_has_established_metrics_or_alerts=False,
            system_relies_primarily_on_logs=False,
        )
        self.assertEqual(regime, brs.ObservabilityRegime.NONE_ESTABLISHED)


class UndetectableFailureCanStillQualifyTests(unittest.TestCase):
    """(6) A material undetectable failure may still qualify as a finding
    even without an existing metric precedent."""

    def test_high_impact_and_undiagnosable_with_no_precedent_is_a_finding(self) -> None:
        self.assertTrue(
            brs.undetectable_failure_finding_required(
                has_established_observability_precedent=False,
                diff_introduces_or_materially_changes_high_impact_failure_mode=True,
                effectively_undiagnosable_via_anything_already_in_repo=True,
            )
        )

    def test_high_impact_alone_without_undiagnosability_is_not_enough(self) -> None:
        self.assertFalse(
            brs.undetectable_failure_finding_required(
                has_established_observability_precedent=False,
                diff_introduces_or_materially_changes_high_impact_failure_mode=True,
                effectively_undiagnosable_via_anything_already_in_repo=False,
            )
        )

    def test_established_precedent_routes_through_the_precedent_check_instead(self) -> None:
        self.assertFalse(
            brs.undetectable_failure_finding_required(
                has_established_observability_precedent=True,
                diff_introduces_or_materially_changes_high_impact_failure_mode=True,
                effectively_undiagnosable_via_anything_already_in_repo=True,
            )
        )


class ContractExceptionSemanticsTests(unittest.TestCase):
    """(7) Contract/exception semantics direct investigation toward actual
    callers/consumers within relevant blast radius."""

    def test_any_caller_visible_change_requires_the_consumer_check(self) -> None:
        self.assertFalse(brs.caller_visible_change_requires_consumer_check())
        self.assertTrue(
            brs.caller_visible_change_requires_consumer_check(return_value_changed=True)
        )
        self.assertTrue(
            brs.caller_visible_change_requires_consumer_check(exception_behavior_changed=True)
        )
        self.assertTrue(
            brs.caller_visible_change_requires_consumer_check(status_or_state_value_changed=True)
        )
        self.assertTrue(
            brs.caller_visible_change_requires_consumer_check(event_or_message_shape_changed=True)
        )

    def test_unchanged_propagation_does_not_require_a_caller_trace(self) -> None:
        self.assertFalse(
            brs.exception_change_requires_caller_trace(
                brs.ExceptionSemanticsChange.PROPAGATED_UNCHANGED
            )
        )

    def test_swallowed_translated_and_fallback_all_require_a_caller_trace(self) -> None:
        for change in (
            brs.ExceptionSemanticsChange.SWALLOWED,
            brs.ExceptionSemanticsChange.TRANSLATED_OR_WRAPPED,
            brs.ExceptionSemanticsChange.FALLBACK_MASKS_FAILURE,
        ):
            with self.subTest(change=change):
                self.assertTrue(brs.exception_change_requires_caller_trace(change))

    def test_review_scope_names_swallowed_translated_and_fallback_explicitly(self) -> None:
        section = REVIEW_SCOPE[REVIEW_SCOPE.index("## Related changes as one unit") :]
        section = section[: section.index("## Existing behavior ownership")]
        self.assertIn("swallowed", section)
        self.assertIn("translated/wrapped", section)
        self.assertIn("fallback value that can", section)


class SeverityAndEvidenceStillGovernTests(unittest.TestCase):
    """(8) Existing severity and evidence rules still govern whether a
    concern becomes P0/P1/P2 or no finding — the new heuristics introduce no
    new severity or decision path."""

    def test_ownership_finding_gate_is_named_after_severity_classification(self) -> None:
        section = REVIEW_SCOPE[REVIEW_SCOPE.index("## Existing behavior ownership") :]
        self.assertIn("classified under", section)
        self.assertIn("severity.md", section)

    def test_failure_section_reuses_evidence_scaling_not_a_new_rule(self) -> None:
        section = REVIEW_SCOPE[
            REVIEW_SCOPE.index("## Failure state, retry safety, and recovery") :
        ]
        self.assertIn("evidence.md", section)

    def test_no_new_severity_or_decision_enum_is_introduced_by_this_module(self) -> None:
        # Governance: this module must not define its own Severity/Decision
        # concept — those remain owned by decision_semantics.py /
        # severity.md exclusively.
        public_names = {name for name in dir(brs) if not name.startswith("_")}
        self.assertNotIn("Severity", public_names)
        self.assertNotIn("Decision", public_names)
        self.assertNotIn("derive_decision", public_names)


class LocalFirstNoBlanketAuditTests(unittest.TestCase):
    """(9) The Skill remains local-first and does not acquire blanket
    repository-audit behavior."""

    def test_module_defines_no_unscoped_search_capability(self) -> None:
        public_names = {name for name in dir(brs) if not name.startswith("_")}
        offending = {
            name
            for name in public_names
            if any(
                fragment in name.lower()
                for fragment in brs.PROHIBITED_UNSCOPED_SEARCH_NAME_FRAGMENTS
            )
        }
        self.assertEqual(
            offending,
            set(),
            "behavioral_review_signals.py must never expose an unconditional, "
            "repository-wide-audit, or always-add-a-metric capability",
        )

    def test_no_function_accepts_an_unscoped_or_mandatory_everywhere_parameter(self) -> None:
        suspicious_param_fragments = ("repo_wide", "every_diff_mandatory", "scan_all")
        for name, obj in inspect.getmembers(brs):
            if not inspect.isfunction(obj):
                continue
            for param_name in inspect.signature(obj).parameters:
                lowered = param_name.lower()
                for fragment in suspicious_param_fragments:
                    self.assertNotIn(
                        fragment,
                        lowered,
                        f"{name}() must not accept an unscoped/mandatory-everywhere "
                        f"parameter, found: {param_name}",
                    )

    def test_review_scope_ties_both_new_sections_to_blast_radius_scaling(self) -> None:
        self.assertIn(
            "scale depth to\nactual risk exactly as".replace("\n", " "),
            " ".join(REVIEW_SCOPE.split()),
        )
        self.assertTrue(brs.ownership_and_failure_signal_search_is_scoped_to_blast_radius())

    def test_evidence_md_states_neither_new_section_licenses_a_repo_wide_audit(self) -> None:
        self.assertIn("neither is a license for a repository-wide audit", EVIDENCE)


if __name__ == "__main__":
    unittest.main()
