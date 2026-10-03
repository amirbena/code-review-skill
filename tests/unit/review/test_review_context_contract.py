#!/usr/bin/env python3
"""Cross-Skill input-contract tests for Review Target, Review Context, and
Existing Review Evidence.

Pins what local-code-review and github-pr-review share, and that their
intentional differences stay distinct, using only the test-only references.
"""

from __future__ import annotations

import dataclasses
import unittest

from tests.reference.review.local_review_target import (
    CategoryScope,
    LocalReviewTarget,
    LocalReviewTargetError,
    SyncStatus,
    staged_scope_from_raw_diff,
)
from tests.reference.review.pr_checkout import InvalidShaError, NormalizedPrSource
from tests.reference.review.pr_context_reconciliation import (
    ArchitecturalDecision,
    DecisionStatus as LocalDecisionStatus,
    ExistingFinding,
    FindingReconciliation,
    FindingStatus,
    PRContextAvailability,
    ReviewedState,
    reconcile_decision,
    reconcile_finding,
    should_block_local_review,
    should_emit_separate_finding,
)
from tests.reference.review.current_evidence import CurrentEvidenceKind
from tests.reference.review.pr_review_evidence import (
    AuthorType,
    DecisionStatus as PrDecisionStatus,
    HistoryCompleteness,
    PriorFinding,
    PriorItemClass,
    Reconciliation,
    SettledDecision,
    history_blocks_review,
    reconcile_prior_finding,
    reconcile_settled_decision,
    should_suppress_as_duplicate,
)
from tests.reference.review.review_context import (
    ReviewContext,
    ReviewContextAvailability,
    context_section_required,
    should_block_review,
    should_prompt_user_for_context,
)

BASE_SHA = "a" * 40
HEAD_SHA = "b" * 40
NEW_HEAD_SHA = "c" * 40
TOUCHES = frozenset({"src/payments/charge.py"})
OTHER_TOUCHES = frozenset({"docs/marketing/landing-page-copy.md"})

# Neither a git object id: too short, too long, non-hex, empty.
INVALID_SHAS = ("abc12", "a" * 65, "z" * 40, "")


def make_local_target(**overrides) -> LocalReviewTarget:
    fields = dict(
        base_branch="main",
        base_sha=BASE_SHA,
        head_sha=HEAD_SHA,
        sync_status=SyncStatus.IN_SYNC,
        remote_head_sha=HEAD_SHA,
        committed=CategoryScope(included=True),
        staged=staged_scope_from_raw_diff(b""),
        unstaged=CategoryScope(included=True),
        untracked=CategoryScope(included=True),
    )
    fields.update(overrides)
    return LocalReviewTarget(**fields)


def make_pr_source(**overrides) -> NormalizedPrSource:
    fields = dict(
        repo_url="https://example.invalid/org/repo.git",
        pr_number=76,
        base_ref="main",
        base_sha=BASE_SHA,
        head_ref="feature/context",
        head_sha=HEAD_SHA,
        pull_ref="refs/pull/76/head",
    )
    fields.update(overrides)
    return NormalizedPrSource(**fields)


