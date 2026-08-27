#!/usr/bin/env python3
"""Coverage for the behavioral review-signal heuristics and their wiring
into both Skills.

Contract: shared/policies/review-scope.md ("Existing behavior ownership",
"Root-cause and model-completeness pass", "Failure state, retry safety, and
recovery", "Related changes as one unit").
Prose checks only — there is deliberately no second implementation of the
rules (see AGENTS.md section 18).
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from tests.support.paths import REPO_ROOT
SHARED_DIR = REPO_ROOT / "shared"
LOCAL_SKILL_DIR = REPO_ROOT / "skills/local-code-review"
GITHUB_SKILL_DIR = REPO_ROOT / "skills/github-pr-review"

REVIEW_SCOPE = SHARED_DIR / "policies/review-scope.md"
EVIDENCE = SHARED_DIR / "policies/evidence.md"
LOCAL_SKILL_MD = LOCAL_SKILL_DIR / "SKILL.md"
LOCAL_RUNBOOK = LOCAL_SKILL_DIR / "runbooks/local-review.md"
GITHUB_SKILL_MD = GITHUB_SKILL_DIR / "SKILL.md"
GITHUB_REASONING = GITHUB_SKILL_DIR / "policies/review-reasoning.md"
GITHUB_ACTIVE_RUNBOOK = GITHUB_SKILL_DIR / "runbooks/active-pr-review.md"
GITHUB_PASSIVE_RUNBOOK = GITHUB_SKILL_DIR / "runbooks/passive-pr-review.md"


def _text(path: Path) -> str:
    raw = path.read_text(encoding="utf-8").replace("**", "").replace("`", "")
    return re.sub(r"\s+", " ", raw)


def _section(text: str, heading: str, next_heading: str | None = None) -> str:
    start = text.index(heading)
    if next_heading is None:
        return text[start:]
    return text[start : text.index(next_heading, start)]


class RunbookReferencesCanonicalPoliciesTests(unittest.TestCase):
    """(1) local-review.md still references all canonical policies required
    for normal execution."""

    def setUp(self) -> None:
        self.text = _text(LOCAL_RUNBOOK)

    def test_always_applicable_shared_policies_are_referenced(self) -> None:
        for policy in (
            "review-scope.md",
            "severity.md",
            "evidence.md",
            "repository-instructions.md",
            "file-reviewability.md",
            "git-safety.md",
            "review-summary.md",
        ):
            self.assertIn(policy, self.text)

    def test_skill_owned_policies_are_referenced(self) -> None:
        for policy in ("invocation-approval.md", "repository-state.md"):
            self.assertIn(policy, self.text)

    def test_conditional_policies_are_referenced(self) -> None:
        for policy in ("review-context.md", "pr-context.md"):
            self.assertIn(policy, self.text)


class BehavioralHeuristicsReachableThroughReviewStepTests(unittest.TestCase):
    """(2) The new behavioral heuristics are reachable through the normal
    review phase, not disconnected prose."""

    def test_review_scope_defines_all_four_heuristics(self) -> None:
        text = _text(REVIEW_SCOPE)
        self.assertIn("## Existing behavior ownership", text)
        self.assertIn("## Root-cause and model-completeness pass", text)
        self.assertIn("## Failure state, retry safety, and recovery", text)
        self.assertIn("## Related changes as one unit", text)

    def test_local_skill_always_loads_review_scope_and_evidence(self) -> None:
        text = _text(LOCAL_SKILL_MD)
        self.assertIn("review-scope.md", text)
        self.assertIn("evidence.md", text)

    def test_local_runbook_review_step_names_both_new_sections(self) -> None:
        review_step = self.text = _text(LOCAL_RUNBOOK)
        step9 = self.text.find("9. Review the complete delta against")
        step10 = self.text.find("10. Classify findings per")
        self.assertGreater(step9, -1)
        self.assertGreater(step10, step9)
        step9_body = self.text[step9:step10]
        self.assertIn("Existing behavior ownership", step9_body)
        self.assertIn("Root-cause and model-completeness pass", step9_body)
        self.assertIn("Failure state, retry safety, and recovery", step9_body)
        self.assertIn("Related changes as one unit", step9_body)


class RunbookDoesNotDuplicateBehavioralPolicyTextTests(unittest.TestCase):
    """(3) The runbook does not need to duplicate full behavioral policy
    text — it names the governing sections and lets them govern."""

    def setUp(self) -> None:
        self.runbook_text = _text(LOCAL_RUNBOOK)
        self.policy_text = _text(REVIEW_SCOPE)

    def test_ownership_search_gating_language_lives_only_in_the_policy(self) -> None:
        gating_phrase = (
            "perform a targeted search, scoped to the current delta's "
            "realistic blast radius, for an existing canonical owner"
        )
        self.assertIn(gating_phrase, self.policy_text)
        self.assertNotIn(gating_phrase, self.runbook_text)

    def test_failure_retry_trigger_conditions_live_only_in_the_policy(self) -> None:
        trigger_phrase = (
            "It triggers on a concrete signal in the diff: more than one "
            "side-effecting step"
        )
        self.assertIn(trigger_phrase, self.policy_text)
        self.assertNotIn(trigger_phrase, self.runbook_text)

    def test_observability_hierarchy_prose_lives_only_in_the_policy(self) -> None:
        hierarchy_phrase = "never a generic \"add more logs\" recommendation"
        self.assertIn(hierarchy_phrase, self.policy_text)
        self.assertNotIn(hierarchy_phrase, self.runbook_text)


class OwnershipReuseIsTargetedTests(unittest.TestCase):
    """(shared semantics) ownership/reuse remains targeted, not generic
    DRY auditing."""

    def setUp(self) -> None:
        self.section = _section(
            _text(REVIEW_SCOPE),
            "## Existing behavior ownership",
            "## Failure state, retry safety, and recovery",
        )

    def test_search_is_scoped_to_blast_radius(self) -> None:
        self.assertIn("scoped to the current delta's realistic blast radius", self.section)

    def test_generic_dry_is_explicitly_disclaimed(self) -> None:
        self.assertIn("not generic", self.section)
        self.assertIn("not a repository-wide", self.section)

    def test_finding_requires_a_real_risk_not_mere_duplication(self) -> None:
        self.assertIn(
            "Raise a finding only when the evidence supports a real "
            "consistency, correctness, or maintainability risk",
            self.section,
        )


class RootCauseAndModelCompletenessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.section = _section(
            _text(REVIEW_SCOPE),
            "## Root-cause and model-completeness pass",
            "## Failure state, retry safety, and recovery",
        )

    def test_multiple_symptoms_trigger_a_structural_pass_without_fixed_threshold(self) -> None:
        for signal in (
            "related defects with the same failure shape",
            "individually correct helpers whose composition remains unsafe",
            "same invariant bypassed through multiple paths",
            "several special cases accumulating around one abstraction",
        ):
            self.assertIn(signal, self.section)
        self.assertIn("strong signal, not a mandatory numeric threshold", self.section)

    def test_model_completeness_requires_evidenced_missing_dimension(self) -> None:
        self.assertIn("an author without the authority kind being established", self.section)
        self.assertIn("Do not invent dimensions speculatively", self.section)
        self.assertIn("cannot represent a distinction required", self.section)

    def test_one_structural_finding_does_not_collapse_distinct_causes(self) -> None:
        self.assertIn("Prefer one structural finding", self.section)
        self.assertIn("Keep findings separate when causes or fixes are materially different", self.section)
        self.assertIn("semantic deduplication, not under-reporting", self.section)

    def test_canonical_repository_owner_is_preferred(self) -> None:
        self.assertIn("recommend fixing or consuming that owner", self.section)
        self.assertIn("instead of adding more local copies", self.section)

    def test_evidenced_upstream_fix_prefers_package_upgrade(self) -> None:
        self.assertIn("Upstream defect with an evidenced maintained fix", self.section)
        self.assertIn("prefer upgrading the same package to the fixed version", self.section)
        for evidence in ("release notes", "changelog", "advisory", "upstream issue"):
            self.assertIn(evidence, self.section)

    def test_unknown_fixed_version_is_never_invented(self) -> None:
        self.assertIn("Upstream defect without a verified fixed version", self.section)
        self.assertIn("do not invent a version", self.section)
        self.assertIn("state the limitation rather than guessing", self.section)

    def test_local_misuse_is_fixed_locally_not_upgraded_automatically(self) -> None:
        self.assertIn("Local misuse or unsupported configuration", self.section)
        self.assertIn("correct the local call, configuration, or ordering", self.section)
        self.assertIn("Package upgrades are not a blanket dependency rule", self.section)

    def test_breaking_upgrade_requires_migration_evidence(self) -> None:
        self.assertIn("Breaking or major-version upgrade", self.section)
        self.assertIn("account for migration and compatibility implications", self.section)
        self.assertIn("never present it as a trivial remediation", self.section)

    def test_rereview_verifies_invariant_across_related_paths(self) -> None:
        self.assertIn("verify on re-review that the corrected invariant covers the related paths", self.section)
        self.assertIn("same unfixed mechanism reconciles to the same finding", self.section)

    def test_existing_review_evidence_triggers_but_does_not_prove_root_cause(self) -> None:
        self.assertIn("may trigger this pass as Existing Review Evidence", self.section)
        self.assertIn("never widen the current Review Target", self.section)
        self.assertIn("never prove the root cause by themselves", self.section)

    def test_policy_stays_a_bounded_reasoning_rule(self) -> None:
        for excluded in (
            "finding graph",
            "clustering/similarity system",
            "dependency scanner",
            "automatic package resolver",
        ):
            self.assertIn(excluded, self.section)


class FailureRetryRecoverySignalTriggeredTests(unittest.TestCase):
    """(shared semantics) failure/retry/recovery remains signal-triggered."""

    def setUp(self) -> None:
        self.section = _section(
            _text(REVIEW_SCOPE),
            "## Failure state, retry safety, and recovery",
            "## Technology neutrality",
        )

    def test_absent_a_signal_the_section_does_not_apply(self) -> None:
        self.assertIn(
            "Absent such a signal, this section does not apply and requires no action",
            self.section,
        )

    def test_not_an_exhaustive_checklist(self) -> None:
        self.assertIn(
            "does not require enumerating every failure point in every review",
            self.section,
        )

    def test_recovery_must_be_evidenced_not_assumed(self) -> None:
        self.assertIn(
            'never accepted merely because "another process will eventually '
            'fix it," with no evidence that such a process exists',
            self.section,
        )


class ContractExceptionBlastRadiusTests(unittest.TestCase):
    """(shared semantics) contract/exception analysis follows actual
    callers/consumers within justified blast radius."""

    def setUp(self) -> None:
        self.section = _section(
            _text(REVIEW_SCOPE),
            "## Related changes as one unit",
            "## Existing behavior ownership",
        )

    def test_caller_visible_changes_are_followed_to_consumers(self) -> None:
        self.assertIn(
            "following a changed return value, exception, status/state "
            "value, or event/message to its actual callers or consumers "
            "within the diff's blast radius",
            self.section,
        )

    def test_swallowed_translated_and_fallback_exceptions_are_named(self) -> None:
        self.assertIn("swallowed", self.section)
        self.assertIn("translated/wrapped", self.section)
        self.assertIn("fallback value that can", self.section)


class ObservabilityApplicabilityGateTests(unittest.TestCase):
    """(shared semantics) observability has an explicit applicability gate;
    frontend/agent/policy changes are not automatically treated like
    backend operational flows."""

    def setUp(self) -> None:
        self.section = _section(
            _text(REVIEW_SCOPE),
            "### Observability is applicability-gated, not universal",
            "## Technology neutrality",
        )

    def test_gate_question_precedes_the_hierarchy(self) -> None:
        gate_index = self.section.index(
            "does this diff introduce or modify a production-operational "
            "failure mode for which detection or diagnosis is materially "
            "relevant"
        )
        hierarchy_index = self.section.index("already uses metrics, counters,")
        self.assertLess(gate_index, hierarchy_index)

    def test_commonly_relevant_examples_are_backend_operational(self) -> None:
        for example in (
            "backend/service runtime behavior",
            "payments or",
            "queues/events/webhooks",
            "external integrations",
            "asynchronous processing",
            "retries/redelivery",
            "background jobs",
        ):
            self.assertIn(example, self.section)

    def test_frontend_is_conditionally_relevant_not_default(self) -> None:
        self.assertIn("Conditionally relevant for frontend/client changes", self.section)
        self.assertIn(
            "Do not turn an ordinary frontend review into a search for "
            "backend-style metrics",
            self.section,
        )

    def test_policy_and_agent_instruction_changes_are_usually_secondary(self) -> None:
        self.assertIn("Usually secondary or not applicable", self.section)
        for example in (
            "agent instructions",
            "prompts",
            "review Skills",
            "policy Markdown",
            "static docs",
            "non-runtime configuration",
        ):
            self.assertIn(example, self.section)

    def test_runtime_agent_behavior_still_escalates_within_that_category(self) -> None:
        self.assertIn("agent orchestration", self.section)
        self.assertIn("tool-invocation failures", self.section)
        self.assertIn("scheduled/background execution", self.section)


class MetricsNotUniversallyRequiredTests(unittest.TestCase):
    """(shared semantics) metrics/alerts are not universally required; logs
    remain valid observability where appropriate; a materially undetectable
    high-impact failure can still be a finding."""

    def setUp(self) -> None:
        self.section = _section(
            _text(REVIEW_SCOPE),
            "## Failure state, retry safety, and recovery",
            "## Technology neutrality",
        )

    def test_established_metrics_check_is_participation_only(self) -> None:
        self.assertIn(
            "check only that the changed or new failure path participates "
            "in that existing mechanism consistently",
            self.section,
        )

    def test_logs_are_a_valid_mechanism_when_that_is_the_convention(self) -> None:
        self.assertIn(
            "If the surrounding code relies primarily on logs, check only "
            "whether the existing logging convention",
            self.section,
        )

    def test_generic_add_more_logs_is_explicitly_rejected(self) -> None:
        self.assertIn('never a generic "add more logs" recommendation', self.section)

    def test_undetectable_high_impact_failure_can_still_be_a_finding(self) -> None:
        self.assertIn(
            "a missing signal is a finding only when the diff introduces "
            "or materially changes a high-impact failure mode that would "
            "otherwise be effectively undiagnosable",
            self.section,
        )
        self.assertIn(
            "the concern is that the failure is undetectable, not merely "
            "that a particular metric is absent",
            self.section,
        )


class EvidenceScalingCrossReferenceTests(unittest.TestCase):
    """The new sections reuse existing blast-radius scaling rather than
    inventing a new evidentiary standard."""

    def test_evidence_md_cross_references_both_new_sections(self) -> None:
        text = _text(EVIDENCE)
        self.assertIn("Existing behavior ownership", text)
        self.assertIn("Failure state, retry safety, and recovery", text)
        self.assertIn("repository-wide audit", text)


class CrossSkillConsistencyTests(unittest.TestCase):
    """(cross-Skill) both Skills consume the intended shared behavioral
    policies; neither Skill contains an unnecessary fork/copy."""

    def test_both_skills_always_load_review_scope_and_evidence(self) -> None:
        local_text = _text(LOCAL_SKILL_MD)
        github_text = _text(GITHUB_SKILL_MD)
        self.assertIn("review-scope.md", local_text)
        self.assertIn("evidence.md", local_text)
        self.assertIn("review-scope.md", github_text)
        self.assertIn("evidence.md", github_text)

    def test_github_review_reasoning_forwards_generically_without_restating(
        self,
    ) -> None:
        text = _text(GITHUB_REASONING)
        self.assertIn("review-scope.md", text)
        self.assertIn("Root-Cause and Model-Completeness Review", text)
        self.assertIn("Root-cause and model-completeness pass", text)
        self.assertIn("this file does not restate their full text", text)
        # It must not have grown a private copy of the new section names —
        # it consumes them through the shared file, not by forking them.
        self.assertNotIn("## Existing behavior ownership", text)
        self.assertNotIn("## Failure state, retry safety, and recovery", text)

    def test_github_runbooks_apply_review_scope_in_full(self) -> None:
        for runbook in (GITHUB_ACTIVE_RUNBOOK, GITHUB_PASSIVE_RUNBOOK):
            text = _text(runbook)
            self.assertIn("review-scope.md", text)

    def test_no_skill_specific_policy_forks_the_shared_section_text(self) -> None:
        # Every Skill-specific policy file, in either Skill, must not
        # contain a private copy of either new shared heading — the only
        # occurrence of each heading in the whole tree is in review-scope.md
        # itself (checked positively above) and, incidentally, cross-linked
        # by name (never restated) from local-review.md/README docs.
        forbidden_headings = (
            "## Existing behavior ownership",
            "## Root-cause and model-completeness pass",
            "## Failure state, retry safety, and recovery",
        )
        skill_policy_dirs = [
            LOCAL_SKILL_DIR / "policies",
            GITHUB_SKILL_DIR / "policies",
        ]
        for policy_dir in skill_policy_dirs:
            for policy_file in sorted(policy_dir.glob("*.md")):
                text = policy_file.read_text(encoding="utf-8")
                for heading in forbidden_headings:
                    self.assertNotIn(
                        heading,
                        text,
                        f"{policy_file} must not fork {heading!r} from "
                        "shared/policies/review-scope.md",
                    )


class NoSecondSourceOfTruthTests(unittest.TestCase):
    """(ownership of policy logic) this suite does not require, and this
    repository does not contain, a second hand-maintained implementation
    of the behavioral heuristics."""

    def test_behavioral_review_signals_module_was_removed(self) -> None:
        for candidate in (
            REPO_ROOT / "tests" / "reference" / "behavioral_review_signals.py",
            REPO_ROOT / "tests" / "support" / "behavioral_review_signals.py",
        ):
            self.assertFalse(candidate.exists())

    def test_no_python_module_imports_a_behavioral_signals_mirror(self) -> None:
        this_file = Path(__file__).resolve()
        for base in (REPO_ROOT / "tests" / "reference", REPO_ROOT / "tests" / "support"):
            for py_file in sorted(base.glob("*.py")):
                if py_file.resolve() == this_file:
                    continue  # never scanned here, but keep the guard explicit
                text = py_file.read_text(encoding="utf-8")
                self.assertNotIn("behavioral_review_signals", text)


if __name__ == "__main__":
    unittest.main()
