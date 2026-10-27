#!/usr/bin/env python3
"""Delegated reviewers inherit the policy-loading contract (Issue #830).

Contract: shared/policies/agent-delegation.md ("Delegated reviewers inherit the
policy-loading contract"), shared/policies/parallel-review.md, and
shared/policies/review-stopping-criteria.md ("Mandatory-loading checkpoint").
"""

from __future__ import annotations

import re
import unittest

from runtime_platform.benchmark.reference import benchmark_policy_loading as pl
from tests.reference.review import decision_semantics as ds
from tests.reference.review.parallel_review import (
    AggregateOutcome,
    ReviewDimension,
    WorkerFinding,
    WorkerResult,
    WorkerStatus,
    aggregate,
)
from tests.support.paths import REPO_ROOT
from tests.support.policy_docs import extract_section, load_normalized_text as _norm

SHARED = REPO_ROOT / "shared" / "policies"
DELEGATION = SHARED / "agent-delegation.md"
PARALLEL = SHARED / "parallel-review.md"
STOPPING = SHARED / "review-stopping-criteria.md"
BRIEF = REPO_ROOT / "skills" / "github-pr-review" / "policies" / "reviewer-brief.md"
HEADING = "Delegated reviewers inherit the policy-loading contract"
D = ReviewDimension


def _section() -> str:
    return extract_section(_norm(DELEGATION), HEADING, "Reporting an event")


def _p2() -> WorkerFinding:
    return WorkerFinding(
        location="a.py:1", finding="naming", evidence="e", impact="i",
        candidate_severity=ds.Severity.P2, dimension=D.CORRECTNESS_REGRESSION,
    )


def _ok(dim: ReviewDimension, *, confirmed: bool = True, findings=()) -> WorkerResult:
    return WorkerResult(dim, WorkerStatus.OK, tuple(findings), loading_confirmed=confirmed)


class InheritanceIsStatedByReference(unittest.TestCase):
    def test_section_exists_and_points_at_the_canonical_homes(self) -> None:
        text = _section()
        self.assertTrue(text, "section missing")
        for needle in (
            "never narrows review obligations",
            "`SKILL.md` section 2",
            "Mandatory-loading checkpoint and pre-verdict recheck",
            "review-stopping-criteria.md",
        ):
            self.assertIn(needle.replace("`", ""), text.replace("`", ""))

    def test_covers_workers_and_subagents_that_render_a_decision(self) -> None:
        text = _section()
        self.assertIn("a read-only worker, or a sub-agent that runs the Skill and renders its own Decision", text)

    def test_inventory_is_referenced_not_duplicated(self) -> None:
        text = _section()
        for policy in ("severity.md", "evidence.md", "review-scope.md", "git-safety.md", "file-reviewability.md"):
            self.assertNotIn(policy, text)

    def test_skipped_partial_or_unconfirmed_loading_is_incomplete_with_precedence(self) -> None:
        text = _section()
        self.assertIn("A worker that skipped, partially read, or cannot confirm required loading makes the aggregating reviewer's coverage incomplete", text)
        self.assertIn("A sub-agent that runs the Skill and renders its own Decision renders REVIEW INCOMPLETE", text)
        self.assertIn("never override it", text)
        self.assertIn("REVIEW INCOMPLETE > CHANGES REQUIRED > REVIEW CLEAN".replace("`", ""), text.replace("`", ""))

    def test_brief_without_the_obligation_does_not_remove_it(self) -> None:
        text = _section()
        self.assertIn("names the Skill's section 2 and the checkpoint, and asks for a load confirmation", text)
        self.assertIn("does not remove the obligation", text)

    def test_parent_never_launders_a_delegates_gap(self) -> None:
        self.assertIn("treats a required file its delegate did not confirm as not loaded", _section())