class ReviewTargetContractTests(unittest.TestCase):
    def test_both_targets_carry_the_same_base_and_head_identity(self) -> None:
        local, pr = make_local_target(), make_pr_source()
        self.assertEqual((local.base_sha, local.head_sha), (pr.base_sha, pr.head_sha))

    def test_shared_identity_fields_are_a_subset_of_each_target(self) -> None:
        shared = {"base_sha", "head_sha"}
        for cls in (LocalReviewTarget, NormalizedPrSource):
            with self.subTest(target=cls.__name__):
                self.assertLessEqual(shared, set(cls.__dataclass_fields__))

    def test_both_accept_short_and_full_object_ids(self) -> None:
        for sha in ("a" * 7, "a" * 40, "a" * 64):
            with self.subTest(sha=len(sha)):
                make_local_target(base_sha=sha, remote_head_sha=HEAD_SHA)
                make_pr_source(base_sha=sha)

    def test_local_only_state_is_not_collapsed_into_the_pr_target(self) -> None:
        local_only = {
            "sync_status",
            "remote_head_sha",
            "committed",
            "staged",
            "unstaged",
            "untracked",
        }
        self.assertFalse(local_only & set(NormalizedPrSource.__dataclass_fields__))
        self.assertLessEqual(local_only, set(LocalReviewTarget.__dataclass_fields__))

    def test_pr_only_identity_is_not_collapsed_into_the_local_target(self) -> None:
        pr_only = {"repo_url", "pr_number", "head_ref", "pull_ref"}
        self.assertFalse(pr_only & set(LocalReviewTarget.__dataclass_fields__))
        self.assertLessEqual(pr_only, set(NormalizedPrSource.__dataclass_fields__))

    def test_base_is_a_branch_locally_and_a_ref_on_the_pr(self) -> None:
        self.assertIn("base_branch", LocalReviewTarget.__dataclass_fields__)
        self.assertNotIn("base_ref", LocalReviewTarget.__dataclass_fields__)
        self.assertIn("base_ref", NormalizedPrSource.__dataclass_fields__)
        self.assertNotIn("base_branch", NormalizedPrSource.__dataclass_fields__)

    def test_only_the_local_target_projects_a_reviewed_state(self) -> None:
        self.assertTrue(hasattr(LocalReviewTarget, "to_reviewed_state"))
        self.assertFalse(hasattr(NormalizedPrSource, "to_reviewed_state"))

    def test_local_reviewed_state_reuses_the_target_base_and_head(self) -> None:
        state = make_local_target().to_reviewed_state()
        self.assertEqual((state.base_sha, state.head_sha), (BASE_SHA, HEAD_SHA))

    def test_targets_are_immutable(self) -> None:
        for target in (make_local_target(), make_pr_source()):
            with self.subTest(target=type(target).__name__):
                with self.assertRaises(dataclasses.FrozenInstanceError):
                    target.head_sha = NEW_HEAD_SHA

    def test_both_reject_an_invalid_base_or_head(self) -> None:
        for sha in INVALID_SHAS:
            for field in ("base_sha", "head_sha"):
                with self.subTest(field=field, sha=sha):
                    with self.assertRaises(LocalReviewTargetError):
                        make_local_target(**{field: sha})
                    with self.assertRaises(InvalidShaError):
                        make_pr_source(**{field: sha})

    def test_rejection_types_stay_skill_specific(self) -> None:
        self.assertFalse(issubclass(LocalReviewTargetError, InvalidShaError))
        self.assertFalse(issubclass(InvalidShaError, LocalReviewTargetError))

    def test_local_only_invalid_states_are_rejected(self) -> None:
        invalid = (
            dict(base_branch=""),
            dict(sync_status=SyncStatus.NO_TRACKING_BRANCH),  # remote HEAD set
            dict(remote_head_sha=NEW_HEAD_SHA),  # "in sync" but remote differs
            dict(committed=CategoryScope(included=False)),  # excluded, no reason
            dict(staged=CategoryScope(included=True)),  # staged, no fingerprint
        )
        for overrides in invalid:
            with self.subTest(overrides=sorted(overrides)):
                with self.assertRaises(LocalReviewTargetError):
                    make_local_target(**overrides)


