#!/usr/bin/env python3
"""Prose checks pinning the PR-context contract in local-code-review's files
(canonical category names, status vocabulary, explicit conditionality).

Complements test_pr_context_reconciliation.py (decision-table logic).
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from tests.support.paths import REPO_ROOT
LOCAL_SKILL_DIR = REPO_ROOT / "skills/local-code-review"
PR_CONTEXT_POLICY = LOCAL_SKILL_DIR / "policies/pr-context.md"
INVOCATION_APPROVAL_POLICY = LOCAL_SKILL_DIR / "policies/invocation-approval.md"
SKILL_MD = LOCAL_SKILL_DIR / "SKILL.md"
RUNBOOK = LOCAL_SKILL_DIR / "runbooks/local-review.md"
REPORT_TEMPLATE = LOCAL_SKILL_DIR / "templates/local-review-report.md"
METADATA = LOCAL_SKILL_DIR / "metadata/skill.yaml"


def _text(path: Path) -> str:
    # Strip Markdown emphasis markers and collapse all whitespace
    # (including line wraps within a paragraph) to single spaces, so
    # assertions on phrasing don't break merely because a word is
    # bolded/italicized, or because prose wraps across source lines —
    # only the actual words and their order matter here.
    raw = path.read_text(encoding="utf-8").replace("**", "").replace("`", "")
    return re.sub(r"\s+", " ", raw)


class PRContextPolicyExistsAndIsScopedTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = _text(PR_CONTEXT_POLICY)

    def test_policy_file_exists(self) -> None:
        self.assertTrue(PR_CONTEXT_POLICY.is_file())

    def test_states_it_is_conditional_and_additive(self) -> None:
        self.assertIn(
            "If no PR reference is supplied, this file does not apply and "
            "nothing in this Skill's behavior changes",
            self.text,
        )

    def test_local_delta_established_before_pr_context_is_read(self) -> None:
        self.assertIn("Ordering: local scope first", self.text)
        self.assertIn(
            "never expands review scope to the PR's full historical diff",
            self.text,
        )

    def test_documents_all_five_classification_categories(self) -> None:
        for category in (
            "actionable defect/finding",
            "architectural/design decision",
            "implementation preference/suggestion",
            "informational comment",
            "resolved or obsolete feedback",
        ):
            self.assertIn(category, self.text)

    def test_thread_resolution_beats_earlier_comments(self) -> None:
        self.assertIn("the resolution/conclusion governs", self.text)

    def test_documents_all_four_finding_reconciliation_statuses(self) -> None:
        for status in (
            "still present",
            "resolved",
            "requires re-evaluation",
            "outside the current local review scope",
        ):
            self.assertIn(status, self.text)

    def test_evidence_not_authority_language_is_present(self) -> None:
        self.assertIn(
            "Existing reviewer findings are evidence and context, not authority",
            self.text,
        )

    def test_dedup_rule_is_present(self) -> None:
        self.assertIn(
            "it is not additionally reported as a separate, newly discovered "
            "finding",
            self.text,
        )

    def test_settled_decision_requires_actual_agreement_evidence(self) -> None:
        self.assertIn(
            "A decision is settled only when the PR context provides "
            "sufficient evidence it was actually agreed upon",
            self.text,
        )

    def test_settled_decision_challenge_requires_concrete_new_evidence(self) -> None:
        self.assertIn(
            "A settled decision may only be challenged when the current "
            "local delta carries concrete new evidence",
            self.text,
        )
        for evidence_kind in (
            "changed requirements",
            "correctness or reliability problem",
            "invalidated assumption",
            "newly discovered dependency or constraint",
            "security/performance concern",
            "newer explicit architectural decision",
        ):
            self.assertIn(evidence_kind, self.text)

    def test_documents_a_concrete_retrieval_example_scoped_to_the_delta(self) -> None:
        self.assertIn("### Retrieval (integration example)", self.text)
        self.assertIn("gh api --paginate", self.text)
        self.assertIn("reviewThreads { isResolved }", self.text)
        self.assertIn("this Skill is not bound to gh", self.text)
        self.assertIn(
            "Keep only the reviews, comments, and threads that touch files, "
            "hunks, or symbols in the current local delta",
            self.text,
        )

    def test_resolved_thread_is_not_proof_the_delta_is_correct(self) -> None:
        self.assertIn("### Authorship and resolved threads", self.text)
        self.assertIn(
            "A resolved thread is evidence of a past conclusion, not proof the "
            "current local delta is correct",
            self.text,
        )
        self.assertIn(
            "if the delta reintroduces the defect a resolved thread described, "
            "that is a still present finding",
            self.text,
        )
        self.assertIn(
            "automated / bot comments provide observations only and never by "
            "themselves settle a design decision",
            self.text,
        )

    def test_unresolved_pr_context_falls_back_without_blocking_review(self) -> None:
        self.assertIn("## Unavailable or unresolved PR context", self.text)
        self.assertIn(
            "proceed with the normal local review exactly as if no PR "
            "reference had been supplied",
            self.text,
        )
        self.assertIn(
            "never a reason to fail, block, or degrade the local review "
            "itself",
            self.text,
        )

    def test_read_only_github_boundary_is_explicit(self) -> None:
        self.assertIn("## Boundary with `github-pr-review`".replace("`", ""), self.text)
        self.assertIn(
            "no inline PR comments, no GitHub review submission, no "
            "Approve/Request Changes decision, no PR-level GitHub mutation "
            "of any kind",
            self.text,
        )

    def test_final_decision_ownership_is_retained_by_this_skill(self) -> None:
        self.assertIn(
            "this Skill's own final severity and", self.text,
        )
        self.assertIn(
            "reconciled PR findings and decisions inform it, they never "
            "substitute for it",
            self.text,
        )

    def test_invocation_approval_is_explicitly_not_bypassed(self) -> None:
        self.assertIn(
            "supplying a PR reference is never itself approval to invoke "
            "this Skill, and never bypasses the per-invocation, current-"
            "interaction, explicit-approval requirement",
            self.text,
        )

    def test_avoids_output_noise_for_resolved_and_preserved_context(self) -> None:
        self.assertIn(
            "Resolved findings and preserved (followed or intentionally "
            "superseded) decisions are not listed individually unless they "
            "materially affect",
            self.text,
        )


class InvocationApprovalPolicyUnaffectedTests(unittest.TestCase):
    """Governance: PR context must not weaken the pre-existing, unrelated
    approval contract. This pins the load-bearing sentences that already
    existed before PR-context support was added, guarding against an
    accidental future edit to invocation-approval.md made "for" this
    feature."""

    def setUp(self) -> None:
        self.text = _text(INVOCATION_APPROVAL_POLICY)

    def test_per_invocation_fresh_approval_invariant_is_still_present(self) -> None:
        self.assertIn(
            "local-code-review MUST NOT be invoked automatically", self.text
        )
        self.assertIn(
            "Each invocation requires fresh, explicit user approval scoped "
            "to that specific review run",
            self.text,
        )

    def test_approval_is_not_persistent_invariant_is_still_present(self) -> None:
        self.assertIn(
            "Approval for review N never authorizes review N+1", self.text
        )


class SkillMdConditionalityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = _text(SKILL_MD)

    def test_pr_reference_is_documented_as_optional_input(self) -> None:
        self.assertIn("Optional: a reference to an associated GitHub PR", self.text)
        self.assertIn(
            "When omitted, this Skill's behavior is exactly as if this "
            "input did not exist",
            self.text,
        )

    def test_pr_context_policy_only_loaded_when_pr_reference_supplied(self) -> None:
        self.assertIn(
            "This policy is never loaded or applied when no PR reference "
            "is supplied",
            self.text,
        )

    def test_mutation_boundary_still_forbids_github_writes_with_pr_context(self) -> None:
        self.assertIn(
            "reading PR review context is read-only and never becomes "
            "GitHub publication, an Approve/Request Changes decision, or "
            "any other GitHub mutation",
            self.text,
        )

    def test_review_ownership_section_is_unaffected(self) -> None:
        # Pre-existing invariant, unrelated to PR context — pinned so a
        # future edit doesn't accidentally fold PR-context ownership into
        # (or weaken) Agent-level review ownership.
        self.assertIn(
            "If another Code Review Agent already owns this local "
            "branch/scope, return REVIEW ALREADY OWNED",
            self.text,
        )


class RunbookConditionalStepTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = _text(RUNBOOK)

    def test_pr_context_step_is_explicitly_conditional(self) -> None:
        self.assertIn(
            "If, and only if, the caller supplied a PR reference", self.text
        )
        self.assertIn(
            "If no PR reference was supplied, skip this step entirely and "
            "proceed directly to the review step below",
            self.text,
        )

    def test_flow_diagram_shows_pr_branch_never_expanding_scope(self) -> None:
        self.assertIn("PR reference supplied?", self.text)
        self.assertIn("scope never expands to the PR", self.text)

    def test_dedup_guidance_appears_in_finding_classification_step(self) -> None:
        # The runbook no longer restates the full dedup rule inline — it
        # points to pr-context.md's own "Avoiding duplicate findings" (the
        # canonical owner) instead of repeating its text.
        self.assertIn(
            "reconciled PR context per those policies' own", self.text
        )
        self.assertIn(
            "rather than reporting the same underlying issue twice",
            self.text,
        )
        self.assertIn(
            "Avoiding duplicate findings",
            _text(PR_CONTEXT_POLICY),
        )

    def test_constraints_still_forbid_github_mutation(self) -> None:
        self.assertIn("Must not mutate GitHub state", self.text)


class ReportTemplateOptionalSectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = _text(REPORT_TEMPLATE)

    def test_pr_context_section_is_documented_as_omitted_by_default(self) -> None:
        self.assertIn("### PR Context", self.text)
        self.assertIn(
            "omitted entirely otherwise, including whenever no PR "
            "reference was supplied",
            self.text,
        )

    def test_rules_section_states_no_pr_case_is_the_default_backward_compatible_case(
        self,
    ) -> None:
        self.assertIn(
            "this is the no-PR backward-compatible case and the default",
            self.text,
        )

    def test_existing_decision_labels_are_unchanged(self) -> None:
        # Backward compatibility: the decision vocabulary a caller already
        # parses must not have grown a third value for the PR-context case.
        self.assertIn("REVIEW CLEAN", self.text)
        self.assertIn("CHANGES REQUIRED", self.text)

        # This check needs the literal `**` bold markers, which _text()
        # (used for self.text) deliberately strips — so it reads the raw
        # file directly rather than the normalized prose used elsewhere in
        # this test class.
        raw_text = REPORT_TEMPLATE.read_text(encoding="utf-8")
        decision_labels = set(re.findall(r"\*\*([A-Z][A-Z _]+)\*\*", raw_text))

        # Sanity: no unexpected all-caps decision-shaped token snuck in
        # beside the two documented labels.
        unexpected = decision_labels - {"REVIEW CLEAN", "CHANGES REQUIRED"}
        self.assertEqual(
            unexpected,
            set(),
            f"unexpected new bolded ALL-CAPS label(s) in template: {sorted(unexpected)!r}",
        )


class MetadataOptionalCapabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = METADATA.read_text(encoding="utf-8")

    def test_github_read_access_is_declared_optional_not_required(self) -> None:
        self.assertIn("github_read_access: optional", self.text)

    def test_core_capabilities_remain_required(self) -> None:
        self.assertIn("git: required", self.text)
        self.assertIn("local_repository_access: required", self.text)

    def test_output_contract_still_declares_no_github_mutation(self) -> None:
        self.assertIn("mutates_github: false", self.text)


if __name__ == "__main__":
    unittest.main()