class ParallelAndStoppingWiring(unittest.TestCase):
    def test_worker_input_carries_the_loading_contract_and_output_a_confirmation(self) -> None:
        text = _norm(PARALLEL)
        self.assertIn("Policy-loading contract", text)
        self.assertIn("Mandatory-loading checkpoint and pre-verdict recheck", text)
        self.assertIn("Each worker also returns one policy-loading confirmation, even with zero findings", text)
        self.assertIn("A missing confirmation counts as unconfirmed", text)

    def test_failure_table_makes_an_unconfirmed_required_worker_incomplete(self) -> None:
        text = _norm(PARALLEL)
        self.assertIn("skipped, partially read, or could not confirm required policy loading", text)

    def test_stopping_criteria_applies_the_checkpoint_to_delegates_without_a_new_trigger(self) -> None:
        text = _norm(STOPPING)
        self.assertIn("Delegation does not move this checkpoint", text)
        self.assertIn("did not confirm in full counts as not loaded", text)
        raw = STOPPING.read_text(encoding="utf-8")
        triggers = extract_section(raw, "Incomplete triggers (closed set, evaluated per-pass)", "Mandatory-loading checkpoint")
        self.assertEqual(len(re.findall(r"^\d\. \*\*", triggers, re.M)), 4)

    def test_reviewer_brief_is_untouched_presentation_only(self) -> None:
        self.assertIn("cannot change coverage accounting", _norm(BRIEF))


class DelegatedLoadingDecidesTheVerdict(unittest.TestCase):
    def test_unconfirmed_loading_prevents_review_clean(self) -> None:
        r = aggregate([_ok(D.CORRECTNESS_REGRESSION), _ok(D.SCOPE_REQUIREMENTS, confirmed=False)])
        self.assertIs(r.outcome, AggregateOutcome.INCOMPLETE)
        self.assertIsNone(r.decision)
        self.assertEqual(r.missing_dimensions, (D.SCOPE_REQUIREMENTS,))

    def test_full_diff_with_zero_blocking_findings_is_still_incomplete(self) -> None:
        r = aggregate([_ok(D.CORRECTNESS_REGRESSION, confirmed=False, findings=[_p2()])])
        self.assertEqual(ds.blocking_findings(()), ())
        self.assertIs(r.outcome, AggregateOutcome.INCOMPLETE)
        self.assertIsNot(r.decision, ds.Decision.CLEAN)

    def test_partial_or_truncated_loading_is_treated_as_incomplete(self) -> None:
        cut = pl.load_required(lambda p, first, n: [f"{p}:{i}" for i in range(first, min(200, first - 1 + (n or 60)) + 1)], {"severity.md": 500})
        self.assertEqual(cut.coverage, "incomplete")
        r = aggregate([_ok(D.CORRECTNESS_REGRESSION, confirmed=cut.coverage == "complete")])
        self.assertIs(r.outcome, AggregateOutcome.INCOMPLETE)

    def test_a_recovered_load_is_confirmed_and_grades_normally(self) -> None:
        ok = pl.load_required(lambda p, first, n: [f"{p}:{i}" for i in range(first, min(500, first - 1 + min(n or 120, 120)) + 1)], {"severity.md": 500})
        self.assertEqual(ok.coverage, "complete")
        r = aggregate([_ok(D.CORRECTNESS_REGRESSION, confirmed=ok.coverage == "complete", findings=[_p2()])])
        self.assertIs(r.outcome, AggregateOutcome.GRADED)
        self.assertIs(r.decision, ds.Decision.CLEAN)

    def test_confirmed_loading_leaves_existing_behavior_unchanged(self) -> None:
        blocking = WorkerFinding("b.py:2", "bug", "e", "i", ds.Severity.P1, D.CORRECTNESS_REGRESSION)
        self.assertIs(aggregate([_ok(D.CORRECTNESS_REGRESSION, findings=[blocking])]).decision, ds.Decision.CHANGES_REQUIRED)
        self.assertIs(aggregate([_ok(D.CORRECTNESS_REGRESSION)]).decision, ds.Decision.CLEAN)

    def test_incomplete_never_hides_a_finding_the_worker_produced(self) -> None:
        # Policy: findings already produced stay reported; the label alone changes.
        self.assertIn("Findings it did produce are still reported", _norm(PARALLEL))

    def test_optional_worker_with_unconfirmed_loading_is_recoverable_by_the_parent(self) -> None:
        opt = WorkerResult(D.TESTS_CONFIG, WorkerStatus.OK, (), required=False, loading_confirmed=False)
        r = aggregate([_ok(D.CORRECTNESS_REGRESSION), opt])
        self.assertIs(r.outcome, AggregateOutcome.GRADED)
        self.assertEqual(r.recovered_dimensions, (D.TESTS_CONFIG,))


if __name__ == "__main__":
    unittest.main()