class ReviewContextContractTests(unittest.TestCase):
    def test_one_context_shape_serves_both_skills(self) -> None:
        pr_sourced = ReviewContext(
            raw_context="Reject writes to a locked record.",
            source_type="pr-description",
            source_name="#76",
        )
        local_sourced = ReviewContext(
            raw_context="Reject writes to a locked record.",
            source_type="design-notes",
            source_name="notes.md",
        )
        self.assertIs(type(pr_sourced), type(local_sourced))
        self.assertEqual(pr_sourced.raw_context, local_sourced.raw_context)

    def test_only_raw_context_is_required(self) -> None:
        required = [
            f.name
            for f in dataclasses.fields(ReviewContext)
            if f.default is dataclasses.MISSING
            and f.default_factory is dataclasses.MISSING
        ]
        self.assertEqual(required, ["raw_context"])

    def test_context_has_no_skill_specific_fields(self) -> None:
        names = set(ReviewContext.__dataclass_fields__)
        for forbidden in ("pr_number", "head_sha", "base_sha", "staged", "reviewed_state"):
            self.assertNotIn(forbidden, names)

    def test_missing_context_never_blocks_either_skill(self) -> None:
        for availability in ReviewContextAvailability:
            self.assertFalse(should_block_review(availability))
        for availability in PRContextAvailability:
            self.assertFalse(should_block_local_review(availability))

    def test_neither_skill_prompts_for_context(self) -> None:
        for supplied in (True, False):
            self.assertFalse(should_prompt_user_for_context(supplied))

    def test_context_section_requires_supplied_and_material_context(self) -> None:
        self.assertFalse(context_section_required(False, focused_a_finding=True))
        self.assertFalse(context_section_required(True))
        self.assertTrue(context_section_required(True, surfaced_a_mismatch=True))

    def test_github_history_gaps_do_not_block_review_either(self) -> None:
        for completeness in HistoryCompleteness:
            self.assertFalse(history_blocks_review(completeness))

    def test_context_availability_and_history_completeness_stay_distinct(self) -> None:
        self.assertNotEqual(
            {s.name for s in PRContextAvailability},
            {s.name for s in HistoryCompleteness},
        )

    def test_empty_context_is_a_valid_input(self) -> None:
        # Context is opt-in: an empty string is still a well-formed value.
        self.assertEqual(ReviewContext(raw_context="").raw_context, "")

    def test_context_rejects_missing_raw_context(self) -> None:
        with self.assertRaises(TypeError):
            ReviewContext()  # type: ignore[call-arg]


