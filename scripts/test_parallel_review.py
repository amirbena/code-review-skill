#!/usr/bin/env python3
"""Portable parallel-review planning, worker inputs, and aggregation.

Contract: shared/policies/parallel-review.md and
skills/github-pr-review/policies/parallel-review.md.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

import decision_semantics as ds
import parallel_review as pr
from parallel_review import (
    AggregateOutcome,
    ParallelCapability,
    ReviewDimension,
    ReviewSignals,
    WorkerFinding,
    WorkerResult,
    WorkerStatus,
    aggregate,
    build_worker_inputs,
    plan_review_execution,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
SHARED_POLICY = REPO_ROOT / "shared" / "policies" / "parallel-review.md"
GH_POLICY = REPO_ROOT / "skills" / "github-pr-review" / "policies" / "parallel-review.md"


def _text(path: Path) -> str:
    return re.sub(r"\s+", " ", path.read_text(encoding="utf-8").replace("**", "").replace("`", ""))


SMALL = ReviewSignals(
    changed_file_count=2,
    material_dimensions=(ReviewDimension.CORRECTNESS_REGRESSION,),
    shared_context_normalized=True,
    repository_instructions_resolved=True,
)
COMPLEX = ReviewSignals(
    changed_file_count=4,
    material_dimensions=(
        ReviewDimension.SCOPE_REQUIREMENTS,
        ReviewDimension.ARCHITECTURE_INVARIANTS,
        ReviewDimension.CORRECTNESS_REGRESSION,
        ReviewDimension.TESTS_CONFIG,
    ),
    dimensions_are_independent=True,
    expected_latency_reduction=True,
    shared_context_normalized=True,
    repository_instructions_resolved=True,
)


class PlanningTests(unittest.TestCase):
    def test_no_capability_is_always_sequential(self) -> None:
        for sig in (SMALL, COMPLEX):
            self.assertFalse(plan_review_execution(sig, ParallelCapability.NONE).parallel)

    def test_small_pr_is_sequential_even_with_capability(self) -> None:
        for cap in (ParallelCapability.SUBAGENTS, ParallelCapability.AGENT_TEAMS,
                    ParallelCapability.CONCURRENT_AGENTS):
            self.assertFalse(plan_review_execution(SMALL, cap).parallel)

    def test_complex_pr_with_capability_is_parallel(self) -> None:
        for cap in (ParallelCapability.SUBAGENTS, ParallelCapability.AGENT_TEAMS,
                    ParallelCapability.CONCURRENT_AGENTS):
            self.assertTrue(plan_review_execution(COMPLEX, cap).parallel)

    def test_many_trivial_files_do_not_trigger_parallelism(self) -> None:
        signals = ReviewSignals(
            changed_file_count=300,
            material_dimensions=(ReviewDimension.CORRECTNESS_REGRESSION,),
            shared_context_normalized=True,
            repository_instructions_resolved=True,
        )
        self.assertFalse(plan_review_execution(signals, ParallelCapability.SUBAGENTS).parallel)

    def test_small_architecture_heavy_review_may_be_parallel(self) -> None:
        signals = ReviewSignals(
            changed_file_count=3,
            material_dimensions=(
                ReviewDimension.ARCHITECTURE_INVARIANTS,
                ReviewDimension.CORRECTNESS_REGRESSION,
            ),
            dimensions_are_independent=True,
            expected_latency_reduction=True,
            shared_context_normalized=True,
            repository_instructions_resolved=True,
        )
        self.assertTrue(plan_review_execution(signals, ParallelCapability.SUBAGENTS).parallel)

    def test_unresolved_context_prevents_spawn(self) -> None:
        for context_ready, instructions_ready in ((False, True), (True, False)):
            unresolved = ReviewSignals(
                material_dimensions=COMPLEX.material_dimensions,
                dimensions_are_independent=True,
                expected_latency_reduction=True,
                shared_context_normalized=context_ready,
                repository_instructions_resolved=instructions_ready,
            )
            self.assertFalse(
                plan_review_execution(unresolved, ParallelCapability.SUBAGENTS).parallel
            )

    def test_sequential_dependency_prevents_parallelism(self) -> None:
        dependent = ReviewSignals(
            material_dimensions=COMPLEX.material_dimensions,
            dimensions_are_independent=False,
            expected_latency_reduction=True,
            shared_context_normalized=True,
            repository_instructions_resolved=True,
        )
        self.assertFalse(plan_review_execution(dependent, ParallelCapability.SUBAGENTS).parallel)

    def test_no_expected_latency_benefit_keeps_review_sequential(self) -> None:
        no_benefit = ReviewSignals(
            material_dimensions=COMPLEX.material_dimensions,
            dimensions_are_independent=True,
            expected_latency_reduction=False,
            shared_context_normalized=True,
            repository_instructions_resolved=True,
        )
        self.assertFalse(plan_review_execution(no_benefit, ParallelCapability.SUBAGENTS).parallel)


class SharedWorkerInputTests(unittest.TestCase):
    def test_all_workers_get_identical_normalized_inputs_except_dimension(self) -> None:
        dims = list(ReviewDimension)
        inputs = build_worker_inputs(
            review_target="PR#7 delta abc..def",
            review_context="ctx",
            repository_context_location="/tmp/pr-review-x/checkout",
            repository_snapshot_identity="head:def",
            repository_instruction_context_identity="instructions:123",
            existing_review_evidence="prior: none",
            dimensions=dims,
            policies_by_dimension={d: (f"{d.value}.md",) for d in dims},
        )
        keys = {wi.shared_key() for wi in inputs}
        self.assertEqual(len(keys), 1, "workers received different repo/context snapshots")
        self.assertTrue(all(wi.repository_instruction_context_identity == "instructions:123"
                            for wi in inputs))
        self.assertEqual(sorted(wi.dimension.value for wi in inputs),
                         sorted(d.value for d in dims))


class DeterministicAggregationTests(unittest.TestCase):
    def _results(self):
        f_arch = WorkerFinding("src/a.py:10", "interface violated", "ev", "im",
                               ds.Severity.P1, ReviewDimension.ARCHITECTURE_INVARIANTS)
        f_corr = WorkerFinding("src/b.py:3", "off-by-one", "ev", "im",
                               ds.Severity.P2, ReviewDimension.CORRECTNESS_REGRESSION)
        f_test = WorkerFinding("tests/x.py:1", "missing regression test", "ev", "im",
                               ds.Severity.P2, ReviewDimension.TESTS_CONFIG)
        return [
            WorkerResult(ReviewDimension.ARCHITECTURE_INVARIANTS, WorkerStatus.OK, (f_arch,)),
            WorkerResult(ReviewDimension.CORRECTNESS_REGRESSION, WorkerStatus.OK, (f_corr,)),
            WorkerResult(ReviewDimension.TESTS_CONFIG, WorkerStatus.OK, (f_test,)),
            WorkerResult(ReviewDimension.SCOPE_REQUIREMENTS, WorkerStatus.OK, ()),
            WorkerResult(ReviewDimension.EXISTING_REVIEW_RECONCILIATION, WorkerStatus.OK, ()),
        ]

    def test_completion_order_does_not_change_the_result(self) -> None:
        import itertools

        base = self._results()
        first = aggregate(base)
        for perm in itertools.islice(itertools.permutations(base), 12):
            self.assertEqual(aggregate(list(perm)), first)

    def test_decision_comes_only_from_the_aggregator(self) -> None:
        agg = aggregate(self._results())
        self.assertEqual(agg.outcome, AggregateOutcome.GRADED)
        self.assertEqual(agg.decision, ds.Decision.CHANGES_REQUIRED)  # a P1 present
        self.assertEqual([f.severity.name for f in agg.findings].count("P1"), 1)

    def test_duplicate_findings_reconcile_to_one_at_higher_severity(self) -> None:
        d1 = WorkerFinding("src/pay.py:42", "Validation can be bypassed", "e1", "i1",
                           ds.Severity.P2, ReviewDimension.CORRECTNESS_REGRESSION)
        d2 = WorkerFinding("SRC/pay.py:42 ", "validation  can be  bypassed", "e2", "i2",
                           ds.Severity.P1, ReviewDimension.SCOPE_REQUIREMENTS)
        agg = aggregate([
            WorkerResult(ReviewDimension.CORRECTNESS_REGRESSION, WorkerStatus.OK, (d1,)),
            WorkerResult(ReviewDimension.SCOPE_REQUIREMENTS, WorkerStatus.OK, (d2,)),
        ])
        self.assertEqual(len(agg.findings), 1)
        self.assertEqual(agg.findings[0].severity, ds.Severity.P1)


class FailureNeverBecomesCleanTests(unittest.TestCase):
    def test_required_worker_failure_yields_incomplete_not_clean(self) -> None:
        for bad in (WorkerStatus.FAILED, WorkerStatus.TIMED_OUT,
                    WorkerStatus.MALFORMED, WorkerStatus.CANCELLED):
            agg = aggregate([
                WorkerResult(ReviewDimension.CORRECTNESS_REGRESSION, WorkerStatus.OK, ()),
                WorkerResult(ReviewDimension.SCOPE_REQUIREMENTS, bad, (), required=True),
            ], parent_can_recover=True)
            self.assertEqual(agg.outcome, AggregateOutcome.INCOMPLETE, bad)
            self.assertIsNone(agg.decision)
            self.assertIn(ReviewDimension.SCOPE_REQUIREMENTS, agg.missing_dimensions)

    def test_optional_worker_failure_is_recovered_and_still_graded(self) -> None:
        agg = aggregate([
            WorkerResult(ReviewDimension.CORRECTNESS_REGRESSION, WorkerStatus.OK, ()),
            WorkerResult(ReviewDimension.TESTS_CONFIG, WorkerStatus.FAILED, (), required=False),
        ], parent_can_recover=True)
        self.assertEqual(agg.outcome, AggregateOutcome.GRADED)
        self.assertIn(ReviewDimension.TESTS_CONFIG, agg.recovered_dimensions)

    def test_optional_worker_failure_the_parent_cannot_recover_is_incomplete(self) -> None:
        agg = aggregate([
            WorkerResult(ReviewDimension.TESTS_CONFIG, WorkerStatus.FAILED, (), required=False),
        ], parent_can_recover=False)
        self.assertEqual(agg.outcome, AggregateOutcome.INCOMPLETE)

    def test_no_findings_with_all_workers_ok_is_a_real_clean(self) -> None:
        agg = aggregate([
            WorkerResult(d, WorkerStatus.OK, ()) for d in ReviewDimension
        ])
        self.assertEqual(agg.outcome, AggregateOutcome.GRADED)
        self.assertEqual(agg.decision, ds.Decision.CLEAN)


class SharedPolicyContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.t = _text(SHARED_POLICY)

    def test_semantic_equivalence_is_stated(self) -> None:
        self.assertIn(
            "sequential and parallel execution must produce equivalent final "
            "findings and decisions",
            self.t,
        )
        self.assertIn("Sequential execution is always a valid", self.t)

    def test_capability_detection_not_assumption(self) -> None:
        self.assertIn("Capability detection, not assumption", self.t)
        self.assertIn("no universal", self.t)
        self.assertIn("If detection is uncertain, treat the capability as none", self.t)

    def test_worker_contract_and_output_format(self) -> None:
        self.assertIn("bounded, normalized input", self.t)
        self.assertIn("structured candidate findings only", self.t)
        for field in ("affected file / location", "candidate severity",
                      "review dimension / source worker", "related prior finding"):
            self.assertIn(field, self.t)
        self.assertIn("do not invent JSON infrastructure", self.t)

    def test_centralized_aggregation_and_failure_table(self) -> None:
        self.assertIn("Centralized aggregation", self.t)
        self.assertIn("Worker completion order never affects the result", self.t)
        self.assertIn("Parallel capability unavailable", self.t)
        self.assertIn("Fall back to sequential analysis", self.t)
        self.assertIn("never a clean/approved result", self.t)
        self.assertIn("parallelism never manufactures REVIEW CLEAN", self.t)
        self.assertIn("Missing coverage is reported as missing", self.t)


class RuntimeRealisationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.t = _text(GH_POLICY)

    def test_claude_code_agent_teams_prerequisite_is_documented_not_set(self) -> None:
        self.assertIn("Claude Code", self.t)
        self.assertIn("CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1", self.t)
        self.assertIn("The Skill detects it; it never sets it", self.t)

    def test_cursor_subagents_and_compat_locations(self) -> None:
        self.assertIn("Cursor", self.t)
        self.assertIn("Subagents", self.t)
        self.assertIn(".cursor/agents/", self.t)
        self.assertIn(".claude/agents/", self.t)
        self.assertIn(".codex/agents/", self.t)

    def test_codex_concurrent_agents_and_worktree_separation(self) -> None:
        self.assertIn("Codex", self.t)
        self.assertIn("concurrent agents", self.t)
        self.assertIn("isolated worktrees", self.t)

    def test_shared_checkout_not_one_per_worker(self) -> None:
        self.assertIn("one clone, not one per worker", self.t)
        self.assertIn("same PR base/head state", self.t)
        self.assertIn("runtime execution isolation", self.t)
        self.assertIn("semantic repository snapshot", self.t)

    def test_sequential_fallback_never_fails_the_review(self) -> None:
        self.assertIn(
            "Sequential review is always the fallback and never fails the review",
            self.t,
        )

    def test_no_agent_definition_directories_were_added(self) -> None:
        for d in (".cursor/agents", ".claude/agents", ".codex/agents"):
            self.assertFalse((REPO_ROOT / d).exists(),
                             f"{d} added — Phase 2 keeps the contract in the packaged policy")


if __name__ == "__main__":
    unittest.main()