class ExistingFindingContractTests(unittest.TestCase):
    """Local `reconcile_finding` against GitHub `reconcile_prior_finding`."""

    def local(self, **kwargs) -> FindingReconciliation:
        state = ReviewedState("f" * 64, BASE_SHA, HEAD_SHA)
        finding = ExistingFinding("F1", TOUCHES, reviewed_state=state)
        kwargs.setdefault("current_state", state)
        return reconcile_finding(finding, TOUCHES, **kwargs)

    def pr(self, **kwargs) -> Reconciliation:
        kwargs.setdefault("current_head_sha", HEAD_SHA)
        return reconcile_prior_finding(PriorFinding("F1", HEAD_SHA), **kwargs)

    def test_present_issue_is_still_valid_and_reuses_evidence(self) -> None:
        local = self.local(issue_still_present=True)
        pr = self.pr(present_on_current_head=True)
        self.assertEqual(local.status, FindingStatus.STILL_VALID)
        self.assertEqual(pr.item_class, PriorItemClass.STILL_RELEVANT)
        self.assertTrue(local.reuse_evidence and pr.reuse_prior_evidence)

    def test_absent_issue_is_resolved_without_reusing_evidence(self) -> None:
        local = self.local(issue_still_present=False)
        pr = self.pr(present_on_current_head=False)
        self.assertEqual(local.status, FindingStatus.RESOLVED)
        self.assertEqual(pr.item_class, PriorItemClass.RESOLVED)
        self.assertFalse(local.reuse_evidence or pr.reuse_prior_evidence)

    def test_undeterminable_presence_forces_reevaluation_in_both(self) -> None:
        local = self.local(issue_still_present=None)
        pr = self.pr(present_on_current_head=None)
        self.assertEqual(local.status, FindingStatus.REQUIRES_REEVALUATION)
        self.assertEqual(pr.item_class, PriorItemClass.STALE)
        self.assertTrue(local.reuse_evidence and pr.reuse_prior_evidence)

    def test_absent_after_material_churn_is_reevaluated_not_resolved(self) -> None:
        moved = ReviewedState("e" * 64, BASE_SHA, NEW_HEAD_SHA)
        local = self.local(
            issue_still_present=False,
            current_state=moved,
            surrounding_code_materially_changed=True,
        )
        pr = reconcile_prior_finding(
            PriorFinding("F1", HEAD_SHA),
            current_head_sha=NEW_HEAD_SHA,
            present_on_current_head=False,
            surrounding_code_materially_changed=True,
        )
        self.assertEqual(local.status, FindingStatus.REQUIRES_REEVALUATION)
        self.assertEqual(pr.item_class, PriorItemClass.STALE)

    def test_churn_without_a_changed_target_still_resolves_in_both(self) -> None:
        local = self.local(
            issue_still_present=False, surrounding_code_materially_changed=True
        )
        pr = self.pr(
            present_on_current_head=False, surrounding_code_materially_changed=True
        )
        self.assertEqual(local.status, FindingStatus.RESOLVED)
        self.assertEqual(pr.item_class, PriorItemClass.RESOLVED)

    def test_rediscovered_still_valid_finding_is_not_emitted_twice(self) -> None:
        local = self.local(issue_still_present=True)
        pr = self.pr(present_on_current_head=True, independently_rediscovered=True)
        self.assertFalse(
            should_emit_separate_finding(local, independently_discovered_same_issue=True)
        )
        self.assertTrue(should_suppress_as_duplicate(pr))

    def test_unrediscovered_finding_is_still_emitted(self) -> None:
        local = self.local(issue_still_present=True)
        self.assertTrue(
            should_emit_separate_finding(local, independently_discovered_same_issue=False)
        )
        self.assertFalse(
            should_suppress_as_duplicate(self.pr(present_on_current_head=True))
        )

    # --- intentional differences stay distinct ---

    def test_local_scopes_findings_to_the_delta_and_github_does_not(self) -> None:
        finding = ExistingFinding("F1", OTHER_TOUCHES)
        out = reconcile_finding(finding, TOUCHES, issue_still_present=True)
        self.assertEqual(out.status, FindingStatus.OUT_OF_SCOPE)
        self.assertFalse(out.reuse_evidence)
        self.assertNotIn("touches", PriorFinding.__dataclass_fields__)
        self.assertNotIn("OUT_OF_SCOPE", PriorItemClass.__members__)

    def test_local_identity_is_a_reviewed_state_and_github_identity_is_a_head(self) -> None:
        self.assertIn("reviewed_state", ExistingFinding.__dataclass_fields__)
        self.assertIn("reviewed_sha", PriorFinding.__dataclass_fields__)
        self.assertNotIn("reviewed_sha", ExistingFinding.__dataclass_fields__)
        self.assertNotIn("reviewed_state", PriorFinding.__dataclass_fields__)

    def test_local_unknown_reviewed_state_counts_as_changed(self) -> None:
        finding = ExistingFinding("F1", TOUCHES)  # no recorded identity
        out = reconcile_finding(
            finding,
            TOUCHES,
            issue_still_present=False,
            surrounding_code_materially_changed=True,
        )
        self.assertEqual(out.status, FindingStatus.REQUIRES_REEVALUATION)

    def test_local_status_vocabulary_is_not_the_github_class_vocabulary(self) -> None:
        local = {s.value for s in FindingStatus}
        pr = {c.value for c in PriorItemClass}
        self.assertNotEqual(local, pr)
        self.assertIn("duplicate", pr)
        self.assertNotIn("duplicate", local)

    def test_findings_carry_no_severity_in_either_skill(self) -> None:
        for cls in (FindingReconciliation, Reconciliation):
            self.assertNotIn("severity", cls.__dataclass_fields__)


class SettledDecisionContractTests(unittest.TestCase):
    def local(self, *, settled: bool, follows: bool, evidence=()):
        decision = ArchitecturalDecision("D1", TOUCHES, is_settled=settled)
        return reconcile_decision(
            decision,
            TOUCHES,
            delta_follows_decision=follows,
            current_evidence=evidence,
        )

    def pr(self, *, settled: bool, follows: bool, evidence=()):
        decision = SettledDecision(
            "D1",
            AuthorType.MAINTAINER,
            has_explicit_agreement=settled,
        )
        return reconcile_settled_decision(
            decision, current_delta_follows=follows, current_evidence=evidence
        )

    def test_unsettled_decision_never_constrains_either_skill(self) -> None:
        for follows in (True, False):
            local = self.local(settled=False, follows=follows)
            pr = self.pr(settled=False, follows=follows)
            self.assertEqual(local.status, LocalDecisionStatus.NOT_SETTLED)
            self.assertEqual(pr.status, PrDecisionStatus.NOT_SETTLED)
            self.assertFalse(local.emit_finding or pr.emit_finding)

    def test_settled_decision_is_followed_or_violated_in_both(self) -> None:
        self.assertEqual(
            self.local(settled=True, follows=True).status, LocalDecisionStatus.FOLLOWED
        )
        self.assertEqual(
            self.pr(settled=True, follows=True).status, PrDecisionStatus.FOLLOWED
        )
        local = self.local(settled=True, follows=False)
        pr = self.pr(settled=True, follows=False)
        self.assertEqual(local.status, LocalDecisionStatus.VIOLATED)
        self.assertEqual(pr.status, PrDecisionStatus.VIOLATED)
        self.assertTrue(local.emit_finding and pr.emit_finding)

    def test_overriding_current_evidence_supersedes_in_both(self) -> None:
        evidence = (CurrentEvidenceKind.NEWER_EXPLICIT_DECISION,)
        local = self.local(settled=True, follows=False, evidence=evidence)
        pr = self.pr(settled=True, follows=False, evidence=evidence)
        self.assertEqual(local.status, LocalDecisionStatus.SUPERSEDED)
        self.assertEqual(pr.status, PrDecisionStatus.SUPERSEDED)
        self.assertFalse(local.emit_finding or pr.emit_finding)

    def test_non_material_evidence_does_not_supersede_in_either(self) -> None:
        evidence = (CurrentEvidenceKind.STYLE_PREFERENCE,)
        self.assertEqual(
            self.local(settled=True, follows=False, evidence=evidence).status,
            LocalDecisionStatus.VIOLATED,
        )
        self.assertEqual(
            self.pr(settled=True, follows=False, evidence=evidence).status,
            PrDecisionStatus.VIOLATED,
        )

    def test_malformed_evidence_is_rejected_by_both(self) -> None:
        for settled in (True, False):
            with self.subTest(settled=settled):
                with self.assertRaises(ValueError):
                    self.local(settled=settled, follows=True, evidence=("bogus",))
                with self.assertRaises(ValueError):
                    self.pr(settled=settled, follows=True, evidence=("bogus",))

    # --- intentional differences stay distinct ---

    def test_github_settlement_needs_a_human_author_and_local_does_not_model_one(self) -> None:
        bot = SettledDecision(
            "D1", AuthorType.AUTOMATION_BOT, has_explicit_agreement=True
        )
        out = reconcile_settled_decision(bot, current_delta_follows=False)
        self.assertEqual(out.status, PrDecisionStatus.NOT_SETTLED)
        self.assertNotIn("established_by", ArchitecturalDecision.__dataclass_fields__)

    def test_only_the_local_decision_is_scoped_to_the_delta(self) -> None:
        decision = ArchitecturalDecision("D1", OTHER_TOUCHES, is_settled=True)
        out = reconcile_decision(decision, TOUCHES, delta_follows_decision=False)
        self.assertEqual(out.status, LocalDecisionStatus.OUT_OF_SCOPE)
        self.assertFalse(out.emit_finding)
        self.assertNotIn("OUT_OF_SCOPE", PrDecisionStatus.__members__)
        self.assertNotIn("touches", SettledDecision.__dataclass_fields__)


if __name__ == "__main__":
    unittest.main()
